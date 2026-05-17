"""F1a harness refinement contract tests."""
from __future__ import annotations

from scripts.f1a_snapshot import (
    acknowledgement_replay_fingerprint,
    acknowledgement_replay_pair_snapshot,
    acknowledgement_resolution_for_log,
    detect_critical_stop_f1a,
    replay_notification_comparison_f1a,
)


def test_ack_replay_pair_equal_when_same_certainty():
    log = {
        "message_id": "m1",
        "status": "DELIVERED",
        "metadata": {},
    }
    pair = acknowledgement_replay_pair_snapshot(
        log_after_r2=log,
        log_after_r3=log,
        idempotency_key="k1",
    )
    assert pair["acknowledgement_replay_equal"] is True
    assert pair["acknowledgement_certainty_escalation_on_replay"] is False


def test_ack_replay_pair_detects_escalation():
    low = {"message_id": "m1", "status": "DELIVERED", "metadata": {}}
    high = {
        "message_id": "m1",
        "status": "DELIVERED",
        "metadata": {"acknowledged_at": "2026-01-01", "human_confirmed": True},
    }
    pair = acknowledgement_replay_pair_snapshot(
        log_after_r2=low,
        log_after_r3=high,
        idempotency_key="k1",
    )
    assert pair["acknowledgement_certainty_escalation_on_replay"] is True


def test_ack_fingerprint_excludes_message_id():
    a = acknowledgement_resolution_for_log({"message_id": "a", "status": "DELIVERED", "metadata": {}})
    b = acknowledgement_resolution_for_log({"message_id": "b", "status": "DELIVERED", "metadata": {}})
    assert acknowledgement_replay_fingerprint(a) == acknowledgement_replay_fingerprint(b)


def test_replay_comparison_no_vacuous_null_pass():
    runs = [
        {"run": "R1", "sample_semantic_fingerprint": "x"},
        {"run": "R2", "sample_semantic_fingerprint": "a"},
        {"run": "R3", "sample_semantic_fingerprint": "b"},
    ]
    m1 = [
        {
            "run": "R2",
            "notification_intent_fingerprint_semantic_after": "sem-a",
            "notification_intent_fingerprint_raw_after": "raw-a",
        },
        {
            "run": "R3",
            "notification_intent_fingerprint_semantic_after": "sem-a",
            "notification_intent_fingerprint_raw_after": "raw-a",
        },
    ]
    comp = replay_notification_comparison_f1a(runs, m1)
    assert comp["notification_replay_stable_semantic"] is True
    assert comp["vacuous_semantic_comparison_prevented"] is False


def test_replay_comparison_vacuous_when_missing_m1_fields():
    runs = [{"run": "R2"}, {"run": "R3"}]
    comp = replay_notification_comparison_f1a(runs, [])
    assert comp["vacuous_semantic_comparison_prevented"] is True
    assert comp["notification_replay_stable_semantic"] is None


def test_critical_stop_f1a_rc15_only_on_replay_escalation():
    rc = detect_critical_stop_f1a(
        checks={"acknowledgement_certainty_escalation_on_replay": True},
        m1_outcomes=[],
    )
    assert rc == "F1-RC-15"


def test_critical_stop_f1a_no_rc15_from_population_ambiguity_field():
    rc = detect_critical_stop_f1a(
        checks={
            "acknowledgement_replay_equal": True,
            "acknowledgement_certainty_escalation_on_replay": False,
            "population_operational_ambiguity_present": True,
        },
        m1_outcomes=[],
    )
    assert rc is None
