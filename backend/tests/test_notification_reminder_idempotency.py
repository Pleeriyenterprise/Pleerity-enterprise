"""L-008: daily compliance reminder idempotency scope fingerprint."""

from __future__ import annotations

from services.notification_send_idempotency import daily_compliance_reminder_scope_fingerprint


def test_fingerprint_stable_for_same_refs_order_independent():
    a = [
        {"requirement_id": "r2", "due_date": "2026-06-01", "property_id": "p1"},
        {"requirement_id": "r1", "due_date": "2026-05-01", "property_id": "p1"},
    ]
    b = list(reversed(a))
    assert daily_compliance_reminder_scope_fingerprint(reminder_refs=a) == daily_compliance_reminder_scope_fingerprint(
        reminder_refs=b
    )


def test_fingerprint_changes_when_scope_changes():
    x = daily_compliance_reminder_scope_fingerprint(
        reminder_refs=[{"requirement_id": "r1", "due_date": "2026-05-01", "property_id": "p1"}]
    )
    y = daily_compliance_reminder_scope_fingerprint(
        reminder_refs=[{"requirement_id": "r2", "due_date": "2026-05-01", "property_id": "p1"}]
    )
    assert x != y


def test_norefs_placeholder():
    assert daily_compliance_reminder_scope_fingerprint(reminder_refs=None) == "NOREFS"
    assert daily_compliance_reminder_scope_fingerprint(reminder_refs=[]) == "NOREFS"
