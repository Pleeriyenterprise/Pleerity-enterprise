"""
Property-scoped tenant/occupancy operational summary (read-only aggregation).

Authority: composes existing domains — does NOT own rent ledger, maintenance, or tenant CRUD truth.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import database


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _portal_activity_label(tenant: Dict[str, Any]) -> str:
    from services.tenant_portal_service import portal_activity_label

    return portal_activity_label(tenant)


async def build_property_occupancy_operational_summary(
    client_id: str,
    property_id: str,
    *,
    include_rent: bool = True,
    include_maintenance: bool = True,
    include_tenant_portal: bool = True,
) -> Dict[str, Any]:
    db = database.get_db()
    prop = await db.properties.find_one(
        {"client_id": client_id, "property_id": property_id},
        {
            "_id": 0,
            "property_id": 1,
            "nickname": 1,
            "address_line_1": 1,
            "postcode": 1,
            "occupancy": 1,
            "tenancy_active": 1,
            "bedrooms": 1,
            "property_type": 1,
        },
    )
    if not prop:
        raise ValueError("Property not found")

    now = datetime.now(timezone.utc)
    summary: Dict[str, Any] = {
        "property_id": property_id,
        "generated_at_utc": now.isoformat(),
        "authority_note": "Derived operational aggregation. Live truth remains in rent ops, maintenance, and tenant workspace.",
        "applicability": {
            "occupancy": prop.get("occupancy"),
            "tenancy_active": prop.get("tenancy_active"),
            "bedrooms": prop.get("bedrooms"),
            "property_type": prop.get("property_type"),
        },
        "active_tenants": [],
        "tenancy_lifecycle": {
            "tenancy_active": prop.get("tenancy_active"),
            "occupancy": prop.get("occupancy"),
            "move_state": "active" if prop.get("tenancy_active") else "unknown_or_vacant",
        },
        "rent_status": None,
        "open_maintenance": {"open_issues_count": 0, "tenant_reported_open": 0, "active_work_orders": 0, "items": []},
        "certificate_requests": [],
        "compliance_pack_deliveries": [],
        "reminder_history": [],
        "upcoming_visits": [],
        "portal_activity": [],
        "operational_alerts": [],
        "deep_links": {
            "tenants": "/tenants",
            "tenant_delivery": f"/tenants/delivery?property_id={property_id}",
            "rent_operations": f"/operations/rent?property_id={property_id}",
            "maintenance": f"/properties/{property_id}?tab=maintenance",
            "calendar": "/calendar",
        },
    }

    if include_tenant_portal:
        tenants = await db.portal_users.find(
            {"client_id": client_id, "role": "ROLE_TENANT"},
            {"_id": 0, "password_hash": 0},
        ).to_list(200)
        tenant_ids = [t["portal_user_id"] for t in tenants]
        assignments = await db.tenant_assignments.find(
            {"tenant_id": {"$in": tenant_ids}, "property_id": property_id},
            {"_id": 0},
        ).to_list(50)
        assigned_ids = {a["tenant_id"] for a in assignments}
        for t in tenants:
            if t["portal_user_id"] not in assigned_ids:
                continue
            row = {
                "tenant_id": t["portal_user_id"],
                "email": t.get("auth_email"),
                "full_name": t.get("full_name") or t.get("name"),
                "status": t.get("status"),
                "password_status": t.get("password_status"),
                "portal_invite_sent_at": _iso(t.get("portal_invite_sent_at")),
                "last_login_at": _iso(t.get("last_login")),
                "portal_activity": _portal_activity_label(
                    {**t, "assigned_properties": [property_id]}
                ),
            }
            summary["active_tenants"].append(row)
            summary["portal_activity"].append(
                {
                    "tenant_id": t["portal_user_id"],
                    "label": row["full_name"] or row["email"],
                    "activity": row["portal_activity"],
                    "last_login_at": row["last_login_at"],
                }
            )

        cert_cursor = db.tenant_requests.find(
            {"client_id": client_id, "property_id": property_id},
            {"_id": 0},
        ).sort("created_at", -1).limit(15)
        for r in await cert_cursor.to_list(15):
            summary["certificate_requests"].append(
                {
                    "request_id": r.get("request_id"),
                    "tenant_name": r.get("tenant_name"),
                    "certificate_type": r.get("certificate_type"),
                    "status": r.get("status"),
                    "created_at": _iso(r.get("created_at")),
                    "linked_work_order_id": r.get("linked_work_order_id"),
                }
            )

        msg_count = await db.tenant_messages.count_documents({"client_id": client_id, "property_id": property_id})
        if msg_count:
            summary["operational_alerts"].append(
                {"kind": "tenant_messages", "count": msg_count, "severity": "medium", "route": "/tenants/messages"}
            )

        delivery_cursor = db.tenant_delivery_proofs.find(
            {"client_id": client_id, "property_id": property_id},
            {"_id": 0, "delivery_id": 1, "sent_at": 1, "created_at": 1, "status": 1, "tenant_email": 1},
        ).sort("created_at", -1).limit(10)
        for d in await delivery_cursor.to_list(10):
            summary["compliance_pack_deliveries"].append(
                {
                    "delivery_id": d.get("delivery_id"),
                    "sent_at": _iso(d.get("sent_at") or d.get("created_at")),
                    "status": d.get("status"),
                    "tenant_email": d.get("tenant_email"),
                }
            )

    if include_maintenance:
        from services.maintenance_issues_service import SOURCE_TENANT_REQUEST
        from services.maintenance_service import STATUS_COMPLETED, WORK_ORDER_KIND_COMPLIANCE

        open_issues = await db.maintenance_issues.find(
            {
                "client_id": client_id,
                "property_id": property_id,
                "status": {"$nin": ["resolved", "closed", "cancelled"]},
            },
            {"_id": 0, "issue_id": 1, "title": 1, "status": 1, "source": 1, "severity": 1, "created_at": 1},
        ).sort("created_at", -1).limit(12).to_list(12)
        tenant_reported = [i for i in open_issues if i.get("source") in (SOURCE_TENANT_REQUEST, "tenant")]
        summary["open_maintenance"] = {
            "open_issues_count": len(open_issues),
            "tenant_reported_open": len(tenant_reported),
            "items": [
                {
                    "issue_id": i.get("issue_id"),
                    "title": i.get("title"),
                    "status": i.get("status"),
                    "source": i.get("source"),
                    "severity": i.get("severity"),
                    "created_at": _iso(i.get("created_at")),
                }
                for i in open_issues[:8]
            ],
        }
        active_wo = await db.work_orders.find(
            {
                "client_id": client_id,
                "property_id": property_id,
                "status": {"$nin": [STATUS_COMPLETED, "CANCELLED", "CLOSED"]},
            },
            {"_id": 0, "work_order_id": 1, "status": 1, "schedule_status": 1, "scheduled_at": 1, "work_order_kind": 1},
        ).sort("updated_at", -1).limit(8).to_list(8)
        summary["open_maintenance"]["active_work_orders"] = len(active_wo)
        for wo in active_wo:
            if wo.get("scheduled_at"):
                summary["upcoming_visits"].append(
                    {
                        "kind": "work_order_visit",
                        "work_order_id": wo.get("work_order_id"),
                        "schedule_status": wo.get("schedule_status"),
                        "scheduled_at": _iso(wo.get("scheduled_at")),
                        "title": "Compliance inspection" if wo.get("work_order_kind") == WORK_ORDER_KIND_COMPLIANCE else "Repair visit",
                        "note": "Scheduled visit does not mean issue resolved.",
                    }
                )
        if open_issues:
            summary["operational_alerts"].append(
                {
                    "kind": "open_maintenance",
                    "count": len(open_issues),
                    "severity": "high" if tenant_reported else "medium",
                    "route": f"/properties/{property_id}?tab=maintenance",
                }
            )

    if include_rent:
        from services import rent_ledger_service
        from services.property_expense_service import get_property_financial_snapshot

        rent_summary = await rent_ledger_service.get_rent_summary(client_id, property_id=property_id)
        fin = await get_property_financial_snapshot(client_id, property_id)
        last_paid = await db.rent_payments.find(
            {"client_id": client_id, "property_id": property_id},
            {"_id": 0, "payment_date": 1, "amount_minor": 1},
        ).sort("payment_date", -1).limit(1).to_list(1)
        last_payment_at = _iso(last_paid[0].get("payment_date")) if last_paid else None

        summary["rent_status"] = {
            "authority": "rent_operations",
            "currency": rent_summary.get("currency") or fin.get("currency"),
            "overdue_count": rent_summary.get("overdue_count") or 0,
            "severely_overdue_count": rent_summary.get("severely_overdue_count") or 0,
            "partially_paid_count": rent_summary.get("partially_paid_count") or 0,
            "upcoming_due_count": rent_summary.get("upcoming_due_count") or 0,
            "total_outstanding_minor": rent_summary.get("total_outstanding_minor") or 0,
            "rent_collected_this_month_minor": rent_summary.get("rent_collected_this_month_minor") or 0,
            "last_payment_at": last_payment_at,
            "disclaimer": "Financial authority: Rent Operations. Snapshot is operational, not accounting truth.",
        }

        reminder_cursor = db.rent_reminder_events.find(
            {"client_id": client_id, "property_id": property_id},
            {"_id": 0, "reminder_key": 1, "reminder_type": 1, "sent_at": 1, "channel": 1},
        ).sort("sent_at", -1).limit(10)
        for rem in await reminder_cursor.to_list(10):
            summary["reminder_history"].append(
                {
                    "reminder_key": rem.get("reminder_key"),
                    "reminder_type": rem.get("reminder_type"),
                    "sent_at": _iso(rem.get("sent_at")),
                    "channel": rem.get("channel"),
                    "note": "Reminder sent does not mean rent resolved.",
                }
            )

        if (rent_summary.get("overdue_count") or 0) > 0:
            summary["operational_alerts"].append(
                {
                    "kind": "rent_overdue",
                    "count": rent_summary.get("overdue_count"),
                    "severity": "critical" if (rent_summary.get("severely_overdue_count") or 0) > 0 else "high",
                    "route": f"/operations/rent?property_id={property_id}",
                }
            )

    # Calendar-derived visits (requirements expiring + confirmed visits) — scheduling authority
    try:
        from services.client_calendar_timeline_service import get_timeline_events_for_range, filter_timeline_events

        start = now - timedelta(days=30)
        end = now + timedelta(days=90)
        raw = await get_timeline_events_for_range(client_id, start, end, include_work_orders=True)
        events = [e for e in filter_timeline_events(raw) if str(e.get("property_id") or "") == property_id]
        for e in events[:12]:
            et = str(e.get("event_type") or "")
            if "visit" in et or e.get("event_type") in ("requirement_expiring_soon", "requirement_overdue"):
                summary["upcoming_visits"].append(
                    {
                        "kind": e.get("event_category"),
                        "event_type": et,
                        "date": e.get("date"),
                        "title": e.get("title"),
                        "note": "Scheduled or due date is not resolution proof.",
                    }
                )
    except Exception:
        pass

    pending_certs = [r for r in summary["certificate_requests"] if str(r.get("status") or "").lower() not in ("completed", "closed", "cancelled")]
    if pending_certs:
        summary["operational_alerts"].append(
            {
                "kind": "certificate_requests",
                "count": len(pending_certs),
                "severity": "medium",
                "route": "/tenants/certificate-requests",
            }
        )

    pending_invites = [t for t in summary["active_tenants"] if t.get("portal_activity") == "pending_invite"]
    if pending_invites:
        summary["operational_alerts"].append(
            {"kind": "pending_tenant_invite", "count": len(pending_invites), "severity": "low", "route": "/tenants"}
        )

    summary["counts"] = {
        "active_tenants": len(summary["active_tenants"]),
        "open_issues": summary["open_maintenance"]["open_issues_count"],
        "pending_certificate_requests": len(pending_certs),
        "operational_alerts": len(summary["operational_alerts"]),
    }
    return summary
