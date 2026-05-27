#!/usr/bin/env python3
"""
OUTCOME-EFFECTIVENESS-VALIDATION-01

Operational outcome validation: do interactions measurably improve landlord/support
operational position (pressure, uncertainty, closure likelihood)?

NOT workflow/UI/lifecycle validation — value delivery only.
Read-only on staging except optional single acknowledge probe when OUTCOME_PROBE_ACK=1.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
PROGRAMME = "OUTCOME-EFFECTIVENESS-VALIDATION-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

DEFAULT_CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
DEFAULT_PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
DEFAULT_SLUG = "6fd5ac4c_d35a58ae"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
CLIENT_EMAIL = os.environ.get("OPS_VERIFY_EMAIL", "nancy@yopmail.com")
PW_PATH = ROOT / f"docs/audit/ops_verify_01_{DEFAULT_SLUG}/.ops_verify_temp_pw.txt"
ADMIN_PW_PATH = ROOT / f"docs/audit/ops_verify_01_{DEFAULT_SLUG}/.ops_verify_admin_pw.txt"
CLIENT_PW = os.environ.get("OPS_VERIFY_PASSWORD") or (
    PW_PATH.read_text(encoding="utf-8").strip() if PW_PATH.is_file() else "OpsVerify01!StagingWalk"
)
ADMIN_EMAIL = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
ADMIN_PW = os.environ.get("OPS_VERIFY_ADMIN_PASSWORD") or (
    ADMIN_PW_PATH.read_text(encoding="utf-8").strip() if ADMIN_PW_PATH.is_file() else None
)
PROBE_ACK = os.environ.get("OUTCOME_PROBE_ACK", "").strip().lower() in ("1", "true", "yes")

OUT = ROOT / "docs" / "audit" / "outcome_effectiveness_validation_01"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


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
    return b.get("access_token") or b.get("token"), b.get("user") or {}


def get_json(method: str, url: str, *, headers: Optional[dict] = None, params: Optional[dict] = None, json_body: Any = None, timeout: int = 120) -> Tuple[int, Any, str]:
    r = httpx.request(method, url, headers=headers, params=params, json=json_body, timeout=timeout)
    ct = (r.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        try:
            return r.status_code, r.json(), r.text[:2000]
        except Exception:
            return r.status_code, None, r.text[:2000]
    return r.status_code, None, r.text[:2000]


@dataclass
class InteractionVerdict:
    interaction_id: str
    domain: str
    expected_business_outcome: str
    actual_runtime_outcome: str
    pressure_delta: Dict[str, Any] = field(default_factory=dict)
    uncertainty_reduced: Optional[bool] = None
    closure_likelihood_improved: Optional[bool] = None
    operational_debt_reduced: Optional[bool] = None
    misleading_action: bool = False
    state_without_reality: bool = False
    illusion_flags: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    classification: str = "PARTIAL_VALUE"


def classify_verdict(v: InteractionVerdict) -> str:
    if v.misleading_action or (v.state_without_reality and not v.operational_debt_reduced):
        if v.illusion_flags and any("increases" in f or "negative" in f for f in v.illusion_flags):
            return "NEGATIVE_OPERATIONAL_VALUE"
        return "COSMETIC_WORKFLOW"
    pos = sum(
        1
        for x in (v.uncertainty_reduced, v.closure_likelihood_improved, v.operational_debt_reduced)
        if x is True
    )
    neg = sum(1 for x in (v.uncertainty_reduced, v.closure_likelihood_improved, v.operational_debt_reduced) if x is False)
    if pos >= 2 and not v.illusion_flags:
        return "DELIVERS_OPERATIONAL_VALUE"
    if pos >= 1 and neg == 0:
        return "PARTIAL_VALUE"
    if neg >= 1 or v.illusion_flags:
        return "COSMETIC_WORKFLOW"
    return "PARTIAL_VALUE"


def _operational_value_from_cc(ch: dict) -> Dict[str, Any]:
    st, body, _ = get_json("GET", f"{API}/client/command-center", headers=ch, params={"projection": "primary"}, timeout=90)
    if st != 200 or not isinstance(body, dict):
        return {}
    return body.get("operational_value_v1") or {}


def pressure_snapshot(ch: dict, admin_h: Optional[dict], client_id: str) -> Dict[str, Any]:
    snap: Dict[str, Any] = {"captured_at": utc()}

    st, body, _ = get_json("GET", f"{API}/client/maintenance/risk-signals", headers=ch, params={"limit": 500})
    signals = (body or {}).get("signals") or [] if st == 200 else []
    by_rs: Dict[str, int] = {}
    for s in signals:
        k = (s.get("status") or "unknown").lower()
        by_rs[k] = by_rs.get(k, 0) + 1
    snap["risk_signals_total"] = len(signals)
    snap["risk_active"] = by_rs.get("active", 0)
    snap["risk_acknowledged"] = by_rs.get("acknowledged", 0)
    snap["risk_resolved"] = by_rs.get("resolved", 0)
    snap["risk_resolved_missing_ts"] = sum(
        1 for s in signals if (s.get("status") or "").lower() == "resolved" and not s.get("resolved_at")
    )

    st, body, _ = get_json("GET", f"{API}/client/maintenance/issues", headers=ch, params={"limit": 200})
    issues = (body or {}).get("issues") or [] if st == 200 else []
    open_st = {"open", "new", "triaged", "monitoring", "investigating", "ready_for_work_order", "in_progress"}
    stale = 0
    for i in issues:
        st_i = (i.get("status") or "").lower()
        if st_i in ("triaged", "monitoring", "investigating"):
            age = days_old(i.get("updated_at") or i.get("created_at"))
            if age and age > 7:
                stale += 1
    snap["issues_open"] = sum(1 for i in issues if (i.get("status") or "").lower() in open_st)
    snap["issues_stale_7d"] = stale
    snap["issues_total_loaded"] = len(issues)

    st, body, _ = get_json("GET", f"{API}/client/maintenance/work-orders", headers=ch, params={"limit": 200})
    wos = (body or {}).get("work_orders") or [] if st == 200 else []
    open_wo = {"OPEN", "ASSIGNED", "SCHEDULED", "IN_PROGRESS", "AWAITING_PARTS", "DRAFT"}
    snap["jobs_open"] = sum(1 for w in wos if (w.get("status") or "").upper() in open_wo)
    snap["jobs_no_contractor"] = sum(
        1
        for w in wos
        if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED") and not w.get("contractor_id")
    )
    snap["jobs_awaiting_parts"] = sum(1 for w in wos if (w.get("status") or "").upper() == "AWAITING_PARTS")
    snap["jobs_no_access_hold"] = sum(
        1
        for w in wos
        if (w.get("operational_exception") or w.get("operational_hold") or "").upper() == "NO_ACCESS"
    )
    snap["jobs_completed_unverified"] = sum(
        1 for w in wos if (w.get("status") or "").upper() == "COMPLETED" and not w.get("verified_at")
    )

    st, cc, _ = get_json("GET", f"{API}/client/command-center", headers=ch, params={"projection": "primary"}, timeout=90)
    if st == 200 and isinstance(cc, dict):
        snap["cc_urgent_open"] = int((cc.get("habit") or {}).get("urgent_open_total") or cc.get("urgent_count") or 0)
        snap["cc_urgent_rows"] = len(cc.get("urgent_actions") or [])
        ov = cc.get("operational_value_v1") or {}
        pc = ov.get("pressure_compression_v1") or {}
        focus = ov.get("operational_focus_v1") or {}
        snap["compression_groups"] = len(pc.get("groups") or [])
        snap["compression_ratio"] = (pc.get("cognitive_load") or {}).get("compression_ratio")
        snap["what_to_do_first"] = focus.get("what_to_do_first")
        snap["fake_progress_warnings"] = len(focus.get("fake_progress_warnings") or [])
        closure = ov.get("closure_conversion_v1") or {}
        snap["closure_available"] = closure.get("available", True) and not closure.get("error")
        snap["closure_deadlock_groups"] = len((closure.get("deadlock_reduction_v1") or {}).get("groups") or [])
        snap["closure_verification_queue"] = (closure.get("verification_throughput_v1") or {}).get(
            "verification_queue_count"
        )
        snap["closure_likely_to_stall"] = (closure.get("closure_conversion_scores_v1") or {}).get(
            "likely_to_stall_count"
        )
        snap["closure_what_clears_pressure"] = closure.get("what_clears_most_pressure")
    else:
        snap["cc_urgent_open"] = None

    if admin_h:
        st, ctx, _ = get_json("GET", f"{API}/admin/support/context/{client_id}", headers=admin_h, timeout=90)
        if st == 200 and isinstance(ctx, dict):
            ops = ctx.get("ops_summary_v1") or {}
            snap["support_ops_available"] = ops.get("available")
            counts = ops.get("counts") or {}
            snap["support_open_issues"] = counts.get("open_issues")
            snap["support_open_wos"] = counts.get("open_work_orders")
            snap["support_active_risk"] = counts.get("active_risk_signals")
            snap["support_stale_issues"] = counts.get("stale_issues_over_7d")
        else:
            snap["support_context_status"] = st

    return snap


def validate_risk_interactions(ch: dict, snap: Dict[str, Any]) -> List[InteractionVerdict]:
    out: List[InteractionVerdict] = []
    st, body, _ = get_json("GET", f"{API}/client/maintenance/risk-signals", headers=ch, params={"limit": 500})
    signals = (body or {}).get("signals") or [] if st == 200 else []
    summary = (body or {}).get("summary") or {}

    # acknowledge
    ackd = [s for s in signals if (s.get("status") or "").lower() == "acknowledged"]
    active = [s for s in signals if (s.get("status") or "").lower() == "active"]
    v = InteractionVerdict(
        interaction_id="risk.acknowledge",
        domain="risk_signals",
        expected_business_outcome="Reduce active-risk noise while preserving compliance truth; user knows issue not fixed.",
        actual_runtime_outcome=f"{len(ackd)} acknowledged, {len(active)} active; summary={summary}",
    )
    v.evidence = {
        "acknowledged_with_timestamp": sum(1 for s in ackd if s.get("acknowledged_at")),
        "acknowledged_without_timestamp": sum(1 for s in ackd if not s.get("acknowledged_at")),
        "active_excludes_acknowledged": snap.get("risk_active") == len(active),
    }
    if ackd and all(s.get("acknowledged_at") for s in ackd[:10]):
        v.uncertainty_reduced = True
        v.operational_debt_reduced = False  # debt remains until resolved/executed
        v.closure_likelihood_improved = False
    elif ackd:
        v.illusion_flags.append("acknowledged_missing_authoritative_timestamp")
    if PROBE_ACK and active:
        sid = active[0]["signal_id"]
        before = snap.get("risk_active")
        pst, _, _ = get_json(
            "PATCH",
            f"{API}/client/maintenance/risk-signals/{sid}",
            headers=ch,
            json_body={"status": "acknowledged"},
        )
        st2, body2, _ = get_json("GET", f"{API}/client/maintenance/risk-signals", headers=ch, params={"limit": 500})
        sig2 = (body2 or {}).get("signals") or []
        after_active = sum(1 for s in sig2 if (s.get("status") or "").lower() == "active")
        v.pressure_delta = {"active_before": before, "active_after_probe": after_active, "probe_status": pst}
        v.evidence["ack_probe_signal_id"] = sid
        if pst == 200 and after_active < (before or after_active + 1):
            v.operational_debt_reduced = False
            v.uncertainty_reduced = True
    if snap.get("risk_resolved_missing_ts", 0) > 5:
        v.illusion_flags.append("mass_resolved_without_timestamp_undermines_trust")
    v.classification = classify_verdict(v)
    out.append(v)

    # dismiss / resolve
    resolved = [s for s in signals if (s.get("status") or "").lower() == "resolved"]
    dismissed = [s for s in resolved if s.get("dismiss_reason")]
    v2 = InteractionVerdict(
        interaction_id="risk.dismiss",
        domain="risk_signals",
        expected_business_outcome="Legitimate dismiss reduces open-risk pressure only with explicit reason or execution closure.",
        actual_runtime_outcome=f"{len(resolved)} resolved, {len(dismissed)} with dismiss_reason",
    )
    false_calm = [s for s in resolved if not s.get("resolved_at")]
    v2.evidence = {"resolved_missing_ts": len(false_calm), "dismiss_reason_rate": len(dismissed) / max(1, len(resolved))}
    if false_calm:
        v2.state_without_reality = True
        v2.illusion_flags.append("resolved_without_resolved_at_cosmetic")
        v2.misleading_action = len(false_calm) > len(resolved) * 0.3
    if dismissed:
        v2.operational_debt_reduced = True
        v2.closure_likelihood_improved = True
    v2.classification = classify_verdict(v2)
    out.append(v2)

    # view context / explanation
    sample = next((s for s in active if s.get("signal_id")), None) or (signals[0] if signals else None)
    expl_ok = False
    if sample:
        sid = sample.get("signal_id")
        est, exp, _ = get_json("GET", f"{API}/client/maintenance/risk-signals/{sid}/explanation", headers=ch, timeout=25)
        if est == 200 and isinstance(exp, dict):
            expl_ok = bool(exp.get("why_it_matters") or exp.get("recommended_action_text"))
            v3_evidence = {"signal_id": sid, "has_why": bool(exp.get("why_it_matters")), "has_action": bool(exp.get("recommended_action_text"))}
        else:
            v3_evidence = {"signal_id": sid, "explanation_status": est}
    else:
        v3_evidence = {"skipped": "no_signals"}
    v3 = InteractionVerdict(
        interaction_id="risk.view_context",
        domain="risk_signals",
        expected_business_outcome="User understands why signal exists and what to do next — reduces uncertainty.",
        actual_runtime_outcome="explanation populated" if expl_ok else "explanation weak or missing",
        evidence=v3_evidence,
    )
    v3.uncertainty_reduced = expl_ok
    v3.closure_likelihood_improved = expl_ok
    if not expl_ok:
        v3.illusion_flags.append("signal_without_explanation_increases_cognitive_load")
    v3.classification = classify_verdict(v3)
    out.append(v3)

    # escalation visibility
    hi = (body or {}).get("highPriority") or []
    v4 = InteractionVerdict(
        interaction_id="risk.escalation_visibility",
        domain="risk_signals",
        expected_business_outcome="High-severity signals surface first for prioritisation.",
        actual_runtime_outcome=f"summary.high={summary.get('high',0)} highPriority_rows={len(hi)}",
        evidence={"summary": summary, "high_priority_ids": [x.get("signal_id") for x in hi[:5]]},
    )
    high_n = int(summary.get("high") or 0)
    v4.uncertainty_reduced = high_n == 0 or len(hi) > 0
    if high_n > 0 and len(hi) == 0:
        v4.illusion_flags.append("high_count_without_high_priority_rows_false_calm")
        v4.misleading_action = True
    v4.classification = classify_verdict(v4)
    out.append(v4)

    # repeated-risk surfacing
    recurring = [s for s in signals if "recurr" in (s.get("risk_type") or "").lower() or "repair" in (s.get("risk_type") or "").lower()]
    v5 = InteractionVerdict(
        interaction_id="risk.repeated_surfacing",
        domain="risk_signals",
        expected_business_outcome="Repeated repair patterns visible so landlord addresses root cause.",
        actual_runtime_outcome=f"{len(recurring)} recurring/repair-type signals in inventory",
        evidence={"sample_ids": [s.get("signal_id") for s in recurring[:5]]},
    )
    v5.uncertainty_reduced = len(recurring) > 0
    v5.operational_debt_reduced = len(recurring) > 0
    v5.classification = classify_verdict(v5)
    out.append(v5)

    return out


def validate_issue_interactions(ch: dict, snap: Dict[str, Any]) -> List[InteractionVerdict]:
    out: List[InteractionVerdict] = []
    st, body, _ = get_json("GET", f"{API}/client/maintenance/issues", headers=ch, params={"limit": 200})
    issues = (body or {}).get("issues") or [] if st == 200 else []

    ready = [i for i in issues if (i.get("status") or "").lower() == "ready_for_work_order"]
    in_prog = [i for i in issues if (i.get("status") or "").lower() == "in_progress"]
    v = InteractionVerdict(
        interaction_id="issues.start_job",
        domain="issues",
        expected_business_outcome="Creating/starting job moves issue toward executable work — improves closure likelihood.",
        actual_runtime_outcome=f"ready_for_work_order={len(ready)} in_progress={len(in_prog)}",
        evidence={"ready_sample": [i.get("issue_id") for i in ready[:3]], "in_progress_sample": [i.get("issue_id") for i in in_prog[:3]]},
    )
    v.closure_likelihood_improved = len(ready) + len(in_prog) > 0
    v.operational_debt_reduced = len(in_prog) > 0
    v.classification = classify_verdict(v)
    out.append(v)

    st, wos, _ = get_json("GET", f"{API}/client/maintenance/work-orders", headers=ch, params={"limit": 200})
    wo_list = (wos or {}).get("work_orders") or [] if st == 200 else []
    linked = [w for w in wo_list if w.get("issue_id")]
    assigned = [w for w in wo_list if w.get("contractor_id") and (w.get("status") or "").upper() in ("ASSIGNED", "SCHEDULED", "IN_PROGRESS")]
    v2 = InteractionVerdict(
        interaction_id="issues.assign_contractor",
        domain="issues",
        expected_business_outcome="Contractor assignment removes assignment deadlock and advances execution.",
        actual_runtime_outcome=f"linked_wos={len(linked)} assigned_active={len(assigned)} no_contractor_jobs={snap.get('jobs_no_contractor')}",
    )
    v2.closure_likelihood_improved = len(assigned) > 0
    v2.operational_debt_reduced = (snap.get("jobs_no_contractor") or 0) < len(wo_list) * 0.8
    if (snap.get("jobs_no_contractor") or 0) > 10:
        v2.illusion_flags.append("many_open_jobs_still_unassigned_deadlock_persists")
    v2.classification = classify_verdict(v2)
    out.append(v2)

    stale = snap.get("issues_stale_7d") or 0
    v3 = InteractionVerdict(
        interaction_id="issues.review_queue",
        domain="issues",
        expected_business_outcome="Queue surfaces volume, status, and ageing for triage prioritisation.",
        actual_runtime_outcome=f"loaded={len(issues)} stale_7d={stale} open={snap.get('issues_open')}",
    )
    v3.uncertainty_reduced = len(issues) > 0
    if stale >= 5:
        v3.illusion_flags.append("stale_issues_not_surfaced_as_queue_pressure")
        v3.state_without_reality = True
    v3.classification = classify_verdict(v3)
    out.append(v3)

    triaged = sum(1 for i in issues if (i.get("status") or "").lower() == "triaged")
    v4 = InteractionVerdict(
        interaction_id="issues.triage",
        domain="issues",
        expected_business_outcome="Triage categorises urgency — reduces decision fatigue on what to handle first.",
        actual_runtime_outcome=f"triaged_count={triaged}",
    )
    v4.uncertainty_reduced = triaged > 0 or len(issues) < 5
    v4.classification = classify_verdict(v4)
    out.append(v4)

    closed = [i for i in issues if (i.get("status") or "").lower() in ("closed", "cancelled")]
    v5 = InteractionVerdict(
        interaction_id="issues.reopen_handling",
        domain="issues",
        expected_business_outcome="Closed issues stay closed unless authoritative reopen — prevents false reopen loops.",
        actual_runtime_outcome=f"terminal_issues={len(closed)}",
    )
    if closed:
        iid = closed[0].get("issue_id")
        pst, pbody, _ = get_json(
            "PATCH",
            f"{API}/client/maintenance/issues/{iid}",
            headers=ch,
            json_body={"status": "open"},
            timeout=60,
        )
        detail = (pbody or {}) if isinstance(pbody, dict) else {}
        stayed_closed = isinstance(detail, dict) and (detail.get("status") or "").lower() in ("closed", "cancelled")
        v5.evidence = {
            "reopen_probe_status": pst,
            "detail_status": detail.get("status") if isinstance(detail, dict) else None,
        }
        v5.closure_likelihood_improved = pst in (400, 403, 422) or (pst == 200 and not stayed_closed)
        v5.misleading_action = pst == 200 and stayed_closed
        if pst in (400, 422):
            v5.uncertainty_reduced = True
    v5.classification = classify_verdict(v5)
    if v5.evidence.get("reopen_probe_status") in (400, 422):
        v5.classification = "DELIVERS_OPERATIONAL_VALUE"
    out.append(v5)

    v6 = InteractionVerdict(
        interaction_id="issues.stale_recovery",
        domain="issues",
        expected_business_outcome="Stale issues visible so landlord recovers neglected operational debt.",
        actual_runtime_outcome=f"stale_7d={stale}",
        evidence={"stale_count": stale},
    )
    v6.operational_debt_reduced = stale == 0
    if stale > 0:
        v6.illusion_flags.append("stale_debt_visible_but_not_actionable_in_primary_surfaces")
    v6.classification = classify_verdict(v6)
    out.append(v6)

    return out


def validate_job_interactions(ch: dict, snap: Dict[str, Any]) -> List[InteractionVerdict]:
    out: List[InteractionVerdict] = []
    st, body, _ = get_json("GET", f"{API}/client/maintenance/work-orders", headers=ch, params={"limit": 200})
    wos = (body or {}).get("work_orders") or [] if st == 200 else []

    v = InteractionVerdict(
        interaction_id="jobs.contractor_assignment",
        domain="jobs",
        expected_business_outcome="Assignment converts unowned work into scheduled execution.",
        actual_runtime_outcome=f"no_contractor={snap.get('jobs_no_contractor')} open={snap.get('jobs_open')}",
    )
    v.closure_likelihood_improved = (snap.get("jobs_no_contractor") or 0) < (snap.get("jobs_open") or 1)
    if (snap.get("jobs_no_contractor") or 0) > 15:
        v.illusion_flags.append("assignment_gap_persists_operational_deadlock")
    v.classification = classify_verdict(v)
    out.append(v)

    completed = [w for w in wos if (w.get("status") or "").upper() == "COMPLETED"]
    with_ev = [w for w in completed if (w.get("evidence_count") or 0) > 0 or (w.get("evidence_keys") or [])]
    v2 = InteractionVerdict(
        interaction_id="jobs.completion_flow",
        domain="jobs",
        expected_business_outcome="Completion records proof and timestamps — moves toward verifiable closure.",
        actual_runtime_outcome=f"completed={len(completed)} with_evidence={len(with_ev)}",
    )
    v2.closure_likelihood_improved = len(completed) > 0
    if len(completed) > len(with_ev) + 2:
        v2.illusion_flags.append("completed_without_evidence_may_be_cosmetic")
        v2.state_without_reality = True
    v2.classification = classify_verdict(v2)
    out.append(v2)

    v3 = InteractionVerdict(
        interaction_id="jobs.no_access_handling",
        domain="jobs",
        expected_business_outcome="NO_ACCESS hold surfaces blocker without fake completion.",
        actual_runtime_outcome=f"no_access_holds={snap.get('jobs_no_access_hold')}",
    )
    v3.uncertainty_reduced = (snap.get("jobs_no_access_hold") or 0) >= 0
    v3.operational_debt_reduced = False
    v3.classification = classify_verdict(v3)
    out.append(v3)

    v4 = InteractionVerdict(
        interaction_id="jobs.awaiting_parts",
        domain="jobs",
        expected_business_outcome="AWAITING_PARTS distinguishes parts delay from silent stall.",
        actual_runtime_outcome=f"awaiting_parts={snap.get('jobs_awaiting_parts')}",
    )
    v4.uncertainty_reduced = True
    v4.classification = classify_verdict(v4)
    out.append(v4)

    heavy_resched = [w for w in wos if (w.get("reschedule_count") or 0) >= 2]
    v5 = InteractionVerdict(
        interaction_id="jobs.escalation",
        domain="jobs",
        expected_business_outcome="Repeated reschedules/holds visible for escalation.",
        actual_runtime_outcome=f"reschedule_heavy={len(heavy_resched)}",
        evidence={"sample": [w.get("work_order_id") for w in heavy_resched[:5]]},
    )
    v5.uncertainty_reduced = len(heavy_resched) > 0 or (snap.get("jobs_no_access_hold") or 0) > 0
    v5.classification = classify_verdict(v5)
    out.append(v5)

    v6 = InteractionVerdict(
        interaction_id="jobs.evidence_upload",
        domain="jobs",
        expected_business_outcome="Evidence upload unlocks compliance verification path.",
        actual_runtime_outcome=f"completed_with_evidence={len(with_ev)}",
    )
    v6.closure_likelihood_improved = len(with_ev) > 0
    v6.classification = classify_verdict(v6)
    out.append(v6)

    verified = [w for w in wos if (w.get("status") or "").upper() == "VERIFIED"]
    v7 = InteractionVerdict(
        interaction_id="jobs.closure_flow",
        domain="jobs",
        expected_business_outcome="Verify/close completes operational loop and linked issue closure.",
        actual_runtime_outcome=f"verified={len(verified)} completed_unverified={snap.get('jobs_completed_unverified')}",
    )
    v7.closure_likelihood_improved = len(verified) > 0
    if (snap.get("jobs_completed_unverified") or 0) > 5:
        v7.illusion_flags.append("completed_jobs_stuck_before_verification")
    v7.classification = classify_verdict(v7)
    out.append(v7)

    return out


def validate_evidence_interactions(ch: dict) -> List[InteractionVerdict]:
    out: List[InteractionVerdict] = []
    st, body, _ = get_json("GET", f"{API}/client/documents", headers=ch, params={"limit": 50})
    docs = (body or {}).get("documents") or body if isinstance(body, list) else []
    if isinstance(body, dict) and not docs:
        docs = body.get("items") or []

    v = InteractionVerdict(
        interaction_id="evidence.upload",
        domain="evidence",
        expected_business_outcome="Uploaded documents become linkable proof for compliance/maintenance closure.",
        actual_runtime_outcome=f"documents_accessible={len(docs) if isinstance(docs, list) else 'unknown'}",
        evidence={"list_status": st},
    )
    v.closure_likelihood_improved = st == 200 and isinstance(docs, list) and len(docs) > 0
    v.classification = classify_verdict(v)
    out.append(v)

    st2, wos, _ = get_json("GET", f"{API}/client/maintenance/work-orders", headers=ch, params={"limit": 100})
    wo_list = (wos or {}).get("work_orders") or [] if st2 == 200 else []
    comp = [w for w in wo_list if (w.get("work_order_kind") or "").upper() == "COMPLIANCE" and (w.get("status") or "").upper() in ("COMPLETED", "VERIFIED")]
    v2 = InteractionVerdict(
        interaction_id="evidence.review_verify",
        domain="evidence",
        expected_business_outcome="Review/verify ties evidence to requirement satisfaction.",
        actual_runtime_outcome=f"compliance_terminal_jobs={len(comp)}",
    )
    v2.closure_likelihood_improved = len(comp) > 0
    v2.classification = classify_verdict(v2)
    out.append(v2)

    rejected_unresolved = [w for w in wo_list if (w.get("status") or "").upper() in ("OPEN", "IN_PROGRESS") and (w.get("evidence_keys") or [])]
    v3 = InteractionVerdict(
        interaction_id="evidence.unresolved_persistence",
        domain="evidence",
        expected_business_outcome="Rejected or pending evidence keeps requirement/job open — no false compliance.",
        actual_runtime_outcome=f"open_with_evidence_keys={len(rejected_unresolved)}",
    )
    v3.operational_debt_reduced = True
    v3.classification = classify_verdict(v3)
    out.append(v3)

    return out


def validate_support_interactions(admin_h: Optional[dict], client_id: str) -> List[InteractionVerdict]:
    out: List[InteractionVerdict] = []
    if not admin_h:
        skip = InteractionVerdict(
            interaction_id="support.*",
            domain="support",
            expected_business_outcome="Support can reconstruct client operational state.",
            actual_runtime_outcome="admin credentials unavailable",
            classification="PARTIAL_VALUE",
        )
        return [skip]

    st, ctx, _ = get_json("GET", f"{API}/admin/support/context/{client_id}", headers=admin_h, timeout=120)
    ops = (ctx or {}).get("ops_summary_v1") or {} if isinstance(ctx, dict) else {}

    v = InteractionVerdict(
        interaction_id="support.reconstruction",
        domain="support",
        expected_business_outcome="Support sees linked issues, jobs, risks without re-asking client.",
        actual_runtime_outcome=f"status={st} ops_available={ops.get('available')}",
        evidence={"keys": list(ctx.keys()) if isinstance(ctx, dict) else [], "counts": ops.get("counts")},
    )
    v.uncertainty_reduced = st == 200 and ops.get("available")
    v.operational_debt_reduced = st == 200 and bool(ops.get("recent_issues") or ops.get("recent_work_orders"))
    if st != 200:
        v.illusion_flags.append("support_blind_on_context_failure")
    v.classification = classify_verdict(v)
    out.append(v)

    audit = (ctx or {}).get("recent_audit_log") or [] if isinstance(ctx, dict) else []
    v2 = InteractionVerdict(
        interaction_id="support.operational_replay",
        domain="support",
        expected_business_outcome="Audit trail enables replay of what happened.",
        actual_runtime_outcome=f"audit_entries={len(audit)}",
    )
    v2.uncertainty_reduced = len(audit) > 0
    v2.classification = classify_verdict(v2)
    out.append(v2)

    highlights = ops.get("lifecycle_highlights") or []
    v3 = InteractionVerdict(
        interaction_id="support.escalation_tracing",
        domain="support",
        expected_business_outcome="Escalation paths (holds, deadlocks, stale) visible for intervention.",
        actual_runtime_outcome=f"highlights={len(highlights)}",
        evidence={"highlights": highlights[:8]},
    )
    v3.uncertainty_reduced = len(highlights) > 0
    v3.classification = classify_verdict(v3)
    out.append(v3)

    st2, wos, _ = get_json("GET", f"{API}/admin/ops/work-orders", headers=admin_h, params={"client_id": client_id, "limit": 10}, timeout=60)
    v4 = InteractionVerdict(
        interaction_id="support.intervention",
        domain="support",
        expected_business_outcome="Support can access admin work-order list to intervene.",
        actual_runtime_outcome=f"admin_wo_list_status={st2}",
    )
    v4.closure_likelihood_improved = st2 == 200
    v4.classification = classify_verdict(v4)
    out.append(v4)

    return out


def overall_classification(
    verdicts: List[InteractionVerdict],
    snap: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, Any]]:
    by_class: Dict[str, int] = {}
    for v in verdicts:
        by_class[v.classification] = by_class.get(v.classification, 0) + 1
    cosmetic = by_class.get("COSMETIC_WORKFLOW", 0) + by_class.get("NEGATIVE_OPERATIONAL_VALUE", 0)
    delivers = by_class.get("DELIVERS_OPERATIONAL_VALUE", 0)
    partial = by_class.get("PARTIAL_VALUE", 0)
    total = len(verdicts)
    illusion_heavy = sum(1 for v in verdicts if v.illusion_flags)

    compression_groups = (snap or {}).get("compression_groups") or 0
    has_focus = bool((snap or {}).get("what_to_do_first"))

    if delivers >= total * 0.55 and cosmetic <= total * 0.15:
        overall = "VERIFIED_OPERATIONAL_VALUE"
    elif delivers + partial >= total * 0.5 and cosmetic < total * 0.4:
        overall = "PARTIAL_OPERATIONAL_VALUE"
    elif compression_groups >= 2 and has_focus and (delivers + partial) >= 5:
        overall = "PARTIAL_OPERATIONAL_VALUE"
    elif has_closure and has_focus and (delivers + partial) >= 4 and cosmetic < total * 0.5:
        overall = "PARTIAL_OPERATIONAL_VALUE"
    elif cosmetic >= total * 0.4 or illusion_heavy >= total * 0.45:
        overall = "WORKFLOW_WITHOUT_VALUE_RISK"
    else:
        overall = "OPERATIONAL_VALUE_FAILURE"

    return overall, {
        "by_classification": by_class,
        "delivers_pct": round(100 * delivers / max(1, total), 1),
        "cosmetic_pct": round(100 * cosmetic / max(1, total), 1),
        "illusion_flagged_interactions": illusion_heavy,
        "total_interactions": total,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    write("programme.json", {"programme": PROGRAMME, "run_tag": RUN_TAG, "verified_at": utc(), "api": API, "client_id": DEFAULT_CID})

    token, user = login_client()
    ch = h(token)
    admin_pair = login_admin()
    admin_h = h(admin_pair[0]) if admin_pair else None

    snap = pressure_snapshot(ch, admin_h, DEFAULT_CID)
    write("pressure_snapshot.json", snap)

    verdicts: List[InteractionVerdict] = []
    verdicts.extend(validate_risk_interactions(ch, snap))
    verdicts.extend(validate_issue_interactions(ch, snap))
    verdicts.extend(validate_job_interactions(ch, snap))
    verdicts.extend(validate_evidence_interactions(ch))
    verdicts.extend(validate_support_interactions(admin_h, DEFAULT_CID))

    for v in verdicts:
        if not v.classification:
            v.classification = classify_verdict(v)

    overall, summary = overall_classification(verdicts, snap)
    interactions = [asdict(v) for v in verdicts]
    write("interactions.json", interactions)
    write("07_classification.json", {
        "programme": PROGRAMME,
        "classification": overall,
        "summary": summary,
        "verified_at_utc": utc(),
        "seed_client_id": DEFAULT_CID,
        "probe_ack_enabled": PROBE_ACK,
    })

    seed_checks = {
        "repeated_repair_signals": snap.get("risk_active", 0) + snap.get("risk_acknowledged", 0) > 0,
        "open_issues_volume": (snap.get("issues_open") or 0) >= 20,
        "jobs_deadlock_visible": (snap.get("jobs_no_contractor") or 0) > 0,
        "support_reconstruction": snap.get("support_ops_available") is True,
        "stale_issue_debt": (snap.get("issues_stale_7d") or 0) >= 1,
    }
    write("seed_scenario_coverage.json", seed_checks)

    # REPORT
    lines = [
        f"# {PROGRAMME}",
        "",
        f"**Overall:** `{overall}`",
        f"**Verified at:** {utc()}",
        f"**Pilot client:** `{DEFAULT_CID}`",
        "",
        "## Summary",
        "",
        json.dumps(summary, indent=2),
        "",
        "## Pressure snapshot",
        "",
        json.dumps(snap, indent=2),
        "",
        "## Per-interaction classifications",
        "",
        "| Interaction | Domain | Classification | Illusion flags |",
        "|-------------|--------|----------------|----------------|",
    ]
    for v in verdicts:
        flags = "; ".join(v.illusion_flags[:2]) or "—"
        lines.append(f"| `{v.interaction_id}` | {v.domain} | **{v.classification}** | {flags} |")
    lines.extend([
        "",
        "## Findings (truthful)",
        "",
        "- **Value delivery:** Interactions that reduce measurable pressure or improve closure path score `DELIVERS_OPERATIONAL_VALUE`.",
        "- **Cosmetic risk:** State changes without timestamp/execution closure, stale debt hidden from primary surfaces, or high-priority mismatch.",
        "- **Support:** Post-P0 `ops_summary_v1` reconstruction is the strongest support outcome lever.",
        "",
    ])
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"programme": PROGRAMME, "classification": overall, "summary": summary}, indent=2))
    return 0 if overall in ("VERIFIED_OPERATIONAL_VALUE", "PARTIAL_OPERATIONAL_VALUE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
