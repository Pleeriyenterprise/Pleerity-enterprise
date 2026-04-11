"""Background jobs for reminders and digests - Compliance Vault Pro"""
import asyncio
import base64
import calendar
import html
import json
import uuid
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta, timezone
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

from utils.expiry_utils import get_effective_expiry_date, get_computed_status, is_included_for_calendar
from services.reminder_truth_service import (
    evaluate_requirement_for_daily_reminder,
    mark_requirement_reminder_sent,
    get_pending_verification_snapshot,
    get_reminder_cooldown_hours,
)
from presentation.label_service import requirement_label

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)


def effective_digest_calendar_day(day_preference: int, when: datetime) -> int:
    """
    Map user preference (1–31) to the actual calendar day in ``when``'s month.
    E.g. preference 31 in April → 30; in February → 28 or 29 (leap).
    """
    try:
        dp = int(day_preference)
    except (TypeError, ValueError):
        dp = 1
    dp = max(1, min(31, dp))
    last_dom = calendar.monthrange(when.year, when.month)[1]
    return min(dp, last_dom)


def _reminder_item_label_from_req(current_req: dict) -> str:
    desc = (current_req.get("description") or "").strip()
    if desc:
        return desc
    code = current_req.get("code") or current_req.get("requirement_type") or current_req.get("requirement_code")
    return requirement_label(code) if code else "Certificate"


def _format_digest_inbox_activity_lines(activity_feed, limit: int = 5):
    """Short lines for monthly digest from real client_task_activity_log rows (newest first in feed)."""
    out = []
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


# Status severity ranking (lower is better)
STATUS_SEVERITY = {
    "GREEN": 0,
    "AMBER": 1,
    "RED": 2
}

def get_status_color(status):
    """Get CSS color for compliance status."""
    return {
        "GREEN": "#22c55e",
        "AMBER": "#f59e0b",
        "RED": "#dc2626"
    }.get(status, "#64748b")

class JobScheduler:
    def __init__(self):
        self.mongo_url = os.environ['MONGO_URL']
        self.db_name = os.environ['DB_NAME']
        self.client = None
        self.db = None
    
    async def connect(self):
        self.client = AsyncIOMotorClient(self.mongo_url)
        self.db = self.client[self.db_name]
        logger.info("Job scheduler connected to MongoDB")
    
    async def close(self):
        if self.client:
            self.client.close()
    
    async def send_daily_reminders(self, client_id: Optional[str] = None):
        """Send daily compliance reminders for expiring requirements.
        Respects user notification preferences.
        
        IMPORTANT: Only runs for clients with ENABLED entitlement.
        Clients with LIMITED or DISABLED entitlement do not receive reminders.

        When ``client_id`` is set (admin scoped run), only that client is evaluated.
        """
        logger.info("Running daily reminder job...")
        
        try:
            base_q = {
                "subscription_status": "ACTIVE",
                "entitlement_status": {"$in": ["ENABLED", None]},  # None for legacy compatibility
            }
            if client_id and str(client_id).strip():
                cid = str(client_id).strip()
                one = await self.db.clients.find_one({**base_q, "client_id": cid}, {"_id": 0})
                if not one:
                    return {
                        "message": f"Client not found or not eligible for reminders: {cid}",
                        "count": 0,
                        "outcome_status": "failed",
                        "error_message": "Client not found or not ACTIVE / not entitled",
                        "outcome_metrics": {"expected_count": 1, "attempted_count": 0, "success_count": 0, "failed_count": 1},
                    }
                clients = [one]
            else:
                clients = await self.db.clients.find(base_q, {"_id": 0}).to_list(1000)
            
            attempted_count = 0
            success_count = 0
            failed_count = 0
            skipped_count = 0
            evaluated_items_count = 0
            suppressed_items_count = 0
            suppressed_by_reason = {}

            for client in clients:
                # Check notification preferences
                prefs = await self.db.notification_preferences.find_one(
                    {"client_id": client["client_id"]},
                    {"_id": 0}
                )
                
                # Default to enabled if no preferences set
                reminders_enabled = prefs.get("expiry_reminders", True) if prefs else True
                reminder_days = prefs.get("reminder_days_before", 30) if prefs else 30
                daily_reminder_enabled = prefs.get("daily_reminder_enabled", True) if prefs else True
                
                if not reminders_enabled:
                    logger.info(f"Skipping reminders for {client['email']} - disabled in preferences")
                    continue
                if not daily_reminder_enabled:
                    logger.info(f"Skipping reminders for {client['email']} - daily reminder disabled in preferences")
                    continue
                if self._is_in_quiet_hours(prefs):
                    logger.info(f"Skipping reminders for {client['email']} - within quiet hours")
                    continue
                
                # Get all requirements for client; use effective expiry (confirmed else extracted else due_date); exclude NOT_REQUIRED
                requirements = await self.db.requirements.find(
                    {"client_id": client["client_id"]},
                    {"_id": 0}
                ).to_list(500)

                # Resolve property addresses once for reminder content
                property_ids = list({r.get("property_id") for r in requirements if r.get("property_id")})
                properties_map = {}
                if property_ids:
                    props_cursor = self.db.properties.find(
                        {"property_id": {"$in": property_ids}},
                        {"_id": 0, "property_id": 1, "address_line_1": 1, "city": 1, "postcode": 1, "nickname": 1}
                    )
                    async for p in props_cursor:
                        addr = p.get("nickname") or p.get("address_line_1") or "Your property"
                        if p.get("city") or p.get("postcode"):
                            addr = f"{addr}, {p.get('city', '')} {p.get('postcode', '')}".strip(", ")
                        properties_map[p["property_id"]] = addr or "Your property"

                expiring_requirements = []
                overdue_requirements = []
                reminder_refs = []  # For message_logs: client_id on log; refs list here
                properties_status_changed = set()
                now_utc = datetime.now(timezone.utc)

                for req in requirements:
                    if not is_included_for_calendar(req):
                        continue
                    cooldown_hours = get_reminder_cooldown_hours("DAILY_COMPLIANCE_EXPIRY_EMAIL")
                    evaluated_items_count += 1
                    truth = await evaluate_requirement_for_daily_reminder(
                        self.db,
                        req,
                        reminder_days=reminder_days,
                        cooldown_hours=cooldown_hours,
                        reminder_type="DAILY_COMPLIANCE_EXPIRY_EMAIL",
                    )
                    if not truth.get("eligible"):
                        suppressed_items_count += 1
                        reason = truth.get("suppression_reason") or "UNKNOWN"
                        suppressed_by_reason[reason] = int(suppressed_by_reason.get(reason, 0)) + 1
                        continue
                    current_req = truth.get("current_requirement") or req
                    due_date = get_effective_expiry_date(current_req)
                    if due_date is None:
                        continue
                    days_until_due = (due_date - now_utc).days

                    if days_until_due < 0:
                        prop_addr = properties_map.get(current_req.get("property_id"), "Your property")
                        overdue_requirements.append({
                            "type": _reminder_item_label_from_req(current_req),
                            "code": current_req.get("code") or current_req.get("requirement_type") or "",
                            "due_date": due_date.strftime("%d %B %Y"),
                            "days_overdue": -days_until_due,
                            "property_address": prop_addr,
                            "__state_key": truth.get("state_key"),
                        })
                        reminder_refs.append({
                            "property_id": current_req.get("property_id"),
                            "requirement_type": current_req.get("requirement_type", ""),
                            "due_date": due_date.strftime("%Y-%m-%d"),
                            "requirement_id": current_req.get("requirement_id"),
                        })
                        await self.db.requirements.update_one(
                            {"requirement_id": current_req["requirement_id"]},
                            {"$set": {"status": "OVERDUE"}}
                        )
                        properties_status_changed.add(current_req.get("property_id"))
                    elif 0 <= days_until_due <= reminder_days:
                        prop_addr = properties_map.get(current_req.get("property_id"), "Your property")
                        expiring_requirements.append({
                            "type": _reminder_item_label_from_req(current_req),
                            "code": current_req.get("code") or current_req.get("requirement_type") or "",
                            "due_date": due_date.strftime("%d %B %Y"),
                            "days_remaining": days_until_due,
                            "status": "URGENT" if days_until_due <= 7 else "WARNING",
                            "property_address": prop_addr,
                            "__state_key": truth.get("state_key"),
                        })
                        reminder_refs.append({
                            "property_id": current_req.get("property_id"),
                            "requirement_type": current_req.get("requirement_type", ""),
                            "due_date": due_date.strftime("%Y-%m-%d"),
                            "requirement_id": current_req.get("requirement_id"),
                        })
                        await self.db.requirements.update_one(
                            {"requirement_id": current_req["requirement_id"]},
                            {"$set": {"status": "EXPIRING_SOON"}}
                        )
                        properties_status_changed.add(current_req.get("property_id"))
                
                # Enqueue compliance recalc for properties whose requirement status changed
                if properties_status_changed:
                    from services.compliance_recalc_queue import enqueue_compliance_recalc
                    from services.compliance_recalc_queue import TRIGGER_EXPIRY_JOB, ACTOR_SYSTEM
                    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    for property_id in properties_status_changed:
                        if not property_id:
                            continue
                        await enqueue_compliance_recalc(
                            property_id=property_id,
                            client_id=client["client_id"],
                            trigger_reason=TRIGGER_EXPIRY_JOB,
                            actor_type=ACTOR_SYSTEM,
                            actor_id=None,
                            correlation_id=f"REMINDER_JOB:{property_id}:{date_str}",
                        )
                
                # Send reminder if there are expiring or overdue requirements
                if expiring_requirements or overdue_requirements:
                    all_state_keys = []
                    for row in overdue_requirements + expiring_requirements:
                        sk = row.pop("__state_key", None)
                        if sk:
                            all_state_keys.append(sk)
                    reminder_recipients = await self._resolve_reminder_recipients(client)
                    for recipient_email in reminder_recipients:
                        attempted_count += 1
                        ok = await self._send_reminder_email(
                            client,
                            expiring_requirements,
                            overdue_requirements,
                            recipient_email=recipient_email,
                            reminder_refs=reminder_refs,
                        )
                        if ok:
                            success_count += 1
                            for sk in all_state_keys:
                                await mark_requirement_reminder_sent(
                                    self.db,
                                    sk,
                                    cooldown_hours=get_reminder_cooldown_hours("DAILY_COMPLIANCE_EXPIRY_EMAIL"),
                                )
                        else:
                            failed_count += 1
                    # Portfolio and above: runtime plan gating before SMS (survives downgrade/cancel)
                    from services.plan_registry import plan_registry
                    sms_allowed, _sms_err, _sms_details = await plan_registry.enforce_feature(
                        client["client_id"], "sms_reminders"
                    )
                    if sms_allowed:
                        # Only send SMS for urgent (overdue) when sms_urgent_alerts_only is True
                        sms_urgent_only = prefs.get("sms_urgent_alerts_only", True) if prefs else True
                        if sms_urgent_only and not overdue_requirements:
                            logger.info("Skipping SMS reminder for client %s - sms_urgent_alerts_only and no overdue items", client["client_id"])
                        else:
                            sms_recipients = await self._resolve_reminder_sms_recipients(client, prefs)
                            for recipient_phone in sms_recipients:
                                await self._maybe_send_reminder_sms(
                                    client,
                                    prefs,
                                    expiring_requirements,
                                    overdue_requirements,
                                    recipient_phone=recipient_phone,
                                    reminder_refs=reminder_refs,
                                )
                    else:
                        logger.info(
                            "Skipping SMS reminder for client %s - plan/subscription does not allow sms_reminders",
                            client["client_id"],
                        )
            
            reminder_count = success_count  # for backward compat message
            logger.info("Daily reminder job complete. attempted=%s success=%s failed=%s", attempted_count, success_count, failed_count)

            # Outcome: success = all sent; degraded = some failed; failed = attempted but none sent
            if attempted_count == 0:
                return {
                    "message": "Daily reminders: no reminders due",
                    "count": 0,
                    "outcome_status": "success",
                    "outcome_metrics": {"expected_count": 0, "attempted_count": 0, "success_count": 0, "failed_count": 0, "skipped_count": skipped_count, "evaluated_items_count": evaluated_items_count, "suppressed_items_count": suppressed_items_count, "suppressed_by_reason": suppressed_by_reason},
                }
            if failed_count > 0 and success_count > 0:
                return {
                    "message": f"Daily reminders: {success_count} sent, {failed_count} failed",
                    "count": success_count,
                    "outcome_status": "degraded",
                    "outcome_metrics": {"expected_count": attempted_count, "attempted_count": attempted_count, "success_count": success_count, "failed_count": failed_count, "skipped_count": skipped_count, "evaluated_items_count": evaluated_items_count, "suppressed_items_count": suppressed_items_count, "suppressed_by_reason": suppressed_by_reason},
                }
            if failed_count > 0 and success_count == 0:
                return {
                    "message": f"Daily reminders: all {attempted_count} send(s) failed",
                    "count": 0,
                    "outcome_status": "failed",
                    "error_message": f"All {attempted_count} reminder send(s) failed",
                    "outcome_metrics": {"expected_count": attempted_count, "attempted_count": attempted_count, "success_count": 0, "failed_count": failed_count, "skipped_count": skipped_count, "evaluated_items_count": evaluated_items_count, "suppressed_items_count": suppressed_items_count, "suppressed_by_reason": suppressed_by_reason},
                }
            return {
                "message": f"Daily reminders sent: {success_count}",
                "count": success_count,
                "outcome_status": "success",
                "outcome_metrics": {"expected_count": attempted_count, "attempted_count": attempted_count, "success_count": success_count, "failed_count": 0, "skipped_count": skipped_count, "evaluated_items_count": evaluated_items_count, "suppressed_items_count": suppressed_items_count, "suppressed_by_reason": suppressed_by_reason},
            }

        except Exception as e:
            logger.exception("Daily reminder job error: %s", e)
            raise

    async def build_monthly_digest_content_for_client(
        self,
        client: dict,
        prefs: Optional[dict],
        period_start: datetime,
        period_end: datetime,
        report_month_key: str,
        reporting_month_label: str,
        *,
        property_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Full digest payload from live entities (same truth as dashboard / score / Today)."""
        from services.monthly_digest_assembly_service import assemble_monthly_digest_payload

        return await assemble_monthly_digest_payload(
            client,
            prefs,
            period_start=period_start,
            period_end=period_end,
            report_month_key=report_month_key,
            reporting_month_label=reporting_month_label,
            property_ids=property_ids,
        )

    async def send_monthly_digest_for_client(
        self,
        client_id: str,
        *,
        force: bool = False,
        triggered_by_admin_id: Optional[str] = None,
        property_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Send one monthly digest email (+ PDF). Admin may force send (ignore prefs / quiet hours).

        Optional ``property_ids`` limits tables to those properties; monthly snapshot is not updated (subset run).
        """
        client = await self.db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            return {
                "message": "Client not found",
                "count": 0,
                "outcome_status": "failed",
                "error_message": "Client not found",
                "outcome_metrics": {"expected_count": 1, "attempted_count": 0, "success_count": 0, "failed_count": 1},
            }
        if client.get("subscription_status") != "ACTIVE":
            return {
                "message": "Client subscription not active",
                "count": 0,
                "outcome_status": "failed",
                "error_message": "subscription_status not ACTIVE",
                "outcome_metrics": {"expected_count": 1, "attempted_count": 0, "success_count": 0, "failed_count": 1},
            }
        if client.get("entitlement_status") == "DISABLED":
            return {
                "message": "Client entitlement disabled",
                "count": 0,
                "outcome_status": "failed",
                "error_message": "entitlement DISABLED",
                "outcome_metrics": {"expected_count": 1, "attempted_count": 0, "success_count": 0, "failed_count": 1},
            }

        prefs = await self.db.notification_preferences.find_one({"client_id": client_id}, {"_id": 0})
        if not force:
            monthly_digest_enabled = prefs.get("monthly_digest", True) if prefs else True
            if not monthly_digest_enabled:
                return {
                    "message": "Skipped: monthly digest disabled in preferences",
                    "count": 0,
                    "outcome_status": "success",
                    "outcome_metrics": {"skipped_count": 1, "attempted_count": 0, "success_count": 0, "failed_count": 0},
                }
            if self._is_in_quiet_hours(prefs):
                return {
                    "message": "Skipped: quiet hours",
                    "count": 0,
                    "outcome_status": "success",
                    "outcome_metrics": {"skipped_count": 1, "attempted_count": 0, "success_count": 0, "failed_count": 0},
                }

        from services.monthly_digest_assembly_service import reporting_period_for_previous_calendar_month

        period_start, period_end, report_month_key, reporting_month_label = reporting_period_for_previous_calendar_month()
        digest_id = str(uuid.uuid4())
        await self._delete_stale_queued_digest_logs(client_id, report_month_key)
        await self._insert_queued_digest_log(
            digest_id=digest_id,
            client_id=client_id,
            report_month_key=report_month_key,
            period_start=period_start,
            period_end=period_end,
            manual_trigger=bool(triggered_by_admin_id),
            triggered_by_admin_id=triggered_by_admin_id,
        )
        try:
            digest_content = await self.build_monthly_digest_content_for_client(
                client,
                prefs,
                period_start,
                period_end,
                report_month_key,
                reporting_month_label,
                property_ids=property_ids,
            )
            digest_content["digest_id"] = digest_id
        except Exception as asm_err:
            logger.exception("Monthly digest assembly failed for %s: %s", client_id, asm_err)
            await self._finalize_digest_log(
                digest_id=digest_id,
                digest_content={},
                period_start=period_start,
                period_end=period_end,
                report_month_key=report_month_key,
                email_subject=None,
                pdf_relpath=None,
                delivery_status="failed_assembly",
                failure_reason=str(asm_err)[:500],
                provider_message_id=None,
                manual_trigger=bool(triggered_by_admin_id),
                triggered_by_admin_id=triggered_by_admin_id,
            )
            return {
                "message": "Digest assembly failed",
                "count": 0,
                "outcome_status": "failed",
                "error_message": str(asm_err)[:500],
                "outcome_metrics": {"expected_count": 1, "attempted_count": 1, "success_count": 0, "failed_count": 1},
            }

        force_key = bool(force or triggered_by_admin_id)
        send_out = await self._send_digest_email(client, digest_content, force_new_idempotency=force_key)
        if not send_out.get("ok"):
            await self._finalize_digest_log(
                digest_id=digest_id,
                digest_content=digest_content,
                period_start=period_start,
                period_end=period_end,
                report_month_key=report_month_key,
                email_subject=send_out.get("email_subject") or digest_content.get("subject"),
                pdf_relpath=send_out.get("pdf_storage_relpath"),
                delivery_status=send_out.get("delivery_status") or "failed_email",
                failure_reason=send_out.get("failure_reason"),
                provider_message_id=send_out.get("provider_message_id"),
                manual_trigger=bool(triggered_by_admin_id),
                triggered_by_admin_id=triggered_by_admin_id,
            )
            return {
                "message": send_out.get("failure_reason") or "Digest not sent",
                "count": 0,
                "outcome_status": "failed",
                "error_message": send_out.get("failure_reason") or "email send failed or skipped",
                "outcome_metrics": {"expected_count": 1, "attempted_count": 1, "success_count": 0, "failed_count": 1},
            }
        await self._finalize_digest_log(
            digest_id=digest_id,
            digest_content=digest_content,
            period_start=period_start,
            period_end=period_end,
            report_month_key=report_month_key,
            email_subject=send_out.get("email_subject") or digest_content.get("subject"),
            pdf_relpath=send_out.get("pdf_storage_relpath"),
            delivery_status="sent",
            failure_reason=None,
            provider_message_id=send_out.get("provider_message_id"),
            manual_trigger=bool(triggered_by_admin_id),
            triggered_by_admin_id=triggered_by_admin_id,
        )
        subset_run = bool(property_ids)
        if not subset_run:
            try:
                from services.monthly_digest_snapshot_service import persist_snapshot

                fps = digest_content.get("_requirement_fingerprints") or {}

                await persist_snapshot(
                    self.db,
                    client_id=client_id,
                    digest_id=digest_id,
                    report_month_key=report_month_key,
                    compliance_score=int(digest_content.get("compliance_score") or 0),
                    risk_level=str(digest_content.get("risk_level") or ""),
                    total_requirements=int(digest_content.get("total_requirements") or 0),
                    valid_count=int(digest_content.get("valid_count") or digest_content.get("compliant") or 0),
                    expiring_soon_count=int(digest_content.get("expiring_soon") or 0),
                    overdue_count=int(digest_content.get("overdue") or 0),
                    missing_evidence_count=int(digest_content.get("missing_evidence_count") or 0),
                    open_compliance_jobs=int(digest_content.get("open_compliance_jobs") or 0),
                    open_maintenance_jobs=int(digest_content.get("open_maintenance_jobs") or 0),
                    documents_uploaded_in_report_period=int(digest_content.get("documents_uploaded_period") or 0),
                    requirement_fingerprints=fps,
                )
            except Exception as snap_err:
                logger.warning("Monthly digest: snapshot persist failed for %s: %s", client_id, snap_err)
        else:
            logger.info(
                "Monthly digest: skipping monthly_compliance_snapshots persist (property subset run) client=%s",
                client_id,
            )
        try:
            from utils.audit import create_audit_log
            from models import AuditAction

            await create_audit_log(
                action=AuditAction.DIGEST_SENT,
                client_id=client_id,
                actor_id=triggered_by_admin_id,
                metadata={
                    "digest_id": digest_id,
                    "channel": "EMAIL",
                    "manual_trigger": bool(triggered_by_admin_id),
                },
            )
        except Exception as audit_err:
            logger.warning("Failed to log DIGEST_SENT audit for %s: %s", digest_id, audit_err)
        return {
            "message": "Monthly digest sent",
            "count": 1,
            "outcome_status": "success",
            "outcome_metrics": {"expected_count": 1, "attempted_count": 1, "success_count": 1, "failed_count": 0},
        }
    
    async def send_monthly_digests(self):
        """Send monthly compliance digest to all active clients.
        Respects user notification preferences.
        
        IMPORTANT: Only runs for clients with ENABLED entitlement.
        Clients with LIMITED or DISABLED entitlement do not receive digests.
        """
        logger.info("Running monthly digest job...")
        
        try:
            # Get all active clients with ENABLED entitlement
            # Per spec: no background jobs when entitlement is DISABLED
            clients = await self.db.clients.find(
                {
                    "subscription_status": "ACTIVE",
                    "entitlement_status": {"$in": ["ENABLED", None]}  # None for legacy compatibility
                },
                {"_id": 0}
            ).to_list(1000)
            
            digest_count = 0
            attempted_digests = 0
            failed_digests = 0
            now_utc = datetime.now(timezone.utc)

            from services.monthly_digest_assembly_service import reporting_period_for_previous_calendar_month

            period_start, period_end, report_month_key, reporting_month_label = reporting_period_for_previous_calendar_month(
                now_utc
            )

            for client in clients:
                prefs = await self.db.notification_preferences.find_one(
                    {"client_id": client["client_id"]},
                    {"_id": 0},
                )
                monthly_digest_enabled = prefs.get("monthly_digest", True) if prefs else True
                if not monthly_digest_enabled:
                    logger.info(f"Skipping monthly digest for {client['email']} - disabled in preferences")
                    continue
                if self._is_in_quiet_hours(prefs):
                    logger.info(f"Skipping monthly digest for {client['email']} - within quiet hours")
                    continue
                day_pref = int(prefs.get("digest_day_of_month", 1) or 1) if prefs else 1
                effective_dom = effective_digest_calendar_day(day_pref, now_utc)
                if now_utc.day != effective_dom:
                    continue

                dup = await self.db.digest_logs.find_one(
                    {
                        "client_id": client["client_id"],
                        "report_month_key": report_month_key,
                        "delivery_status": "sent",
                    },
                    {"_id": 1},
                )
                if dup:
                    logger.info(
                        "Skipping monthly digest for client %s — already sent for %s",
                        client["client_id"],
                        report_month_key,
                    )
                    continue

                digest_id = str(uuid.uuid4())
                await self._delete_stale_queued_digest_logs(client["client_id"], report_month_key)
                await self._insert_queued_digest_log(
                    digest_id=digest_id,
                    client_id=client["client_id"],
                    report_month_key=report_month_key,
                    period_start=period_start,
                    period_end=period_end,
                    manual_trigger=False,
                    triggered_by_admin_id=None,
                )
                try:
                    digest_content = await self.build_monthly_digest_content_for_client(
                        client, prefs, period_start, period_end, report_month_key, reporting_month_label
                    )
                    digest_content["digest_id"] = digest_id
                except Exception as asm_err:
                    logger.exception(
                        "Monthly digest assembly failed for client %s: %s",
                        client["client_id"],
                        asm_err,
                    )
                    await self._finalize_digest_log(
                        digest_id=digest_id,
                        digest_content={},
                        period_start=period_start,
                        period_end=period_end,
                        report_month_key=report_month_key,
                        email_subject=None,
                        pdf_relpath=None,
                        delivery_status="failed_assembly",
                        failure_reason=str(asm_err)[:500],
                        provider_message_id=None,
                        manual_trigger=False,
                        triggered_by_admin_id=None,
                    )
                    failed_digests += 1
                    continue

                attempted_digests += 1
                send_out = await self._send_digest_email(client, digest_content, force_new_idempotency=False)
                if not send_out.get("ok"):
                    await self._finalize_digest_log(
                        digest_id=digest_id,
                        digest_content=digest_content,
                        period_start=period_start,
                        period_end=period_end,
                        report_month_key=report_month_key,
                        email_subject=send_out.get("email_subject") or digest_content.get("subject"),
                        pdf_relpath=send_out.get("pdf_storage_relpath"),
                        delivery_status=send_out.get("delivery_status") or "failed_email",
                        failure_reason=send_out.get("failure_reason"),
                        provider_message_id=send_out.get("provider_message_id"),
                        manual_trigger=False,
                        triggered_by_admin_id=None,
                    )
                    failed_digests += 1
                    continue
                await self._finalize_digest_log(
                    digest_id=digest_id,
                    digest_content=digest_content,
                    period_start=period_start,
                    period_end=period_end,
                    report_month_key=report_month_key,
                    email_subject=send_out.get("email_subject") or digest_content.get("subject"),
                    pdf_relpath=send_out.get("pdf_storage_relpath"),
                    delivery_status="sent",
                    failure_reason=None,
                    provider_message_id=send_out.get("provider_message_id"),
                    manual_trigger=False,
                    triggered_by_admin_id=None,
                )
                try:
                    from utils.audit import create_audit_log
                    from models import AuditAction
                    from services.monthly_digest_snapshot_service import persist_snapshot

                    await create_audit_log(
                        action=AuditAction.DIGEST_SENT,
                        client_id=client["client_id"],
                        metadata={"digest_id": digest_id, "channel": "EMAIL", "report_month_key": report_month_key},
                    )
                    fps = digest_content.get("_requirement_fingerprints") or {}
                    await persist_snapshot(
                        self.db,
                        client_id=client["client_id"],
                        digest_id=digest_id,
                        report_month_key=report_month_key,
                        compliance_score=int(digest_content.get("compliance_score") or 0),
                        risk_level=str(digest_content.get("risk_level") or ""),
                        total_requirements=int(digest_content.get("total_requirements") or 0),
                        valid_count=int(digest_content.get("valid_count") or digest_content.get("compliant") or 0),
                        expiring_soon_count=int(digest_content.get("expiring_soon") or 0),
                        overdue_count=int(digest_content.get("overdue") or 0),
                        missing_evidence_count=int(digest_content.get("missing_evidence_count") or 0),
                        open_compliance_jobs=int(digest_content.get("open_compliance_jobs") or 0),
                        open_maintenance_jobs=int(digest_content.get("open_maintenance_jobs") or 0),
                        documents_uploaded_in_report_period=int(digest_content.get("documents_uploaded_period") or 0),
                        requirement_fingerprints=fps,
                    )
                except Exception as audit_err:
                    logger.warning("Digest audit/snapshot failed for %s: %s", digest_id, audit_err)
                digest_count += 1

            logger.info("Monthly digest job complete. attempted=%s success=%s failed=%s", attempted_digests, digest_count, failed_digests)

            if attempted_digests == 0:
                return {
                    "message": "Monthly digests: none due",
                    "count": 0,
                    "outcome_status": "success",
                    "outcome_metrics": {"expected_count": 0, "attempted_count": 0, "success_count": 0, "failed_count": 0, "skipped_count": 0},
                }
            if failed_digests > 0 and digest_count > 0:
                return {
                    "message": f"Monthly digests: {digest_count} sent, {failed_digests} failed",
                    "count": digest_count,
                    "outcome_status": "degraded",
                    "outcome_metrics": {"expected_count": attempted_digests, "attempted_count": attempted_digests, "success_count": digest_count, "failed_count": failed_digests, "skipped_count": 0},
                }
            if failed_digests > 0 and digest_count == 0:
                return {
                    "message": f"Monthly digests: all {attempted_digests} send(s) failed",
                    "count": 0,
                    "outcome_status": "failed",
                    "error_message": f"All {attempted_digests} digest send(s) failed",
                    "outcome_metrics": {"expected_count": attempted_digests, "attempted_count": attempted_digests, "success_count": 0, "failed_count": failed_digests, "skipped_count": 0},
                }
            return {
                "message": f"Monthly digests sent: {digest_count}",
                "count": digest_count,
                "outcome_status": "success",
                "outcome_metrics": {"expected_count": attempted_digests, "attempted_count": attempted_digests, "success_count": digest_count, "failed_count": 0, "skipped_count": 0},
            }

        except Exception as e:
            logger.exception("Monthly digest job error: %s", e)
            raise
    
    async def _resolve_reminder_recipients(self, client) -> list:
        """
        Resolve reminder email recipients from client + properties.
        Uses property send_reminders_to (LANDLORD / AGENT / BOTH) and agent_email.
        Returns list of distinct email addresses to send the daily reminder to.
        """
        client_email = (client.get("email") or client.get("contact_email") or "").strip()
        properties = await self.db.properties.find(
            {"client_id": client["client_id"]},
            {"_id": 0, "send_reminders_to": 1, "agent_email": 1}
        ).to_list(500)
        send_to_landlord = False
        agent_emails = set()
        for prop in properties:
            to_whom = (prop.get("send_reminders_to") or "LANDLORD").upper()
            if to_whom in ("LANDLORD", "BOTH"):
                send_to_landlord = True
            if to_whom in ("AGENT", "BOTH"):
                ae = (prop.get("agent_email") or "").strip()
                if ae:
                    agent_emails.add(ae)
        recipients = []
        if send_to_landlord and client_email:
            recipients.append(client_email)
        for ae in agent_emails:
            if ae and ae not in recipients:
                recipients.append(ae)
        if not recipients and client_email:
            recipients = [client_email]
        return recipients

    async def _resolve_reminder_sms_recipients(self, client, prefs) -> list:
        """
        Resolve SMS reminder recipients: client phone + agent phones when send_reminders_to is AGENT/BOTH.
        Returns list of phone numbers (only if SMS is enabled in prefs for client; agent phones included by property setting).
        """
        phones = []
        client_phone = (prefs.get("sms_phone_number") if prefs else None) or client.get("sms_phone_number") or ""
        client_phone = (client_phone or "").strip()
        if prefs and prefs.get("sms_enabled") and client_phone:
            phones.append(client_phone)
        properties = await self.db.properties.find(
            {"client_id": client["client_id"]},
            {"_id": 0, "send_reminders_to": 1, "agent_phone": 1}
        ).to_list(500)
        for prop in properties:
            to_whom = (prop.get("send_reminders_to") or "LANDLORD").upper()
            if to_whom in ("AGENT", "BOTH"):
                ap = (prop.get("agent_phone") or "").strip()
                if ap and ap not in phones:
                    phones.append(ap)
        return phones

    async def _send_reminder_email(self, client, expiring, overdue, recipient_email=None, reminder_refs=None):
        """Send reminder email via NotificationOrchestrator. Returns True if sent (or duplicate_ignored), False if skipped/failed."""
        try:
            from services.notification_orchestrator import notification_orchestrator
            from services.webhook_service import fire_reminder_sent
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            to_addr = (recipient_email or client.get("email") or client.get("contact_email") or "").strip()
            if not to_addr:
                return False
            key_suffix = to_addr.replace("@", "_at_") if recipient_email else "client"
            idempotency_key = f"{client['client_id']}_COMPLIANCE_EXPIRY_REMINDER_{date_key}_{key_suffix}"
            from utils.app_urls import get_app_base_url

            base_url = get_app_base_url(for_email_links=True).strip().rstrip("/")
            portal_link = f"{base_url}/dashboard"
            context = {
                "client_name": client.get("full_name", "Valued Customer"),
                "expiring_count": len(expiring),
                "overdue_count": len(overdue),
                "portal_link": portal_link,
                "company_name": client.get("company_name") or "Pleerity Enterprise Ltd",
            }
            if recipient_email:
                context["recipient"] = recipient_email
            if reminder_refs is not None:
                context["reminder_refs"] = json.dumps(reminder_refs)
            # Fill single-requirement placeholders for template (subject/body use first item)
            first_item = (overdue[0] if overdue else expiring[0]) if (overdue or expiring) else None
            if first_item:
                context["requirement_name"] = first_item.get("type", "Certificate")
                rc_item = (first_item.get("code") or "").strip()
                if rc_item:
                    context["requirement_code"] = rc_item
                context["property_address"] = first_item.get("property_address", "Your property")
                context["due_date"] = first_item.get("due_date", "")
                is_overdue = first_item.get("days_overdue") is not None
                if is_overdue:
                    context["days_remaining"] = 0
                    context["days_overdue"] = first_item.get("days_overdue", 0)
                    context["subject"] = f"Action Required: {context['requirement_name']} Overdue"
                else:
                    context["days_remaining"] = first_item.get("days_remaining", 0)
                    context["days_overdue"] = None
                    context["subject"] = f"Action Required: {context['requirement_name']} Due Soon"
            result = await notification_orchestrator.send(
                template_key="COMPLIANCE_EXPIRY_REMINDER",
                client_id=client["client_id"],
                context=context,
                idempotency_key=idempotency_key,
                event_type="REMINDER",
            )
            ok = result.outcome in ("sent", "duplicate_ignored")
            if ok:
                logger.info(f"Sending reminder to {to_addr}: {len(expiring)} expiring, {len(overdue)} overdue")
                try:
                    await fire_reminder_sent(client_id=client["client_id"], recipient=to_addr, expiring_count=len(expiring), overdue_count=len(overdue))
                except Exception as webhook_err:
                    logger.error(f"Webhook error for reminder: {webhook_err}")
                audit_log = {
                    "audit_id": str(datetime.now(timezone.utc).timestamp()),
                    "action": "REMINDER_SENT",
                    "client_id": client["client_id"],
                    "metadata": {"expiring_count": len(expiring), "overdue_count": len(overdue), "recipient": to_addr},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await self.db.audit_logs.insert_one(audit_log)
            return ok
        except Exception as e:
            logger.error("Failed to send reminder email: %s", e)
            return False

    def _strip_digest_content_for_storage(self, digest_content: Dict[str, Any]) -> Dict[str, Any]:
        _heavy = frozenset({"requirement_rows_pdf", "property_rows_pdf", "score_block"})
        content_store = {
            k: v
            for k, v in (digest_content or {}).items()
            if not str(k).startswith("_") and k not in _heavy
        }
        if any(k in (digest_content or {}) for k in _heavy):
            content_store["detail_redacted_for_storage"] = True
        return content_store

    async def _delete_stale_queued_digest_logs(self, client_id: str, report_month_key: str) -> None:
        """Remove abandoned queued rows so a retry can start clean for the same report month."""
        try:
            await self.db.digest_logs.delete_many(
                {"client_id": client_id, "report_month_key": report_month_key, "delivery_status": "queued"}
            )
        except Exception as e:
            logger.warning("digest_logs delete stale queued failed client=%s: %s", client_id, e)

    async def _insert_queued_digest_log(
        self,
        *,
        digest_id: str,
        client_id: str,
        report_month_key: str,
        period_start: datetime,
        period_end: datetime,
        manual_trigger: bool,
        triggered_by_admin_id: Optional[str],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.digest_logs.insert_one(
            {
                "digest_id": digest_id,
                "client_id": client_id,
                "report_month_key": report_month_key,
                "digest_period_start": period_start.isoformat(),
                "digest_period_end": period_end.isoformat(),
                "content": {},
                "email_subject": None,
                "pdf_storage_relpath": None,
                "delivery_status": "queued",
                "failure_reason": None,
                "provider_message_id": None,
                "sent_at": None,
                "queued_at": now,
                "created_at": now,
                "updated_at": now,
                "manual_trigger": manual_trigger,
                "triggered_by_admin_id": triggered_by_admin_id,
            }
        )

    async def _finalize_digest_log(
        self,
        *,
        digest_id: str,
        digest_content: Dict[str, Any],
        period_start: datetime,
        period_end: datetime,
        report_month_key: str,
        email_subject: Optional[str],
        pdf_relpath: Optional[str],
        delivery_status: str,
        failure_reason: Optional[str],
        provider_message_id: Optional[str],
        manual_trigger: bool,
        triggered_by_admin_id: Optional[str],
    ) -> None:
        """Update queued digest row to terminal state (sent, failed_*, skipped_*)."""
        now = datetime.now(timezone.utc).isoformat()
        content_store = self._strip_digest_content_for_storage(digest_content)
        payload: Dict[str, Any] = {
            "digest_period_start": period_start.isoformat(),
            "digest_period_end": period_end.isoformat(),
            "report_month_key": report_month_key,
            "content": content_store,
            "email_subject": email_subject,
            "pdf_storage_relpath": pdf_relpath,
            "delivery_status": delivery_status,
            "failure_reason": failure_reason,
            "provider_message_id": provider_message_id,
            "manual_trigger": manual_trigger,
            "triggered_by_admin_id": triggered_by_admin_id,
            "updated_at": now,
        }
        if delivery_status == "sent":
            payload["sent_at"] = now
        else:
            payload["sent_at"] = None
        res = await self.db.digest_logs.update_one({"digest_id": digest_id}, {"$set": payload})
        if res.matched_count == 0:
            logger.error("digest_logs finalize: no row for digest_id=%s", digest_id)

    async def _maybe_send_reminder_sms(self, client, prefs, expiring, overdue, recipient_phone=None, reminder_refs=None):
        """Send SMS reminder via NotificationOrchestrator (plan-gated, 24h throttle inside orchestrator). Writes message_log with event_type REMINDER and reminder_refs in metadata."""
        try:
            from services.notification_orchestrator import notification_orchestrator
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            key_suffix = (recipient_phone or "").replace("+", "").replace(" ", "")[:20] if recipient_phone else "client"
            idempotency_key = f"{client['client_id']}_COMPLIANCE_EXPIRY_REMINDER_SMS_{date_key}_{key_suffix}"
            from utils.app_urls import get_app_base_url

            base_url = get_app_base_url(for_email_links=True).strip().rstrip("/")
            portal_link = f"{base_url}/dashboard"
            total = len(expiring) + len(overdue)
            context = {"count": total, "portal_link": portal_link}
            if recipient_phone:
                context["recipient"] = recipient_phone
            if reminder_refs is not None:
                context["reminder_refs"] = json.dumps(reminder_refs)
            await notification_orchestrator.send(
                template_key="COMPLIANCE_EXPIRY_REMINDER_SMS",
                client_id=client["client_id"],
                context=context,
                idempotency_key=idempotency_key,
                event_type="REMINDER",
            )
        except Exception as e:
            logger.warning("SMS reminder error for client %s (non-fatal): %s", client.get("client_id"), e)
    
    async def _send_digest_email(self, client, content, *, force_new_idempotency: bool = False) -> Dict[str, Any]:
        """
        Build mandatory PDF, persist to storage, send action email via orchestrator.
        Returns outcome dict for digest_logs / retries (never silently drops PDF failure).
        """
        from services.notification_orchestrator import notification_orchestrator
        from services.webhook_service import fire_digest_sent
        from utils.audit import create_audit_log
        from models import AuditAction
        from utils.app_urls import get_app_base_url
        from services.monthly_digest_pdf_service import build_monthly_digest_pdf_bytes, write_monthly_digest_pdf_to_storage
        from services.branding_resolver_service import resolve_branding, BrandingContext

        subj = (content.get("subject") or "Monthly Compliance Summary").strip()
        report_mk = (content.get("report_month_key") or "").strip()

        def _fail(delivery_status: str, reason: str, pdf_storage_relpath: Optional[str] = None):
            return {
                "ok": False,
                "delivery_status": delivery_status,
                "failure_reason": (reason[:500] if reason else None),
                "email_subject": subj,
                "provider_message_id": None,
                "pdf_storage_relpath": pdf_storage_relpath,
            }

        try:
            recipient = (client.get("email") or client.get("contact_email") or "").strip()
            if not recipient:
                await create_audit_log(
                    action=AuditAction.EMAIL_SKIPPED_NO_RECIPIENT,
                    client_id=client["client_id"],
                    metadata={
                        "template_key": "MONTHLY_DIGEST",
                        "report_month_key": report_mk,
                        "properties_count": content.get("properties_count", 0),
                        "total_requirements": content.get("total_requirements", 0),
                    },
                )
                logger.info("Digest skipped for client %s: no email or contact_email", client["client_id"])
                return _fail("skipped_no_recipient", "No recipient email on client record")

            if force_new_idempotency and content.get("digest_id"):
                idempotency_key = f"{client['client_id']}_MONTHLY_DIGEST_{content.get('digest_id')}"
            else:
                idempotency_key = f"{client['client_id']}_MONTHLY_DIGEST_{report_mk or 'unknown'}"

            base_url = get_app_base_url(for_email_links=True).strip().rstrip("/")
            template_model = {k: v for k, v in content.items() if not str(k).startswith("_")}
            template_model.setdefault("company_name", "Pleerity Enterprise Ltd")
            template_model.setdefault("tagline", "AI-Driven Solutions & Compliance")
            template_model.setdefault("subject", subj)
            template_model.setdefault("portal_link", f"{base_url}/today")
            template_model.setdefault("primary_cta_url", template_model.get("portal_link"))
            _cname = (client.get("full_name") or client.get("contact_name") or "").strip()
            if _cname:
                template_model["client_name"] = _cname

            pdf_model = {k: v for k, v in content.items() if not str(k).startswith("_")}
            try:
                brand_pdf = await resolve_branding(client["client_id"], BrandingContext.CLIENT_DOCUMENT_PDF)
                pdf_bytes = build_monthly_digest_pdf_bytes(pdf_model, brand=brand_pdf)
                relpath = write_monthly_digest_pdf_to_storage(client["client_id"], report_mk or "report", pdf_bytes)
            except Exception as pdf_err:
                logger.error(
                    "Monthly digest PDF failed for client %s: %s",
                    client.get("client_id"),
                    pdf_err,
                    exc_info=True,
                )
                return _fail("failed_pdf", str(pdf_err))

            safe_fname = f"monthly-compliance-summary-{report_mk or 'report'}.pdf"
            template_model["attachments"] = [
                {
                    "Name": safe_fname,
                    "Content": base64.b64encode(pdf_bytes).decode("ascii"),
                    "ContentType": "application/pdf",
                }
            ]
            template_model["digest_pdf_attached"] = True
            template_model["pdf_storage_relpath"] = relpath

            result = await notification_orchestrator.send(
                template_key="MONTHLY_DIGEST",
                client_id=client["client_id"],
                context=template_model,
                idempotency_key=idempotency_key,
                event_type="monthly_digest",
            )
            provider_id = (result.details or {}).get("provider_message_id") if result.details else None
            if result.outcome not in ("sent", "duplicate_ignored"):
                return {
                    "ok": False,
                    "delivery_status": "failed_email",
                    "failure_reason": (result.error_message or result.outcome or "send_failed")[:500],
                    "email_subject": subj,
                    "provider_message_id": provider_id,
                    "pdf_storage_relpath": relpath,
                }

            logger.info(
                "Digest sent to %s: report=%s requirements=%s",
                recipient,
                report_mk,
                content.get("total_requirements", 0),
            )
            try:
                await fire_digest_sent(
                    client_id=client["client_id"],
                    digest_type="monthly",
                    recipients=[recipient],
                    properties_count=content.get("properties_count", 0),
                    requirements_summary={
                        "total": content.get("total_requirements", 0),
                        "compliant": content.get("valid_count", content.get("compliant", 0)),
                        "overdue": content.get("overdue", 0),
                        "expiring_soon": content.get("expiring_soon", 0),
                    },
                )
            except Exception as webhook_err:
                logger.error("Webhook error for digest: %s", webhook_err)

            return {
                "ok": True,
                "delivery_status": "sent",
                "failure_reason": None,
                "email_subject": subj,
                "provider_message_id": provider_id,
                "pdf_storage_relpath": relpath,
            }
        except Exception as e:
            logger.error("Failed to send digest email: %s", e, exc_info=True)
            return _fail("failed_email", str(e))
    
    async def send_pending_verification_digest(self):
        """Send daily summary of documents with status UPLOADED (counts only, no PII) to OWNER/ADMIN via orchestrator."""
        logger.info("Running pending verification digest job...")
        try:
            from services.notification_orchestrator import notification_orchestrator
            from models import AuditAction, UserRole, UserStatus
            from utils.audit import create_audit_log

            snapshot = await get_pending_verification_snapshot(self.db)
            count_pending = snapshot["count_pending"]
            count_older_24h = snapshot["count_older_24h"]
            admins = await self.db.portal_users.find(
                {
                    "role": {"$in": [UserRole.ROLE_OWNER.value, UserRole.ROLE_ADMIN.value]},
                    "status": UserStatus.ACTIVE.value,
                },
                {"_id": 0, "auth_email": 1}
            ).to_list(100)

            recipient_emails = [a["auth_email"] for a in admins if a.get("auth_email")]
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            attempted = len(recipient_emails)
            sent = 0
            if count_pending == 0:
                await create_audit_log(
                    action=AuditAction.ADMIN_ACTION,
                    actor_id="system",
                    metadata={
                        "action_type": "PENDING_VERIFICATION_DIGEST_SUPPRESSED",
                        "suppression_reason": "ZERO_PENDING_ITEMS",
                        "count_pending": 0,
                        "count_older_24h": 0,
                    },
                )
                logger.info("Pending verification digest suppressed: zero pending items at send-time truth check")
                return {
                    "message": "Pending verification digest: suppressed (zero pending items)",
                    "count": 0,
                    "outcome_status": "success",
                    "outcome_metrics": {
                        "expected_count": 0,
                        "attempted_count": 0,
                        "success_count": 0,
                        "failed_count": 0,
                        "skipped_count": len(recipient_emails),
                        "suppression_reason": "ZERO_PENDING_ITEMS",
                    },
                }
            for email in recipient_emails:
                try:
                    result = await notification_orchestrator.send(
                        template_key="PENDING_VERIFICATION_DIGEST",
                        client_id=None,
                        context={
                            "recipient": email,
                            "count_pending": count_pending,
                            "count_older_24h": count_older_24h,
                            "company_name": "Pleerity Enterprise Ltd",
                            "tagline": "AI-Driven Solutions & Compliance",
                            "subject": "Pending verification digest",
                        },
                        idempotency_key=f"PENDING_VERIFICATION_DIGEST_{date_key}_{email}",
                        event_type="pending_verification_digest",
                    )
                    if result.outcome in ("sent", "duplicate_ignored"):
                        sent += 1
                except Exception as e:
                    logger.warning("Pending verification digest send failed to %s: %s", email, e)

            failed = max(0, attempted - sent)
            await create_audit_log(
                action=AuditAction.PENDING_VERIFICATION_DIGEST_SENT,
                actor_id="system",
                metadata={
                    "recipient_count": sent,
                    "count_pending": count_pending,
                    "count_older_24h": count_older_24h,
                },
            )
            logger.info("Pending verification digest sent to %s/%s recipients (count_pending=%s, count_older_24h=%s)", sent, attempted, count_pending, count_older_24h)

            if attempted == 0:
                return {"message": "Pending verification digest: no admin recipients", "count": 0, "outcome_status": "success", "outcome_metrics": {"expected_count": 0, "attempted_count": 0, "success_count": 0, "failed_count": 0, "skipped_count": 0}}
            if failed > 0 and sent > 0:
                return {"message": f"Pending verification digest: {sent} sent, {failed} failed", "count": sent, "outcome_status": "degraded", "outcome_metrics": {"expected_count": attempted, "attempted_count": attempted, "success_count": sent, "failed_count": failed, "skipped_count": 0}}
            if failed > 0 and sent == 0:
                return {"message": f"Pending verification digest: all {attempted} send(s) failed", "count": 0, "outcome_status": "failed", "error_message": f"All {attempted} digest send(s) failed", "outcome_metrics": {"expected_count": attempted, "attempted_count": attempted, "success_count": 0, "failed_count": failed, "skipped_count": 0}}
            return {"message": f"Pending verification digest sent to {sent} recipients", "count": sent, "outcome_status": "success", "outcome_metrics": {"expected_count": attempted, "attempted_count": attempted, "success_count": sent, "failed_count": 0, "skipped_count": 0}}
        except Exception as e:
            logger.exception("Pending verification digest job error: %s", e)
            raise

    async def check_compliance_status_changes(self, client_id: Optional[str] = None):
        """Check for compliance status changes and send alerts.
        
        This job:
        1. Evaluates current compliance status for all properties
        2. Compares with stored previous status
        3. Sends email alerts when status degrades (GREEN→AMBER, AMBER→RED, GREEN→RED)
        4. Fires webhooks for status changes
        5. Updates the stored status
        6. Respects user notification preferences

        When ``client_id`` is set, only that client is scanned (admin scoped run).
        """
        logger.info("Running compliance status change check...")
        
        try:
            from services.webhook_service import fire_compliance_status_changed
            
            base_q = {
                "subscription_status": "ACTIVE",
                "entitlement_status": {"$in": ["ENABLED", None]},  # None for legacy compatibility
            }
            if client_id and str(client_id).strip():
                cid = str(client_id).strip()
                one = await self.db.clients.find_one({**base_q, "client_id": cid}, {"_id": 0})
                if not one:
                    return {
                        "message": f"Client not found or not eligible: {cid}",
                        "count": 0,
                        "outcome_status": "failed",
                        "error_message": "Client not found or not ACTIVE / not entitled",
                    }
                clients = [one]
            else:
                clients = await self.db.clients.find(base_q, {"_id": 0}).to_list(1000)
            
            alert_count = 0
            attempted_alerts = 0
            failed_alerts = 0

            for client in clients:
                # Check notification preferences
                prefs = await self.db.notification_preferences.find_one(
                    {"client_id": client["client_id"]},
                    {"_id": 0}
                )
                
                # Default to enabled if no preferences set
                status_alerts_enabled = prefs.get("status_change_alerts", True) if prefs else True
                
                if self._is_in_quiet_hours(prefs):
                    logger.info(f"Skipping compliance alert for {client['email']} - within quiet hours")
                    status_alerts_enabled = False  # skip send for this client
                
                # Get all properties for this client
                properties = await self.db.properties.find(
                    {"client_id": client["client_id"]},
                    {"_id": 0}
                ).to_list(100)
                
                properties_with_changes = []
                
                for prop in properties:
                    # Get requirements for this property
                    requirements = await self.db.requirements.find(
                        {"property_id": prop["property_id"]},
                        {"_id": 0}
                    ).to_list(100)
                    
                    # Calculate current compliance status based on requirements
                    new_status = self._calculate_property_compliance(requirements)
                    old_status = prop.get("compliance_status", "GREEN")
                    previous_notified_status = prop.get("last_notified_status", old_status)
                    
                    # Check if status has changed at all
                    if new_status != old_status:
                        # Determine reason for change
                        reason = self._get_status_change_reason(requirements, new_status)
                        property_address = f"{prop.get('address_line_1', 'Unknown')}, {prop.get('city', '')}"
                        
                        # Fire webhook for ANY status change (not just degradation)
                        try:
                            await fire_compliance_status_changed(
                                client_id=client["client_id"],
                                property_id=prop["property_id"],
                                property_address=property_address,
                                old_status=old_status,
                                new_status=new_status,
                                reason=reason
                            )
                        except Exception as webhook_err:
                            logger.error(f"Webhook error for property {prop['property_id']}: {webhook_err}")
                        
                        # Check if status has degraded since last notification
                        old_severity = STATUS_SEVERITY.get(previous_notified_status, 0)
                        new_severity = STATUS_SEVERITY.get(new_status, 0)
                        
                        # Only add to email alert on degradation (getting worse)
                        if new_severity > old_severity:
                            properties_with_changes.append({
                                "property_id": prop["property_id"],
                                "address": property_address,
                                "previous_status": previous_notified_status,
                                "new_status": new_status,
                                "reason": reason
                            })
                            
                            # Update property with new status and last notified status
                            await self.db.properties.update_one(
                                {"property_id": prop["property_id"]},
                                {"$set": {
                                    "compliance_status": new_status,
                                    "last_notified_status": new_status,
                                    "status_changed_at": datetime.now(timezone.utc).isoformat()
                                }}
                            )
                        else:
                            # Status changed but not degraded - just update the status
                            await self.db.properties.update_one(
                                {"property_id": prop["property_id"]},
                                {"$set": {
                                    "compliance_status": new_status,
                                    "status_changed_at": datetime.now(timezone.utc).isoformat()
                                }}
                            )
                
                # Send email alert via orchestrator if there are properties with degraded status
                if properties_with_changes and status_alerts_enabled:
                    attempted_alerts += 1
                    try:
                        from utils.app_urls import get_app_base_url
                        from services.notification_orchestrator import notification_orchestrator

                        frontend_url = get_app_base_url(for_email_links=True)
                        date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        ids_hash = "_".join(sorted(p.get("property_id", "") for p in properties_with_changes))[:32]
                        idempotency_key = f"{client['client_id']}_COMPLIANCE_ALERT_{date_key}_{ids_hash}"
                        await notification_orchestrator.send(
                            template_key="COMPLIANCE_ALERT",
                            client_id=client["client_id"],
                            context={
                                "client_name": client.get("full_name", "Valued Customer"),
                                "affected_properties": properties_with_changes,
                                "portal_link": f"{frontend_url}/app/dashboard",
                            },
                            idempotency_key=idempotency_key,
                            event_type="compliance_status_changed",
                        )
                        # Audit log
                        audit_log = {
                            "audit_id": str(datetime.now(timezone.utc).timestamp()),
                            "action": "COMPLIANCE_ALERT_SENT",
                            "client_id": client["client_id"],
                            "metadata": {
                                "properties_affected": len(properties_with_changes),
                                "changes": properties_with_changes
                            },
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        await self.db.audit_logs.insert_one(audit_log)
                        alert_count += 1
                        logger.info("Sent compliance alert to %s for %s properties", client["email"], len(properties_with_changes))
                    except Exception as send_err:
                        failed_alerts += 1
                        logger.warning("Compliance alert send failed for client %s: %s", client["client_id"], send_err)
                elif not status_alerts_enabled and properties_with_changes:
                    logger.info(f"Skipping email alert for {client['email']} - disabled in preferences (webhooks still fired)")
            
            logger.info("Compliance status check complete. attempted=%s success=%s failed=%s", attempted_alerts, alert_count, failed_alerts)

            if attempted_alerts == 0:
                return {"message": "Compliance status check: no alerts due", "count": 0, "outcome_status": "success", "outcome_metrics": {"expected_count": 0, "attempted_count": 0, "success_count": 0, "failed_count": 0, "skipped_count": 0}}
            if failed_alerts > 0 and alert_count > 0:
                return {"message": f"Compliance status check: {alert_count} sent, {failed_alerts} failed", "count": alert_count, "outcome_status": "degraded", "outcome_metrics": {"expected_count": attempted_alerts, "attempted_count": attempted_alerts, "success_count": alert_count, "failed_count": failed_alerts, "skipped_count": 0}}
            if failed_alerts > 0 and alert_count == 0:
                return {"message": f"Compliance status check: all {attempted_alerts} send(s) failed", "count": 0, "outcome_status": "failed", "error_message": f"All {attempted_alerts} alert send(s) failed", "outcome_metrics": {"expected_count": attempted_alerts, "attempted_count": attempted_alerts, "success_count": 0, "failed_count": failed_alerts, "skipped_count": 0}}
            return {"message": f"Compliance status check: {alert_count} alerts sent", "count": alert_count, "outcome_status": "success", "outcome_metrics": {"expected_count": attempted_alerts, "attempted_count": attempted_alerts, "success_count": alert_count, "failed_count": 0, "skipped_count": 0}}

        except Exception as e:
            logger.exception("Compliance status check error: %s", e)
            raise
    
    def _is_in_quiet_hours(self, prefs) -> bool:
        """True if quiet hours are enabled and current UTC time is within the window (e.g. 22:00-08:00)."""
        if not prefs or not prefs.get("quiet_hours_enabled"):
            return False
        try:
            start_str = (prefs.get("quiet_hours_start") or "22:00").strip()
            end_str = (prefs.get("quiet_hours_end") or "08:00").strip()
            start_parts = start_str.split(":")
            end_parts = end_str.split(":")
            start_min = int(start_parts[0]) * 60 + (int(start_parts[1]) if len(start_parts) > 1 else 0)
            end_min = int(end_parts[0]) * 60 + (int(end_parts[1]) if len(end_parts) > 1 else 0)
            now = datetime.now(timezone.utc)
            now_min = now.hour * 60 + now.minute
            # Window crosses midnight (e.g. 22:00-08:00): in window if now_min >= start_min or now_min < end_min
            if start_min > end_min:
                return now_min >= start_min or now_min < end_min
            return start_min <= now_min < end_min
        except (ValueError, IndexError, TypeError):
            return False
    
    def _calculate_property_compliance(self, requirements):
        """Calculate overall compliance status for a property based on its requirements.
        OVERDUE/EXPIRED → RED; EXPIRING_SOON or PENDING (missing evidence) → AMBER; else GREEN.
        """
        if not requirements:
            return "GREEN"  # No requirements = compliant

        now = datetime.now(timezone.utc)
        has_overdue = False
        has_expiring_soon = False
        has_pending = False

        for req in requirements:
            status = req.get("status", "PENDING")

            if status in ["OVERDUE", "EXPIRED"]:
                has_overdue = True
            elif status == "EXPIRING_SOON":
                has_expiring_soon = True
            elif status == "PENDING":
                has_pending = True
                # Also check due date: if past due or within 30 days, upgrade to overdue/expiring
                due_date_str = req.get("due_date")
                if due_date_str:
                    try:
                        due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')) if isinstance(due_date_str, str) else due_date_str
                        days_until_due = (due_date - now).days

                        if days_until_due < 0:
                            has_overdue = True
                        elif days_until_due <= 30:
                            has_expiring_soon = True
                    except Exception:
                        pass

        if has_overdue:
            return "RED"
        elif has_expiring_soon or has_pending:
            return "AMBER"
        else:
            return "GREEN"
    
    def _get_status_change_reason(self, requirements, new_status):
        """Generate a human-readable reason for the status change."""
        if new_status == "RED":
            overdue_types = []
            for req in requirements:
                if req.get("status") in ["OVERDUE", "EXPIRED"]:
                    overdue_types.append(_reminder_item_label_from_req(req))
            
            if overdue_types:
                return f"Overdue: {', '.join(overdue_types[:2])}" + ("..." if len(overdue_types) > 2 else "")
            return "Requirements overdue"
        
        elif new_status == "AMBER":
            expiring_types = []
            for req in requirements:
                if req.get("status") == "EXPIRING_SOON":
                    expiring_types.append(_reminder_item_label_from_req(req))
            
            if expiring_types:
                return f"Expiring soon: {', '.join(expiring_types[:2])}" + ("..." if len(expiring_types) > 2 else "")
            return "Requirements expiring soon"
        
        return "Status updated"

    async def send_renewal_reminders(self):
        """Backward-compatible alias for subscription lifecycle + renewal reminders."""
        return await self.process_subscription_lifecycle_and_reminders()

    async def process_subscription_lifecycle_and_reminders(self):
        """
        Post-grace enforcement, mid-grace dunning nudge, and renewal reminders (7d + 3d).
        Uses Stripe-backed billing records and idempotent period keys.
        """
        logger.info("Running subscription lifecycle and renewal reminders job...")
        import stripe
        from services.subscription_lifecycle_service import (
            apply_post_grace_transitions,
            grace_period_days,
            build_renewal_email_context,
            renewal_reminder_days,
        )
        from services.billing_period_utils import normalize_stored_period_end_for_api
        from services.notification_orchestrator import notification_orchestrator
        from utils.app_urls import get_app_base_url

        now = datetime.now(timezone.utc)
        frontend_url = get_app_base_url(for_email_links=False)
        billing_url = f"{frontend_url}/settings/billing"
        stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY") or "").strip()

        transitioned = await apply_post_grace_transitions(now)

        grace_sent = 0
        grace_docs = await self.db.client_billing.find(
            {"billing_lifecycle_state": "grace_period"},
            {"_id": 0},
        ).to_list(500)
        gdays = grace_period_days()
        for b in grace_docs:
            client_id = b.get("client_id")
            if not client_id:
                continue
            pfail = b.get("payment_failed_at")
            if not pfail:
                continue
            if getattr(pfail, "tzinfo", None) is None:
                pfail = pfail.replace(tzinfo=timezone.utc)
            mid_point = pfail + timedelta(days=max(1.0, gdays / 2))
            if now < mid_point or b.get("grace_mid_reminder_sent_at"):
                continue
            try:
                client = await self.db.clients.find_one(
                    {"client_id": client_id},
                    {"_id": 0, "contact_name": 1, "full_name": 1},
                )
                name = (client or {}).get("contact_name") or (client or {}).get("full_name") or "Valued Customer"
                g_end = b.get("grace_period_ends_at")
                g_end_s = g_end.strftime("%d %B %Y") if hasattr(g_end, "strftime") else ""
                idempotency_key = f"{client_id}_GRACE_REMINDER_{(b.get('dunning_stripe_invoice_id') or '')[:40]}"
                grace_msg = (
                    f"<p>We still could not charge your saved payment method. "
                    f"Please update it before <strong>{html.escape(g_end_s)}</strong> "
                    f"to keep full access. Some automations stay paused until payment succeeds.</p>"
                    f"<p><a href=\"{html.escape(billing_url, quote=True)}\">Open Billing</a></p>"
                )
                await notification_orchestrator.send(
                    template_key="SUBSCRIPTION_GRACE_REMINDER",
                    client_id=client_id,
                    context={
                        "client_name": name,
                        "message": grace_msg,
                        "subject": "Reminder: update your payment method",
                    },
                    idempotency_key=idempotency_key,
                    event_type="subscription_grace_reminder",
                )
                await self.db.client_billing.update_one(
                    {"client_id": client_id},
                    {"$set": {"grace_mid_reminder_sent_at": now}},
                )
                grace_sent += 1
            except Exception as e:
                logger.error("Grace reminder failed for %s: %s", client_id, e)

        billings = await self.db.client_billing.find(
            {
                "subscription_status": {"$in": ["ACTIVE", "TRIALING"]},
                "cancel_at_period_end": {"$ne": True},
                "current_period_end": {"$gte": now},
            },
            {"_id": 0},
        ).to_list(2000)

        day7, day3 = renewal_reminder_days()
        renewal_7 = 0
        renewal_3 = 0

        for billing in billings:
            client_id = billing.get("client_id")
            if not client_id:
                continue
            if (billing.get("entitlement_status") or "").upper() not in ("ENABLED", ""):
                continue

            prefs = await self.db.notification_preferences.find_one(
                {"client_id": client_id},
                {"_id": 0},
            )
            if prefs and prefs.get("renewal_reminders") is False:
                continue

            cpe = normalize_stored_period_end_for_api(billing.get("current_period_end"))
            if not cpe:
                continue
            delta = cpe - now
            days_until = max(0, delta.days)
            period_key = cpe.isoformat()

            charge_auto = True
            sub_id = billing.get("stripe_subscription_id")
            if sub_id and stripe_key:
                try:
                    stripe.api_key = stripe_key
                    sub = stripe.Subscription.retrieve(sub_id)
                    charge_auto = sub.get("collection_method") == "charge_automatically"
                except Exception:
                    charge_auto = True

            renewal_display = cpe.strftime("%d %B %Y")
            client = await self.db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "contact_name": 1, "full_name": 1},
            )
            name = (client or {}).get("contact_name") or (client or {}).get("full_name") or "Valued Customer"
            ctx_base = build_renewal_email_context(
                client_name=name,
                renewal_date_display=renewal_display,
                days_until=days_until,
                charge_automatically=charge_auto,
                billing_url=billing_url,
            )
            msg_html = (
                f"<p>{html.escape(ctx_base['body_framing'])}</p>"
                f"<p><a href=\"{html.escape(billing_url, quote=True)}\">Open Billing</a> to review your plan and payment method.</p>"
            )

            try:
                if days_until in (day7 - 1, day7) and billing.get("renewal_reminder_period_key_7d") != period_key:
                    await notification_orchestrator.send(
                        template_key="SUBSCRIPTION_RENEWAL_REMINDER_7D",
                        client_id=client_id,
                        context={
                            "client_name": name,
                            "message": msg_html,
                            "subject": "Upcoming subscription renewal (7 days)",
                        },
                        idempotency_key=f"{client_id}_RENEW7_{period_key}",
                        event_type="subscription_renewal_reminder_7d",
                    )
                    await self.db.client_billing.update_one(
                        {"client_id": client_id},
                        {"$set": {"renewal_reminder_period_key_7d": period_key}},
                    )
                    renewal_7 += 1
                if days_until in (day3 - 1, day3) and billing.get("renewal_reminder_period_key_3d") != period_key:
                    await notification_orchestrator.send(
                        template_key="SUBSCRIPTION_RENEWAL_REMINDER_3D",
                        client_id=client_id,
                        context={
                            "client_name": name,
                            "message": msg_html,
                            "subject": "Upcoming subscription renewal (3 days)",
                        },
                        idempotency_key=f"{client_id}_RENEW3_{period_key}",
                        event_type="subscription_renewal_reminder_3d",
                    )
                    await self.db.client_billing.update_one(
                        {"client_id": client_id},
                        {"$set": {"renewal_reminder_period_key_3d": period_key}},
                    )
                    renewal_3 += 1
            except Exception as e:
                logger.error("Renewal reminder failed for %s: %s", client_id, e)

        msg = (
            f"Lifecycle: post_grace_updates={transitioned}, grace_nudges={grace_sent}, "
            f"renewal_7d={renewal_7}, renewal_3d={renewal_3}"
        )
        logger.info("Subscription lifecycle job complete. %s", msg)
        return {
            "message": msg,
            "count": transitioned + grace_sent + renewal_7 + renewal_3,
            "outcome_metrics": {
                "post_grace_updates": transitioned,
                "grace_reminders": grace_sent,
                "renewal_7d": renewal_7,
                "renewal_3d": renewal_3,
            },
        }

async def run_daily_job():
    """Run daily reminder job."""
    scheduler = JobScheduler()
    await scheduler.connect()
    await scheduler.send_daily_reminders()
    await scheduler.close()

async def run_monthly_job():
    """Run monthly digest job."""
    scheduler = JobScheduler()
    await scheduler.connect()
    await scheduler.send_monthly_digests()
    await scheduler.close()

async def run_compliance_check():
    """Run compliance status change check."""
    scheduler = JobScheduler()
    await scheduler.connect()
    count = await scheduler.check_compliance_status_changes()
    await scheduler.close()
    return count


async def run_renewal_reminders():
    """Run subscription lifecycle, grace enforcement, and renewal reminder emails."""
    scheduler = JobScheduler()
    await scheduler.connect()
    result = await scheduler.send_renewal_reminders()
    await scheduler.close()
    if isinstance(result, dict):
        return result
    return {"message": f"Subscription lifecycle job: {result}", "count": result}


async def run_scheduled_reports():
    """Run scheduled report generation and email delivery."""
    scheduler = JobScheduler()
    await scheduler.connect()
    count = await scheduler.send_scheduled_reports()
    await scheduler.close()
    return count


class ScheduledReportJob:
    """Handles scheduled report generation and email delivery."""
    
    def __init__(self, db):
        self.db = db
    
    async def process_scheduled_reports(self):
        """Process all due scheduled reports and send them via email.
        
        IMPORTANT: Only runs for clients with ENABLED entitlement.
        Per spec: no background jobs when entitlement is DISABLED.
        """
        from services.reporting_service import reporting_service

        logger.info("Processing scheduled reports...")

        now = datetime.now(timezone.utc)
        reports_sent = 0
        attempted_reports = 0
        schedules_failed = 0  # schedule-level exceptions (per-schedule try/except)

        try:
            # Find all active schedules that are due
            schedules = await self.db.report_schedules.find(
                {
                    "is_active": True,
                    "$or": [
                        {"next_scheduled": {"$lte": now.isoformat()}},
                        {"next_scheduled": None}
                    ]
                },
                {"_id": 0}
            ).to_list(100)
            
            for schedule in schedules:
                try:
                    # Get client info
                    client = await self.db.clients.find_one(
                        {"client_id": schedule["client_id"]},
                        {"_id": 0}
                    )
                    
                    # Skip if client not active or entitlement not ENABLED
                    if not client:
                        continue
                    if client.get("subscription_status") != "ACTIVE":
                        continue
                    if client.get("entitlement_status") not in ["ENABLED", None]:
                        logger.info(f"Skipping scheduled report for {schedule['client_id']} - entitlement is {client.get('entitlement_status')}")
                        continue
                    
                    # Runtime plan gating: scheduled_reports must be allowed (survives downgrade/cancel)
                    from services.plan_registry import plan_registry
                    allowed, error_msg, error_details = await plan_registry.enforce_feature(
                        schedule["client_id"], "scheduled_reports"
                    )
                    if not allowed:
                        logger.info(
                            "Skipping scheduled report for client %s - plan/subscription does not allow scheduled_reports: %s",
                            schedule["client_id"],
                            error_msg,
                        )
                        from utils.audit import create_audit_log
                        from models import AuditAction
                        await create_audit_log(
                            action=AuditAction.ADMIN_ACTION,
                            actor_role="SYSTEM",
                            client_id=schedule["client_id"],
                            metadata={
                                "action_type": "SCHEDULED_REPORT_BLOCKED_PLAN",
                                "schedule_id": schedule.get("schedule_id"),
                                "reason": error_msg,
                                "error_code": (error_details or {}).get("error_code"),
                            },
                        )
                        # MessageLog for visibility in notification health
                        try:
                            await self.db.message_logs.insert_one({
                                "message_id": str(__import__("uuid").uuid4()),
                                "client_id": schedule["client_id"],
                                "recipient": None,
                                "template_key": "SCHEDULED_REPORT",
                                "channel": "EMAIL",
                                "status": "BLOCKED_PLAN",
                                "attempt_count": 1,
                                "error_message": error_msg,
                                "metadata": {"event_type": "scheduled_report", "block_reason": "BLOCKED_PLAN"},
                                "created_at": datetime.now(timezone.utc),
                            })
                        except Exception:
                            pass
                        continue
                    
                    # Generate report
                    report_type = schedule.get("report_type", "compliance_summary")
                    
                    if report_type == "compliance_summary":
                        report_data = await reporting_service.generate_compliance_summary_report(
                            client_id=schedule["client_id"],
                            format="csv",
                            include_details=schedule.get("include_details", True)
                        )
                    elif report_type == "requirements":
                        report_data = await reporting_service.generate_requirements_report(
                            client_id=schedule["client_id"],
                            format="csv"
                        )
                    else:
                        logger.warning(f"Unknown report type: {report_type}")
                        continue
                    
                    # Prepare email; ensure recipients is always a list (may be stored as string)
                    raw_recipients = schedule.get("recipients", [client.get("email")])
                    if isinstance(raw_recipients, str):
                        recipients = [r.strip() for r in raw_recipients.split(",") if r.strip()]
                    else:
                        recipients = list(raw_recipients) if raw_recipients else []
                    if not recipients:
                        recipients = [client.get("email")] if client.get("email") else []
                    frequency = schedule.get("frequency", "weekly")
                    
                    subject = f"Your {frequency.title()} Compliance Report - {now.strftime('%d %b %Y')}"
                    
                    # Send to each recipient via orchestrator
                    date_key = now.strftime("%Y-%m-%d")
                    schedule_sent = 0
                    from utils.app_urls import get_app_base_url

                    base_url = get_app_base_url(for_email_links=True).strip().rstrip("/")
                    scheduled_portal_link = f"{base_url}/today"
                    for recipient in recipients:
                        attempted_reports += 1
                        try:
                            idempotency_key = f"{schedule.get('schedule_id', schedule['client_id'])}_SCHEDULED_REPORT_{date_key}_{recipient}"
                            from services.notification_orchestrator import notification_orchestrator
                            rows = report_data.get("rows") or []
                            summary = report_data.get("report_summary")
                            props_snap = report_data.get("properties_snapshot")
                            result = await notification_orchestrator.send(
                                template_key="SCHEDULED_REPORT",
                                client_id=schedule["client_id"],
                                context={
                                    "recipient": recipient,
                                    "client_name": client.get("full_name", "there"),
                                    "customer_reference": (client.get("customer_reference") or "").strip(),
                                    "report_type": report_type.replace("_", " ").title(),
                                    "frequency": frequency,
                                    "generated_date": now.strftime("%d %B %Y"),
                                    "report_rows": rows,
                                    "total_requirements": len(rows) if rows else (summary or {}).get("total_requirements", 0),
                                    "report_summary": summary,
                                    "properties_snapshot": props_snap if props_snap is not None else [],
                                    "portal_link": scheduled_portal_link,
                                    "company_name": client.get("company_name", "Your Company"),
                                    "subject": subject,
                                    "email_render_engine": "unified_scheduled_digest_v1",
                                },
                                idempotency_key=idempotency_key,
                                event_type="scheduled_report",
                            )
                            if result.outcome in ("sent", "duplicate_ignored"):
                                reports_sent += 1
                                schedule_sent += 1
                        except Exception as e:
                            logger.error(f"Failed to send report to {recipient}: {e}")
                    
                    # Advance next_scheduled when at least one email was sent; otherwise retry next hour.
                    # Always set last_attempted_at so UI can show when the job last ran.
                    now_iso = now.isoformat()
                    if schedule_sent > 0:
                        next_scheduled = self._calculate_next_schedule(frequency, now)
                        await self.db.report_schedules.update_one(
                            {"schedule_id": schedule["schedule_id"]},
                            {"$set": {
                                "last_sent": now_iso,
                                "last_attempted_at": now_iso,
                                "next_scheduled": next_scheduled.isoformat()
                            }}
                        )
                        logger.info(f"Sent {report_type} report for client {schedule['client_id']}")
                    else:
                        # No successful sends: avoid stuck "Next" date in UI — if next_scheduled is already in the past, advance to next period
                        current_next_raw = schedule.get("next_scheduled")
                        try:
                            current_next = datetime.fromisoformat(
                                current_next_raw.replace("Z", "+00:00")
                            ) if current_next_raw else None
                        except (ValueError, TypeError):
                            current_next = None
                        if current_next and (now - current_next) > timedelta(minutes=30):
                            next_scheduled = self._calculate_next_schedule(frequency, now)
                            await self.db.report_schedules.update_one(
                                {"schedule_id": schedule["schedule_id"]},
                                {"$set": {"next_scheduled": next_scheduled.isoformat(), "last_attempted_at": now_iso}}
                            )
                            logger.info(
                                "Scheduled report for client %s (schedule %s) produced no sends; advanced next_scheduled to %s so UI and next run are correct",
                                schedule["client_id"],
                                schedule.get("schedule_id"),
                                next_scheduled.isoformat(),
                            )
                        else:
                            await self.db.report_schedules.update_one(
                                {"schedule_id": schedule["schedule_id"]},
                                {"$set": {"last_attempted_at": now_iso}}
                            )
                            logger.warning(
                                "Scheduled report for client %s (schedule %s) produced no successful sends; not advancing next_scheduled",
                                schedule["client_id"],
                                schedule.get("schedule_id"),
                            )
                    
                except Exception as e:
                    logger.error("Error processing schedule %s: %s", schedule.get("schedule_id"), e)
                    schedules_failed += 1
            
            failed_reports = max(0, attempted_reports - reports_sent)
            logger.info("Scheduled reports job complete. attempted=%s success=%s failed=%s", attempted_reports, reports_sent, failed_reports)

            base_metrics = {"expected_count": attempted_reports, "attempted_count": attempted_reports, "success_count": reports_sent, "failed_count": failed_reports, "skipped_count": 0, "schedules_failed": schedules_failed}
            if attempted_reports == 0 and schedules_failed == 0:
                return {"message": "Scheduled reports: none due", "count": 0, "outcome_status": "success", "outcome_metrics": {"expected_count": 0, "attempted_count": 0, "success_count": 0, "failed_count": 0, "skipped_count": 0, "schedules_failed": 0}}
            if attempted_reports == 0 and schedules_failed > 0:
                return {"message": f"Scheduled reports: {schedules_failed} schedule(s) failed with errors", "count": 0, "outcome_status": "degraded", "outcome_metrics": {**base_metrics, "expected_count": 0}}
            if schedules_failed > 0 and (failed_reports > 0 or reports_sent > 0):
                base_metrics["schedules_failed"] = schedules_failed
                return {"message": f"Scheduled reports: {reports_sent} sent, {failed_reports} failed, {schedules_failed} schedule(s) error(s)", "count": reports_sent, "outcome_status": "degraded", "outcome_metrics": base_metrics}
            if failed_reports > 0 and reports_sent > 0:
                return {"message": f"Scheduled reports: {reports_sent} sent, {failed_reports} failed", "count": reports_sent, "outcome_status": "degraded", "outcome_metrics": base_metrics}
            if failed_reports > 0 and reports_sent == 0:
                return {"message": f"Scheduled reports: all {attempted_reports} send(s) failed", "count": 0, "outcome_status": "failed", "error_message": f"All {attempted_reports} report send(s) failed", "outcome_metrics": base_metrics}
            return {"message": f"Scheduled reports sent: {reports_sent}", "count": reports_sent, "outcome_status": "success", "outcome_metrics": base_metrics}

        except Exception as e:
            logger.exception("Scheduled reports job failed: %s", e)
            raise
    
    def _calculate_next_schedule(self, frequency, from_time):
        """Calculate the next scheduled time based on frequency."""
        if frequency == "daily":
            return from_time + timedelta(days=1)
        elif frequency == "weekly":
            return from_time + timedelta(weeks=1)
        elif frequency == "monthly":
            # Add roughly 30 days
            return from_time + timedelta(days=30)
        else:
            return from_time + timedelta(weeks=1)


# Add to JobScheduler class
JobScheduler.send_scheduled_reports = lambda self: ScheduledReportJob(self.db).process_scheduled_reports()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "daily":
            asyncio.run(run_daily_job())
        elif sys.argv[1] == "monthly":
            asyncio.run(run_monthly_job())
        elif sys.argv[1] == "compliance":
            asyncio.run(run_compliance_check())
        else:
            print("Usage: python jobs.py [daily|monthly|compliance]")
    else:
        print("Usage: python jobs.py [daily|monthly|compliance]")
