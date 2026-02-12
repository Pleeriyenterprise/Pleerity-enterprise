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
    """Resend password setup endpoint returns 502 with error_code when send_email returns status failed."""
    from routes.admin import resend_password_setup
    from fastapi import Request, HTTPException
    from models import EmailTemplateAlias

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN", "email": "admin@test.com"}

    db = MagicMock()
    db.password_tokens = MagicMock()
    db.clients = MagicMock()
    db.portal_users = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "email": "c@test.com", "full_name": "Client"})
    db.portal_users.find_one = AsyncMock(return_value={"portal_user_id": "pu1", "client_id": "c1"})
    db.password_tokens.update_many = AsyncMock()
    db.password_tokens.insert_one = AsyncMock()

    failed_log = MagicMock()
    failed_log.status = "failed"
    failed_log.message_id = "msg-123"
    failed_log.postmark_message_id = None

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value=request.state.user), \
         patch("routes.admin.database.get_db", return_value=db), \
         patch("routes.admin.rate_limiter") as rate_limiter, \
         patch("routes.admin.create_audit_log", new_callable=AsyncMock):
        rate_limiter.check_rate_limit = AsyncMock(return_value=(True, None))
        with patch("routes.admin.generate_secure_token", return_value="tok"), \
             patch("routes.admin.hash_token", return_value="hash"), \
             patch("routes.admin.provisioning_service", MagicMock()), \
             patch("services.email_service.email_service.send_password_setup_email", AsyncMock(return_value=failed_log)):

            with pytest.raises(HTTPException) as exc_info:
                await resend_password_setup(request, "c1")
            assert exc_info.value.status_code == 502
            assert exc_info.value.detail["error_code"] == "EMAIL_SEND_FAILED"
            assert exc_info.value.detail["template"] == EmailTemplateAlias.PASSWORD_SETUP.value
            assert exc_info.value.detail.get("message_id") == "msg-123"


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
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "email": "", "full_name": "Client"})
    db.portal_users.find_one = AsyncMock(return_value={"portal_user_id": "pu1", "client_id": "c1"})
    db.password_tokens.update_many = AsyncMock()
    db.password_tokens.insert_one = AsyncMock()

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value=request.state.user), \
         patch("routes.admin.database.get_db", return_value=db), \
         patch("routes.admin.rate_limiter") as rate_limiter:
        rate_limiter.check_rate_limit = AsyncMock(return_value=(True, None))
        with patch("routes.admin.generate_secure_token", return_value="tok"), \
             patch("routes.admin.hash_token", return_value="hash"):
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
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "email": "c@test.com", "full_name": "Client"})
    db.portal_users.find_one = AsyncMock(return_value={"portal_user_id": "pu1", "client_id": "c1"})
    db.password_tokens.update_many = AsyncMock()
    db.password_tokens.insert_one = AsyncMock()

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value=request.state.user), \
         patch("routes.admin.database.get_db", return_value=db), \
         patch("routes.admin.rate_limiter") as rate_limiter:
        rate_limiter.check_rate_limit = AsyncMock(return_value=(True, None))
        with patch("routes.admin.generate_secure_token", return_value="tok"), \
             patch("routes.admin.hash_token", return_value="hash"), \
             patch("services.email_service.email_service.send_password_setup_email", AsyncMock(side_effect=RuntimeError("Postmark down"))):

            with pytest.raises(HTTPException) as exc_info:
                await resend_password_setup(request, "c1")
            assert exc_info.value.status_code == 502
            assert exc_info.value.detail["error_code"] == "EMAIL_SEND_FAILED"


@pytest.mark.asyncio
async def test_monthly_digest_calls_send_email_and_writes_audit():
    """_send_digest_email calls send_email with MONTHLY_DIGEST (counts-only) and send_email path writes one audit."""
    from services.jobs import JobScheduler
    from models import EmailTemplateAlias

    scheduler = MagicMock(spec=JobScheduler)
    scheduler.db = MagicMock()
    scheduler._send_digest_email = JobScheduler._send_digest_email.__get__(scheduler, JobScheduler)

    client = {"client_id": "c1", "email": "client@test.com"}
    content = {
        "period_start": "2025-01-01T00:00:00",
        "period_end": "2025-01-31T23:59:59",
        "properties_count": 2,
        "total_requirements": 10,
        "compliant": 8,
        "overdue": 1,
        "expiring_soon": 1,
        "documents_uploaded": 3,
    }

    send_email_mock = AsyncMock(return_value=MagicMock(status="sent", message_id="m1"))

    with patch("services.email_service.email_service.send_email", send_email_mock), \
         patch("services.jobs.fire_digest_sent", new_callable=AsyncMock):
        await scheduler._send_digest_email(client, content)

    send_email_mock.assert_called_once()
    call_kw = send_email_mock.call_args[1]
    assert call_kw["recipient"] == "client@test.com"
    assert call_kw["template_alias"] == EmailTemplateAlias.MONTHLY_DIGEST
    assert call_kw["client_id"] == "c1"
    model = call_kw["template_model"]
    assert model["properties_count"] == 2
    assert model["total_requirements"] == 10
    assert model["compliant"] == 8
    assert "client_name" not in model
    assert "email" not in model


@pytest.mark.asyncio
async def test_monthly_digest_send_email_writes_one_audit_record():
    """Real send_email (with mocked DB/Postmark) writes one audit record (EMAIL_SENT) per call."""
    from services.email_service import EmailService
    from models import EmailTemplateAlias

    db = MagicMock()
    db.email_templates = MagicMock()
    db.email_templates.find_one = AsyncMock(return_value=None)
    db.message_logs = MagicMock()
    db.message_logs.insert_one = AsyncMock()

    create_audit_log_mock = AsyncMock(return_value="aid")

    with patch("services.email_service.database.get_db", return_value=db), \
         patch("services.email_service.create_audit_log", create_audit_log_mock):
        svc = EmailService()
        svc.client = None
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
    assert create_audit_log_mock.call_count == 1
    assert create_audit_log_mock.call_args[1]["client_id"] == "c1"


@pytest.mark.asyncio
async def test_monthly_digest_skips_and_audits_when_no_recipient():
    """_send_digest_email skips send and writes EMAIL_SKIPPED_NO_RECIPIENT when client has no email or contact_email."""
    from services.jobs import JobScheduler
    from models import AuditAction, EmailTemplateAlias

    scheduler = MagicMock(spec=JobScheduler)
    scheduler.db = MagicMock()
    scheduler._send_digest_email = JobScheduler._send_digest_email.__get__(scheduler, JobScheduler)

    client = {"client_id": "c1", "email": "", "contact_email": None}
    content = {"properties_count": 1, "total_requirements": 5, "compliant": 4, "overdue": 0, "expiring_soon": 1, "documents_uploaded": 0}

    create_audit_log_mock = AsyncMock(return_value="aid")
    send_email_mock = AsyncMock()

    with patch("utils.audit.create_audit_log", create_audit_log_mock), \
         patch("services.email_service.email_service.send_email", send_email_mock):
        result = await scheduler._send_digest_email(client, content)

    assert result is False
    send_email_mock.assert_not_called()
    create_audit_log_mock.assert_called_once()
    call_kw = create_audit_log_mock.call_args[1]
    assert call_kw["action"] == AuditAction.EMAIL_SKIPPED_NO_RECIPIENT
    assert call_kw["client_id"] == "c1"
    assert call_kw["metadata"]["template"] == EmailTemplateAlias.MONTHLY_DIGEST.value
    assert "properties_count" in call_kw["metadata"]
    assert "total_requirements" in call_kw["metadata"]
