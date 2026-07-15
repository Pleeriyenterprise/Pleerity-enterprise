"""Tests for governed Zoho CRM outbound sync (Phase C)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.integrations.zoho.adapters.crm import (
    ZohoCrmAdapter,
    build_pleerity_lead_id_search_criteria,
)
from services.integrations.zoho.registry import (
    map_lead_to_zoho_crm,
    validate_crm_outbound_payload,
)
from services.integrations.zoho.types import SyncSkipReason, SyncStatus


@pytest.fixture(autouse=True)
def zoho_flags(monkeypatch):
    monkeypatch.setenv("ZOHO_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("ZOHO_CRM_SYNC_ENABLED", "true")
    monkeypatch.setenv("ZOHO_KILL_SWITCH", "false")
    monkeypatch.setenv("ZOHO_CLIENT_ID", "cid")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("ZOHO_CRM_REFRESH_TOKEN", "crm-refresh")
    monkeypatch.setenv("ZOHO_CRM_MODULE", "Leads")


def test_search_criteria_uses_pleerity_lead_id_only():
    assert build_pleerity_lead_id_search_criteria("LEAD-1") == "(Pleerity_Lead_ID:equals:LEAD-1)"
    assert "Email" not in build_pleerity_lead_id_search_criteria("LEAD-1")


def test_map_lead_derives_last_name_from_display_name():
    mapped = map_lead_to_zoho_crm(
        {
            "lead_id": "LEAD-NAME",
            "email": "n@example.com",
            "name": "Staging Display Name",
            "last_name": None,
        }
    )
    assert mapped["Last_Name"] == "Staging Display Name"
    assert mapped["Pleerity_Lead_ID"] == "LEAD-NAME"
    assert validate_crm_outbound_payload(mapped) == []


def test_validate_crm_payload_requires_identity_email_lastname():
    issues = validate_crm_outbound_payload({})
    assert "payload_empty_or_not_object" in issues
    mapped = map_lead_to_zoho_crm(
        {"lead_id": "LEAD-9", "email": "a@b.com", "last_name": "Smith", "first_name": "A"}
    )
    assert validate_crm_outbound_payload(mapped) == []
    bad = map_lead_to_zoho_crm({"lead_id": "LEAD-9", "email": "a@b.com"})
    assert "missing_required:Last_Name" in validate_crm_outbound_payload(bad)


def test_crm_expected_scope_includes_read():
    from services.integrations.zoho.oauth_credential_registry import OAUTH_INTEGRATION_REGISTRY

    scope = OAUTH_INTEGRATION_REGISTRY["crm"].expected_scope
    assert "CREATE" in scope
    assert "UPDATE" in scope
    assert "READ" in scope
    assert "ALL" not in scope


@pytest.mark.asyncio
async def test_crm_create_persists_external_key(monkeypatch):
    lead = {
        "lead_id": "LEAD-100",
        "email": "create@example.com",
        "last_name": "Create",
        "first_name": "Test",
        "stage": "NEW",
    }
    mock_db = MagicMock()
    mock_db.leads.find_one = AsyncMock(return_value=lead)

    with (
        patch("services.integrations.zoho.adapters.crm.database.get_db", return_value=mock_db),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_sync_store.get_external_key",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "services.integrations.zoho.adapters.crm.lookup_zoho_id_by_pleerity_lead_id",
            new_callable=AsyncMock,
            return_value=(None, None),
        ),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_http_client.request",
            new_callable=AsyncMock,
            return_value=(True, {"data": [{"details": {"id": "ZCRM-9"}}]}, None),
        ) as http,
        patch(
            "services.integrations.zoho.adapters.crm.zoho_sync_store.store_external_key",
            new_callable=AsyncMock,
            return_value="ZCRM-9",
        ) as store,
    ):
        result = await ZohoCrmAdapter().execute(
            "lead.created", {"sync_id": "ZSYNC-1", "lead_id": "LEAD-100"}
        )
    assert result.status == SyncStatus.SUCCESS
    assert result.external_id == "ZCRM-9"
    store.assert_awaited_with("crm", "LEAD-100", "ZCRM-9")
    assert http.await_args.args[0] == "POST"
    assert result.metadata["result_summary"]["identity_source"] == "create"
    assert result.metadata["result_summary"]["external_key_persisted"] is True


@pytest.mark.asyncio
async def test_crm_create_without_id_is_failure():
    lead = {
        "lead_id": "LEAD-101",
        "email": "noid@example.com",
        "last_name": "NoId",
    }
    mock_db = MagicMock()
    mock_db.leads.find_one = AsyncMock(return_value=lead)
    with (
        patch("services.integrations.zoho.adapters.crm.database.get_db", return_value=mock_db),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_sync_store.get_external_key",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "services.integrations.zoho.adapters.crm.lookup_zoho_id_by_pleerity_lead_id",
            new_callable=AsyncMock,
            return_value=(None, None),
        ),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_http_client.request",
            new_callable=AsyncMock,
            return_value=(True, {"data": [{}]}, None),
        ),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_sync_store.store_external_key",
            new_callable=AsyncMock,
        ) as store,
    ):
        result = await ZohoCrmAdapter().execute(
            "upsert_lead", {"sync_id": "ZSYNC-2", "lead_id": "LEAD-101"}
        )
    assert result.status == SyncStatus.FAILED
    assert result.message == "crm_create_external_id_not_extracted"
    store.assert_not_awaited()


@pytest.mark.asyncio
async def test_crm_identity_lookup_before_create():
    lead = {
        "lead_id": "LEAD-102",
        "email": "exist@example.com",
        "last_name": "Exist",
    }
    mock_db = MagicMock()
    mock_db.leads.find_one = AsyncMock(return_value=lead)
    with (
        patch("services.integrations.zoho.adapters.crm.database.get_db", return_value=mock_db),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_sync_store.get_external_key",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "services.integrations.zoho.adapters.crm.lookup_zoho_id_by_pleerity_lead_id",
            new_callable=AsyncMock,
            return_value=("ZCRM-EXIST", None),
        ),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_http_client.request",
            new_callable=AsyncMock,
            return_value=(True, {"data": [{"details": {"id": "ZCRM-EXIST"}}]}, None),
        ) as http,
        patch(
            "services.integrations.zoho.adapters.crm.zoho_sync_store.store_external_key",
            new_callable=AsyncMock,
            return_value="ZCRM-EXIST",
        ) as store,
    ):
        result = await ZohoCrmAdapter().execute(
            "lead.updated", {"sync_id": "ZSYNC-3", "lead_id": "LEAD-102"}
        )
    assert result.status == SyncStatus.SUCCESS
    assert result.external_id == "ZCRM-EXIST"
    assert http.await_args.args[0] == "PUT"
    assert result.metadata["result_summary"]["identity_source"] == "pleerity_lead_id_lookup"
    assert result.metadata["result_summary"]["duplicate_create_prevented"] is True
    assert store.await_count >= 1


@pytest.mark.asyncio
async def test_crm_update_uses_external_key_first():
    lead = {
        "lead_id": "LEAD-103",
        "email": "upd@example.com",
        "last_name": "Upd",
    }
    mock_db = MagicMock()
    mock_db.leads.find_one = AsyncMock(return_value=lead)
    with (
        patch("services.integrations.zoho.adapters.crm.database.get_db", return_value=mock_db),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_sync_store.get_external_key",
            new_callable=AsyncMock,
            return_value="ZCRM-LOCAL",
        ),
        patch(
            "services.integrations.zoho.adapters.crm.lookup_zoho_id_by_pleerity_lead_id",
            new_callable=AsyncMock,
        ) as lookup,
        patch(
            "services.integrations.zoho.adapters.crm.zoho_http_client.request",
            new_callable=AsyncMock,
            return_value=(True, {"data": [{"details": {"id": "ZCRM-LOCAL"}}]}, None),
        ),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_sync_store.store_external_key",
            new_callable=AsyncMock,
            return_value="ZCRM-LOCAL",
        ),
    ):
        result = await ZohoCrmAdapter().execute(
            "lead.lost", {"sync_id": "ZSYNC-4", "lead_id": "LEAD-103"}
        )
    assert result.status == SyncStatus.SUCCESS
    lookup.assert_not_awaited()
    assert result.metadata["result_summary"]["identity_source"] == "external_key"


@pytest.mark.asyncio
async def test_crm_soft_fail_enters_dead_letter():
    from services.integrations.zoho.service import ZohoIntegrationService
    from services.integrations.zoho.types import SyncResult

    svc = ZohoIntegrationService()
    failed = SyncResult(
        success=False,
        sync_id="ZSYNC-DL",
        integration="crm",
        operation="upsert_lead",
        status=SyncStatus.FAILED,
        message="crm_create_external_id_not_extracted",
        metadata={"result_summary": {"lead_id": "LEAD-X"}},
    )
    with (
        patch(
            "services.integrations.zoho.service.zoho_sync_store.create_run",
            new_callable=AsyncMock,
            return_value="ZSYNC-DL",
        ),
        patch(
            "services.integrations.zoho.service.zoho_sync_store.mark_running",
            new_callable=AsyncMock,
        ),
        patch(
            "services.integrations.zoho.service.get_adapter",
            return_value=MagicMock(authority_check_outbound=lambda p: None, execute=AsyncMock(return_value=failed)),
        ),
        patch(
            "services.integrations.zoho.service.zoho_oauth_configured_for",
            return_value=True,
        ),
        patch(
            "services.integrations.zoho.service.zoho_integration_enabled",
            return_value=True,
        ),
        patch(
            "services.integrations.zoho.service.zoho_kill_switch_active",
            return_value=False,
        ),
        patch(
            "services.integrations.zoho.service.is_integration_enabled",
            return_value=True,
        ),
        patch(
            "services.integrations.zoho.service.zoho_sync_store.add_dead_letter",
            new_callable=AsyncMock,
            return_value="ZDL-1",
        ) as add_dl,
        patch(
            "services.integrations.zoho.service.log_zoho_sync_event",
            new_callable=AsyncMock,
        ),
    ):
        result = await svc.run_sync("crm", "upsert_lead", {"lead_id": "LEAD-X"})
    assert result.status == SyncStatus.DEAD_LETTER
    add_dl.assert_awaited()


@pytest.mark.asyncio
async def test_crm_payload_invalid_skips_without_http():
    lead = {"lead_id": "LEAD-104", "email": "x@y.com"}  # missing last_name
    mock_db = MagicMock()
    mock_db.leads.find_one = AsyncMock(return_value=lead)
    with (
        patch("services.integrations.zoho.adapters.crm.database.get_db", return_value=mock_db),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_http_client.request",
            new_callable=AsyncMock,
        ) as http,
    ):
        result = await ZohoCrmAdapter().execute(
            "upsert_lead", {"sync_id": "ZSYNC-5", "lead_id": "LEAD-104"}
        )
    assert result.status == SyncStatus.SKIPPED
    assert result.skip_reason == SyncSkipReason.PAYLOAD_INVALID
    http.assert_not_awaited()


def test_extract_duplicate_crm_record_id_from_body():
    from services.integrations.zoho.adapters.crm import extract_duplicate_crm_record_id

    body = {
        "data": [
            {
                "code": "DUPLICATE_DATA",
                "details": {
                    "api_name": "Pleerity_Lead_ID",
                    "duplicate_record": {"id": "625014000001936001"},
                },
            }
        ]
    }
    assert extract_duplicate_crm_record_id("Zoho API 400: truncated", body) == "625014000001936001"


def test_extract_duplicate_crm_record_id_from_error_text():
    from services.integrations.zoho.adapters.crm import extract_duplicate_crm_record_id

    err = (
        'Zoho API 400: {"data":[{"code":"DUPLICATE_DATA","details":'
        '{"api_name":"Pleerity_Lead_ID","duplicate_record":{"id":"991"}}]}'
    )
    assert extract_duplicate_crm_record_id(err, None) == "991"


@pytest.mark.asyncio
async def test_crm_duplicate_data_binds_from_duplicate_record_id_without_search():
    lead = {
        "lead_id": "LEAD-DUP",
        "email": "dup@example.com",
        "last_name": "Dup",
    }
    mock_db = MagicMock()
    mock_db.leads.find_one = AsyncMock(return_value=lead)
    err_body = {
        "data": [
            {
                "code": "DUPLICATE_DATA",
                "details": {"duplicate_record": {"id": "ZCRM-DUP-1"}},
            }
        ]
    }
    http = AsyncMock(
        side_effect=[
            (False, err_body, 'Zoho API 400: {"data":[{"code":"DUPLICATE_DATA"}]}'),
            (True, {"data": [{"details": {"id": "ZCRM-DUP-1"}}]}, None),
        ]
    )
    with (
        patch("services.integrations.zoho.adapters.crm.database.get_db", return_value=mock_db),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_sync_store.get_external_key",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "services.integrations.zoho.adapters.crm.lookup_zoho_id_by_pleerity_lead_id",
            new_callable=AsyncMock,
            return_value=(None, None),
        ) as lookup,
        patch(
            "services.integrations.zoho.adapters.crm.zoho_http_client.request",
            new=http,
        ),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_sync_store.store_external_key",
            new_callable=AsyncMock,
            return_value="ZCRM-DUP-1",
        ) as store,
    ):
        result = await ZohoCrmAdapter().execute(
            "upsert_lead", {"sync_id": "ZSYNC-DUP", "lead_id": "LEAD-DUP"}
        )
    assert result.status == SyncStatus.SUCCESS
    assert result.external_id == "ZCRM-DUP-1"
    assert result.message == "crm_outbound_bound_after_duplicate"
    assert result.metadata["result_summary"]["identity_source"] == "duplicate_record_id"
    store.assert_awaited_with("crm", "LEAD-DUP", "ZCRM-DUP-1")
    # Pre-create identity lookup only — no Search fallback after duplicate_record.id bind
    assert lookup.await_count == 1
    assert http.await_args_list[0].args[0] == "POST"
    assert http.await_args_list[1].args[0] == "PUT"

@pytest.mark.asyncio
async def test_crm_duplicate_data_falls_back_to_search_when_id_absent():
    lead = {
        "lead_id": "LEAD-DUP2",
        "email": "dup2@example.com",
        "last_name": "Dup2",
    }
    mock_db = MagicMock()
    mock_db.leads.find_one = AsyncMock(return_value=lead)
    http = AsyncMock(
        side_effect=[
            (False, {"data": [{"code": "DUPLICATE_DATA", "details": {}}]}, "Zoho API 400: DUPLICATE_DATA"),
            (True, {"data": [{"details": {"id": "ZCRM-SEARCH"}}]}, None),
        ]
    )
    with (
        patch("services.integrations.zoho.adapters.crm.database.get_db", return_value=mock_db),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_sync_store.get_external_key",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "services.integrations.zoho.adapters.crm.lookup_zoho_id_by_pleerity_lead_id",
            new_callable=AsyncMock,
            side_effect=[(None, None), ("ZCRM-SEARCH", None)],
        ),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_http_client.request",
            new=http,
        ),
        patch(
            "services.integrations.zoho.adapters.crm.zoho_sync_store.store_external_key",
            new_callable=AsyncMock,
            return_value="ZCRM-SEARCH",
        ),
    ):
        result = await ZohoCrmAdapter().execute(
            "upsert_lead", {"sync_id": "ZSYNC-DUP2", "lead_id": "LEAD-DUP2"}
        )
    assert result.status == SyncStatus.SUCCESS
    assert result.external_id == "ZCRM-SEARCH"
    assert result.metadata["result_summary"]["identity_source"] == "duplicate_conflict_lookup"
