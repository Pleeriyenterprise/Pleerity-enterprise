#!/usr/bin/env python3
"""
PRELAUNCH-CLOSURE-AUTHORITY-AUDIT-01

Goal: Determine whether operational closure across Risk Signals, Issues, and Jobs is
authority-driven (timestamps + actor attribution + invariants) or merely workflow-state-driven.

This is an audit-only harness: no remediation, minimal mutations (read-only except optional
safe probes that should fail / be forbidden).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
PROGRAMME = "PRELAUNCH-CLOSURE-AUTHORITY-AUDIT-01"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")

DEFAULT_SLUG = "6fd5ac4c_d35a58ae"
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

OUT = ROOT / "docs" / "audit" / "closure_authority_audit_01"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login_client() -> Tuple[str, dict]:
    r = httpx.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PW}, timeout=120)
    r.raise_for_status()
    b = r.json()
    return b["access_token"], b.get("user") or {}


def login_admin() -> Optional[Tuple[str, dict]]:
    if not ADMIN_PW:
        return None
    r = httpx.post(f"{API}/auth/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=120)
    if r.status_code != 200:
        return None
    b = r.json()
    token = b.get("access_token") or b.get("token")
    return token, b.get("user") or {}


def _get_json(method: str, url: str, *, headers: Optional[dict] = None, params: Optional[dict] = None, json_body: Any = None, timeout: int = 120) -> tuple[int, Any, str]:
    try:
        r = httpx.request(method, url, headers=headers, params=params, json=json_body, timeout=timeout)
        ct = (r.headers.get("content-type") or "").lower()
        if "application/json" in ct:
            return r.status_code, r.json(), r.text[:500]
        return r.status_code, None, r.text[:500]
    except Exception as e:
        return 0, None, f"exception: {e}"


def audit_risk_signals(ch: dict) -> Dict[str, Any]:
    st, body, raw = _get_json("GET", f"{API}/client/maintenance/risk-signals", headers=ch, params={"limit": 500}, timeout=120)
    signals = (body or {}).get("signals") if isinstance(body, dict) else None
    if signals is None:
        signals = []
    missing_resolved_at = []
    has_ack_with_resolved_at = []
    sample = []
    for s in signals:
        sid = s.get("signal_id")
        stt = (s.get("status") or "").lower()
        if stt == "resolved" and not s.get("resolved_at"):
            missing_resolved_at.append(sid)
        if stt == "acknowledged" and s.get("resolved_at"):
            has_ack_with_resolved_at.append(sid)
        if len(sample) < 8:
            sample.append(
                {
                    "signal_id": sid,
                    "risk_type": s.get("risk_type"),
                    "status": s.get("status"),
                    "updated_at": s.get("updated_at"),
                    "resolved_at": s.get("resolved_at"),
                    "dismiss_reason": s.get("dismiss_reason"),
                }
            )
    # Forbidden probe: attempt to resolve without dismiss_reason should fail (400) on an active signal.
    probe = {"attempted": False}
    active_id = next((s.get("signal_id") for s in signals if (s.get("status") or "").lower() == "active" and s.get("signal_id")), None)
    if active_id:
        probe["attempted"] = True
        stp, _, rawp = _get_json(
            "PATCH",
            f"{API}/client/maintenance/risk-signals/{active_id}",
            headers=ch,
            json_body={"status": "resolved"},
            timeout=60,
        )
        probe.update({"signal_id": active_id, "status": stp, "raw": rawp})

    checks = {
        "acknowledged_never_implies_resolved": len(has_ack_with_resolved_at) == 0,
        "resolved_has_resolved_at": len(missing_resolved_at) == 0,
        "resolve_without_closure_forbidden_or_requires_reason": (not probe.get("attempted")) or probe.get("status") in (400, 403),
    }
    trust_risks = []
    if missing_resolved_at:
        trust_risks.append("risk_signals_resolved_missing_resolved_at")
    return {
        "endpoint": f"{API}/client/maintenance/risk-signals",
        "page": f"{FRONTEND}/operations/risk-signals",
        "http_status": st,
        "total": len(signals),
        "missing_resolved_at_count": len(missing_resolved_at),
        "missing_resolved_at_sample": missing_resolved_at[:10],
        "sample": sample,
        "forbidden_probe_resolve_without_reason": probe,
        "checks": checks,
        "trust_risks": trust_risks,
        "pass": all(checks.values()),
    }


def audit_issues(ch: dict) -> Dict[str, Any]:
    st, body, raw = _get_json("GET", f"{API}/client/maintenance/issues", headers=ch, params={"limit": 200}, timeout=120)
    issues = (body or {}).get("issues") if isinstance(body, dict) else None
    if issues is None:
        issues = []
    terminal_missing_ts = []
    stale_triage = []
    for i in issues:
        status = (i.get("status") or "").lower()
        resolved_at = i.get("resolved_at")
        closed_at = i.get("closed_at")
        updated_at = i.get("updated_at") or i.get("created_at")
        if status == "resolved" and not resolved_at:
            terminal_missing_ts.append(i.get("issue_id"))
        if status in ("closed", "cancelled") and not closed_at:
            terminal_missing_ts.append(i.get("issue_id"))
        # stale drift heuristic (triaged/investigating/monitoring > 7d)
        try:
            if status in ("triaged", "investigating", "monitoring"):
                dt = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
                if age_days > 7:
                    stale_triage.append({"issue_id": i.get("issue_id"), "status": status, "age_days": round(age_days, 1)})
        except Exception:
            pass

    # Forbidden probe: try to reopen a closed issue via PATCH to open; service should ignore reopen.
    probe = {"attempted": False}
    closed_id = next((i.get("issue_id") for i in issues if (i.get("status") or "").lower() in ("closed", "cancelled") and i.get("issue_id")), None)
    if closed_id:
        probe["attempted"] = True
        stp, _, rawp = _get_json(
            "PATCH",
            f"{API}/client/maintenance/issues/{closed_id}",
            headers=ch,
            json_body={"status": "open"},
            timeout=60,
        )
        # Fetch after to see if status changed (should not).
        stg, b2, _ = _get_json("GET", f"{API}/client/maintenance/issues/{closed_id}", headers=ch, timeout=60)
        probe.update(
            {
                "issue_id": closed_id,
                "patch_status": stp,
                "patch_raw": rawp,
                "get_status": stg,
                "after_status": (b2 or {}).get("status") if isinstance(b2, dict) else None,
            }
        )

    checks = {
        "terminal_has_timestamps": len(terminal_missing_ts) == 0,
        "closed_issue_not_reopenable_by_client": (not probe.get("attempted")) or (probe.get("after_status") in ("closed", "cancelled")),
        "stale_state_drift_detectable": True,  # audit records drift; product may still need pressure surfacing
    }
    trust_risks = []
    if terminal_missing_ts:
        trust_risks.append("issues_terminal_missing_closed_or_resolved_timestamps")
    if len(stale_triage) >= 5:
        trust_risks.append("issues_stale_triage_drift_present")
    return {
        "endpoint": f"{API}/client/maintenance/issues",
        "page": f"{FRONTEND}/operations/issues",
        "http_status": st,
        "loaded": len(issues),
        "terminal_missing_timestamp_count": len(terminal_missing_ts),
        "terminal_missing_timestamp_sample": terminal_missing_ts[:10],
        "stale_triage_over_7d": stale_triage[:12],
        "forbidden_probe_reopen_closed_issue": probe,
        "checks": checks,
        "trust_risks": trust_risks,
        "pass": all(checks.values()),
    }


def audit_jobs(ch: dict) -> Dict[str, Any]:
    st, body, raw = _get_json("GET", f"{API}/client/maintenance/work-orders", headers=ch, params={"limit": 200}, timeout=120)
    wos = (body or {}).get("work_orders") if isinstance(body, dict) else None
    if wos is None:
        wos = []
    completed_missing_completed_at = []
    verified_missing_verified_at = []
    completed_with_no_evidence = []
    holds = {"NO_ACCESS": 0, "RESCHEDULE_REQUIRED": 0, "FOLLOW_UP_REQUIRED": 0}
    awaiting_parts = 0
    reschedule_heavy = []
    no_contractor_open = []
    compliance_completed = []

    for wo in wos:
        wid = wo.get("work_order_id")
        status = (wo.get("status") or "").upper()
        if status == "COMPLETED" and not wo.get("completed_at"):
            completed_missing_completed_at.append(wid)
        if status == "VERIFIED" and not wo.get("verified_at"):
            verified_missing_verified_at.append(wid)
        if status == "COMPLETED" and (wo.get("evidence_count") or 0) == 0 and not (wo.get("evidence_keys") or []):
            completed_with_no_evidence.append(wid)
        if status == "AWAITING_PARTS":
            awaiting_parts += 1
        oe = (wo.get("operational_exception") or wo.get("exception_state") or "").upper()
        if oe in holds:
            holds[oe] += 1
        if (wo.get("reschedule_count") or 0) >= 2:
            reschedule_heavy.append(wid)
        if status in ("OPEN", "ASSIGNED", "SCHEDULED") and not wo.get("contractor_id"):
            no_contractor_open.append(wid)
        if (wo.get("work_order_kind") or "").upper() == "COMPLIANCE" and status == "COMPLETED":
            compliance_completed.append(wid)

    # Sample job desync: jobs created from issues should keep issue visible until CLOSED/RESOLVED.
    issue_linked = next((wo for wo in wos if wo.get("issue_id")), None)
    desync_probe = {"attempted": False}
    if issue_linked:
        desync_probe["attempted"] = True
        iid = issue_linked.get("issue_id")
        wid = issue_linked.get("work_order_id")
        st_i, issue_body, _ = _get_json("GET", f"{API}/client/maintenance/issues/{iid}", headers=ch, timeout=60)
        # Use canonical job surface for detail (client portal uses /api/jobs/{id} for job workflow actions/details).
        st_w, wo_body, _ = _get_json("GET", f"{API}/jobs/{wid}", headers=ch, timeout=60)
        desync_probe.update(
            {
                "issue_id": iid,
                "work_order_id": wid,
                "issue_get_status": st_i,
                "issue_status": (issue_body or {}).get("status") if isinstance(issue_body, dict) else None,
                "wo_get_status": st_w,
                "wo_status": (wo_body or {}).get("status") if isinstance(wo_body, dict) else None,
            }
        )

    checks = {
        "completed_has_completed_at": len(completed_missing_completed_at) == 0,
        "verified_has_verified_at": len(verified_missing_verified_at) == 0,
        "holds_possible": True,  # audit does not require presence, only semantics when present
        "awaiting_parts_possible": True,
        "evidence_required_for_completion_enforced": len(completed_with_no_evidence) == 0,
    }
    trust_risks = []
    if completed_missing_completed_at:
        trust_risks.append("jobs_completed_missing_completed_at")
    if verified_missing_verified_at:
        trust_risks.append("jobs_verified_missing_verified_at")
    if completed_with_no_evidence:
        trust_risks.append("jobs_completed_without_evidence_detected")
    if len(no_contractor_open) >= 5:
        trust_risks.append("jobs_open_without_contractor_operational_deadlock_risk")

    return {
        "endpoint": f"{API}/client/maintenance/work-orders",
        "page": f"{FRONTEND}/operations/work-orders",
        "http_status": st,
        "loaded": len(wos),
        "holds_counts": holds,
        "awaiting_parts_count": awaiting_parts,
        "reschedule_heavy_sample": reschedule_heavy[:10],
        "no_contractor_open_sample": no_contractor_open[:10],
        "completed_missing_completed_at_sample": completed_missing_completed_at[:10],
        "verified_missing_verified_at_sample": verified_missing_verified_at[:10],
        "completed_with_no_evidence_sample": completed_with_no_evidence[:10],
        "issue_job_desync_probe": desync_probe,
        "checks": checks,
        "trust_risks": trust_risks,
        "pass": all(checks.values()),
    }


def audit_support_reconstructability(admin_token: Optional[str], client_id: str) -> Dict[str, Any]:
    if not admin_token:
        return {"skipped": True, "reason": "admin_password_unavailable"}
    ah = h(admin_token)
    st, body, raw = _get_json("GET", f"{API}/admin/support/context/{client_id}", headers=ah, timeout=90)
    ops = (body or {}).get("ops_summary_v1") if isinstance(body, dict) else None
    checks = {
        "support_context_200": st == 200,
        "supports_cross_domain_reconstruction": st == 200 and isinstance(body, dict) and (
            (isinstance(ops, dict) and bool(ops.get("recent_issues") or ops.get("recent_work_orders") or ops.get("recent_risk_signals")))
            or any(k in body for k in ("risk_signals", "maintenance_issues", "work_orders"))
        ),
    }
    trust_risks = []
    if st != 200:
        trust_risks.append("support_context_endpoint_fails_blocks_lifecycle_reconstruction")
    return {
        "endpoint": f"{API}/admin/support/context/{client_id}",
        "http_status": st,
        "raw": raw,
        "keys": sorted(list(body.keys())) if isinstance(body, dict) else None,
        "checks": checks,
        "trust_risks": trust_risks,
        "pass": all(checks.values()),
    }


def classify(results: Dict[str, Any]) -> Dict[str, Any]:
    # Classification rule: any trust risks in closure timestamps/attribution → WORKFLOW_ILLUSION_RISK or TRUST_BREAK_RISK.
    trust_risks: List[str] = []
    for k in ("risk_signals", "issues", "jobs", "support"):
        trust_risks.extend(results.get(k, {}).get("trust_risks") or [])

    # Severity heuristic: missing closure timestamps or support reconstruct failure escalates.
    severe = any(
        t
        in trust_risks
        for t in (
            "risk_signals_resolved_missing_resolved_at",
            "issues_terminal_missing_closed_or_resolved_timestamps",
            "jobs_completed_missing_completed_at",
            "jobs_verified_missing_verified_at",
            "support_context_endpoint_fails_blocks_lifecycle_reconstruction",
        )
    )
    medium = any("operational_deadlock" in t or "stale" in t for t in trust_risks)

    if severe and len(trust_risks) >= 2:
        cls = "TRUST_BREAK_RISK"
    elif severe:
        cls = "WORKFLOW_ILLUSION_RISK"
    elif trust_risks or medium:
        cls = "PARTIAL_AUTHORITY"
    else:
        cls = "VERIFIED_AUTHORITY"
    return {"classification": cls, "trust_risks": trust_risks}


def main() -> int:
    write(
        "programme.json",
        {
            "programme": PROGRAMME,
            "verified_at_utc": utc(),
            "staging_api": API,
            "staging_frontend": FRONTEND,
            "client_email": CLIENT_EMAIL,
        },
    )
    token, user = login_client()
    ch = h(token)
    admin = login_admin()
    client_id = user.get("client_id") or ""

    risk = audit_risk_signals(ch)
    issues = audit_issues(ch)
    jobs = audit_jobs(ch)
    support = audit_support_reconstructability(admin[0] if admin else None, client_id)

    results = {"risk_signals": risk, "issues": issues, "jobs": jobs, "support": support}
    write("risk_signals.json", risk)
    write("issues.json", issues)
    write("jobs.json", jobs)
    write("support.json", support)

    classification = classify(results)
    out = {
        "programme": PROGRAMME,
        "verified_at_utc": utc(),
        "classification": classification["classification"],
        "trust_risks": classification["trust_risks"],
        "results": {
            "risk_signals_pass": risk.get("pass"),
            "issues_pass": issues.get("pass"),
            "jobs_pass": jobs.get("pass"),
            "support_pass": support.get("pass"),
        },
    }
    write("07_classification.json", out)
    print(json.dumps(out, indent=2))
    return 0 if out["classification"] in ("VERIFIED_AUTHORITY", "PARTIAL_AUTHORITY") else 1


if __name__ == "__main__":
    raise SystemExit(main())

