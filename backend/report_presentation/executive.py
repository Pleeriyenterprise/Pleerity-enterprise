"""Executive summary presentation blocks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from report_presentation.profiles import PresentationProfile, profile_config


def build_executive_summary_payload(
    *,
    report_class: str,
    posture_lines: Optional[List[str]] = None,
    metrics: Optional[List[Tuple[str, str]]] = None,
    interpretation: Optional[List[str]] = None,
    key_findings: Optional[List[str]] = None,
    highest_priorities: Optional[List[str]] = None,
    profile: PresentationProfile = "executive",
) -> Dict[str, Any]:
    """
    Structured executive summary content.
    Consumes upstream report data — does not calculate compliance posture.
    """
    cfg = profile_config(profile)
    return {
        "profile": profile,
        "title": "Executive summary",
        "intro": _executive_intro(report_class),
        "posture_lines": list(posture_lines or []),
        "metrics": list(metrics or []),
        "interpretation": list(interpretation or []),
        "key_findings": list(key_findings or []),
        "highest_priorities": list(highest_priorities or []),
        "lead_with_executive_summary": bool(cfg.get("lead_with_executive_summary")),
    }


def _executive_intro(report_class: str) -> str:
    key = (report_class or "").strip().lower().replace("-", "_")
    intros = {
        "compliance_summary": (
            "Current portfolio compliance posture, key exposure themes, and recommended focus areas."
        ),
        "evidence_readiness": (
            "Audit preparation posture — evidence completeness, gaps, and remediation priorities."
        ),
        "requirements": (
            "Operational obligation triage — highest-priority actions across the portfolio."
        ),
        "audit_evidence_pack": (
            "Evidential summary for external review — compliance position and evidence scope."
        ),
        "professional_audit_log": (
            "Summary of compliance-related activity during the selected period."
        ),
        "monthly_digest": (
            "Portfolio intelligence summary — trends, stability, and items warranting attention."
        ),
    }
    return intros.get(
        key,
        "Overall compliance position and recommended next steps at the report date.",
    )
