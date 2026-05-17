"""
F1 harness: notification replay, delivery authority, acknowledgement semantics,
visible impact, lineage boundedness — verification/governance only.

Normalization applies ONLY to observational replay noise (timestamps, run labels).
Never normalize: delivery authority, visible user impact, lineage, acknowledgement
certainty, suppression state, or replay amplification signals.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scripts.c2_snapshot import fp32, select_control_entity  # noqa: F401

__all__ = [
    "FIXTURE_NOTIFICATION_CAPABLE",
    "FIXTURE_NOTIFICATION_PARTIAL",
    "FIXTURE_NOTIFICATION_INCAPABLE",
    "OBSERVATIONAL_MESSAGE_LOG_OMIT_KEYS",
    "DELIVERY_AUTHORITY_RANK",
    "ACKNOWLEDGEMENT_AMBIGUITY_CLASSES",
    "F1_RC_STOP_IMMEDIATE",
    "normalize_message_log_observational",
    "notification_intent_fingerprint_semantic",
    "notification_intent_fingerprint_raw",
    "replay_notification_comparison",
    "suppression_replay_fingerprint_semantic",
    "classify_f1_fixture",
    "resolve_f1_fixture",
    "message_log_semantic_row",
    "delivery_authority_snapshot",
    "acknowledgement_semantics_snapshot",
    "visible_impact_snapshot",
    "lineage_boundedness_snapshot",
    "dedupe_determinism_snapshot",
    "delivery_truth_matrix_rows",
    "notification_explainability_snapshot",
    "temporal_ordering_snapshot",
    "audit_notification_noise_snapshot",
    "notification_branch_classification",
    "detect_primary_rc_f1",
    "detect_critical_stop_f1",
    "unrelated_message_logs_fingerprints",
    "load_notification_governance_inventory",
    "activation_blocked_snapshot",
]

FIXTURE_NOTIFICATION_CAPABLE = "notification-replay-capable"
FIXTURE_NOTIFICATION_PARTIAL = "notification-partially-capable"
FIXTURE_NOTIFICATION_INCAPABLE = "notification-incapable"

# Observational-only — never strip from semantic / authority / ack / suppression paths.
OBSERVATIONAL_MESSAGE_LOG_OMIT_KEYS: Tuple[str, ...] = (
    "created_at",
    "updated_at",
    "sent_at",
    "delivered_at",
    "provider_accepted_at",
    "observed_at",
    "acknowledged_at",
    "next_run_at",
    "last_attempt_at",
)

DELIVERY_AUTHORITY_RANK: Tuple[str, ...] = (
    "user_visible_authority",
    "observed_authority",
    "platform_authority",
    "provider_authority",
    "operational_observability_authority",
)

ACKNOWLEDGEMENT_AMBIGUITY_CLASSES: Tuple[str, ...] = (
    "observed_not_acknowledged",
    "acknowledged_without_confirmed_human",
    "partial_acknowledgement",
    "inferred_acknowledgement",
    "delayed_acknowledgement",
    "stale_acknowledgement",
)

# Critical operational stop — preserve artifacts, classify RC, do not remediate.
F1_RC_STOP_IMMEDIATE: Tuple[str, ...] = (
    "F1-RC-2",
    "F1-RC-3",
    "F1-RC-5",
    "F1-RC-9",
    "F1-RC-14",
    "F1-RC-15",
    "F1-RC-16",
    "F1-RC-17",
)

_STATUS_TO_GOVERNED_STATE = {
    "PENDING": "queued",
    "QUEUED": "queued",
    "SENT": "provider_accepted",
    "DELIVERED": "delivered",
    "FAILED": "attempted",
    "BLOCKED": "blocked",
    "SUPPRESSED": "suppressed",
    "DEFERRED_THROTTLED": "queued",
    "DUPLICATE_IGNORED": "replay-collapsed",
}


def normalize_message_log_observational(row: Dict[str, Any]) -> Dict[str, Any]:
    """Strip timestamp churn only — not semantic delivery fields."""
    if not row:
        return {}
    out = copy.deepcopy(row)
    for key in OBSERVATIONAL_MESSAGE_LOG_OMIT_KEYS:
        out.pop(key, None)
    meta = out.get("metadata")
    if isinstance(meta, dict):
        meta_copy = copy.deepcopy(meta)
        for key in OBSERVATIONAL_MESSAGE_LOG_OMIT_KEYS:
            meta_copy.pop(key, None)
        out["metadata"] = meta_copy
    return out


def message_log_semantic_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Semantic notification intent — never omit status/outcome/suppression/lineage keys."""
    base = normalize_message_log_observational(row)
    return {
        "message_id": base.get("message_id"),
        "client_id": base.get("client_id"),
        "template_key": base.get("template_key"),
        "channel": base.get("channel"),
        "status": base.get("status"),
        "idempotency_key": base.get("idempotency_key"),
        "recipient": base.get("recipient"),
        "attempt_count": base.get("attempt_count"),
        "error_message": base.get("error_message"),
        "block_reason": base.get("block_reason"),
        "metadata": base.get("metadata"),
    }


def notification_intent_fingerprint_semantic(row: Optional[Dict[str, Any]]) -> str:
    return fp32(message_log_semantic_row(row or {}))


def notification_intent_fingerprint_raw(row: Optional[Dict[str, Any]]) -> str:
    if not row:
        return fp32({})
    slim = {
        k: v
        for k, v in row.items()
        if k not in ("_id",)
    }
    return fp32(slim)


def suppression_replay_fingerprint_semantic(outcomes: List[Dict[str, Any]]) -> str:
    semantic = [
        {k: v for k, v in o.items() if k not in ("run", "dry_run", "captured_at_utc")}
        for o in outcomes
    ]
    return fp32({"outcomes": semantic})


def replay_notification_comparison(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    raw_fps = {str(r["run"]): r.get("notification_intent_fingerprint_raw_after") for r in runs}
    sem_fps = {str(r["run"]): r.get("notification_intent_fingerprint_semantic_after") for r in runs}
    raw_stable = raw_fps.get("R2") == raw_fps.get("R3") and bool(raw_fps.get("R2"))
    semantic_stable = sem_fps.get("R2") == sem_fps.get("R3")
    return {
        "raw_fingerprint": {"R2": raw_fps.get("R2"), "R3": raw_fps.get("R3"), "replay_stable": raw_stable},
        "semantic_fingerprint": {
            "R2": sem_fps.get("R2"),
            "R3": sem_fps.get("R3"),
            "replay_stable": semantic_stable,
        },
        "notification_replay_stable_raw": raw_stable,
        "notification_replay_stable_semantic": semantic_stable,
        "timestamp_only_drift": (not raw_stable) and semantic_stable,
        "replay_branch_hint": "replay-collapsible" if semantic_stable else "unstable",
    }


def _governed_state_from_log(row: Dict[str, Any]) -> str:
    status = str(row.get("status") or "").upper()
    if row.get("block_reason"):
        return "blocked"
    return _STATUS_TO_GOVERNED_STATE.get(status, status.lower() or "unknown")


def _implied_user_state(governed_state: str) -> str:
    if governed_state in ("delivered", "observed"):
        return "may_have_received"
    if governed_state in ("provider_accepted", "attempted"):
        return "delivery_uncertain"
    if governed_state in ("blocked", "suppressed", "replay-collapsed"):
        return "not_sent_or_suppressed"
    if governed_state in ("queued", "intended_to_send"):
        return "not_delivered"
    return "unknown"


def delivery_truth_matrix_rows(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for log in logs[:40]:
        governed = _governed_state_from_log(log)
        implied = _implied_user_state(governed)
        status = str(log.get("status") or "").upper()
        false_delivery = status in ("SENT", "DELIVERED") and governed not in ("delivered", "observed")
        rows.append(
            {
                "surface": "message_logs",
                "message_id": log.get("message_id"),
                "template_key": log.get("template_key"),
                "recorded_state": status,
                "governed_state": governed,
                "implied_user_state": implied,
                "truthful": not false_delivery,
            }
        )
    return rows


def _authority_source_for_log(row: Dict[str, Any]) -> str:
    status = str(row.get("status") or "").upper()
    meta = row.get("metadata") or {}
    if meta.get("user_ack") or meta.get("read_receipt"):
        return "user_visible_authority"
    if row.get("observed_at") or meta.get("observed_delivery"):
        return "observed_authority"
    if status in ("SENT", "DELIVERED", "FAILED", "PENDING", "BLOCKED", "DEFERRED_THROTTLED"):
        return "platform_authority"
    if meta.get("provider_message_id"):
        return "provider_authority"
    return "operational_observability_authority"


def delivery_authority_snapshot(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    resolutions: List[Dict[str, Any]] = []
    violations: List[Dict[str, Any]] = []
    for log in logs[:40]:
        sources = []
        for probe in (
            _authority_source_for_log(log),
            "provider_authority" if (log.get("metadata") or {}).get("provider_message_id") else None,
            "platform_authority",
        ):
            if probe and probe not in sources:
                sources.append(probe)
        winning = sources[0] if sources else "operational_observability_authority"
        governed = _governed_state_from_log(log)
        implied = _implied_user_state(governed)
        low_wins = winning == "operational_observability_authority" and implied == "may_have_received"
        precedence_pass = not low_wins
        if not precedence_pass:
            violations.append({"message_id": log.get("message_id"), "winning_source": winning, "implied": implied})
        resolutions.append(
            {
                "surface": "message_logs",
                "message_id": log.get("message_id"),
                "winning_source": winning,
                "delivery_authority_precedence": sources,
                "overridden_delivery_authorities": sources[1:] if len(sources) > 1 else [],
                "governed_state": governed,
                "precedence_pass": precedence_pass,
            }
        )
    return {
        "delivery_truth_resolution": resolutions,
        "delivery_authority_precedence_violations": violations,
        "delivery_authority_precedence_pass": len(violations) == 0,
    }


def acknowledgement_semantics_snapshot(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    resolutions: List[Dict[str, Any]] = []
    for log in logs[:40]:
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
        resolutions.append(
            {
                "message_id": log.get("message_id"),
                "acknowledgement_class": ack_class,
                "acknowledgement_confidence": confidence,
                "acknowledgement_ambiguity_reason": reason,
                "sources": {"status": status, "observed": bool(observed), "ack_at": bool(ack_at)},
            }
        )
    fps = [fp32(r) for r in resolutions]
    replay_equal = len(fps) <= 1 or len(set(fps)) == 1
    return {
        "acknowledgement_state_resolution": resolutions,
        "acknowledgement_replay_equal": replay_equal,
        "acknowledgement_fingerprint": fp32(resolutions) if resolutions else "",
    }


def visible_impact_snapshot(
    logs: List[Dict[str, Any]],
    *,
    runs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """User-visible fingerprint — never normalized for timestamp churn."""
    visible_rows = []
    for log in logs[:50]:
        visible_rows.append(
            {
                "template_key": log.get("template_key"),
                "channel": log.get("channel"),
                "status": log.get("status"),
                "block_reason": log.get("block_reason"),
                "recipient": log.get("recipient"),
                "idempotency_key": log.get("idempotency_key"),
            }
        )
    fingerprint = fp32(visible_rows)
    curve: List[Dict[str, Any]] = []
    if runs:
        for r in runs:
            curve.append(
                {
                    "run": r.get("run"),
                    "visible_count": r.get("visible_message_log_count"),
                    "user_visible_notification_fingerprint": r.get("user_visible_notification_fingerprint"),
                }
            )
    r2 = next((c for c in curve if c.get("run") == "R2"), {})
    r3 = next((c for c in curve if c.get("run") == "R3"), {})
    stable = (
        r2.get("user_visible_notification_fingerprint") == r3.get("user_visible_notification_fingerprint")
        if r2 and r3
        else None
    )
    return {
        "user_visible_notification_fingerprint": fingerprint,
        "visible_notification_delta": len(visible_rows),
        "visible_replay_growth_curve": curve,
        "replay_visible_impact_stable": stable,
    }


def lineage_boundedness_snapshot(
    logs: List[Dict[str, Any]],
    *,
    runs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    depths: List[int] = []
    for log in logs[:50]:
        meta = log.get("metadata") or {}
        chain = 0
        if log.get("idempotency_key"):
            chain += 1
        if meta.get("correlation_id"):
            chain += 1
        if meta.get("event_type"):
            chain += 1
        if log.get("attempt_count"):
            chain += int(log.get("attempt_count") or 1) - 1
        depths.append(chain)
    max_depth = max(depths) if depths else 0
    growth_curve: List[Dict[str, Any]] = []
    if runs:
        for r in runs:
            growth_curve.append(
                {
                    "run": r.get("run"),
                    "message_log_count": r.get("message_log_count"),
                    "lineage_sample_depth": r.get("lineage_sample_depth"),
                }
            )
    r1_depth = next((g.get("lineage_sample_depth") for g in growth_curve if g.get("run") == "R1"), max_depth)
    r2_depth = next((g.get("lineage_sample_depth") for g in growth_curve if g.get("run") == "R2"), None)
    r3_depth = next((g.get("lineage_sample_depth") for g in growth_curve if g.get("run") == "R3"), None)
    growth_pass = (
        r2_depth is not None
        and r3_depth is not None
        and r2_depth == r3_depth
        and (r1_depth is None or r2_depth <= r1_depth + 1)
    )
    return {
        "notification_lineage_depth": max_depth,
        "lineage_growth_curve": growth_curve,
        "lineage_growth_pass": growth_pass if runs else None,
        "lineage_collapse_state": "collapsed_stable" if growth_pass else "expanded",
    }


def dedupe_determinism_snapshot(outcomes: List[Dict[str, Any]]) -> Dict[str, Any]:
    r2 = next((o for o in outcomes if o.get("run") == "R2"), {})
    r3 = next((o for o in outcomes if o.get("run") == "R3"), {})
    stable = (
        r2.get("outcome") == r3.get("outcome")
        and r2.get("idempotency_key") == r3.get("idempotency_key")
        if r2 and r3
        else None
    )
    return {
        "m1_outcomes": outcomes,
        "expected_dedupe_outcome": "duplicate_ignored",
        "dedupe_deterministic": stable,
        "dedupe_replay_equal": stable,
    }


def notification_explainability_snapshot(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    gaps: List[str] = []
    samples: List[Dict[str, Any]] = []
    for log in logs[:25]:
        status = log.get("status")
        reason = log.get("block_reason") or log.get("error_message") or (log.get("metadata") or {}).get("event_type")
        reconstructable = bool(status) and (bool(reason) or status in ("SENT", "DELIVERED", "PENDING"))
        if not reconstructable:
            gaps.append(str(log.get("message_id")))
        samples.append(
            {
                "message_id": log.get("message_id"),
                "status": status,
                "reason": reason,
                "reconstructable": reconstructable,
            }
        )
    return {
        "samples": samples,
        "explainability_reconstruction_pass": len(gaps) == 0,
        "gaps": gaps,
    }


def temporal_ordering_snapshot(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    timeline: List[Dict[str, Any]] = []
    contradictions: List[Dict[str, Any]] = []
    order_rank = {
        "queued": 1,
        "attempted": 2,
        "provider_accepted": 3,
        "delivered": 4,
        "observed": 5,
    }
    for log in logs[:25]:
        governed = _governed_state_from_log(log)
        timeline.append(
            {
                "message_id": log.get("message_id"),
                "governed_state": governed,
                "created_at": log.get("created_at"),
                "sent_at": log.get("sent_at"),
                "delivered_at": log.get("delivered_at"),
            }
        )
        if governed == "delivered" and not log.get("sent_at") and not log.get("created_at"):
            contradictions.append({"message_id": log.get("message_id"), "issue": "delivered_without_attempt_timestamp"})
    return {
        "notification_order_timeline": timeline,
        "temporal_contradictions": contradictions,
        "temporal_sane": len(contradictions) == 0,
    }


def notification_branch_classification(outcome: Dict[str, Any]) -> str:
    o = str(outcome.get("outcome") or "")
    if o == "duplicate_ignored":
        return "idempotent"
    if o == "blocked":
        br = str(outcome.get("block_reason") or "")
        if "DISPATCH" in br.upper() or "ACTIVATION" in br.upper():
            return "activation-blocked"
        return "suppression-stable"
    if o == "sent":
        return "replay-regenerative"
    return "replay-collapsible"


def audit_notification_noise_snapshot(
    before: Dict[str, int],
    after: Dict[str, int],
) -> Dict[str, Any]:
    delta = int(after.get("notification_audit_events", 0)) - int(before.get("notification_audit_events", 0))
    return {
        "notification_audit_event_delta": delta,
        "noise_pass": delta == 0,
        "before": before,
        "after": after,
    }


def classify_f1_fixture(
    *,
    client_id: str,
    property_id: str,
    message_log_count: int,
    idempotency_key_count: int,
    template_probe_available: bool,
) -> Dict[str, Any]:
    fail_fast: List[str] = []
    if message_log_count == 0:
        fail_fast.append("no_message_logs_for_pilot_client")
    if idempotency_key_count == 0:
        fail_fast.append("no_idempotency_history_for_m1_replay")
    if not template_probe_available and idempotency_key_count == 0:
        fail_fast.append("no_governed_template_probe")

    if idempotency_key_count > 0 and message_log_count > 0:
        classification = FIXTURE_NOTIFICATION_CAPABLE
        proof_eligible = True
    elif message_log_count > 0:
        classification = FIXTURE_NOTIFICATION_PARTIAL
        proof_eligible = False
        fail_fast.append("partial_history_without_stable_idempotency_key")
    else:
        classification = FIXTURE_NOTIFICATION_INCAPABLE
        proof_eligible = False

    return {
        "fixture_classification": classification,
        "proof_eligible": proof_eligible,
        "fail_fast_reasons": fail_fast,
        "vacuous_proof_prevented": classification == FIXTURE_NOTIFICATION_INCAPABLE,
        "client_id": client_id,
        "property_id": property_id,
        "message_log_count": message_log_count,
        "idempotency_key_count": idempotency_key_count,
    }


async def resolve_f1_fixture(db, *, cid: str, pid: str) -> Dict[str, Any]:
    message_log_count = await db.message_logs.count_documents({"client_id": cid})
    idempotency_key_count = await db.message_logs.count_documents(
        {"client_id": cid, "idempotency_key": {"$exists": True, "$ne": None}}
    )
    sample = await db.message_logs.find_one(
        {"client_id": cid, "idempotency_key": {"$exists": True, "$ne": None}},
        {"_id": 0, "template_key": 1, "idempotency_key": 1, "message_id": 1, "metadata": 1, "status": 1},
        sort=[("created_at", -1)],
    )
    template_probe_available = False
    if sample and sample.get("template_key"):
        tpl = await db.notification_templates.find_one(
            {"template_key": sample["template_key"], "is_active": True},
            {"_id": 0, "template_key": 1},
        )
        template_probe_available = bool(tpl)
    classification = classify_f1_fixture(
        client_id=cid,
        property_id=pid,
        message_log_count=message_log_count,
        idempotency_key_count=idempotency_key_count,
        template_probe_available=template_probe_available,
    )
    return {
        **classification,
        "m1_probe_sample": sample,
        "template_probe_available": template_probe_available,
    }


def load_notification_governance_inventory() -> Dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / "docs" / "audit" / "NOTIFICATION_GOVERNANCE_INVENTORY.json"
    if not path.is_file():
        return {"policy": {"notification_dispatch_workflow_family_globally_activated": None}}
    return json.loads(path.read_text(encoding="utf-8"))


def activation_blocked_snapshot() -> Dict[str, Any]:
    inv = load_notification_governance_inventory()
    globally_on = bool(
        (inv.get("policy") or {}).get("notification_dispatch_workflow_family_globally_activated")
    )
    return {
        "notification_dispatch_globally_activated": globally_on,
        "expected_f1_m8_class": "activation-blocked" if not globally_on else "delegated-regenerative",
        "activation_blocked_observed": not globally_on,
        "governance_source": "NOTIFICATION_GOVERNANCE_INVENTORY.json",
    }


async def unrelated_message_logs_fingerprints(db, *, cid: str) -> Dict[str, Any]:
    count = await db.message_logs.count_documents({"client_id": cid})
    recent = await db.message_logs.find(
        {"client_id": cid},
        {"_id": 0, "message_id": 1, "template_key": 1, "status": 1, "idempotency_key": 1},
    ).sort("created_at", -1).limit(25).to_list(25)
    return {
        "message_log_count": count,
        "fingerprint": fp32(recent),
    }


def detect_critical_stop_f1(
    *,
    checks: Dict[str, Any],
    m1_outcomes: List[Dict[str, Any]],
) -> Optional[str]:
    """Immediate stop conditions — preserve artifacts, classify RC, no remediation."""
    if checks.get("cross_tenant_bleed"):
        return "F1-RC-9"
    if checks.get("delivery_authority_precedence_pass") is False:
        return "F1-RC-14"
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
    if checks.get("false_delivery_implication"):
        return "F1-RC-5"
    return None


def detect_primary_rc_f1(checks: Dict[str, bool]) -> Optional[str]:
    """Suggested RC order — used only when classification is enabled."""
    mapping = [
        ("delivery_authority_precedence_pass", "F1-RC-14"),
        ("acknowledgement_replay_equal", "F1-RC-15"),
        ("replay_visible_impact_stable", "F1-RC-16"),
        ("lineage_growth_pass", "F1-RC-17"),
        ("notification_replay_stable_semantic", "F1-RC-1"),
        ("dedupe_deterministic", "F1-RC-3"),
        ("suppression_replay_equal", "F1-RC-7"),
        ("lineage_attributable", "F1-RC-4"),
        ("false_delivery_implication", "F1-RC-5"),
        ("delivery_bounded_pass", "F1-RC-6"),
        ("temporal_sane", "F1-RC-8"),
        ("unrelated_delta_zero", "F1-RC-9"),
        ("audit_noise_pass", "F1-RC-10"),
        ("replay_collapse_consistent", "F1-RC-11"),
        ("retry_bounded_pass", "F1-RC-12"),
        ("explainability_reconstruction_pass", "F1-RC-13"),
    ]
    for key, rc in mapping:
        if checks.get(key) is False:
            return rc
    return None
