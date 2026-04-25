"""
Assemble monthly digest payload from live portal truth: compliance_score service,
requirements, documents, unified tasks (command centre), work orders.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from database import database
from presentation.label_service import compliance_requirement_status_label, requirement_label
from presentation.jurisdiction_reporting import (
    digest_jurisdiction_notice_text,
    jurisdiction_default_fallback_report_disclaimer,
)
from services.compliance_rules_registry import build_jurisdiction_compliance_notice
from services.monthly_digest_snapshot_service import (
    build_fingerprint_map,
    compute_deltas,
    load_latest_snapshot,
)
from utils.risk_bands import score_to_risk_level
from utils.expiry_utils import get_effective_expiry_date
from services.requirement_evidence_authority import authority_runtime_requirement_status

from services.monthly_digest_limits import (
    DIGEST_EMAIL_TOP_PROPERTIES_AT_RISK,
    DIGEST_MAX_PROPERTIES_FETCH,
    DIGEST_MAX_REQUIREMENTS_FETCH,
    DIGEST_PDF_MAX_REQUIREMENT_ROWS,
)


def _digest_inbox_activity_lines(activity_feed: Any, limit: int = 5) -> List[str]:
    out: List[str] = []
    act_labels = {
        "snooze": "Today item snoozed",
        "dismiss": "Today item hidden from Today",
        "done": "Today inbox marked done (legacy)",
        "reviewed": "Today item marked reviewed in Today only",
        "restore": "Today item restored to Today",
    }
    for row in (activity_feed or [])[:limit]:
        act = (row.get("action") or "").strip().lower()
        extra = row.get("extra") or {}
        title = (extra.get("title") or "").strip()
        tid = (row.get("task_id") or "").strip()
        label = title or tid
        verb = (row.get("action_label") or "").strip()
        if not verb:
            verb = act_labels.get(act, act.replace("_", " ").title() if act else "Today inbox activity")
        if label:
            out.append(f"{verb}: {label}")
        else:
            out.append(verb)
    return out


def _parse_iso(dt_val: Any) -> Optional[datetime]:
    if dt_val is None:
        return None
    if isinstance(dt_val, datetime):
        return dt_val.replace(tzinfo=timezone.utc) if dt_val.tzinfo is None else dt_val
    try:
        s = str(dt_val).replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
    except Exception:
        return None


def reporting_period_for_previous_calendar_month(
    now: Optional[datetime] = None,
) -> Tuple[datetime, datetime, str, str]:
    """
    Period [start, end] UTC for the last completed calendar month and YYYY-MM key.
    Also returns human label e.g. 'March 2026'.
    """
    now = now or datetime.now(timezone.utc)
    first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_prev = first_this - timedelta(days=1)
    start_prev = end_prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    y, m = start_prev.year, start_prev.month
    _, last_day = monthrange(y, m)
    end_prev_inclusive = start_prev.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999000)
    key = f"{y:04d}-{m:02d}"
    label = start_prev.strftime("%B %Y")
    return start_prev, end_prev_inclusive, key, label


def _applicable_requirement(r: Dict[str, Any]) -> bool:
    if (r.get("applicability") or "").upper() == "NOT_REQUIRED":
        return False
    if (r.get("status") or "").upper() == "NOT_REQUIRED":
        return False
    return True


def _missing_evidence(r: Dict[str, Any]) -> bool:
    if not _applicable_requirement(r):
        return False
    es = (r.get("evidence_state") or "").upper()
    if es == "MISSING":
        return True
    st = (r.get("status") or "").upper()
    if st == "PENDING" and es in ("", "MISSING"):
        return True
    return False


def _days_remaining_or_overdue(due_val: Any, now: datetime) -> Tuple[Optional[int], str]:
    due = _parse_iso(due_val)
    if not due:
        return None, "unknown"
    delta = (due.date() - now.date()).days
    if delta >= 0:
        return delta, "remaining"
    return -delta, "overdue"


def _abs_url(base: str, path: str) -> str:
    p = (path or "").strip()
    if not p:
        return base.rstrip("/") + "/today"
    if p.startswith("http://") or p.startswith("https://"):
        return p
    if not p.startswith("/"):
        p = "/" + p
    return base.rstrip("/") + p


async def assemble_monthly_digest_payload(
    client: Dict[str, Any],
    prefs: Optional[Dict[str, Any]],
    *,
    period_start: datetime,
    period_end: datetime,
    report_month_key: str,
    reporting_month_label: str,
    property_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Full digest model for email + PDF. All counts from live DB + calculate_compliance_score.

    Optional ``property_ids`` restricts property and requirement tables to those IDs (must belong to the client).
    Headline compliance score remains full-account; subset runs do not update monthly_compliance_snapshots.
    """
    from services.compliance_score import calculate_compliance_score
    from services.unified_tasks_service import get_unified_tasks_for_client

    db = database.get_db()
    cid = client["client_id"]
    now = datetime.now(timezone.utc)
    base_url = __import__("utils.app_urls", fromlist=["get_app_base_url"]).get_app_base_url(
        for_email_links=True
    ).strip().rstrip("/")

    score_block = await calculate_compliance_score(cid)
    score = int(score_block.get("score") or 0)
    risk_level = score_to_risk_level(score)
    stats = score_block.get("stats") or {}

    prop_filter_primary = {"client_id": cid, "is_active": {"$ne": False}}
    prop_filter_fallback = {"client_id": cid}
    property_total_count = int(await db.properties.count_documents(prop_filter_primary))
    if property_total_count == 0:
        property_total_count = int(await db.properties.count_documents(prop_filter_fallback))
        prop_active = False
    else:
        prop_active = True

    properties = await db.properties.find(
        prop_filter_primary if prop_active else prop_filter_fallback,
        {"_id": 0},
    ).to_list(DIGEST_MAX_PROPERTIES_FETCH)

    pid_filter: Optional[set] = None
    subset_unknown_ids: List[str] = []
    if property_ids:
        raw_pids = {str(x).strip() for x in property_ids if x and str(x).strip()}
        if raw_pids:
            pid_filter = raw_pids
            known_ids = {p.get("property_id") for p in properties if p.get("property_id")}
            subset_unknown_ids = sorted([x for x in raw_pids if x not in known_ids])
            properties = [p for p in properties if p.get("property_id") in pid_filter]

    requirements = await db.requirements.find({"client_id": cid}, {"_id": 0}).to_list(
        DIGEST_MAX_REQUIREMENTS_FETCH
    )
    requirements_fetch_hit_limit = len(requirements) >= DIGEST_MAX_REQUIREMENTS_FETCH
    if pid_filter:
        requirements = [r for r in requirements if r.get("property_id") in pid_filter]
    from services.requirement_client_runtime_surface import (
        filter_requirement_rows_for_client_runtime_surfaces,
    )

    requirements = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=cid,
        requirements=requirements,
        client_doc=client,
        properties=properties,
    )
    requirements_total_count = len(requirements)
    applicable = [r for r in requirements if _applicable_requirement(r)]

    # Portfolio counts: same aggregates as compliance score / dashboard stats
    total_requirements = int(stats.get("total_requirements") or len(applicable))
    valid_count = int(stats.get("compliant") or 0)
    expiring_soon_count = int(stats.get("expiring_soon") or 0)
    overdue_count = int(stats.get("overdue") or 0)
    missing_evidence_count = sum(1 for r in applicable if _missing_evidence(r))

    ps_iso = period_start.isoformat()
    pe_iso = period_end.isoformat()
    recent_documents = await db.documents.find(
        {
            "client_id": cid,
            "uploaded_at": {"$gte": ps_iso, "$lte": pe_iso},
        },
        {"_id": 0},
    ).to_list(2000)
    if pid_filter:
        recent_documents = [
            d
            for d in recent_documents
            if not d.get("property_id") or d.get("property_id") in pid_filter
        ]
    documents_uploaded_period = len(recent_documents)

    open_wos = await db.work_orders.find(
        {"client_id": cid, "status": {"$nin": ["COMPLETED", "CANCELLED", "CLOSED"]}},
        {"_id": 0, "work_order_id": 1, "work_order_kind": 1, "status": 1, "property_id": 1},
    ).to_list(500)
    if pid_filter:
        open_wos = [w for w in open_wos if w.get("property_id") in pid_filter]
    open_compliance_jobs = sum(
        1 for w in open_wos if str(w.get("work_order_kind") or "").upper() == "COMPLIANCE"
    )
    open_maintenance_jobs = len(open_wos) - open_compliance_jobs

    prop_labels: Dict[str, str] = {}
    for p in properties:
        pid = p.get("property_id")
        if pid:
            prop_labels[pid] = (
                (p.get("nickname") or "").strip()
                or ", ".join(
                    x for x in [(p.get("address_line_1") or "").strip(), (p.get("postcode") or "").strip()] if x
                )
                or str(pid)
            )

    property_rows_pdf: List[Dict[str, Any]] = []
    score_pb = score_block.get("property_breakdown") or []
    pb_map = {x.get("property_id"): x for x in score_pb if x.get("property_id")}
    for p in properties:
        pid = p.get("property_id")
        if not pid:
            continue
        pb = pb_map.get(pid) or {}
        overdue_c = int(pb.get("overdue") or 0)
        exp_c = int(pb.get("expiring") or pb.get("expiring_soon") or 0)
        valid_c = int(pb.get("valid") or 0)
        p_score = p.get("compliance_score")
        if p_score is None:
            p_score = pb.get("score")
        miss_c = sum(
            1
            for r in applicable
            if r.get("property_id") == pid and _missing_evidence(r)
        )
        wo_c = sum(1 for w in open_wos if w.get("property_id") == pid)
        prop_risk = score_to_risk_level(int(p_score)) if p_score is not None else risk_level
        property_rows_pdf.append(
            {
                "property_id": pid,
                "name": prop_labels.get(pid, pid),
                "score": p_score,
                "risk_level": prop_risk,
                "overdue_count": overdue_c,
                "expiring_soon_count": exp_c,
                "valid_count": valid_c,
                "missing_evidence_count": miss_c,
                "open_jobs_count": wo_c,
            }
        )

    requirement_rows_pdf: List[Dict[str, Any]] = []
    for r in sorted(applicable, key=lambda x: (x.get("property_id") or "", x.get("requirement_type") or "")):
        pid = r.get("property_id")
        code = r.get("code") or r.get("requirement_type")
        label = requirement_label(code)
        st = str(authority_runtime_requirement_status(r) or r.get("status") or "").upper()
        ea = r.get("evidence_authority") or {}
        ev_raw = (ea.get("state") or r.get("evidence_state") or "—") if r.get("evidence_authority_synced_at") else (r.get("evidence_state") or "—")
        ev = str(ev_raw).upper()
        eff_dt = get_effective_expiry_date(r)
        date_used_s = eff_dt.isoformat() if eff_dt else ""
        ea_src = (ea.get("expiry_source") or r.get("expiry_source") or "").upper()
        verified = ea_src in ("VERIFIED_DOCUMENT", "CONFIRMED") or (r.get("confidence_state") or "").upper() == "VERIFIED"
        date_kind = "verified" if verified else "estimated"
        days_n, direction = _days_remaining_or_overdue(date_used_s or None, now)
        if st in ("OVERDUE", "EXPIRED"):
            next_action = "Renew or upload compliant evidence urgently."
        elif _missing_evidence(r):
            next_action = "Upload evidence for this requirement."
        elif st == "EXPIRING_SOON":
            next_action = "Plan renewal before the due date."
        elif st == "COMPLIANT":
            next_action = "Monitor upcoming expiry in the calendar."
        else:
            next_action = "Review this item in the requirements workspace."

        requirement_rows_pdf.append(
            {
                "property_name": prop_labels.get(pid, pid or "—"),
                "requirement_name": label,
                "state": compliance_requirement_status_label(st),
                "evidence_state": ev.replace("_", " ").title() if ev else "—",
                "date_used": date_used_s[:10] if date_used_s else "—",
                "date_kind": date_kind,
                "days_value": days_n,
                "days_direction": direction,
                "next_action": next_action,
            }
        )

    def _prop_risk_sort_key(row: Dict[str, Any]) -> tuple:
        ps = row.get("score")
        try:
            ps_i = int(ps) if ps is not None else 101
        except (TypeError, ValueError):
            ps_i = 101
        return (
            -int(row.get("overdue_count") or 0),
            -int(row.get("missing_evidence_count") or 0),
            ps_i,
        )

    digest_email_top_properties_at_risk: List[Dict[str, Any]] = []
    if DIGEST_EMAIL_TOP_PROPERTIES_AT_RISK > 0 and property_rows_pdf:
        for pr in sorted(property_rows_pdf, key=_prop_risk_sort_key)[:DIGEST_EMAIL_TOP_PROPERTIES_AT_RISK]:
            digest_email_top_properties_at_risk.append(
                {
                    "name": pr.get("name"),
                    "score": pr.get("score"),
                    "risk_level": pr.get("risk_level"),
                    "overdue_count": int(pr.get("overdue_count") or 0),
                    "expiring_soon_count": int(pr.get("expiring_soon_count") or 0),
                    "missing_evidence_count": int(pr.get("missing_evidence_count") or 0),
                }
            )

    urgent_items: List[Dict[str, Any]] = []
    try:
        full_tasks = await get_unified_tasks_for_client(cid, raw_limit=80)
        urgent = (full_tasks.get("tasks") or {}).get("urgent") or []
        upcoming = (full_tasks.get("tasks") or {}).get("upcoming") or []
        seen_u = {t.get("id") for t in urgent if t.get("id")}
        ordered_upcoming = [t for t in upcoming if t.get("id") not in seen_u]
        candidates = list(urgent) + ordered_upcoming
        seen = set()
        for t in candidates:
            if len(urgent_items) >= 5:
                break
            tid = t.get("id") or str(t.get("title"))
            if tid in seen:
                continue
            seen.add(tid)
            title = (t.get("title") or "Action item").strip()
            section = (t.get("section") or "").lower()
            p_label = (t.get("property_label") or "").strip()
            suffix = ""
            if section == "urgent":
                if (t.get("overdue_days") or 0) > 0:
                    suffix = " — overdue"
                else:
                    suffix = " — urgent"
            elif t.get("primary_action_type") == "upload_evidence":
                suffix = " — missing evidence"
            else:
                suffix = " — due soon" if section == "upcoming" else ""
            line = f"{title}{suffix}"
            if p_label:
                line = f"{line} ({p_label})"
            url = _abs_url(base_url, t.get("primary_action_url") or "/today")
            urgent_items.append({"line": line, "title": title, "url": url})
    except Exception:
        urgent_items = []

    drivers = score_block.get("drivers") or []
    top_risk_drivers = [str(d) for d in drivers[:5] if d]
    recs = score_block.get("recommendations") or []
    top_next_actions = [str(x) for x in recs[:5] if x]

    fingerprints = build_fingerprint_map(applicable)

    def _labels_for_ids(rids: List[str]) -> List[str]:
        by_id = {str(r.get("requirement_id")): r for r in applicable}
        out: List[str] = []
        for rid in rids[:8]:
            r = by_id.get(rid)
            if not r:
                continue
            code = r.get("code") or r.get("requirement_type")
            pl = prop_labels.get(r.get("property_id"), "")
            out.append(f"{requirement_label(code)}{' — ' + pl if pl else ''}")
        return out

    if pid_filter:
        deltas = {
            "has_prior_snapshot": False,
            "score_delta": None,
            "newly_overdue_ids": [],
            "resolved_improved_ids": [],
            "newly_expiring_ids": [],
            "documents_uploaded_delta_vs_prev_period": None,
            "newly_missing_evidence_delta": None,
            "newly_overdue_labels": [],
            "resolved_improved_labels": [],
            "newly_expiring_labels": [],
            "subset_digest": True,
        }
    else:
        prev_snapshot = await load_latest_snapshot(db, cid)
        deltas = compute_deltas(
            prev_snapshot,
            fingerprints,
            applicable,
            current_score=score,
            current_missing_evidence=missing_evidence_count,
            documents_uploaded_period=documents_uploaded_period,
        )
        deltas["newly_overdue_labels"] = _labels_for_ids(deltas.get("newly_overdue_ids") or [])
        deltas["resolved_improved_labels"] = _labels_for_ids(deltas.get("resolved_improved_ids") or [])
        deltas["newly_expiring_labels"] = _labels_for_ids(deltas.get("newly_expiring_ids") or [])

    crn = (client.get("customer_reference") or "").strip() or None
    account_name = (
        (client.get("company_name") or "").strip()
        or (client.get("full_name") or "").strip()
        or (client.get("contact_name") or "").strip()
        or "Your account"
    )

    digest_prefs = {
        "include_compliance_summary": prefs.get("digest_compliance_summary", True) if prefs else True,
        "include_action_items": prefs.get("digest_action_items", True) if prefs else True,
        "include_upcoming_expiries": prefs.get("digest_upcoming_expiries", True) if prefs else True,
        "include_property_breakdown": prefs.get("digest_property_breakdown", True) if prefs else True,
        "include_recent_documents": prefs.get("digest_recent_documents", True) if prefs else True,
        "include_recommendations": prefs.get("digest_recommendations", True) if prefs else True,
        "include_audit_summary": prefs.get("digest_audit_summary", False) if prefs else False,
    }

    portal_dashboard_url = f"{base_url}/dashboard"
    portal_today_url = f"{base_url}/today"
    portal_requirements_url = f"{base_url}/requirements"

    _jur_notice = build_jurisdiction_compliance_notice(client, properties)

    payload: Dict[str, Any] = {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "report_month_key": report_month_key,
        "reporting_month_label": reporting_month_label,
        "data_as_of": now.isoformat(),
        "generated_at_display": now.strftime("%d %B %Y %H:%M UTC"),
        "client_id": cid,
        "account_name": account_name,
        "client_name": account_name,
        "customer_reference": crn,
        "properties_count": len(properties),
        "digest_property_total_in_account": property_total_count,
        "digest_requirements_total_in_account": requirements_total_count,
        "compliance_score": score,
        "risk_level": risk_level,
        "total_requirements": total_requirements,
        "compliant": valid_count,
        "valid_count": valid_count,
        "overdue": overdue_count,
        "expiring_soon": expiring_soon_count,
        "missing_evidence_count": missing_evidence_count,
        "documents_uploaded": documents_uploaded_period,
        "documents_uploaded_period": documents_uploaded_period,
        "open_compliance_jobs": open_compliance_jobs,
        "open_maintenance_jobs": open_maintenance_jobs,
        "portal_link": portal_today_url,
        "portal_dashboard_url": portal_dashboard_url,
        "portal_today_url": portal_today_url,
        "portal_requirements_url": portal_requirements_url,
        "primary_cta_url": portal_today_url,
        "primary_cta_label": "Review & Fix Compliance Now",
        "urgent_items": urgent_items,
        "deltas": deltas,
        "top_risk_drivers": top_risk_drivers,
        "top_next_actions": top_next_actions,
        "property_rows_pdf": property_rows_pdf,
        "requirement_rows_pdf": requirement_rows_pdf,
        "score_block": score_block,
        "digest_email_top_properties_at_risk": digest_email_top_properties_at_risk,
        "digest_report_kind": "property_subset" if pid_filter else "full",
        "digest_property_subset_ids": sorted(pid_filter) if pid_filter else None,
        "digest_score_scope_note": (
            "Headline score and summary metrics reflect your full account; tables and counts below are limited to the selected properties. "
            "Month-over-month comparison is omitted for subset digests."
            if pid_filter
            else None
        ),
        "digest_subset_unknown_property_ids": subset_unknown_ids or None,
        "digest_jurisdiction_framing": digest_jurisdiction_notice_text(client, properties),
        "digest_jurisdiction_fallback_disclaimer": (
            jurisdiction_default_fallback_report_disclaimer() if _jur_notice.get("active") else None
        ),
        "jurisdiction_compliance_notice": _jur_notice,
        **digest_prefs,
    }

    try:
        from services.portal_activity_service import compute_activity_deltas

        period_act = await compute_activity_deltas(cid, ps_iso, pe_iso)
        payload["digest_period_activity_included"] = True
        payload["digest_period_activity_lines"] = period_act.get("lines") or []
    except Exception:
        payload["digest_period_activity_included"] = False
        payload["digest_period_activity_lines"] = []

    if payload.get("include_action_items", True):
        try:
            from services.unified_tasks_service import get_unified_tasks_digest

            ut_digest = await get_unified_tasks_digest(cid, activity_limit=5)
            summ = ut_digest.get("summary") or {}
            payload["command_centre_digest_included"] = True
            payload["command_centre_urgent_open"] = int(summ.get("urgent_count") or 0)
            payload["command_centre_upcoming_open"] = int(summ.get("upcoming_count") or 0)
            payload["command_centre_in_progress_open"] = int(summ.get("in_progress_count") or 0)
            payload["command_centre_snoozed"] = int(summ.get("snoozed_count") or 0)
            payload["command_centre_recent_activity_lines"] = _digest_inbox_activity_lines(
                ut_digest.get("activity_feed") or [],
                limit=5,
            )
        except Exception:
            payload["command_centre_digest_included"] = False

    subj_suffix = " (selected properties)" if pid_filter else ""
    payload["subject"] = f"Monthly Compliance Summary — {reporting_month_label}{subj_suffix}"
    payload["email_header_title"] = f"Monthly Compliance Summary — {reporting_month_label}{subj_suffix}"
    payload["_requirement_fingerprints"] = fingerprints

    trunc_reasons: List[str] = []
    trunc_lines: List[str] = []
    if subset_unknown_ids:
        trunc_reasons.append("SUBSET_UNKNOWN_PROPERTY_IDS")
        trunc_lines.append(
            "Unknown or out-of-scope property_ids requested (ignored): "
            + ", ".join(subset_unknown_ids[:12])
            + ("…" if len(subset_unknown_ids) > 12 else "")
        )
    if property_total_count > DIGEST_MAX_PROPERTIES_FETCH:
        trunc_reasons.append("PROPERTIES_QUERY_LIMIT")
        trunc_lines.append(
            f"This account has {property_total_count} properties; only the first "
            f"{DIGEST_MAX_PROPERTIES_FETCH} included in this report are reflected in portfolio detail. "
            "See the portal for the full portfolio."
        )
    if requirements_fetch_hit_limit:
        trunc_reasons.append("REQUIREMENTS_QUERY_LIMIT")
        trunc_lines.append(
            f"This digest loads at most {DIGEST_MAX_REQUIREMENTS_FETCH} requirement rows from the database "
            "for detailed listing and period comparison; additional rows may exist. "
            "Open the portal for the complete requirement register."
        )
    n_req_rows = len(requirement_rows_pdf)
    if n_req_rows > DIGEST_PDF_MAX_REQUIREMENT_ROWS:
        trunc_reasons.append("PDF_REQUIREMENT_LIST_LIMIT")
        omitted = n_req_rows - DIGEST_PDF_MAX_REQUIREMENT_ROWS
        trunc_lines.append(
            f"The PDF lists {DIGEST_PDF_MAX_REQUIREMENT_ROWS} of {n_req_rows} requirements ({omitted} omitted); "
            "open the portal for the full requirement register."
        )
    payload["digest_truncated"] = bool(trunc_reasons)
    payload["digest_truncation_reasons"] = trunc_reasons
    payload["digest_truncation_display_lines"] = trunc_lines
    payload["digest_pdf_requirement_rows_total"] = n_req_rows
    payload["digest_pdf_requirement_rows_omitted"] = max(0, n_req_rows - DIGEST_PDF_MAX_REQUIREMENT_ROWS)

    return payload
