"""Agreement render integrity: no demo placeholders, single render context builder, public /current safe."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from server import app
from services.agreement_render_context import (
    PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
    build_agreement_render_context,
    validate_accepted_artifact_text,
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


def test_validate_acceptance_requires_normalized_utc_and_human_display():
    ctx = build_agreement_render_context(
        commercial_snapshot=_snap(),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Jane Example",
        acceptance_timestamp_display="2026-04-27T18:42:00+01:00",
        agreement_version_number=1,
    )
    ok, errs = validate_checkout_grade_render_context(ctx, billing_amount_minor=1999, preview_mode=False)
    assert ok is True
    assert ctx["acceptance_timestamp_utc"].endswith("Z")
    assert "UTC" in ctx["acceptance_timestamp"]


def test_validate_rejects_truncated_address_postcode():
    ctx = build_agreement_render_context(
        commercial_snapshot=_snap(client_address="Chelsea, SW.", client_postcode="SW."),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Jane Example",
        acceptance_timestamp_display="2026-04-27T18:42:00Z",
        agreement_version_number=1,
    )
    ok, errs = validate_checkout_grade_render_context(ctx, billing_amount_minor=1999, preview_mode=False)
    assert ok is False
    assert "client_postcode_malformed_or_truncated" in errs or "client_address_malformed_or_truncated" in errs


def test_validate_rejects_ky0_and_outward_only_ky10():
    """Regression: outward-only or 3-char fragments must not pass as client_postcode."""
    ctx_ky0 = build_agreement_render_context(
        commercial_snapshot=_snap(client_postcode="KY0", client_address="1 High St, Anstruther, KY0"),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Jane Example",
        acceptance_timestamp_display="2026-04-27T18:42:00Z",
        agreement_version_number=1,
    )
    ok0, errs0 = validate_checkout_grade_render_context(ctx_ky0, billing_amount_minor=1999, preview_mode=False)
    assert ok0 is False
    assert "client_postcode_malformed_or_truncated" in errs0

    ctx_out = build_agreement_render_context(
        commercial_snapshot=_snap(client_postcode="KY10", client_address="1 High St, Town, KY10"),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Jane Example",
        acceptance_timestamp_display="2026-04-27T18:42:00Z",
        agreement_version_number=1,
    )
    ok1, errs1 = validate_checkout_grade_render_context(ctx_out, billing_amount_minor=1999, preview_mode=False)
    assert ok1 is False
    assert "client_postcode_malformed_or_truncated" in errs1


def test_accepted_artifact_rejects_preview_placeholder_leak():
    ctx = build_agreement_render_context(
        commercial_snapshot=_snap(),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Jane Example",
        acceptance_timestamp_display="2026-04-27T18:42:00Z",
        agreement_version_number=1,
    )
    ok, errs = validate_accepted_artifact_text(
        canonical_text=f"Accepted on {PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER}",
        render_context=ctx,
    )
    assert ok is False
    assert "accepted_artifact_contains_preview_timestamp_placeholder" in errs


def test_parties_statement_no_company():
    ctx = build_agreement_render_context(
        commercial_snapshot=_snap(client_company_name=""),
        settings={"provider_company_name": "Pleerity Enterprise Ltd", "provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Jane Example",
        acceptance_timestamp_display=PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
        agreement_version_number=1,
    )
    assert 'operating as' not in ctx["parties_statement"].lower()
    assert "where applicable" not in ctx["parties_statement"].lower()


def test_parties_statement_with_company():
    ctx = build_agreement_render_context(
        commercial_snapshot=_snap(client_company_name="ABC Lettings"),
        settings={"provider_company_name": "Pleerity Enterprise Ltd", "provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Jane Example",
        acceptance_timestamp_display=PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
        agreement_version_number=1,
    )
    assert "operating as ABC Lettings" in ctx["parties_statement"]


def test_commercial_wording_context_hardened():
    ctx = build_agreement_render_context(
        commercial_snapshot=_snap(onboarding_fee_minor=4900),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Jane Example",
        acceptance_timestamp_display=PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
        agreement_version_number=1,
    )
    assert "One-time onboarding fee" in ctx["onboarding_fee_line"]


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


@pytest.mark.asyncio
async def test_build_intake_agreement_preview_rejects_truncated_ky0_postcode():
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
                postcode="KY0",
                address_line_1="1 High Street",
                city="Anstruther",
                property_type="house",
                jurisdiction="Scotland",
            )
        ],
        document_submission_method="UPLOAD",
        consent_data_processing=True,
        consent_service_boundary=True,
        intake_session_id="session-aaaa-bbbb",
    )
    with patch("services.agreement_preview_service.get_current_published_bundle", new_callable=AsyncMock, return_value=(tpl, ver)):
        with patch(
            "services.agreement_preview_service.get_system_document_settings",
            new_callable=AsyncMock,
            return_value={"provider_email": "info@pleerityenterprise.co.uk"},
        ):
            payload, err, v_errs = await mod.build_intake_agreement_preview(
                intake_session_id="session-aaaa-bbbb",
                client_id=None,
                intake=intake,
            )
    assert payload is None
    assert err == "AGREEMENT_RENDER_INVALID"
    assert v_errs and "client_postcode_malformed_or_truncated" in v_errs


@pytest.mark.asyncio
async def test_build_intake_agreement_preview_accepts_full_ky10_postcode_from_intake():
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
                postcode="KY10 2AA",
                address_line_1="1 High Street",
                city="Anstruther",
                property_type="house",
                jurisdiction="Scotland",
            )
        ],
        document_submission_method="UPLOAD",
        consent_data_processing=True,
        consent_service_boundary=True,
        intake_session_id="session-aaaa-bbbb",
    )
    with patch("services.agreement_preview_service.get_current_published_bundle", new_callable=AsyncMock, return_value=(tpl, ver)):
        with patch(
            "services.agreement_preview_service.compile_agreement_document",
            return_value={"valid": True, "document": {}, "issues": [], "render_hash_sha256": "a" * 64},
        ):
            with patch(
                "services.agreement_preview_service.get_system_document_settings",
                new_callable=AsyncMock,
                return_value={"provider_email": "info@pleerityenterprise.co.uk"},
            ):
                payload, err, v_errs = await mod.build_intake_agreement_preview(
                    intake_session_id="session-aaaa-bbbb",
                    client_id=None,
                    intake=intake,
                )
    assert err is None
    assert v_errs is None
    assert payload is not None


def test_commercial_snapshot_from_intake_preserves_full_postcode_for_render_context():
    from models.core import BillingPlan, ClientType, IntakeFormData, IntakePropertyData, PreferredContact

    from services.agreement_commercial_snapshot import build_commercial_snapshot_from_intake_form
    from services.agreement_render_context import (
        PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
        build_agreement_render_context,
        validate_checkout_grade_render_context,
    )

    intake = IntakeFormData(
        full_name="Valid User",
        email="valid@example.com",
        client_type=ClientType.INDIVIDUAL,
        preferred_contact=PreferredContact.EMAIL,
        billing_plan=BillingPlan.PLAN_1_SOLO,
        properties=[
            IntakePropertyData(
                postcode="KY102AA",
                address_line_1="1 High Street",
                city="Anstruther",
                property_type="house",
                jurisdiction="Scotland",
            )
        ],
        document_submission_method="UPLOAD",
        consent_data_processing=True,
        consent_service_boundary=True,
        intake_session_id="session-aaaa-bbbb",
    )
    snap = build_commercial_snapshot_from_intake_form(intake, "t1", "v1")
    assert snap["client_postcode"] == "KY10 2AA"
    ctx = build_agreement_render_context(
        commercial_snapshot=snap,
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Valid User",
        acceptance_timestamp_display=PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
        agreement_version_number=1,
    )
    ok, errs = validate_checkout_grade_render_context(
        ctx, billing_amount_minor=int(snap["billing_amount_minor"]), preview_mode=True
    )
    assert ok is True
    assert not errs


def test_preview_electronic_record_line_not_pasted_after_on():
    """Intake preview must not read as 'accepted on <placeholder sentence>'."""
    ctx = build_agreement_render_context(
        commercial_snapshot=_snap(),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Samantha Brown",
        acceptance_timestamp_display=PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
        agreement_version_number=3,
    )
    line = str(ctx.get("acceptance_electronic_record_line") or "")
    assert "not yet recorded" in line.lower()
    assert PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER not in line
    assert ctx.get("acceptance_timestamp") == PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER
