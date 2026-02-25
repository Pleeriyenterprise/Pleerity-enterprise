"""
Compliance Risk Check – deterministic scoring for the standalone conversion demo.
Not legal advice. Do not reuse for real compliance scoring (see compliance_scoring).
"""
from typing import Any, List

# Demo-specific bands (do not import utils.risk_bands – different thresholds)
RISK_CHECK_BAND_LOW_MIN = 75      # 75–100 = LOW
RISK_CHECK_BAND_MODERATE_MIN = 50  # 50–74 = MODERATE
# 0–49 = HIGH

# Penalties: start at 100, subtract
GAS_VALID, GAS_UNKNOWN, GAS_EXPIRED = 0, 12, 25
EICR_VALID, EICR_UNKNOWN, EICR_EXPIRED = 0, 10, 20
HMO_NO, HMO_YES = 0, 10
TRACKING_AUTOMATED, TRACKING_SPREADSHEET, TRACKING_MANUAL, TRACKING_NONE = 0, 6, 10, 15

EXPOSURE_LABELS = {
    "HIGH": "Your current structure suggests potential vulnerability to missed renewals and documentation gaps.",
    "MODERATE": "Some gaps may require attention.",
    "LOW": "Generally organised, keep tracking renewals.",
}

DISCLAIMER = (
    "This assessment is an informational monitoring indicator based solely on your responses. "
    "It does not constitute legal advice, regulatory approval, or confirmation of compliance. "
    "Local authority requirements may vary."
)


def _normalize(val: Any) -> str:
    if val is None:
        return ""
    s = (str(val) or "").strip().lower()
    return s


def _gas_penalty(status: str) -> int:
    s = _normalize(status)
    if s in ("expired", "expired "):
        return GAS_EXPIRED
    if s in ("unknown", "not sure", "not_sure"):
        return GAS_UNKNOWN
    return GAS_VALID


def _eicr_penalty(status: str) -> int:
    s = _normalize(status)
    if s in ("expired", "expired "):
        return EICR_EXPIRED
    if s in ("unknown", "not sure", "not_sure"):
        return EICR_UNKNOWN
    return EICR_VALID


def _hmo_penalty(any_hmo: Any) -> int:
    if any_hmo is True:
        return HMO_YES
    s = _normalize(any_hmo)
    if s in ("yes", "true", "1"):
        return HMO_YES
    return HMO_NO


def _tracking_penalty(method: str) -> int:
    s = _normalize(method)
    if s in ("automated", "automated system"):
        return TRACKING_AUTOMATED
    if s in ("spreadsheet", "spreadsheet "):
        return TRACKING_SPREADSHEET
    if s in ("manual", "manual reminders"):
        return TRACKING_MANUAL
    if s in ("none", "no structured tracking", "no structured tracking "):
        return TRACKING_NONE
    return TRACKING_MANUAL  # default treat as manual


def _build_flags(
    property_count: int,
    any_hmo: Any,
    gas_status: str,
    eicr_status: str,
    tracking_method: str,
) -> List[dict]:
    """Return list of { title, description, recommended_next_step } for display."""
    flags = []
    g = _normalize(gas_status)
    e = _normalize(eicr_status)
    t = _normalize(tracking_method)

    if g in ("expired", "expired "):
        flags.append({
            "title": "Gas Safety Certificate",
            "description": "Status reported as expired. Renewals may be at risk.",
            "recommended_next_step": "Renew and upload your gas safety certificate; use expiry tracking to avoid future gaps.",
        })
    elif g in ("unknown", "not sure", "not_sure"):
        flags.append({
            "title": "Gas Safety Certificate",
            "description": "Status not confirmed. Visibility is key to compliance.",
            "recommended_next_step": "Confirm expiry date and add to a central tracking system.",
        })

    if e in ("expired", "expired "):
        flags.append({
            "title": "Electrical Installation Condition Report (EICR)",
            "description": "EICR status reported as expired.",
            "recommended_next_step": "Arrange an EICR and track the next due date.",
        })
    elif e in ("unknown", "not sure", "not_sure"):
        flags.append({
            "title": "Electrical Installation Condition Report (EICR)",
            "description": "EICR status not confirmed.",
            "recommended_next_step": "Confirm EICR date and track renewals.",
        })

    if any_hmo in (True, "yes", "true", "1") or _normalize(any_hmo) == "yes":
        flags.append({
            "title": "HMO Licensing",
            "description": "You have HMO properties. Licensing and safety requirements are typically higher.",
            "recommended_next_step": "Keep licences and certificates in one place with expiry reminders.",
        })

    if t in ("none", "no structured tracking", "no structured tracking "):
        flags.append({
            "title": "Renewal Tracking",
            "description": "No structured tracking increases the risk of missed renewals.",
            "recommended_next_step": "Use a central system for certificate dates and reminders.",
        })
    elif t in ("manual", "manual reminders"):
        flags.append({
            "title": "Manual Tracking",
            "description": "Manual reminders can be missed as portfolio or workload grows.",
            "recommended_next_step": "Consider automated expiry alerts and a single dashboard.",
        })

    if property_count > 1 and len(flags) == 0:
        flags.append({
            "title": "Portfolio Visibility",
            "description": "Multiple properties benefit from a single view of compliance status.",
            "recommended_next_step": "Centralise certificate dates and renewal reminders.",
        })

    return flags


def compute_risk_check_result(
    property_count: int,
    any_hmo: Any,
    gas_status: str,
    eicr_status: str,
    tracking_method: str,
) -> dict:
    """
    Pure function: compute score, band, exposure label, and flags.
    property_count: 1–100 (used for display; no penalty in MVP).
    Returns: score (0–100), risk_band (HIGH|MODERATE|LOW), exposure_range_label, flags, disclaimer_text.
    """
    score = 100
    score -= _gas_penalty(gas_status)
    score -= _eicr_penalty(eicr_status)
    score -= _hmo_penalty(any_hmo)
    score -= _tracking_penalty(tracking_method)
    score = max(0, min(100, score))

    if score >= RISK_CHECK_BAND_LOW_MIN:
        risk_band = "LOW"
    elif score >= RISK_CHECK_BAND_MODERATE_MIN:
        risk_band = "MODERATE"
    else:
        risk_band = "HIGH"

    exposure_range_label = EXPOSURE_LABELS.get(risk_band, EXPOSURE_LABELS["HIGH"])
    flags = _build_flags(property_count, any_hmo, gas_status, eicr_status, tracking_method)

    return {
        "score": score,
        "risk_band": risk_band,
        "exposure_range_label": exposure_range_label,
        "flags": flags,
        "disclaimer_text": DISCLAIMER,
    }


def simulated_property_breakdown(
    property_count: int,
    score: int,
    gas_status: str,
    eicr_status: str,
    tracking_method: str,
) -> List[dict]:
    """
    Return a list of simulated per-property rows for display when property_count > 1.
    Each item: { "label": "Property 1", "score": 58, "gas": "...", "electrical": "...", "tracking": "..." }.
    """
    if property_count <= 1:
        return [{"label": "Property 1", "score": score, "gas": gas_status or "—", "electrical": eicr_status or "—", "tracking": tracking_method or "—"}]

    # Distribute score around the portfolio score with small variance (display only)
    import random
    random.seed(score + property_count)
    base = score
    out = []
    for i in range(property_count):
        delta = random.randint(-8, 8)
        p_score = max(0, min(100, base + delta))
        out.append({
            "label": f"Property {i + 1}",
            "score": p_score,
            "gas": gas_status or "—",
            "electrical": eicr_status or "—",
            "tracking": tracking_method or "—",
        })
    return out
