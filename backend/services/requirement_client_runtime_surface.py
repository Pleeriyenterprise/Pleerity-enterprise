"""
Central gate for *client-facing* requirement rows on runtime surfaces (reminders, digests,
exports, dashboards, notifications, calendar, unified tasks, etc.).

INVARIANT — all client-facing requirement output must pass through published runtime
eligibility + jurisdiction + condition filtering aligned with ``build_requirement_plan_for_property``
(planner truth for catalog-backed rows), plus row-level NOT_REQUIRED / visibility / hidden-action /
archived-metadata gates.

Bounded exception: allowlisted ``condition_standard_pilot_ops`` rows for
``CONDITION_STANDARD_ACTIVE_STANDARD`` may pass without catalog planner membership when
``evaluate_condition_standard_pilot_runtime_legitimacy`` returns true (see
``services.condition_standard_pilot_materialisation``). Prefer ``filter_requirement_rows_for_client_runtime_surfaces`` (async, DB-aware)
or call ``requirement_row_passes_client_runtime_surface_gates`` after you have loaded published entries
and per-property plan type sets.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from services.compliance_registry_publish_service import fetch_active_published_registry_entries
from services.compliance_requirement_registry import (
    REQUIREMENT_GENERATION_SOURCE_REGISTRY,
    build_requirement_plan_for_property,
    resolve_published_entry_for_requirement,
)
from services.compliance_registry_admin_service import registry_entry_key
from services.compliance_registry_conditions import property_matches_registry_conditions
from services.compliance_rules_registry import (
    canonicalize_uk_portfolio_label,
    portfolio_jurisdiction_label,
)
from services.condition_standard_pilot_materialisation import (
    evaluate_condition_standard_pilot_runtime_legitimacy,
    is_condition_standard_pilot_runtime_legitimate,
)
from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE
from services.requirement_code_registry import normalize_requirement_code
from services.requirement_not_required_governance import (
    automated_not_required_from_row,
    is_operator_curated_not_required,
)


CLIENT_RUNTIME_REQUIREMENT_SURFACE_INVARIANT = (
    "All client-facing requirement output must pass through published runtime eligibility + "
    "jurisdiction + condition filtering (shared planner for catalog-backed rows), excluding "
    "NOT_REQUIRED, non-visible, hidden-primary-action, archived metadata, draft-only registry rows, "
    "and wrong-jurisdiction rows."
)

_ALIAS_FAMILY_BY_CANONICAL: Dict[str, str] = {
    # Domestic alarm / smoke / CO / fire alarm & detection testing evidence (single client-facing family).
    "fire_detection": "fire_detection_alias_family",
    "fire_alarm": "fire_detection_alias_family",
    "smoke_alarms": "fire_detection_alias_family",
    "co_alarms": "fire_detection_alias_family",
    "smoke_heat_alarms": "fire_detection_alias_family",
    # True alias family: same HMO fire-risk obligation represented in legacy/evidence variants.
    "hmo_fire_risk": "hmo_fire_risk_alias_family",
    "hmo_fire_risk_evidence": "hmo_fire_risk_alias_family",
    # True alias family: tenancy deposit protection rows from legacy/current slugs.
    "deposit_pi": "tenancy_deposit_alias_family",
    "tenancy_deposit_protection": "tenancy_deposit_alias_family",
    "deposit_prescribed_info": "tenancy_deposit_alias_family",
    # True alias family: right-to-rent check slugs.
    "right_to_rent": "right_to_rent_alias_family",
    "right_to_rent_checks": "right_to_rent_alias_family",
}


def client_portal_surface_visible_row(row: Dict[str, Any]) -> bool:
    """True unless the row is explicitly hidden from client portal surfaces."""
    return row.get("client_surface_visible") is not False


def project_requirement_row_client_runtime(requirement: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single projection for portfolio stats, /client/dashboard summaries, and legacy portfolio KPIs:
    authority-backed status when evidence authority is synced, else legacy ``status``;
    ``due_date`` as ISO from ``get_effective_expiry_date``; evidence_state from authority when present.
    Matches ``services.compliance_score.calculate_compliance_score`` row shaping.

    See ``docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`` for allowed client-facing status strings and semantics.
    """
    from utils.expiry_utils import get_effective_expiry_date
    from services.requirement_evidence_authority import (
        authority_runtime_requirement_status,
        authority_state,
        normalized_evidence_state_for_policy,
    )

    eff = get_effective_expiry_date(requirement)
    st = authority_runtime_requirement_status(requirement) or requirement.get("status")
    out = {
        **requirement,
        "status": st,
        "due_date": eff.isoformat() if eff else None,
        "evidence_state": authority_state(requirement) or requirement.get("evidence_state"),
    }
    # PR2 write-path enrichment pass-through: runtime projections must not strip policy snapshot fields.
    out.setdefault("requirement_code_normalized", requirement.get("requirement_code_normalized"))
    out.setdefault("applicability_state", requirement.get("applicability_state"))
    out.setdefault("is_mandatory", requirement.get("is_mandatory"))
    out.setdefault("policy_criticality", requirement.get("policy_criticality"))
    out.setdefault("policy_classification_version", requirement.get("policy_classification_version"))
    out["evidence_state_normalized"] = normalized_evidence_state_for_policy(requirement)
    from services.lifecycle_semantics_shadow import observe_lifecycle_semantics_shadow_if_enabled

    observe_lifecycle_semantics_shadow_if_enabled(requirement)
    return out


def _compute_legacy_portal_requirement_stats(portal_projected_rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """Legacy status-based KPI aggregation (authoritative when KPI flag is off)."""
    total = len(portal_projected_rows)
    compliant = 0
    satisfied = 0
    pending = 0
    missing_evidence = 0
    expiring_soon = 0
    overdue = 0
    from services.requirement_satisfaction_service import is_requirement_satisfied, row_counts_as_missing_evidence

    for r in portal_projected_rows:
        if is_requirement_satisfied(r):
            satisfied += 1
        s = (str(r.get("status") or "PENDING")).strip().upper()
        if s in ("COMPLIANT", "VALID"):
            compliant += 1
        elif s == "PENDING":
            pending += 1
            if row_counts_as_missing_evidence(r):
                missing_evidence += 1
        elif s == "MISSING":
            if row_counts_as_missing_evidence(r):
                missing_evidence += 1
        elif s == "EXPIRING_SOON":
            expiring_soon += 1
        elif s in ("OVERDUE", "EXPIRED"):
            overdue += 1
    return {
        "total_requirements": total,
        # Authoritative satisfied count for portfolio KPIs (includes recorded-on-file / declaration paths).
        "compliant": satisfied,
        "satisfied": satisfied,
        "status_valid": compliant,
        "pending": pending,
        "missing_evidence": missing_evidence,
        "expiring_soon": expiring_soon,
        "overdue": overdue,
    }


def compute_client_portal_requirement_stats(portal_projected_rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Aggregate counts from **portal-visible** rows that have already passed
    ``project_requirement_row_client_runtime``. Single authority for KPI tiles, Command Centre,
    compliance score ``stats``, and reporting parity.
    """
    legacy_stats = _compute_legacy_portal_requirement_stats(portal_projected_rows)
    from services.lifecycle_aware_kpis_config import is_lifecycle_aware_kpi_active
    from services.lifecycle_kpi_gates import (
        compute_lifecycle_kpi_stats,
        lifecycle_kpi_enabled,
        lifecycle_stats_authoritative_payload,
        observe_kpi_shadow,
    )

    if is_lifecycle_aware_kpi_active():
        return lifecycle_stats_authoritative_payload(
            compute_lifecycle_kpi_stats(portal_projected_rows),
        )

    if lifecycle_kpi_enabled():
        observe_kpi_shadow(
            legacy_stats=legacy_stats,
            lifecycle_stats=compute_lifecycle_kpi_stats(portal_projected_rows),
        )
    return legacy_stats


def _status_upper(val: Optional[str]) -> str:
    return (val or "").strip().upper()


def _norm_requirement_type(row: Dict[str, Any]) -> str:
    return (
        str(row.get("requirement_type") or row.get("requirement_code") or row.get("code") or "")
        .strip()
        .lower()
    )


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    s = str(value or "").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.min


def _property_jurisdiction_source(property_doc: Dict[str, Any], client_doc: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    raw = str((property_doc or {}).get("jurisdiction") or "").strip()
    if raw:
        canon = canonicalize_uk_portfolio_label(raw) or raw
        return canon, "property_explicit"
    cdef = str((client_doc or {}).get("default_jurisdiction") or "").strip()
    if cdef:
        canon = canonicalize_uk_portfolio_label(cdef) or cdef
        return canon, "client_default"
    return "England", "default_fallback"


def _published_overlay_exists_for_row(
    row: Dict[str, Any],
    *,
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
    published_registry_entries: Optional[Dict[str, Any]],
) -> bool:
    plabel = portfolio_jurisdiction_label(property_doc, client_doc or {})
    pe = resolve_published_entry_for_requirement(
        published_registry_entries=published_registry_entries,
        requirement_type=str(row.get("requirement_type") or row.get("requirement_code") or ""),
        portfolio_label=str(plabel or ""),
        property_doc=property_doc,
        enforce_conditions=True,
    )
    return isinstance(pe, dict)


def _runtime_source_for_row(
    row: Dict[str, Any],
    *,
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
    published_registry_entries: Optional[Dict[str, Any]],
    baseline_plan_types_lower: Set[str],
) -> str:
    if _legacy_readonly_visible(row):
        return "legacy_readonly"
    rt = _norm_requirement_type(row)
    baseline = rt in baseline_plan_types_lower
    overlay = _published_overlay_exists_for_row(
        row,
        property_doc=property_doc,
        client_doc=client_doc,
        published_registry_entries=published_registry_entries,
    )
    if baseline and overlay:
        return "both"
    if overlay:
        return "published"
    return "baseline"


def _alias_family_key_for_row(row: Dict[str, Any]) -> Optional[str]:
    raw = str(row.get("requirement_code") or row.get("requirement_type") or "").strip()
    canon = normalize_requirement_code(raw) or _norm_requirement_type(row)
    return _ALIAS_FAMILY_BY_CANONICAL.get(str(canon or "").strip().lower())


def _canonical_code_for_row(row: Dict[str, Any]) -> str:
    raw = str(row.get("requirement_code") or row.get("requirement_type") or "").strip()
    canon = normalize_requirement_code(raw)
    if canon:
        return canon
    return str(_norm_requirement_type(row) or raw).strip().lower()


def _dedupe_rank_for_row(row: Dict[str, Any]) -> Tuple[int, int, datetime]:
    # Precedence:
    # a) published-enriched row wins
    # b) evidence/tracked row wins
    # c) newest row wins
    meta = row.get("registry_metadata") if isinstance(row.get("registry_metadata"), dict) else {}
    has_published = int(
        bool(meta.get("action_links_published"))
        or bool(meta.get("why_it_matters_short_published"))
        or bool(meta.get("why_it_matters_long_published"))
        or str(row.get("source") or "").strip().lower() in {"published", "both"}
    )
    has_evidence_or_tracking = int(
        bool(row.get("evidence_doc_id"))
        or bool(str(row.get("document_id") or "").strip())
        or bool(row.get("is_tracked") is True)
        or str(row.get("evidence_state") or "").strip().upper() not in {"", "MISSING"}
    )
    return (has_published, has_evidence_or_tracking, _parse_dt(row.get("updated_at")))


def _build_canonical_runtime_row(
    row: Dict[str, Any],
    *,
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
    source: str,
) -> Dict[str, Any]:
    out = dict(row)
    prop_jur, jur_source = _property_jurisdiction_source(property_doc, client_doc)
    out["property_jurisdiction"] = prop_jur
    out["jurisdiction_source"] = jur_source
    out["jurisdiction_basis"] = "property_jurisdiction" if jur_source == "property_explicit" else jur_source
    out["canonical_code"] = _canonical_code_for_row(row)
    out["display_name"] = str(row.get("display_label") or row.get("description") or row.get("requirement_code") or row.get("requirement_type") or "")
    out["category"] = (
        ((row.get("registry_metadata") or {}).get("category"))
        or ((row.get("registry_metadata") or {}).get("identity_category"))
        or None
    )
    out["risk"] = str(row.get("criticality") or row.get("risk_level") or "").strip().upper() or None
    out["cta_action_mode"] = str(((row.get("take_action") or {}).get("primary") or {}).get("action_type") or "").strip() or None
    out["cta_label"] = str(((row.get("take_action") or {}).get("primary") or {}).get("label") or "").strip() or None
    out["cta_url"] = ((row.get("take_action") or {}).get("primary") or {}).get("url")
    out["source"] = source
    out["legacy_requirement_state"] = row.get("legacy_requirement_state")
    out["legacy_readonly_visible"] = bool(row.get("legacy_readonly_visible"))
    out["legacy_review_required"] = bool(row.get("legacy_review_required"))
    out["legacy_canonical_requirement_code"] = row.get("legacy_canonical_requirement_code")
    out["trigger_explanation"] = {
        "jurisdiction_basis": out.get("jurisdiction_basis"),
        "property_jurisdiction": out.get("property_jurisdiction"),
        "requirement_type": row.get("requirement_type"),
    }
    return out


def _dedupe_alias_rows_for_property(
    rows: List[Dict[str, Any]],
    *,
    include_trace: bool,
) -> List[Dict[str, Any]]:
    if not rows:
        return rows
    keep: List[Dict[str, Any]] = []
    by_family: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        fam = _alias_family_key_for_row(r)
        if not fam:
            keep.append(r)
            continue
        by_family.setdefault(fam, []).append(r)
    for fam, family_rows in by_family.items():
        if len(family_rows) == 1:
            row = family_rows[0]
            if include_trace:
                row["_runtime_trace"] = {
                    **(row.get("_runtime_trace") if isinstance(row.get("_runtime_trace"), dict) else {}),
                    "alias_family": fam,
                    "dedupe_decision": "kept_single_family_row",
                    "dedupe_candidates": [str(row.get("requirement_id") or row.get("requirement_type") or "")],
                }
            keep.append(row)
            continue
        ordered = sorted(family_rows, key=_dedupe_rank_for_row, reverse=True)
        winner = ordered[0]
        losers = ordered[1:]
        if include_trace:
            winner["_runtime_trace"] = {
                **(winner.get("_runtime_trace") if isinstance(winner.get("_runtime_trace"), dict) else {}),
                "alias_family": fam,
                "dedupe_decision": "kept_winner_alias_row",
                "dedupe_candidates": [str(x.get("requirement_id") or x.get("requirement_type") or "") for x in ordered],
                "dedupe_excluded": [str(x.get("requirement_id") or x.get("requirement_type") or "") for x in losers],
            }
        keep.append(winner)
    return keep


def _generation_source(row: Dict[str, Any]) -> str:
    return str(row.get("requirement_generation_source") or "").strip()


def _needs_catalog_planner_membership(row: Dict[str, Any]) -> bool:
    src = _generation_source(row)
    if src == REQUIREMENT_GENERATION_SOURCE_DB_RULE:
        return False
    if src in ("", REQUIREMENT_GENERATION_SOURCE_REGISTRY):
        return True
    # Unknown / legacy sources: fail closed to planner membership when property-backed
    return True


def _primary_action_hidden(row: Dict[str, Any]) -> bool:
    meta = row.get("registry_metadata")
    if not isinstance(meta, dict):
        return False
    return str(meta.get("primary_action_mode") or "").strip().lower() == "hidden"


def _registry_metadata_archived(row: Dict[str, Any]) -> bool:
    meta = row.get("registry_metadata")
    if not isinstance(meta, dict):
        return False
    life = meta.get("lifecycle") if isinstance(meta.get("lifecycle"), dict) else {}
    st = str(life.get("status") or meta.get("lifecycle_status") or "").strip().lower()
    return st in ("archived", "superseded", "disabled", "withdrawn")


def _registry_draft_or_unpublished_materialization(row: Dict[str, Any]) -> bool:
    """Rows materialised only from unpublished / draft registry must never surface to clients."""
    meta = row.get("registry_metadata") if isinstance(row.get("registry_metadata"), dict) else {}
    if meta.get("draft_only_materialization") is True:
        return True
    rps = str(meta.get("registry_publish_state") or "").strip().lower()
    return rps in ("draft", "draft_only", "unpublished")


def _legacy_readonly_visible(row: Dict[str, Any]) -> bool:
    state = str(row.get("legacy_requirement_state") or "").strip().lower()
    if state in ("mapped_readonly", "unmapped_readonly"):
        return True
    return row.get("legacy_readonly_visible") is True


def _explicit_row_jurisdiction_mismatches_property(
    row: Dict[str, Any],
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
) -> bool:
    """
    True when the row carries an explicit UK portfolio label that disagrees with the
    property's resolved portfolio label (stale / cross-region materialised rows).
    """
    raw = row.get("jurisdiction")
    if not raw or not str(raw).strip():
        return False
    row_label = canonicalize_uk_portfolio_label(str(raw).strip())
    if not row_label:
        return False
    prop_label = portfolio_jurisdiction_label(property_doc, client_doc or {})
    prop_canon = canonicalize_uk_portfolio_label(prop_label) or prop_label
    return bool(row_label and prop_canon and row_label != prop_canon)


def requirement_row_passes_client_runtime_surface_gates(
    row: Dict[str, Any],
    *,
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
    plan_types_lower: Set[str],
    published_registry_entries: Optional[Dict[str, Any]],
) -> bool:
    """
    Pure predicate: caller supplies property doc, client doc, and precomputed planner types
    for that property (from ``build_requirement_plan_for_property`` with the same published snapshot).
    """
    if _status_upper(row.get("applicability")) == "NOT_REQUIRED" or _status_upper(row.get("status")) == "NOT_REQUIRED":
        return False
    if row.get("client_surface_visible") is False:
        return False
    if _primary_action_hidden(row):
        return False
    if _registry_metadata_archived(row):
        return False
    if _registry_draft_or_unpublished_materialization(row):
        return False
    if _explicit_row_jurisdiction_mismatches_property(row, property_doc, client_doc):
        return False

    rtype = _norm_requirement_type(row)
    if not rtype:
        return False

    if is_condition_standard_pilot_runtime_legitimate(
        row,
        property_doc=property_doc,
        client_doc=client_doc,
        published_registry_entries=published_registry_entries,
    ):
        return True

    if _needs_catalog_planner_membership(row):
        if rtype not in plan_types_lower:
            return False
    if published_registry_entries is not None:
        has_published_overlay = _published_overlay_exists_for_row(
            row,
            property_doc=property_doc,
            client_doc=client_doc,
            published_registry_entries=published_registry_entries,
        )
        if not has_published_overlay and not _legacy_readonly_visible(row):
            return False

    return True


def _first_exclusion_reason(
    row: Dict[str, Any],
    *,
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
    plan_types_lower: Set[str],
    published_registry_entries: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if _status_upper(row.get("applicability")) == "NOT_REQUIRED" or _status_upper(row.get("status")) == "NOT_REQUIRED":
        return "not_required_row"
    if row.get("client_surface_visible") is False:
        return "client_surface_hidden"
    if _primary_action_hidden(row):
        return "primary_action_hidden"
    if _registry_metadata_archived(row):
        return "archived_registry_metadata"
    if _registry_draft_or_unpublished_materialization(row):
        return "draft_or_unpublished_materialization"
    if _explicit_row_jurisdiction_mismatches_property(row, property_doc, client_doc):
        return "row_jurisdiction_mismatch"
    rtype = _norm_requirement_type(row)
    if not rtype:
        return "missing_requirement_type"
    _ok_pilot, pilot_reason = evaluate_condition_standard_pilot_runtime_legitimacy(
        row,
        property_doc=property_doc,
        client_doc=client_doc,
        published_registry_entries=published_registry_entries,
    )
    if str(row.get("requirement_generation_source") or "").strip() == "condition_standard_pilot_ops":
        if not _ok_pilot:
            return f"condition_standard_pilot_not_legitimate:{pilot_reason}"
        return None
    if _needs_catalog_planner_membership(row) and rtype not in plan_types_lower:
        return "not_in_planner_membership"
    return None


def _property_plan_types_lower(
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
    published_registry_entries: Optional[Dict[str, Any]],
) -> Set[str]:
    plan = build_requirement_plan_for_property(
        property_doc,
        client_doc,
        published_registry_entries=published_registry_entries,
    )
    return {str(x.requirement_type or "").strip().lower() for x in plan if str(x.requirement_type or "").strip()}


async def filter_requirement_rows_for_client_runtime_surfaces(
    db,
    *,
    client_id: str,
    requirements: List[Dict[str, Any]],
    client_doc: Optional[Dict[str, Any]] = None,
    properties: Optional[List[Dict[str, Any]]] = None,
    published_registry_entries: Optional[Dict[str, Any]] = None,
    include_trace: bool = False,
) -> List[Dict[str, Any]]:
    """
    Async safe wrapper: loads published snapshot once, resolves property docs, filters rows.
    """
    if not requirements:
        return []

    if published_registry_entries is None:
        try:
            published_registry_entries = await fetch_active_published_registry_entries(db)
        except TypeError:
            # Tests may pass a stub ``db`` without awaitable collection accessors; planner still runs.
            published_registry_entries = None

    if client_doc is None:
        client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}

    # Prefer authoritative DB property docs for planner membership + conditions; caller-supplied
    # ``properties`` is a fallback when tests or offline callers omit Mongo reads.
    prop_by_id: Dict[str, Dict[str, Any]] = {}
    if properties:
        for p in properties:
            pid = p.get("property_id")
            if pid:
                prop_by_id[str(pid)] = dict(p)

    req_pids = sorted({str(r.get("property_id")) for r in requirements if r.get("property_id")})
    if req_pids:
        missing = [pid for pid in req_pids if str(pid) not in prop_by_id]
        if missing:
            cur = db.properties.find(
                {"client_id": client_id, "property_id": {"$in": missing}},
                {"_id": 0},
            )
            async for p in cur:
                pid = p.get("property_id")
                if pid:
                    prop_by_id[str(pid)] = p

    plan_cache: Dict[str, Set[str]] = {}
    baseline_plan_cache: Dict[str, Set[str]] = {}

    def plan_for(pid: str) -> Set[str]:
        if pid in plan_cache:
            return plan_cache[pid]
        prop = prop_by_id.get(pid) or {}
        types_lower = _property_plan_types_lower(prop, client_doc, published_registry_entries)
        plan_cache[pid] = types_lower
        return types_lower

    def baseline_plan_for(pid: str) -> Set[str]:
        if pid in baseline_plan_cache:
            return baseline_plan_cache[pid]
        prop = prop_by_id.get(pid) or {}
        types_lower = _property_plan_types_lower(prop, client_doc, None)
        baseline_plan_cache[pid] = types_lower
        return types_lower

    out: List[Dict[str, Any]] = []
    out_by_property: Dict[str, List[Dict[str, Any]]] = {}
    for row in requirements:
        pid = row.get("property_id")
        if not pid:
            continue
        prop = prop_by_id.get(str(pid))
        if not prop:
            continue
        pt = plan_for(str(pid))
        if requirement_row_passes_client_runtime_surface_gates(
            row,
            property_doc=prop,
            client_doc=client_doc,
            plan_types_lower=pt,
            published_registry_entries=published_registry_entries,
        ):
            source = _runtime_source_for_row(
                row,
                property_doc=prop,
                client_doc=client_doc,
                published_registry_entries=published_registry_entries,
                baseline_plan_types_lower=baseline_plan_for(str(pid)),
            )
            canon_row = _build_canonical_runtime_row(
                row,
                property_doc=prop,
                client_doc=client_doc,
                source=source,
            )
            if include_trace:
                _pilot_ok, _pilot_reason = evaluate_condition_standard_pilot_runtime_legitimacy(
                    row,
                    property_doc=prop,
                    client_doc=client_doc,
                    published_registry_entries=published_registry_entries,
                )
                trace: Dict[str, Any] = {
                    "included": True,
                    "inclusion_reason": (
                        "condition_standard_pilot_runtime_legitimate"
                        if _pilot_ok
                        else "passes_runtime_surface_gates"
                    ),
                    "matched_published_overlay": source in ("published", "both"),
                    "source": source,
                }
                if str(row.get("requirement_generation_source") or "").strip() == "condition_standard_pilot_ops":
                    trace["condition_standard_pilot_runtime_legitimacy"] = _pilot_reason
                canon_row["_runtime_trace"] = trace
            out.append(canon_row)
            out_by_property.setdefault(str(pid), []).append(canon_row)

    deduped: List[Dict[str, Any]] = []
    for pid, rows in out_by_property.items():
        _ = pid
        deduped.extend(_dedupe_alias_rows_for_property(rows, include_trace=include_trace))
    return deduped


async def requirement_row_eligible_on_client_runtime_surfaces(
    db,
    *,
    client_id: str,
    row: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]] = None,
    property_doc: Optional[Dict[str, Any]] = None,
    published_registry_entries: Optional[Dict[str, Any]] = None,
) -> bool:
    """Single-row convenience for explanation routes and spot checks."""
    pid = row.get("property_id")
    if not pid:
        return False
    prop = property_doc
    if prop is None:
        prop = await db.properties.find_one(
            {"client_id": client_id, "property_id": pid},
            {"_id": 0},
        )
    if not prop:
        return False
    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=[row],
        client_doc=client_doc,
        properties=[prop],
        published_registry_entries=published_registry_entries,
    )
    return len(filtered) == 1


def _not_required_persistence_snapshot_for_explain(row: Dict[str, Any]) -> Dict[str, Any]:
    """B1: surface persisted NOT_REQUIRED provenance on explain rows (no filter bypass)."""
    return {
        "status": row.get("status"),
        "applicability": row.get("applicability"),
        "not_required_reason": row.get("not_required_reason"),
        "operator_curated_not_required": is_operator_curated_not_required(row),
        "automated_not_required": automated_not_required_from_row(row),
        "reconciled_obsolete": bool((row.get("registry_metadata") or {}).get("reconciled_obsolete")),
    }


async def explain_runtime_requirement_rows_for_property(
    db,
    *,
    client_id: str,
    property_id: str,
) -> Dict[str, Any]:
    """
    Admin/dev explain payload for requirement inclusion/exclusion decisions on one property.
    """
    prop = await db.properties.find_one({"client_id": client_id, "property_id": property_id}, {"_id": 0}) or {}
    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    raw = await db.requirements.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    ).to_list(5000)
    published = await fetch_active_published_registry_entries(db)
    included = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=raw,
        client_doc=client_doc,
        properties=[prop],
        published_registry_entries=published,
        include_trace=True,
    )
    included_by_id = {str(r.get("requirement_id") or ""): r for r in included if str(r.get("requirement_id") or "")}
    plan_types = _property_plan_types_lower(prop, client_doc, published)
    baseline_types = _property_plan_types_lower(prop, client_doc, None)
    explained_rows: List[Dict[str, Any]] = []
    for row in raw:
        rid = str(row.get("requirement_id") or "")
        plabel = portfolio_jurisdiction_label(prop, client_doc)
        pe = resolve_published_entry_for_requirement(
            published_registry_entries=published,
            requirement_type=str(row.get("requirement_type") or row.get("requirement_code") or ""),
            portfolio_label=plabel,
            property_doc=prop,
            enforce_conditions=True,
        )
        conditions = (pe or {}).get("conditions") if isinstance(pe, dict) else None
        cond_ok = property_matches_registry_conditions(prop, conditions) if isinstance(conditions, dict) else None
        if rid and rid in included_by_id:
            ir = included_by_id[rid]
            explained_rows.append(
                {
                    "requirement_id": rid,
                    "requirement_type": row.get("requirement_type"),
                    "requirement_code": row.get("requirement_code"),
                    "property_jurisdiction": ir.get("property_jurisdiction"),
                    "jurisdiction_source": ir.get("jurisdiction_source"),
                    "matched_published_key": registry_entry_key(pe) if isinstance(pe, dict) else None,
                    "baseline_key": _canonical_code_for_row(row),
                    "conditions_satisfied": cond_ok,
                    "conditions": conditions,
                    "source": ir.get("source"),
                    "included": True,
                    "inclusion_reason": ((ir.get("_runtime_trace") or {}).get("inclusion_reason") if isinstance(ir.get("_runtime_trace"), dict) else "included"),
                    "alias_dedupe_decision": ((ir.get("_runtime_trace") or {}).get("dedupe_decision") if isinstance(ir.get("_runtime_trace"), dict) else None),
                    "trace": ir.get("_runtime_trace"),
                    "persistence": _not_required_persistence_snapshot_for_explain(row),
                }
            )
            continue
        reason = _first_exclusion_reason(
            row,
            property_doc=prop,
            client_doc=client_doc,
            plan_types_lower=plan_types,
            published_registry_entries=published,
        )
        source = _runtime_source_for_row(
            row,
            property_doc=prop,
            client_doc=client_doc,
            published_registry_entries=published,
            baseline_plan_types_lower=baseline_types,
        )
        explained_rows.append(
            {
                "requirement_id": rid,
                "requirement_type": row.get("requirement_type"),
                "requirement_code": row.get("requirement_code"),
                "property_jurisdiction": _property_jurisdiction_source(prop, client_doc)[0],
                "jurisdiction_source": _property_jurisdiction_source(prop, client_doc)[1],
                "matched_published_key": registry_entry_key(pe) if isinstance(pe, dict) else None,
                "baseline_key": _canonical_code_for_row(row),
                "conditions_satisfied": cond_ok,
                "conditions": conditions,
                "source": source,
                "included": False,
                "exclusion_reason": reason or "excluded_by_alias_dedupe_or_runtime_policy",
                "alias_dedupe_decision": "excluded_or_not_selected",
                "persistence": _not_required_persistence_snapshot_for_explain(row),
            }
        )
    return {
        "client_id": client_id,
        "property_id": property_id,
        "property_jurisdiction": _property_jurisdiction_source(prop, client_doc)[0],
        "jurisdiction_source": _property_jurisdiction_source(prop, client_doc)[1],
        "included_count": len(included),
        "raw_count": len(raw),
        "rows": explained_rows,
    }


__all__ = (
    "CLIENT_RUNTIME_REQUIREMENT_SURFACE_INVARIANT",
    "filter_requirement_rows_for_client_runtime_surfaces",
    "requirement_row_passes_client_runtime_surface_gates",
    "requirement_row_eligible_on_client_runtime_surfaces",
    "explain_runtime_requirement_rows_for_property",
)
