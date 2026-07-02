"""Report Presentation Authority constants."""

from __future__ import annotations

AUTHORITY_VERSION = "report_presentation_v1"

# Reader-aware presentation profiles
PROFILE_EXECUTIVE = "executive"
PROFILE_OPERATIONAL = "operational"
PROFILE_EVIDENTIAL = "evidential"

PresentationProfile = str  # executive | operational | evidential

DEFAULT_PROFILE_BY_REPORT_CLASS: dict[str, str] = {
    "compliance_summary": PROFILE_EXECUTIVE,
    "requirements": PROFILE_OPERATIONAL,
    "evidence_readiness": PROFILE_OPERATIONAL,
    "audit_evidence_pack": PROFILE_EVIDENTIAL,
    "audit_trail": PROFILE_EVIDENTIAL,
    "monthly_digest": PROFILE_EXECUTIVE,
    "score_explanation": PROFILE_EXECUTIVE,
    "professional_audit_log": PROFILE_EVIDENTIAL,
    "expiry_schedule": PROFILE_OPERATIONAL,
    "compliance_pack": PROFILE_EXECUTIVE,
    "scheduled_report": PROFILE_EXECUTIVE,
}

# Actions suppressed from primary business chronology (available in technical appendix)
PRIMARY_LAYER_SUPPRESSED_ACTIONS = frozenset(
    {
        "RISK_SIGNAL_REGEN_STARTED",
        "RISK_SIGNAL_REGEN_COMPLETED",
        "RISK_SIGNAL_REGEN_FAILED",
        "COMPLIANCE_RECALC_SLA_BREACH",
        "COMPLIANCE_RECALC_SLA_RESOLVED",
        "HEARTBEAT",
        "PING",
    }
)

# Actions collapsed when repeated in sequence within a short window
COLLAPSIBLE_REGEN_PREFIXES = ("RISK_SIGNAL_REGEN_", "COMPLIANCE_RECALC_SLA_")
