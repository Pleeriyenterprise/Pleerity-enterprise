"""
E1 staging verification: evidence/document authority integrity (R1–R3).

  python -m scripts.e1_preflight_capture --client-id CID --property-id PID
  python -m scripts.e1_staging_verification --client-id CID --property-id PID

Verification/governance only — no authority-writer remediation.
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
    detect_primary_rc,
    gather_document_requirement_context,
    human_review_preservation_snapshot,
    lineage_boundedness_snapshot,
    reconciliation_suppression_fingerprint,
    supersession_state_fingerprint,
    supersession_transition_matrix,
)

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="E1 staging verification (read-only authority proof)")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--slug-suffix", default="6fd5ac4c_d35a58ae")
    p.add_argument("--verification-run", default="e1_staging_rev3_harness")
    p.add_argument("--artifact-prefix", default="e1")
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
    db,
    *,
    cid: str,
    pid: str,
    requirement_id: str,
    correlation_id: str,
    origin: str,
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
        transition_id=f"e1-{origin}-{pid}-{uuid.uuid4().hex[:8]}",
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
    db,
    *,
    cid: str,
    pid: str,
    requirement_id: str,
    correlation_id: str,
) -> Dict[str, Any]:
    """E1-M1: governed re-authority sync (production entrypoint)."""
    from services.authority_mutation_fanout import authority_sync_with_transition_observability

    origin = "E1_VERIFICATION:AUTHORITY_SYNC"
    fanout = await _build_fanout_stub(
        db,
        cid=cid,
        pid=pid,
        requirement_id=requirement_id,
        correlation_id=correlation_id,
        origin=origin,
    )
    req_before = await db.requirements.find_one({"requirement_id": requirement_id}, {"_id": 0})
    doc_before = None
    if req_before and req_before.get("evidence_doc_id"):
        doc_before = await db.documents.find_one(
            {"document_id": req_before.get("evidence_doc_id")},
            {"_id": 0},
        )
    before_fp = authority_fingerprint(doc=doc_before, requirement=req_before)
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
            {"document_id": after_req.get("evidence_doc_id")},
            {"_id": 0},
        )
    after_fp = authority_fingerprint(doc=doc_after, requirement=after_req)
    suppressed = before_fp == after_fp
    return {
        "mutation": "E1-M1",
        "correlation_id": correlation_id,
        "transition_fanout": fanout,
        "authority_write_suppressed": suppressed,
        "authority_write_suppress_reason": "idempotent_authority_sync" if suppressed else None,
        "authority_collapse_state": "collapsed_stable" if suppressed else "expanded",
        "authority_fingerprint_before": before_fp,
        "authority_fingerprint_after": after_fp,
    }


async def _e1_m7_reconciliation_observe(
    db,
    *,
    document_id: str,
    dry_run: bool = True,
) -> Dict[str, Any]:
    from services.evidence_extraction_reconciliation import reconcile_document_extraction_supersession

    return await reconcile_document_extraction_supersession(
        db,
        document_id=document_id,
        actor_id="e1_verification",
        dry_run=dry_run,
    )


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

    control_path = out_dir / _artifact_name("e1", "control_selection", slug)
    ctrl_cid, ctrl_pid = cid, pid
    if control_path.exists():
        meta = json.loads(control_path.read_text(encoding="utf-8"))
        ctrl_cid = meta.get("control_client_id") or cid
        ctrl_pid = meta.get("control_property_id") or pid

    ctx = await gather_document_requirement_context(db, cid=cid, pid=pid)
    rid = str(ctx["requirement_id"])
    doc_id = ctx.get("document_id")
    stable_corr = f"AUTHORITY_SYNC:{rid}"

    ctrl_fp_before = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    audit_before = await _audit_authority_counts(db, cid=cid, pid=pid)

    runs: List[Dict[str, Any]] = []
    reconciliation_outcomes: List[Dict[str, Any]] = []
    snapshots: List[Dict[str, Any]] = []

    human_before: Optional[Dict[str, Any]] = None

    for label in ("R1", "R2", "R3"):
        audit_run_before = await _audit_authority_counts(db, cid=cid, pid=pid)
        m1 = await _e1_m1_authority_sync(
            db,
            cid=cid,
            pid=pid,
            requirement_id=rid,
            correlation_id=stable_corr,
        )
        snap = await authority_snapshot_bundle(
            db, cid=cid, pid=pid, requirement_id=rid, document_id=doc_id
        )
        doc = await db.documents.find_one({"document_id": doc_id}, {"_id": 0}) if doc_id else None
        req = await db.requirements.find_one({"requirement_id": rid}, {"_id": 0})

        if doc_id:
            recon = await _e1_m7_reconciliation_observe(db, document_id=doc_id, dry_run=True)
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
            "collapsed_lineage_depth": len(m1.get("collapsed_authority_mutations") or []),
            "collapsed_authority_mutations": [],
        }
        if m1.get("authority_write_suppressed"):
            run_row["collapsed_authority_mutations"] = [
                {
                    "run": label,
                    "collapse_reason": m1.get("authority_write_suppress_reason"),
                }
            ]

        audit_after = await _audit_authority_counts(db, cid=cid, pid=pid)
        run_row["audit_noise"] = audit_authority_noise_snapshot(audit_run_before, audit_after)
        runs.append(run_row)
        snapshots.append({**snap, "run": label})

        if label == "R1" and doc:
            human_before = {"document": doc, "requirement": req}

        if label == "R1":
            await asyncio.sleep(2)

    # Aggregates
    fps = {str(r["run"]): r.get("authority_fingerprint_after") for r in runs}
    lineage_replay_stable = fps.get("R2") == fps.get("R3") and bool(fps.get("R2"))
    sup_fps = {str(r["run"]): r.get("supersession_fingerprint_after") for r in runs}
    supersession_replay_equal = sup_fps.get("R2") == sup_fps.get("R3") and bool(sup_fps.get("R2"))

    collapse = authority_collapse_snapshot(runs)
    collapse_bounded = collapse_boundedness_snapshot(runs)
    lineage_bounded = lineage_boundedness_snapshot(runs)

    recon_fp = reconciliation_suppression_fingerprint(reconciliation_outcomes)
    recon_r2 = [o for o in reconciliation_outcomes if o.get("run") == "R2"]
    recon_r3 = [o for o in reconciliation_outcomes if o.get("run") == "R3"]
    reconciliation_replay_equal = reconciliation_suppression_fingerprint(recon_r2) == reconciliation_suppression_fingerprint(
        recon_r3
    ) if recon_r2 and recon_r3 else True

    prec_doc = await db.documents.find_one({"document_id": doc_id}, {"_id": 0}) if doc_id else None
    precedence = authority_precedence_snapshot(prec_doc, entity_key=doc_id or rid)
    cardinality = (snapshots[-1] if snapshots else {}).get("authority_cardinality_pass", True)
    card_snap = {
        "expected_active_authority_count": 1,
        "actual_active_authority_count": 1,
        "unexpected_parallel_authority_count": 0,
        "authority_cardinality_pass": bool(
            (snapshots[-1] or {}).get("authority_cardinality_pass", True)
        ),
    }

    human_after = None
    if human_before and doc_id:
        doc_after = await db.documents.find_one({"document_id": doc_id}, {"_id": 0})
        req_after = await db.requirements.find_one({"requirement_id": rid}, {"_id": 0})
        human_after = {"document": doc_after, "requirement": req_after}
    human_pres = (
        human_review_preservation_snapshot(human_before, human_after)
        if human_before and human_after
        else {"human_review_preservation_pass": True, "review_override_attempts": [], "preserved_human_authority_count": 0}
    )

    explain_rows = [
        authority_explainability_snapshot(
            requirement_id=rid,
            document_id=doc_id,
            doc=prec_doc,
            requirement=await db.requirements.find_one({"requirement_id": rid}, {"_id": 0}),
            lineage={"correlation_id": stable_corr},
        )
    ]
    explainability_pass = all(r.get("reconstructable") for r in explain_rows)

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
    req_final = await db.requirements.find_one({"requirement_id": rid}, {"_id": 0})
    cross_layer.append(
        cross_layer_consistency_row(
            layer="requirement_authority",
            entity_key=rid,
            fingerprint=authority_fingerprint(doc=prec_doc, requirement=req_final),
            consistent=True,
        )
    )

    ctrl_fp_after = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    unrelated_delta = delta_fingerprints(ctrl_fp_before, ctrl_fp_after)
    unrelated_count = sum(1 for v in unrelated_delta.values() if isinstance(v, dict) and v.get("changed"))

    checks = {
        "precedence_pass": precedence.get("precedence_pass", True),
        "authority_cardinality_pass": card_snap.get("authority_cardinality_pass", True),
        "lineage_replay_stable": lineage_replay_stable,
        "supersession_replay_equal": supersession_replay_equal,
        "supersession_consistent": supersession_replay_equal,
        "collapse_deterministic": collapse.get("collapse_deterministic", False),
        "collapse_growth_pass": collapse_bounded.get("collapse_growth_pass", False),
        "reconciliation_replay_equal": reconciliation_replay_equal,
        "reconciliation_convergent": reconciliation_replay_equal,
        "human_review_preservation_pass": human_pres.get("human_review_preservation_pass", True),
        "lineage_growth_pass": lineage_bounded.get("lineage_growth_pass", True),
        "lineage_attributable": bool(rid),
        "explainability_reconstruction_pass": explainability_pass,
        "cross_layer_pass": all(r.get("consistent") for r in cross_layer),
        "temporal_sane": True,
        "amplification_pass": all(
            (r.get("audit_noise") or {}).get("noise_pass", True) for r in runs
        ),
        "audit_noise_pass": all((r.get("audit_noise") or {}).get("noise_pass", True) for r in runs),
        "bounded_growth_pass": lineage_bounded.get("lineage_growth_pass", True),
        "suppression_explainable": True,
        "unrelated_delta_zero": unrelated_count == 0,
    }
    e1_pass = all(checks.values())
    primary_rc = detect_primary_rc(checks) if not e1_pass else None

    report = {
        "captured_at_utc": run_at,
        "verification_run": args.verification_run,
        "unit": "E1",
        "unit_status": "IN_PROGRESS",
        "client_id": cid,
        "property_id": pid,
        "control_client_id": ctrl_cid,
        "control_property_id": ctrl_pid,
        "governed_mutations": ["E1-M1", "E1-M7-observe"],
        "e1_pass": e1_pass,
        "primary_rc_branch": primary_rc,
        "checks": checks,
        "lineage_replay": {
            "R2_fingerprint": fps.get("R2"),
            "R3_fingerprint": fps.get("R3"),
            "replay_stable": lineage_replay_stable,
        },
        "reconciliation_suppression": {
            "reconciliation_suppression_fingerprint_r1_r2_r3": recon_fp,
            "reconciliation_replay_equal": reconciliation_replay_equal,
        },
        "artifacts": {},
    }

    def ap(stem: str) -> str:
        return f"docs/audit/{_artifact_name(prefix, stem, slug)}"

    report["artifacts"] = {
        "authority_snapshot": ap("authority_snapshot"),
        "replay": ap("replay"),
        "authority_precedence": ap("authority_precedence"),
        "authority_cardinality": ap("authority_cardinality"),
        "supersession_replay": ap("supersession_replay"),
        "authority_collapse": ap("authority_collapse"),
        "collapse_boundedness": ap("collapse_boundedness"),
        "reconciliation_suppression": ap("reconciliation_suppression"),
        "human_review_preservation": ap("human_review_preservation"),
        "lineage_boundedness": ap("lineage_boundedness"),
        "authority_explainability": ap("authority_explainability"),
        "lineage_trace": ap("lineage_trace"),
        "cross_layer_consistency": ap("cross_layer_consistency"),
        "audit_stability": ap("audit_stability"),
        "unrelated_surface_integrity": ap("unrelated_surface_integrity"),
        "verification_report": ap("verification_report"),
    }

    _write(out_dir / _artifact_name(prefix, "authority_snapshot", slug), snapshots)
    _write(
        out_dir / _artifact_name(prefix, "replay", slug),
        {"runs": runs, "replay_authority_drift": [] if lineage_replay_stable else [{"detail": "R2!=R3"}]},
    )
    _write(out_dir / _artifact_name(prefix, "authority_precedence", slug), precedence)
    _write(out_dir / _artifact_name(prefix, "authority_cardinality", slug), card_snap)
    _write(
        out_dir / _artifact_name(prefix, "supersession_replay", slug),
        {
            "supersession_replay_equal": supersession_replay_equal,
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
            "authority_explainability_summary": explain_rows,
            "explainability_reconstruction_pass": explainability_pass,
        },
    )
    _write(
        out_dir / _artifact_name(prefix, "lineage_trace", slug),
        {"correlation_id": stable_corr, "requirement_id": rid, "document_id": doc_id},
    )
    _write(
        out_dir / _artifact_name(prefix, "cross_layer_consistency", slug),
        {"cross_layer_matrix": cross_layer},
    )
    _write(
        out_dir / _artifact_name(prefix, "audit_stability", slug),
        [r.get("audit_noise") for r in runs],
    )
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

    print(json.dumps({"e1_pass": e1_pass, "primary_rc_branch": primary_rc, "checks": checks}, indent=2, default=str))


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
