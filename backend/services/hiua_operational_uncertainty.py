"""
Phase 1: HIGH_IMPACT_UNRESOLVED_APPLICABILITY (HIUA) — read-time operational uncertainty.

UNKNOWN applicability must not be treated as REQUIRED; strict ``high_risk_gap`` /
``critical_mandatory_breach`` predicates are unchanged. HIUA is a separate signal only.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Optional, Set

from services.policy_field_normalizer import normalize_requirement_code, resolve_policy_facts
from services.policy_reason_codes import PolicyReasonCode

# Aligned with ``portfolio_risk_policy`` bad evidence states (do not import private sets).
HIUA_BAD_EVIDENCE_STATES: FrozenSet[str] = frozenset(
    {"MISSING", "REJECTED", "MISMATCH_FLAGGED", "VERIFIED_EXPIRED"}
)
HIUA_GOOD_EVIDENCE_CONFIRMED: FrozenSet[str] = frozenset({"VERIFIED"})

HIUA_ELIGIBLE_REQUIREMENT_CODES: FrozenSet[str] = frozenset(
    {
        "gas_safety",
        "eicr",
        "smoke_alarm",
        "co_alarm",
        "hmo_licence",
        "hmo_license",
        "fire_risk_assessment",
        "fire_doors",
        "emergency_lighting",
    }
)

HIUA_MATERIAL_GAP_KINDS: FrozenSet[str] = frozenset({"MISSING_EVIDENCE", "MISMATCHED_EVIDENCE", "EXPIRED"})
HIUA_EXPIRING_SOON_KIND = "EXPIRING_SOON"
HIUA_EXPIRING_SOON_MAX_DAYS = 30

_MAX_GAPS_SCAN_DEFAULT = 500
_MAX_DETAIL_DEFAULT = 20


def _gap_to_requirement_like(gap: Dict[str, Any]) -> Dict[str, Any]:
    """Build a minimal requirement-shaped dict from persisted gap policy snapshots."""
    row: Dict[str, Any] = {
        "requirement_code": gap.get("requirement_code"),
        "requirement_type": gap.get("requirement_code") or gap.get("requirement_type"),
        "applicability_state": gap.get("applicability_state"),
        "is_mandatory": gap.get("is_mandatory"),
        "policy_criticality": gap.get("policy_criticality"),
    }
    if gap.get("requirement_code_normalized"):
        row["requirement_code_normalized"] = gap.get("requirement_code_normalized")
    ea = gap.get("evidence_authority")
    if isinstance(ea, dict):
        row["evidence_authority"] = ea
    else:
        row["evidence_authority"] = {}
    evn = gap.get("evidence_state_normalized")
    if evn and not (isinstance(ea, dict) and (ea.get("state") or "").strip()):
        row["evidence_state"] = evn
    return row


def derive_hiua_signal_for_open_gap(gap: Dict[str, Any]) -> bool:
    """
    Read-time HIUA: high-impact code, applicability still UNKNOWN, material exposure,
    strict policy lanes not already asserted on the gap row.

    Does not read ``severity`` (no severity-only escalation).
    """
    if not isinstance(gap, dict):
        return False
    if str(gap.get("status") or "").lower() != "open":
        return False
    if bool(gap.get("high_risk_gap")) or bool(gap.get("critical_mandatory_breach")):
        return False

    req_like = _gap_to_requirement_like(gap)
    facts = resolve_policy_facts(
        req_like,
        registry_metadata={},
        catalog_defaults={},
        gap_payload={
            "gap_kind": gap.get("gap_kind"),
            "authority_snapshot": gap.get("authority_snapshot") if isinstance(gap.get("authority_snapshot"), dict) else {},
        },
    )
    if str(facts.get("applicability_state") or "").upper() != "UNKNOWN":
        return False

    code = str(facts.get("requirement_code_normalized") or "").strip().lower()
    if not code:
        code = normalize_requirement_code(req_like)
    code = str(code or "").strip().lower()
    if code not in HIUA_ELIGIBLE_REQUIREMENT_CODES:
        return False

    gk = str(gap.get("gap_kind") or "").strip().upper()
    ev = str(facts.get("evidence_state_normalized") or "").strip().upper()

    if gk in HIUA_MATERIAL_GAP_KINDS:
        return ev in HIUA_BAD_EVIDENCE_STATES

    if gk == HIUA_EXPIRING_SOON_KIND:
        raw_d = gap.get("days_to_expiry")
        try:
            di = int(raw_d) if raw_d is not None else None
        except (TypeError, ValueError):
            di = None
        if di is None or not (0 <= di <= HIUA_EXPIRING_SOON_MAX_DAYS):
            return False
        return ev not in HIUA_GOOD_EVIDENCE_CONFIRMED

    return False


def hiua_command_centre_copy(*, active: bool, count: int) -> Dict[str, Optional[str]]:
    """Short strings for Command Centre (no legal certification wording)."""
    if not active or count <= 0:
        return {
            "message": None,
            "tooltip": None,
            "filter_label": None,
        }
    return {
        "message": (
            f"{count} high-impact item(s) need applicability confirmation before policy risk classification is final."
        ),
        "tooltip": (
            "Eligibility is not yet confirmed for one or more high-impact obligations. "
            "Review and confirm applicability; this is operational follow-up, not a confirmed policy breach flag."
        ),
        "filter_label": "High impact — applicability not confirmed",
    }


def hiua_digest_report_copy(*, active: bool, count: int) -> Dict[str, Optional[str]]:
    """Digest / report appendix framing (same tenant scope as caller)."""
    if not active or count <= 0:
        return {
            "digest_line": None,
            "report_framing_notice": None,
        }
    return {
        "digest_line": (
            f"{count} high-impact item(s) are open while applicability is still being confirmed — "
            "treat as operational priority until confirmed."
        ),
        "report_framing_notice": (
            "Some high-impact compliance items appear in an open state while obligation applicability is still "
            "marked unknown. These are not counted as confirmed policy high-risk gaps until applicability is resolved."
        ),
    }


async def _cursor_to_list(cursor: Any, cap: int) -> List[Dict[str, Any]]:
    if cursor is None:
        return []
    fn = getattr(cursor, "to_list", None)
    if callable(fn):
        return await fn(cap)
    out: List[Dict[str, Any]] = []
    async for doc in cursor:
        out.append(doc)
        if len(out) >= cap:
            break
    return out


async def hiua_tenant_operational_summary(
    db: Any,
    client_id: str,
    *,
    property_ids: Optional[Set[str]] = None,
    max_gaps_scan: int = _MAX_GAPS_SCAN_DEFAULT,
    max_detail: int = _MAX_DETAIL_DEFAULT,
) -> Dict[str, Any]:
    """
    Tenant-scoped, bounded scan of open compliance gaps. Read-time only; no writes.
    """
    prop_filter = set(property_ids) if property_ids else None
    projection = {
        "_id": 0,
        "gap_key": 1,
        "gap_kind": 1,
        "status": 1,
        "property_id": 1,
        "requirement_id": 1,
        "requirement_code": 1,
        "requirement_code_normalized": 1,
        "applicability_state": 1,
        "is_mandatory": 1,
        "policy_criticality": 1,
        "evidence_authority": 1,
        "authority_snapshot": 1,
        "critical_mandatory_breach": 1,
        "high_risk_gap": 1,
        "days_to_expiry": 1,
    }
    cur = db.compliance_gaps.find({"client_id": client_id, "status": "open"}, projection).limit(max(1, max_gaps_scan))
    rows = await _cursor_to_list(cur, max(1, max_gaps_scan))

    hits: List[Dict[str, Any]] = []
    count = 0
    for g in rows:
        if prop_filter is not None:
            pid = str(g.get("property_id") or "").strip()
            if pid and pid not in prop_filter:
                continue
        if not derive_hiua_signal_for_open_gap(g):
            continue
        count += 1
        if len(hits) < max(0, max_detail):
            hits.append(
                {
                    "gap_key": g.get("gap_key"),
                    "gap_kind": g.get("gap_kind"),
                    "property_id": g.get("property_id"),
                    "requirement_id": g.get("requirement_id"),
                    "requirement_code": g.get("requirement_code"),
                    "applicability_state": g.get("applicability_state"),
                    "high_risk_gap": bool(g.get("high_risk_gap")),
                    "critical_mandatory_breach": bool(g.get("critical_mandatory_breach")),
                    "hiua": True,
                }
            )

    reason = PolicyReasonCode.HIGH_IMPACT_UNRESOLVED_APPLICABILITY.value
    active = count > 0
    cc = hiua_command_centre_copy(active=active, count=count)
    dr = hiua_digest_report_copy(active=active, count=count)
    return {
        "hiua_active": active,
        "hiua_open_gap_count": count,
        "hiua_reason_codes": [reason] if active else [],
        "hiua_gap_details": hits,
        "hiua_command_centre_message": cc.get("message"),
        "hiua_command_centre_tooltip": cc.get("tooltip"),
        "hiua_command_centre_filter_label": cc.get("filter_label"),
        "hiua_digest_line": dr.get("digest_line"),
        "hiua_report_framing_notice": dr.get("report_framing_notice"),
    }
