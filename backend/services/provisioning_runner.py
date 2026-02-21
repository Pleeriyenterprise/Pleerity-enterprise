"""
Provisioning job runner: single authoritative workflow for purchase lifecycle.

Runner order: PAYMENT_CONFIRMED -> PROVISIONING_STARTED -> (core) -> PROVISIONING_COMPLETED
-> migrate CLEAN IntakeUploads -> send password setup email -> WELCOME_EMAIL_SENT.
If email fails, do NOT set FAILED; set last_error and allow retry of email step only.

Idempotent: no duplicate portal users, documents, or emails.
Job-level lock (locked_until + lock_owner) prevents two runners from executing the same job.
"""
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from pymongo import ReturnDocument

from database import database
from models import ProvisioningJobStatus, ProvisioningJob
from services.provisioning import provisioning_service

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5  # Retry policy: cap attempts for FAILED; email retry can be separate
LOCK_DURATION_SECONDS = 300  # 5 minutes; expired lock is considered free
OPS_ALERT_EMAIL = (os.getenv("OPS_ALERT_EMAIL") or "").strip()
ADMIN_ALERT_EMAILS_RAW = (os.getenv("ADMIN_ALERT_EMAILS") or "").strip()


def _admin_alert_recipients() -> list:
    if ADMIN_ALERT_EMAILS_RAW:
        return [e.strip() for e in ADMIN_ALERT_EMAILS_RAW.split(",") if e.strip()]
    return [OPS_ALERT_EMAIL] if OPS_ALERT_EMAIL else []


async def _send_provisioning_failed_admin_alert(job_id: str, client_id: Optional[str], error_message: str) -> None:
    """Send PROVISIONING_FAILED_ADMIN to ADMIN_ALERT_EMAILS or OPS_ALERT_EMAIL."""
    recipients = _admin_alert_recipients()
    if not recipients:
        logger.warning("OPS_ALERT_EMAIL / ADMIN_ALERT_EMAILS not set; provisioning failed admin alert not sent")
        return
    try:
        from services.notification_orchestrator import notification_orchestrator
        subject = f"[Admin] Provisioning failed: job {job_id}" + (f" client {client_id}" if client_id else "")
        message = f"Job ID: {job_id}\nClient ID: {client_id or 'N/A'}\nError: {error_message[:500]}"
        for recipient in recipients:
            idempotency_key = f"PROVISIONING_FAILED_ADMIN_{job_id}_{hash(recipient) % 10**8}"
            await notification_orchestrator.send(
                template_key="PROVISIONING_FAILED_ADMIN",
                client_id=None,
                context={"recipient": recipient, "subject": subject, "message": message},
                idempotency_key=idempotency_key,
                event_type="provisioning_failed_admin",
            )
    except Exception as e:
        logger.exception("Failed to send provisioning failed admin alert: %s", e)


def _worker_id() -> str:
    return os.environ.get("PROVISIONING_WORKER_ID", f"{os.getpid()}-{uuid.uuid4().hex[:8]}")


async def _acquire_lock(job_id: str) -> bool:
    """Atomically acquire lock on job. Returns True if we got the lock."""
    db = database.get_db()
    now = datetime.now(timezone.utc)
    lock_until = now + timedelta(seconds=LOCK_DURATION_SECONDS)
    worker = _worker_id()
    result = await db.provisioning_jobs.find_one_and_update(
        {
            "job_id": job_id,
            "$or": [
                {"locked_until": None},
                {"locked_until": {"$exists": False}},
                {"locked_until": {"$lt": now}},
            ],
        },
        {"$set": {"locked_until": lock_until, "lock_owner": worker}},
        return_document=ReturnDocument.AFTER,
    )
    return result is not None


async def _release_lock(job_id: str) -> None:
    """Clear lock so another runner can pick up the job if needed."""
    db = database.get_db()
    await db.provisioning_jobs.update_one(
        {"job_id": job_id},
        {"$unset": {"locked_until": "", "lock_owner": ""}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )


async def run_provisioning_job(job_id: str) -> bool:
    """
    Run one provisioning job. Idempotent: safe to call multiple times for same job.
    Acquires job-level lock atomically; exits if another runner holds it.
    Returns True if job reached WELCOME_EMAIL_SENT or already was; False if still in progress or FAILED.
    """
    db = database.get_db()
    job = await db.provisioning_jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        logger.warning(f"Provisioning job not found: {job_id}")
        return False

    status = job.get("status")
    client_id = job.get("client_id")
    if status == ProvisioningJobStatus.WELCOME_EMAIL_SENT.value:
        await db.provisioning_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"needs_run": False, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        return True
    if status not in (
        ProvisioningJobStatus.PAYMENT_CONFIRMED.value,
        ProvisioningJobStatus.PROVISIONING_STARTED.value,
        ProvisioningJobStatus.PROVISIONING_COMPLETED.value,  # Retry email only
        ProvisioningJobStatus.FAILED.value,  # Retry full flow
    ):
        logger.info(f"Job {job_id} status {status} not runnable, skipping")
        return False
    if status == ProvisioningJobStatus.FAILED.value:
        attempt_count = job.get("attempt_count", 0)
        if attempt_count >= MAX_ATTEMPTS:
            await db.provisioning_jobs.update_one(
                {"job_id": job_id},
                {"$set": {"needs_run": False, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            logger.info(f"Job {job_id} FAILED and at max attempts ({MAX_ATTEMPTS}), skipping")
            return False
        # Reset to PAYMENT_CONFIRMED so we re-run from start
        await db.provisioning_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": ProvisioningJobStatus.PAYMENT_CONFIRMED.value, "last_error": None}}
        )
        job = await db.provisioning_jobs.find_one({"job_id": job_id}, {"_id": 0})
        status = job.get("status")

    if not await _acquire_lock(job_id):
        logger.info(f"Job {job_id} locked by another runner, skipping")
        return False

    try:
        return await _run_provisioning_job_locked(job_id, job, status)
    finally:
        await _release_lock(job_id)


async def _run_provisioning_job_locked(job_id: str, job: dict, status: str) -> bool:
    """Execute job work (caller must hold lock)."""
    db = database.get_db()
    client_id = job.get("client_id")
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Retry email only: status is PROVISIONING_COMPLETED, last_error set
    if status == ProvisioningJobStatus.PROVISIONING_COMPLETED.value:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "email": 1, "full_name": 1})
        portal_user = await db.portal_users.find_one(
            {"client_id": client_id, "role": "ROLE_CLIENT_ADMIN"},
            {"_id": 0, "portal_user_id": 1}
        )
        if not client or not portal_user:
            logger.error(f"Job {job_id}: client or portal user missing for email retry")
            return False
        try:
            await provisioning_service._send_password_setup_link(
                client_id,
                portal_user["portal_user_id"],
                client["email"],
                client.get("full_name", "Valued Customer"),
                idempotency_key=f"{job_id}_welcome",
            )
            await db.clients.update_one({"client_id": client_id}, {"$unset": {"last_invite_error": ""}})
            await db.provisioning_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": ProvisioningJobStatus.WELCOME_EMAIL_SENT.value,
                        "welcome_email_sent_at": now_iso,
                        "last_error": None,
                        "needs_run": False,
                        "updated_at": now_iso,
                    }
                }
            )
            logger.info(f"Job {job_id}: welcome email sent (retry)")
            return True
        except Exception as e:
            err_msg = str(e)[:500]
            logger.error(f"Job {job_id}: welcome email retry failed: {e}")
            await db.provisioning_jobs.update_one(
                {"job_id": job_id},
                {"$set": {"last_error": err_msg, "updated_at": now_iso}}
            )
            await db.clients.update_one(
                {"client_id": client_id},
                {"$set": {"last_invite_error": err_msg}}
            )
            return False

    # Transition to PROVISIONING_STARTED and run core
    await db.provisioning_jobs.update_one(
        {"job_id": job_id},
        {
            "$set": {
                "status": ProvisioningJobStatus.PROVISIONING_STARTED.value,
                "provisioning_started_at": now_iso,
                "updated_at": now_iso,
            },
            "$inc": {"attempt_count": 1},
        }
    )
    logger.info("PROVISIONING_STARTED job_id=%s client_id=%s", job_id, client_id)

    success, message, user_id = await provisioning_service.provision_client_portal_core(client_id)
    if not success:
        await db.provisioning_jobs.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": ProvisioningJobStatus.FAILED.value,
                    "last_error": message[:500],
                    "failed_at": now_iso,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        )
        logger.error(f"Job {job_id}: provisioning core failed: {message}")
        # Admin alert on final failure (attempt_count >= MAX_ATTEMPTS)
        updated = await db.provisioning_jobs.find_one({"job_id": job_id}, {"_id": 0, "attempt_count": 1})
        if updated and updated.get("attempt_count", 0) >= MAX_ATTEMPTS:
            await _send_provisioning_failed_admin_alert(job_id, client_id, message)
        return False

    # PROVISIONING_COMPLETED
    now2 = datetime.now(timezone.utc).isoformat()
    await db.provisioning_jobs.update_one(
        {"job_id": job_id},
        {
            "$set": {
                "status": ProvisioningJobStatus.PROVISIONING_COMPLETED.value,
                "provisioning_completed_at": now2,
                "last_error": None,
                "updated_at": now2,
            }
        }
    )

    # Migrate CLEAN intake uploads
    try:
        from services.intake_upload_migration import migrate_intake_uploads_to_vault
        result = await migrate_intake_uploads_to_vault(client_id)
        if result.get("migrated", 0) > 0:
            logger.info(f"Job {job_id}: migrated {result['migrated']} intake upload(s)")
        if result.get("errors"):
            logger.warning(f"Job {job_id}: migration errors: {result['errors']}")
    except Exception as mig_err:
        logger.warning(f"Job {job_id}: intake migration failed: {mig_err}")

    # Send password setup email
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "email": 1, "full_name": 1})
    if not client or not user_id:
        logger.error(f"Job {job_id}: client or user_id missing for email")
        return False
    try:
        await provisioning_service._send_password_setup_link(
            client_id,
            user_id,
            client["email"],
            client.get("full_name", "Valued Customer"),
            idempotency_key=f"{job_id}_welcome",
        )
        now3 = datetime.now(timezone.utc).isoformat()
        await db.provisioning_jobs.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": ProvisioningJobStatus.WELCOME_EMAIL_SENT.value,
                    "welcome_email_sent_at": now3,
                    "needs_run": False,
                    "updated_at": now3,
                }
            }
        )
        logger.info("PROVISIONING_COMPLETED job_id=%s client_id=%s", job_id, client_id)
        return True
    except Exception as email_err:
        err_msg = str(email_err)[:500]
        logger.error(f"Job {job_id}: welcome email failed: {email_err}")
        await db.clients.update_one(
            {"client_id": client_id},
            {"$set": {"last_invite_error": err_msg}}
        )
        await db.provisioning_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"last_error": err_msg, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        # Do NOT set status to FAILED; remain PROVISIONING_COMPLETED for retry
        return False
