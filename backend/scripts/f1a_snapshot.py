"""
F1a harness refinement: replay-pair acknowledgement semantics, fingerprint alignment,
vacuous replay prevention — verification/governance only.

Parent F1 remains IN_PROGRESS. Does not modify f1_snapshot behaviour or f1_* artifacts.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scripts.c2_snapshot import fp32
from scripts.f1_snapshot import (
    FIXTURE_NOTIFICATION_CAPABLE,
    FIXTURE_NOTIFICATION_INCAPABLE,
    acknowledgement_semantics_snapshot,
    replay_notification_comparison,
)

__all__ = [
    "ACK_CONFIDENCE_RANK",
    "acknowledgement_resolution_for_log",
    "acknowledgement_replay_fingerprint",
    "acknowledgement_replay_pair_snapshot",
    "acknowledgement_population_ambiguity_snapshot",
    "replay_notification_comparison_f1a",
    "detect_critical_stop_f1a",
    "detect_primary_rc_f1a",
    "delivery_truth_replay_probe_row",
]

# Higher rank = stronger asserted certainty (replay escalation = R3 rank > R2 rank).
ACK_CONFIDENCE_RANK: Dict[str, int] = {
    "ambiguous": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
}


def acknowledgement_resolution_for_log(log: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Single-row acknowledgement taxonomy — excludes message_id from replay fingerprint."""
    if not log:
        return {
            "acknowledgement_class": "observed_not_acknowledged",
            "acknowledgement_confidence": "ambiguous",
            "acknowledgement_ambiguity_reason": "missing_log_row",
            "operational_ambiguity_only": True,
        }
    meta = log.get("metadata") or {}
    status = str(log.get("status") or "").upper()
    ack_at = log.get("acknowledged_at") or meta.get("acknowledged_at")
    observed = log.get("observed_at") or meta.get("observed_delivery")
    ack_class = "observed_not_acknowledged"
    confidence = "ambiguous"
    reason = ""
    if ack_at and not meta.get("human_confirmed"):
        ack_class = "acknowledged_without_confirmed_human"
        confidence = "medium"
        reason = "system_ack_without_human_confirmation"
    elif ack_at and meta.get("human_confirmed"):
        confidence = "high"
        ack_class = "observed_not_acknowledged"
        reason = "human_confirmed_ack"
    elif observed and not ack_at:
        ack_class = "observed_not_acknowledged"
        confidence = "low"
        reason = "delivered_observed_no_ack"
    elif status == "DELIVERED" and not ack_at:
        ack_class = "inferred_acknowledgement"
        confidence = "ambiguous"
        reason = "status_delivered_without_ack_signal"
    return {
        "message_id": log.get("message_id"),
        "acknowledgement_class": ack_class,
        "acknowledgement_confidence": confidence,
        "acknowledgement_ambiguity_reason": reason,
        "operational_ambiguity_only": confidence in ("ambiguous", "low"),
        "sources": {"status": status, "observed": bool(observed), "ack_at": bool(ack_at)},
    }


def acknowledgement_replay_fingerprint(resolution: Dict[str, Any]) -> str:
    """Replay-pair fingerprint — certainty/class only; never message_id or timestamps."""
    return fp32(
        {
            "acknowledgement_class": resolution.get("acknowledgement_class"),
            "acknowledgement_confidence": resolution.get("acknowledgement_confidence"),
        }
    )


def acknowledgement_replay_pair_snapshot(
    *,
    log_after_r2: Optional[Dict[str, Any]],
    log_after_r3: Optional[Dict[str, Any]],
    idempotency_key: str,
) -> Dict[str, Any]:
    """
    Governed replay-pair question: did R2/R3 replay alter acknowledgement certainty?
    Historical population diversity is out of scope for this comparison.
    """
    res_r2 = acknowledgement_resolution_for_log(log_after_r2)
    res_r3 = acknowledgement_resolution_for_log(log_after_r3)
    fp_r2 = acknowledgement_replay_fingerprint(res_r2)
    fp_r3 = acknowledgement_replay_fingerprint(res_r3)
    rank_r2 = ACK_CONFIDENCE_RANK.get(str(res_r2.get("acknowledgement_confidence") or ""), 0)
    rank_r3 = ACK_CONFIDENCE_RANK.get(str(res_r3.get("acknowledgement_confidence") or ""), 0)
    vacuous = not log_after_r2 or not log_after_r3
    replay_equal = (fp_r2 == fp_r3) if not vacuous else None
    certainty_escalation = (not vacuous) and rank_r3 > rank_r2
    return {
        "replay_pair_question": "did_R2_R3_replay_alter_acknowledgement_certainty",
        "idempotency_key": idempotency_key,
        "acknowledgement_replay_equal": replay_equal,
        "acknowledgement_certainty_escalation_on_replay": certainty_escalation,
        "acknowledgement_fingerprint_r2": fp_r2,
        "acknowledgement_fingerprint_r3": fp_r3,
        "confidence_rank_r2": rank_r2,
        "confidence_rank_r3": rank_r3,
        "R2_resolution": res_r2,
        "R3_resolution": res_r3,
        "vacuous_replay_pair": vacuous,
        "historical_ambiguity_excluded_from_replay_rc": True,
    }


def acknowledgement_population_ambiguity_snapshot(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Operational ambiguity inventory — does NOT set replay_equal or trigger F1-RC-15."""
    pop = acknowledgement_semantics_snapshot(logs)
    by_class: Dict[str, int] = {}
    by_confidence: Dict[str, int] = {}
    for row in pop.get("acknowledgement_state_resolution") or []:
        cls = str(row.get("acknowledgement_class") or "unknown")
        conf = str(row.get("acknowledgement_confidence") or "unknown")
        by_class[cls] = by_class.get(cls, 0) + 1
        by_confidence[conf] = by_confidence.get(conf, 0) + 1
    return {
        "population_scope": "historical_message_logs_sample",
        "excluded_from_replay_rc": True,
        "acknowledgement_class_counts": by_class,
        "acknowledgement_confidence_counts": by_confidence,
        "operational_ambiguity_present": any(
            c in ("ambiguous", "low") for c in by_confidence
        ),
        "acknowledgement_state_resolution_sample": (pop.get("acknowledgement_state_resolution") or [])[:10],
    }


def replay_notification_comparison_f1a(
    runs: List[Dict[str, Any]],
    m1_outcomes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Align replay comparison fields from M1 probe outcomes; prevent null==null vacuous pass."""
    enriched: List[Dict[str, Any]] = []
    probe_by_run = {str(o.get("run")): o for o in m1_outcomes if o.get("run")}
    for r in runs:
        er = dict(r)
        label = str(r.get("run") or "")
        if label in ("R2", "R3"):
            probe = probe_by_run.get(label) or {}
            sem = probe.get("notification_intent_fingerprint_semantic_after") or r.get(
                "sample_semantic_fingerprint"
            )
            raw = probe.get("notification_intent_fingerprint_raw_after") or r.get("sample_raw_fingerprint")
            er["notification_intent_fingerprint_semantic_after"] = sem
            er["notification_intent_fingerprint_raw_after"] = raw
        enriched.append(er)

    comp = replay_notification_comparison(enriched)
    sem_r2 = comp.get("semantic_fingerprint", {}).get("R2")
    sem_r3 = comp.get("semantic_fingerprint", {}).get("R3")
    raw_r2 = comp.get("raw_fingerprint", {}).get("R2")
    raw_r3 = comp.get("raw_fingerprint", {}).get("R3")
    vacuous_semantic = not sem_r2 or not sem_r3
    vacuous_raw = not raw_r2 or not raw_r3

    if vacuous_semantic:
        semantic_stable: Optional[bool] = None
    else:
        semantic_stable = sem_r2 == sem_r3

    if vacuous_raw:
        raw_stable: Optional[bool] = None
    else:
        raw_stable = raw_r2 == raw_r3

    timestamp_only = (
        raw_stable is False and semantic_stable is True
    ) if (raw_stable is not None and semantic_stable is not None) else None

    comp["notification_replay_stable_semantic"] = semantic_stable
    comp["notification_replay_stable_raw"] = raw_stable
    comp["vacuous_semantic_comparison_prevented"] = vacuous_semantic
    comp["vacuous_raw_comparison_prevented"] = vacuous_raw
    comp["timestamp_only_drift"] = timestamp_only
    comp["replay_branch_hint"] = (
        "replay-collapsible"
        if semantic_stable is True
        else ("unstable" if semantic_stable is False else "indeterminate_vacuous")
    )
    comp["field_alignment"] = "m1_probe_outcomes_merged_into_r2_r3"
    return comp


def delivery_truth_replay_probe_row(log: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Truth check scoped to M1 replay probe row only — not historical population."""
    if not log:
        return {"truthful": None, "scoped": "m1_replay_probe", "reason": "missing_row"}
    from scripts.f1_snapshot import _governed_state_from_log, _implied_user_state

    status = str(log.get("status") or "").upper()
    governed = _governed_state_from_log(log)
    implied = _implied_user_state(governed)
    false_delivery = status in ("SENT", "DELIVERED") and governed not in ("delivered", "observed")
    return {
        "scoped": "m1_replay_probe",
        "message_id": log.get("message_id"),
        "recorded_state": status,
        "governed_state": governed,
        "implied_user_state": implied,
        "truthful": not false_delivery,
        "false_delivery_implication_on_probe": false_delivery,
    }


def detect_critical_stop_f1a(
    *,
    checks: Dict[str, Any],
    m1_outcomes: List[Dict[str, Any]],
) -> Optional[str]:
    """F1a: F1-RC-15 only on replay-pair escalation/drift — not population ambiguity."""
    if checks.get("cross_tenant_bleed"):
        return "F1-RC-9"
    if checks.get("delivery_authority_precedence_pass") is False:
        return "F1-RC-14"
    if checks.get("acknowledgement_certainty_escalation_on_replay"):
        return "F1-RC-15"
    if checks.get("acknowledgement_replay_equal") is False:
        return "F1-RC-15"
    if checks.get("replay_visible_impact_stable") is False:
        return "F1-RC-16"
    if checks.get("lineage_growth_pass") is False:
        return "F1-RC-17"
    for o in m1_outcomes:
        if o.get("run") in ("R2", "R3") and o.get("outcome") == "sent":
            return "F1-RC-2"
    if checks.get("dedupe_deterministic") is False:
        return "F1-RC-3"
    if checks.get("false_delivery_implication_on_replay_probe"):
        return "F1-RC-5"
    return None


def detect_primary_rc_f1a(checks: Dict[str, bool]) -> Optional[str]:
    mapping = [
        ("delivery_authority_precedence_pass", "F1-RC-14"),
        ("acknowledgement_certainty_escalation_on_replay", "F1-RC-15"),
        ("acknowledgement_replay_equal", "F1-RC-15"),
        ("replay_visible_impact_stable", "F1-RC-16"),
        ("lineage_growth_pass", "F1-RC-17"),
        ("notification_replay_stable_semantic", "F1-RC-1"),
        ("dedupe_deterministic", "F1-RC-3"),
        ("suppression_replay_equal", "F1-RC-7"),
        ("false_delivery_implication_on_replay_probe", "F1-RC-5"),
        ("unrelated_delta_zero", "F1-RC-9"),
    ]
    for key, rc in mapping:
        val = checks.get(key)
        if val is False:
            return rc
    return None
