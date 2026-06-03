"""
SCORING_SEMANTICS_V1 — canonical product contract for compliance headline scores.

This module is the **authoritative reference** for:
- Allowed ``score_status`` values on client-visible surfaces
- Meaning of ``score_authority`` strings emitted by APIs
- Portfolio aggregation semantics (persisted property scores only for headline numerics)
- Stale-score policy (wall-clock age of ``compliance_last_calculated_at``)
- Safe export/report labelling (no silent healthy defaults)

**Not in scope for this version:** confidence scoring dimensions, remediation DTOs.

Downstream code MUST NOT invent alternate meanings for the same JSON keys; version bumps
require a new module (e.g. ``scoring_semantics_v2``) or an explicit ``scoring_semantics_version`` field.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from utils.risk_bands import score_to_risk_level

# --- Contract version (increment only on breaking semantic change) ---
SCORING_SEMANTICS_VERSION = "v1"

# --- Canonical score_status (client-visible union) ---
SCORE_STATUS_OK = "ok"
SCORE_STATUS_PARTIAL = "partial"
SCORE_STATUS_CALCULATING = "calculating"
SCORE_STATUS_RECONCILIATION_REQUIRED = "reconciliation_required"
SCORE_STATUS_UNAVAILABLE = "unavailable"
SCORE_STATUS_STALE = "stale"
SCORE_STATUS_UNKNOWN = "unknown"

SCORE_STATUS_ALL: Tuple[str, ...] = (
    SCORE_STATUS_OK,
    SCORE_STATUS_PARTIAL,
    SCORE_STATUS_CALCULATING,
    SCORE_STATUS_RECONCILIATION_REQUIRED,
    SCORE_STATUS_UNAVAILABLE,
    SCORE_STATUS_STALE,
    SCORE_STATUS_UNKNOWN,
)

# --- score_authority (headline / lens) ---
SCORE_AUTHORITY_PERSISTED_PORTFOLIO_AGGREGATE = "persisted_portfolio_aggregate"
SCORE_AUTHORITY_PERSISTED_PROPERTY = "persisted_property_score"
SCORE_AUTHORITY_PERSISTED_HEADLINE = "persisted_headline"
SCORE_AUTHORITY_OPERATIONAL_PREVIEW = "operational_preview_only"
SCORE_AUTHORITY_NON_AUTHORITATIVE_MATRIX = "non_authoritative_requirement_matrix"
SCORE_AUTHORITY_NON_AUTHORITATIVE_LEGACY_MATRIX = "non_authoritative_legacy_matrix"
SCORE_AUTHORITY_UNAVAILABLE = "unavailable"

# Persisted score older than this (UTC) is ``stale`` at property level; contributes to portfolio ``stale`` when applicable.
_STALE_DAYS_DEFAULT = 90
STALE_SCORE_MAX_AGE_DAYS = int(os.environ.get("COMPLIANCE_SCORE_STALE_DAYS", str(_STALE_DAYS_DEFAULT)))


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            s = value.replace("Z", "+00:00") if value.endswith("Z") else value
            dt = datetime.fromisoformat(s)
        except (TypeError, ValueError):
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_property_score_stale(prop: Dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    """True when a persisted score exists but last calculation is older than policy."""
    if prop.get("compliance_score") is None:
        return False
    ts = parse_iso_datetime(prop.get("compliance_last_calculated_at"))
    if ts is None:
        return True
    now = now or datetime.now(timezone.utc)
    from datetime import timedelta

    return (now - ts) > timedelta(days=STALE_SCORE_MAX_AGE_DAYS)


def resolve_property_score_status(prop: Dict[str, Any], *, now: Optional[datetime] = None) -> str:
    """
    Single-property headline status for persisted authority.

    Precedence: unavailable inputs are handled at portfolio layer; here property row only.
    ``unknown`` is reserved for future explicit suppression flags — not emitted unless
    ``compliance_headline_status_override`` == ``unknown`` (integration/tests only).

    ``compliance_score_pending`` dominates an existing persisted score: the numeric headline
    is a stale snapshot until the recalc worker completes.
    """
    override = prop.get("compliance_headline_status_override")
    if override == SCORE_STATUS_UNKNOWN:
        return SCORE_STATUS_UNKNOWN
    if prop.get("compliance_score_pending"):
        return SCORE_STATUS_CALCULATING
    if prop.get("compliance_score") is not None:
        if is_property_score_stale(prop, now=now):
            return SCORE_STATUS_STALE
        return SCORE_STATUS_OK
    return SCORE_STATUS_RECONCILIATION_REQUIRED


def resolve_property_score_status_message(prop: Dict[str, Any], *, score_status: Optional[str] = None) -> Optional[str]:
    """Client-visible explanation for property headline score status."""
    st = score_status or resolve_property_score_status(prop)
    if st == SCORE_STATUS_CALCULATING:
        if prop.get("compliance_score") is not None:
            return (
                "Your latest changes are saved. The property score updates after the next background calculation."
            )
        return "Compliance score is being calculated for this property."
    if st == SCORE_STATUS_RECONCILIATION_REQUIRED:
        return "Compliance score is not yet available; reconciliation may be required."
    if st == SCORE_STATUS_STALE:
        return (
            f"Stored compliance score is older than {STALE_SCORE_MAX_AGE_DAYS} days; refresh is recommended."
        )
    return None


def refine_portfolio_score_status(
    base_status: str,
    *,
    has_missing: bool,
    any_stale_among_scored: bool,
) -> str:
    """
    Portfolio headline ``score_status`` refinement after numeric aggregate.

    ``partial`` (incomplete coverage) dominates ``stale`` so users always see under-count risk first.
    """
    if base_status in (SCORE_STATUS_UNAVAILABLE, SCORE_STATUS_RECONCILIATION_REQUIRED, SCORE_STATUS_CALCULATING):
        return base_status
    if has_missing:
        return SCORE_STATUS_PARTIAL
    if any_stale_among_scored:
        return SCORE_STATUS_STALE
    return SCORE_STATUS_OK if base_status == SCORE_STATUS_OK else base_status


def portfolio_last_calculated_at_iso(properties_with_score: List[Dict[str, Any]]) -> Optional[str]:
    """Newest ``compliance_last_calculated_at`` among properties included in the portfolio average."""
    best: Optional[datetime] = None
    for p in properties_with_score:
        dt = parse_iso_datetime(p.get("compliance_last_calculated_at"))
        if dt is None:
            continue
        if best is None or dt > best:
            best = dt
    return best.isoformat() if best else None


def aggregate_persisted_portfolio_headline(
    properties: List[Dict[str, Any]],
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Persisted-only portfolio headline: simple mean of ``compliance_score`` over scored properties;
    never imputes healthy defaults for missing scores.
    """
    now = now or datetime.now(timezone.utc)
    n = len(properties)
    if n == 0:
        return {
            "portfolio_score": None,
            "portfolio_risk_level": None,
            "risk_level": None,
            "score_status": SCORE_STATUS_UNAVAILABLE,
            "score_status_message": "No properties to evaluate",
            "properties_total": 0,
            "properties_with_score": 0,
            "properties_missing_score": 0,
            "portfolio_last_calculated_at": None,
            "score_coverage": {
                "properties_total": 0,
                "properties_with_score": 0,
                "properties_missing_score": 0,
                "properties_with_stale_persisted_score": 0,
            },
        }
    with_score = [p for p in properties if p.get("compliance_score") is not None]
    missing = n - len(with_score)
    stale_among = [p for p in with_score if is_property_score_stale(p, now=now)]
    stale_count = len(stale_among)
    any_stale = stale_count > 0
    if not with_score:
        any_pending = any(bool(p.get("compliance_score_pending")) for p in properties)
        st = SCORE_STATUS_CALCULATING if any_pending else SCORE_STATUS_RECONCILIATION_REQUIRED
        msg = (
            "Compliance scores are being calculated for one or more properties."
            if any_pending
            else "Persisted compliance scores are not available yet for this portfolio."
        )
        return {
            "portfolio_score": None,
            "portfolio_risk_level": None,
            "risk_level": None,
            "score_status": st,
            "score_status_message": msg,
            "properties_total": n,
            "properties_with_score": 0,
            "properties_missing_score": missing,
            "portfolio_last_calculated_at": None,
            "score_coverage": {
                "properties_total": n,
                "properties_with_score": 0,
                "properties_missing_score": missing,
                "properties_with_stale_persisted_score": 0,
            },
        }
    pending_count = sum(1 for p in properties if bool(p.get("compliance_score_pending")))
    vals = [float(p["compliance_score"]) for p in with_score]
    avg = round(sum(vals) / len(vals))
    rl = score_to_risk_level(avg)
    base = SCORE_STATUS_PARTIAL if missing else SCORE_STATUS_OK
    msg = (
        f"Portfolio score averages {len(with_score)} of {n} properties with persisted scores; "
        f"{missing} propert{'ies' if missing != 1 else 'y'} still need calculation."
        if missing
        else None
    )
    if pending_count > 0:
        pending_msg = (
            f"{pending_count} propert{'ies' if pending_count != 1 else 'y'} "
            "have score updates processing after recent changes."
        )
        msg = f"{msg} {pending_msg}".strip() if msg else pending_msg
        if base == SCORE_STATUS_OK and missing == 0:
            base = SCORE_STATUS_PARTIAL
    refined = refine_portfolio_score_status(base, has_missing=missing > 0, any_stale_among_scored=any_stale and missing == 0)
    if refined == SCORE_STATUS_STALE:
        msg = (msg + " " if msg else "") + (
            f"One or more scored properties have a compliance score older than {STALE_SCORE_MAX_AGE_DAYS} days; refresh is recommended."
        )
    plast = portfolio_last_calculated_at_iso(with_score)
    return {
        "portfolio_score": avg,
        "portfolio_risk_level": rl,
        "risk_level": rl,
        "score_status": refined,
        "score_status_message": msg,
        "properties_total": n,
        "properties_with_score": len(with_score),
        "properties_missing_score": missing,
        "portfolio_last_calculated_at": plast,
        "score_coverage": {
            "properties_total": n,
            "properties_with_score": len(with_score),
            "properties_missing_score": missing,
            "properties_with_stale_persisted_score": stale_count,
        },
    }


def headline_score_display_for_export(score: Any, score_status: Optional[str]) -> str:
    """CSV/PDF-safe display: never fabricates a numeric score when status forbids it."""
    st = score_status or SCORE_STATUS_UNAVAILABLE
    if st in (SCORE_STATUS_UNAVAILABLE, SCORE_STATUS_RECONCILIATION_REQUIRED, SCORE_STATUS_UNKNOWN):
        return "N/A"
    if st == SCORE_STATUS_CALCULATING:
        return "Calculating"
    if score is None:
        return "N/A"
    return str(int(round(float(score))))


def attach_semantics_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Embed contract version on API payloads for audits and drift detection."""
    out = dict(payload)
    out["scoring_semantics_version"] = SCORING_SEMANTICS_VERSION
    return out
