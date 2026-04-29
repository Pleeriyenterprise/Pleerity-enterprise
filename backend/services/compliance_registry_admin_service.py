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
from services.compliance_registry_conditions import (
    VALID_REGISTRY_CONDITION_FIELDS,
    human_summary_registry_conditions,
    property_matches_registry_conditions,
    validate_registry_conditions,
)
from services.compliance_registry_controlled_vocab import (
    REGISTRY_ALLOWED_UPLOAD_TYPE_SET,
    REGISTRY_IDENTITY_CATEGORY_SET,
    REGISTRY_UK_DISPLAY_REGION_SET,
    normalise_registry_draft_for_storage,
)
from services.requirement_action_links_admin_service import validate_action_links_override

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_VALID_REQ_TYPES = frozenset({"DOCUMENT", "JOB", "OBLIGATION", "SYSTEM"})
_VALID_CRITICALITY = frozenset({"HIGH", "MEDIUM", "LOW"})
_VALID_ACTION_MODES = frozenset({"upload_document", "arrange_job", "view_guidance", "hidden"})
# Backward-compatible names for imports of this module.
_VALID_CONDITION_FIELDS = VALID_REGISTRY_CONDITION_FIELDS

# Seeded on new manual drafts so validation passes; editors must replace before publish-quality copy.
REGISTRY_WHY_SHORT_MANUAL_PLACEHOLDER = (
    "Draft placeholder: replace with a concise client-facing reason (max 280 characters)."
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
            "category": "REGULATORY",
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
        "why_it_matters_short": REGISTRY_WHY_SHORT_MANUAL_PLACEHOLDER,
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
    normalise_registry_draft_for_storage(doc)

    code = str(doc.get("canonical_code") or "").strip().upper()
    if not code or not _CODE_RE.match(code):
        errs.append("canonical_code must match ^[A-Z][A-Z0-9_]{0,63}$")
    sk = str(doc.get("scope_key") or "DEFAULT").strip() or "DEFAULT"
    if len(sk) > 64:
        errs.append("scope_key too long")

    ident = doc.get("identity") if isinstance(doc.get("identity"), dict) else {}
    if not str(ident.get("name") or "").strip():
        errs.append("identity.name is required")
    cat = str(ident.get("category") or "").strip().upper()
    if not cat:
        errs.append("identity.category is required (controlled taxonomy)")
    elif cat not in REGISTRY_IDENTITY_CATEGORY_SET:
        errs.append(
            "identity.category must be a controlled value: "
            + ", ".join(sorted(REGISTRY_IDENTITY_CATEGORY_SET))
            + f"; got {ident.get('category')!r}",
        )

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
    if isinstance(dj, list):
        for idx, x in enumerate(dj):
            tok = str(x or "").strip().upper()
            if not tok:
                errs.append(f"jurisdiction.display_jurisdictions[{idx}] is empty")
            elif tok not in REGISTRY_UK_DISPLAY_REGION_SET:
                errs.append(
                    "jurisdiction.display_jurisdictions must use canonical UK codes "
                    "(ENGLAND, SCOTLAND, WALES, NORTHERN_IRELAND) — "
                    f"got {x!r} at index {idx}",
                )

    cond = doc.get("conditions") if isinstance(doc.get("conditions"), dict) else {}
    errs.extend(validate_registry_conditions(cond))

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
    why_text = str(doc.get("why_it_matters_short") or "").strip()
    missing_why_short = why_required and not why_text
    if missing_why_short:
        errs.append("why_it_matters_short is required for client-visible actionable requirements")
    # Placeholder satisfies API validation but must still surface in editorial review until replaced.
    incomplete_why_short = why_required and (
        not why_text or why_text == REGISTRY_WHY_SHORT_MANUAL_PLACEHOLDER
    )
    gov = doc.get("governance") if isinstance(doc.get("governance"), dict) else {}
    needs_review = list(gov.get("needs_review_fields") or [])
    needs_review = [str(x) for x in needs_review if str(x).strip()]
    if incomplete_why_short and "why_it_matters_short" not in needs_review:
        needs_review.append("why_it_matters_short")
    if (not incomplete_why_short) and "why_it_matters_short" in needs_review:
        needs_review = [x for x in needs_review if x != "why_it_matters_short"]
    gov["needs_review_fields"] = needs_review
    doc["governance"] = gov

    er = doc.get("evidence_resolution") if isinstance(doc.get("evidence_resolution"), dict) else None
    if er:
        from services.compliance_evidence_record_service import ALL_EVIDENCE_MODES

        modes = er.get("allowed_evidence_modes")
        if modes is None:
            modes_norm = ["DOCUMENT_UPLOAD"]
        elif not isinstance(modes, list) or not modes:
            errs.append("evidence_resolution.allowed_evidence_modes must be a non-empty list")
            modes_norm: List[str] = []
        else:
            modes_norm = []
            for i, m in enumerate(modes):
                tok = str(m or "").strip().upper()
                if tok not in ALL_EVIDENCE_MODES:
                    errs.append(f"evidence_resolution.allowed_evidence_modes[{i}] is not a recognised mode")
                elif tok not in modes_norm:
                    modes_norm.append(tok)
        prw = str(er.get("primary_resolution_workflow") or "").strip()
        if prw and prw not in {
            "GUIDED_EVIDENCE_RESOLUTION",
            "LEGACY_DOCUMENT_UPLOAD",
            "DIRECT_EVIDENCE_ACTION",
        }:
            errs.append(
                "evidence_resolution.primary_resolution_workflow must be one of "
                "GUIDED_EVIDENCE_RESOLUTION, DIRECT_EVIDENCE_ACTION, LEGACY_DOCUMENT_UPLOAD"
            )
        if prw == "LEGACY_DOCUMENT_UPLOAD" and "DOCUMENT_UPLOAD" not in set(modes_norm):
            errs.append(
                "evidence_resolution.primary_resolution_workflow=LEGACY_DOCUMENT_UPLOAD requires "
                "DOCUMENT_UPLOAD in allowed_evidence_modes"
            )
        non_doc_modes = [m for m in modes_norm if m != "DOCUMENT_UPLOAD"]
        if prw == "GUIDED_EVIDENCE_RESOLUTION" and modes_norm:
            if len(modes_norm) < 2 and not (len(non_doc_modes) == 1 and len(modes_norm) == 1):
                errs.append(
                    "evidence_resolution.primary_resolution_workflow=GUIDED_EVIDENCE_RESOLUTION requires "
                    "at least two modes, or exactly one non-document mode"
                )
        for k in ("allow_medium_non_document_satisfaction", "allow_low_non_document_satisfaction"):
            if er.get(k) is not None and not isinstance(er.get(k), bool):
                errs.append(f"evidence_resolution.{k} must be boolean when set")
        for k in ("supporting_upload_required", "supporting_upload_recommended"):
            if er.get(k) is not None and not isinstance(er.get(k), bool):
                errs.append(f"evidence_resolution.{k} must be boolean when set")
        aut = er.get("allowed_upload_types")
        if aut is not None:
            if not isinstance(aut, list) or not all(str(x or "").strip() for x in aut):
                errs.append("evidence_resolution.allowed_upload_types must be a non-empty list of mime types/extensions when set")
            else:
                for i, raw in enumerate(aut):
                    tok = str(raw or "").strip().lower()
                    if tok not in REGISTRY_ALLOWED_UPLOAD_TYPE_SET:
                        errs.append(
                            "evidence_resolution.allowed_upload_types[%s] must be one of: %s"
                            % (i, ", ".join(sorted(REGISTRY_ALLOWED_UPLOAD_TYPE_SET)))
                        )
        cs = er.get("checklist_schema_by_mode")
        if cs is not None and not isinstance(cs, dict):
            errs.append("evidence_resolution.checklist_schema_by_mode must be an object when set")
        if er.get("supporting_upload_required") is True and not non_doc_modes:
            errs.append(
                "evidence_resolution.supporting_upload_required requires at least one non-document "
                "mode in allowed_evidence_modes"
            )
        if er.get("verification_required") is not None and not isinstance(er.get("verification_required"), bool):
            errs.append("evidence_resolution.verification_required must be boolean when set")
        if er.get("reviewer_role_required") is not None and not str(er.get("reviewer_role_required") or "").strip():
            errs.append("evidence_resolution.reviewer_role_required must be a non-empty string when set")
        if crit == "HIGH" and bool(er.get("allow_low_non_document_satisfaction")):
            if "evidence_resolution.low_confidence_critical_warning" not in needs_review:
                needs_review.append("evidence_resolution.low_confidence_critical_warning")
        else:
            needs_review = [x for x in needs_review if x != "evidence_resolution.low_confidence_critical_warning"]
        gov["needs_review_fields"] = needs_review

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
    csum = human_summary_registry_conditions(draft.get("conditions") if isinstance(draft.get("conditions"), dict) else {})
    row("conditions (human-readable)", csum, None)
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
        "governance",
        "baseline_alignment",
        "evidence_resolution",
    ):
        if key in patch and isinstance(patch[key], dict):
            base = out.get(key)
            if not isinstance(base, dict):
                base = {}
            base.update(patch[key])
            out[key] = base
    if "action_links" in patch:
        al = patch.get("action_links")
        if isinstance(al, list):
            out["action_links"] = [dict(x) for x in al if isinstance(x, dict)]
        elif al is None:
            out["action_links"] = []
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
            # Domestic fire alarm / detection / testing evidence maps to SMOKE_HEAT_ALARMS published row only.
            if c == "FIRE_DETECTION":
                continue
            out.add(str(spec.storage_type).strip().lower())
    extra: Dict[str, FrozenSet[str]] = {
        # Scotland uses ``scotland_landlord_registration``; NI uses ``landlord_registration_ni`` under
        # ``LANDLORD_REGISTRATION_NI`` so published rows can strict-gate by ``display_jurisdictions``.
        "LANDLORD_REGISTRATION": frozenset({"scotland_landlord_registration", "landlord_registration"}),
        # Legacy + current row variants in live data.
        "OCCUPATION_CONTRACT": frozenset({"wales_occupation_contract", "occupation_contract"}),
        # Core registry uses hmo_fire_risk; catalog may surface a distinct evidence row.
        "HMO_FIRE_RISK": frozenset({"hmo_fire_risk_evidence"}),
        # Single England-facing authority: both storage slugs attach to RIGHT_TO_RENT only.
        "RIGHT_TO_RENT": frozenset({"right_to_rent", "right_to_rent_checks"}),
        "RENT_SMART_WALES": frozenset({"rent_smart_wales", "rent_smart_wales_registration"}),
        "RENT_SMART_WALES_REGISTRATION": frozenset({"rent_smart_wales", "rent_smart_wales_registration"}),
        "LANDLORD_REGISTRATION_NI": frozenset({"landlord_registration_ni"}),
        "PAT_TESTING": frozenset({"portable_appliance_test", "pat_testing"}),
        "PORTABLE_APPLIANCE": frozenset({"portable_appliance_test", "pat_testing"}),
        "HMO_LICENSING": frozenset({"hmo_license", "property_licence", "hmo_licensing"}),
        # SMOKE_HEAT_ALARMS: single published authority for domestic alarm + detection/testing evidence slugs.
        "SMOKE_HEAT_ALARMS": frozenset(
            {
                "smoke_alarms",
                "co_alarms",
                "smoke_heat_alarms",
                "fire_alarm",
                "fire_detection",
            }
        ),
        "TENANCY_DEPOSIT_PROTECTION": frozenset({"deposit_pi", "tenancy_deposit_protection"}),
        "TENANCY_AGREEMENT": frozenset({"tenancy_agreement"}),
        "HOW_TO_RENT": frozenset({"how_to_rent"}),
        # Matches ``CANONICAL_FIRE_RISK_ASSESSMENT`` / action-link registry spelling.
        "FIRE_RISK_ASSESSMENT": frozenset({"fire_risk_assessment"}),
        # Often informational/system; currently no direct planner emission in some tenants.
        "FITNESS_FOR_HUMAN_HABITATION": frozenset({"fitness_for_human_habitation"}),
        "REPAIRING_STANDARD": frozenset({"repairing_standard"}),
        "LEAD_TESTING": frozenset({"lead_testing"}),
    }
    out |= set(extra.get(c, frozenset()))
    return frozenset(out)


def _display_jurisdiction_list_to_region_codes(dj: Any) -> Optional[Set[str]]:
    """
    Normalise ``jurisdiction.display_jurisdictions`` tokens to canonical region codes.

    Returns:
        non-empty set of codes in REGISTRY_UK_DISPLAY_REGION_SET,
        empty set when the list exists but resolves to no valid codes (fail closed),
        None when ``dj`` is missing / not a list (legacy: fall through to scope_key heuristics).
    """
    if not isinstance(dj, list):
        return None
    codes: Set[str] = set()
    for x in dj:
        tok = str(x or "").strip().upper().replace(" ", "_")
        if tok == "NORTHERNIRELAND":
            tok = "NORTHERN_IRELAND"
        if tok in REGISTRY_UK_DISPLAY_REGION_SET:
            codes.add(tok)
    return codes


def draft_applies_to_portfolio_label(draft: Dict[str, Any], portfolio_label: str) -> bool:
    """True when the draft's ``display_jurisdictions`` explicitly includes this property's UK region."""
    from services.requirement_action_links import portfolio_label_to_region

    active_region = portfolio_label_to_region(portfolio_label)
    label = (portfolio_label or "").strip()
    jur = draft.get("jurisdiction") if isinstance(draft.get("jurisdiction"), dict) else {}
    dj = jur.get("display_jurisdictions")
    codes = _display_jurisdiction_list_to_region_codes(dj)
    if codes is not None:
        return active_region in codes
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
    property_doc: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    rt = (requirement_type or "").strip().lower()
    matched = [
        d
        for d in drafts
        if isinstance(d, dict)
        and draft_applies_to_portfolio_label(d, portfolio_label)
        and property_matches_registry_conditions(property_doc, d.get("conditions"))
        and rt in plan_types_for_draft_canonical(str(d.get("canonical_code") or ""))
    ]
    matched.sort(key=lambda d: (-draft_overlay_specificity(d), str(d.get("entry_id") or "")))
    return matched


def merge_draft_overlay_onto_plan_row(
    prod: Dict[str, Any],
    draft: Dict[str, Any],
    *,
    portfolio_label: str,
) -> Dict[str, Any]:
    """Apply one draft's overlay fields onto a serialized plan row (preview / published merge)."""
    from services.requirement_action_links import filter_action_links_for_region, portfolio_label_to_region

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

    ab = draft.get("action_behaviour") if isinstance(draft.get("action_behaviour"), dict) else {}
    pam = str(ab.get("primary_action_mode") or "").strip().lower()
    if pam in _VALID_ACTION_MODES:
        out["primary_action_mode"] = pam
    cta_ov = str(ab.get("cta_label_override") or "").strip()
    if cta_ov:
        out["cta_label_override"] = cta_ov
    if pam == "hidden":
        out["client_surface_visible"] = False

    region = portfolio_label_to_region(portfolio_label)
    if isinstance(out.get("action_links"), list) and out["action_links"]:
        out["action_links"] = filter_action_links_for_region(
            [x for x in out["action_links"] if isinstance(x, dict)],
            region,
            max_links=24,
        )

    er = draft.get("evidence_resolution") if isinstance(draft.get("evidence_resolution"), dict) else None
    if er:
        modes = er.get("allowed_evidence_modes")
        if isinstance(modes, list) and modes:
            out["allowed_evidence_modes"] = [
                str(x).strip().upper() for x in modes if str(x or "").strip()
            ]
        prw = str(er.get("primary_resolution_workflow") or "").strip()
        if prw:
            out["primary_resolution_workflow"] = prw
        if er.get("allow_medium_non_document_satisfaction") is not None:
            out["allow_medium_non_document_satisfaction"] = bool(er.get("allow_medium_non_document_satisfaction"))
        if er.get("allow_low_non_document_satisfaction") is not None:
            out["allow_low_non_document_satisfaction"] = bool(er.get("allow_low_non_document_satisfaction"))
        if er.get("supporting_upload_required") is not None:
            out["supporting_upload_required"] = bool(er.get("supporting_upload_required"))
        if er.get("supporting_upload_recommended") is not None:
            out["supporting_upload_recommended"] = bool(er.get("supporting_upload_recommended"))
        aut = er.get("allowed_upload_types")
        if isinstance(aut, list) and aut:
            out["allowed_upload_types"] = [str(x).strip().lower() for x in aut if str(x or "").strip()]
        cs = er.get("checklist_schema_by_mode")
        if isinstance(cs, dict) and cs:
            out["checklist_schema_by_mode"] = cs
        if er.get("verification_required") is not None:
            out["verification_required"] = bool(er.get("verification_required"))
        rrr = str(er.get("reviewer_role_required") or "").strip()
        if rrr:
            out["reviewer_role_required"] = rrr
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
        "Property applicability via ``conditions.rules`` (same JSON as drafts) so overlays respect boolean / scalar predicates.",
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
        matched = matching_drafts_for_plan_row(drafts, rt, portfolio, property_doc)
        preview = dict(prod)
        sources: List[Dict[str, str]] = []
        for d in matched:
            preview = merge_draft_overlay_onto_plan_row(preview, d, portfolio_label=portfolio)
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
