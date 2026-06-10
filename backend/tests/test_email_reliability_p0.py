"""
P0 email reliability: resend returns 502 on send failure; monthly digest uses send_email and audit.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.mark.asyncio
async def test_resend_password_setup_returns_502_when_send_returns_failed():
    """Resend returns 502 EMAIL_PROVIDER_REJECTED when orchestrator reports outcome failed."""
    from routes.admin import resend_password_setup
    from fastapi import Request, HTTPException

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN", "email": "admin@test.com"}

    db = MagicMock()
    db.password_tokens = MagicMock()
    db.clients = MagicMock()
    db.portal_users = MagicMock()
    db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "email": "c@test.com",
            "full_name": "Client",
            "onboarding_status": "PROVISIONED",
        }
    )
    db.portal_users.find_one = AsyncMock(return_value={"portal_user_id": "pu1", "client_id": "c1"})
    db.password_tokens.update_many = AsyncMock()
    db.password_tokens.insert_one = AsyncMock()
    db.clients.update_one = AsyncMock()

    send_result = MagicMock(
        outcome="failed",
        error_message="provider rejected",
        message_id="msg-123",
    )

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value=request.state.user), \
         patch("routes.admin.require_recent_step_up", new_callable=AsyncMock), \
         patch("routes.admin.database.get_db", return_value=db), \
         patch("routes.admin.rate_limiter") as rate_limiter, \
         patch("routes.admin.create_audit_log", new_callable=AsyncMock):
        rate_limiter.check_rate_limit = AsyncMock(return_value=(True, None))
        with patch("auth.generate_secure_token", return_value="tok"), \
             patch("auth.hash_token", return_value="hash"), \
             patch(
                 "services.notification_orchestrator.notification_orchestrator.send",
                 AsyncMock(return_value=send_result),
             ):

            with pytest.raises(HTTPException) as exc_info:
                await resend_password_setup(request, "c1")
            assert exc_info.value.status_code == 502
            assert exc_info.value.detail["error_code"] == "EMAIL_PROVIDER_REJECTED"
            assert "provider rejected" in (exc_info.value.detail.get("message") or "")


@pytest.mark.asyncio
async def test_resend_password_setup_returns_400_when_recipient_missing():
    """Resend password setup returns 400 EMAIL_INPUT_INVALID when client has no email."""
    from routes.admin import resend_password_setup
    from fastapi import Request, HTTPException

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN", "email": "admin@test.com"}

    db = MagicMock()
    db.clients = MagicMock()
    db.portal_users = MagicMock()
    db.password_tokens = MagicMock()
    db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "email": "",
            "full_name": "Client",
            "onboarding_status": "PROVISIONED",
        }
    )
    db.portal_users.find_one = AsyncMock(return_value={"portal_user_id": "pu1", "client_id": "c1"})
    db.password_tokens.update_many = AsyncMock()
    db.password_tokens.insert_one = AsyncMock()

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value=request.state.user), \
         patch("routes.admin.require_recent_step_up", new_callable=AsyncMock), \
         patch("routes.admin.database.get_db", return_value=db), \
         patch("routes.admin.rate_limiter") as rate_limiter:
        rate_limiter.check_rate_limit = AsyncMock(return_value=(True, None))
        with patch("auth.generate_secure_token", return_value="tok"), \
             patch("auth.hash_token", return_value="hash"):
            with pytest.raises(HTTPException) as exc_info:
                await resend_password_setup(request, "c1")
            assert exc_info.value.status_code == 400
            assert exc_info.value.detail["error_code"] == "EMAIL_INPUT_INVALID"


@pytest.mark.asyncio
async def test_resend_password_setup_returns_502_when_send_throws():
    """Resend password setup returns 502 when send_password_setup_email raises (provider throw)."""
    from routes.admin import resend_password_setup
    from fastapi import Request, HTTPException

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN", "email": "admin@test.com"}

    db = MagicMock()
    db.clients = MagicMock()
    db.portal_users = MagicMock()
    db.password_tokens = MagicMock()
    db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "email": "c@test.com",
            "full_name": "Client",
            "onboarding_status": "PROVISIONED",
        }
    )
    db.portal_users.find_one = AsyncMock(return_value={"portal_user_id": "pu1", "client_id": "c1"})
    db.password_tokens.update_many = AsyncMock()
    db.password_tokens.insert_one = AsyncMock()

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value=request.state.user), \
         patch("routes.admin.require_recent_step_up", new_callable=AsyncMock), \
         patch("routes.admin.database.get_db", return_value=db), \
         patch("routes.admin.rate_limiter") as rate_limiter:
        rate_limiter.check_rate_limit = AsyncMock(return_value=(True, None))
        with patch("auth.generate_secure_token", return_value="tok"), \
             patch("auth.hash_token", return_value="hash"), \
             patch(
                 "services.notification_orchestrator.notification_orchestrator.send",
                 AsyncMock(side_effect=RuntimeError("Postmark down")),
             ):

            with pytest.raises(HTTPException) as exc_info:
                await resend_password_setup(request, "c1")
            assert exc_info.value.status_code == 502
            assert exc_info.value.detail["error_code"] == "EMAIL_SEND_FAILED"
            from models import EmailTemplateAlias

            assert exc_info.value.detail.get("template") == EmailTemplateAlias.PASSWORD_SETUP.value


@pytest.mark.asyncio
async def test_monthly_digest_calls_send_email_and_writes_audit():
    """_send_digest_email uses notification_orchestrator.send with MONTHLY_DIGEST context (counts-only)."""
    from services.jobs import JobScheduler

    scheduler = MagicMock(spec=JobScheduler)
    scheduler.db = MagicMock()
    scheduler._send_digest_email = JobScheduler._send_digest_email.__get__(scheduler, JobScheduler)

    client = {"client_id": "c1", "email": "client@test.com"}
    content = {
        "period_start": "2025-01-01T00:00:00",
        "period_end": "2025-01-31T23:59:59",
        "report_month_key": "2025-01",
        "subject": "Monthly Operations Intelligence Digest — January 2025",
        "properties_count": 2,
        "total_requirements": 10,
        "compliant": 8,
        "valid_count": 8,
        "overdue": 1,
        "expiring_soon": 1,
        "documents_uploaded": 3,
        "documents_uploaded_period": 3,
        "compliance_score": 80,
        "risk_level": "Low Risk",
        "deltas": {"has_prior_snapshot": False},
        "urgent_items": [],
    }

    send_mock = AsyncMock(return_value=MagicMock(outcome="sent", details={"provider_message_id": "pm-1"}))

    with patch("services.notification_orchestrator.notification_orchestrator.send", send_mock), \
         patch("services.branding_resolver_service.resolve_branding", new_callable=AsyncMock) as rb, \
         patch("services.monthly_digest_pdf_service.build_monthly_digest_pdf_bytes", return_value=b"%PDF-1.4"), \
         patch("services.monthly_digest_pdf_service.write_monthly_digest_pdf_to_storage", return_value="monthly_digest_pdfs/c1/2025-01.pdf"), \
         patch("services.webhook_service.fire_digest_sent", new_callable=AsyncMock):
        rb.return_value = MagicMock()
        out = await scheduler._send_digest_email(client, content)

    assert out.get("ok") is True
    send_mock.assert_called_once()
    call_kw = send_mock.call_args[1]
    assert call_kw["template_key"] == "MONTHLY_DIGEST"
    assert call_kw["client_id"] == "c1"
    assert call_kw["idempotency_key"] == "c1_MONTHLY_DIGEST_2025-01"
    ctx = call_kw["context"]
    assert ctx["properties_count"] == 2
    assert ctx["total_requirements"] == 10
    assert ctx["compliant"] == 8
    assert ctx.get("digest_pdf_attached") is True
    assert "client_name" not in ctx
    assert "email" not in ctx


@pytest.mark.asyncio
async def test_monthly_digest_send_email_writes_one_audit_record():
    """Direct EmailService.send_email is blocked; production path is notification_orchestrator."""
    from services.email_service import EmailService
    from models import EmailTemplateAlias

    svc = EmailService()
    with pytest.raises(RuntimeError, match="notification_orchestrator"):
        await svc.send_email(
            recipient="u@test.com",
            template_alias=EmailTemplateAlias.MONTHLY_DIGEST,
            template_model={
                "period_start": "2025-01-01",
                "period_end": "2025-01-31",
                "properties_count": 1,
                "total_requirements": 5,
                "compliant": 4,
                "overdue": 0,
                "expiring_soon": 1,
                "documents_uploaded": 2,
                "company_name": "Pleerity",
                "tagline": "Tag",
            },
            client_id="c1",
            subject="Monthly Digest",
        )


@pytest.mark.asyncio
async def test_monthly_digest_skips_and_audits_when_no_recipient():
    """_send_digest_email skips send and writes EMAIL_SKIPPED_NO_RECIPIENT when client has no email or contact_email."""
    from services.jobs import JobScheduler
    from models import AuditAction

    scheduler = MagicMock(spec=JobScheduler)
    scheduler.db = MagicMock()
    scheduler._send_digest_email = JobScheduler._send_digest_email.__get__(scheduler, JobScheduler)

    client = {"client_id": "c1", "email": "", "contact_email": None}
    content = {
        "properties_count": 1,
        "total_requirements": 5,
        "compliant": 4,
        "overdue": 0,
        "expiring_soon": 1,
        "documents_uploaded": 0,
        "report_month_key": "2025-01",
        "subject": "Monthly Operations Intelligence Digest — January 2025",
    }

    create_audit_log_mock = AsyncMock(return_value="aid")
    orch_send = AsyncMock()

    with patch("utils.audit.create_audit_log", create_audit_log_mock), \
         patch("services.notification_orchestrator.notification_orchestrator.send", orch_send):
        result = await scheduler._send_digest_email(client, content)

    assert result.get("ok") is False
    orch_send.assert_not_called()
    create_audit_log_mock.assert_called_once()
    call_kw = create_audit_log_mock.call_args[1]
    assert call_kw["action"] == AuditAction.EMAIL_SKIPPED_NO_RECIPIENT
    assert call_kw["client_id"] == "c1"
    assert call_kw["metadata"]["template_key"] == "MONTHLY_DIGEST"
    assert "properties_count" in call_kw["metadata"]
    assert "total_requirements" in call_kw["metadata"]
