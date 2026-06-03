#!/usr/bin/env python3
"""SCORE-RECALCULATION-LATENCY-CONVERGENCE-01 — audit pack generator."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/score_recalculation_latency_convergence_01"
FRONTEND = ROOT.parent / "frontend"
BACKEND = ROOT


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _run(cmd: str, cwd: Path) -> bool:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, shell=True, timeout=300)
    return proc.returncode == 0


def main() -> int:
    verified_at = _utc()

    root_cause = {
        "programme": "SCORE-RECALCULATION-LATENCY-CONVERGENCE-01",
        "verified_at": verified_at,
        "prior_programme": "PROPERTY-COMPLIANCE-SCORE-CONVERGENCE-DRIFT-01 (PARTIAL @ 0b7ed60c)",
        "propagation_flow": {
            "mutation": "evidence/declaration/verify → authority sync → enqueue_compliance_recalc",
            "queue": "compliance_recalc_queue (PENDING → RUNNING → DONE)",
            "worker": "job_runner.run_compliance_recalc_worker (~15s schedule)",
            "persist": "recalculate_and_persist → compliance_score_pending=false",
            "read_models": "portfolio/compliance-score APIs + score_cognition_service",
        },
        "root_causes": [
            "resolve_property_score_status returned ok/stale when score existed even if compliance_score_pending=true",
            "duplicate enqueue suppression did not re-mark compliance_score_pending on property",
            "portfolio aggregate ignored pending recalc when all properties had persisted scores",
            "stale risk_level and grade shown during async window on property/portfolio surfaces",
            "read-path authority refresh (client_applicability_coherence) synced authority without enqueue",
        ],
        "stale_snapshot_window": "From mutation until worker completes recalculate_and_persist (typically seconds–minutes)",
        "fixes": [
            "pending dominates property score_status (calculating)",
            "duplicate enqueue re-sets compliance_score_pending for PENDING/RUNNING/FAILED jobs",
            "portfolio partial + pending message when recalc in flight",
            "suppress stale risk labels when calculating; show Updating…",
            "enqueue recalc after stale authority read-path refresh",
        ],
    }
    _write("root_cause.json", root_cause)

    governance = {
        "verified_at": verified_at,
        "timing_model": {
            "immediate_ui_truth": "Requirement lifecycle / attention / missing-doc KPIs converge on mutation response",
            "persisted_score_snapshot": "Async via compliance_recalc_queue worker",
            "async_window_ux": [
                "score_status=calculating",
                "Score updating — recent compliance changes are being processed",
                "portfolio_score_recalc_pending_note on compliance-score API",
            ],
            "must_not": "Users believe unresolved legal risk exists when only recalc is pending",
        },
    }
    _write("governance_runtime.json", governance)

    enqueue = {
        "verified_at": verified_at,
        "with_enqueue": [
            "document upload/verify/delete (fanout)",
            "CER create + platform/org verification (propagate_requirement_evidence_outcome)",
            "evidence review V2 verify",
            "patch_requirement, mark_not_applicable, reopen",
            "property create/update, requirements sync",
            "tenant delivery gap sync, provisioning, governed rules",
            "lazy backfill, admin manual recalc, expiry rollover job",
            "stale authority read-path refresh (NEW)",
        ],
        "sync_recalc_no_queue": ["compliance_outcome_engine.apply_outcome", "admin validate fix=true"],
        "gaps_closed": [
            "duplicate suppression now re-marks compliance_score_pending",
            "authority read refresh now enqueues per property",
        ],
        "residual_risks": [
            "activation gate may defer enqueue (governed; propagation_notice)",
            "same correlation_id replay after DONE does not auto-regenerate without new correlation",
        ],
    }
    _write("enqueue_runtime.json", enqueue)

    latency = {
        "verified_at": verified_at,
        "targets": {
            "queue_worker_schedule_seconds": 15,
            "acceptable_recalc_completion": "< 2 minutes under normal load",
            "degraded": "2–10 minutes with backlog",
            "operationally_dangerous": "> 10 minutes or pending flag stuck true",
        },
        "classification": "acceptable_architecture_degraded_ux_without_pending_honesty",
        "note": "Latency not re-profiled on staging in this slice; UX convergence is primary remediation.",
    }
    _write("latency_runtime.json", latency)

    repair = {
        "verified_at": verified_at,
        "tooling": {
            "admin_recalc": "POST /api/admin/.../actions/recalculate-compliance",
            "validate_repair": "POST validate-compliance-score fix=true → recalculate_and_persist",
            "reconciliation_batch": "compliance_score_reconciliation_service",
            "queue_monitor": "GET compliance-recalc-status, compliance-sla",
            "scheduled_batch": "run_compliance_recalc_enqueue_property",
        },
        "properties": ["audited", "idempotent enqueue", "tenant-scoped", "correlation_id dedupe"],
    }
    _write("repair_runtime.json", repair)

    browser = {
        "verified_at": verified_at,
        "status": "PARTIAL",
        "expected_sequence": {
            "before": "Persisted score reflects pre-mutation snapshot",
            "pending": "score_status=calculating, Updating…, no Elevated risk label, cognition line shows processing",
            "converged": "Worker completes; pending=false; score/risk align with requirement truth",
        },
        "note": "Structural/API convergence verified via unit tests; live browser capture pending staging deploy.",
    }
    _write("browser_runtime.json", browser)

    be_ok = _run(
        "python -m pytest tests/test_scoring_semantics_v1.py tests/test_compliance_recalc_queue_stabilization_phase1.py "
        "tests/test_score_cognition_service.py tests/test_compliance_scoring_satisfaction_convergence.py "
        "tests/test_portfolio_pending_score_recalc_snapshot.py tests/test_requirement_action_orchestration.py -q",
        BACKEND,
    )

    regression = {
        "verified_at": verified_at,
        "backend_tests_passed": be_ok,
        "surfaces": [
            "scoring semantics v1",
            "recalc queue",
            "score cognition",
            "satisfaction scoring convergence",
            "requirement action orchestration",
        ],
    }
    _write("regression_runtime.json", regression)

    classification = {
        "programme": "SCORE-RECALCULATION-LATENCY-CONVERGENCE-01",
        "verified_at": verified_at,
        "classification": "SCORE_PROPAGATION_DRIFT" if be_ok else "FAIL_OPERATIONAL",
        "code_convergence": "COMPLETE" if be_ok else "INCOMPLETE",
        "rationale": "Stale snapshot cognition during async window remediated; VERIFIED_OPERATIONALLY requires staging browser proof.",
        "requires_follow_up": ["Staging browser before/pending/after capture on declaration or verify flow"],
    }
    if be_ok:
        classification["classification"] = "PARTIAL"
    _write("classifications.json", classification)

    watchlist = """# Watchlist — SCORE-RECALCULATION-LATENCY-CONVERGENCE-01

## Post-deploy verification
- [ ] Submit declaration → property shows Updating… / calculating (not stale Elevated risk)
- [ ] Verify document → pending state → score converges within worker SLA
- [ ] Portfolio with 1 pending property shows partial + pending note

## Monitor
- [ ] compliance_recalc_queue backlog depth
- [ ] Properties with compliance_score_pending=true > 10 minutes (stuck marker)
- [ ] activation gate deferrals without propagation_notice

## Residual
- Outcome engine sync recalc vs async queue mixed semantics (documented, not unified)
"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")

    report = f"""# SCORE-RECALCULATION-LATENCY-CONVERGENCE-01

Verified at: {verified_at}
Builds on: PROPERTY-COMPLIANCE-SCORE-CONVERGENCE-DRIFT-01 @ 0b7ed60c

## Problem
Requirement truth converged immediately but persisted score/risk cognition could lag during async recalc, showing stale low scores and Elevated risk after satisfied mutations.

## Fix
1. **Pending dominates** — `compliance_score_pending` → `score_status=calculating` even when a numeric snapshot exists
2. **Duplicate enqueue** — re-mark pending while worker job is active
3. **Portfolio honesty** — partial status + pending message when recalc in flight
4. **UI** — Updating… headline, suppress stale risk labels, cognition line during pending
5. **Read-path gap** — enqueue after stale authority refresh

## Classification
{classification['classification']}

## Tests
Backend: {'PASS' if be_ok else 'FAIL'}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    print(f"Audit pack written to {OUT}")
    return 0 if be_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
