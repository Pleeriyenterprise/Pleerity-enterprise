"""Zoho CRM one-way outbound sync adapter."""
from __future__ import annotations

from typing import Any, Dict

from database import database
from services.integrations.zoho.adapters.base import BaseZohoAdapter
from services.integrations.zoho.client import zoho_http_client
from services.integrations.zoho.config import zoho_crm_module
from services.integrations.zoho.registry import map_lead_to_zoho_crm, validate_inbound_crm_fields
from services.integrations.zoho.sync_store import zoho_sync_store
from services.integrations.zoho.types import SyncResult, SyncStatus


class ZohoCrmAdapter(BaseZohoAdapter):
    integration = "crm"

    async def execute(self, operation: str, payload: Dict[str, Any]) -> SyncResult:
        sync_id = payload.get("sync_id", "")

        if operation == "inbound_rejected":
            blocked = validate_inbound_crm_fields(payload.get("fields") or {})
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=f"inbound_authority_denied:{blocked}",
            )

        lead_id = payload.get("lead_id")
        if not lead_id:
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message="missing_lead_id",
            )

        db = database.get_db()
        lead = await db.leads.find_one({"lead_id": lead_id}, {"_id": 0})
        if not lead:
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message="lead_not_found",
            )

        zoho_payload = {"data": [map_lead_to_zoho_crm(lead)]}
        module = zoho_crm_module()
        existing_zoho_id = await zoho_sync_store.get_external_key("crm", lead_id)

        if existing_zoho_id or operation in ("lead.updated", "lead.stage_changed", "lead.converted", "lead.created"):
            if existing_zoho_id:
                path = f"/crm/v6/{module}/{existing_zoho_id}"
                method = "PUT"
            else:
                path = f"/crm/v6/{module}"
                method = "POST"

            ok, data, err = await zoho_http_client.request(
                method, path, integration=self.integration, json_body=zoho_payload
            )
            if not ok:
                return SyncResult(
                    success=False,
                    sync_id=sync_id,
                    integration=self.integration,
                    operation=operation,
                    status=SyncStatus.FAILED,
                    message=err or "crm_sync_failed",
                )

            zoho_id = existing_zoho_id
            if not zoho_id and data:
                details = (data.get("data") or [{}])[0]
                zoho_id = details.get("details", {}).get("id") or details.get("id")
            if zoho_id:
                await zoho_sync_store.store_external_key("crm", lead_id, str(zoho_id))

            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SUCCESS,
                message="crm_outbound_sync_ok",
                external_id=str(zoho_id) if zoho_id else None,
            )

        return SyncResult(
            success=False,
            sync_id=sync_id,
            integration=self.integration,
            operation=operation,
            status=SyncStatus.FAILED,
            message=f"unknown_operation:{operation}",
        )
