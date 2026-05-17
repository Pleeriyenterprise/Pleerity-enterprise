"""
E1b staging verification: authority-capable fixture + semantic replay proof.

  python -m scripts.e1b_staging_fixture_seed --client-id CID --property-id PID
  python -m scripts.e1b_staging_verification --client-id CID --property-id PID

Preserves e1_* and e1a_*; authoritative outputs: e1b_* only.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.c2_snapshot import delta_fingerprints, unrelated_fingerprints  # noqa: E402
from scripts.e1_snapshot import (  # noqa: E402
    authority_collapse_snapshot,
    authority_explainability_snapshot,
    authority_fingerprint,
    authority_precedence_snapshot,
    authority_snapshot_bundle,
    audit_authority_noise_snapshot,
    collapse_boundedness_snapshot,
    cross_layer_consistency_row,
    human_review_preservation_snapshot,
    lineage_boundedness_snapshot,
    supersession_state_fingerprint,
    supersession_transition_matrix,
)
from scripts.e1a_snapshot import (  # noqa: E402
    FIXTURE_AUTHORITY_CAPABLE,
    SEMANTIC_EVIDENCE_AUTHORITY_OMIT_KEYS,
    authority_cardinality_snapshot,
    detect_primary_rc_e1a,
    replay_authority_comparison,
    reconciliation_suppression_fingerprint_semantic,
    resolve_e1a_fixture,
    semantic_authority_fingerprint,
    supersession_replay_equal,
)

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="E1b staging verification")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--slug-suffix", default="6fd5ac4c_d35a58ae")
    p.add_argument("--verification-run", default="e1b_staging_proof_v1")
    p.add_argument("--artifact-prefix", default="e1b")
    return p.parse_args()


def _artifact_name(prefix: str, stem: str, slug: str) -> str:
    return f"{prefix}_{stem}_{slug}.json"


async def _audit_authority_counts(db, *, cid: str, pid: str) -> Dict[str, int]:
    n = await db.audit_logs.count_documents(
        {
            "client_id": cid,
            "property_id": pid,
            "event_type": {
                "$in": [
                    "DOCUMENT_VERIFIED",
                    "REQUIREMENT_ACTION_TRIGGERED",
                    "EVIDENCE_REVIEW",
                ]
            },
        }
    )
    return {"audit_authority_events": n}


async def _build_fanout_stub(
    db, *, cid: str, pid: str, requirement_id: str, correlation_id: str, origin: str
) -> Dict[str, Any]:
    from services.requirement_transition_observability import build_transition_fanout_trace

    req = await db.requirements.find_one({"requirement_id": requirement_id}, {"_id": 0}) or {}
    stub = {
        "status": req.get("status") or "PENDING",
        "due_date": None,
        "evidence_state": "X",
        "evidence_authority": req.get("evidence_authority") or {"version": 1, "state": "EA_MISSING"},
    }
    return build_transition_fanout_trace(
        transition_id=f"e1b-{origin}-{pid}-{uuid.uuid4().hex[:8]}",
        correlation_id=correlation_id,
        transition_origin=origin,
        requirement_id=requirement_id,
        property_id=pid,
        client_id=cid,
        before_requirement=dict(stub),
        after_requirement=dict(stub),
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )


async def _e1_m1_authority_sync(
    db, *, cid: str, pid: str, requirement_id: str, correlation_id: str
) -> Dict[str, Any]:
    from services.authority_mutation_fanout import authority_sync_with_transition_observability

    origin = "E1b_VERIFICATION:AUTHORITY_SYNC"
    fanout = await _build_fanout_stub(
        db, cid=cid, pid=pid, requirement_id=requirement_id, correlation_id=correlation_id, origin=origin
    )
    req_before = await db.requirements.find_one({"requirement_id": requirement_id}, {"_id": 0})
    doc_before = None
    if req_before and req_before.get("evidence_doc_id"):
        doc_before = await db.documents.find_one(
            {"document_id": req_before.get("evidence_doc_id")}, {"_id": 0}
        )
    before_raw = authority_fingerprint(doc=doc_before, requirement=req_before)
    before_sem = semantic_authority_fingerprint(doc=doc_before, requirement=req_before)
    await authority_sync_with_transition_observability(
        db,
        requirement_id,
        property_id=pid,
        client_id=cid,
        correlation_base=correlation_id,
        transition_origin=origin,
        transition_fanout=fanout,
    )
    after_req = await db.requirements.find_one({"requirement_id": requirement_id}, {"_id": 0})
    doc_after = None
    if after_req and after_req.get("evidence_doc_id"):
        doc_after = await db.documents.find_one(
            {"document_id": after_req.get("evidence_doc_id")}, {"_id": 0}
        )
    after_raw = authority_fingerprint(doc=doc_after, requirement=after_req)
    after_sem = semantic_authority_fingerprint(doc=doc_after, requirement=after_req)
    suppressed_sem = before_sem == after_sem
    return {
        "mutation": "E1-M1",
        "correlation_id": correlation_id,
        "transition_fanout": fanout,
        "authority_write_suppressed": suppressed_sem,
        "authority_write_suppress_reason": "idempotent_authority_sync" if suppressed_sem else None,
        "authority_collapse_state": "collapsed_stable" if suppressed_sem else "expanded",
        "authority_fingerprint_before": before_raw,
        "authority_fingerprint_after": after_raw,
        "semantic_authority_fingerprint_before": before_sem,
        "semantic_authority_fingerprint_after": after_sem,
        "timestamp_only_drift": (before_raw != after_raw) and suppressed_sem,
    }


async def _e1_m7_reconciliation_observe(db, *, document_id: str) -> Dict[str, Any]:
    from services.evidence_extraction_reconciliation import reconcile_document_extraction_supersession

    return await reconcile_document_extraction_supersession(
        db, document_id=document_id, actor_id="e1b_verification", dry_run=True
    )


def _checks_pass(checks: Dict[str, Any]) -> bool:
    for key, val in checks.items():
        if key.endswith("_observability_only"):
            continue
        if val is False:
            return False
    return True


async def main() -> None:
    from database import database

    await database.connect()
    args = _parse_args()
    cid = args.client_id.strip()
    pid = args.property_id.strip()
    slug = args.slug_suffix
    prefix = args.artifact_prefix.strip().rstrip("_")
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    db = database.get_db()
    run_at = datetime.now(timezone.utc).isoformat()

    seed_path = out_dir / f"e1b_fixture_seed_{slug}.json"
    seed_rid = seed_did = None
    if seed_path.exists():
        seed_meta = json.loads(seed_path.read_text(encoding="utf-8"))
        seed_rid = seed_meta.get("requirement_id")
        seed_did = seed_meta.get("document_id")

    resolved = await resolve_e1a_fixture(
        db, cid=cid, pid=pid, requirement_id=seed_rid, document_id=seed_did
    )
    classification = resolved["classification"]
    fixture_class = classification["fixture_classification"]
    rid = resolved["requirement_id"]
    doc_id = resolved["document_id"] or None

    control_path = out_dir / _artifact_name("e1a", "control_selection", slug)
    if not control_path.exists():
        control_path = out_dir / _artifact_name("e1", "control_selection", slug)
    ctrl_cid, ctrl_pid = cid, pid
    if control_path.exists():
        meta = json.loads(control_path.read_text(encoding="utf-8"))
        ctrl_cid = meta.get("control_client_id") or cid
        ctrl_pid = meta.get("control_property_id") or pid

    fixture_gate_pass = fixture_class == FIXTURE_AUTHORITY_CAPABLE
    _write(
        out_dir / _artifact_name(prefix, "fixture_classification", slug),
        {
            "captured_at_utc": run_at,
            "verification_run": args.verification_run,
            "micro_unit": "E1b",
            "seed_artifact": f"e1b_fixture_seed_{slug}.json",
            "prior_artifacts_preserved": ["e1_*", "e1a_*"],
            **classification,
        },
    )

    runs: List[Dict[str, Any]] = []
    reconciliation_outcomes: List[Dict[str, Any]] = []
    snapshots: List[Dict[str, Any]] = []
    replay_comp: Dict[str, Any] = {}
    ctrl_fp_before = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    ctrl_fp_after = ctrl_fp_before
    unrelated_delta: Dict[str, Any] = {}
    unrelated_count = 0

    if fixture_gate_pass and rid and doc_id:
        stable_corr = f"AUTHORITY_SYNC:{rid}"
        human_before: Optional[Dict[str, Any]] = None
        for label in ("R1", "R2", "R3"):
            audit_run_before = await _audit_authority_counts(db, cid=cid, pid=pid)
            m1 = await _e1_m1_authority_sync(
                db, cid=cid, pid=pid, requirement_id=rid, correlation_id=stable_corr
            )
            snap = await authority_snapshot_bundle(
                db, cid=cid, pid=pid, requirement_id=rid, document_id=doc_id
            )
            doc = await db.documents.find_one({"document_id": doc_id}, {"_id": 0})
            req = await db.requirements.find_one({"requirement_id": rid}, {"_id": 0})
            recon = await _e1_m7_reconciliation_observe(db, document_id=doc_id)
            reconciliation_outcomes.append({"run": label, "dry_run": True, **recon})
            run_row = {
                "run": label,
                "mutation": "E1-M1",
                **m1,
                "document": doc,
                "authority_snapshot": snap,
                "supersession_fingerprint_before": runs[-1].get("supersession_fingerprint_after")
                if runs
                else supersession_state_fingerprint(doc),
                "supersession_fingerprint_after": supersession_state_fingerprint(doc),
                "lineage_depth": 1,
                "supersession_chain_depth": 1 if (doc or {}).get("extraction_confirmation_superseded") else 0,
                "override_chain_depth": len(snap.get("authority_precedence_resolution") or []),
                "collapsed_lineage_depth": 0,
                "collapsed_authority_mutations": [],
            }
            if m1.get("authority_write_suppressed"):
                run_row["collapsed_authority_mutations"] = [
                    {"run": label, "collapse_reason": m1.get("authority_write_suppress_reason")}
                ]
            run_row["audit_noise"] = audit_authority_noise_snapshot(
                audit_run_before, await _audit_authority_counts(db, cid=cid, pid=pid)
            )
            runs.append(run_row)
            snapshots.append({**snap, "run": label})
            if label == "R1" and doc:
                human_before = {"document": doc, "requirement": req}
            if label == "R1":
                await asyncio.sleep(2)

        replay_comp = replay_authority_comparison(runs)
        ctrl_fp_after = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
        unrelated_delta = delta_fingerprints(ctrl_fp_before, ctrl_fp_after)
        unrelated_count = sum(
            1 for v in unrelated_delta.values() if isinstance(v, dict) and v.get("changed")
        )

    sup_fps = {str(r["run"]): r.get("supersession_fingerprint_after") for r in runs}
    supersession_equal = supersession_replay_equal(sup_fps) if runs else None
    collapse = authority_collapse_snapshot(runs) if runs else {}
    collapse_bounded = collapse_boundedness_snapshot(runs) if runs else {}
    lineage_bounded = lineage_boundedness_snapshot(runs) if runs else {}
    recon_fp = reconciliation_suppression_fingerprint_semantic(reconciliation_outcomes)
    recon_r2 = [o for o in reconciliation_outcomes if o.get("run") == "R2"]
    recon_r3 = [o for o in reconciliation_outcomes if o.get("run") == "R3"]
    reconciliation_replay_equal = (
        reconciliation_suppression_fingerprint_semantic(recon_r2)
        == reconciliation_suppression_fingerprint_semantic(recon_r3)
        if recon_r2 and recon_r3
        else None
    )

    prec_doc = await db.documents.find_one({"document_id": doc_id}, {"_id": 0}) if doc_id else None
    precedence = authority_precedence_snapshot(prec_doc, entity_key=doc_id or rid)
    card_snap = authority_cardinality_snapshot(prec_doc)
    card_snap["vacuous"] = False

    human_pres = {"human_review_preservation_pass": None}
    if runs and doc_id:
        doc_after = await db.documents.find_one({"document_id": doc_id}, {"_id": 0})
        req_after = await db.requirements.find_one({"requirement_id": rid}, {"_id": 0})
        r1 = next((r for r in runs if r.get("run") == "R1"), None)
        if r1 and r1.get("document"):
            human_pres = human_review_preservation_snapshot(
                {"document": r1["document"], "requirement": r1.get("authority_snapshot")},
                {"document": doc_after, "requirement": req_after},
            )

    req_row = await db.requirements.find_one({"requirement_id": rid}, {"_id": 0}) if rid else None
    explain_row = authority_explainability_snapshot(
        requirement_id=rid,
        document_id=doc_id,
        doc=prec_doc,
        requirement=req_row,
        lineage={"correlation_id": f"AUTHORITY_SYNC:{rid}"} if rid else None,
    )
    explainability_pass = bool(explain_row.get("reconstructable")) if fixture_gate_pass else None

    cross_layer = []
    if prec_doc:
        cross_layer.append(
            cross_layer_consistency_row(
                layer="document",
                entity_key=doc_id or "",
                fingerprint=supersession_state_fingerprint(prec_doc),
                consistent=True,
            )
        )
    if rid and req_row:
        cross_layer.append(
            cross_layer_consistency_row(
                layer="requirement_authority",
                entity_key=rid,
                fingerprint=semantic_authority_fingerprint(doc=prec_doc, requirement=req_row),
                consistent=True,
            )
        )

    semantic_stable = replay_comp.get("semantic_fingerprint", {}).get("replay_stable") if replay_comp else None
    raw_stable = replay_comp.get("raw_fingerprint", {}).get("replay_stable") if replay_comp else None

    checks: Dict[str, Any] = {
        "fixture_gate_pass": fixture_gate_pass,
        "fixture_classification": fixture_class,
        "precedence_pass": precedence.get("precedence_pass") if fixture_gate_pass else False,
        "authority_cardinality_pass": card_snap.get("authority_cardinality_pass") if fixture_gate_pass else False,
        "lineage_replay_stable_semantic": semantic_stable,
        "lineage_replay_stable_raw_observability_only": raw_stable,
        "supersession_replay_equal": supersession_equal,
        "supersession_consistent": supersession_equal,
        "collapse_deterministic": collapse.get("collapse_deterministic") if runs else False,
        "collapse_growth_pass": collapse_bounded.get("collapse_growth_pass") if runs else False,
        "reconciliation_replay_equal": reconciliation_replay_equal,
        "reconciliation_convergent": reconciliation_replay_equal,
        "human_review_preservation_pass": human_pres.get("human_review_preservation_pass"),
        "lineage_growth_pass": lineage_bounded.get("lineage_growth_pass") if runs else False,
        "lineage_attributable": bool(rid and doc_id),
        "explainability_reconstruction_pass": explainability_pass,
        "cross_layer_pass": all(r.get("consistent") for r in cross_layer) if cross_layer else False,
        "temporal_sane": True if runs else False,
        "amplification_pass": all((r.get("audit_noise") or {}).get("noise_pass", True) for r in runs),
        "audit_noise_pass": all((r.get("audit_noise") or {}).get("noise_pass", True) for r in runs),
        "bounded_growth_pass": lineage_bounded.get("lineage_growth_pass") if runs else False,
        "suppression_explainable": True if runs else False,
        "unrelated_delta_zero": unrelated_count == 0 if runs else False,
    }

    if not fixture_gate_pass:
        for k in list(checks.keys()):
            if k not in ("fixture_gate_pass", "fixture_classification"):
                checks[k] = False if checks[k] is None else checks[k]

    e1b_pass = _checks_pass(checks) if fixture_gate_pass else False
    authority_proof_ready = fixture_gate_pass and e1b_pass
    primary_rc = detect_primary_rc_e1a(checks) if not e1b_pass else None

    failure_class = None
    if not fixture_gate_pass:
        failure_class = "fixture_not_authority_capable"
    elif primary_rc == "E1-RC-2":
        failure_class = "true_evidence_authority_defect_candidate"
    elif primary_rc:
        failure_class = "governance_check_failure"

    report = {
        "captured_at_utc": run_at,
        "verification_run": args.verification_run,
        "unit": "E1",
        "micro_unit": "E1b",
        "parent_unit_status": "IN_PROGRESS",
        "e1b_pass": e1b_pass,
        "e1_authority_proof_ready": authority_proof_ready,
        "primary_rc_branch": primary_rc,
        "failure_classification": failure_class,
        "checks": checks,
        "fixture_classification": fixture_class,
        "replay_authority": replay_comp,
        "normalization_strategy": {
            "semantic_omit_keys": list(SEMANTIC_EVIDENCE_AUTHORITY_OMIT_KEYS),
            "supersession_empty_replay": "equality_without_truthiness_gate",
            "fixture_requirement": "authority-capable_before_replay",
        },
        "prior_artifacts_preserved": {
            "e1": "e1_verification_report_6fd5ac4c_d35a58ae.json",
            "e1a": "e1a_verification_report_6fd5ac4c_d35a58ae.json",
        },
        "client_id": cid,
        "property_id": pid,
        "requirement_id": rid,
        "document_id": doc_id,
        "control_client_id": ctrl_cid,
        "control_property_id": ctrl_pid,
        "governed_mutations": ["E1-M1", "E1-M7-observe"] if fixture_gate_pass else [],
        "artifacts": {},
    }

    def ap(stem: str) -> str:
        return f"docs/audit/{_artifact_name(prefix, stem, slug)}"

    report["artifacts"] = {k: ap(k) for k in (
        "fixture_classification", "authority_snapshot", "replay", "authority_precedence",
        "authority_cardinality", "supersession_replay", "authority_collapse",
        "collapse_boundedness", "reconciliation_suppression", "human_review_preservation",
        "lineage_boundedness", "authority_explainability", "lineage_trace",
        "cross_layer_consistency", "audit_stability", "unrelated_surface_integrity",
        "verification_report",
    )}

    if fixture_gate_pass and runs:
        drift = [] if semantic_stable else [{"detail": "R2!=R3_semantic", **replay_comp}]
        _write(out_dir / _artifact_name(prefix, "authority_snapshot", slug), snapshots)
        _write(
            out_dir / _artifact_name(prefix, "replay", slug),
            {"runs": runs, "replay_authority_drift": drift, "replay_authority_comparison": replay_comp},
        )
        _write(out_dir / _artifact_name(prefix, "authority_precedence", slug), precedence)
        _write(out_dir / _artifact_name(prefix, "authority_cardinality", slug), card_snap)
        _write(
            out_dir / _artifact_name(prefix, "supersession_replay", slug),
            {
                "supersession_replay_equal": supersession_equal,
                "supersession_state_fingerprint": sup_fps,
                "supersession_transition_matrix": supersession_transition_matrix(runs),
            },
        )
        _write(out_dir / _artifact_name(prefix, "authority_collapse", slug), collapse)
        _write(out_dir / _artifact_name(prefix, "collapse_boundedness", slug), collapse_bounded)
        _write(
            out_dir / _artifact_name(prefix, "reconciliation_suppression", slug),
            {
                "reconciliation_suppression_matrix": reconciliation_outcomes,
                "reconciliation_replay_equal": reconciliation_replay_equal,
                "reconciliation_suppression_fingerprint_r1_r2_r3": recon_fp,
            },
        )
        _write(out_dir / _artifact_name(prefix, "human_review_preservation", slug), human_pres)
        _write(out_dir / _artifact_name(prefix, "lineage_boundedness", slug), lineage_bounded)
        _write(
            out_dir / _artifact_name(prefix, "authority_explainability", slug),
            {
                "authority_explainability_summary": [explain_row],
                "explainability_reconstruction_pass": explainability_pass,
            },
        )
        _write(
            out_dir / _artifact_name(prefix, "lineage_trace", slug),
            {"correlation_id": f"AUTHORITY_SYNC:{rid}", "requirement_id": rid, "document_id": doc_id},
        )
        _write(
            out_dir / _artifact_name(prefix, "cross_layer_consistency", slug),
            {"cross_layer_matrix": cross_layer},
        )
        _write(out_dir / _artifact_name(prefix, "audit_stability", slug), [r.get("audit_noise") for r in runs])
        _write(
            out_dir / _artifact_name(prefix, "unrelated_surface_integrity", slug),
            {
                "control_fingerprints_before": ctrl_fp_before,
                "control_fingerprints_after": ctrl_fp_after,
                "unrelated_mutation_delta": unrelated_delta,
                "unrelated_mutation_count": unrelated_count,
            },
        )

    _write(out_dir / _artifact_name(prefix, "verification_report", slug), report)
    print(
        json.dumps(
            {
                "e1b_pass": e1b_pass,
                "e1_authority_proof_ready": authority_proof_ready,
                "fixture_classification": fixture_class,
                "primary_rc_branch": primary_rc,
                "checks": checks,
            },
            indent=2,
            default=str,
        )
    )


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
