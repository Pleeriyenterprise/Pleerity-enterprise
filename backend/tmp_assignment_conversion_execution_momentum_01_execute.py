#!/usr/bin/env python3
"""
ASSIGNMENT-CONVERSION-AND-EXECUTION-MOMENTUM-01

Coordination trace + live assignment conversion experiment on staging.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
PROGRAMME = "ASSIGNMENT-CONVERSION-AND-EXECUTION-MOMENTUM-01"
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
SKIP_LIVE = os.environ.get("MOMENTUM_SKIP_LIVE", "").strip().lower() in ("1", "true", "yes")

OUT = ROOT / "docs" / "audit" / "assignment_conversion_execution_momentum_01"
EXPERIMENT_CAP = int(os.environ.get("MOMENTUM_EXPERIMENT_CAP", "5"))


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


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


def momentum_snapshot(client_tok: str) -> Dict[str, Any]:
    snap: Dict[str, Any] = {"captured_at": utc()}
    r = httpx.get(
        f"{API}/client/command-center",
        headers=h(client_tok),
        params={"projection": "primary"},
        timeout=300,
    )
    if r.status_code != 200:
        snap["error"] = f"command_center_{r.status_code}"
        return snap

    ov = r.json().get("operational_value_v1") or {}
    am = ov.get("assignment_execution_momentum_v1") or {}
    ec = ov.get("execution_capacity_v1") or {}
    closure = ov.get("closure_conversion_v1") or {}

    snap["momentum_available"] = am.get("available", True) and not am.get("error")
    trace = am.get("assignment_conversion_trace_v1") or {}
    kpis = am.get("operational_momentum_kpis_v1") or {}
    snap["eligible_but_unassigned"] = trace.get("eligible_but_unassigned_count")
    snap["coordination_taxonomy"] = trace.get("coordination_failure_taxonomy")
    snap["dominant_coordination_failure"] = trace.get("dominant_failure")
    snap["execution_momentum_score"] = kpis.get("execution_momentum_score")
    snap["follow_through_rate"] = kpis.get("operational_follow_through_rate")
    snap["stalled_momentum_ratio"] = (am.get("execution_momentum_engine_v1") or {}).get("stalled_momentum_ratio")
    snap["decision_confidence"] = (closure.get("landlord_decision_confidence_v1") or {}).get("decision_confidence_score")
    snap["coordination_nudges"] = (am.get("coordination_nudges_v1") or {}).get("nudge_count")
    snap["urgent_coordination_actions"] = sum(
        1
        for u in (r.json().get("urgent_actions") or [])
        if ((u.get("metadata") or {}).get("coordination_momentum_action"))
    )

    w = httpx.get(f"{API}/client/maintenance/work-orders", headers=h(client_tok), params={"limit": 200}, timeout=120)
    if w.status_code == 200:
        wos = (w.json().get("work_orders") or [])
        snap["jobs_no_contractor"] = sum(
            1
            for wo in wos
            if (wo.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED") and not wo.get("contractor_id")
        )

    snap["open_unassigned"] = (ec.get("assignment_conversion_v1") or {}).get("open_unassigned_count")
    return snap


def run_live_experiment(client_tok: str, admin_tok: Optional[str]) -> Dict[str, Any]:
    """Phase 7 — assign via confirm-alternate where assignable contractors exist."""
    if SKIP_LIVE:
        return {"skipped": True, "reason": "MOMENTUM_SKIP_LIVE=1"}

    experiment: Dict[str, Any] = {"mutations": [], "assigned_ok": 0}
    st, body = _get(f"{API}/client/maintenance/work-orders", client_tok, params={"limit": 200})
    wos = (body or {}).get("work_orders") or [] if st == 200 else []
    candidates = [
        w
        for w in wos
        if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED")
        and not w.get("contractor_id")
        and (w.get("work_order_kind") or "MAINTENANCE").upper() != "COMPLIANCE"
    ]
    candidates.sort(key=lambda w: -(w.get("updated_at") or w.get("created_at") or ""))

    assigned = 0
    for w in candidates:
        if assigned >= EXPERIMENT_CAP:
            break
        wid = w.get("work_order_id")
        if not wid:
            continue
        st_a, assignable = _get(
            f"{API}/client/maintenance/work-orders/{wid}/assignable-contractors",
            client_tok,
            params={"limit": 5},
        )
        contractors = []
        if st_a == 200 and isinstance(assignable, dict):
            contractors = assignable.get("contractors") or []
        if not contractors:
            experiment["mutations"].append({"work_order_id": wid, "skipped": "no_assignable_contractor"})
            continue
        cid = contractors[0].get("contractor_id")
        if not cid:
            continue

        # Client-authoritative: confirm-alternate (governed, no silent auto-assign)
        st_c, res = _post(
            f"{API}/client/maintenance/work-orders/{wid}/contractor-routing/confirm-alternate",
            client_tok,
            {"contractor_id": cid},
        )
        row = {"work_order_id": wid, "contractor_id": cid, "confirm_alternate_status": st_c}
        if st_c == 200:
            assigned += 1
            row["assigned_at"] = (res or {}).get("assigned_at") if isinstance(res, dict) else True
        else:
            row["detail"] = str(res)[:300]
            if admin_tok and st_c >= 400:
                st_ad, res_ad = _patch_admin(
                    admin_tok,
                    wid,
                    {"contractor_id": cid, "action_reason": f"{PROGRAMME} live coordination experiment"},
                )
                row["admin_fallback_status"] = st_ad
                if st_ad == 200:
                    assigned += 1
        experiment["mutations"].append(row)
        time.sleep(0.6)

    experiment["assigned_ok"] = assigned
    return experiment


def _get(url: str, token: str, *, params: Optional[dict] = None) -> Tuple[int, Any]:
    r = httpx.get(url, headers=h(token), params=params, timeout=120)
    if "application/json" in (r.headers.get("content-type") or "").lower():
        return r.status_code, r.json()
    return r.status_code, r.text


def _post(url: str, token: str, body: dict) -> Tuple[int, Any]:
    r = httpx.post(url, headers=h(token), json=body, timeout=120)
    if "application/json" in (r.headers.get("content-type") or "").lower():
        return r.status_code, r.json()
    return r.status_code, r.text


def _patch_admin(token: str, wid: str, body: dict) -> Tuple[int, Any]:
    r = httpx.patch(f"{API}/admin/ops/work-orders/{wid}", headers=h(token), json=body, timeout=120)
    if "application/json" in (r.headers.get("content-type") or "").lower():
        return r.status_code, r.json()
    return r.status_code, r.text


def delta(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "eligible_but_unassigned",
        "jobs_no_contractor",
        "execution_momentum_score",
        "follow_through_rate",
        "decision_confidence",
        "stalled_momentum_ratio",
    ]
    d: Dict[str, Any] = {}
    for k in keys:
        if k in before and k in after and before[k] is not None and after[k] is not None:
            if isinstance(before[k], (int, float)) and isinstance(after[k], (int, float)):
                d[k] = round(float(after[k]) - float(before[k]), 3)
    return d


def classify(snap: Dict[str, Any], deltas: Dict[str, Any], assigned_ok: int) -> Tuple[str, str]:
    if not snap.get("momentum_available"):
        return "STALLED_OPERATIONAL_SYSTEM", "OPERATIONAL_VALUE_FAILURE", {}

    eligible = snap.get("eligible_but_unassigned") or 0
    conf = snap.get("execution_momentum_score") or 0
    ft = snap.get("follow_through_rate") or 0

    if assigned_ok >= 3 and (deltas.get("eligible_but_unassigned") or 0) < 0:
        exec_c = "VERIFIED_EXECUTION_RELIABILITY"
    elif snap.get("momentum_available") and snap.get("coordination_taxonomy"):
        exec_c = "PARTIAL_EXECUTION_RELIABILITY"
    elif eligible >= 15:
        exec_c = "EXECUTION_NETWORK_FAILURE_RISK"
    else:
        exec_c = "PARTIAL_EXECUTION_RELIABILITY"

    if exec_c == "VERIFIED_EXECUTION_RELIABILITY":
        ov = "VERIFIED_OPERATIONAL_VALUE"
    elif exec_c == "PARTIAL_EXECUTION_RELIABILITY" and conf >= 0.5:
        ov = "PARTIAL_OPERATIONAL_VALUE"
    elif exec_c == "EXECUTION_NETWORK_FAILURE_RISK":
        ov = "EXECUTION_CAPACITY_RISK"
    else:
        ov = "PARTIAL_OPERATIONAL_VALUE"

    return exec_c, ov, {"assigned_ok": assigned_ok, "deltas": deltas}


def run_child(script: str) -> Dict[str, Any]:
    proc = subprocess.run([sys.executable, str(ROOT / script)], cwd=str(ROOT), capture_output=True, text=True)
    for line in reversed((proc.stdout or "").strip().split("\n")):
        if line.strip().startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"exit_code": proc.returncode}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    write("programme.json", {"programme": PROGRAMME, "run_tag": RUN_TAG, "experiment_cap": EXPERIMENT_CAP})

    client_tok = login_client()
    admin_tok = login_admin()

    before = momentum_snapshot(client_tok)
    write("01_metrics_before.json", before)

    experiment = run_live_experiment(client_tok, admin_tok)
    write("02_live_experiment.json", experiment)

    time.sleep(5)
    after = momentum_snapshot(client_tok)
    write("03_metrics_after.json", after)
    deltas = delta(before, after)
    write("04_metrics_delta.json", deltas)

    exec_c, ov_c, detail = classify(before, deltas, experiment.get("assigned_ok") or 0)
    write(
        "05_classification.json",
        {
            "programme": PROGRAMME,
            "execution_reliability_classification": exec_c,
            "operational_value_classification": ov_c,
            "detail": detail,
            "verified_at_utc": utc(),
        },
    )

    validations = {
        "execution_capacity": run_child("tmp_execution_capacity_network_reliability_01_execute.py"),
        "closure": run_child("tmp_closure_conversion_effectiveness_01_execute.py"),
    }
    write("06_child_validations.json", validations)

    print(
        json.dumps(
            {
                "programme": PROGRAMME,
                "execution_reliability_classification": exec_c,
                "operational_value_classification": ov_c,
                "assigned_ok": experiment.get("assigned_ok"),
                "deltas": deltas,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
