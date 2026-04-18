"""
Admin Compliance Requirement Registry — draft storage, validation, and compare vs engine baseline.

Mongo drafts do not affect client generation until promoted through the **publish queue** into the
active published snapshot; ``materialize_requirements_for_property`` merges that snapshot into the
same planner output as in-code registry rules.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from services.compliance_rules_registry import ComplianceRuleSpec, REGISTRY_BY_JURISDICTION, get_rule
from services.requirement_action_links import _load_registry_by_code
from services.requirement_action_links_admin_service import validate_action_links_override

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_VALID_REQ_TYPES = frozenset({"DOCUMENT", "JOB", "OBLIGATION", "SYSTEM"})
_VALID_CRITICALITY = frozenset({"HIGH", "MEDIUM", "LOW"})
_VALID_ACTION_MODES = frozenset({"upload_document", "arrange_job", "view_guidance", "hidden"})
_VALID_CONDITION_OPS = frozenset({"==", "!=", "in", "not_in", "true", "false", "gt", "lt"})
_VALID_CONDITION_FIELDS = frozenset(
    {
        "is_hmo",
        "has_gas_supply",
        "tenancy_active",
        "furnished",
        "deposit_taken",
        "has_communal_areas",
        "local_authority",
        "property_type",
        "building_age_years",
        "licence_required",
        "cert_gas_safety",
        "cert_licence",
        "licence_type",
    }
)

COLLECTION = "compliance_requirement_registry_drafts"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_rule_spec(spec: ComplianceRuleSpec) -> Dict[str, Any]:
    return {
        "canonical_code": spec.canonical_code,
        "storage_type": spec.storage_type,
        "description": spec.description,
        "frequency_days": spec.frequency_days,
        "warning_days": spec.warning_days,
        "expects_expiry": spec.expects_expiry,
        "condition": spec.condition,
        "frequency_by_age": dict(spec.frequency_by_age) if spec.frequency_by_age else None,
        "expiring_soon_days_override": spec.expiring_soon_days_override,
        "allowed_document_types": list(spec.allowed_document_types) if spec.allowed_document_types else None,
        "required_metadata_fields": list(spec.required_metadata_fields) if spec.required_metadata_fields else (),
    }


def build_published_baseline_snapshot(canonical_code: str) -> Dict[str, Any]:
    """
    Read-only projection from the in-code compliance_rules_registry (+ optional catalog hints).
    Not used for client generation; compare-only for admin UI.
    """
    code = str(canonical_code or "").strip().upper()
    out: Dict[str, Any] = {"canonical_code": code, "buckets": {}}
    for bucket in sorted(REGISTRY_BY_JURISDICTION.keys()):
        spec = get_rule(bucket, code)
        if spec:
            out["buckets"][bucket] = _serialize_rule_spec(spec)
    out["action_links_registry"] = _load_registry_by_code().get(code) or []
    return out


def default_draft_shell(
    *,
    canonical_code: str,
    scope_key: str = "DEFAULT",
    identity_name: Optional[str] = None,
) -> Dict[str, Any]:
    code = str(canonical_code or "").strip().upper()
    spec_ew = get_rule("ENGLAND_WALES", code)
    name = identity_name or (spec_ew.description if spec_ew else code.replace("_", " ").title())
    freq_days = int(spec_ew.frequency_days) if spec_ew else 365
    warn_days = int(spec_ew.warning_days) if spec_ew else 30
    storage = spec_ew.storage_type if spec_ew else code.lower().replace("_", "_")
    req_class = "DOCUMENT"
    if code in ("LEGIONELLA",):
        req_class = "JOB"
    requires_job = req_class == "JOB"
    return {
        "entry_id": str(uuid.uuid4()),
        "status": "draft",
        "scope_key": scope_key,
        "canonical_code": code,
        "identity": {
            "name": name,
            "category": "COMPLIANCE",
            "description": spec_ew.description if spec_ew else "",
            "legal_reference": "",
            "display_order": 0,
            "tags": [],
        },
        "classification": {
            "requirement_type": req_class,
            "criticality": "HIGH",
            "requires_document": True,
            "requires_job": requires_job,
            "client_surface_visible": True,
            "default_tracking_mode": None,
        },
        "jurisdiction": {
            "display_jurisdictions": ["ENGLAND", "SCOTLAND", "WALES", "NORTHERN_IRELAND"],
            "scoring_jurisdiction_note": None,
            "effective_from": None,
            "effective_to": None,
            "is_active": True,
            "deprecated": False,
        },
        "conditions": {"logic": "ALL", "rules": []},
        "frequency": {
            "frequency_days": freq_days,
            "reminder_lead_days": warn_days,
            "label": None,
            "event_based": False,
            "needs_review": [],
        },
        "action_behaviour": {
            "primary_action_mode": "upload_document",
            "cta_label_override": None,
            "completion_notes": None,
        },
        "action_links": list(_load_registry_by_code().get(code) or []),
        "why_it_matters_short": "",
        "why_it_matters_long": "",
        "why_it_matters_by_jurisdiction": {},
        "why_it_matters_by_context": {},
        "governance": {
            "change_reason": "",
            "internal_notes": "",
            "legal_source_summary": "",
            "needs_review_fields": [],
            "import_source": None,
            "import_row_ref": None,
        },
        "baseline_alignment": {"engine_storage_type": storage, "catalog_code": storage},
        "updated_at": _utc(),
        "updated_by": {},
    }


def validate_registry_draft(doc: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    code = str(doc.get("canonical_code") or "").strip().upper()
    if not code or not _CODE_RE.match(code):
        errs.append("canonical_code must match ^[A-Z][A-Z0-9_]{0,63}$")
    sk = str(doc.get("scope_key") or "DEFAULT").strip() or "DEFAULT"
    if len(sk) > 64:
        errs.append("scope_key too long")

    ident = doc.get("identity") if isinstance(doc.get("identity"), dict) else {}
    if not str(ident.get("name") or "").strip():
        errs.append("identity.name is required")

    cls = doc.get("classification") if isinstance(doc.get("classification"), dict) else {}
    rt = str(cls.get("requirement_type") or "").strip().upper()
    if rt not in _VALID_REQ_TYPES:
        errs.append("classification.requirement_type must be DOCUMENT, JOB, OBLIGATION, or SYSTEM")
    crit = str(cls.get("criticality") or "MEDIUM").strip().upper()
    if crit not in _VALID_CRITICALITY:
        errs.append("classification.criticality must be HIGH, MEDIUM, or LOW")
    if rt == "DOCUMENT" and cls.get("requires_document") is False:
        errs.append("DOCUMENT normally expects requires_document true")
    if rt == "JOB" and cls.get("requires_job") is False:
        errs.append("JOB normally expects requires_job true")

    jur = doc.get("jurisdiction") if isinstance(doc.get("jurisdiction"), dict) else {}
    dj = jur.get("display_jurisdictions")
    if dj is not None and not isinstance(dj, list):
        errs.append("jurisdiction.display_jurisdictions must be a list when set")
    j_client_actionable = cls.get("client_surface_visible") is not False and rt in {
        "DOCUMENT",
        "JOB",
        "OBLIGATION",
    }
    if j_client_actionable:
        if not isinstance(dj, list) or not [x for x in dj if str(x or "").strip()]:
            errs.append(
                "jurisdiction.display_jurisdictions must list at least one UK region for client-visible "
                "actionable requirements; an empty or missing list makes applicability unsafe to publish"
            )

    cond = doc.get("conditions") if isinstance(doc.get("conditions"), dict) else {}
    logic = str(cond.get("logic") or "ALL").upper()
    if logic not in ("ALL", "ANY"):
        errs.append("conditions.logic must be ALL or ANY")
    rules = cond.get("rules")
    if rules is not None:
        if not isinstance(rules, list):
            errs.append("conditions.rules must be a list")
        else:
            for i, r in enumerate(rules):
                if not isinstance(r, dict):
                    errs.append(f"conditions.rules[{i}] must be an object")
                    continue
                f = str(r.get("field") or "")
                if f and f not in _VALID_CONDITION_FIELDS:
                    errs.append(f"conditions.rules[{i}].field is not an allowed controlled field: {f}")
                op = str(r.get("op") or "")
                if op and op not in _VALID_CONDITION_OPS:
                    errs.append(f"conditions.rules[{i}].op is not allowed: {op}")

    ab = doc.get("action_behaviour") if isinstance(doc.get("action_behaviour"), dict) else {}
    pam = str(ab.get("primary_action_mode") or "upload_document").strip().lower()
    if pam not in _VALID_ACTION_MODES:
        errs.append("action_behaviour.primary_action_mode is invalid")

    links = doc.get("action_links")
    if links is not None:
        if not isinstance(links, list):
            errs.append("action_links must be a list")
        else:
            errs.extend(validate_action_links_override([x for x in links if isinstance(x, dict)]))
    witm_short = doc.get("why_it_matters_short")
    if witm_short is not None:
        if not isinstance(witm_short, str):
            errs.append("why_it_matters_short must be a string")
        elif len(witm_short.strip()) > 280:
            errs.append("why_it_matters_short too long (max 280 chars)")
    witm_long = doc.get("why_it_matters_long")
    if witm_long is not None:
        if not isinstance(witm_long, str):
            errs.append("why_it_matters_long must be a string")
        elif len(witm_long.strip()) > 4000:
            errs.append("why_it_matters_long too long (max 4000 chars)")
    witm_by_j = doc.get("why_it_matters_by_jurisdiction")
    if witm_by_j is not None:
        if not isinstance(witm_by_j, dict):
            errs.append("why_it_matters_by_jurisdiction must be an object")
        else:
            for k, v in witm_by_j.items():
                kk = str(k).strip().upper()
                if kk not in {"ENGLAND", "WALES", "SCOTLAND", "NORTHERN_IRELAND"}:
                    errs.append(f"why_it_matters_by_jurisdiction has unsupported key: {k}")
                if v is None:
                    continue
                if not isinstance(v, dict):
                    errs.append(f"why_it_matters_by_jurisdiction.{k} must be an object")
                    continue
                s = v.get("short")
                if s is not None and (not isinstance(s, str) or len(s.strip()) > 280):
                    errs.append(f"why_it_matters_by_jurisdiction.{k}.short must be a string <= 280 chars")
                lg = v.get("long")
                if lg is not None and (not isinstance(lg, str) or len(lg.strip()) > 4000):
                    errs.append(f"why_it_matters_by_jurisdiction.{k}.long must be a string <= 4000 chars")
    why_required = cls.get("client_surface_visible") is not False and rt in {"DOCUMENT", "JOB", "OBLIGATION"}
    missing_why_short = why_required and not str(doc.get("why_it_matters_short") or "").strip()
    if missing_why_short:
        errs.append("why_it_matters_short is required for client-visible actionable requirements")
    gov = doc.get("governance") if isinstance(doc.get("governance"), dict) else {}
    needs_review = list(gov.get("needs_review_fields") or [])
    needs_review = [str(x) for x in needs_review if str(x).strip()]
    if missing_why_short and "why_it_matters_short" not in needs_review:
        needs_review.append("why_it_matters_short")
    if (not missing_why_short) and "why_it_matters_short" in needs_review:
        needs_review = [x for x in needs_review if x != "why_it_matters_short"]
    gov["needs_review_fields"] = needs_review
    doc["governance"] = gov

    return errs


def diff_draft_vs_baseline(draft: Dict[str, Any], baseline: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Field-level summary for admin UI (draft vs in-code engine baseline)."""
    rows: List[Dict[str, Any]] = []
    ew = (baseline.get("buckets") or {}).get("ENGLAND_WALES") or {}
    sc = (baseline.get("buckets") or {}).get("SCOTLAND") or {}

    def row(path: str, left: Any, right: Any) -> None:
        rows.append({"path": path, "draft": left, "published_baseline": right, "changed": left != right})

    row("identity.name", (draft.get("identity") or {}).get("name"), ew.get("description") if ew else None)
    row("frequency.frequency_days", (draft.get("frequency") or {}).get("frequency_days"), ew.get("frequency_days"))
    row("frequency.reminder_lead_days", (draft.get("frequency") or {}).get("reminder_lead_days"), ew.get("warning_days"))
    row("classification.requirement_type", (draft.get("classification") or {}).get("requirement_type"), None)
    row("jurisdiction.display_jurisdictions", (draft.get("jurisdiction") or {}).get("display_jurisdictions"), None)
    row("why_it_matters_short", draft.get("why_it_matters_short"), None)
    row("why_it_matters_long", draft.get("why_it_matters_long"), None)
    row("why_it_matters_by_jurisdiction", draft.get("why_it_matters_by_jurisdiction"), None)
    row("action_links.length", len(draft.get("action_links") or []), len(baseline.get("action_links_registry") or []))
    if sc and str(draft.get("canonical_code") or "").upper() == "GAS_SAFETY":
        row(
            "engine.gas_safety.frequency_days_by_bucket",
            (draft.get("frequency") or {}).get("frequency_days"),
            {"ENGLAND_WALES": ew.get("frequency_days"), "SCOTLAND": sc.get("frequency_days")},
        )
    return rows


def merge_partial_draft(existing: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-merge known sections only (no arbitrary keys at root except allowed)."""
    out = deepcopy(existing)
    for key in (
        "identity",
        "classification",
        "jurisdiction",
        "conditions",
        "frequency",
        "action_behaviour",
        "action_links",
        "governance",
        "baseline_alignment",
    ):
        if key in patch and isinstance(patch[key], dict):
            base = out.get(key)
            if not isinstance(base, dict):
                base = {}
            base.update(patch[key])
            out[key] = base
    if "why_it_matters" in patch and "why_it_matters_short" not in patch:
        out["why_it_matters_short"] = str(patch.get("why_it_matters") or "").strip()
    if "why_it_matters_short" in patch:
        out["why_it_matters_short"] = str(patch.get("why_it_matters_short") or "").strip()
    if "why_it_matters_long" in patch:
        out["why_it_matters_long"] = str(patch.get("why_it_matters_long") or "").strip()
    if "why_it_matters_by_jurisdiction" in patch:
        out["why_it_matters_by_jurisdiction"] = (
            patch.get("why_it_matters_by_jurisdiction") if isinstance(patch.get("why_it_matters_by_jurisdiction"), dict) else {}
        )
    if "why_it_matters_by_context" in patch:
        out["why_it_matters_by_context"] = (
            patch.get("why_it_matters_by_context") if isinstance(patch.get("why_it_matters_by_context"), dict) else {}
        )
    if "canonical_code" in patch and patch["canonical_code"]:
        out["canonical_code"] = str(patch["canonical_code"]).strip().upper()
    if "scope_key" in patch and patch["scope_key"] is not None:
        out["scope_key"] = str(patch["scope_key"]).strip() or "DEFAULT"
    out["updated_at"] = _utc()
    return out


def load_baseline_bundle_from_disk() -> Dict[str, Any]:
    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "presentation",
        "compliance_registry_baseline_bundle.json",
    )
    path = os.path.normpath(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _ensure_why_it_matters_short_for_baseline_import(
    doc: Dict[str, Any], summary: Dict[str, Any], canonical_code: str
) -> None:
    """
    Baseline JSON often omits product copy. ``validate_registry_draft`` requires a non-empty
    ``why_it_matters_short`` when the draft is client-visible and actionable. Fill a short
    placeholder and flag for editorial review so imports can persist.
    """
    cls = doc.get("classification") if isinstance(doc.get("classification"), dict) else {}
    rt = str(cls.get("requirement_type") or "").strip().upper()
    if cls.get("client_surface_visible") is False:
        return
    if rt not in {"DOCUMENT", "JOB", "OBLIGATION"}:
        return
    if str(doc.get("why_it_matters_short") or "").strip():
        return
    name = str((doc.get("identity") or {}).get("name") or canonical_code or "requirement").strip()
    stub = f"Statutory and portfolio compliance: {name}."
    doc["why_it_matters_short"] = stub[:280]
    gov = doc.setdefault("governance", {})
    if isinstance(gov, dict):
        nr = [str(x) for x in (gov.get("needs_review_fields") or []) if str(x).strip()]
        if "why_it_matters_short" not in nr:
            nr.append("why_it_matters_short")
        gov["needs_review_fields"] = nr
    summary.setdefault("autofilled_why_it_matters_short", []).append(
        {"canonical_code": str(canonical_code or "").upper(), "scope_key": str(doc.get("scope_key") or "DEFAULT")}
    )


def bundle_entries_to_drafts(bundle: Dict[str, Any], *, actor: Dict[str, str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Convert import bundle entries to draft documents.
    Each entry: canonical_code, scope_key?, draft_overlay? (merged onto default_draft_shell), or full draft.
    Returns (drafts, summary) with mapping warnings and conflicts.
    """
    summary: Dict[str, Any] = {
        "source": bundle.get("source"),
        "disclaimer": bundle.get("disclaimer"),
        "row_count": 0,
        "drafts_built": 0,
        "warnings": [],
        "needs_review": [],
        "duplicate_codes_in_bundle": [],
    }
    entries = bundle.get("entries")
    if not isinstance(entries, list):
        summary["warnings"].append("bundle.entries missing or not a list")
        return [], summary

    seen: set = set()
    out: List[Dict[str, Any]] = []
    for i, raw in enumerate(entries):
        if not isinstance(raw, dict):
            summary["warnings"].append(f"row {i}: not an object")
            continue
        code = str(raw.get("canonical_code") or "").strip().upper()
        sk = str(raw.get("scope_key") or "DEFAULT").strip() or "DEFAULT"
        key = (code, sk)
        if key in seen:
            summary["duplicate_codes_in_bundle"].append({"canonical_code": code, "scope_key": sk})
        seen.add(key)

        if raw.get("draft") and isinstance(raw.get("draft"), dict):
            doc = deepcopy(raw["draft"])
        else:
            doc = default_draft_shell(canonical_code=code, scope_key=sk)
            overlay = raw.get("draft_overlay")
            if isinstance(overlay, dict):
                doc = merge_partial_draft(doc, overlay)

        if not doc.get("entry_id"):
            doc["entry_id"] = str(uuid.uuid4())
        doc.setdefault("status", "draft")
        doc["scope_key"] = sk
        doc["canonical_code"] = code
        doc["updated_at"] = _utc()
        doc["updated_by"] = actor
        gov = doc.setdefault("governance", {})
        if isinstance(gov, dict):
            gov["import_source"] = str(bundle.get("import_bundle_version") or bundle.get("source") or "bundle")
            if raw.get("import_row_ref"):
                gov["import_row_ref"] = raw.get("import_row_ref")
            nrv = raw.get("needs_review_fields")
            if isinstance(nrv, list) and nrv:
                gov["needs_review_fields"] = list(
                    dict.fromkeys(list(gov.get("needs_review_fields") or []) + [str(x) for x in nrv])
                )
                summary["needs_review"].append({"canonical_code": code, "fields": gov["needs_review_fields"]})
        _ensure_why_it_matters_short_for_baseline_import(doc, summary, code)
        out.append(doc)
        summary["drafts_built"] += 1

    summary["row_count"] = len(entries)
    return out, summary


def plan_types_for_draft_canonical(canonical_code: str) -> FrozenSet[str]:
    """
    Planner ``requirement_type`` values (storage slugs) a registry draft canonical_code may affect.
    Includes engine storage_type plus known catalog row aliases that do not reuse the same slug.
    """
    c = str(canonical_code or "").strip().upper()
    out: Set[str] = set()
    for bucket in ("ENGLAND_WALES", "SCOTLAND"):
        spec = get_rule(bucket, c)
        if spec and spec.storage_type:
            out.add(str(spec.storage_type).strip().lower())
    extra: Dict[str, FrozenSet[str]] = {
        "LANDLORD_REGISTRATION": frozenset({"scotland_landlord_registration"}),
        "OCCUPATION_CONTRACT": frozenset({"wales_occupation_contract"}),
        # Core registry uses hmo_fire_risk; catalog may surface a distinct evidence row.
        "HMO_FIRE_RISK": frozenset({"hmo_fire_risk_evidence"}),
    }
    out |= set(extra.get(c, frozenset()))
    return frozenset(out)


def draft_applies_to_portfolio_label(draft: Dict[str, Any], portfolio_label: str) -> bool:
    """True when draft jurisdiction metadata does not exclude this property's portfolio label."""
    label = (portfolio_label or "").strip()
    jur = draft.get("jurisdiction") if isinstance(draft.get("jurisdiction"), dict) else {}
    dj = jur.get("display_jurisdictions")
    if isinstance(dj, list) and dj:
        allowed = {str(x).strip().lower() for x in dj if str(x).strip()}
        return label.lower() in allowed
    sk = str(draft.get("scope_key") or "DEFAULT").strip().upper()
    if sk == "WALES":
        return label == "Wales"
    if sk == "SCOTLAND":
        return label == "Scotland"
    return True


def draft_overlay_specificity(draft: Dict[str, Any]) -> int:
    sk = str(draft.get("scope_key") or "DEFAULT").strip().upper()
    if sk in ("SCOTLAND", "WALES"):
        return 2
    if sk != "DEFAULT":
        return 1
    return 0


def matching_drafts_for_plan_row(
    drafts: List[Dict[str, Any]],
    requirement_type: str,
    portfolio_label: str,
) -> List[Dict[str, Any]]:
    rt = (requirement_type or "").strip().lower()
    matched = [
        d
        for d in drafts
        if isinstance(d, dict)
        and draft_applies_to_portfolio_label(d, portfolio_label)
        and rt in plan_types_for_draft_canonical(str(d.get("canonical_code") or ""))
    ]
    matched.sort(key=lambda d: (-draft_overlay_specificity(d), str(d.get("entry_id") or "")))
    return matched


def merge_draft_overlay_onto_plan_row(prod: Dict[str, Any], draft: Dict[str, Any]) -> Dict[str, Any]:
    """Apply one draft's overlay fields onto a serialized plan row (preview only)."""
    out = dict(prod)
    ident = draft.get("identity") if isinstance(draft.get("identity"), dict) else {}
    name = str(ident.get("name") or "").strip()
    if name:
        out["description"] = name
    freq = draft.get("frequency") if isinstance(draft.get("frequency"), dict) else {}
    if freq.get("frequency_days") is not None:
        try:
            out["frequency_days"] = int(freq["frequency_days"])
        except (TypeError, ValueError):
            pass
    if freq.get("reminder_lead_days") is not None:
        try:
            out["warning_days"] = int(freq["reminder_lead_days"])
        except (TypeError, ValueError):
            pass
    cls = draft.get("classification") if isinstance(draft.get("classification"), dict) else {}
    req_t = str(cls.get("requirement_type") or "").strip().upper()
    if req_t in _VALID_REQ_TYPES:
        out["compliance_requirement_class"] = req_t
    if cls.get("client_surface_visible") is not None:
        out["client_surface_visible"] = bool(cls.get("client_surface_visible"))
    links = draft.get("action_links")
    if isinstance(links, list):
        out["action_links"] = [dict(x) for x in links if isinstance(x, dict)]
    witm_short = str(draft.get("why_it_matters_short") or draft.get("why_it_matters") or "").strip()
    witm_long = str(draft.get("why_it_matters_long") or "").strip()
    if witm_short:
        out["why_it_matters_short"] = witm_short
    if witm_long:
        out["why_it_matters_long"] = witm_long
    by_j = draft.get("why_it_matters_by_jurisdiction")
    if isinstance(by_j, dict) and by_j:
        out["why_it_matters_by_jurisdiction"] = by_j
    return out


# Shipped on every preview response so clients and docs stay aligned on scope (API + UI).
REGISTRY_PREVIEW_COVERAGE: Dict[str, Any] = {
    "decorates_only": True,
    "mode": "decorate_production_plan_rows",
    "summary": (
        "Preview runs the production planner, then merges drafts onto rows that planner already emitted. "
        "It does not synthesise a full post-publish plan."
    ),
    "useful_for": [
        "Metadata / copy changes surfaced as description and related display fields on existing rows.",
        "Client visibility (e.g. client_surface_visible) and classification on existing rows.",
        "Jurisdiction-scoped draft matching (display_jurisdictions / scope_key) for overrides on rows that already exist in the plan.",
        "Frequency and warning cadence hints merged onto matching existing requirement types.",
    ],
    "not_yet": [
        "Brand-new requirement types or plan members that would appear only after publish (would-publish expansion).",
        "Full publish-impact simulation for net-new draft-driven rows not emitted by the current planner + catalog path.",
    ],
    "sequencing_note": (
        "Published snapshot merge is live in the planner/materialiser; this preview still only "
        "decorates rows the planner already emits (no net-new expansion simulation)."
    ),
}


def build_registry_preview_simulation(
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
    drafts: List[Dict[str, Any]],
    *,
    include_explanations: bool = False,
    published_registry_entries: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Read-only simulation: same planner as production (``build_requirement_plan_for_property`` +
    ``serialize_registry_plan_items``), including optional **active published** snapshot merge, then
    merge Mongo draft overlays for display only.

    **Coverage:** Overlays apply only to plan rows the production planner already produces. This is
    not a complete publish-impact simulator for net-new requirement rows (see ``REGISTRY_PREVIEW_COVERAGE``).

    Does not write requirements, does not change the engine, and does not call materialise.
    """
    from services.compliance_rules_registry import portfolio_jurisdiction_label
    from services.compliance_requirement_registry import build_requirement_plan_for_property
    from services.requirement_materialization_service import serialize_registry_plan_items

    cdoc = client_doc or {}
    portfolio = portfolio_jurisdiction_label(property_doc, cdoc)
    items = build_requirement_plan_for_property(
        property_doc,
        cdoc,
        published_registry_entries=published_registry_entries,
    )
    base_rows = serialize_registry_plan_items(
        items,
        include_explanations=include_explanations,
        property_doc=property_doc,
        client_doc=cdoc,
    )
    production: List[Dict[str, Any]] = []
    for item, row in zip(items, base_rows):
        p = dict(row)
        p["description"] = item.description
        production.append(p)

    preview_rows: List[Dict[str, Any]] = []
    for prod in production:
        rt = str(prod.get("requirement_type") or "")
        matched = matching_drafts_for_plan_row(drafts, rt, portfolio)
        preview = dict(prod)
        sources: List[Dict[str, str]] = []
        for d in matched:
            preview = merge_draft_overlay_onto_plan_row(preview, d)
            sources.append(
                {
                    "entry_id": str(d.get("entry_id") or ""),
                    "canonical_code": str(d.get("canonical_code") or ""),
                    "scope_key": str(d.get("scope_key") or "DEFAULT"),
                }
            )
        deltas: Dict[str, Any] = {}
        for k in (
            "description",
            "frequency_days",
            "warning_days",
            "compliance_requirement_class",
            "client_surface_visible",
            "why_it_matters_short",
            "why_it_matters_long",
            "why_it_matters_by_jurisdiction",
            "action_links",
        ):
            pv, pr = preview.get(k), prod.get(k)
            if pv != pr:
                deltas[k] = {"production": pr, "preview": pv}
        preview_rows.append(
            {
                "requirement_type": rt,
                "production": prod,
                "preview": preview,
                "registry_preview": {
                    "read_only": True,
                    "overlay_count": len(matched),
                    "overlay_sources": sources,
                    "deltas": deltas,
                },
            }
        )

    pub_n = len(published_registry_entries) if isinstance(published_registry_entries, dict) else 0
    return {
        "preview_mode": "read_only_draft_overlay",
        "plan_builder": "build_requirement_plan_for_property",
        "serializer": "serialize_registry_plan_items",
        "portfolio_jurisdiction_label": portfolio,
        "published_registry_entry_count": pub_n,
        "draft_documents_considered": len(drafts),
        "planned_row_count": len(preview_rows),
        "rows": preview_rows,
        "preview_coverage": REGISTRY_PREVIEW_COVERAGE,
    }


_UK_ALL = frozenset({"ENGLAND", "WALES", "SCOTLAND", "NORTHERN_IRELAND"})


def registry_entry_key(doc: Dict[str, Any]) -> str:
    """Stable key for published snapshot rows: CANONICAL_CODE|scope_key."""
    cc = str(doc.get("canonical_code") or "").strip().upper()
    sk = str(doc.get("scope_key") or "DEFAULT").strip() or "DEFAULT"
    return f"{cc}|{sk}"


def _norm_region_token(s: str) -> str:
    t = (s or "").strip().upper().replace(" ", "_")
    if t in ("NORTHERN_IRELAND", "NI", "N_IRELAND"):
        return "NORTHERN_IRELAND"
    if t in ("E_W", "ENGLAND_WALES", "ENGLANDANDWALES"):
        return "ENGLAND"  # conservative: do not count as "all four"
    return t


def build_registry_publish_impact(
    draft_docs: List[Dict[str, Any]],
    *,
    published_entries: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Pre-publish / operator summary: per-draft validation, key overlap with active published,
    and union of display_jurisdictions. Honest: does not assert fleet rematerialisation.
    """
    pe: Dict[str, Any] = published_entries if isinstance(published_entries, dict) else {}
    per: List[Dict[str, Any]] = []
    region_union: Set[str] = set()
    scopes: Set[str] = set()
    for raw in draft_docs or []:
        d2: Dict[str, Any] = deepcopy(raw) if raw else {}
        key = registry_entry_key(d2)
        errs = validate_registry_draft(d2)
        jur = d2.get("jurisdiction") if isinstance(d2.get("jurisdiction"), dict) else {}
        dj = jur.get("display_jurisdictions")
        in_pub = key in pe
        r_norm: Set[str] = set()
        if isinstance(dj, list):
            for r in dj:
                rn = _norm_region_token(str(r))
                if rn:
                    r_norm.add(rn)
                    region_union.add(rn)
        uk_all_covered = _UK_ALL.issubset(r_norm) if r_norm else False
        can = str(d2.get("canonical_code") or "")
        if can:
            scopes.add(str(d2.get("scope_key") or "DEFAULT") or "DEFAULT")
        per.append(
            {
                "entry_id": d2.get("entry_id"),
                "canonical_code": d2.get("canonical_code"),
                "scope_key": d2.get("scope_key") or "DEFAULT",
                "publish_key": key,
                "in_active_published": in_pub,
                "change_kind": "update" if in_pub else "new",
                "display_regions": sorted(r_norm) if r_norm else [],
                "validation_errors": errs,
                "broad_uk_covered_by_this_draft": uk_all_covered,
            }
        )
    blockers = [p for p in per if p.get("validation_errors")]
    broad = any(p.get("broad_uk_covered_by_this_draft") for p in per)
    return {
        "draft_count": len(draft_docs or []),
        "unique_scope_keys": sorted(scopes) if scopes else ["DEFAULT"],
        "display_regions_union": sorted(region_union),
        "broad_uk_included_in_union": _UK_ALL.issubset(region_union) if region_union else False,
        "any_draft_covers_all_four_regions": broad,
        "broad_uk_operator_warning": broad
        or (_UK_ALL.issubset(region_union) if region_union else False),
        "per_draft": per,
        "has_blocking_validation_errors": len(blockers) > 0,
        "blocking_draft_count": len(blockers),
    }
