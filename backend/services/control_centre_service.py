"""
Pleerity Control Centre — unified snapshot of health, automation, security, revenue, engagement, alerts.
All metrics are read from MongoDB / existing subsystems; no placeholder values.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database
from routes.observability import build_health_summary_payload
from services.job_schedule_registry import (
    JOB_STATE_CONDITIONAL_NO_OUTPUT,
    JOB_STATE_DEGRADED,
    JOB_STATE_FAILED,
    JOB_STATE_HEALTHY,
    JOB_STATE_MISSED,
    JOB_STATE_NEVER_RAN,
    JOB_STATE_NEVER_RAN_AND_OVERDUE,
    JOB_STATE_NOT_YET_DUE_SINCE_STARTUP,
    OVERALL_HEALTH_ATTENTION_REQUIRED,
    OVERALL_HEALTH_DEGRADED,
    OVERALL_HEALTH_FAILED,
    get_critical_job_ids,
    get_registry_by_id,
)
from models import UserRole
from services.security_monitoring_service import get_security_dashboard_summary
from services.plan_registry import plan_registry
from services.control_centre_no_expected_outcome_flag import (
    should_flag_no_expected_outcome_control_centre,
)

logger = logging.getLogger(__name__)

REVENUE_REDACTED_REASON = "Revenue metrics require Owner role (ROLE_OWNER)."


def _clamp(n: float, lo: float = 0, hi: float = 100) -> int:
    return int(max(lo, min(hi, n)))


def _payment_created_ts_stage() -> Dict[str, Any]:
    """Normalize payments.created_at (BSON date or ISO string) for range queries."""
    return {
        "$addFields": {
            "_ts": {
                "$switch": {
                    "branches": [
                        {"case": {"$eq": [{"$type": "$created_at"}, "date"]}, "then": "$created_at"},
                        {
                            "case": {"$eq": [{"$type": "$created_at"}, "string"]},
                            "then": {
                                "$convert": {
                                    "input": "$created_at",
                                    "to": "date",
                                    "onError": None,
                                    "onNull": None,
                                }
                            },
                        },
                    ],
                    "default": None,
                }
            }
        }
    }


async def _payments_aggregate_range(
    db,
    *,
    status: str,
    start: datetime,
    end: datetime,
) -> Tuple[int, int]:
    """Return (sum amount pence, count) for payments in [start, end] with normalized timestamps."""
    pipeline: List[Dict[str, Any]] = [
        {"$match": {"status": status}},
        _payment_created_ts_stage(),
        {"$match": {"_ts": {"$ne": None, "$gte": start, "$lte": end}}},
        {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$amount", 0]}}, "n": {"$sum": 1}}},
    ]
    rows = await db.payments.aggregate(pipeline).to_list(1)
    if not rows:
        return 0, 0
    row = rows[0]
    return int(row.get("total") or 0), int(row.get("n") or 0)


def _severity_sort_key(severity: str) -> int:
    s = (severity or "").upper()
    if s in ("P0", "CRITICAL", "HIGH"):
        return 0
    if s in ("P1", "MEDIUM"):
        return 1
    if s in ("P2", "LOW"):
        return 2
    return 3


def _parse_ts(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t
    except Exception:
        return None


def _compute_automation_health_score(health: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    sc = health.get("summary_counts") or {}
    base = 100.0
    base -= min(40.0, float(sc.get("failed_24h") or 0) * 4.0)
    base -= min(30.0, float(sc.get("degraded_24h") or 0) * 2.0)
    base -= float(sc.get("critical_missed") or 0) * 12.0
    base -= float(sc.get("never_ran_overdue") or 0) * 15.0
    if sc.get("heartbeat_stale"):
        base -= 35.0
    base -= min(50.0, float(health.get("open_p0_p1_count") or 0) * 25.0)
    base -= min(24.0, float(sc.get("delivery_unknown_stale") or 0) * 4.0)
    score = _clamp(base)
    breakdown = {
        "failed_runs_24h_penalty": min(40, (sc.get("failed_24h") or 0) * 4),
        "degraded_runs_24h_penalty": min(30, (sc.get("degraded_24h") or 0) * 2),
        "critical_missed_penalty": (sc.get("critical_missed") or 0) * 12,
        "never_ran_overdue_penalty": (sc.get("never_ran_overdue") or 0) * 15,
        "heartbeat_stale_penalty": 35 if sc.get("heartbeat_stale") else 0,
        "open_p0_p1_penalty": min(50, (health.get("open_p0_p1_count") or 0) * 25),
        "delivery_unknown_stale_penalty": min(24, (sc.get("delivery_unknown_stale") or 0) * 4),
    }
    return score, breakdown


def _compute_security_risk_score(sec: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Higher score = worse risk (0–100)."""
   
    r = 0.0
    breakdown: Dict[str, Any] = {}
    open_inc = int((sec.get("incidents") or {}).get("open") or 0)
    r += min(40.0, open_inc * 8.0)
    breakdown["open_security_incidents"] = min(40, open_inc * 8)

    aa = sec.get("authentication_activity") or {}
    failed_auth = int(aa.get("failed_attempts") or 0)
    r += min(25.0, failed_auth / 10.0)
    breakdown["failed_auth_attempts_window"] = min(25, int(failed_auth / 10))

    sy = sec.get("system_integrity") or {}
    r += min(20.0, float(sy.get("jwt_validation_failures") or 0) * 2.0)
    breakdown["jwt_failures"] = min(20, int(sy.get("jwt_validation_failures") or 0) * 2)
    r += min(15.0, float(sy.get("token_misuse") or 0) * 5.0)
    breakdown["token_misuse"] = min(15, int(sy.get("token_misuse") or 0) * 5)

    fd = sec.get("file_document_access") or {}
    cross_u = int(fd.get("cross_user_access_attempts") or 0)
    r += min(15.0, cross_u * 3.0)
    breakdown["cross_user_access"] = min(15, cross_u * 3)

    pw = sec.get("payment_webhook_integrity") or {}
    sig_fail = int(pw.get("stripe_signature_failures") or 0)
    r += min(15.0, float(sig_fail) * 5.0)
    breakdown["webhook_signature_failures"] = min(15, sig_fail * 5)

    td = sec.get("threat_detections") or {}
    threat_sum = sum(int(v or 0) for v in td.values())
    r += min(30.0, float(threat_sum) * 3.0)
    breakdown["threat_detection_incidents"] = min(30, threat_sum * 3)

    score = _clamp(r)
    return score, breakdown


def _compute_revenue_health_score(rev: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    base = 100.0
    breakdown: Dict[str, Any] = {}
    pd = int(rev.get("past_due_accounts") or 0)
    base -= min(45.0, float(pd) * 12.0)
    breakdown["past_due_penalty"] = min(45, pd * 12)

    fp = int(rev.get("failed_payments_30d") or 0)
    base -= min(30.0, float(fp) * 3.0)
    breakdown["failed_payments_penalty"] = min(30, fp * 3)

    lim = int(rev.get("limited_entitlement_clients") or 0)
    base -= min(25.0, float(lim) * 2.0)
    breakdown["limited_entitlement_penalty"] = min(25, lim * 2)

    sf = int(rev.get("stripe_events_failed_recent") or 0)
    base -= min(20.0, float(sf) * 5.0)
    breakdown["stripe_processing_failures_penalty"] = min(20, sf * 5)

    score = _clamp(base)
    return score, breakdown


def _control_status(
    overall_health: str,
    automation_score: int,
    security_risk: int,
    revenue_score: int,
    heartbeat_stale: bool,
    open_p0_p1: int,
) -> str:
    if (
        overall_health == OVERALL_HEALTH_ATTENTION_REQUIRED
        or overall_health == OVERALL_HEALTH_FAILED
        or heartbeat_stale
        or open_p0_p1 > 0
        or automation_score < 35
        or security_risk > 78
        or revenue_score < 38
    ):
        return "critical"
    if (
        overall_health == OVERALL_HEALTH_DEGRADED
        or automation_score < 72
        or security_risk > 45
        or revenue_score < 68
    ):
        return "degraded"
    return "healthy"


async def _collect_revenue_block(db, now: datetime) -> Dict[str, Any]:
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = day_start.replace(day=1)

    revenue_day_pence, paid_day = await _payments_aggregate_range(
        db, status="paid", start=day_start, end=now
    )
    revenue_month_pence, paid_month = await _payments_aggregate_range(
        db, status="paid", start=month_start, end=now
    )

    active_subscribers = 0
    mrr_pence = 0
    async for b in db.client_billing.find({}, {"subscription_status": 1, "current_plan_code": 1}):
        status = (b.get("subscription_status") or "").upper()
        plan_code = b.get("current_plan_code") or "PLAN_1_SOLO"
        if status in ("ACTIVE", "TRIALING"):
            active_subscribers += 1
            plan_def = plan_registry.get_plan_by_code_string(plan_code)
            monthly_gbp = (plan_def or {}).get("monthly_price") or 0
            mrr_pence += int(round(monthly_gbp * 100))

    last_30 = now - timedelta(days=30)
    _, failed_payments_30d = await _payments_aggregate_range(
        db, status="failed", start=last_30, end=now
    )

    past_due_accounts = await db.client_billing.count_documents(
        {"subscription_status": {"$in": ["PAST_DUE", "past_due"]}}
    )
    limited_entitlement = await db.clients.count_documents({"entitlement_status": "LIMITED"})
    pending_invoices = await db.invoices.count_documents({"status": "pending"})

    recent_cut = now - timedelta(days=3)
    stripe_events_failed_recent = await db.stripe_events.count_documents(
        {"status": "FAILED", "created": {"$gte": recent_cut}}
    )

    revenue_at_risk_pence = 0
    async for b in db.client_billing.find(
        {"subscription_status": {"$in": ["PAST_DUE", "past_due"]}},
        {"current_plan_code": 1},
    ):
        plan_code = b.get("current_plan_code") or "PLAN_1_SOLO"
        plan_def = plan_registry.get_plan_by_code_string(plan_code)
        monthly_gbp = (plan_def or {}).get("monthly_price") or 0
        revenue_at_risk_pence += int(round(monthly_gbp * 100))
    if limited_entitlement > 0:
        async for c in db.clients.find({"entitlement_status": "LIMITED"}, {"billing_plan": 1}):
            pc = c.get("billing_plan") or "PLAN_1_SOLO"
            plan_def = plan_registry.get_plan_by_code_string(pc)
            revenue_at_risk_pence += int(round(((plan_def or {}).get("monthly_price") or 0) * 100))

    return {
        "revenue_today_pence": revenue_day_pence,
        "revenue_this_month_pence": revenue_month_pence,
        "paid_charges_today_count": paid_day,
        "paid_charges_month_count": paid_month,
        "active_subscriptions": active_subscribers,
        "mrr_pence": mrr_pence,
        "failed_payments_30d": failed_payments_30d,
        "past_due_accounts": past_due_accounts,
        "pending_invoices": pending_invoices,
        "limited_entitlement_clients": limited_entitlement,
        "stripe_events_failed_recent": stripe_events_failed_recent,
        "revenue_at_risk_pence": revenue_at_risk_pence,
        "revenue_at_risk_note": "Sum of monthly plan prices for past_due client_billing rows plus LIMITED clients (heuristic MRR at risk).",
    }


async def _collect_engagement_block(db, now: datetime) -> Dict[str, Any]:
    seven_ago = (now - timedelta(days=7)).isoformat()
    thirty_ago = (now - timedelta(days=30)).isoformat()

    new_clients_7d = await db.clients.count_documents({"created_at": {"$gte": seven_ago}})

    provisioned = await db.clients.count_documents({"onboarding_status": "PROVISIONED"})
    total_clients = await db.clients.count_documents({})
    onboarding_completion_rate = round(100.0 * provisioned / max(1, total_clients), 1)

    portal_active = await db.portal_users.count_documents(
        {
            "role": {"$in": ["ROLE_CLIENT", "ROLE_CLIENT_ADMIN"]},
            "status": "ACTIVE",
        }
    )
    portal_inactive_30d = await db.portal_users.count_documents(
        {
            "role": {"$in": ["ROLE_CLIENT", "ROLE_CLIENT_ADMIN"]},
            "status": "ACTIVE",
            "$or": [
                {"last_login": {"$exists": False}},
                {"last_login": None},
                {"last_login": {"$lt": thirty_ago}},
            ],
        }
    )

    uploads_7d = await db.documents.count_documents({"uploaded_at": {"$gte": seven_ago}})

    properties = await db.properties.find(
        {}, {"_id": 0, "compliance_status": 1, "compliance_score": 1}
    ).to_list(50000)
    compliance_distribution = {"GREEN": 0, "AMBER": 0, "RED": 0, "UNKNOWN": 0}
    compliance_score_buckets = {"0_39": 0, "40_59": 0, "60_79": 0, "80_100": 0, "unknown": 0}
    for p in properties:
        cs = p.get("compliance_status") or "UNKNOWN"
        if cs in compliance_distribution:
            compliance_distribution[cs] += 1
        else:
            compliance_distribution["UNKNOWN"] += 1
        raw_score = p.get("compliance_score")
        if raw_score is None:
            compliance_score_buckets["unknown"] += 1
            continue
        try:
            v = float(raw_score)
        except (TypeError, ValueError):
            compliance_score_buckets["unknown"] += 1
            continue
        if v < 40:
            compliance_score_buckets["0_39"] += 1
        elif v < 60:
            compliance_score_buckets["40_59"] += 1
        elif v < 80:
            compliance_score_buckets["60_79"] += 1
        else:
            compliance_score_buckets["80_100"] += 1

    return {
        "new_clients_7d": new_clients_7d,
        "provisioned_clients_total": provisioned,
        "portal_users_active_client_roles": portal_active,
        "portal_users_inactive_30d_client_roles": portal_inactive_30d,
        "onboarding_completion_rate_percent": onboarding_completion_rate,
        "document_uploads_7d": uploads_7d,
        "compliance_status_by_property": compliance_distribution,
        "compliance_numeric_score_buckets": compliance_score_buckets,
        "total_properties_scored": len(properties),
    }


def _compact_security_summary(sec: Dict[str, Any]) -> Dict[str, Any]:
    """Smaller payload: cap incidents.recent for the Control Centre UI."""
    out = {**sec}
    inc = {**(sec.get("incidents") or {})}
    recent = list(inc.get("recent") or [])
    limit = 8
    if len(recent) > limit:
        inc["recent"] = recent[:limit]
        inc["recent_truncated"] = True
        inc["recent_omitted_count"] = len(recent) - limit
    else:
        inc["recent_truncated"] = False
        inc["recent_omitted_count"] = 0
    out["incidents"] = inc
    return out


async def get_control_centre_snapshot(*, viewer_role: Optional[str] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    db = database.get_db()
    is_owner = viewer_role == UserRole.ROLE_OWNER.value

    health = await build_health_summary_payload()
    sec_full = await get_security_dashboard_summary(days=7)
    sec_compact = _compact_security_summary(sec_full)
    if is_owner:
        rev = await _collect_revenue_block(db, now)
    else:
        rev = {"redacted": True, "reason": REVENUE_REDACTED_REASON}
    engagement = await _collect_engagement_block(db, now)

    automation_score, automation_breakdown = _compute_automation_health_score(health)
    security_risk, security_breakdown = _compute_security_risk_score(sec_full)
    if is_owner:
        revenue_score, revenue_breakdown = _compute_revenue_health_score(rev)
    else:
        revenue_score = None
        revenue_breakdown = {}
    revenue_score_for_status = int(revenue_score) if is_owner and revenue_score is not None else 100

    overall_h = health.get("overall_health") or "healthy"
    hb_stale = bool(health.get("heartbeat_stale"))
    open_p0_p1 = int(health.get("open_p0_p1_count") or 0)
    status = _control_status(
        overall_h, automation_score, security_risk, revenue_score_for_status, hb_stale, open_p0_p1
    )

    job_states = health.get("job_states") or {}
    critical_ids = get_critical_job_ids()
    states_list = [job_states.get(j, {}).get("state") for j in critical_ids]
    healthy_like = {
        JOB_STATE_HEALTHY,
        JOB_STATE_CONDITIONAL_NO_OUTPUT,
        JOB_STATE_NOT_YET_DUE_SINCE_STARTUP,
    }
    healthy_n = sum(1 for s in states_list if s in healthy_like)
    failed_n = sum(1 for s in states_list if s == JOB_STATE_FAILED)
    degraded_n = sum(1 for s in states_list if s == JOB_STATE_DEGRADED)
    missed_n = sum(1 for s in states_list if s == JOB_STATE_MISSED)
    never_n = sum(
        1 for s in states_list if s in (JOB_STATE_NEVER_RAN, JOB_STATE_NEVER_RAN_AND_OVERDUE)
    )
    job_confidence = _clamp(
        100.0 * healthy_n / max(1, len(states_list)) - failed_n * 8 - degraded_n * 4 - missed_n * 6
    )

    total_job_runs_recorded = await db.job_runs.count_documents({})

    since_24h = (now - timedelta(hours=24)).isoformat()
    outcome_row = (
        await db.job_runs.aggregate(
            [
                {"$match": {"finished_at": {"$gte": since_24h}}},
                {
                    "$group": {
                        "_id": None,
                        "outcome_success_sum": {
                            "$sum": {"$ifNull": ["$outcome_metrics.success_count", 0]}
                        },
                        "outcome_failed_sum": {
                            "$sum": {"$ifNull": ["$outcome_metrics.failed_count", 0]}
                        },
                        "outcome_attempted_sum": {
                            "$sum": {"$ifNull": ["$outcome_metrics.attempted_count", 0]}
                        },
                        "runs_count": {"$sum": 1},
                    }
                },
            ]
        ).to_list(1)
    )
    om = (outcome_row[0] if outcome_row else {}) or {}

    registry = get_registry_by_id()
    jobs_detail = health.get("jobs") or {}
    jobs_no_expected_outcome: List[Dict[str, Any]] = []
    for jid, reg in registry.items():
        if reg.zero_output_ok:
            continue
        st = (job_states.get(jid) or {}).get("state")
        detail = jobs_detail.get(jid) or {}
        if should_flag_no_expected_outcome_control_centre(
            jid,
            zero_output_ok=reg.zero_output_ok,
            job_state=st,
            detail=detail,
        ):
            jobs_no_expected_outcome.append(
                {
                    "job_name": jid,
                    "last_completed": detail.get("last_completed"),
                    "reason": "success_run_with_zero_attempted_and_zero_success_but_output_expected",
                    "recommended_action": "Verify job configuration and input data; confirm zero work was intended.",
                }
            )

    next_runs = [
        (jid, (job_states.get(jid) or {}).get("next_run"))
        for jid in critical_ids
        if (job_states.get(jid) or {}).get("next_run")
    ]
    next_runs_sorted = sorted(next_runs, key=lambda x: str(x[1] or ""))
    last_completed_times = [
        (jobs_detail.get(jid) or {}).get("last_completed")
        for jid in critical_ids
        if (jobs_detail.get(jid) or {}).get("last_completed")
    ]
    last_completed_latest = max(last_completed_times) if last_completed_times else None

    alerts: List[Dict[str, Any]] = []

    inc_cursor = (
        db.incidents.find(
            {"status": {"$in": ["open", "acknowledged"]}},
            {
                "_id": 1,
                "severity": 1,
                "title": 1,
                "description": 1,
                "status": 1,
                "created_at": 1,
                "source": 1,
                "related_job_name": 1,
            },
        )
        .sort("created_at", -1)
        .limit(40)
    )
    async for inc in inc_cursor:
        oid = inc.get("_id")
        oid_str = str(oid) if oid is not None else ""
        alerts.append(
            {
                "id": f"automation:{oid_str}",
                "category": "automation",
                "severity": inc.get("severity") or "P2",
                "timestamp": inc.get("created_at"),
                "status": inc.get("status"),
                "title": inc.get("title") or "Incident",
                "detail": (inc.get("description") or "")[:500],
                "required_action": "Review in Incidents; ack/resolve or run related job if applicable.",
                "link_path": f"/admin/incidents?highlight={oid_str}",
                "metadata": {
                    "source": inc.get("source"),
                    "related_job_name": inc.get("related_job_name"),
                },
            }
        )

    for row in (sec_full.get("incidents") or {}).get("recent") or []:
        if (row.get("status") or "").lower() != "open":
            continue
        alerts.append(
            {
                "id": f"security:{row.get('incident_key')}",
                "category": "security",
                "severity": str(row.get("severity") or "medium").upper(),
                "timestamp": row.get("timestamp"),
                "status": row.get("status"),
                "title": row.get("type") or "Security incident",
                "detail": str(row.get("details") or "")[:500],
                "required_action": "Review Security Monitoring; resolve when mitigated.",
                "link_path": "/admin/security",
                "metadata": {"incident_key": row.get("incident_key")},
            }
        )

    if is_owner:
        if rev.get("past_due_accounts", 0) > 0:
            alerts.append(
                {
                    "id": "billing:past_due",
                    "category": "billing",
                    "severity": "HIGH",
                    "timestamp": now_iso,
                    "status": "open",
                    "title": "Past-due subscriptions",
                    "detail": f"{rev['past_due_accounts']} account(s) in client_billing with past_due status.",
                    "required_action": "Review Billing → clients with past_due; follow dunning or support.",
                    "link_path": "/admin/billing",
                    "metadata": {"count": rev["past_due_accounts"]},
                }
            )
        if rev.get("failed_payments_30d", 0) > 0:
            alerts.append(
                {
                    "id": "billing:failed_payments",
                    "category": "billing",
                    "severity": "MEDIUM",
                    "timestamp": now_iso,
                    "status": "open",
                    "title": "Failed payments (30 days)",
                    "detail": f"{rev['failed_payments_30d']} failed payment record(s) in payments collection.",
                    "required_action": "Inspect Stripe dashboard and payment logs.",
                    "link_path": "/admin/analytics",
                    "metadata": {"count": rev["failed_payments_30d"]},
                }
            )
        if rev.get("stripe_events_failed_recent", 0) > 0:
            alerts.append(
                {
                    "id": "billing:stripe_events_failed",
                    "category": "billing",
                    "severity": "HIGH",
                    "timestamp": now_iso,
                    "status": "open",
                    "title": "Stripe webhook/processing failures (recent)",
                    "detail": f"{rev['stripe_events_failed_recent']} stripe_events with FAILED status in last 3 days.",
                    "required_action": "Check webhook secrets, payload errors, and idempotency.",
                    "link_path": "/admin/billing",
                    "metadata": {"count": rev["stripe_events_failed_recent"]},
                }
            )

    td = sec_full.get("threat_detections") or {}
    if sum(int(v or 0) for v in td.values()) > 0:
        alerts.append(
            {
                "id": "anomaly:threat_detections",
                "category": "anomaly",
                "severity": "MEDIUM",
                "timestamp": now_iso,
                "status": "open",
                "title": "Security threat detections (7d window)",
                "detail": f"Aggregated detection counts: {td}",
                "required_action": "Triage Security dashboard threat cards and open incidents.",
                "link_path": "/admin/security",
                "metadata": {"threat_detections": td},
            }
        )

    alerts.sort(
        key=lambda a: (
            _severity_sort_key(a.get("severity")),
            str(a.get("timestamp") or ""),
        )
    )

    since_7d_res = (now - timedelta(days=7)).isoformat()
    security_resolved_7d = await db["security_incidents"].count_documents(
        {"status": "resolved", "resolved_at": {"$gte": since_7d_res}}
    )

    return {
        "generated_at": now_iso,
        "access": {
            "revenue_visible": is_owner,
            "viewer_role": viewer_role,
        },
        "system": {
            "status": status,
            "overall_automation_health": overall_h,
            "last_system_check_at": now_iso,
            "scores": {
                "automation_health": automation_score,
                "security_risk": security_risk,
                "revenue_health": revenue_score,
                "job_confidence": job_confidence,
            },
            "score_breakdowns": {
                "automation": automation_breakdown,
                "security_risk": security_breakdown,
                "revenue": revenue_breakdown if is_owner else None,
            },
            "observability_db_name": health.get("observability_db_name"),
            "revenue_excluded_from_status_when_redacted": not is_owner,
        },
        "automation": {
            "total_tracked_jobs": len(critical_ids),
            "total_job_runs_recorded": total_job_runs_recorded,
            "healthy_critical_jobs": healthy_n,
            "failed_critical_jobs": failed_n,
            "degraded_critical_jobs": degraded_n,
            "missed_critical_jobs": missed_n,
            "never_ran_overdue_critical_jobs": never_n,
            "failed_runs_24h": (health.get("summary_counts") or {}).get("failed_24h", 0),
            "degraded_runs_24h": (health.get("summary_counts") or {}).get("degraded_24h", 0),
            "last_completed_latest_critical_path": last_completed_latest,
            "next_scheduled_run_earliest": next_runs_sorted[0][1] if next_runs_sorted else None,
            "job_states_sample": {
                k: job_states.get(k)
                for k in critical_ids[:12]
            },
            "business_outcomes_24h": {
                "finished_runs": om.get("runs_count", 0),
                "outcome_success_sum": om.get("outcome_success_sum", 0),
                "outcome_failed_sum": om.get("outcome_failed_sum", 0),
                "outcome_attempted_sum": om.get("outcome_attempted_sum", 0),
            },
            "jobs_flagged_no_expected_outcome": jobs_no_expected_outcome[:20],
            "open_operational_incidents": health.get("open_incidents_count", 0),
        },
        "security": {
            "summary": sec_compact,
            "failed_login_attempts_7d": (sec_compact.get("authentication_activity") or {}).get("failed_attempts", 0),
            "suspicious_activity": {
                "open_security_incidents": (sec_compact.get("incidents") or {}).get("open", 0),
                "threat_detections_7d": sec_compact.get("threat_detections") or {},
                "cross_user_access_attempts_7d": (sec_compact.get("file_document_access") or {}).get(
                    "cross_user_access_attempts", 0
                ),
            },
            "webhook_validation_failures_7d": (sec_compact.get("payment_webhook_integrity") or {}).get(
                "stripe_signature_failures", 0
            ),
            "token_misuse_7d": (sec_compact.get("system_integrity") or {}).get("token_misuse", 0),
            "document_access_violations_7d": (sec_compact.get("file_document_access") or {}).get("failed_access", 0),
            "security_incidents_resolved_7d": security_resolved_7d,
        },
        "revenue": rev,
        "engagement": engagement,
        "alerts": alerts[:80],
        "scoring_notes": {
            "automation_health": "100 minus weighted penalties from failed/degraded runs (24h), missed/never-ran critical jobs, stale heartbeat, P0/P1 incidents, stale delivery_unknown.",
            "security_risk": "0–100 higher=worse from open security incidents, auth failures (7d audit window), JWT/token/document/webhook signals, threat detection counts.",
            "revenue_health": "100 minus penalties for past_due accounts, failed payments (30d), LIMITED entitlements, recent FAILED stripe_events. Visible only to ROLE_OWNER; other roles see null score and redacted revenue block.",
            "job_confidence": "Derived from critical job states (healthy-like vs failed/degraded/missed) with additional deductions.",
        },
    }
