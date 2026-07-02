"""Reader-aware presentation profiles."""

from __future__ import annotations

from typing import Any, Dict

from report_presentation.constants import (
    DEFAULT_PROFILE_BY_REPORT_CLASS,
    PROFILE_EVIDENTIAL,
    PROFILE_EXECUTIVE,
    PROFILE_OPERATIONAL,
    PresentationProfile,
)


_PROFILE_CONFIG: Dict[str, Dict[str, Any]] = {
    PROFILE_EXECUTIVE: {
        "label": "Executive",
        "audience": "Landlords, portfolio owners, investors, senior management",
        "max_timeline_rows": 25,
        "include_technical_appendix": False,
        "timestamp_precision": "minute",
        "lead_with_executive_summary": True,
        "action_detail": "summary",
    },
    PROFILE_OPERATIONAL: {
        "label": "Operational",
        "audience": "Property managers, compliance teams, letting agents",
        "max_timeline_rows": 40,
        "include_technical_appendix": True,
        "timestamp_precision": "minute",
        "lead_with_executive_summary": True,
        "action_detail": "full",
    },
    PROFILE_EVIDENTIAL: {
        "label": "Evidential",
        "audience": "Local authorities, solicitors, tribunals, insurers, mortgage lenders",
        "max_timeline_rows": 60,
        "include_technical_appendix": True,
        "timestamp_precision": "minute",
        "lead_with_executive_summary": True,
        "action_detail": "full",
    },
}


def resolve_profile(
    report_class: str,
    *,
    override: PresentationProfile | None = None,
) -> PresentationProfile:
    if override and override in _PROFILE_CONFIG:
        return override
    key = (report_class or "").strip().lower().replace("-", "_")
    return DEFAULT_PROFILE_BY_REPORT_CLASS.get(key, PROFILE_OPERATIONAL)


def profile_config(profile: PresentationProfile) -> Dict[str, Any]:
    return dict(_PROFILE_CONFIG.get(profile, _PROFILE_CONFIG[PROFILE_OPERATIONAL]))
