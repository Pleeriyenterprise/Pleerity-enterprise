"""
Property Activity & Evidence Report — organises CVP records for a landlord.

Not a legal certification. Does not claim tribunal, court, or council sufficiency.
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import database
from presentation.property_display_name import get_property_display_name
from report_presentation.timeline import present_timeline_row

DISCLAIMER = (
    "This Property Activity & Evidence Report organises records stored in CVP for the selected "
    "property and date range. It does not determine legal sufficiency, tribunal outcome, or "
    "regulatory approval."
)
REPORT_TITLE = "Property Activity & Evidence Report"


def _parse_bound(value: Optional[str], *, end: bool = False) -> datetime:
    raw = (value or "").strip()
    if not raw:
        now = datetime.now(timezone.utc)
        return now if end else now - timedelta(days=365)
    try:
        if len(raw) == 10:
            dt = datetime.fromisoformat(raw)
            if end:
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        now = datetime.now(timezone.utc)
        return now if end else now - timedelta(days=365)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _in_range(ts: Any, start: datetime, end: datetime) -> bool:
    if ts is None:
        return False
    try:
        if hasattr(ts, "timestamp"):
            dt = ts if getattr(ts, "tzinfo", None) else ts.replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return start <= dt <= end
    except Exception:
        return False


def _esc(value: Any) -> str:
    return html.escape(str(value or "").strip())


async def build_property_activity_evidence_report(
    client_id: str,
    property_id: str,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Dict[str, Any]:
    db = database.get_db()
    prop = await db.properties.find_one(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    )
    if not prop:
        raise ValueError("PROPERTY_NOT_FOUND")

    start = _parse_bound(from_date, end=False)
    end = _parse_bound(to_date, end=True)
    property_name = get_property_display_name(prop)
    client_row = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "crn": 1, "client_id": 1}) or {}

    tenancies = await db.property_tenancies.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    ).sort("started_at", -1).to_list(20)

    schedules = await db.rent_schedules.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    ).sort("start_date", -1).to_list(20)

    periods = await db.rent_ledger_periods.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    ).sort("period_start", -1).to_list(50)

    payments = await db.rent_payments.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    ).sort("payment_date", -1).to_list(50)

    issues = await db.maintenance_issues.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(50)

    work_orders = await db.work_orders.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(50)

    contractor_ids = [wo.get("contractor_id") for wo in work_orders if wo.get("contractor_id")]
    contractors = []
    if contractor_ids:
        contractors = await db.contractors.find(
            {"contractor_id": {"$in": contractor_ids}},
            {"_id": 0, "contractor_id": 1, "company_name": 1, "name": 1, "trade_types": 1},
        ).to_list(len(contractor_ids))
    contractor_by_id = {c.get("contractor_id"): c for c in contractors}

    requirements = await db.requirements.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0, "requirement_id": 1, "requirement_code": 1, "name": 1, "status": 1, "due_date": 1, "expiry_date": 1},
    ).to_list(100)

    wo_ids = [wo.get("work_order_id") for wo in work_orders if wo.get("work_order_id")]
    audit_q: Dict[str, Any] = {
        "client_id": client_id,
        "$or": [
            {"metadata.property_id": property_id},
            {"resource_id": property_id},
            {"resource_id": {"$in": wo_ids}} if wo_ids else {"resource_id": property_id},
        ],
    }
    audit_logs = await db.audit_logs.find(audit_q, {"_id": 0}).sort("timestamp", -1).to_list(200)

    chronology: List[Dict[str, Any]] = []
    for log in audit_logs:
        ts = log.get("timestamp")
        if not _in_range(ts, start, end):
            continue
        md = log.get("metadata") if isinstance(log.get("metadata"), dict) else {}
        md = {**md, "property_name": property_name}
        cid = md.get("contractor_id") or log.get("resource_id")
        if cid in contractor_by_id:
            md["contractor_name"] = contractor_by_id[cid].get("company_name") or contractor_by_id[cid].get("name")
        wo_id = md.get("work_order_id") or (log.get("resource_id") if log.get("resource_type") == "work_order" else None)
        if wo_id:
            wo = next((w for w in work_orders if w.get("work_order_id") == wo_id), None)
            if wo and not md.get("description"):
                md["description"] = wo.get("description")
            if wo and wo.get("contractor_id") in contractor_by_id and not md.get("contractor_name"):
                c = contractor_by_id[wo["contractor_id"]]
                md["contractor_name"] = c.get("company_name") or c.get("name")
        presented = present_timeline_row({**log, "metadata": md})
        chronology.append(
            {
                "timestamp": _iso(ts),
                "headline": presented.get("business_event"),
                "summary": presented.get("summary"),
                "action": log.get("action"),
            }
        )

    for wo in work_orders:
        if not _in_range(wo.get("created_at"), start, end):
            continue
        if any(c.get("action") == "WORK_ORDER_CREATED" and c.get("summary") and wo.get("description") and wo.get("description")[:40] in (c.get("summary") or "") for c in chronology):
            continue
        c = contractor_by_id.get(wo.get("contractor_id") or "") or {}
        who = c.get("company_name") or c.get("name") or ""
        title = (wo.get("description") or "Maintenance job").strip()[:80]
        chronology.append(
            {
                "timestamp": _iso(wo.get("created_at")),
                "headline": "Maintenance job created",
                "summary": f"A job was created for “{title}” at {property_name}.",
                "action": "WORK_ORDER_CREATED",
            }
        )
        if wo.get("contractor_id") and _in_range(wo.get("updated_at") or wo.get("created_at"), start, end) and who:
            chronology.append(
                {
                    "timestamp": _iso(wo.get("updated_at") or wo.get("created_at")),
                    "headline": "Contractor assigned",
                    "summary": f"{who} was assigned to “{title}” at {property_name}.",
                    "action": "CONTRACTOR_ASSIGNED_TO_WORK_ORDER",
                }
            )

    chronology.sort(key=lambda row: row.get("timestamp") or "", reverse=False)
    # De-duplicate identical summary+timestamp
    seen = set()
    unique: List[Dict[str, Any]] = []
    for row in chronology:
        key = (row.get("timestamp"), row.get("summary"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)

    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "report_title": REPORT_TITLE,
        "disclaimer": DISCLAIMER,
        "generated_at": generated_at,
        "date_range": {"from": start.date().isoformat(), "to": end.date().isoformat()},
        "property": {
            "property_id": property_id,
            "name": property_name,
            "address_line_1": prop.get("address_line_1"),
            "postcode": prop.get("postcode"),
            "occupancy": prop.get("occupancy"),
            "tenancy_active": prop.get("tenancy_active"),
        },
        "account": {
            "client_id": client_id,
            "account_reference": client_row.get("crn") or client_id,
        },
        "tenancies": [
            {
                "tenancy_id": t.get("tenancy_id"),
                "tenant_display_name": t.get("tenant_display_name"),
                "status": t.get("status"),
                "started_at": _iso(t.get("started_at")),
                "ended_at": _iso(t.get("ended_at")),
                "rent_tracking_enabled": bool(t.get("rent_tracking_enabled")),
            }
            for t in tenancies
        ],
        "compliance": [
            {
                "name": r.get("name") or r.get("requirement_code"),
                "status": r.get("status"),
                "due_date": _iso(r.get("due_date")),
                "expiry_date": _iso(r.get("expiry_date")),
            }
            for r in requirements
        ],
        "maintenance": [
            {
                "work_order_id": wo.get("work_order_id"),
                "description": wo.get("description"),
                "category": wo.get("category"),
                "status": wo.get("status"),
                "severity": wo.get("severity"),
                "contractor_name": (
                    (contractor_by_id.get(wo.get("contractor_id") or "") or {}).get("company_name")
                    or (contractor_by_id.get(wo.get("contractor_id") or "") or {}).get("name")
                ),
                "created_at": _iso(wo.get("created_at")),
                "completed_at": _iso(wo.get("completed_at")),
            }
            for wo in work_orders
            if _in_range(wo.get("created_at"), start, end) or _in_range(wo.get("updated_at"), start, end)
        ],
        "issues": [
            {
                "description": i.get("description"),
                "category": i.get("category"),
                "status": i.get("status"),
                "created_at": _iso(i.get("created_at")),
            }
            for i in issues
            if _in_range(i.get("created_at"), start, end)
        ],
        "rent": {
            "schedules": [
                {
                    "tenant_name": s.get("tenant_name"),
                    "expected_amount_minor": s.get("expected_amount_minor"),
                    "rent_frequency": s.get("rent_frequency"),
                    "start_date": s.get("start_date"),
                    "due_day": s.get("due_day"),
                    "status": s.get("status"),
                }
                for s in schedules
            ],
            "periods": [
                {
                    "period_start": p.get("period_start"),
                    "expected_amount_minor": p.get("expected_amount_minor"),
                    "received_amount_minor": p.get("received_amount_minor"),
                    "outstanding_amount_minor": p.get("outstanding_amount_minor"),
                    "status": p.get("status"),
                }
                for p in periods
            ],
            "payments": [
                {
                    "payment_date": p.get("payment_date"),
                    "amount_minor": p.get("amount_minor"),
                    "method": p.get("method") or p.get("payment_method"),
                }
                for p in payments
                if _in_range(p.get("payment_date"), start, end)
            ],
        },
        "contractors": [
            {
                "name": c.get("company_name") or c.get("name"),
                "trade_types": c.get("trade_types") or [],
            }
            for c in contractors
        ],
        "chronology": unique,
    }


def render_property_activity_evidence_html(report: Dict[str, Any]) -> str:
    prop = report.get("property") or {}
    account = report.get("account") or {}
    dr = report.get("date_range") or {}
    rows = []
    for ev in report.get("chronology") or []:
        rows.append(
            f"<li><time>{_esc(ev.get('timestamp'))}</time> "
            f"<strong>{_esc(ev.get('headline'))}</strong> — {_esc(ev.get('summary'))}</li>"
        )
    chrono = "".join(rows) or "<li>No activity recorded in this date range.</li>"
    tenancy_rows = "".join(
        f"<li>{_esc(t.get('tenant_display_name') or 'Tenancy')} "
        f"({_esc(t.get('status'))}) from {_esc(t.get('started_at'))}</li>"
        for t in report.get("tenancies") or []
    ) or "<li>No rent tenancy records.</li>"
    compliance_rows = "".join(
        f"<li>{_esc(c.get('name'))}: {_esc(c.get('status'))}"
        f"{' · due ' + _esc(c.get('due_date')) if c.get('due_date') else ''}</li>"
        for c in report.get("compliance") or []
    ) or "<li>No compliance requirements listed.</li>"
    maint_rows = "".join(
        f"<li>{_esc(m.get('description'))} "
        f"({_esc(m.get('category'))}, {_esc(m.get('status'))})"
        f"{' — ' + _esc(m.get('contractor_name')) if m.get('contractor_name') else ''}</li>"
        for m in report.get("maintenance") or []
    ) or "<li>No maintenance jobs in this range.</li>"
    rent = report.get("rent") or {}
    pay_rows = "".join(
        f"<li>{_esc(p.get('payment_date'))}: {int(p.get('amount_minor') or 0) / 100:.2f}</li>"
        for p in rent.get("payments") or []
    ) or "<li>No rent payments in this range.</li>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{_esc(report.get('report_title'))}</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 2rem auto; max-width: 52rem; color: #122; }}
    h1, h2 {{ font-family: system-ui, sans-serif; color: #0b1f3a; }}
    .meta {{ color: #445; font-size: 0.95rem; }}
    .disclaimer {{ border: 1px solid #c9d4; background: #f6f8fb; padding: 0.75rem 1rem; }}
    ul {{ line-height: 1.5; }}
    time {{ display: inline-block; min-width: 12rem; color: #456; }}
  </style>
</head>
<body>
  <h1>{_esc(report.get('report_title'))}</h1>
  <p class="disclaimer">{_esc(report.get('disclaimer'))}</p>
  <p class="meta">
    Property: <strong>{_esc(prop.get('name'))}</strong><br/>
    Account: {_esc(account.get('account_reference'))}<br/>
    Date range: {_esc(dr.get('from'))} to {_esc(dr.get('to'))}<br/>
    Generated: {_esc(report.get('generated_at'))}
  </p>
  <h2>Property identity</h2>
  <p>{_esc(prop.get('address_line_1'))} {_esc(prop.get('postcode'))}</p>
  <h2>Tenancy</h2>
  <ul>{tenancy_rows}</ul>
  <h2>Compliance</h2>
  <ul>{compliance_rows}</ul>
  <h2>Maintenance</h2>
  <ul>{maint_rows}</ul>
  <h2>Rent payments</h2>
  <ul>{pay_rows}</ul>
  <h2>Chronological activity</h2>
  <ul>{chrono}</ul>
</body>
</html>
"""
