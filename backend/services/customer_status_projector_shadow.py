"""Shadow comparison — legacy truth_presentation vs customer_status_projector_v2."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services import customer_status_vocabulary as vocab
from services.customer_status_projector_config import get_customer_status_projector_mode

logger = logging.getLogger(__name__)


def _contains_retired_phrase(text: str) -> Optional[str]:
    lower = str(text or "").lower()
    for phrase in vocab.RETIRED_REVIEW_PHRASES:
        if phrase.lower() in lower:
            return phrase
    return None


def _inverse_stage_key(stage: str) -> str:
    st = str(stage or "").strip()
    return vocab.PRESENTATION_STAGE_TO_STATUS_KEY.get(st, "")


def _is_expected_normalization(legacy_label: str, projector_label: str) -> bool:
    leg = legacy_label.lower().strip()
    proj = projector_label.lower().strip()
    if leg == proj:
        return True
    if "escalat" in leg and "escalation required" in proj:
        return True
    if "platform verification" in leg and ("under review" in proj or "recorded on file" in proj):
        return True
    if "follow-up evidence" in leg and "follow-up required" in proj:
        return True
    if "additional action still" in leg and "additional action required" in proj:
        return True
    if leg in ("assessment recorded", "evidence recorded", "declaration recorded") and "recorded on file" in proj:
        return True
    if leg == "valid" and proj == "verified":
        return True
    return False


def compare_legacy_vs_projector(
    requirement: Dict[str, Any],
    legacy: Dict[str, Any],
    projection: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Return divergence payload when legacy and projector differ materially."""
    legacy_label = str(legacy.get("truth_presentation_label") or "").strip()
    legacy_subline = str(legacy.get("truth_presentation_subline") or "").strip()
    legacy_stage = str(legacy.get("truth_presentation_stage") or "").strip()

    proj_label = str(projection.get("customer_status_label") or "").strip()
    proj_subline = str(projection.get("customer_status_subline") or "").strip()
    proj_key = str(projection.get("customer_status_key") or "").strip()
    proj_class = str(projection.get("customer_status_class") or "").strip()

    if not legacy_label and not proj_label:
        return None

    dimensions: List[str] = []
    divergence_type = "label_mismatch"

    if legacy_label.lower() != proj_label.lower():
        dimensions.append("label_mismatch")
    if legacy_subline.lower() != proj_subline.lower() and (legacy_subline or proj_subline):
        dimensions.append("subline_mismatch")

    legacy_key = _inverse_stage_key(legacy_stage)
    if legacy_key and proj_key and legacy_key != proj_key:
        dimensions.append("key_mismatch")

    retired = _contains_retired_phrase(legacy_label) or _contains_retired_phrase(legacy_subline)
    if retired and not _contains_retired_phrase(proj_label):
        dimensions.append("retired_phrase_legacy")
        divergence_type = "retired_phrase_legacy"

    if retired and "review" in retired.lower() and proj_class == "A" and proj_key not in (
        vocab.UNDER_REVIEW,
        vocab.ESCALATION_REQUIRED,
    ):
        dimensions.append("review_without_gate")
        divergence_type = "review_without_gate"

    if "escalat" in legacy_label.lower() and proj_key == vocab.ESCALATION_REQUIRED:
        dimensions.append("escalation_normalization")
        if _is_expected_normalization(legacy_label, proj_label):
            divergence_type = "expected_normalization"

    if not dimensions:
        return None

    if _is_expected_normalization(legacy_label, proj_label) and divergence_type == "label_mismatch":
        divergence_type = "expected_normalization"

    return {
        "legacy_label": legacy_label,
        "legacy_subline": legacy_subline,
        "legacy_stage": legacy_stage,
        "projector_label": proj_label,
        "projector_subline": proj_subline,
        "projector_key": proj_key,
        "divergence_type": divergence_type,
        "divergence_dimensions": dimensions,
        "compared_at": datetime.now(timezone.utc).isoformat(),
        "flag_mode": get_customer_status_projector_mode(),
    }


def log_projector_divergence(
    requirement: Dict[str, Any],
    legacy: Dict[str, Any],
    projection: Dict[str, Any],
    comparison: Dict[str, Any],
) -> None:
    """Structured log — ids and status keys only; no PII."""
    if comparison.get("divergence_type") == "expected_normalization":
        logger.info(
            "customer_status_projector_divergence",
            extra={
                "event": "customer_status_projector_divergence",
                "divergence_type": comparison.get("divergence_type"),
                "requirement_id": str(requirement.get("requirement_id") or ""),
                "client_id": str(requirement.get("client_id") or ""),
                "property_id": str(requirement.get("property_id") or ""),
                "requirement_code": str(
                    requirement.get("requirement_code") or requirement.get("requirement_type") or ""
                ),
                "legacy_label": comparison.get("legacy_label"),
                "projector_label": comparison.get("projector_label"),
                "flag_mode": comparison.get("flag_mode"),
            },
        )
        return

    logger.warning(
        "customer_status_projector_divergence",
        extra={
            "event": "customer_status_projector_divergence",
            "divergence_type": comparison.get("divergence_type"),
            "divergence_dimensions": comparison.get("divergence_dimensions"),
            "requirement_id": str(requirement.get("requirement_id") or ""),
            "client_id": str(requirement.get("client_id") or ""),
            "property_id": str(requirement.get("property_id") or ""),
            "requirement_code": str(
                requirement.get("requirement_code") or requirement.get("requirement_type") or ""
            ),
            "governance_family": str(requirement.get("governance_family") or ""),
            "queue_backed_review": requirement.get("queue_backed_review"),
            "legacy_label": comparison.get("legacy_label"),
            "projector_label": comparison.get("projector_label"),
            "projector_key": comparison.get("projector_key"),
            "flag_mode": comparison.get("flag_mode"),
            "vocabulary_version": projection.get("vocabulary_version"),
            "customer_status_projector_version": projection.get("customer_status_projector_version"),
        },
    )
