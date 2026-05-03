from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agreement_document_authority import compile_agreement_document
from services.agreement_render_context import (
    PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
    build_agreement_render_context,
)


def _snap(**overrides):
    base = {
        "client_full_name": "Ruth Ehijie",
        "client_company_name": "",
        "client_address": "10 King Street, Chelsea, London, SW3 5XP",
        "client_address_raw": "10 King Street\nChelsea\nLondon\nSW3 5XP",
        "client_postcode": "SW3 5XP",
        "client_email": "ruth@example.co.uk",
        "plan_label": "Solo Landlord",
        "selected_plan_code": "PLAN_1_SOLO",
        "billing_amount_minor": 1999,
        "billing_interval": "month",
        "onboarding_fee_minor": 4900,
        "currency": "GBP",
    }
    base.update(overrides)
    return base


def test_render_hash_changes_between_preview_placeholder_and_accepted_timestamp():
    common = {
        "template_name": "Agreement",
        "template_code": "property_compliance_management_agreement",
        "template_id": "t1",
        "version_id": "v1",
        "version_number": 1,
        "published_at": "2026-01-01T00:00:00Z",
        "effective_from": "2026-01-01T00:00:00Z",
        "title": "Property Compliance Management Agreement",
        "subtitle": "(Compliance Vault Pro Service)",
        "content_blocks": [
            {"key": "electronic_acceptance", "label": "Electronic acceptance", "content": "Accepted by {{accepted_signatory_name}} on {{acceptance_timestamp}}.", "enabled": True, "order": 1}
        ],
    }
    preview_ctx = build_agreement_render_context(
        commercial_snapshot=_snap(),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Ruth Ehijie",
        acceptance_timestamp_display=PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
        agreement_version_number=1,
    )
    accepted_ctx = build_agreement_render_context(
        commercial_snapshot=_snap(),
        settings={"provider_email": "info@pleerityenterprise.co.uk"},
        accepted_signatory_name="Ruth Ehijie",
        acceptance_timestamp_display="2026-04-27T18:42:00Z",
        agreement_version_number=1,
    )
    p = compile_agreement_document(render_context=preview_ctx, **common)
    a = compile_agreement_document(render_context=accepted_ctx, **common)
    assert p["valid"] is True
    assert a["valid"] is True
    assert p["render_hash_sha256"] != a["render_hash_sha256"]


@pytest.mark.asyncio
async def test_create_acceptance_persists_governance_metadata_block():
    from models.agreements import COL_AGREEMENT_ACCEPTANCES
    from services import agreement_acceptance_service as svc

    fake_clients = MagicMock()
    fake_clients.find_one = AsyncMock(return_value={"client_id": "c1", "intake_session_id": "sess-1"})
    acc_coll = MagicMock()
    acc_coll.insert_one = AsyncMock(return_value=MagicMock())

    class _DB:
        clients = fake_clients

        def __getitem__(self, name):
            if name == COL_AGREEMENT_ACCEPTANCES:
                return acc_coll
            return MagicMock()

    rendered = {
        "valid": True,
        "issues": [],
        "document": {"title": "A", "subtitle": "", "sections": []},
        "canonical_text": "Agreement accepted text with UTC timestamp",
        "render_hash_sha256": "abc123",
    }

    with (
        patch.object(svc.database, "get_db", return_value=_DB()),
        patch.object(svc, "get_current_published_bundle", new_callable=AsyncMock, return_value=(
            {"template_id": "t1", "code": "property_compliance_management_agreement", "name": "Agreement"},
            {"version_id": "v1", "version_number": 4, "status": "published", "title": "A", "subtitle": "", "content_blocks": []},
        )),
        patch.object(svc, "build_commercial_snapshot", new_callable=AsyncMock, return_value=_snap()),
        patch.object(svc, "get_system_document_settings", new_callable=AsyncMock, return_value={"provider_email": "info@pleerityenterprise.co.uk"}),
        patch.object(svc, "compile_agreement_document", return_value=rendered),
        patch.object(svc, "create_audit_log", new_callable=AsyncMock),
    ):
        doc, err = await svc.create_acceptance(
            client_id="c1",
            intake_session_id="sess-1",
            template_code="property_compliance_management_agreement",
            acceptance_text_snapshot="I agree",
            accepted_by_name="Ruth Ehijie",
            accepted_by_email="ruth@example.co.uk",
            client_rendered_agreement_hash="abc123",
            ip_address="203.0.113.1",
        )
    assert err is None
    assert doc is not None
    meta = doc.get("acceptance_governance_metadata") or {}
    assert meta.get("agreement_version") == 4
    assert meta.get("accepted_at_utc", "").endswith("Z")
    assert meta.get("render_hash_sha256") == "abc123"
    assert meta.get("agreement_hash_sha256") == "abc123"
    assert meta.get("acceptance_session_id") == "sess-1"
    assert meta.get("acceptance_actor_id") == "c1"
    assert meta.get("acceptance_client_id") == "c1"
    assert meta.get("source_ip") == "203.0.113.1"


@pytest.mark.asyncio
async def test_create_acceptance_rejected_without_client_render_hash():
    """Checkbox / UI alone cannot persist acceptance — server requires matching render digest."""
    from models.agreements import COL_AGREEMENT_ACCEPTANCES
    from services import agreement_acceptance_service as svc

    fake_clients = MagicMock()
    fake_clients.find_one = AsyncMock(return_value={"client_id": "c1", "intake_session_id": "sess-1"})
    acc_coll = MagicMock()
    acc_coll.insert_one = AsyncMock(return_value=MagicMock())

    class _DB:
        clients = fake_clients

        def __getitem__(self, name):
            if name == COL_AGREEMENT_ACCEPTANCES:
                return acc_coll
            return MagicMock()

    rendered = {
        "valid": True,
        "issues": [],
        "document": {"title": "A", "subtitle": "", "sections": []},
        "canonical_text": "Agreement accepted text with UTC timestamp",
        "render_hash_sha256": "abc123",
    }

    with (
        patch.object(svc.database, "get_db", return_value=_DB()),
        patch.object(svc, "get_current_published_bundle", new_callable=AsyncMock, return_value=(
            {"template_id": "t1", "code": "property_compliance_management_agreement", "name": "Agreement"},
            {"version_id": "v1", "version_number": 4, "status": "published", "title": "A", "subtitle": "", "content_blocks": []},
        )),
        patch.object(svc, "build_commercial_snapshot", new_callable=AsyncMock, return_value=_snap()),
        patch.object(svc, "get_system_document_settings", new_callable=AsyncMock, return_value={"provider_email": "info@pleerityenterprise.co.uk"}),
        patch.object(svc, "compile_agreement_document", return_value=rendered),
    ):
        doc, err = await svc.create_acceptance(
            client_id="c1",
            intake_session_id="sess-1",
            template_code="property_compliance_management_agreement",
            acceptance_text_snapshot="I agree",
            accepted_by_name="Ruth Ehijie",
            accepted_by_email="ruth@example.co.uk",
            client_rendered_agreement_hash=None,
        )
    assert doc is None
    assert err == "AGREEMENT_RENDER_HASH_MISSING"
    acc_coll.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_checkout_replay_fails_when_rendered_snapshot_modified():
    from services import agreement_acceptance_service as svc

    acc = {
        "acceptance_id": "acc-t1",
        "client_id": "c1",
        "status": "recorded",
        "template_id": "t1",
        "template_version_id": "v1",
        "accepted_at": "2026-04-27T18:42:00Z",
        "accepted_by_name": "Ruth Ehijie",
        "intake_snapshot": _snap(),
        "agreement_render_validation": {
            "valid": True,
            "render_hash_sha256": "h-ok",
            "rendered_snapshot_hash_sha256": "expected-snapshot-hash",
        },
        "acceptance_governance_metadata": {
            "accepted_at_utc": "2026-04-27T18:42:00Z",
            "render_hash_sha256": "h-ok",
            "agreement_hash_sha256": "h-ok",
            "rendered_snapshot_hash_sha256": "expected-snapshot-hash",
        },
        "rendered_agreement_snapshot": {"title": "Tampered", "subtitle": "", "sections": []},
    }
    fake_db = MagicMock()
    fake_db.__getitem__.return_value.find_one = AsyncMock(return_value=acc)
    with (
        patch.object(svc.database, "get_db", return_value=fake_db),
        patch.object(svc, "hash_document_structure_sha256", return_value="different-snapshot-hash"),
    ):
        out, err = await svc.validate_acceptance_for_checkout(client_id="c1", acceptance_id="acc-t1")
    assert out is None
    assert err == "ACCEPTANCE_INTEGRITY_INVALID"


@pytest.mark.asyncio
async def test_checkout_replay_fails_when_governance_hash_altered():
    from services import agreement_acceptance_service as svc

    acc = {
        "acceptance_id": "acc-t2",
        "client_id": "c1",
        "status": "recorded",
        "template_id": "t1",
        "template_version_id": "v1",
        "accepted_at": "2026-04-27T18:42:00Z",
        "accepted_by_name": "Ruth Ehijie",
        "intake_snapshot": _snap(),
        "agreement_render_validation": {"valid": True, "render_hash_sha256": "h-ok", "rendered_snapshot_hash_sha256": "s-ok"},
        "acceptance_governance_metadata": {
            "accepted_at_utc": "2026-04-27T18:42:00Z",
            "render_hash_sha256": "tampered-hash",
            "agreement_hash_sha256": "tampered-hash",
            "rendered_snapshot_hash_sha256": "s-ok",
        },
        "rendered_agreement_snapshot": {"title": "A", "subtitle": "", "sections": []},
    }
    fake_db = MagicMock()
    fake_db.__getitem__.return_value.find_one = AsyncMock(return_value=acc)
    with patch.object(svc.database, "get_db", return_value=fake_db):
        out, err = await svc.validate_acceptance_for_checkout(client_id="c1", acceptance_id="acc-t2")
    assert out is None
    assert err == "ACCEPTANCE_INTEGRITY_INVALID"


@pytest.mark.asyncio
async def test_checkout_replay_fails_when_accepted_at_changed():
    from services import agreement_acceptance_service as svc

    acc = {
        "acceptance_id": "acc-t3",
        "client_id": "c1",
        "status": "recorded",
        "template_id": "t1",
        "template_version_id": "v1",
        "accepted_at": "2026-04-28T18:42:00Z",
        "accepted_by_name": "Ruth Ehijie",
        "intake_snapshot": _snap(),
        "agreement_render_validation": {"valid": True, "render_hash_sha256": "h-ok", "rendered_snapshot_hash_sha256": "s-ok"},
        "acceptance_governance_metadata": {
            "accepted_at_utc": "2026-04-27T18:42:00Z",
            "render_hash_sha256": "h-ok",
            "agreement_hash_sha256": "h-ok",
            "rendered_snapshot_hash_sha256": "s-ok",
        },
        "rendered_agreement_snapshot": {"title": "A", "subtitle": "", "sections": []},
    }
    fake_db = MagicMock()
    fake_db.__getitem__.return_value.find_one = AsyncMock(return_value=acc)
    with patch.object(svc.database, "get_db", return_value=fake_db):
        out, err = await svc.validate_acceptance_for_checkout(client_id="c1", acceptance_id="acc-t3")
    assert out is None
    assert err == "ACCEPTANCE_INTEGRITY_INVALID"


@pytest.mark.asyncio
async def test_issuance_fails_explicitly_on_acceptance_integrity_invalid():
    from services import agreement_issuance_service as iss

    class _Coll:
        def __init__(self):
            self.find_one = AsyncMock(side_effect=self._find_one)
            self.insert_one = AsyncMock(return_value=MagicMock())

        async def _find_one(self, query, *args, **kwargs):
            if query.get("acceptance_id") == "acc-t4" and len(query.keys()) == 1:
                return {
                    "acceptance_id": "acc-t4",
                    "client_id": "c1",
                    "template_version_id": "v1",
                }
            return None

    class _DB:
        def __getitem__(self, name):
            return _Coll()

    fake_db = _DB()
    with (
        patch.object(iss.database, "get_db", return_value=fake_db),
        patch.object(iss, "_validate_acceptance_integrity", new_callable=AsyncMock, return_value=(False, "ACCEPTANCE_INTEGRITY_INVALID")),
        patch.object(iss, "_fail", new_callable=AsyncMock, return_value=(False, "ACCEPTANCE_INTEGRITY_INVALID", None)),
    ):
        ok, reason, doc = await iss.issue_agreement_for_subscription_payment(
            client_id="c1",
            acceptance_id="acc-t4",
            template_version_id_from_metadata="v1",
            payment_reference="pay-1",
            stripe_event_id="evt-1",
            crn="CRN-1",
        )
    assert ok is False
    assert reason == "ACCEPTANCE_INTEGRITY_INVALID"
    assert doc is None

