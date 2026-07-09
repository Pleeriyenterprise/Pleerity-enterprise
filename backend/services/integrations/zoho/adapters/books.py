"""Zoho Books finance export — Stripe summaries only, never client_billing writes."""
from __future__ import annotations

from typing import Any, Dict

from services.integrations.zoho.adapters.base import BaseZohoAdapter
from services.integrations.zoho.client import zoho_http_client
from services.integrations.zoho.config import zoho_org_id
from services.integrations.zoho.metrics.books_export import build_books_export
from services.integrations.zoho.types import SyncResult, SyncStatus


class ZohoBooksAdapter(BaseZohoAdapter):
    integration = "books"

    async def execute(self, operation: str, payload: Dict[str, Any]) -> SyncResult:
        sync_id = payload.get("sync_id", "")

        auth_err = self.authority_check_outbound(payload)
        if auth_err:
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=auth_err,
            )

        if operation == "inbound_rejected":
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message="books_inbound_writes_forbidden",
            )

        if operation != "export_finance_summary":
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=f"unknown_operation:{operation}",
            )

        export_data = payload.get("export_data") or await build_books_export()
        org = zoho_org_id()
        if not org:
            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SUCCESS,
                message="books_export_built_locally_no_org",
                metadata={"export": export_data},
            )

        ok, data, err = await zoho_http_client.request(
            "POST",
            f"/books/v3/journals?organization_id={org}",
            integration=self.integration,
            json_body=export_data,
        )
        if ok:
            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SUCCESS,
                message="books_export_delivered",
                metadata={"response": data or {}},
            )
        return SyncResult(
            success=False,
            sync_id=sync_id,
            integration=self.integration,
            operation=operation,
            status=SyncStatus.FAILED,
            message=err or "books_export_failed",
            metadata={"export": export_data},
        )
