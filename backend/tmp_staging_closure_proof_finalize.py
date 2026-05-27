#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/staging_closure_proof_run_01"
API = "https://pleerity-enterprise.onrender.com/api"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_PW = (ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt").read_text().strip()

cr = httpx.post(f"{API}/auth/login", json={"email": "nancy@yopmail.com", "password": CLIENT_PW}, timeout=120)
ct = cr.json()["access_token"]
h = {"Authorization": f"Bearer {ct}"}


def snap():
    s = {}
    w = httpx.get(f"{API}/client/maintenance/work-orders", headers=h, params={"limit": 200}, timeout=120)
    wos = (w.json().get("work_orders") or []) if w.status_code == 200 else []
    s["jobs_no_contractor"] = sum(
        1
        for wo in wos
        if (wo.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED") and not wo.get("contractor_id")
    )
    s["jobs_completed_unverified"] = sum(
        1 for wo in wos if (wo.get("status") or "").upper() == "COMPLETED" and not wo.get("verified_at")
    )
    s["jobs_verified"] = sum(1 for wo in wos if (wo.get("status") or "").upper() == "VERIFIED")
    cc = httpx.get(f"{API}/client/command-center", headers=h, params={"projection": "primary"}, timeout=90)
    if cc.status_code == 200:
        ov = cc.json().get("operational_value_v1") or {}
        cl = ov.get("closure_conversion_v1") or {}
        s["fake_progress_chains"] = (cl.get("closure_conversion_scores_v1") or {}).get("fake_progress_chain_count")
        s["likely_to_stall"] = (cl.get("closure_conversion_scores_v1") or {}).get("likely_to_stall_count")
        s["decision_confidence"] = (cl.get("landlord_decision_confidence_v1") or {}).get("decision_confidence_score")
    rs = httpx.get(f"{API}/client/maintenance/risk-signals", headers=h, params={"limit": 500}, timeout=120)
    sigs = (rs.json().get("signals") or []) if rs.status_code == 200 else []
    s["risk_active"] = sum(1 for x in sigs if (x.get("status") or "").lower() == "active")
    return s


before = json.loads((OUT / "01_metrics_before.json").read_text())
after = snap()
delta = {
    k: round(after.get(k, 0) - before.get(k, 0), 2)
    for k in after
    if k in before and isinstance(after.get(k), (int, float))
}
(OUT / "05_metrics_after.json").write_text(json.dumps(after, indent=2) + "\n")
(OUT / "06_metrics_delta.json").write_text(json.dumps(delta, indent=2) + "\n")

for script, outn in [
    ("tmp_outcome_effectiveness_validation_01_execute.py", "07_outcome_validation.json"),
    ("tmp_closure_conversion_effectiveness_01_execute.py", "08_closure_validation.json"),
    ("tmp_backlog_reduction_runtime_01_execute.py", "09_backlog_validation.json"),
]:
    p = subprocess.run([sys.executable, str(ROOT / script)], cwd=str(ROOT), capture_output=True, text=True)
    for line in reversed((p.stdout or "").strip().split("\n")):
        if line.strip().startswith("{"):
            (OUT / outn).write_text(line.strip() + "\n")
            break

oc = json.loads((OUT / "07_outcome_validation.json").read_text())
cc = json.loads((OUT / "08_closure_validation.json").read_text())
classif = {
    "programme": "STAGING-CLOSURE-PROOF-RUN-01",
    "operational_value_classification": oc.get("classification"),
    "closure_conversion_classification": cc.get("classification"),
    "deltas": delta,
}
(OUT / "10_classification.json").write_text(json.dumps(classif, indent=2) + "\n")
print(json.dumps(classif, indent=2))
