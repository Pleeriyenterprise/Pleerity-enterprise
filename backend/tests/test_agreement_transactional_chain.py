"""Focused tests: agreement acceptance binding, issuance idempotency, admin agreement routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from middleware import admin_route_guard
from server import app


def test_public_acceptance_403_when_intake_session_invalid():
    with patch("routes.agreements_public.rate_limiter.check_rate_limit", new_callable=AsyncMock, return_value=(True, None)):
        with patch(
            "routes.agreements_public.create_acceptance",
            new_callable=AsyncMock,
            return_value=(None, "INTAKE_SESSION_INVALID"),
        ):
            client = TestClient(app)
            r = client.post(
                "/api/public/agreements/acceptance",
                json={
                    "client_id": "c1",
                    "intake_session_id": "wrong-session",
                    "acceptance_text_snapshot": "I agree to the terms shown.",
                    "accepted_by_name": "Jane",
                    "accepted_by_email": "j@ex.com",
                },
            )
    assert r.status_code == 403
    body = r.json()
    assert body.get("detail", {}).get("error_code") == "INTAKE_SESSION_INVALID"


def test_public_acceptance_422_when_agreement_render_invalid():
    with patch("routes.agreements_public.rate_limiter.check_rate_limit", new_callable=AsyncMock, return_value=(True, None)):
        with patch(
            "routes.agreements_public.create_acceptance",
            new_callable=AsyncMock,
            return_value=(None, "AGREEMENT_RENDER_INVALID"),
        ):
            client = TestClient(app)
            r = client.post(
                "/api/public/agreements/acceptance",
                json={
                    "client_id": "c1",
                    "intake_session_id": "s1",
                    "acceptance_text_snapshot": "I agree to the terms shown.",
                    "accepted_by_name": "Jane",
                    "accepted_by_email": "j@ex.com",
                },
            )
    assert r.status_code == 422
    body = r.json()
    assert body.get("detail", {}).get("error_code") == "AGREEMENT_RENDER_INVALID"


def test_public_current_is_metadata_only_no_checkout_document():
    tpl = {"template_id": "t1", "code": "property_compliance_management_agreement", "name": "Agreement"}
    ver = {
        "version_id": "v1",
        "version_number": 3,
        "title": "Property Compliance Management Agreement",
        "subtitle": "(Compliance Vault Pro Service)",
        "content_blocks": [{"key": "scope", "label": "Service Scope", "content": "Scope text", "enabled": True, "order": 1}],
        "published_at": "2026-01-01T00:00:00Z",
        "effective_from": "2026-01-01T00:00:00Z",
        "status": "published",
    }
    with patch("routes.agreements_public.get_current_published_bundle", new_callable=AsyncMock, return_value=(tpl, ver)):
        client = TestClient(app)
        r = client.get("/api/public/agreements/current")
    assert r.status_code == 200
    body = r.json()
    assert body.get("document_structure") is None
    assert body.get("content_blocks") == []


@pytest.mark.asyncio
async def test_issue_agreement_idempotent_same_stripe_event_no_second_insert():
    """Duplicate Stripe event id does not insert a second issued row when first issuance succeeded."""
    from models.agreements import COL_ISSUED_AGREEMENTS
    from services import agreement_issuance_service as mod

    existing = {
        "issued_id": "issued-1",
        "outcome": "issued",
        "stripe_event_id": "evt_dup",
        "client_id": "c1",
        "acceptance_id": "acc1",
    }
    issued_coll = MagicMock()
    issued_coll.find_one = AsyncMock(return_value=existing)
    issued_coll.insert_one = AsyncMock()

    class FakeDB:
        def __getitem__(self, name):
            if name == COL_ISSUED_AGREEMENTS:
                return issued_coll
            m = MagicMock()
            m.find_one = AsyncMock(return_value=None)
            m.insert_one = AsyncMock()
            return m

    db = FakeDB()

    with patch.object(mod.database, "get_db", return_value=db):
        ok1, e1, d1 = await mod.issue_agreement_for_subscription_payment(
            client_id="c1",
            acceptance_id="acc1",
            template_version_id_from_metadata="v1",
            payment_reference="cs_x",
            stripe_event_id="evt_dup",
            crn="CRN1",
        )
        ok2, e2, d2 = await mod.issue_agreement_for_subscription_payment(
            client_id="c1",
            acceptance_id="acc1",
            template_version_id_from_metadata="v1",
            payment_reference="cs_x",
            stripe_event_id="evt_dup",
            crn="CRN1",
        )
    assert ok1 and ok2
    assert d1.get("issued_id") == "issued-1"
    assert d2.get("issued_id") == "issued-1"
    issued_coll.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_issue_passes_template_version_from_acceptance():
    """Admin retry path must pass acceptance.template_version_id into issuance (not live-catalog drift)."""
    from models.agreements import COL_AGREEMENT_ACCEPTANCES
    from services import agreement_issuance_service as mod

    acc_coll = MagicMock()
    acc_coll.find_one = AsyncMock(
        return_value={
            "acceptance_id": "a1",
            "client_id": "c1",
            "template_version_id": "ver-bound-to-acceptance",
        }
    )

    class FakeDB:
        def __getitem__(self, name):
            if name == COL_AGREEMENT_ACCEPTANCES:
                return acc_coll
            m = MagicMock()
            m.find_one = AsyncMock(return_value=None)
            return m

    db = FakeDB()

    captured = {}

    async def fake_issue(**kwargs):
        captured.update(kwargs)
        return True, None, {"issued_id": "i1"}

    with patch.object(mod.database, "get_db", return_value=db):
        with patch.object(mod, "issue_agreement_for_subscription_payment", fake_issue):
            with patch.object(mod, "create_audit_log", new_callable=AsyncMock):
                ok, err, doc = await mod.issue_agreement_for_subscription_payment_retry(
                    client_id="c1",
                    acceptance_id="a1",
                    payment_reference="cs_pay",
                    crn="CRN9",
                )
    assert ok and doc
    assert captured.get("template_version_id_from_metadata") == "ver-bound-to-acceptance"
    assert captured.get("acceptance_id") == "a1"
    assert captured.get("crn") == "CRN9"


def test_admin_issued_agreement_pdf_requires_auth():
    client = TestClient(app)
    r = client.get("/api/admin/clients/c1/agreements/issued/i1/pdf")
    assert r.status_code in (401, 403)


def test_admin_issued_agreement_pdf_with_admin_auth_loads_bytes():
    """With admin dependency satisfied, PDF route returns application/pdf when storage has bytes."""
    app.dependency_overrides[admin_route_guard] = _admin_user
    client = TestClient(app)
    try:
        with patch(
            "routes.admin_client_agreements.load_issued_pdf_bytes",
            new_callable=AsyncMock,
            return_value=b"%PDF-1.4 test",
        ):
            r = client.get("/api/admin/clients/c1/agreements/issued/i9/pdf")
        assert r.status_code == 200
        assert "application/pdf" in (r.headers.get("content-type") or "")
    finally:
        app.dependency_overrides.clear()
        client.close()


def test_admin_retry_issue_requires_auth():
    client = TestClient(app)
    r = client.post(
        "/api/admin/clients/c1/agreements/retry-issue",
        json={"acceptance_id": "a1", "payment_reference": "cs_x"},
    )
    assert r.status_code in (401, 403)


def _admin_user():
    return {"user_id": "admin-1", "email": "admin@example.com", "role": "ADMIN"}


def test_admin_retry_wrong_client_scoped_returns_error():
    """Retry for another client's acceptance_id must not issue (acceptance not found for path client)."""
    app.dependency_overrides[admin_route_guard] = _admin_user
    client = TestClient(app)
    try:
        mock_db = MagicMock()
        mock_db.clients.find_one = AsyncMock(return_value={"customer_reference": "CRN12345"})
        with patch("routes.admin_client_agreements.database.get_db", return_value=mock_db):
            with patch(
                "routes.admin_client_agreements.issue_agreement_for_subscription_payment_retry",
                new_callable=AsyncMock,
                return_value=(False, "ACCEPTANCE_NOT_FOUND", None),
            ):
                r = client.post(
                    "/api/admin/clients/client-A/agreements/retry-issue",
                    json={"acceptance_id": "belongs-to-B", "payment_reference": "cs_123"},
                )
        assert r.status_code == 400
        assert "ACCEPTANCE_NOT_FOUND" in str(r.json())
    finally:
        app.dependency_overrides.clear()
        client.close()


def test_legacy_checkout_skips_issuance_audit_path_exists():
    """Regression anchor: webhook documents skip when acceptance metadata missing (no architecture change)."""
    from models import AuditAction

    assert hasattr(AuditAction, "AGREEMENT_ISSUANCE_SKIPPED_LEGACY_CHECKOUT")
