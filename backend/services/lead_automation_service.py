"""Lead/client automation runtime for conversion-driven behavioral sequences."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import uuid
from urllib.parse import quote
from statistics import median

from database import database
from services.lead_models import LeadStatus, FollowUpStatus

LEAD_EVENTS_COLLECTION = "lead_events"
LEAD_RULES_COLLECTION = "lead_automation_rules"
LEAD_SEQUENCE_STATE_COLLECTION = "lead_sequence_state"
LEAD_SEQUENCE_SENDS_COLLECTION = "lead_sequence_sends"

SUBJECT_LEAD = "lead"
SUBJECT_CLIENT = "client"

EVENT_RISK_CHECK_COMPLETED = "risk_check_completed"
EVENT_CHECKOUT_STARTED = "checkout_started"
EVENT_CHECKOUT_ABANDONED = "checkout_abandoned"
EVENT_PAYMENT_SUCCESSFUL = "payment_successful"
EVENT_PROVISIONING_COMPLETED = "provisioning_completed"
EVENT_PASSWORD_SET = "password_set"
EVENT_DASHBOARD_READY = "dashboard_ready"
EVENT_MISSING_DOCUMENT = "missing_document"
EVENT_EXPIRED_CERTIFICATE = "expired_certificate"
EVENT_HIGH_RISK_SIGNAL = "high_risk_signal"
EVENT_INACTIVE_USER = "inactive_user"
EVENT_INTAKE_STARTED = "intake_started"
EVENT_EMAIL_OPENED = "email_opened"
EVENT_LINK_CLICKED = "link_clicked"
EVENT_LEAD_CREATED = "lead_created"
EVENT_LEAD_CONVERTED = "lead_converted"

SEQUENCE_RISK_TO_CONVERSION = "risk_to_conversion"
SEQUENCE_ABANDONED_CHECKOUT = "abandoned_checkout"
SEQUENCE_POST_PAYMENT_ACTIVATION = "post_payment_activation"
SEQUENCE_COMPLIANCE_GAP = "compliance_gap"
SEQUENCE_INACTIVE_REACTIVATION = "inactive_user_reactivation"

MAX_RETRIES = 3

SEQUENCE_DEFINITIONS: Dict[str, List[Dict[str, Any]]] = {
    SEQUENCE_RISK_TO_CONVERSION: [
        {"step": 1, "delay_minutes": 0, "subject": "Your Risk Check Results Are Ready", "message": "Your risk check identified actionable compliance gaps. Start now to prevent avoidable penalties."},
        {"step": 2, "delay_minutes": 24 * 60, "subject": "24-hour Follow-up: Complete Your Compliance Setup", "message": "You can activate compliance monitoring in minutes. Your earlier risk findings are still unresolved."},
        {"step": 3, "delay_minutes": 72 * 60, "subject": "72-hour Reminder: Reduce Compliance Risk", "message": "Your risk profile remains open. Activating monitoring now can reduce exposure and missed renewals."},
        {"step": 4, "delay_minutes": 5 * 24 * 60, "subject": "Day 5: Final Prompt to Activate Monitoring", "message": "This is a final reminder based on your risk check activity. Activate monitoring to close open risk items."},
    ],
    SEQUENCE_ABANDONED_CHECKOUT: [
        {"step": 1, "delay_minutes": 60, "subject": "Complete Your Checkout", "message": "You started checkout but did not finish payment. Your order is still available to complete."},
        {"step": 2, "delay_minutes": 24 * 60, "subject": "Checkout Reminder: Resume Your Order", "message": "Your checkout is still pending. Complete payment to start delivery and compliance setup."},
        {"step": 3, "delay_minutes": 48 * 60, "subject": "Final Checkout Reminder", "message": "Your order remains unpaid. Complete checkout now to avoid re-entering details later."},
    ],
    SEQUENCE_POST_PAYMENT_ACTIVATION: [
        {"step": 1, "delay_minutes": 0, "subject": "Payment Received", "message": "Payment confirmed. We are preparing your workspace and activation steps now."},
        {"step": 2, "delay_minutes": 30, "subject": "Set Your Password To Activate", "message": "Provisioning is complete. Set your password to access your dashboard and tools."},
        {"step": 3, "delay_minutes": 120, "subject": "Dashboard Ready", "message": "Your dashboard is ready. Log in to review compliance status and next actions."},
        {"step": 4, "delay_minutes": 7 * 24 * 60, "subject": "We Noticed Inactivity", "message": "You have not used your dashboard recently. Return to continue compliance progress."},
    ],
    SEQUENCE_COMPLIANCE_GAP: [
        {"step": 1, "delay_minutes": 0, "subject": "Compliance Gap Detected", "message": "A compliance gap needs attention: missing document, expired certificate, or high-risk signal."},
        {"step": 2, "delay_minutes": 48 * 60, "subject": "48-hour Reminder: Compliance Gap Still Open", "message": "The detected compliance gap is still unresolved. Please take corrective action now."},
    ],
    SEQUENCE_INACTIVE_REACTIVATION: [
        {"step": 1, "delay_minutes": 0, "subject": "Your Compliance Dashboard Needs Attention", "message": "We noticed recent inactivity. Log in to keep documents and obligations current."},
        {"step": 2, "delay_minutes": 48 * 60, "subject": "Step 2: Resume Monitoring", "message": "Continue from where you left off to reduce compliance risk and avoid missed deadlines."},
        {"step": 3, "delay_minutes": 7 * 24 * 60, "subject": "Final Reactivation Reminder", "message": "This is the final reminder in this re-engagement sequence. Log in to resume control."},
    ],
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_event_key(subject_type: str, subject_key: str, event_type: str, source_ref: Optional[str], at_iso: str) -> str:
    raw = f"{subject_type}|{subject_key}|{event_type}|{source_ref or ''}|{at_iso}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _default_rules() -> List[Dict[str, Any]]:
    return [
        {"rule_key": "risk_to_conversion", "enabled": True, "event_type": EVENT_RISK_CHECK_COMPLETED, "subject_type": SUBJECT_LEAD, "conditions": {"exclude_statuses": [LeadStatus.CONVERTED.value, LeadStatus.LOST.value, LeadStatus.MERGED.value], "min_wait_minutes": 60}, "action": {"type": "trigger_sequence", "sequence_key": SEQUENCE_RISK_TO_CONVERSION}},
        {"rule_key": "checkout_started_followup", "enabled": True, "event_type": EVENT_CHECKOUT_STARTED, "subject_type": SUBJECT_LEAD, "conditions": {"exclude_statuses": [LeadStatus.CONVERTED.value, LeadStatus.LOST.value, LeadStatus.MERGED.value], "min_wait_minutes": 15}, "action": {"type": "trigger_sequence", "sequence_key": SEQUENCE_ABANDONED_CHECKOUT}},
        {"rule_key": "post_payment_activation", "enabled": True, "event_type": EVENT_PAYMENT_SUCCESSFUL, "subject_type": SUBJECT_CLIENT, "conditions": {}, "action": {"type": "trigger_sequence", "sequence_key": SEQUENCE_POST_PAYMENT_ACTIVATION}},
        {"rule_key": "compliance_gap_alerts", "enabled": True, "event_type": EVENT_MISSING_DOCUMENT, "subject_type": SUBJECT_CLIENT, "conditions": {}, "action": {"type": "trigger_sequence", "sequence_key": SEQUENCE_COMPLIANCE_GAP}},
        {"rule_key": "compliance_gap_alerts_expired", "enabled": True, "event_type": EVENT_EXPIRED_CERTIFICATE, "subject_type": SUBJECT_CLIENT, "conditions": {}, "action": {"type": "trigger_sequence", "sequence_key": SEQUENCE_COMPLIANCE_GAP}},
        {"rule_key": "compliance_gap_alerts_risk", "enabled": True, "event_type": EVENT_HIGH_RISK_SIGNAL, "subject_type": SUBJECT_CLIENT, "conditions": {}, "action": {"type": "trigger_sequence", "sequence_key": SEQUENCE_COMPLIANCE_GAP}},
        {"rule_key": "inactive_reactivation", "enabled": True, "event_type": EVENT_INACTIVE_USER, "subject_type": SUBJECT_CLIENT, "conditions": {}, "action": {"type": "trigger_sequence", "sequence_key": SEQUENCE_INACTIVE_REACTIVATION}},
    ]


async def _record_subject_event(*, subject_type: str, subject_key: str, event_type: str, source: str, metadata: Optional[Dict[str, Any]] = None, source_ref: Optional[str] = None, occurred_at: Optional[str] = None) -> Dict[str, Any]:
    db = database.get_db()
    at_iso = occurred_at or _utc_now().isoformat()
    key = _canonical_event_key(subject_type, subject_key, event_type, source_ref, at_iso)
    doc = {
        "event_key": key,
        "subject_type": subject_type,
        "subject_key": subject_key,
        "lead_id": subject_key if subject_type == SUBJECT_LEAD else None,
        "client_id": subject_key if subject_type == SUBJECT_CLIENT else None,
        "event_type": event_type,
        "source": source,
        "source_ref": source_ref,
        "metadata": metadata or {},
        "occurred_at": at_iso,
        "created_at": _utc_now().isoformat(),
    }
    await db[LEAD_EVENTS_COLLECTION].update_one({"event_key": key}, {"$setOnInsert": doc}, upsert=True)
    return doc


async def record_event(*, lead_id: str, event_type: str, source: str, metadata: Optional[Dict[str, Any]] = None, source_ref: Optional[str] = None, occurred_at: Optional[str] = None) -> Dict[str, Any]:
    return await _record_subject_event(subject_type=SUBJECT_LEAD, subject_key=lead_id, event_type=event_type, source=source, metadata=metadata, source_ref=source_ref, occurred_at=occurred_at)


async def record_client_event(*, client_id: str, event_type: str, source: str, metadata: Optional[Dict[str, Any]] = None, source_ref: Optional[str] = None, occurred_at: Optional[str] = None) -> Dict[str, Any]:
    return await _record_subject_event(subject_type=SUBJECT_CLIENT, subject_key=client_id, event_type=event_type, source=source, metadata=metadata, source_ref=source_ref, occurred_at=occurred_at)


async def _subject_doc(subject_type: str, subject_key: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    if subject_type == SUBJECT_LEAD:
        return await db.leads.find_one({"lead_id": subject_key}, {"_id": 0})
    return await db.clients.find_one({"client_id": subject_key}, {"_id": 0})


async def evaluate_automation_rules(lead_id: str, event_type: str) -> int:
    return await evaluate_subject_automation_rules(subject_type=SUBJECT_LEAD, subject_key=lead_id, event_type=event_type)


async def evaluate_client_automation_rules(client_id: str, event_type: str) -> int:
    return await evaluate_subject_automation_rules(subject_type=SUBJECT_CLIENT, subject_key=client_id, event_type=event_type)


async def evaluate_subject_automation_rules(*, subject_type: str, subject_key: str, event_type: str) -> int:
    db = database.get_db()
    doc = await _subject_doc(subject_type, subject_key)
    if not doc:
        return 0
    rules = await db[LEAD_RULES_COLLECTION].find({"enabled": True, "event_type": event_type, "$or": [{"subject_type": subject_type}, {"subject_type": {"$exists": False}}]}, {"_id": 0}).to_list(100)
    if not rules:
        rules = [r for r in _default_rules() if r.get("event_type") == event_type and r.get("subject_type") == subject_type]
    triggered = 0
    for rule in rules:
        conditions = rule.get("conditions") or {}
        if subject_type == SUBJECT_LEAD and doc.get("status") in (conditions.get("exclude_statuses") or []):
            continue
        action = rule.get("action") or {}
        if action.get("type") != "trigger_sequence":
            continue
        min_wait = int(conditions.get("min_wait_minutes") or 0)
        start_at = (_utc_now() + timedelta(minutes=min_wait)).isoformat()
        ok = await trigger_sequence(subject_type=subject_type, subject_key=subject_key, sequence_key=str(action.get("sequence_key") or "").strip(), trigger_event=event_type, start_at=start_at)
        if ok:
            triggered += 1
    return triggered


async def trigger_sequence(*, subject_type: str, subject_key: str, sequence_key: str, trigger_event: str, start_at: Optional[str] = None) -> bool:
    db = database.get_db()
    if sequence_key not in SEQUENCE_DEFINITIONS:
        return False
    now_iso = _utc_now().isoformat()
    state_id = f"{subject_type}:{subject_key}:{sequence_key}"
    existing = await db[LEAD_SEQUENCE_STATE_COLLECTION].find_one({"state_id": state_id}, {"_id": 0})
    if existing and existing.get("status") in ("active", "completed"):
        return False
    next_run = start_at or now_iso
    await db[LEAD_SEQUENCE_STATE_COLLECTION].update_one(
        {"state_id": state_id},
        {"$set": {"state_id": state_id, "subject_type": subject_type, "subject_key": subject_key, "lead_id": subject_key if subject_type == SUBJECT_LEAD else None, "client_id": subject_key if subject_type == SUBJECT_CLIENT else None, "sequence_key": sequence_key, "status": "active", "current_step": 0, "last_sent_at": None, "next_run_at": next_run, "trigger_event": trigger_event, "updated_at": now_iso}, "$setOnInsert": {"created_at": now_iso, "retry_count": 0}},
        upsert=True,
    )
    if subject_type == SUBJECT_LEAD:
        await db.leads.update_one({"lead_id": subject_key}, {"$set": {"followup_status": FollowUpStatus.IN_PROGRESS.value, "updated_at": now_iso}})
    return True


async def stop_sequence(*, state_id: str, reason: str) -> bool:
    db = database.get_db()
    res = await db[LEAD_SEQUENCE_STATE_COLLECTION].update_one({"state_id": state_id, "status": "active"}, {"$set": {"status": "stopped", "stop_reason": reason, "updated_at": _utc_now().isoformat()}})
    return bool(res.modified_count)


def _minutes(step_cfg: Dict[str, Any]) -> int:
    if "delay_minutes" in step_cfg:
        return int(step_cfg["delay_minutes"])
    if "delay_hours" in step_cfg:
        return int(step_cfg["delay_hours"]) * 60
    if "delay_days" in step_cfg:
        return int(step_cfg["delay_days"]) * 24 * 60
    return 0


def _format_step_message(template: str, variables: Dict[str, Any]) -> str:
    out = template
    for k, v in variables.items():
        out = out.replace(f"{{{{{k}}}}}", str(v if v is not None else ""))
    return out


def _default_cta_path(sequence_key: str) -> str:
    if sequence_key in (SEQUENCE_RISK_TO_CONVERSION, SEQUENCE_COMPLIANCE_GAP, SEQUENCE_INACTIVE_REACTIVATION):
        return "/app/dashboard"
    if sequence_key == SEQUENCE_ABANDONED_CHECKOUT:
        return "/order/intake"
    return "/app/dashboard"


async def _email_variables(state: Dict[str, Any], display_name: str) -> Dict[str, Any]:
    db = database.get_db()
    first_name = (display_name or "there").strip().split(" ")[0]
    property_name = "your property"
    risk_level = "Unknown"
    top_risk_1 = "Document expiry may be unmanaged"
    top_risk_2 = "Potential certificate gap detected"
    issue_type = "Compliance gap"
    recommended_action = "Upload and verify the missing/expired evidence in your dashboard."
    if state.get("subject_type") == SUBJECT_CLIENT and state.get("client_id"):
        cid = state["client_id"]
        prop = await db.properties.find_one({"client_id": cid}, {"_id": 0, "nickname": 1, "address_line_1": 1})
        if prop:
            property_name = prop.get("nickname") or prop.get("address_line_1") or property_name
        high = await db.risk_signals.find_one({"client_id": cid, "status": {"$nin": ["resolved"]}}, {"_id": 0, "title": 1, "signal_category": 1, "risk_level": 1}, sort=[("updated_at", -1)])
        if high:
            issue_type = high.get("title") or high.get("signal_category") or issue_type
            risk_level = str(high.get("risk_level") or risk_level)
            top_risk_1 = issue_type
            top_risk_2 = f"Risk level: {risk_level}"
    return {
        "first_name": first_name,
        "property_name": property_name,
        "risk_level": risk_level,
        "top_risk_1": top_risk_1,
        "top_risk_2": top_risk_2,
        "issue_type": issue_type,
        "recommended_action": recommended_action,
    }


def _template_catalog() -> Dict[Tuple[str, int], Dict[str, str]]:
    return {
        (SEQUENCE_RISK_TO_CONVERSION, 1): {"subject": "Your compliance risk score — action required", "body": "Hello {{first_name}},\n\nWe’ve analysed your property data.\n\nYour current compliance status is: {{risk_level}}\n\nHere’s what stands out:\n• {{top_risk_1}}\n• {{top_risk_2}}\n\nThese are not theoretical risks. They can lead to fines, invalid insurance, and enforcement action."},
        (SEQUENCE_RISK_TO_CONVERSION, 2): {"subject": "Most landlords overlook this", "body": "Hello {{first_name}},\n\nMost compliance issues happen because requirements change, documents expire quietly, and tracking is fragmented.\n\nFrom what we’ve seen, your setup may already have gaps."},
        (SEQUENCE_RISK_TO_CONVERSION, 3): {"subject": "This is how penalties actually happen", "body": "Hello {{first_name}},\n\nA certificate expires. No reminder is acted on. A tenant issue arises. Inspection follows.\n\nThat is when problems surface. This system is designed to prevent that."},
        (SEQUENCE_RISK_TO_CONVERSION, 4): {"subject": "We can handle this for you", "body": "Hello {{first_name}},\n\nIf compliance feels too much to track, that is normal. Most users move from manual reminders to one structured system."},
        (SEQUENCE_ABANDONED_CHECKOUT, 1): {"subject": "You didn’t complete your setup", "body": "Hello {{first_name}},\n\nYou started setting up your compliance system but did not finish.\n\nYou can continue where you left off."},
        (SEQUENCE_ABANDONED_CHECKOUT, 2): {"subject": "Your compliance setup is still incomplete", "body": "Hello {{first_name}},\n\nUntil setup is completed, compliance is not tracked and risks remain unmanaged."},
        (SEQUENCE_ABANDONED_CHECKOUT, 3): {"subject": "Final reminder to complete your setup", "body": "Hello {{first_name}},\n\nWe won’t keep sending reminders. This setup remains incomplete."},
        (SEQUENCE_POST_PAYMENT_ACTIVATION, 1): {"subject": "Payment received — next steps", "body": "Hello {{first_name}},\n\nYour payment has been successfully received. We are now setting up your compliance workspace."},
        (SEQUENCE_POST_PAYMENT_ACTIVATION, 2): {"subject": "Your account is ready — set your password", "body": "Hello {{first_name}},\n\nYour compliance workspace is ready. Set your password to access it."},
        (SEQUENCE_POST_PAYMENT_ACTIVATION, 3): {"subject": "Your dashboard is ready", "body": "Hello {{first_name}},\n\nYour account is now fully active. You can view properties, upload certificates, and track status."},
        (SEQUENCE_POST_PAYMENT_ACTIVATION, 4): {"subject": "You’re not fully set up yet", "body": "Hello {{first_name}},\n\nYour system is ready, but it has not been fully used yet. Complete setup to enable full tracking."},
        (SEQUENCE_COMPLIANCE_GAP, 1): {"subject": "Action required: compliance gap detected", "body": "Hello {{first_name}},\n\nWe’ve detected an issue:\n{{issue_type}}\nProperty: {{property_name}}\n\nRecommended action:\n{{recommended_action}}"},
        (SEQUENCE_COMPLIANCE_GAP, 2): {"subject": "Reminder: unresolved compliance gap", "body": "Hello {{first_name}},\n\nThe previously detected compliance gap is still unresolved."},
        (SEQUENCE_INACTIVE_REACTIVATION, 1): {"subject": "Your compliance status may be outdated", "body": "Hello {{first_name}},\n\nIt has been a while since your last check. Compliance status can change over time."},
        (SEQUENCE_INACTIVE_REACTIVATION, 2): {"subject": "Something may have changed", "body": "Hello {{first_name}},\n\nA quick review now can prevent avoidable surprises later."},
        (SEQUENCE_INACTIVE_REACTIVATION, 3): {"subject": "Final reminder", "body": "Hello {{first_name}},\n\nThis is the final reminder in this re-engagement sequence."},
    }


async def _recipient_and_name(subject_type: str, subject_key: str) -> Tuple[Optional[str], str]:
    db = database.get_db()
    if subject_type == SUBJECT_LEAD:
        lead = await db.leads.find_one({"lead_id": subject_key}, {"_id": 0, "email": 1, "name": 1, "status": 1})
        if not lead or lead.get("status") in (LeadStatus.LOST.value, LeadStatus.MERGED.value):
            return None, "Customer"
        return (lead.get("email") or "").strip() or None, (lead.get("name") or "Customer")
    client = await db.clients.find_one({"client_id": subject_key}, {"_id": 0, "contact_email": 1, "email": 1, "full_name": 1})
    if not client:
        return None, "Customer"
    return ((client.get("contact_email") or client.get("email") or "").strip() or None), (client.get("full_name") or "Customer")


async def _is_still_eligible(state: Dict[str, Any], step_idx: int) -> Tuple[bool, str]:
    db = database.get_db()
    subject_type = state.get("subject_type")
    subject_key = state.get("subject_key")
    if state.get("sequence_key") in (SEQUENCE_RISK_TO_CONVERSION, SEQUENCE_ABANDONED_CHECKOUT):
        lead = await db.leads.find_one({"lead_id": subject_key}, {"_id": 0, "status": 1, "client_id": 1})
        if not lead:
            return False, "lead_not_found"
        if lead.get("status") == LeadStatus.CONVERTED.value or lead.get("client_id"):
            return False, "already_converted"
    if state.get("sequence_key") == SEQUENCE_POST_PAYMENT_ACTIVATION:
        if step_idx == 2:
            pu = await db.portal_users.find_one({"client_id": subject_key, "role": "CLIENT_ADMIN"}, {"_id": 0, "password_status": 1})
            if pu and (pu.get("password_status") or "").upper() == "SET":
                return False, "password_already_set"
        if step_idx == 3:
            pu = await db.portal_users.find_one({"client_id": subject_key, "role": "CLIENT_ADMIN"}, {"_id": 0, "password_status": 1})
            if not pu or (pu.get("password_status") or "").upper() != "SET":
                return False, "password_not_set_yet"
    if state.get("sequence_key") == SEQUENCE_COMPLIANCE_GAP and step_idx == 2 and subject_type == SUBJECT_CLIENT:
        open_risks = await db.risk_signals.count_documents({"client_id": subject_key, "status": {"$nin": ["resolved"]}})
        open_expired = await db.requirements.count_documents({"client_id": subject_key, "status": {"$in": ["OVERDUE", "EXPIRED"]}})
        if (open_risks + open_expired) <= 0:
            return False, "gap_resolved"
    return True, "ok"


async def process_due_sequences(limit: int = 100) -> Dict[str, int]:
    db = database.get_db()
    now = _utc_now()
    due = await db[LEAD_SEQUENCE_STATE_COLLECTION].find({"status": "active", "next_run_at": {"$lte": now.isoformat()}}, {"_id": 0}).sort("next_run_at", 1).to_list(limit)
    sent = 0
    skipped = 0
    failed = 0
    for state in due:
        seq = SEQUENCE_DEFINITIONS.get(state.get("sequence_key") or "") or []
        next_step = int(state.get("current_step") or 0) + 1
        if next_step > len(seq):
            await db[LEAD_SEQUENCE_STATE_COLLECTION].update_one({"state_id": state["state_id"]}, {"$set": {"status": "completed", "updated_at": now.isoformat()}})
            continue
        eligible, reason = await _is_still_eligible(state, next_step)
        if not eligible:
            # for deferred milestones in activation flow, retry later instead of stopping
            if reason in ("password_not_set_yet",):
                await db[LEAD_SEQUENCE_STATE_COLLECTION].update_one({"state_id": state["state_id"]}, {"$set": {"next_run_at": (now + timedelta(hours=6)).isoformat(), "updated_at": now.isoformat(), "last_skip_reason": reason}})
                skipped += 1
                continue
            await db[LEAD_SEQUENCE_STATE_COLLECTION].update_one({"state_id": state["state_id"]}, {"$set": {"status": "stopped", "stop_reason": reason, "updated_at": now.isoformat()}})
            skipped += 1
            continue
        step_cfg = seq[next_step - 1]
        recipient, display_name = await _recipient_and_name(state.get("subject_type"), state.get("subject_key"))
        if not recipient:
            await db[LEAD_SEQUENCE_STATE_COLLECTION].update_one({"state_id": state["state_id"]}, {"$set": {"status": "stopped", "stop_reason": "no_recipient", "updated_at": now.isoformat()}})
            skipped += 1
            continue
        # Consolidation guard: core onboarding/provisioning lifecycle already sends
        # payment/activation/dashboard milestone emails. Avoid duplicate user comms.
        tracking_key = str(uuid.uuid4())
        if state.get("sequence_key") == SEQUENCE_POST_PAYMENT_ACTIVATION and next_step in (1, 2, 3):
            send_id = hashlib.sha256(f"{state['state_id']}|{next_step}".encode("utf-8")).hexdigest()
            await db[LEAD_SEQUENCE_SENDS_COLLECTION].update_one(
                {"send_id": send_id},
                {
                    "$set": {
                        "send_id": send_id,
                        "lead_id": state.get("lead_id"),
                        "client_id": state.get("client_id"),
                        "state_id": state["state_id"],
                        "sequence_key": state["sequence_key"],
                        "step": next_step,
                        "subject": step_cfg["subject"],
                        "template_key": "LEAD_FOLLOWUP",
                        "recipient": recipient,
                        "tracking_key": tracking_key,
                        "open_count": 0,
                        "click_count": 0,
                        "status": "suppressed_existing_lifecycle",
                        "error_message": None,
                        "created_at": now.isoformat(),
                    }
                },
                upsert=True,
            )
            next_run_at = (now + timedelta(minutes=_minutes(step_cfg))).isoformat()
            await db[LEAD_SEQUENCE_STATE_COLLECTION].update_one(
                {"state_id": state["state_id"]},
                {
                    "$set": {
                        "current_step": next_step,
                        "last_sent_at": now.isoformat(),
                        "next_run_at": next_run_at,
                        "retry_count": 0,
                        "last_skip_reason": "handled_by_core_lifecycle",
                        "updated_at": now.isoformat(),
                    }
                },
            )
            skipped += 1
            continue
        from services.notification_orchestrator import notification_orchestrator
        from utils.app_urls import get_app_base_url, get_api_base_url
        idempotency_key = f"AUTOSEQ_{state['state_id']}_{next_step}"
        vars_map = await _email_variables(state, display_name)
        template = _template_catalog().get((state.get("sequence_key"), next_step), {"subject": step_cfg["subject"], "body": step_cfg.get("message", "")})
        subject = _format_step_message(template["subject"], vars_map)
        body_txt = _format_step_message(template["body"], vars_map)
        app_base = get_app_base_url(for_email_links=True).rstrip("/")
        api_base = get_api_base_url().rstrip("/")
        cta_url = f"{app_base}{_default_cta_path(state.get('sequence_key', ''))}"
        track_click_url = f"{api_base}/api/leads/automation/track-click?key={quote(tracking_key)}&url={quote(cta_url, safe='')}"
        track_open_url = f"{api_base}/api/leads/automation/track-open?key={quote(tracking_key)}"
        from email_presentation.copy import WHY_RECEIVED_COMPLIANCE_GAP
        from email_presentation.shell import render_lead_sequence_email

        seq_key = state.get("sequence_key", "")
        cta_key = "review_issue" if seq_key == SEQUENCE_COMPLIANCE_GAP else "continue"
        why = WHY_RECEIVED_COMPLIANCE_GAP if seq_key == SEQUENCE_COMPLIANCE_GAP else None
        header_title = "Compliance gap" if seq_key == SEQUENCE_COMPLIANCE_GAP else "Pleerity"
        body = render_lead_sequence_email(
            None,
            display_name=display_name,
            body_text=body_txt,
            header_title=header_title,
            cta_url=track_click_url,
            cta_key=cta_key,
            why_received=why,
            show_preferences_link=bool(state.get("client_id")),
            tracking_open_url=track_open_url,
        )
        result = await notification_orchestrator.send(
            template_key="LEAD_FOLLOWUP",
            client_id=state.get("client_id"),
            context={"recipient": recipient, "subject": subject, "message": body},
            idempotency_key=idempotency_key,
            event_type=f"automation_{state.get('sequence_key')}_step_{next_step}",
        )
        outcome = "sent" if result.outcome in ("sent", "duplicate_ignored") else "failed"
        send_id = hashlib.sha256(f"{state['state_id']}|{next_step}".encode("utf-8")).hexdigest()
        await db[LEAD_SEQUENCE_SENDS_COLLECTION].update_one(
            {"send_id": send_id},
            {"$set": {"send_id": send_id, "lead_id": state.get("lead_id"), "client_id": state.get("client_id"), "state_id": state["state_id"], "sequence_key": state["sequence_key"], "step": next_step, "subject": subject, "template_key": "LEAD_FOLLOWUP", "recipient": recipient, "tracking_key": tracking_key, "open_count": 0, "click_count": 0, "sent_at": now.isoformat() if outcome == "sent" else None, "status": outcome, "error_message": None if outcome == "sent" else (result.error_message or result.block_reason or result.outcome), "created_at": now.isoformat()}},
            upsert=True,
        )
        if outcome != "sent":
            retries = int(state.get("retry_count") or 0) + 1
            if retries >= MAX_RETRIES:
                await db[LEAD_SEQUENCE_STATE_COLLECTION].update_one({"state_id": state["state_id"]}, {"$set": {"status": "failed", "updated_at": now.isoformat(), "retry_count": retries}})
            else:
                await db[LEAD_SEQUENCE_STATE_COLLECTION].update_one({"state_id": state["state_id"]}, {"$set": {"retry_count": retries, "next_run_at": (now + timedelta(minutes=15 * retries)).isoformat(), "updated_at": now.isoformat()}})
            failed += 1
            continue
        sent += 1
        next_run_at = (now + timedelta(minutes=_minutes(step_cfg))).isoformat()
        await db[LEAD_SEQUENCE_STATE_COLLECTION].update_one({"state_id": state["state_id"]}, {"$set": {"current_step": next_step, "last_sent_at": now.isoformat(), "next_run_at": next_run_at, "retry_count": 0, "updated_at": now.isoformat()}})
    return {"sent": sent, "skipped": skipped, "failed": failed}


async def detect_inactive_users_and_trigger() -> int:
    db = database.get_db()
    now = _utc_now()
    cutoff = now - timedelta(days=7)
    cursor = db.portal_users.find({"role": "CLIENT_ADMIN"}, {"_id": 0, "client_id": 1, "last_login": 1})
    triggered = 0
    async for row in cursor:
        last_login = row.get("last_login")
        try:
            if isinstance(last_login, str):
                last_login = datetime.fromisoformat(last_login.replace("Z", "+00:00"))
            if last_login is None:
                continue
            if getattr(last_login, "tzinfo", None) is None:
                last_login = last_login.replace(tzinfo=timezone.utc)
            if last_login <= cutoff:
                cid = row.get("client_id")
                if not cid:
                    continue
                await record_client_event(client_id=cid, event_type=EVENT_INACTIVE_USER, source="inactive_user_scan", metadata={"last_login": last_login.isoformat()})
                triggered += await evaluate_client_automation_rules(cid, EVENT_INACTIVE_USER)
        except Exception:
            continue
    return triggered


async def detect_compliance_gap_and_trigger() -> int:
    from services.requirement_evidence_authority import authority_gap_missing_states, EA_VERIFIED_EXPIRED

    db = database.get_db()
    gap_states = authority_gap_missing_states()
    clients = await db.clients.find({}, {"_id": 0, "client_id": 1}).to_list(2000)
    triggered = 0
    for c in clients:
        cid = c.get("client_id")
        if not cid:
            continue
        missing_docs = await db.requirements.count_documents(
            {
                "client_id": cid,
                "$or": [
                    {
                        "evidence_authority_synced_at": {"$ne": None},
                        "evidence_authority.version": {"$gte": 1},
                        "evidence_authority.state": {"$in": gap_states},
                    },
                    {
                        "$or": [
                            {"evidence_authority_synced_at": None},
                            {"evidence_authority.version": {"$lt": 1}},
                        ],
                        "status": {"$in": ["MISSING", "MISSING_EVIDENCE"]},
                    },
                ],
            }
        )
        expired = await db.requirements.count_documents(
            {
                "client_id": cid,
                "$or": [
                    {
                        "evidence_authority_synced_at": {"$ne": None},
                        "evidence_authority.version": {"$gte": 1},
                        "evidence_authority.state": EA_VERIFIED_EXPIRED,
                    },
                    {
                        "$or": [
                            {"evidence_authority_synced_at": None},
                            {"evidence_authority.version": {"$lt": 1}},
                        ],
                        "status": {"$in": ["OVERDUE", "EXPIRED"]},
                    },
                ],
            }
        )
        high_risk = await db.risk_signals.count_documents({"client_id": cid, "status": {"$nin": ["resolved"]}, "risk_level": {"$in": ["HIGH", "CRITICAL"]}})
        if missing_docs > 0:
            await record_client_event(client_id=cid, event_type=EVENT_MISSING_DOCUMENT, source="compliance_gap_scan", metadata={"count": int(missing_docs)})
            triggered += await evaluate_client_automation_rules(cid, EVENT_MISSING_DOCUMENT)
        if expired > 0:
            await record_client_event(client_id=cid, event_type=EVENT_EXPIRED_CERTIFICATE, source="compliance_gap_scan", metadata={"count": int(expired)})
            triggered += await evaluate_client_automation_rules(cid, EVENT_EXPIRED_CERTIFICATE)
        if high_risk > 0:
            await record_client_event(client_id=cid, event_type=EVENT_HIGH_RISK_SIGNAL, source="compliance_gap_scan", metadata={"count": int(high_risk)})
            triggered += await evaluate_client_automation_rules(cid, EVENT_HIGH_RISK_SIGNAL)
    return triggered


async def get_sequence_metrics(limit: int = 50) -> Dict[str, Any]:
    db = database.get_db()
    active = await db[LEAD_SEQUENCE_STATE_COLLECTION].find({"status": "active"}, {"_id": 0}).to_list(limit)
    counts = await db[LEAD_SEQUENCE_STATE_COLLECTION].aggregate([
        {"$group": {"_id": "$sequence_key", "total": {"$sum": 1}, "active": {"$sum": {"$cond": [{"$eq": ["$status", "active"]}, 1, 0]}}, "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}}}}
    ]).to_list(100)
    return {"active_sequences": active, "metrics": counts}


async def mark_send_opened(tracking_key: str) -> bool:
    db = database.get_db()
    now = _utc_now().isoformat()
    res = await db[LEAD_SEQUENCE_SENDS_COLLECTION].update_one(
        {"tracking_key": tracking_key},
        {"$inc": {"open_count": 1}, "$set": {"last_opened_at": now}, "$setOnInsert": {"first_opened_at": now}},
    )
    if res.modified_count:
        row = await db[LEAD_SEQUENCE_SENDS_COLLECTION].find_one({"tracking_key": tracking_key}, {"_id": 0, "lead_id": 1, "client_id": 1, "sequence_key": 1, "step": 1})
        if row and row.get("lead_id"):
            await record_event(lead_id=row["lead_id"], event_type=EVENT_EMAIL_OPENED, source="automation_track_open", metadata={"sequence_key": row.get("sequence_key"), "step": row.get("step")})
        return True
    return False


async def mark_send_clicked(tracking_key: str, target_url: str) -> bool:
    db = database.get_db()
    now = _utc_now().isoformat()
    res = await db[LEAD_SEQUENCE_SENDS_COLLECTION].update_one(
        {"tracking_key": tracking_key},
        {"$inc": {"click_count": 1}, "$set": {"last_clicked_at": now, "last_clicked_url": target_url}, "$setOnInsert": {"first_clicked_at": now}},
    )
    if res.modified_count:
        row = await db[LEAD_SEQUENCE_SENDS_COLLECTION].find_one({"tracking_key": tracking_key}, {"_id": 0, "lead_id": 1, "client_id": 1, "sequence_key": 1, "step": 1})
        if row and row.get("lead_id"):
            await record_event(lead_id=row["lead_id"], event_type=EVENT_LINK_CLICKED, source="automation_track_click", metadata={"sequence_key": row.get("sequence_key"), "step": row.get("step"), "url": target_url})
        return True
    return False


async def apply_conversion_attribution(lead_id: Optional[str], client_id: Optional[str], converted_at_iso: str) -> Dict[str, Any]:
    db = database.get_db()
    q = {"status": "sent"}
    if lead_id:
        q["lead_id"] = lead_id
    elif client_id:
        q["client_id"] = client_id
    else:
        return {}
    last_click = await db[LEAD_SEQUENCE_SENDS_COLLECTION].find_one({**q, "last_clicked_at": {"$exists": True, "$lte": converted_at_iso}}, {"_id": 0}, sort=[("last_clicked_at", -1)])
    chosen = last_click
    via = "click"
    if not chosen:
        chosen = await db[LEAD_SEQUENCE_SENDS_COLLECTION].find_one({**q, "last_opened_at": {"$exists": True, "$lte": converted_at_iso}}, {"_id": 0}, sort=[("last_opened_at", -1)])
        via = "open" if chosen else ""
    if not chosen:
        return {}
    return {
        "attributed_send_id": chosen.get("send_id"),
        "attributed_flow_key": chosen.get("sequence_key"),
        "attributed_step": chosen.get("step"),
        "attributed_via": via,
    }


async def get_email_performance_metrics(days: int = 30) -> Dict[str, Any]:
    db = database.get_db()
    start = (_utc_now() - timedelta(days=max(1, int(days)))).isoformat()
    pipeline = [
        {"$match": {"created_at": {"$gte": start}}},
        {"$group": {
            "_id": {"flow": "$sequence_key", "step": "$step"},
            "sent": {"$sum": {"$cond": [{"$eq": ["$status", "sent"]}, 1, 0]}},
            "opens": {"$sum": {"$cond": [{"$gt": ["$open_count", 0]}, 1, 0]}},
            "clicks": {"$sum": {"$cond": [{"$gt": ["$click_count", 0]}, 1, 0]}},
        }},
        {"$sort": {"_id.flow": 1, "_id.step": 1}},
    ]
    rows = await db[LEAD_SEQUENCE_SENDS_COLLECTION].aggregate(pipeline).to_list(500)
    conversions = await db.leads.aggregate(
        [
            {"$match": {"converted_at": {"$gte": start}, "conversion_attribution": {"$exists": True, "$ne": None}}},
            {
                "$group": {
                    "_id": {
                        "flow": "$conversion_attribution.attributed_flow_key",
                        "step": "$conversion_attribution.attributed_step",
                    },
                    "conversions": {"$sum": 1},
                }
            },
        ]
    ).to_list(500)
    conv_map: Dict[Tuple[str, int], int] = {}
    duration_map: Dict[Tuple[str, int], List[float]] = {}
    for c in conversions:
        ck = c.get("_id") or {}
        flow = str(ck.get("flow") or "")
        step = int(ck.get("step") or 0)
        if flow and step > 0:
            conv_map[(flow, step)] = int(c.get("conversions") or 0)
    attributed_leads = await db.leads.find(
        {"converted_at": {"$gte": start}, "conversion_attribution": {"$exists": True, "$ne": None}},
        {"_id": 0, "converted_at": 1, "conversion_attribution": 1},
    ).to_list(2000)
    for lead in attributed_leads:
        attr = lead.get("conversion_attribution") or {}
        send_id = attr.get("attributed_send_id")
        flow = str(attr.get("attributed_flow_key") or "")
        step = int(attr.get("attributed_step") or 0)
        converted_at = lead.get("converted_at")
        if not send_id or not flow or step <= 0 or not converted_at:
            continue
        send = await db[LEAD_SEQUENCE_SENDS_COLLECTION].find_one({"send_id": send_id}, {"_id": 0, "sent_at": 1})
        sent_at = (send or {}).get("sent_at")
        if not sent_at:
            continue
        try:
            conv_dt = datetime.fromisoformat(str(converted_at).replace("Z", "+00:00"))
            send_dt = datetime.fromisoformat(str(sent_at).replace("Z", "+00:00"))
            if conv_dt.tzinfo is None:
                conv_dt = conv_dt.replace(tzinfo=timezone.utc)
            if send_dt.tzinfo is None:
                send_dt = send_dt.replace(tzinfo=timezone.utc)
            delta_hours = max(0.0, (conv_dt - send_dt).total_seconds() / 3600.0)
            duration_map.setdefault((flow, step), []).append(delta_hours)
        except Exception:
            continue
    for r in rows:
        sent = int(r.get("sent") or 0)
        rid = r.get("_id") or {}
        flow = str(rid.get("flow") or "")
        step = int(rid.get("step") or 0)
        conv_count = int(conv_map.get((flow, step), 0))
        durations = duration_map.get((flow, step), [])
        r["conversions"] = conv_count
        r["open_rate_percent"] = round((int(r.get("opens") or 0) / sent * 100), 2) if sent else 0.0
        r["click_rate_percent"] = round((int(r.get("clicks") or 0) / sent * 100), 2) if sent else 0.0
        r["conversion_rate_percent"] = round((conv_count / sent * 100), 2) if sent else 0.0
        r["median_hours_to_conversion"] = round(float(median(durations)), 2) if durations else None
    by_flow: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        rid = r.get("_id") or {}
        flow = str(rid.get("flow") or "")
        if not flow:
            continue
        by_flow.setdefault(flow, []).append(r)
    highlights: List[Dict[str, Any]] = []
    for flow, fr in by_flow.items():
        top_conv = max(fr, key=lambda x: float(x.get("conversion_rate_percent") or 0.0)) if fr else None
        valid_fast = [x for x in fr if x.get("median_hours_to_conversion") is not None]
        fastest = min(valid_fast, key=lambda x: float(x.get("median_hours_to_conversion") or 0.0)) if valid_fast else None
        highlights.append(
            {
                "flow": flow,
                "top_conversion_step": (top_conv.get("_id") or {}).get("step") if top_conv else None,
                "top_conversion_rate_percent": float(top_conv.get("conversion_rate_percent") or 0.0) if top_conv else 0.0,
                "fastest_step": (fastest.get("_id") or {}).get("step") if fastest else None,
                "fastest_median_hours": float(fastest.get("median_hours_to_conversion")) if fastest and fastest.get("median_hours_to_conversion") is not None else None,
            }
        )
    return {"window_days": days, "rows": rows, "highlights": highlights}
