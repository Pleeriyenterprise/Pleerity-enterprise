#!/usr/bin/env python3
"""
STAGING-CLOSURE-PROOF-RUN-01

Controlled staging proof: operational mutations via authoritative APIs, before/after measurement.
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
PROGRAMME = "STAGING-CLOSURE-PROOF-RUN-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

DEFAULT_CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
DEFAULT_SLUG = "6fd5ac4c_d35a58ae"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"

import os  # noqa: E402

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

OUT = ROOT / "docs" / "audit" / "staging_closure_proof_run_01"
ACTION_REASON = "STAGING-CLOSURE-PROOF-RUN-01 controlled operational progression proof"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def days_old(s: Optional[str]) -> Optional[float]:
    d = parse_dt(s)
    if not d:
        return None
    return (datetime.now(timezone.utc) - d).total_seconds() / 86400


def req(
    method: str,
    url: str,
    *,
    token: str,
    params: Optional[dict] = None,
    body: Optional[dict] = None,
    timeout: int = 120,
) -> Tuple[int, Any]:
    r = httpx.request(method, url, headers=h(token), params=params, json=body, timeout=timeout)
    ct = (r.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text
    return r.status_code, r.text


def login_client() -> str:
    r = httpx.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PW}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def login_admin() -> str:
    if not ADMIN_PW:
        raise RuntimeError("Admin password required for staging proof mutations")
    r = httpx.post(f"{API}/auth/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=120)
    r.raise_for_status()
    return r.json().get("access_token") or r.json().get("token")


def fleet_snapshot(client_tok: str) -> Dict[str, Any]:
    snap: Dict[str, Any] = {"captured_at": utc()}

    st, body = req("GET", f"{API}/client/maintenance/work-orders", token=client_tok, params={"limit": 200})
    wos = (body or {}).get("work_orders") or [] if st == 200 else []
    snap["jobs_no_contractor"] = sum(
        1
        for w in wos
        if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED") and not w.get("contractor_id")
    )
    snap["jobs_completed_unverified"] = sum(
        1 for w in wos if (w.get("status") or "").upper() == "COMPLETED" and not w.get("verified_at")
    )
    snap["jobs_verified"] = sum(1 for w in wos if (w.get("status") or "").upper() == "VERIFIED")

    st, body = req("GET", f"{API}/client/maintenance/risk-signals", token=client_tok, params={"limit": 500})
    signals = (body or {}).get("signals") or [] if st == 200 else []
    snap["risk_active"] = sum(1 for s in signals if (s.get("status") or "").lower() == "active")
    snap["risk_resolved_missing_ts"] = sum(
        1 for s in signals if (s.get("status") or "").lower() == "resolved" and not s.get("resolved_at")
    )

    st, body = req("GET", f"{API}/client/maintenance/issues", token=client_tok, params={"limit": 200})
    issues = (body or {}).get("issues") or [] if st == 200 else []
    snap["issues_stale_7d"] = sum(
        1
        for i in issues
        if (i.get("status") or "").lower() in ("triaged", "monitoring", "investigating")
        and (days_old(i.get("updated_at")) or 0) > 7
    )

    st, cc = req("GET", f"{API}/client/command-center", token=client_tok, params={"projection": "primary"}, timeout=90)
    if st == 200 and isinstance(cc, dict):
        ov = cc.get("operational_value_v1") or {}
        closure = ov.get("closure_conversion_v1") or {}
        scores = closure.get("closure_conversion_scores_v1") or {}
        conf = closure.get("landlord_decision_confidence_v1") or {}
        snap["fake_progress_chains"] = scores.get("fake_progress_chain_count")
        snap["likely_to_stall"] = scores.get("likely_to_stall_count")
        snap["decision_confidence"] = conf.get("decision_confidence_score")

    return snap


def select_proof_sample(client_tok: str, admin_tok: str) -> Dict[str, Any]:
    sample: Dict[str, Any] = {"selected_at": utc(), "entities": []}

    st, body = req("GET", f"{API}/client/maintenance/work-orders", token=client_tok, params={"limit": 200})
    wos = (body or {}).get("work_orders") or [] if st == 200 else []

    unassigned = [
        w
        for w in wos
        if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED")
        and not w.get("contractor_id")
        and (w.get("work_order_kind") or "MAINTENANCE").upper() != "COMPLIANCE"
    ]
    unassigned.sort(key=lambda w: -(days_old(w.get("updated_at") or w.get("created_at")) or 0))

    completed_unverified = [
        w
        for w in wos
        if (w.get("status") or "").upper() == "COMPLETED" and not w.get("verified_at")
    ]
    completed_unverified.sort(key=lambda w: -(days_old(w.get("completed_at")) or 0))

    st, ibody = req("GET", f"{API}/client/maintenance/issues", token=client_tok, params={"limit": 200})
    issues = (ibody or {}).get("issues") or [] if st == 200 else []
    stale = [
        i
        for i in issues
        if (i.get("status") or "").lower() in ("triaged", "monitoring", "investigating")
        and (days_old(i.get("updated_at")) or 0) > 7
    ]
    stale.sort(key=lambda i: -(days_old(i.get("updated_at")) or 0))

    st, rsbody = req("GET", f"{API}/client/maintenance/risk-signals", token=client_tok, params={"limit": 500})
    signals = (rsbody or {}).get("signals") or [] if st == 200 else []
    recurring = [
        s
        for s in signals
        if "recurring" in (s.get("risk_type") or "").lower() and (s.get("status") or "").lower() == "active"
    ]
    if not recurring:
        recurring = [s for s in signals if (s.get("status") or "").lower() == "active"][:3]

    likely_stall_wo = next(
        (
            w
            for w in wos
            if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED")
            and not w.get("contractor_id")
            and (days_old(w.get("updated_at")) or 0) > 7
        ),
        unassigned[0] if unassigned else None,
    )

    def entity_row(kind: str, doc: Dict[str, Any], extra: Optional[Dict] = None) -> Dict[str, Any]:
        row = {
            "kind": kind,
            "id": doc.get("work_order_id") or doc.get("issue_id") or doc.get("signal_id"),
            "status": doc.get("status"),
            "age_days": round(
                days_old(
                    doc.get("updated_at")
                    or doc.get("completed_at")
                    or doc.get("created_at")
                    or doc.get("generated_at")
                )
                or 0,
                1,
            ),
            "blockers": [],
        }
        if kind == "work_order" and not doc.get("contractor_id"):
            row["blockers"].append("contractor_deadlock")
        if kind == "work_order" and (doc.get("status") or "").upper() == "COMPLETED":
            row["blockers"].append("verification_backlog")
        if extra:
            row.update(extra)
        return row

    for w in unassigned[:3]:
        sample["entities"].append(entity_row("work_order_unassigned", w))
    for w in completed_unverified[:2]:
        sample["entities"].append(entity_row("work_order_completed_unverified", w))
    if stale:
        sample["entities"].append(entity_row("issue_stale", stale[0]))
    if likely_stall_wo:
        sample["entities"].append(entity_row("likely_to_stall", likely_stall_wo))
    if recurring:
        sample["entities"].append(
            entity_row(
                "recurring_risk",
                recurring[0],
                {"risk_type": recurring[0].get("risk_type"), "property_id": recurring[0].get("property_id")},
            )
        )

    sample["work_order_ids_assign"] = [w["work_order_id"] for w in unassigned[:3] if w.get("work_order_id")]
    sample["work_order_ids_verify"] = [w["work_order_id"] for w in completed_unverified[:2] if w.get("work_order_id")]
    sample["issue_id_stale"] = stale[0].get("issue_id") if stale else None
    sample["risk_signal_id_recurring"] = recurring[0].get("signal_id") if recurring else None
    sample["momentum_work_order_id"] = sample["work_order_ids_assign"][0] if sample["work_order_ids_assign"] else None

    return sample


def get_contractor_id(client_tok: str, work_order_id: str) -> Optional[str]:
    st, body = req(
        "GET",
        f"{API}/client/maintenance/work-orders/{work_order_id}/assignable-contractors",
        token=client_tok,
        params={"limit": 5},
    )
    if st != 200:
        return None
    contractors = (body or {}).get("contractors") or body if isinstance(body, list) else []
    if isinstance(body, dict):
        contractors = body.get("contractors") or body.get("items") or []
    for c in contractors:
        cid = c.get("contractor_id")
        if cid:
            return cid
    return None


def admin_patch_wo(admin_tok: str, wid: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    st, body = req("PATCH", f"{API}/admin/ops/work-orders/{wid}", token=admin_tok, body=patch)
    return {"status": st, "body": body, "work_order_id": wid, "patch": patch}


def client_patch_issue(client_tok: str, iid: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    st, body = req("PATCH", f"{API}/client/maintenance/issues/{iid}", token=client_tok, body=patch)
    return {"status": st, "body": body, "issue_id": iid, "patch": patch}


def execute_mutations(
    client_tok: str,
    admin_tok: str,
    sample: Dict[str, Any],
) -> Dict[str, Any]:
    mutations: List[Dict[str, Any]] = []
    contractor_id: Optional[str] = None
    momentum_wid = sample.get("momentum_work_order_id")

    if momentum_wid:
        contractor_id = get_contractor_id(client_tok, momentum_wid)
        if not contractor_id:
            st, rec = req("GET", f"{API}/admin/ops/work-orders/{momentum_wid}/recommend-contractors", token=admin_tok)
            if st == 200 and isinstance(rec, dict):
                recs = rec.get("recommendations") or rec.get("contractors") or []
                if recs:
                    contractor_id = recs[0].get("contractor_id")

    for wid in sample.get("work_order_ids_assign") or []:
        cid = contractor_id or get_contractor_id(client_tok, wid)
        if not cid:
            mutations.append({"phase": "assignment", "work_order_id": wid, "error": "no_assignable_contractor"})
            continue
        contractor_id = cid
        r = admin_patch_wo(
            admin_tok,
            wid,
            {
                "contractor_id": cid,
                "action_reason": ACTION_REASON,
            },
        )
        mutations.append({"phase": "assignment", **r})
        time.sleep(0.5)

    if momentum_wid and contractor_id:
        r = admin_patch_wo(
            admin_tok,
            momentum_wid,
            {"status": "IN_PROGRESS", "action_reason": ACTION_REASON},
        )
        mutations.append({"phase": "momentum_in_progress", **r})

    for wid in sample.get("work_order_ids_verify") or []:
        r = admin_patch_wo(
            admin_tok,
            wid,
            {"status": "VERIFIED", "action_reason": ACTION_REASON},
        )
        mutations.append({"phase": "verification", **r})
        time.sleep(0.5)

    iid = sample.get("issue_id_stale")
    if iid:
        r = client_patch_issue(client_tok, iid, {"status": "ready_for_work_order"})
        mutations.append({"phase": "stale_recovery", **r})

    sid = sample.get("risk_signal_id_recurring")
    if sid:
        r_issue: Dict[str, Any] = {}
        st, issue = req(
            "POST",
            f"{API}/client/maintenance/risk-signals/{sid}/create-issue",
            token=client_tok,
            body={},
        )
        r_issue = {"create_issue_status": st, "issue": issue}
        mutations.append({"phase": "risk_create_issue", **r_issue})
        if st in (200, 201) and isinstance(issue, dict) and issue.get("issue_id"):
            iid2 = issue["issue_id"]
            st2, wo = req("POST", f"{API}/client/maintenance/issues/{iid2}/create-work-order", token=client_tok)
            mutations.append({"phase": "risk_create_wo", "status": st2, "work_order": wo})
            if st2 in (200, 201) and isinstance(wo, dict) and wo.get("work_order_id"):
                wid2 = wo["work_order_id"]
                cid2 = contractor_id or get_contractor_id(client_tok, wid2)
                if cid2:
                    mutations.append(
                        {
                            "phase": "risk_assign",
                            **admin_patch_wo(
                                admin_tok,
                                wid2,
                                {"contractor_id": cid2, "action_reason": ACTION_REASON},
                            ),
                        }
                    )
                    mutations.append(
                        {
                            "phase": "risk_complete",
                            **admin_patch_wo(
                                admin_tok,
                                wid2,
                                {"status": "COMPLETED", "action_reason": ACTION_REASON},
                            ),
                        }
                    )
                    mutations.append(
                        {
                            "phase": "risk_verify",
                            **admin_patch_wo(
                                admin_tok,
                                wid2,
                                {"status": "VERIFIED", "action_reason": ACTION_REASON},
                            ),
                        }
                    )
                st3, resolved = req(
                    "PATCH",
                    f"{API}/client/maintenance/risk-signals/{sid}",
                    token=client_tok,
                    body={"status": "resolved"},
                )
                mutations.append({"phase": "risk_resolve", "status": st3, "body": resolved})

    return {"mutations": mutations, "contractor_id_used": contractor_id}


def verify_authority(client_tok: str, mutations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for m in mutations:
        if m.get("phase") == "assignment" and m.get("status") == 200:
            wid = m.get("work_order_id")
            st, wo = req("GET", f"{API}/client/maintenance/work-orders/{wid}", token=client_tok)
            if st == 200 and isinstance(wo, dict):
                checks.append(
                    {
                        "work_order_id": wid,
                        "has_contractor": bool(wo.get("contractor_id")),
                        "assigned_at": wo.get("assigned_at"),
                        "status": wo.get("status"),
                    }
                )
        if m.get("phase") == "verification" and m.get("status") == 200:
            wid = m.get("work_order_id")
            st, wo = req("GET", f"{API}/client/maintenance/work-orders/{wid}", token=client_tok)
            if st == 200 and isinstance(wo, dict):
                checks.append(
                    {
                        "work_order_id": wid,
                        "status": wo.get("status"),
                        "verified_at": wo.get("verified_at"),
                    }
                )
    return checks


def delta(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "jobs_no_contractor",
        "jobs_completed_unverified",
        "jobs_verified",
        "fake_progress_chains",
        "likely_to_stall",
        "decision_confidence",
        "issues_stale_7d",
        "risk_active",
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
    return {"exit_code": proc.returncode}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    write("programme.json", {"programme": PROGRAMME, "run_tag": RUN_TAG, "client_id": DEFAULT_CID})

    client_tok = login_client()
    admin_tok = login_admin()

    before = fleet_snapshot(client_tok)
    write("01_metrics_before.json", before)

    sample = select_proof_sample(client_tok, admin_tok)
    write("02_proof_sample.json", sample)

    mutation_report = execute_mutations(client_tok, admin_tok, sample)
    write("03_mutations.json", mutation_report)

    authority = verify_authority(client_tok, mutation_report.get("mutations") or [])
    write("04_authority_checks.json", authority)

    time.sleep(4)
    after = fleet_snapshot(client_tok)
    write("05_metrics_after.json", after)
    deltas = delta(before, after)
    write("06_metrics_delta.json", deltas)

    outcome = run_child("tmp_outcome_effectiveness_validation_01_execute.py")
    closure = run_child("tmp_closure_conversion_effectiveness_01_execute.py")
    backlog = run_child("tmp_backlog_reduction_runtime_01_execute.py")
    write("07_outcome_validation.json", outcome)
    write("08_closure_validation.json", closure)
    write("09_backlog_validation.json", backlog)

    oc = outcome.get("classification", "UNKNOWN")
    cc = closure.get("classification", "UNKNOWN")

    assignment_ok = sum(1 for m in mutation_report.get("mutations") or [] if m.get("phase") == "assignment" and m.get("status") == 200)
    verify_ok = sum(1 for m in mutation_report.get("mutations") or [] if m.get("phase") == "verification" and m.get("status") == 200)

    write(
        "10_classification.json",
        {
            "programme": PROGRAMME,
            "operational_value_classification": oc,
            "closure_conversion_classification": cc,
            "assignment_mutations_ok": assignment_ok,
            "verification_mutations_ok": verify_ok,
            "deltas": deltas,
            "verified_at_utc": utc(),
        },
    )

    lines = [
        f"# {PROGRAMME}",
        "",
        f"**Outcome:** `{oc}` | **Closure:** `{cc}`",
        "",
        "## Deltas",
        "",
        json.dumps(deltas, indent=2),
        "",
        "## Mutations summary",
        "",
        f"Assignments OK: {assignment_ok}, Verifications OK: {verify_ok}",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "programme": PROGRAMME,
                "operational_value_classification": oc,
                "closure_conversion_classification": cc,
                "deltas": deltas,
                "assignment_ok": assignment_ok,
                "verify_ok": verify_ok,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
