"""Sync unit tests for onboarding email governance helpers."""
from datetime import datetime, timezone

from services.onboarding_email_governance import milestone_set_payload


def test_milestone_set_payload_single_key():
    dt = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    d = milestone_set_payload("password_set_at", dt)
    assert len(d) == 1
    assert d["onboarding_milestones.password_set_at"] == dt.isoformat()
