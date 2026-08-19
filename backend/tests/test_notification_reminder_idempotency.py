"""L-008: daily compliance reminder idempotency scope fingerprint."""

from __future__ import annotations

from services.notification_send_idempotency import (
    daily_compliance_reminder_item_idempotency_key,
    daily_compliance_reminder_scope_fingerprint,
)


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


def test_item_idempotency_key_stable_and_distinct_per_requirement():
    kwargs = dict(
        client_id="c1",
        template_key="COMPLIANCE_EXPIRY_REMINDER",
        date_key="2026-08-18",
        recipient_suffix="a_at_test.com",
        property_id="p1",
        due_date="2026-06-01",
        lifecycle_window="overdue",
    )
    a = daily_compliance_reminder_item_idempotency_key(requirement_id="r1", **kwargs)
    b = daily_compliance_reminder_item_idempotency_key(requirement_id="r1", **kwargs)
    c = daily_compliance_reminder_item_idempotency_key(requirement_id="r2", **kwargs)
    assert a == b
    assert a != c
    # Display names must not be part of identity.
    assert "Scottish" not in a
    assert "registration" not in a.lower() or "COMPLIANCE" in a


def test_item_idempotency_key_distinct_for_same_requirement_two_properties():
    base = dict(
        client_id="c1",
        template_key="COMPLIANCE_EXPIRY_REMINDER",
        date_key="2026-08-18",
        recipient_suffix="a_at_test.com",
        requirement_id="r-same-code",
        due_date="2026-06-01",
        lifecycle_window="overdue",
    )
    a = daily_compliance_reminder_item_idempotency_key(property_id="p1", **base)
    b = daily_compliance_reminder_item_idempotency_key(property_id="p2", **base)
    assert a != b
