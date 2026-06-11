"""
Manual admin job execution scope governance — source of truth for scope matrix,
target resolution, impact preview, and validation.

Scheduled runs are unaffected; this applies to POST /api/admin/jobs/run only.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.job_scope_registry import (
    get_job_run_scope,
    validate_manual_job_scope,
    validate_property_ids_belong_to_client,
)

logger = logging.getLogger(__name__)

MAX_MANUAL_BATCH_CLIENTS = 100


class ExecutionScopeType(str, Enum):
    CLIENT = "CLIENT"
    PROPERTY = "PROPERTY"
    CLIENT_GROUP = "CLIENT_GROUP"
    PLAN = "PLAN"
    JURISDICTION = "JURISDICTION"
    FILTERED_COHORT = "FILTERED_COHORT"
    PORTFOLIO_WIDE = "PORTFOLIO_WIDE"


PLAN_OPTIONS = [
    {"code": "PLAN_1_SOLO", "label": "Solo"},
    {"code": "PLAN_2_PORTFOLIO", "label": "Portfolio"},
    {"code": "PLAN_3_PRO", "label": "Professional"},
]

COHORT_FILTER_OPTIONS = [
    {"key": "overdue_only", "label": "Overdue requirements only"},
    {"key": "expiring_soon", "label": "Expiring within 30 days"},
    {"key": "risk_level_high", "label": "High risk signals"},
    {"key": "compliance_status_red", "label": "Red compliance status"},
]

# Per-job allowed execution scopes (authoritative matrix).
_JOB_ALLOWED_SCOPES: Dict[str, List[ExecutionScopeType]] = {
    "monthly_digest": [
        ExecutionScopeType.CLIENT,
        ExecutionScopeType.CLIENT_GROUP,
        ExecutionScopeType.PLAN,
        ExecutionScopeType.PORTFOLIO_WIDE,
    ],
    "daily_reminders": [
        ExecutionScopeType.CLIENT,
        ExecutionScopeType.PROPERTY,
        ExecutionScopeType.FILTERED_COHORT,
        ExecutionScopeType.PORTFOLIO_WIDE,
    ],
    "compliance_check_morning": [
        ExecutionScopeType.CLIENT,
        ExecutionScopeType.PROPERTY,
        ExecutionScopeType.JURISDICTION,
        ExecutionScopeType.PORTFOLIO_WIDE,
    ],
    "compliance_check_evening": [
        ExecutionScopeType.CLIENT,
        ExecutionScopeType.PROPERTY,
        ExecutionScopeType.JURISDICTION,
        ExecutionScopeType.PORTFOLIO_WIDE,
    ],
    "compliance_score_snapshots": [
        ExecutionScopeType.CLIENT,
        ExecutionScopeType.PLAN,
        ExecutionScopeType.PORTFOLIO_WIDE,
    ],
    "risk_signals_job": [
        ExecutionScopeType.CLIENT,
        ExecutionScopeType.PROPERTY,
    ],
    "rent_operations_daily_job": [
        ExecutionScopeType.CLIENT,
        ExecutionScopeType.PORTFOLIO_WIDE,
    ],
    "compliance_recalc_enqueue_property": [
        ExecutionScopeType.PROPERTY,
    ],
    "notification_retry_worker": [
        ExecutionScopeType.CLIENT,
        ExecutionScopeType.PORTFOLIO_WIDE,
    ],
}


def get_allowed_scopes(job_id: str) -> List[ExecutionScopeType]:
    if job_id in _JOB_ALLOWED_SCOPES:
        return list(_JOB_ALLOWED_SCOPES[job_id])
    # Global-only jobs: portfolio-wide manual run only (with governance).
    return [ExecutionScopeType.PORTFOLIO_WIDE]


def get_governance_matrix() -> Dict[str, Any]:
    rows = []
    for job_id, scopes in sorted(_JOB_ALLOWED_SCOPES.items()):
        rows.append(
            {
                "job_id": job_id,
                "allowed_scopes": [s.value for s in scopes],
                "portfolio_wide_allowed": ExecutionScopeType.PORTFOLIO_WIDE in scopes,
            }
        )
    return {
        "scope_types": [s.value for s in ExecutionScopeType],
        "plan_options": PLAN_OPTIONS,
        "cohort_filter_options": COHORT_FILTER_OPTIONS,
        "jobs": rows,
        "classification": "MANUAL_JOB_GOVERNANCE_CONVERGED",
    }


def get_job_governance(job_id: str) -> Dict[str, Any]:
    scopes = get_allowed_scopes(job_id)
    legacy = get_job_run_scope(job_id)
    return {
        "job_id": job_id,
        "allowed_scopes": [s.value for s in scopes],
        "portfolio_wide_allowed": ExecutionScopeType.PORTFOLIO_WIDE in scopes,
        "accepts_client_id": legacy.accepts_client_id,
        "accepts_property_id": legacy.accepts_property_id,
        "accepts_property_ids_filter": legacy.accepts_property_ids_filter,
        "manual_requires_property_id": legacy.manual_requires_property_id,
        "plan_options": PLAN_OPTIONS,
        "cohort_filter_options": COHORT_FILTER_OPTIONS,
    }


@dataclass
class ExecutionRequest:
    scope_type: ExecutionScopeType
    client_id: Optional[str] = None
    client_ids: Optional[List[str]] = None
    property_id: Optional[str] = None
    property_ids: Optional[List[str]] = None
    plan_code: Optional[str] = None
    jurisdiction: Optional[str] = None
    cohort_filter: Optional[str] = None
    portfolio_wide: bool = False
    portfolio_wide_confirmed: bool = False
    reason: Optional[str] = None


@dataclass
class ResolvedExecution:
    scope_type: ExecutionScopeType
    client_ids: List[str] = field(default_factory=list)
    property_id: Optional[str] = None
    property_ids: Optional[List[str]] = None
    is_portfolio_wide: bool = False
    batch_mode: bool = False


def infer_scope_type(
    *,
    scope_type: Optional[str],
    client_id: Optional[str],
    property_id: Optional[str],
    client_ids: Optional[List[str]],
    plan_code: Optional[str],
    jurisdiction: Optional[str],
    cohort_filter: Optional[str],
    portfolio_wide: bool,
) -> ExecutionScopeType:
    if scope_type:
        try:
            return ExecutionScopeType(str(scope_type).strip().upper())
        except ValueError:
            raise ValueError(f"Invalid scope_type '{scope_type}'")
    if portfolio_wide:
        return ExecutionScopeType.PORTFOLIO_WIDE
    if property_id and str(property_id).strip():
        return ExecutionScopeType.PROPERTY
    if client_ids and [x for x in client_ids if x and str(x).strip()]:
        return ExecutionScopeType.CLIENT_GROUP
    if plan_code and str(plan_code).strip():
        return ExecutionScopeType.PLAN
    if jurisdiction and str(jurisdiction).strip():
        return ExecutionScopeType.JURISDICTION
    if cohort_filter and str(cohort_filter).strip():
        return ExecutionScopeType.FILTERED_COHORT
    if client_id and str(client_id).strip():
        return ExecutionScopeType.CLIENT
    return ExecutionScopeType.PORTFOLIO_WIDE


def validate_scope_for_job(job_id: str, scope: ExecutionScopeType) -> Optional[str]:
    allowed = get_allowed_scopes(job_id)
    if scope not in allowed:
        allowed_labels = ", ".join(s.value for s in allowed)
        return (
            f"Job '{job_id}' does not support scope '{scope.value}'. "
            f"Allowed scopes: {allowed_labels}."
        )
    return None


def validate_execution_request(job_id: str, req: ExecutionRequest) -> Optional[str]:
    err = validate_scope_for_job(job_id, req.scope_type)
    if err:
        return err

    if req.scope_type == ExecutionScopeType.PORTFOLIO_WIDE:
        if not req.portfolio_wide and not req.portfolio_wide_confirmed:
            return (
                f"Job '{job_id}' requires explicit portfolio-wide scope. "
                "Set scope_type=PORTFOLIO_WIDE with portfolio_wide=true and portfolio_wide_confirmed=true."
            )
        if not (req.reason or "").strip() or len((req.reason or "").strip()) < 10:
            return "Support reason of at least 10 characters is required for portfolio-wide execution."
        if not req.portfolio_wide_confirmed:
            return "Portfolio-wide execution requires portfolio_wide_confirmed=true."
        return None

    if req.scope_type == ExecutionScopeType.CLIENT:
        if not (req.client_id or "").strip():
            return "CLIENT scope requires client_id."
    elif req.scope_type == ExecutionScopeType.PROPERTY:
        if not (req.property_id or "").strip():
            return "PROPERTY scope requires property_id."
    elif req.scope_type == ExecutionScopeType.CLIENT_GROUP:
        ids = [str(x).strip() for x in (req.client_ids or []) if x and str(x).strip()]
        if not ids:
            return "CLIENT_GROUP scope requires at least one client_id in client_ids."
        if len(ids) > MAX_MANUAL_BATCH_CLIENTS:
            return f"CLIENT_GROUP limited to {MAX_MANUAL_BATCH_CLIENTS} clients per manual run."
    elif req.scope_type == ExecutionScopeType.PLAN:
        if not (req.plan_code or "").strip():
            return "PLAN scope requires plan_code."
    elif req.scope_type == ExecutionScopeType.JURISDICTION:
        if not (req.jurisdiction or "").strip():
            return "JURISDICTION scope requires jurisdiction."
    elif req.scope_type == ExecutionScopeType.FILTERED_COHORT:
        if not (req.cohort_filter or "").strip():
            return "FILTERED_COHORT scope requires cohort_filter."

    if not (req.reason or "").strip() or len((req.reason or "").strip()) < 10:
        return "Support reason of at least 10 characters is required."

    # Legacy scope param validation (property_ids etc.)
    return validate_manual_job_scope(
        job_id,
        client_id=req.client_id,
        property_id=req.property_id,
        property_ids=req.property_ids,
    )


async def _active_client_query(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    q: Dict[str, Any] = {
        "subscription_status": "ACTIVE",
        "entitlement_status": {"$in": ["ENABLED", None]},
    }
    if extra:
        q.update(extra)
    return q


async def resolve_execution(db, job_id: str, req: ExecutionRequest) -> Tuple[Optional[str], Optional[ResolvedExecution]]:
    """Resolve scope to concrete targets. Returns (error, resolved)."""
    if req.scope_type == ExecutionScopeType.PORTFOLIO_WIDE:
        return None, ResolvedExecution(
            scope_type=req.scope_type,
            is_portfolio_wide=True,
        )

    if req.scope_type == ExecutionScopeType.CLIENT:
        cid = (req.client_id or "").strip()
        doc = await db.clients.find_one({"client_id": cid}, {"_id": 1})
        if not doc:
            return "Client not found", None
        pids = [str(x).strip() for x in (req.property_ids or []) if x and str(x).strip()] or None
        if pids:
            own_err = await validate_property_ids_belong_to_client(cid, pids)
            if own_err:
                return own_err, None
        return None, ResolvedExecution(
            scope_type=req.scope_type,
            client_ids=[cid],
            property_ids=pids,
        )

    if req.scope_type == ExecutionScopeType.PROPERTY:
        pid = (req.property_id or "").strip()
        prop = await db.properties.find_one({"property_id": pid}, {"_id": 0, "client_id": 1})
        if not prop:
            return "Property not found", None
        legacy = get_job_run_scope(job_id)
        if legacy.manual_requires_property_id:
            return None, ResolvedExecution(
                scope_type=req.scope_type,
                property_id=pid,
                client_ids=[],
            )
        cid = prop.get("client_id")
        return None, ResolvedExecution(
            scope_type=req.scope_type,
            property_id=pid,
            client_ids=[cid] if cid else [],
        )

    if req.scope_type == ExecutionScopeType.CLIENT_GROUP:
        ids = [str(x).strip() for x in (req.client_ids or []) if x and str(x).strip()]
        found = await db.clients.find({"client_id": {"$in": ids}}, {"_id": 0, "client_id": 1}).to_list(len(ids) + 1)
        found_set = {r.get("client_id") for r in found}
        missing = [i for i in ids if i not in found_set]
        if missing:
            return f"Clients not found: {', '.join(missing[:5])}", None
        return None, ResolvedExecution(
            scope_type=req.scope_type,
            client_ids=ids,
            batch_mode=len(ids) > 1,
        )

    if req.scope_type == ExecutionScopeType.PLAN:
        plan = (req.plan_code or "").strip()
        q = await _active_client_query({"$or": [{"plan": plan}, {"billing_plan": plan}]})
        rows = await db.clients.find(q, {"_id": 0, "client_id": 1}).to_list(MAX_MANUAL_BATCH_CLIENTS + 1)
        if len(rows) > MAX_MANUAL_BATCH_CLIENTS:
            return f"PLAN scope matches more than {MAX_MANUAL_BATCH_CLIENTS} clients; narrow the cohort.", None
        cids = [r["client_id"] for r in rows if r.get("client_id")]
        if not cids:
            return f"No active clients found for plan {plan}.", None
        return None, ResolvedExecution(
            scope_type=req.scope_type,
            client_ids=cids,
            batch_mode=len(cids) > 1,
        )

    if req.scope_type == ExecutionScopeType.JURISDICTION:
        juris = (req.jurisdiction or "").strip().upper()
        props = await db.properties.find(
            {"jurisdiction": juris},
            {"_id": 0, "client_id": 1, "property_id": 1},
        ).to_list(MAX_MANUAL_BATCH_CLIENTS * 5)
        cids = list({p.get("client_id") for p in props if p.get("client_id")})[:MAX_MANUAL_BATCH_CLIENTS]
        if not cids:
            return f"No properties found for jurisdiction {juris}.", None
        return None, ResolvedExecution(
            scope_type=req.scope_type,
            client_ids=cids,
            batch_mode=len(cids) > 1,
        )

    if req.scope_type == ExecutionScopeType.FILTERED_COHORT:
        cids = await _resolve_cohort_client_ids(db, (req.cohort_filter or "").strip())
        if not cids:
            return "FILTERED_COHORT matched no eligible clients.", None
        if len(cids) > MAX_MANUAL_BATCH_CLIENTS:
            return f"FILTERED_COHORT matches more than {MAX_MANUAL_BATCH_CLIENTS} clients; narrow filters.", None
        return None, ResolvedExecution(
            scope_type=req.scope_type,
            client_ids=cids,
            batch_mode=len(cids) > 1,
        )

    return "Unsupported scope", None


async def _resolve_cohort_client_ids(db, cohort_filter: str) -> List[str]:
    """Lightweight cohort resolution — approximate, capped."""
    key = cohort_filter.strip().lower()
    if key == "overdue_only":
        rows = await db.requirements.find(
            {"status": {"$in": ["OVERDUE", "EXPIRED"]}},
            {"_id": 0, "client_id": 1},
        ).to_list(5000)
    elif key == "expiring_soon":
        from datetime import date, timedelta

        cutoff = (date.today() + timedelta(days=30)).isoformat()
        rows = await db.requirements.find(
            {"due_date": {"$lte": cutoff}, "status": {"$nin": ["NOT_REQUIRED", "COMPLIANT"]}},
            {"_id": 0, "client_id": 1},
        ).to_list(5000)
    elif key == "risk_level_high":
        rows = await db.risk_signals.find(
            {"severity": {"$in": ["HIGH", "CRITICAL"]}, "status": {"$ne": "RESOLVED"}},
            {"_id": 0, "client_id": 1},
        ).to_list(5000)
    elif key == "compliance_status_red":
        rows = await db.properties.find(
            {"compliance_status": {"$in": ["RED", "NON_COMPLIANT"]}},
            {"_id": 0, "client_id": 1},
        ).to_list(5000)
    else:
        return []
    return list({r.get("client_id") for r in rows if r.get("client_id")})[:MAX_MANUAL_BATCH_CLIENTS]


async def estimate_execution_impact(db, job_id: str, req: ExecutionRequest) -> Dict[str, Any]:
    """Approximate impact preview — cheap counts only."""
    err, resolved = await resolve_execution(db, job_id, req)
    if err or not resolved:
        return {
            "ok": False,
            "error": err or "Could not resolve scope",
            "estimates": {},
        }

    estimates: Dict[str, Any] = {
        "scope_type": resolved.scope_type.value,
        "is_portfolio_wide": resolved.is_portfolio_wide,
    }

    if resolved.is_portfolio_wide:
        client_count = await db.clients.count_documents(await _active_client_query())
        estimates["clients_affected"] = client_count
        prop_count = await db.properties.count_documents({})
        estimates["properties_affected"] = prop_count
        estimates["summary_lines"] = [
            f"~{client_count} active clients affected",
            f"~{prop_count} properties in portfolio",
            _job_impact_hint(job_id, client_count, prop_count),
        ]
        return {"ok": True, "estimates": estimates}

    client_count = len(resolved.client_ids)
    estimates["clients_affected"] = client_count

    if resolved.property_id:
        estimates["properties_affected"] = 1
        estimates["summary_lines"] = [
            "1 property targeted",
            f"Client scope derived from property",
            _job_impact_hint(job_id, 1, 1),
        ]
    elif resolved.property_ids:
        estimates["properties_affected"] = len(resolved.property_ids)
        estimates["summary_lines"] = [
            f"{client_count} client(s) affected",
            f"{len(resolved.property_ids)} properties in digest subset",
            _job_impact_hint(job_id, client_count, len(resolved.property_ids)),
        ]
    else:
        prop_count = 0
        if resolved.client_ids:
            prop_count = await db.properties.count_documents({"client_id": {"$in": resolved.client_ids}})
        estimates["properties_affected"] = prop_count
        estimates["summary_lines"] = [
            f"{client_count} client(s) affected",
            f"~{prop_count} properties under those clients",
            _job_impact_hint(job_id, client_count, prop_count),
        ]

    if resolved.batch_mode:
        estimates["batch_execution"] = True
        estimates["summary_lines"].append(f"Will execute sequentially for {client_count} clients")

    return {"ok": True, "estimates": estimates}


def _job_impact_hint(job_id: str, clients: int, properties: int) -> str:
    hints = {
        "daily_reminders": f"~{max(clients, 1) * 3} reminders estimated (approx.)",
        "monthly_digest": f"~{clients} digest email(s) estimated",
        "compliance_check_morning": f"~{properties} properties evaluated for status changes",
        "compliance_check_evening": f"~{properties} properties evaluated for status changes",
        "risk_signals_job": f"~{properties} properties targeted for risk regen",
        "rent_operations_daily_job": f"~{clients} rent ledger account(s) processed",
    }
    return hints.get(job_id, f"Job will run for {clients} client(s)")


def build_job_kwargs_for_run(job_id: str, resolved: ResolvedExecution, *, triggered_by_admin_id: Optional[str] = None) -> Dict[str, Any]:
    legacy = get_job_run_scope(job_id)
    kw: Dict[str, Any] = {}
    if legacy.manual_requires_property_id and resolved.property_id:
        kw["property_id"] = resolved.property_id
        return kw
    if legacy.accepts_client_id and resolved.client_ids and len(resolved.client_ids) == 1:
        kw["client_id"] = resolved.client_ids[0]
    if legacy.accepts_property_id and resolved.property_id:
        kw["property_id"] = resolved.property_id
    if legacy.accepts_property_ids_filter and resolved.property_ids:
        kw["property_ids"] = resolved.property_ids
    if job_id == "monthly_digest" and triggered_by_admin_id:
        kw["triggered_by_admin_id"] = triggered_by_admin_id
    return kw


def build_start_metadata(resolved: ResolvedExecution, req: ExecutionRequest) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "scope_type": resolved.scope_type.value,
        "portfolio_wide": resolved.is_portfolio_wide,
    }
    if resolved.client_ids:
        meta["client_ids"] = resolved.client_ids
        if len(resolved.client_ids) == 1:
            meta["client_id"] = resolved.client_ids[0]
            meta["scope"] = "client"
    if resolved.property_id:
        meta["property_id"] = resolved.property_id
    if resolved.property_ids:
        meta["property_ids"] = resolved.property_ids
    if resolved.is_portfolio_wide:
        meta["scope"] = "global"
    elif not meta.get("scope"):
        meta["scope"] = "client" if resolved.client_ids else "global"
    if req.plan_code:
        meta["plan_code"] = req.plan_code
    if req.jurisdiction:
        meta["jurisdiction"] = req.jurisdiction
    if req.cohort_filter:
        meta["cohort_filter"] = req.cohort_filter
    return meta


def governance_action_id(resolved: ResolvedExecution) -> str:
    if resolved.is_portfolio_wide:
        return "run_portfolio_wide_job"
    return "run_scoped_automation_job"
