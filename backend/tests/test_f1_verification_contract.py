"""F1 harness contract tests (mocked / unit-level)."""
from __future__ import annotations

from scripts.f1_snapshot import (
    FIXTURE_NOTIFICATION_CAPABLE,
    FIXTURE_NOTIFICATION_INCAPABLE,
    activation_blocked_snapshot,
    classify_f1_fixture,
    dedupe_determinism_snapshot,
    delivery_authority_snapshot,
    detect_critical_stop_f1,
    detect_primary_rc_f1,
    normalize_message_log_observational,
    notification_intent_fingerprint_semantic,
    replay_notification_comparison,
    suppression_replay_fingerprint_semantic,
    visible_impact_snapshot,
)


def test_semantic_fingerprint_ignores_created_at_only():
    row_a = {
        "message_id": "m1",
        "status": "SENT",
        "template_key": "COMPLIANCE_ALERT",
        "idempotency_key": "k1",
        "created_at": "2026-05-17T10:00:00Z",
    }
    row_b = {**row_a, "created_at": "2026-05-17T10:00:05Z"}
    assert notification_intent_fingerprint_semantic(row_a) == notification_intent_fingerprint_semantic(row_b)


def test_semantic_fingerprint_differs_on_status_change():
    row_a = {"message_id": "m1", "status": "PENDING", "template_key": "T", "idempotency_key": "k1"}
    row_b = {"message_id": "m1", "status": "SENT", "template_key": "T", "idempotency_key": "k1"}
    assert notification_intent_fingerprint_semantic(row_a) != notification_intent_fingerprint_semantic(row_b)


def test_normalize_observational_strips_timestamps_not_status():
    raw = {"status": "BLOCKED", "created_at": "x", "block_reason": "prefs"}
    out = normalize_message_log_observational(raw)
    assert "created_at" not in out
    assert out["status"] == "BLOCKED"
    assert out["block_reason"] == "prefs"


def test_replay_comparison_timestamp_only_drift():
    runs = [
        {
            "run": "R2",
            "notification_intent_fingerprint_raw_after": "raw-a",
            "notification_intent_fingerprint_semantic_after": "sem-stable",
        },
        {
            "run": "R3",
            "notification_intent_fingerprint_raw_after": "raw-b",
            "notification_intent_fingerprint_semantic_after": "sem-stable",
        },
    ]
    comp = replay_notification_comparison(runs)
    assert comp["notification_replay_stable_semantic"] is True
    assert comp["notification_replay_stable_raw"] is False
    assert comp["timestamp_only_drift"] is True


def test_suppression_semantic_ignores_run_label():
    outcomes = [
        {"run": "R2", "outcome": "duplicate_ignored", "idempotency_key": "k"},
        {"run": "R3", "outcome": "duplicate_ignored", "idempotency_key": "k"},
    ]
    assert suppression_replay_fingerprint_semantic([outcomes[0]]) == suppression_replay_fingerprint_semantic(
        [outcomes[1]]
    )


def test_dedupe_determinism_equal_outcomes():
    dedupe = dedupe_determinism_snapshot(
        [
            {"run": "R2", "outcome": "duplicate_ignored", "idempotency_key": "k"},
            {"run": "R3", "outcome": "duplicate_ignored", "idempotency_key": "k"},
        ]
    )
    assert dedupe["dedupe_deterministic"] is True


def test_fixture_incapable_without_logs():
    out = classify_f1_fixture(
        client_id="c",
        property_id="p",
        message_log_count=0,
        idempotency_key_count=0,
        template_probe_available=False,
    )
    assert out["fixture_classification"] == FIXTURE_NOTIFICATION_INCAPABLE
    assert out["vacuous_proof_prevented"] is True


def test_fixture_capable_with_idempotency_history():
    out = classify_f1_fixture(
        client_id="c",
        property_id="p",
        message_log_count=5,
        idempotency_key_count=2,
        template_probe_available=True,
    )
    assert out["fixture_classification"] == FIXTURE_NOTIFICATION_CAPABLE
    assert out["proof_eligible"] is True


def test_delivery_authority_snapshot_blocked_is_precedence_pass():
    snap = delivery_authority_snapshot(
        [{"message_id": "m1", "status": "BLOCKED", "block_reason": "BLOCKED_PREFERENCE_DISABLED"}]
    )
    assert snap["delivery_authority_precedence_pass"] is True
    assert len(snap["delivery_truth_resolution"]) == 1


def test_visible_impact_not_normalized_by_timestamp():
    logs = [
        {"template_key": "T", "status": "SENT", "created_at": "a"},
        {"template_key": "T", "status": "SENT", "created_at": "b"},
    ]
    fp_a = visible_impact_snapshot([logs[0]])["user_visible_notification_fingerprint"]
    fp_b = visible_impact_snapshot([logs[1]])["user_visible_notification_fingerprint"]
    assert fp_a == fp_b


def test_activation_blocked_snapshot_reads_inventory_policy():
    snap = activation_blocked_snapshot()
    assert snap["activation_blocked_observed"] is True


def test_critical_stop_on_cross_tenant_bleed():
    rc = detect_critical_stop_f1(checks={"cross_tenant_bleed": True}, m1_outcomes=[])
    assert rc == "F1-RC-9"


def test_critical_stop_on_m1_sent_amplification():
    rc = detect_critical_stop_f1(
        checks={},
        m1_outcomes=[{"run": "R2", "outcome": "sent"}, {"run": "R3", "outcome": "duplicate_ignored"}],
    )
    assert rc == "F1-RC-2"


def test_primary_rc_order_delivery_authority_first():
    rc = detect_primary_rc_f1(
        {
            "delivery_authority_precedence_pass": False,
            "notification_replay_stable_semantic": False,
        }
    )
    assert rc == "F1-RC-14"
