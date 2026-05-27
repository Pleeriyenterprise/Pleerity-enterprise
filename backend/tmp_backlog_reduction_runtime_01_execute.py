#!/usr/bin/env python3
"""
BACKLOG-REDUCTION-RUNTIME-01

Measures real operational backlog reduction after authority backfill + throughput surfaces.
Phases: P0-D backfill (dry-run/apply), before/after metrics, outcome + closure re-validation.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
PROGRAMME = "BACKLOG-REDUCTION-RUNTIME-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

DEFAULT_CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
DEFAULT_SLUG = "6fd5ac4c_d35a58ae"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
CLIENT_EMAIL = os.environ.get("OPS_VERIFY_EMAIL", "nancy@yopmail.com")
PW_PATH = ROOT / f"docs/audit/ops_verify_01_{DEFAULT_SLUG}/.ops_verify_temp_pw.txt"
CLIENT_PW = os.environ.get("OPS_VERIFY_PASSWORD") or (
    PW_PATH.read_text(encoding="utf-8").strip() if PW_PATH.is_file() else "OpsVerify01!StagingWalk"
)
ADMIN_EMAIL = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
ADMIN_PW_PATH = ROOT / f"docs/audit/ops_verify_01_{DEFAULT_SLUG}/.ops_verify_admin_pw.txt"
ADMIN_PW = os.environ.get("OPS_VERIFY_ADMIN_PASSWORD") or (
    ADMIN_PW_PATH.read_text(encoding="utf-8").strip() if ADMIN_PW_PATH.is_file() else None
)
REASON = os.environ.get(
    "BACKLOG_REDUCTION_REASON",
    "BACKLOG-REDUCTION-RUNTIME-01 staging authority backfill and throughput validation",
)
SKIP_APPLY = os.environ.get("BACKLOG_SKIP_APPLY", "").strip().lower() in ("1", "true", "yes")

OUT = ROOT / "docs" / "audit" / "backlog_reduction_runtime_01"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def h(token: str, conf: str = "") -> dict:
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if conf:
        hdr["X-Admin-Confirmation-Token"] = conf
    return hdr


def login_client() -> str:
    r = httpx.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PW}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def login_admin() -> Optional[str]:
    if not ADMIN_PW:
        return None
    r = httpx.post(f"{API}/auth/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=120)
    if r.status_code != 200:
        return None
    return r.json().get("access_token") or r.json().get("token")


def confirmation_token(admin: str, action: str, resource: str) -> str:
    r = httpx.post(
        f"{API}/admin/governance/confirmation-token",
        headers=h(admin),
        json={"action_id": action, "reason": REASON, "resource_key": resource},
        timeout=90,
    )
    return (r.json() or {}).get("token", "") if r.status_code == 200 else ""


def fleet_metrics(client_token: str) -> Dict[str, Any]:
    ch = h(client_token)
    snap: Dict[str, Any] = {"captured_at": utc()}

    st, body = _get(f"{API}/client/maintenance/risk-signals", ch, params={"limit": 500})
    signals = (body or {}).get("signals") or [] if st == 200 else []
    snap["risk_resolved_missing_ts"] = sum(
        1 for s in signals if (s.get("status") or "").lower() == "resolved" and not s.get("resolved_at")
    )

    st, body = _get(f"{API}/client/maintenance/work-orders", ch, params={"limit": 200})
    wos = (body or {}).get("work_orders") or [] if st == 200 else []
    snap["jobs_no_contractor"] = sum(
        1
        for w in wos
        if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED") and not w.get("contractor_id")
    )
    snap["jobs_completed_unverified"] = sum(
        1 for w in wos if (w.get("status") or "").upper() == "COMPLETED" and not w.get("verified_at")
    )

    st, cc = _get(f"{API}/client/command-center", ch, params={"projection": "primary"}, timeout=90)
    if st == 200 and isinstance(cc, dict):
        ov = cc.get("operational_value_v1") or {}
        closure = ov.get("closure_conversion_v1") or {}
        backlog = ov.get("backlog_reduction_v1") or {}
        scores = closure.get("closure_conversion_scores_v1") or {}
        conf = closure.get("landlord_decision_confidence_v1") or {}
        momentum = backlog.get("operational_momentum_validation_v1") or {}
        snap["fake_progress_chains"] = scores.get("fake_progress_chain_count")
        snap["likely_to_stall"] = scores.get("likely_to_stall_count")
        snap["decision_confidence"] = conf.get("decision_confidence_score")
        snap["backlog_available"] = backlog.get("available", True) and not backlog.get("error")
        snap["unassigned_critical"] = (backlog.get("contractor_throughput_v1") or {}).get("critical_unassigned_count")
        snap["verification_critical"] = (backlog.get("verification_throughput_execution_v1") or {}).get(
            "critical_verification_count"
        )
        snap["simulation_coverage"] = (backlog.get("staging_simulation_coverage_v1") or {}).get("coverage_count")
    return snap


def _get(url: str, headers: dict, *, params: Optional[dict] = None, timeout: int = 120) -> Tuple[int, Any]:
    r = httpx.get(url, headers=headers, params=params, timeout=timeout)
    if "application/json" in (r.headers.get("content-type") or "").lower():
        return r.status_code, r.json()
    return r.status_code, r.text


def run_backfill_via_api(admin: str, *, apply: bool) -> Dict[str, Any]:
    action = "authority_backfill_p0_apply" if apply else "authority_backfill_p0_dry_run"
    tok = confirmation_token(admin, action, DEFAULT_CID)
    r = httpx.post(
        f"{API}/admin/ops/authority-backfill-p0",
        headers=h(admin, tok),
        json={"reason": REASON, "client_id": DEFAULT_CID, "apply": apply},
        timeout=300,
    )
    if r.status_code == 200:
        return r.json()
    return {"error": True, "status": r.status_code, "detail": r.text[:500]}


def run_backfill_local(*, apply: bool) -> Dict[str, Any]:
    cmd = [sys.executable, str(ROOT / "scripts" / "authority_backfill_p0.py")]
    if apply:
        cmd.append("--apply")
    cmd.extend(["--client-id", DEFAULT_CID, "--out", str(OUT / ("backfill_apply.json" if apply else "backfill_dry_run.json"))])
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if proc.returncode != 0:
        return {"error": True, "stderr": (proc.stderr or proc.stdout)[:500]}
    try:
        return json.loads(proc.stdout)
    except Exception:
        out_path = OUT / ("backfill_apply.json" if apply else "backfill_dry_run.json")
        if out_path.is_file():
            return json.loads(out_path.read_text(encoding="utf-8"))
        return {"error": True, "stdout": proc.stdout[:500]}


def summarize_backfill(report: Dict[str, Any]) -> Dict[str, Any]:
    totals = {
        "repaired_resolved_at": 0,
        "repaired_acknowledged_at": 0,
        "repaired_closed_at": 0,
        "repaired_verified_at": 0,
        "recoverable": 0,
        "applied": 0,
        "non_recoverable": 0,
        "ambiguous": 0,
    }
    for sec in report.get("sections") or []:
        coll = sec.get("collection") or ""
        totals["recoverable"] += sec.get("recoverable") or 0
        totals["applied"] += sec.get("applied") or 0
        totals["non_recoverable"] += sec.get("non_recoverable") or 0
        totals["ambiguous"] += sec.get("ambiguous") or 0
        if coll == "risk_signals":
            totals["repaired_resolved_at"] += sec.get("recoverable") or 0
            totals["repaired_acknowledged_at"] += sec.get("ack_recoverable") or 0
        elif coll == "maintenance_issues":
            totals["repaired_closed_at"] += sec.get("recoverable") or 0
        elif coll == "work_orders":
            totals["repaired_verified_at"] += sec.get("recoverable") or 0
    return totals


def delta(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "risk_resolved_missing_ts",
        "jobs_no_contractor",
        "jobs_completed_unverified",
        "fake_progress_chains",
        "likely_to_stall",
        "decision_confidence",
    ]
    d: Dict[str, Any] = {}
    for k in keys:
        if k in before and k in after and before[k] is not None and after[k] is not None:
            if isinstance(before[k], (int, float)) and isinstance(after[k], (int, float)):
                d[k] = round(float(after[k]) - float(before[k]), 2)
    return d


def run_child(script: str) -> Dict[str, Any]:
    proc = subprocess.run([sys.executable, str(ROOT / script)], cwd=str(ROOT), capture_output=True, text=True)
    for line in reversed((proc.stdout or "").strip().split("\n")):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"exit_code": proc.returncode, "stdout_tail": (proc.stdout or "")[-400:]}


def classify_programme(
    before: Dict[str, Any],
    after: Dict[str, Any],
    deltas: Dict[str, Any],
    outcome: Dict[str, Any],
    closure: Dict[str, Any],
) -> Tuple[str, str, Dict[str, Any]]:
    oc = outcome.get("classification") or "OPERATIONAL_VALUE_FAILURE"
    cc = closure.get("classification") or "STALLED_OPERATIONAL_SYSTEM"
    fp_delta = deltas.get("fake_progress_chains")
    ts_delta = deltas.get("risk_resolved_missing_ts")
    detail = {
        "outcome_classification": oc,
        "closure_classification": cc,
        "deltas": deltas,
        "fake_progress_reduced": fp_delta is not None and fp_delta < 0,
        "resolved_ts_reduced": ts_delta is not None and ts_delta < 0,
    }
    return oc, cc, detail


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    write("programme.json", {"programme": PROGRAMME, "run_tag": RUN_TAG, "client_id": DEFAULT_CID, "api": API})

    client_token = login_client()
    before = fleet_metrics(client_token)
    write("01_metrics_before.json", before)

    admin = login_admin()
    dry_report: Dict[str, Any] = {}
    apply_report: Dict[str, Any] = {}

    if admin:
        dry_report = run_backfill_via_api(admin, apply=False)
        write("02_backfill_dry_run.json", dry_report)
        if not SKIP_APPLY:
            apply_report = run_backfill_via_api(admin, apply=True)
            write("03_backfill_apply.json", apply_report)
    else:
        dry_report = run_backfill_local(apply=False)
        write("02_backfill_dry_run.json", dry_report)
        if not SKIP_APPLY and os.environ.get("MONGO_URL"):
            apply_report = run_backfill_local(apply=True)
            write("03_backfill_apply.json", apply_report)
        else:
            write("03_backfill_apply.json", {"skipped": True, "reason": "no admin login or MONGO_URL"})

    write("02_backfill_summary_dry.json", summarize_backfill(dry_report))
    if apply_report and not apply_report.get("skipped"):
        write("03_backfill_summary_apply.json", summarize_backfill(apply_report))

    time.sleep(3)
    after = fleet_metrics(client_token)
    write("04_metrics_after.json", after)
    deltas = delta(before, after)
    write("05_metrics_delta.json", deltas)

    outcome = run_child("tmp_outcome_effectiveness_validation_01_execute.py")
    closure = run_child("tmp_closure_conversion_effectiveness_01_execute.py")
    write("06_outcome_validation.json", outcome)
    write("07_closure_validation.json", closure)

    oc, cc, detail = classify_programme(before, after, deltas, outcome, closure)
    write(
        "08_classification.json",
        {
            "programme": PROGRAMME,
            "operational_value_classification": oc,
            "closure_conversion_classification": cc,
            "detail": detail,
            "verified_at_utc": utc(),
        },
    )

    lines = [
        f"# {PROGRAMME}",
        "",
        f"**Operational value:** `{oc}`",
        f"**Closure conversion:** `{cc}`",
        "",
        "## Before / after",
        "",
        json.dumps({"before": before, "after": after, "delta": deltas}, indent=2),
        "",
        "## Backfill apply summary",
        "",
        json.dumps(summarize_backfill(apply_report) if apply_report else {}, indent=2),
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "programme": PROGRAMME,
                "operational_value_classification": oc,
                "closure_conversion_classification": cc,
                "delta": deltas,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
