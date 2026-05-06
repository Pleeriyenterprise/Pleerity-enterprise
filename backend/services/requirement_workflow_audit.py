"""
Read-only workflow class reference + drift detection (decision-record alignment).

Does not modify resolver, registry data, evidence authority, or execution paths.
Compares published-registry optional ``client_workflow_class`` (when present) or a static
fallback map to enriched runtime fields emitted by the existing resolver/enrich path.

**Payload scope:** ``apply_workflow_reference_audit`` must only run for admin audience
(``enrich_requirement_dict(..., audience="admin")``). Tenant client routes must call
``strip_workflow_diagnostics_from_payload`` so diagnostic keys never appear in
``enrich_requirements_for_client`` responses.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
from services.maintenance_service import STATUS_COMPLETED, WORK_ORDER_KIND_COMPLIANCE
from services.requirement_action_resolver import ACTION_JOB, ACTION_OBLIGATION, infer_action_type
from services.requirement_code_registry import (
    is_documented_low_risk_alias_slug,
    normalize_requirement_code,
)
from services.requirement_evidence_completeness import requirement_status_appears_satisfied_top_level

logger = logging.getLogger(__name__)

# Never expose these keys on tenant client requirement APIs (admin / audit tooling only).
WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "workflow_class_reference",
        "workflow_class_reference_source",
        "workflow_runtime_behaviour",
        "workflow_mismatch_flags",
        "workflow_mismatch_severity",
    }
)


def strip_workflow_diagnostics_from_payload(out: Dict[str, Any]) -> None:
    """Remove workflow drift diagnostics from a requirement dict (mutates in place)."""
    for k in WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS:
        out.pop(k, None)


# Decision-record §3 enum strings (read-only contract).
WC_DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
WC_MULTI_EVIDENCE = "MULTI_EVIDENCE"
WC_GUIDED_DECLARATION = "GUIDED_DECLARATION"
WC_REGISTRATION_TRACKING = "REGISTRATION_TRACKING"
WC_TENANT_DELIVERY = "TENANT_DELIVERY"
WC_REMEDIATION_JOB = "REMEDIATION_JOB"
WC_EXTERNAL_REMEDIATION_TRACKING = "EXTERNAL_REMEDIATION_TRACKING"
WC_EXTERNAL_ASSESSMENT_EVIDENCE = "EXTERNAL_ASSESSMENT_EVIDENCE"
WC_GUIDANCE_ONLY = "GUIDANCE_ONLY"
WC_HIDDEN_SYSTEM = "HIDDEN_SYSTEM"
WC_UNKNOWN = "UNKNOWN"

# Fallback when registry does not publish ``client_workflow_class`` (see REQUIREMENT_WORKFLOW_CLASS_DECISION_RECORD.md §4).
_FALLBACK_REFERENCE_BY_CANONICAL: Dict[str, str] = {
    "gas_safety": WC_DOCUMENT_UPLOAD,
    "eicr": WC_DOCUMENT_UPLOAD,
    "epc": WC_DOCUMENT_UPLOAD,
    "portable_appliance_test": WC_DOCUMENT_UPLOAD,
    "hmo_license": WC_DOCUMENT_UPLOAD,
    "property_licence": WC_DOCUMENT_UPLOAD,
    "selective_license": WC_DOCUMENT_UPLOAD,
    "landlord_registration": WC_REGISTRATION_TRACKING,
    "scotland_landlord_registration": WC_REGISTRATION_TRACKING,
    "rent_smart_wales": WC_REGISTRATION_TRACKING,
    "landlord_registration_ni": WC_REGISTRATION_TRACKING,
    # Domestic alarm / smoke / CO / fire detection (registry canonical ``smoke_heat_alarms``).
    "smoke_heat_alarms": WC_MULTI_EVIDENCE,
    "fire_risk_assessment": WC_MULTI_EVIDENCE,
    "hmo_fire_risk": WC_MULTI_EVIDENCE,
    "hmo_fire_risk_evidence": WC_MULTI_EVIDENCE,
    "legionella": WC_EXTERNAL_ASSESSMENT_EVIDENCE,
    "lead_testing": WC_EXTERNAL_ASSESSMENT_EVIDENCE,
    "right_to_rent": WC_GUIDED_DECLARATION,
    "deposit_pi": WC_GUIDED_DECLARATION,
    "deposit_prescribed_info": WC_GUIDED_DECLARATION,
    "tenancy_agreement": WC_GUIDED_DECLARATION,
    "occupation_contract": WC_GUIDED_DECLARATION,
    "wales_occupation_contract": WC_GUIDED_DECLARATION,
    "how_to_rent": WC_TENANT_DELIVERY,
    "fitness_for_human_habitation": WC_GUIDANCE_ONLY,
    "repairing_standard": WC_GUIDANCE_ONLY,
    "emergency_lighting": WC_REMEDIATION_JOB,
    "fire_extinguisher": WC_REMEDIATION_JOB,
    "communal_cleaning": WC_REMEDIATION_JOB,
    "communal_fire_doors": WC_REMEDIATION_JOB,
    "hmo_classification": WC_HIDDEN_SYSTEM,
    "property_classification": WC_HIDDEN_SYSTEM,
}
_ACTIVE_STANDARD_CANONICAL = frozenset({"fitness_for_human_habitation", "repairing_standard"})


def _slug_raw_code(raw: str) -> str:
    return str(raw or "").strip().lower().replace(" ", "_")


def extract_registry_workflow_class_reference(published_entry: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Optional registry keys (no migration required — absent keys fall back to static map).
    """
    if not isinstance(published_entry, dict):
        return None
    top = published_entry.get("client_workflow_class")
    if isinstance(top, str) and top.strip():
        return top.strip().upper()
    er = published_entry.get("evidence_resolution")
    if isinstance(er, dict):
        v = er.get("client_workflow_class")
        if isinstance(v, str) and v.strip():
            return v.strip().upper()
    cls = published_entry.get("classification")
    if isinstance(cls, dict):
        v = cls.get("client_workflow_class")
        if isinstance(v, str) and v.strip():
            return v.strip().upper()
    return None


def resolve_workflow_class_reference(
    requirement_code_raw: str,
    *,
    published_entry: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Return (reference_class, source) where source is registry | decision_record_fallback | unknown."""
    reg = extract_registry_workflow_class_reference(published_entry)
    if reg:
        return reg, "registry"
    canon = normalize_requirement_code(requirement_code_raw) or _slug_raw_code(requirement_code_raw)
    if canon and canon in _FALLBACK_REFERENCE_BY_CANONICAL:
        return _FALLBACK_REFERENCE_BY_CANONICAL[canon], "decision_record_fallback"
    return WC_UNKNOWN, "unknown"


def describe_runtime_behaviour(enriched: Dict[str, Any]) -> str:
    """Human-readable summary of resolver-enriched runtime (existing fields only)."""
    wf = str(enriched.get("workflow_class") or "").strip() or "?"
    at = str(enriched.get("action_type") or infer_action_type(enriched)).strip().upper()
    take = enriched.get("take_action") or {}
    pri = take.get("primary") if isinstance(take.get("primary"), dict) else {}
    intent = str(pri.get("intent") or "").strip() or "?"
    kind = str(pri.get("kind") or "").strip() or "?"
    modes = enriched.get("allowed_evidence_modes") or []
    mode_n = len(modes) if isinstance(modes, list) else 0
    return f"workflow_class={wf}; action_type={at}; primary_intent={intent}; primary_kind={kind}; evidence_modes_n={mode_n}"


def _reference_family(ref: str) -> str:
    r = (ref or "").strip().upper()
    if r in (WC_REMEDIATION_JOB,):
        return "job"
    if r in (WC_GUIDANCE_ONLY, WC_HIDDEN_SYSTEM):
        return "guidance"
    if r in (WC_DOCUMENT_UPLOAD, WC_EXTERNAL_REMEDIATION_TRACKING):
        return "document"
    if r in (WC_EXTERNAL_ASSESSMENT_EVIDENCE,):
        return "guided"
    if r in (WC_MULTI_EVIDENCE, WC_GUIDED_DECLARATION, WC_TENANT_DELIVERY, WC_REGISTRATION_TRACKING):
        return "guided"
    return "unknown"


def _runtime_family(enriched: Dict[str, Any]) -> str:
    wf = str(enriched.get("workflow_class") or "").strip().upper()
    at = str(enriched.get("action_type") or infer_action_type(enriched)).strip().upper()
    if at == ACTION_JOB:
        return "job"
    if at == ACTION_OBLIGATION and wf == "GUIDANCE_ONLY":
        return "guidance"
    if wf == "GUIDANCE_ONLY":
        return "guidance"
    if wf == "EXTERNAL_ASSESSMENT_EVIDENCE":
        return "guided"
    if wf == "LEGACY_DOCUMENT_UPLOAD":
        return "document"
    if wf in (
        "GUIDED_EVIDENCE_RESOLUTION",
        "DIRECT_EVIDENCE_ACTION",
        WC_REGISTRATION_TRACKING,
        WC_TENANT_DELIVERY,
        WC_GUIDED_DECLARATION,
    ):
        return "guided"
    return "document"


def compute_workflow_mismatch_flags(
    enriched: Dict[str, Any],
    *,
    reference_class: str,
    reference_source: str,
) -> List[Dict[str, Any]]:
    flags: List[Dict[str, Any]] = []
    raw_code = str(enriched.get("requirement_code") or enriched.get("requirement_type") or "").strip()
    canon = normalize_requirement_code(raw_code)
    stored_slug = _slug_raw_code(raw_code)
    if canon and stored_slug != canon:
        if is_documented_low_risk_alias_slug(stored_slug):
            flags.append(
                {
                    "id": "ALIAS_LEGACY_STORAGE_SLUG",
                    "severity": "LOW",
                    "detail": (
                        f"documented legacy storage slug {stored_slug!r} maps to canonical {canon!r} "
                        "(data hygiene / migration; workflow aligns when resolver uses canonical)"
                    ),
                }
            )
        else:
            flags.append(
                {
                    "id": "ALIAS_NOT_NORMALIZED",
                    "severity": "MEDIUM",
                    "detail": f"stored_code_slug={stored_slug!r} canonical={canon!r}",
                }
            )

    modes = enriched.get("allowed_evidence_modes") or []
    if not isinstance(modes, list):
        modes = []
    norm_modes = [str(m or "").strip().upper() for m in modes if m]
    doc_only = len(norm_modes) == 1 and norm_modes[0] == EVIDENCE_MODE_DOCUMENT_UPLOAD

    ref = reference_class.upper()
    req_jur = str(enriched.get("jurisdiction") or enriched.get("property_jurisdiction") or "").strip().lower()
    take = enriched.get("take_action") if isinstance(enriched.get("take_action"), dict) else {}
    pri = take.get("primary") if isinstance(take.get("primary"), dict) else {}
    primary_intent = str(pri.get("intent") or "").strip().lower()
    primary_label = str(pri.get("label") or "").strip().lower()
    if ref == WC_REGISTRATION_TRACKING and doc_only:
        flags.append(
            {
                "id": "REGISTRATION_TRACKING_DOCUMENT_ONLY",
                "severity": "HIGH",
                "detail": "registration obligations expect STRUCTURED_DECLARATION + DOCUMENT_UPLOAD but only DOCUMENT_UPLOAD is allowed (published registry override or legacy evidence_resolution)",
            }
        )
    if ref == WC_TENANT_DELIVERY and doc_only:
        flags.append(
            {
                "id": "TENANT_DELIVERY_DOCUMENT_ONLY",
                "severity": "HIGH",
                "detail": "How to Rent tenant delivery expects STRUCTURED_DECLARATION + DOCUMENT_UPLOAD but only DOCUMENT_UPLOAD is allowed (published registry override or legacy evidence_resolution)",
            }
        )
    if ref == WC_GUIDED_DECLARATION and doc_only and canon == "right_to_rent":
        flags.append(
            {
                "id": "RIGHT_TO_RENT_GUIDED_DECLARATION_DOCUMENT_ONLY",
                "severity": "HIGH",
                "detail": "Right to Rent expects STRUCTURED_DECLARATION + DOCUMENT_UPLOAD but only DOCUMENT_UPLOAD is allowed (published registry override or legacy evidence_resolution)",
            }
        )
    if ref == WC_GUIDED_DECLARATION and doc_only and canon == "deposit_pi":
        flags.append(
            {
                "id": "DEPOSIT_GUIDED_DECLARATION_DOCUMENT_ONLY",
                "severity": "HIGH",
                "detail": "Deposit compliance expects STRUCTURED_DECLARATION + DOCUMENT_UPLOAD but only DOCUMENT_UPLOAD is allowed (published registry override or legacy evidence_resolution)",
            }
        )
    if ref == WC_GUIDED_DECLARATION and doc_only and canon in ("wales_occupation_contract", "occupation_contract"):
        flags.append(
            {
                "id": "WALES_OCCUPATION_CONTRACT_GUIDED_DECLARATION_DOCUMENT_ONLY",
                "severity": "HIGH",
                "detail": "Wales occupation contract expects STRUCTURED_DECLARATION + DOCUMENT_UPLOAD but only DOCUMENT_UPLOAD is allowed (published registry override or legacy evidence_resolution)",
            }
        )
    if ref == WC_GUIDED_DECLARATION and doc_only and canon == "tenancy_agreement":
        flags.append(
            {
                "id": "TENANCY_AGREEMENT_GUIDED_DECLARATION_DOCUMENT_ONLY",
                "severity": "HIGH",
                "detail": "Tenancy agreement expects STRUCTURED_DECLARATION + DOCUMENT_UPLOAD but only DOCUMENT_UPLOAD is allowed (published registry override or legacy evidence_resolution)",
            }
        )
    if ref == WC_EXTERNAL_ASSESSMENT_EVIDENCE and doc_only and canon == "legionella":
        flags.append(
            {
                "id": "LEGIONELLA_EXTERNAL_ASSESSMENT_DOCUMENT_ONLY",
                "severity": "HIGH",
                "detail": "Legionella external assessment evidence expects STRUCTURED_DECLARATION + DOCUMENT_UPLOAD but only DOCUMENT_UPLOAD is allowed (published registry override or legacy evidence_resolution)",
            }
        )
    if ref == WC_EXTERNAL_ASSESSMENT_EVIDENCE and doc_only and canon == "lead_testing":
        flags.append(
            {
                "id": "LEAD_TESTING_EXTERNAL_ASSESSMENT_DOCUMENT_ONLY",
                "severity": "HIGH",
                "detail": "Lead testing external assessment evidence expects STRUCTURED_DECLARATION + DOCUMENT_UPLOAD but only DOCUMENT_UPLOAD is allowed (published registry override or legacy evidence_resolution)",
            }
        )
    if (canon or stored_slug) in ("lead_testing", "lead_testing_scotland") and req_jur and req_jur != "scotland":
        flags.append(
            {
                "id": "LEAD_TESTING_UNSUPPORTED_JURISDICTION",
                "severity": "HIGH",
                "detail": f"lead_testing surfaced outside Scotland (jurisdiction={req_jur!r}).",
            }
        )
    canon_or_slug = canon or stored_slug
    if canon_or_slug in _ACTIVE_STANDARD_CANONICAL:
        if doc_only or primary_intent == "upload_evidence" or ("upload" in primary_label and "issue" not in primary_label):
            flags.append(
                {
                    "id": "CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY",
                    "severity": "HIGH",
                    "detail": "Condition standards must not resolve to document-upload-primary CTA.",
                }
            )
        if canon_or_slug == "repairing_standard" and req_jur and req_jur != "scotland":
            flags.append(
                {
                    "id": "CONDITION_STANDARD_UNSUPPORTED_JURISDICTION",
                    "severity": "HIGH",
                    "detail": f"repairing_standard surfaced outside Scotland (jurisdiction={req_jur!r}).",
                }
            )
        if canon_or_slug == "fitness_for_human_habitation" and req_jur == "scotland":
            flags.append(
                {
                    "id": "CONDITION_STANDARD_UNSUPPORTED_JURISDICTION",
                    "severity": "HIGH",
                    "detail": "fitness_for_human_habitation surfaced in Scotland where planner support is not expected.",
                }
            )
        status_upper = str(enriched.get("status") or "").strip().upper()
        if requirement_status_appears_satisfied_top_level(enriched) or status_upper in ("COMPLIANT", "VALID"):
            summary = (
                enriched.get("active_standard_status_summary")
                if isinstance(enriched.get("active_standard_status_summary"), dict)
                else {}
            )
            if str(summary.get("state") or "").strip().lower() in ("", "unknown"):
                flags.append(
                    {
                        "id": "CONDITION_STANDARD_MARKED_COMPLETE_WITHOUT_OPERATIONAL_SIGNALS",
                        "severity": "HIGH",
                        "detail": "Condition standard appears satisfied but has unknown operational signal summary.",
                    }
                )
    if ref == WC_MULTI_EVIDENCE and doc_only:
        # Domestic alarm family: authoritative class is MULTI_EVIDENCE; avoid drift noise while legacy rows catch up.
        if normalize_requirement_code(raw_code) != "smoke_heat_alarms":
            flags.append(
                {
                    "id": "MULTI_EVIDENCE_DOCUMENT_ONLY",
                    "severity": "MEDIUM",
                    "detail": "reference expects multi-mode evidence but only DOCUMENT_UPLOAD is allowed",
                }
            )

    if ref == WC_DOCUMENT_UPLOAD and len(norm_modes) > 1 and _runtime_family(enriched) == "guided":
        flags.append(
            {
                "id": "EVIDENCE_MODE_MISMATCH",
                "severity": "MEDIUM",
                "detail": f"reference DOCUMENT_UPLOAD but allowed_modes={norm_modes}",
            }
        )

    rf = _reference_family(ref)
    tf = _runtime_family(enriched)
    if (
        ref != WC_UNKNOWN
        and rf != "unknown"
        and tf != "unknown"
        and rf != tf
    ):
        flags.append(
            {
                "id": "RESOLVER_CTA_MISMATCH",
                "severity": "HIGH" if rf in ("job", "guidance") or tf in ("job", "guidance") else "MEDIUM",
                "detail": f"reference_family={rf} runtime_family={tf}; runtime={describe_runtime_behaviour(enriched)}",
            }
        )

    return flags


def max_severity(flags: List[Dict[str, Any]]) -> str:
    order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    best = "NONE"
    best_n = 0
    for f in flags:
        s = str(f.get("severity") or "").upper()
        if order.get(s, 0) > best_n:
            best_n = order[s]
            best = s
    return best if best_n else "NONE"


def apply_workflow_reference_audit(
    out: Dict[str, Any],
    *,
    published_entry: Optional[Dict[str, Any]],
) -> None:
    """
    Mutates ``out`` in place: adds reference class, runtime behaviour summary, mismatch flags.
    Logs warnings when mismatches are present (drift visibility).
    """
    raw = str(out.get("requirement_code") or out.get("requirement_type") or "").strip()
    ref, src = resolve_workflow_class_reference(raw, published_entry=published_entry)
    out["workflow_class_reference"] = ref
    out["workflow_class_reference_source"] = src
    out["workflow_runtime_behaviour"] = describe_runtime_behaviour(out)

    flags = compute_workflow_mismatch_flags(out, reference_class=ref, reference_source=src)
    ec = out.get("evidence_completeness")
    if (
        isinstance(ec, dict)
        and ec.get("evaluated") is True
        and ec.get("is_complete") is False
        and ref == WC_MULTI_EVIDENCE
        and normalize_requirement_code(raw) == "smoke_heat_alarms"
        and requirement_status_appears_satisfied_top_level(out)
    ):
        flags.append(
            {
                "id": "INCOMPLETE_UNIFIED_REQUIREMENT",
                "severity": "MEDIUM",
                "detail": ec.get("completeness_reason") or "unified domestic alarm obligation missing sub-component evidence",
            }
        )
    out["workflow_mismatch_flags"] = flags
    out["workflow_mismatch_severity"] = max_severity(flags)

    if flags:
        logger.warning(
            "[workflow_audit] mismatch requirement_id=%s code=%s flags=%s",
            out.get("requirement_id"),
            raw,
            [f.get("id") for f in flags],
            extra={
                "requirement_id": out.get("requirement_id"),
                "client_id": out.get("client_id"),
                "canonical_hint": normalize_requirement_code(raw),
                "workflow_class_reference": ref,
                "workflow_mismatch_flags": flags,
            },
        )


def audit_projection_from_enriched(enriched: Dict[str, Any]) -> Dict[str, Any]:
    """Stable admin/API shape for one requirement row."""
    raw = str(enriched.get("requirement_code") or enriched.get("requirement_type") or "").strip()
    canon = normalize_requirement_code(raw) or _slug_raw_code(raw)
    return {
        "requirement_id": enriched.get("requirement_id"),
        "client_id": enriched.get("client_id"),
        "property_id": enriched.get("property_id"),
        "canonical_code": canon,
        "requirement_code_stored": enriched.get("requirement_code_stored"),
        "canonical_requirement_code": enriched.get("canonical_requirement_code"),
        "workflow_class": enriched.get("workflow_class_reference"),
        "workflow_class_source": enriched.get("workflow_class_reference_source"),
        "resolver_workflow_class": enriched.get("workflow_class"),
        "detected_runtime_behaviour": enriched.get("workflow_runtime_behaviour"),
        "mismatch_flags": enriched.get("workflow_mismatch_flags") or [],
        "severity": enriched.get("workflow_mismatch_severity") or "NONE",
    }


async def summarize_workflow_drift_from_requirements_sample(db, *, max_rows: int = 200) -> Dict[str, Any]:
    """
    Scan a recent slice of ``requirements`` rows, enrich via admin path, aggregate mismatch counts.
    Read-only diagnostic (sampled; not exhaustive).
    """
    from services.requirement_truth import enrich_requirements_for_admin

    max_rows = max(1, min(int(max_rows or 200), 2000))
    cur = (
        db.requirements.find({}, {"_id": 0})
        .sort([("updated_at", -1)])
        .limit(max_rows)
    )
    rows = await cur.to_list(length=max_rows)
    if not rows:
        return {
            "rows_scanned": 0,
            "mismatch_rows": 0,
            "by_severity": {},
            "by_flag": {},
            "sample": [],
        }

    enriched = await enrich_requirements_for_admin(db, rows)
    by_sev: Dict[str, int] = {}
    by_flag: Dict[str, int] = {}
    mismatch_rows = 0
    sample: List[Dict[str, Any]] = []

    for e in enriched:
        flags = e.get("workflow_mismatch_flags") or []
        if not flags:
            continue
        mismatch_rows += 1
        sev = str(e.get("workflow_mismatch_severity") or "NONE").upper()
        by_sev[sev] = by_sev.get(sev, 0) + 1
        for fl in flags:
            fid = str(fl.get("id") or "UNKNOWN")
            by_flag[fid] = by_flag.get(fid, 0) + 1
        if len(sample) < 12:
            sample.append(audit_projection_from_enriched(e))

    return {
        "rows_scanned": len(enriched),
        "mismatch_rows": mismatch_rows,
        "by_severity": by_sev,
        "by_flag": by_flag,
        "sample": sample,
    }


async def list_work_order_job_class_mismatches(
    db,
    *,
    published_entries: Optional[Dict[str, Any]],
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Completed compliance work orders whose linked requirement's reference class is not REMEDIATION_JOB.
    """
    from services.compliance_requirement_registry import resolve_published_entry_for_requirement

    limit = max(1, min(int(limit or 100), 500))
    cur = db.work_orders.find(
        {
            "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
            "status": STATUS_COMPLETED,
            "linked_property_requirement_id": {"$exists": True, "$ne": None},
        },
        {
            "_id": 0,
            "work_order_id": 1,
            "client_id": 1,
            "property_id": 1,
            "requirement_code": 1,
            "linked_property_requirement_id": 1,
            "completed_at": 1,
        },
    ).sort([("completed_at", -1)]).limit(limit)

    out: List[Dict[str, Any]] = []
    async for wo in cur:
        rid = str(wo.get("linked_property_requirement_id") or "").strip()
        cid = str(wo.get("client_id") or "").strip()
        if not rid or not cid:
            continue
        req = await db.requirements.find_one({"requirement_id": rid, "client_id": cid}, {"_id": 0})
        if not isinstance(req, dict):
            continue
        code = str(req.get("requirement_code") or req.get("requirement_type") or "").strip()
        pub = resolve_published_entry_for_requirement(
            published_registry_entries=published_entries,
            requirement_type=code,
            portfolio_label=str(req.get("jurisdiction") or ""),
            property_doc=None,
            enforce_conditions=False,
        )
        ref, src = resolve_workflow_class_reference(code, published_entry=pub if isinstance(pub, dict) else None)
        if ref == WC_REMEDIATION_JOB:
            continue
        out.append(
            {
                "work_order_id": wo.get("work_order_id"),
                "requirement_id": rid,
                "client_id": cid,
                "property_id": wo.get("property_id"),
                "canonical_code": normalize_requirement_code(code) or code,
                "workflow_class": ref,
                "workflow_class_source": src,
                "detected_runtime_behaviour": "compliance_work_order_completed",
                "mismatch_flags": [
                    {
                        "id": "JOB_COMPLETION_NON_REMEDIATION_CLASS",
                        "severity": "HIGH",
                        "detail": "Compliance work order completed but decision-record reference class is not REMEDIATION_JOB",
                    }
                ],
                "severity": "HIGH",
            }
        )
    return out
