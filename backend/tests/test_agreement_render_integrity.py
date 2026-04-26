"""Agreement render integrity: no demo placeholders, single render context builder, public /current safe."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from server import app
from services.agreement_render_context import (
    PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
    build_agreement_render_context,
    validate_checkout_grade_render_context,
)


def _snap(**over):
    base = {
        "client_full_name": "Jane Example",
        "client_company_name": "",
        "client_address": "10 Example Road, Manchester, M1 1AA",
        "client_email": "jane@example.co.uk",
        "selected_plan_code": "PLAN_1_SOLO",
        "plan_label": "Solo Landlord",
        "billing_amount_minor": 1999,
        "billing_interval": "month",
        "onboarding_fee_minor": 4900,
        "currency": "GBP",
    }
    base.update(over)
    return base


def test_validate_rejects_demo_client_name():
    ctx = build_agreement_render_context(
        commercial_snapshot=_snap(client_full_name="Client"),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Client",
        acceptance_timestamp_display=PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
        agreement_version_number=1,
    )
    ok, errs = validate_checkout_grade_render_context(ctx, billing_amount_minor=1999, preview_mode=True)
    assert ok is False
    assert "forbidden_client_name_token" in errs


def test_validate_rejects_demo_email():
    ctx = build_agreement_render_context(
        commercial_snapshot=_snap(client_email="client@example.com"),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Jane Example",
        acceptance_timestamp_display=PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
        agreement_version_number=1,
    )
    ok, errs = validate_checkout_grade_render_context(ctx, billing_amount_minor=1999, preview_mode=True)
    assert ok is False
    assert "forbidden_demo_client_email" in errs


def test_validate_rejects_zero_monthly_fee_when_plan_is_priced():
    ctx = build_agreement_render_context(
        commercial_snapshot=_snap(),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Jane Example",
        acceptance_timestamp_display=PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
        agreement_version_number=1,
    )
    ctx["monthly_fee"] = "£0.00"
    ok, errs = validate_checkout_grade_render_context(ctx, billing_amount_minor=1999, preview_mode=True)
    assert ok is False
    assert "forbidden_zero_monthly_fee_when_plan_priced" in errs


def test_validate_preview_requires_safe_timestamp_sentence():
    ctx = build_agreement_render_context(
        commercial_snapshot=_snap(),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Jane Example",
        acceptance_timestamp_display="2026-01-01T12:00:00Z",
        agreement_version_number=1,
    )
    ok, errs = validate_checkout_grade_render_context(ctx, billing_amount_minor=1999, preview_mode=True)
    assert ok is False
    assert "preview_acceptance_timestamp_must_be_safe_sentence" in errs


def test_validate_acceptance_requires_iso_timestamp():
    ctx = build_agreement_render_context(
        commercial_snapshot=_snap(),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Jane Example",
        acceptance_timestamp_display=PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
        agreement_version_number=1,
    )
    ok, errs = validate_checkout_grade_render_context(ctx, billing_amount_minor=1999, preview_mode=False)
    assert ok is False
    assert "forbidden_preview_timestamp_in_acceptance_render" in errs


def test_public_current_has_no_checkout_document_structure():
    tpl = {"template_id": "t1", "code": "property_compliance_management_agreement", "name": "Agreement"}
    ver = {
        "version_id": "v1",
        "version_number": 3,
        "title": "Property Compliance Management Agreement",
        "subtitle": "(Compliance Vault Pro Service)",
        "content_blocks": [{"key": "scope", "label": "Service Scope", "content": "Scope {{client_full_name}}", "enabled": True, "order": 1}],
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
    assert body.get("version_number") == 3
    assert "Client" not in str(body)
    assert "client@example.com" not in str(body).lower()


@pytest.mark.asyncio
async def test_build_intake_agreement_preview_rejects_session_mismatch():
    from models.core import BillingPlan, ClientType, IntakeFormData, IntakePropertyData, PreferredContact
    from services import agreement_preview_service as mod

    tpl = {"template_id": "t1", "code": "c", "name": "A"}
    ver = {
        "version_id": "v1",
        "version_number": 1,
        "title": "T",
        "subtitle": "",
        "content_blocks": [{"key": "k", "label": "L", "content": "Hello {{client_full_name}}", "order": 1, "enabled": True}],
        "published_at": None,
        "effective_from": None,
        "status": "published",
    }

    intake = IntakeFormData(
        full_name="Valid User",
        email="valid@example.com",
        client_type=ClientType.INDIVIDUAL,
        preferred_contact=PreferredContact.EMAIL,
        billing_plan=BillingPlan.PLAN_1_SOLO,
        properties=[
            IntakePropertyData(
                postcode="SW1A 1AA",
                address_line_1="1 Downing St",
                city="London",
                property_type="flat",
                jurisdiction="England",
            )
        ],
        document_submission_method="UPLOAD",
        consent_data_processing=True,
        consent_service_boundary=True,
        intake_session_id="session-aaaa-bbbb",
    )
    with patch("services.agreement_preview_service.get_current_published_bundle", new_callable=AsyncMock, return_value=(tpl, ver)):
        payload, err, _ = await mod.build_intake_agreement_preview(
            intake_session_id="different-session-id-12345",
            client_id=None,
            intake=intake,
        )
    assert payload is None
    assert err == "INTAKE_SESSION_INVALID"
