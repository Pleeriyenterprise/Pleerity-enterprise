"""Phase 1 workflow nudge guardrails — orchestration only, no authority mutations."""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, Mapping

ALLOWED_AUTOMATION_TYPES: FrozenSet[str] = frozenset({"auto_notify", "auto_prioritise", "recommend_only"})

FORBIDDEN_MUTATION_FIELDS: FrozenSet[str] = frozenset(
    {
        "price_status",
        "schedule_status",
        "status",
        "quote_approved_at",
        "quote_submitted_at",
        "contractor_id",
        "evidence_review_state",
        "compliance_state",
        "client_lifecycle_state",
        "verified_at",
        "assurance_tier",
    }
)

FORBIDDEN_AUTOMATION_VERBS: FrozenSet[str] = frozenset(
    {
        "approve",
        "assign",
        "verify",
        "certify",
        "mark_compliant",
        "confirm_visit",
        "submit_quote",
        "close_work_order",
    }
)


def assert_orchestration_allowed(automation_type: str) -> None:
    if automation_type not in ALLOWED_AUTOMATION_TYPES:
        raise ValueError(f"Automation type not allowed in Phase 1: {automation_type}")


def assert_no_authority_mutation(payload: Mapping[str, Any]) -> None:
    for key in payload:
        if key in FORBIDDEN_MUTATION_FIELDS:
            raise ValueError(f"Authority mutation field forbidden in nudge automation: {key}")


def assert_nudge_action_safe(*, automation_type: str, payload: Mapping[str, Any] | None = None) -> None:
    assert_orchestration_allowed(automation_type)
    if payload:
        assert_no_authority_mutation(payload)
