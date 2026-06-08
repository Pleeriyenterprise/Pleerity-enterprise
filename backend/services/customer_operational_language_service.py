"""
Customer Operational Language Layer — cognition governance boundary.

Internal engine / gap / classifier semantics must not reach landlord, tenant,
contractor, or client-admin surfaces. Admin diagnostics and audit logs are exempt.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

ROLE_LANDLORD = "landlord"
ROLE_CLIENT = "client"
ROLE_TENANT = "tenant"
ROLE_CONTRACTOR = "contractor"
ROLE_CLIENT_ADMIN = "client_admin"

# Fields stripped from customer-visible payloads (preserved internally via _internal mirror if needed).
INTERNAL_FIELD_NAMES = frozenset(
    {
        "gap_key",
        "gap_kind",
        "gap_severity",
        "gap_surfaces",
        "gap_policy",
        "diagnostic_gap_recommended_url",
        "diagnostic_gap_recommended_action_label",
        "recommended_client_authority",
        "operational_root_key",
        "triggering_rule",
        "classifier_state",
        "reconciliation_trace",
        "governance_family",
        "stale_owner",
        "queue_backed_review",
        "evidence_authority_synced_at",
        "registry_metadata",
        "compliance_engine",
        "issue_created_from",
        "issue_triggering_rule",
        "maintenance_escalation_allowed",
    }
)

# Removed from customer payloads after translation (may be read mid-pipeline from metadata).
POST_TRANSLATION_METADATA_STRIP = frozenset(
    {
        "issue_created_from",
        "issue_triggering_rule",
        "maintenance_escalation_allowed",
        "gap_kind",
        "semantic_state",
        "gap_key",
        "severity",
    }
)

FORBIDDEN_CUSTOMER_TERMS = re.compile(
    r"\b("
    r"MISMATCHED_EVIDENCE|MISSING_EVIDENCE|GAP_[A-Z_]+|AUTHORITY_UNSYNCED|"
    r"CLASSIFICATION_AMBIGUOUS|RECONCILIATION_PENDING|NO_ACCEPTABLE_EVIDENCE|"
    r"operational_root_key|gap_key|semantic_state|truth_presentation_stage|"
    r"classification signal|reconciliation|orphan|queue mismatch|"
    r"stale sync|governance.family"
    r")\b",
    re.I,
)

UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.I,
)
GAP_KEY_LEAK = re.compile(r"\bGap:\s*[A-Z_]+.*", re.I | re.S)
KEY_LEAK = re.compile(r"\bKey:\s*[0-9a-f:\-]+.*", re.I | re.S)
SEVERITY_FLAG = re.compile(r"\(\s*(HIGH|MEDIUM|LOW|CRITICAL)\s*\)", re.I)

_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "MISMATCHED_EVIDENCE": {
        "summary": "We could not confidently match this document to a requirement yet.",
        "detail": "Please review the uploaded file and confirm it is the correct certificate or record for this property.",
        "cta": "Review uploaded document",
    },
    "MISSING_EVIDENCE": {
        "summary": "Valid evidence is still needed for this requirement.",
        "detail": "Upload the correct certificate or record so this requirement can be confirmed.",
        "cta": "Upload document",
    },
    "MISSING_EVIDENCE_HIGH": {
        "summary": "A valid certificate or record is still needed for this property.",
        "detail": "Upload the required evidence to keep this requirement on track.",
        "cta": "Upload document",
    },
    "NO_ACCEPTABLE_EVIDENCE": {
        "summary": "We still need valid evidence for this requirement.",
        "detail": "Upload or confirm the correct record for this obligation.",
        "cta": "Upload document",
    },
    "CLASSIFICATION_AMBIGUOUS": {
        "summary": "We need more information before this requirement can be confirmed.",
        "detail": "Review the uploaded file or provide the missing details.",
        "cta": "Review uploaded document",
    },
    "RECONCILIATION_PENDING": {
        "summary": "We are still processing the latest update.",
        "detail": "No action is required right now — check back shortly.",
        "cta": "View requirement",
    },
    "EVIDENCE_UPLOADED_UNCONFIRMED": {
        "summary": "Uploaded evidence still needs your confirmation.",
        "detail": "Confirm the dates and details so they apply correctly.",
        "cta": "Confirm details",
    },
    "EXPIRED": {
        "summary": "Evidence for this requirement has expired.",
        "detail": "Renew or replace the record to restore compliance.",
        "cta": "Renew evidence",
    },
    "EXPIRING_SOON": {
        "summary": "Evidence for this requirement is due for renewal soon.",
        "detail": "Plan renewal before the expiry date.",
        "cta": "Plan renewal",
    },
    "ACTION_REQUIRED": {
        "summary": "This requirement needs your attention.",
        "detail": "Complete the next step shown for this obligation.",
        "cta": "Take action",
    },
    "AUTHORITY_UNSYNCED": {
        "summary": "We are updating the latest compliance status.",
        "detail": "Refresh shortly if this item still appears.",
        "cta": "View requirement",
    },
    "DELIVERY_PROOF_MISSING": {
        "summary": "Completion proof is still needed for this workflow.",
        "detail": "Add proof that the required work or delivery was completed.",
        "cta": "Add proof",
    },
    "COMPLIANCE_GAP": {
        "summary": "A compliance item needs your attention.",
        "detail": "Review the requirement and complete the next step.",
        "cta": "View requirement",
    },
    "DEFAULT": {
        "summary": "Something needs your attention on this property.",
        "detail": "Review the details and complete the recommended next step.",
        "cta": "View details",
    },
}

_EVIDENCE_GAP_KINDS = frozenset(
    {
        "MISMATCHED_EVIDENCE",
        "MISSING_EVIDENCE",
        "EVIDENCE_UPLOADED_UNCONFIRMED",
        "NO_ACCEPTABLE_EVIDENCE",
        "CLASSIFICATION_AMBIGUOUS",
        "ACTION_REQUIRED",
        "AUTHORITY_UNSYNCED",
    }
)


def _norm_role(role: Optional[str]) -> str:
    r = str(role or ROLE_CLIENT).strip().lower()
    if r in ("client", "client_admin", "landlord", "owner"):
        return ROLE_LANDLORD
    if r in ("tenant",):
        return ROLE_TENANT
    if r in ("contractor",):
        return ROLE_CONTRACTOR
    return ROLE_LANDLORD


def _lookup_translation(internal_code: Optional[str]) -> Dict[str, str]:
    code = str(internal_code or "").strip().upper()
    if code in _TRANSLATIONS:
        return _TRANSLATIONS[code]
    if code.endswith("_HIGH") or code.endswith("_MEDIUM") or code.endswith("_LOW"):
        base = code.rsplit("_", 1)[0]
        if base in _TRANSLATIONS:
            return _TRANSLATIONS[base]
    return _TRANSLATIONS["DEFAULT"]


def _strip_internal_leaks(text: str) -> str:
    if not text:
        return ""
    out = str(text)
    out = GAP_KEY_LEAK.sub("", out)
    out = KEY_LEAK.sub("", out)
    out = UUID_PATTERN.sub("", out)
    out = SEVERITY_FLAG.sub("", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def translate_internal_operational_message(
    message: str,
    *,
    internal_code: Optional[str] = None,
    role: Optional[str] = None,
) -> str:
    """Replace or scrub internal diagnostic text with customer-safe language."""
    raw = str(message or "").strip()
    if not raw:
        return _lookup_translation(internal_code)["summary"]
    if FORBIDDEN_CUSTOMER_TERMS.search(raw) or "Gap:" in raw or "Key:" in raw:
        return _lookup_translation(internal_code)["summary"]
    cleaned = _strip_internal_leaks(raw)
    if FORBIDDEN_CUSTOMER_TERMS.search(cleaned):
        return _lookup_translation(internal_code)["summary"]
    return cleaned or _lookup_translation(internal_code)["summary"]


def derive_customer_safe_issue_summary(
    issue: Dict[str, Any],
    *,
    role: Optional[str] = None,
) -> str:
    trig = str(issue.get("triggering_rule") or "")
    gap_kind = trig.split(":", 1)[-1].strip().upper() if trig.startswith("compliance_gap:") else None
    if not gap_kind:
        gap_kind = str(issue.get("gap_kind") or "").strip().upper() or None
    if gap_kind or issue.get("created_from") == "compliance":
        row = _lookup_translation(gap_kind or "COMPLIANCE_GAP")
        desc = str(issue.get("description") or "")
        if "gas safety" in desc.lower() or "cp12" in desc.lower():
            return "A valid gas safety certificate is still needed for this property."
        if "evidence" in desc.lower() and "match" in desc.lower():
            return _TRANSLATIONS["MISMATCHED_EVIDENCE"]["summary"]
        if "evidence" in desc.lower() and "missing" in desc.lower():
            return _TRANSLATIONS["MISSING_EVIDENCE"]["summary"]
        return row["summary"]
    desc = _strip_internal_leaks(str(issue.get("description") or ""))
    if desc and not FORBIDDEN_CUSTOMER_TERMS.search(desc):
        first = desc.split("\n")[0].strip()
        if len(first) > 12 and "Gap:" not in first:
            return first[:160]
    return "A maintenance item needs review on this property."


def derive_customer_safe_issue_detail(
    issue: Dict[str, Any],
    *,
    role: Optional[str] = None,
) -> str:
    trig = str(issue.get("triggering_rule") or "")
    gap_kind = trig.split(":", 1)[-1].strip().upper() if trig.startswith("compliance_gap:") else None
    if not gap_kind:
        gap_kind = str(issue.get("gap_kind") or "").strip().upper() or None
    if gap_kind or issue.get("created_from") == "compliance":
        return _lookup_translation(gap_kind or "COMPLIANCE_GAP")["detail"]
    desc = _strip_internal_leaks(str(issue.get("description") or ""))
    if desc and not FORBIDDEN_CUSTOMER_TERMS.search(desc):
        return desc[:400]
    return "Review the details and complete the recommended next step."


def derive_customer_safe_cta(
    context: Dict[str, Any],
    *,
    role: Optional[str] = None,
) -> Dict[str, str]:
    gap_kind = str(context.get("gap_kind") or "").strip().upper()
    trig = str(context.get("triggering_rule") or "")
    if not gap_kind and trig.startswith("compliance_gap:"):
        gap_kind = trig.split(":", 1)[-1].strip().upper()
    if gap_kind or context.get("created_from") == "compliance":
        label = _lookup_translation(gap_kind or "COMPLIANCE_GAP")["cta"]
        url = str(context.get("recommended_url") or context.get("primary_action_url") or "").strip()
        if not url and context.get("related_property_id"):
            url = f"/documents?property_id={context.get('related_property_id')}"
        return {"label": label, "url": url or "/documents"}
    label = str(context.get("recommended_action_label") or context.get("primary_action_label") or "View details").strip()
    url = str(context.get("recommended_url") or context.get("primary_action_url") or "/operations/issues").strip()
    return {"label": label, "url": url}


def is_customer_safe_maintenance_escalation(context: Dict[str, Any]) -> bool:
    """Evidence/compliance gaps must not surface maintenance-job CTAs as primary."""
    trig = str(context.get("triggering_rule") or "")
    if trig.startswith("compliance_gap:"):
        return False
    if str(context.get("created_from") or "") in ("compliance", "system") and context.get("operational_root_key"):
        gap_kind = trig.split(":", 1)[-1].upper() if ":" in trig else ""
        if not gap_kind and str(context.get("operational_root_key") or ""):
            return False
    gap_kind = str(context.get("gap_kind") or "").strip().upper()
    if gap_kind in _EVIDENCE_GAP_KINDS:
        return False
    st = str(context.get("source_type") or context.get("action_type") or "")
    if st in ("missing_document", "open_operational_issue") and (
        gap_kind or trig.startswith("compliance_gap:")
    ):
        return False
    return True


def _issue_context_from_payload(out: Dict[str, Any]) -> Dict[str, Any]:
    meta = out.get("metadata") if isinstance(out.get("metadata"), dict) else {}
    trig = (
        out.get("triggering_rule")
        or meta.get("triggering_rule")
        or meta.get("issue_triggering_rule")
        or ""
    )
    created = (
        out.get("created_from")
        or meta.get("created_from")
        or meta.get("issue_created_from")
        or ""
    )
    gap_kind = out.get("gap_kind") or meta.get("gap_kind")
    if not gap_kind and str(trig).startswith("compliance_gap:"):
        gap_kind = str(trig).split(":", 1)[-1].strip().upper()
    return {
        **out,
        **meta,
        "triggering_rule": trig,
        "created_from": created,
        "gap_kind": gap_kind,
        "operational_root_key": out.get("operational_root_key") or meta.get("operational_root_key"),
    }


def customer_severity_phrase(internal_severity: Optional[str]) -> Optional[str]:
    s = str(internal_severity or "").strip().upper()
    if s in ("CRITICAL", "HIGH"):
        return "Needs attention soon"
    if s == "MEDIUM":
        return "Needs follow-up"
    return None


def suppress_internal_operational_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Remove internal-only keys from a customer payload (shallow + metadata)."""
    if not isinstance(payload, dict):
        return payload
    out = {k: v for k, v in payload.items() if k not in INTERNAL_FIELD_NAMES}
    meta = out.get("metadata")
    if isinstance(meta, dict):
        out["metadata"] = {k: v for k, v in meta.items() if k not in INTERNAL_FIELD_NAMES}
    return out


def sanitize_customer_visible_payload(
    payload: Dict[str, Any],
    *,
    role: Optional[str] = None,
    surface: str = "generic",
) -> Dict[str, Any]:
    """Universal customer payload sanitisation before API / task delivery."""
    if not isinstance(payload, dict):
        return payload
    out = deepcopy(payload)
    issue_ctx = _issue_context_from_payload(out)

    for key in ("title", "description", "why_matters", "recommended_action", "user_safe_summary"):
        if key in out and out[key] is not None:
            out[key] = translate_internal_operational_message(
                str(out[key]),
                internal_code=issue_ctx.get("gap_kind"),
                role=role,
            )

    if out.get("source_type") == "issue" or str(out.get("action_type") or "") == "open_operational_issue":
        out["customer_safe_title"] = derive_customer_safe_issue_summary(issue_ctx, role=role)
        out["customer_safe_description"] = derive_customer_safe_issue_detail(issue_ctx, role=role)
        out["title"] = out["customer_safe_title"]
        out["description"] = out["customer_safe_description"]
        cta = derive_customer_safe_cta(issue_ctx, role=role)
        if not is_customer_safe_maintenance_escalation(issue_ctx):
            out["primary_action_label"] = cta["label"]
            out["primary_recommended_action"] = cta["label"]
            if cta.get("url"):
                out["primary_action_url"] = cta["url"]
            pri = out.get("primary_cta")
            if isinstance(pri, dict):
                pri["label"] = cta["label"]
                if cta.get("url"):
                    pri["route"] = cta["url"]

    sev_phrase = customer_severity_phrase(
        out.get("severity") or (out.get("metadata") or {}).get("severity")
    )
    if sev_phrase:
        out["urgency_phrase"] = sev_phrase

    out = suppress_internal_operational_fields(out)
    out.pop("severity", None)
    meta = out.get("metadata")
    if isinstance(meta, dict):
        for k in POST_TRANSLATION_METADATA_STRIP:
            meta.pop(k, None)

    return out


def sanitize_task_for_customer(task: Dict[str, Any], *, role: Optional[str] = None) -> Dict[str, Any]:
    return sanitize_customer_visible_payload(task, role=role, surface="task")


def sanitize_issue_for_customer(issue: Dict[str, Any], *, role: Optional[str] = None) -> Dict[str, Any]:
    """Sanitise maintenance issue payloads for client portal list/detail surfaces."""
    if not isinstance(issue, dict):
        return issue
    out = deepcopy(issue)
    issue_ctx = _issue_context_from_payload(out)

    safe_summary = derive_customer_safe_issue_summary(issue_ctx, role=role)
    safe_detail = derive_customer_safe_issue_detail(issue_ctx, role=role)
    out["customer_safe_title"] = safe_summary
    out["customer_safe_description"] = safe_detail
    out["description"] = safe_detail

    triage = out.get("triage")
    if isinstance(triage, dict):
        reasoning = triage.get("reasoning") or []
        if isinstance(reasoning, list):
            triage["reasoning"] = [
                translate_internal_operational_message(str(r), internal_code=issue_ctx.get("gap_kind"), role=role)
                for r in reasoning
                if str(r or "").strip()
            ]

    source = str(out.get("source") or "").strip().lower()
    created_from = str(out.get("created_from") or "").strip().lower()
    if source == "system" or created_from == "compliance":
        out["source_display"] = "Compliance follow-up"
    elif source == "tenant" or source == "tenant_request":
        out["source_display"] = "Tenant report"
    elif source == "client":
        out["source_display"] = "Your report"
    else:
        out["source_display"] = "Maintenance"

    out = suppress_internal_operational_fields(out)
    for k in ("triggering_rule", "created_from", "operational_root_key", "gap_kind", "severity"):
        out.pop(k, None)
    meta = out.get("metadata")
    if isinstance(meta, dict):
        for k in POST_TRANSLATION_METADATA_STRIP:
            meta.pop(k, None)
    return out


def translation_matrix_export() -> Dict[str, Any]:
    return {"version": 1, "mappings": _TRANSLATIONS}


def contains_forbidden_customer_language(text: str) -> bool:
    t = str(text or "")
    if not t.strip():
        return False
    if FORBIDDEN_CUSTOMER_TERMS.search(t):
        return True
    if UUID_PATTERN.search(t) and ("Key:" in t or "Gap:" in t):
        return True
    if "Gap:" in t and re.search(r"[A-Z_]{8,}", t):
        return True
    return False
