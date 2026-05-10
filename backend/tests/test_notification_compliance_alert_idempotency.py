"""L-008d: COMPLIANCE_ALERT idempotency scope fingerprint (collision-safe for large batches)."""

from __future__ import annotations

from services.notification_send_idempotency import compliance_alert_property_scope_fingerprint


def test_short_batch_matches_sorted_join_legacy():
    assert compliance_alert_property_scope_fingerprint(["p2", "p1"]) == "p1_p2"
    assert compliance_alert_property_scope_fingerprint(["p1"]) == "p1"


def test_large_batch_uses_full_sha256_hex_digest():
    ids = [f"id-{i:04d}" for i in range(12)]
    joined = "_".join(sorted(ids))
    assert len(joined) > 32
    fp = compliance_alert_property_scope_fingerprint(ids)
    assert len(fp) == 64
    assert fp == compliance_alert_property_scope_fingerprint(list(reversed(ids)))


def test_large_batch_changes_when_property_set_changes():
    base = [f"id-{i:04d}" for i in range(12)]
    other = list(base)
    other[-1] = "id-9999"
    assert compliance_alert_property_scope_fingerprint(base) != compliance_alert_property_scope_fingerprint(other)
