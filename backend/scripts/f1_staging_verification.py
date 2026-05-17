"""
F1 staging verification: notification governance replay analysis (R1–R3).

  python -m scripts.f1_preflight_capture --client-id CID --property-id PID
  python -m scripts.f1_staging_verification --client-id CID --property-id PID

Verification/governance only — no orchestrator/provider/queue/template remediation.
Pass/fail classification deferred until programme approval.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.c2_snapshot import delta_fingerprints, unrelated_fingerprints  # noqa: E402
from scripts.f1_snapshot import (  # noqa: E402
    FIXTURE_NOTIFICATION_CAPABLE,
    FIXTURE_NOTIFICATION_INCAPABLE,
    OBSERVATIONAL_MESSAGE_LOG_OMIT_KEYS,
    activation_blocked_snapshot,
    acknowledgement_semantics_snapshot,
    audit_notification_noise_snapshot,
    dedupe_determinism_snapshot,
    delivery_authority_snapshot,
    delivery_truth_matrix_rows,
    detect_critical_stop_f1,
    lineage_boundedness_snapshot,
    notification_branch_classification,
    notification_explainability_snapshot,
    notification_intent_fingerprint_raw,
    notification_intent_fingerprint_semantic,
    replay_notification_comparison,
    resolve_f1_fixture,
    suppression_replay_fingerprint_semantic,
    temporal_ordering_snapshot,
    unrelated_message_logs_fingerprints,
    visible_impact_snapshot,
)

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CTRL_CID_DEFAULT = "04ceda9f-dd72-4b70-a6f5-809bef1b7b6a"
CTRL_PID_DEFAULT = "6d939c70-06ab-4dc8-8b36-204958d2cdb3"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="F1 staging verification (harness — classification deferred)")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--slug-suffix", default="6fd5ac4c_d35a58ae")
    p.add_argument("--verification-run", default="f1_harness_in_progress_v1")
    p.add_argument("--artifact-prefix", default="f1")
    p.add_argument("--control-client-id", default=CTRL_CID_DEFAULT)
    p.add_argument("--control-property-id", default=CTRL_PID_DEFAULT)
    p.add_argument("--skip-m1-probe", action="store_true", help="Observe-only: no orchestrator.send replay probe")
    return p.parse_args()


def _artifact_name(prefix: str, stem: str, slug: str) -> str:
    return f"{prefix}_{stem}_{slug}.json"


async def _audit_notification_counts(db, *, cid: str) -> Dict[str, int]:
    n = await db.audit_logs.count_documents(
        {
            "client_id": cid,
            "action": {
                "$in": [
                    "NOTIFICATION_THROTTLED",
                    "NOTIFICATION_BLOCKED_PREFERENCE_DISABLED",
                    "EMAIL_SKIPPED_NO_RECIPIENT",
                ]
            },
        }
    )
    return {"notification_audit_events": n}


async def _fetch_pilot_logs(db, *, cid: str, limit: int = 50) -> List[Dict[str, Any]]:
    return await db.message_logs.find(
        {"client_id": cid},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(limit)


async def _run_snapshot(db, *, cid: str, pid: str) -> Dict[str, Any]:
    logs = await _fetch_pilot_logs(db, cid=cid)
    count = await db.message_logs.count_documents({"client_id": cid})
    visible_fp = visible_impact_snapshot(logs)["user_visible_notification_fingerprint"]
    depth = lineage_boundedness_snapshot(logs)["notification_lineage_depth"]
    return {
        "message_log_count": count,
        "lineage_sample_depth": depth,
        "visible_message_log_count": len(logs),
        "user_visible_notification_fingerprint": visible_fp,
        "sample_message_id": logs[0].get("message_id") if logs else None,
        "sample_semantic_fingerprint": notification_intent_fingerprint_semantic(logs[0]) if logs else None,
        "sample_raw_fingerprint": notification_intent_fingerprint_raw(logs[0]) if logs else None,
    }


async def _f1_m1_replay_probe(
    db,
    *,
    cid: str,
    sample: Dict[str, Any],
    run_label: str,
) -> Dict[str, Any]:
    from services.notification_orchestrator import notification_orchestrator

    template_key = str(sample.get("template_key") or "")
    idempotency_key = str(sample.get("idempotency_key") or "")
    if not template_key or not idempotency_key:
        return {
            "run": run_label,
            "skipped": True,
            "reason": "missing_template_or_idempotency_key",
        }
    meta = sample.get("metadata") if isinstance(sample.get("metadata"), dict) else {}
    result = await notification_orchestrator.send(
        template_key=template_key,
        client_id=cid,
        context={"property_id": meta.get("property_id")},
        idempotency_key=idempotency_key,
        event_type="F1_VERIFICATION:M1_REPLAY",
    )
    row = await db.message_logs.find_one(
        {"idempotency_key": idempotency_key},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    return {
        "run": run_label,
        "outcome": result.outcome,
        "block_reason": result.block_reason,
        "message_id": result.message_id,
        "idempotency_key": idempotency_key,
        "template_key": template_key,
        "notification_branch_class": notification_branch_classification(
            {"outcome": result.outcome, "block_reason": result.block_reason}
        ),
        "notification_intent_fingerprint_semantic_after": notification_intent_fingerprint_semantic(row),
        "notification_intent_fingerprint_raw_after": notification_intent_fingerprint_raw(row),
    }


async def _correlation_matrix(db, *, cid: str, pid: str) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    async for log in db.message_logs.find(
        {"client_id": cid},
        {"_id": 0, "message_id": 1, "metadata": 1, "idempotency_key": 1, "template_key": 1},
    ).sort("created_at", -1).limit(30):
        meta = log.get("metadata") or {}
        corr = meta.get("correlation_id") or meta.get("transition_correlation_id")
        rows.append(
            {
                "message_id": log.get("message_id"),
                "correlation_id": corr,
                "property_id_in_metadata": meta.get("property_id"),
                "property_match": str(meta.get("property_id") or "") == pid,
                "idempotency_key": log.get("idempotency_key"),
                "template_key": log.get("template_key"),
            }
        )
    joinable = sum(1 for r in rows if r.get("correlation_id") or r.get("idempotency_key"))
    return {
        "correlation_rows": rows,
        "joinable_count": joinable,
        "lineage_attributable": joinable == len(rows) if rows else False,
    }


async def main() -> None:
    from database import database

    await database.connect()
    args = _parse_args()
    cid = args.client_id.strip()
    pid = args.property_id.strip()
    slug = args.slug_suffix
    prefix = args.artifact_prefix
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    db = database.get_db()
    run_at = datetime.now(timezone.utc).isoformat()
    ctrl_cid = args.control_client_id.strip()
    ctrl_pid = args.control_property_id.strip()

    fixture = await resolve_f1_fixture(db, cid=cid, pid=pid)
    fixture_class = fixture["fixture_classification"]
    fixture_gate_pass = fixture_class == FIXTURE_NOTIFICATION_CAPABLE

    ctrl_fp_before = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    ctrl_msg_before = await unrelated_message_logs_fingerprints(db, cid=ctrl_cid)
    audit_before = await _audit_notification_counts(db, cid=cid)

    runs: List[Dict[str, Any]] = []
    m1_outcomes: List[Dict[str, Any]] = []

    r1 = await _run_snapshot(db, cid=cid, pid=pid)
    r1["run"] = "R1"
    runs.append(r1)

    sample_probe = fixture.get("m1_probe_sample") or {}
    if fixture_gate_pass and not args.skip_m1_probe and sample_probe:
        for label in ("R2", "R3"):
            probe = await _f1_m1_replay_probe(db, cid=cid, sample=sample_probe, run_label=label)
            m1_outcomes.append(probe)
            snap = await _run_snapshot(db, cid=cid, pid=pid)
            snap["run"] = label
            snap["m1_outcome"] = probe.get("outcome")
            runs.append(snap)
    elif fixture_gate_pass:
        for label in ("R2", "R3"):
            snap = await _run_snapshot(db, cid=cid, pid=pid)
            snap["run"] = label
            snap["observe_only"] = True
            runs.append(snap)

    audit_after = await _audit_notification_counts(db, cid=cid)
    ctrl_fp_after = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    ctrl_msg_after = await unrelated_message_logs_fingerprints(db, cid=ctrl_cid)
    unrelated_delta = delta_fingerprints(ctrl_fp_before, ctrl_fp_after)
    unrelated_count = sum(
        1 for v in unrelated_delta.values() if isinstance(v, dict) and v.get("changed")
    )
    msg_delta = ctrl_msg_before.get("fingerprint") != ctrl_msg_after.get("fingerprint")

    pilot_logs = await _fetch_pilot_logs(db, cid=cid)
    replay_comp = replay_notification_comparison(runs) if len(runs) >= 2 else {}
    delivery_auth = delivery_authority_snapshot(pilot_logs)
    ack = acknowledgement_semantics_snapshot(pilot_logs)
    visible = visible_impact_snapshot(pilot_logs, runs=runs)
    lineage = lineage_boundedness_snapshot(pilot_logs, runs=runs)
    dedupe = dedupe_determinism_snapshot(m1_outcomes) if m1_outcomes else {"dedupe_deterministic": None}
    truth_rows = delivery_truth_matrix_rows(pilot_logs)
    explain = notification_explainability_snapshot(pilot_logs)
    temporal = temporal_ordering_snapshot(pilot_logs)
    correlation = await _correlation_matrix(db, cid=cid, pid=pid)
    activation = activation_blocked_snapshot()

    false_delivery = any(not r.get("truthful", True) for r in truth_rows)
    semantic_stable = replay_comp.get("notification_replay_stable_semantic")
    suppression_fp = suppression_replay_fingerprint_semantic(m1_outcomes) if m1_outcomes else ""
    suppression_equal = (
        m1_outcomes[0].get("outcome") == m1_outcomes[1].get("outcome") if len(m1_outcomes) >= 2 else None
    )

    checks: Dict[str, Any] = {
        "classification_deferred": True,
        "fixture_gate_pass": fixture_gate_pass,
        "fixture_classification": fixture_class,
        "delivery_authority_precedence_pass": delivery_auth.get("delivery_authority_precedence_pass")
        if fixture_gate_pass
        else None,
        "acknowledgement_replay_equal": ack.get("acknowledgement_replay_equal") if fixture_gate_pass else None,
        "replay_visible_impact_stable": visible.get("replay_visible_impact_stable"),
        "lineage_growth_pass": lineage.get("lineage_growth_pass"),
        "notification_replay_stable_semantic": semantic_stable,
        "notification_replay_stable_raw_observability_only": replay_comp.get("notification_replay_stable_raw"),
        "dedupe_deterministic": dedupe.get("dedupe_deterministic"),
        "suppression_replay_equal": suppression_equal,
        "lineage_attributable": correlation.get("lineage_attributable"),
        "false_delivery_implication": false_delivery if fixture_gate_pass else None,
        "delivery_bounded_pass": None,
        "temporal_sane": temporal.get("temporal_sane") if fixture_gate_pass else None,
        "unrelated_delta_zero": unrelated_count == 0 and not msg_delta if fixture_gate_pass else None,
        "cross_tenant_bleed": msg_delta or unrelated_count > 0 if fixture_gate_pass else None,
        "audit_noise_pass": audit_notification_noise_snapshot(audit_before, audit_after).get("noise_pass"),
        "explainability_reconstruction_pass": explain.get("explainability_reconstruction_pass"),
        "replay_collapse_consistent": semantic_stable,
        "retry_bounded_pass": None,
    }

    critical_stop_rc = detect_critical_stop_f1(checks=checks, m1_outcomes=m1_outcomes) if fixture_gate_pass else None

    report = {
        "captured_at_utc": run_at,
        "verification_run": args.verification_run,
        "unit": "F1",
        "unit_status": "IN_PROGRESS",
        "harness_phase": "verification_only",
        "f1_pass": None,
        "classification_deferred": True,
        "primary_rc_branch": critical_stop_rc,
        "critical_stop_triggered": bool(critical_stop_rc),
        "checks": checks,
        "fixture_classification": fixture_class,
        "replay_notification": replay_comp,
        "governed_mutations_wired": ["F1-M1", "F1-M8-observe"] if fixture_gate_pass else [],
        "governed_mutations_deferred": ["F1-M2", "F1-M3", "F1-M4", "F1-M5", "F1-M6", "F1-M7"],
        "normalization_strategy": {
            "observational_omit_keys": list(OBSERVATIONAL_MESSAGE_LOG_OMIT_KEYS),
            "never_normalize": [
                "delivery_authority",
                "visible_user_impact",
                "lineage",
                "acknowledgement_certainty",
                "suppression_state",
                "replay_amplification",
            ],
        },
        "client_id": cid,
        "property_id": pid,
        "control_client_id": ctrl_cid,
        "control_property_id": ctrl_pid,
        "artifacts": {},
    }

    def ap(stem: str) -> str:
        return f"docs/audit/{_artifact_name(prefix, stem, slug)}"

    report["artifacts"] = {
        "notification_replay": ap("notification_replay"),
        "dedupe_determinism": ap("dedupe_determinism"),
        "lineage_trace": ap("lineage_trace"),
        "correlation_matrix": ap("correlation_matrix"),
        "delivery_truth_matrix": ap("delivery_truth_matrix"),
        "delivery_authority": ap("delivery_authority"),
        "acknowledgement_semantics": ap("acknowledgement_semantics"),
        "visible_impact": ap("visible_impact"),
        "lineage_boundedness": ap("lineage_boundedness"),
        "delivery_boundedness": ap("delivery_boundedness"),
        "suppression_replay": ap("suppression_replay"),
        "notification_branch_behaviour": ap("notification_branch_behaviour"),
        "notification_explainability": ap("notification_explainability"),
        "temporal_ordering": ap("temporal_ordering"),
        "audit_stability": ap("audit_stability"),
        "unrelated_surface_integrity": ap("unrelated_surface_integrity"),
        "verification_report": ap("verification_report"),
    }

    if fixture_gate_pass:
        drift = [] if semantic_stable else [{"detail": "R2!=R3_semantic", **replay_comp}]
        _write(
            out_dir / _artifact_name(prefix, "notification_replay", slug),
            {"runs": runs, "replay_notification_drift": drift, "replay_notification_comparison": replay_comp},
        )
        _write(out_dir / _artifact_name(prefix, "dedupe_determinism", slug), dedupe)
        _write(
            out_dir / _artifact_name(prefix, "lineage_trace", slug),
            {"client_id": cid, "property_id": pid, "correlation_matrix_ref": ap("correlation_matrix")},
        )
        _write(out_dir / _artifact_name(prefix, "correlation_matrix", slug), correlation)
        _write(out_dir / _artifact_name(prefix, "delivery_truth_matrix", slug), {"rows": truth_rows})
        _write(out_dir / _artifact_name(prefix, "delivery_authority", slug), delivery_auth)
        _write(out_dir / _artifact_name(prefix, "acknowledgement_semantics", slug), ack)
        _write(out_dir / _artifact_name(prefix, "visible_impact", slug), visible)
        _write(out_dir / _artifact_name(prefix, "lineage_boundedness", slug), lineage)
        _write(
            out_dir / _artifact_name(prefix, "delivery_boundedness", slug),
            {
                "message_logs_growth_on_replay": {
                    "R1": r1.get("message_log_count"),
                    "R2": next((x.get("message_log_count") for x in runs if x.get("run") == "R2"), None),
                    "R3": next((x.get("message_log_count") for x in runs if x.get("run") == "R3"), None),
                },
                "classification_deferred": True,
            },
        )
        _write(
            out_dir / _artifact_name(prefix, "suppression_replay", slug),
            {
                "suppression_fingerprint": suppression_fp,
                "suppression_replay_equal": suppression_equal,
                "m1_outcomes": m1_outcomes,
            },
        )
        _write(
            out_dir / _artifact_name(prefix, "notification_branch_behaviour", slug),
            {
                "notification_behaviour_classes": [
                    {"run": o.get("run"), "class": o.get("notification_branch_class"), "outcome": o.get("outcome")}
                    for o in m1_outcomes
                ],
                "activation_blocked": activation,
            },
        )
        _write(out_dir / _artifact_name(prefix, "notification_explainability", slug), explain)
        _write(out_dir / _artifact_name(prefix, "temporal_ordering", slug), temporal)
        _write(
            out_dir / _artifact_name(prefix, "audit_stability", slug),
            audit_notification_noise_snapshot(audit_before, audit_after),
        )
        _write(
            out_dir / _artifact_name(prefix, "unrelated_surface_integrity", slug),
            {
                "control_fingerprints_before": ctrl_fp_before,
                "control_fingerprints_after": ctrl_fp_after,
                "control_message_logs_before": ctrl_msg_before,
                "control_message_logs_after": ctrl_msg_after,
                "unrelated_mutation_delta": unrelated_delta,
                "unrelated_mutation_count": unrelated_count,
                "control_message_logs_fingerprint_changed": msg_delta,
            },
        )

    _write(out_dir / _artifact_name(prefix, "verification_report", slug), report)

    print(
        json.dumps(
            {
                "f1_pass": None,
                "classification_deferred": True,
                "critical_stop_triggered": bool(critical_stop_rc),
                "primary_rc_branch": critical_stop_rc,
                "fixture_classification": fixture_class,
                "checks": checks,
            },
            indent=2,
            default=str,
        )
    )

    if fixture_class == FIXTURE_NOTIFICATION_INCAPABLE:
        raise SystemExit(2)
    if critical_stop_rc:
        raise SystemExit(3)


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
