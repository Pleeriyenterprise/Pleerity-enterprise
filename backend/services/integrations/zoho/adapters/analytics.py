"""Zoho Analytics read-only export adapter."""
from __future__ import annotations

from typing import Any, Dict

from services.integrations.zoho.adapters.base import BaseZohoAdapter
from services.integrations.zoho.client import zoho_http_client
from services.integrations.zoho.config import zoho_analytics_workspace_id
from services.integrations.zoho.metrics.analytics_export import build_analytics_export
from services.integrations.zoho.pii import is_aggregate_export_safe
from services.integrations.zoho.types import SyncResult, SyncStatus, SyncSkipReason


class ZohoAnalyticsAdapter(BaseZohoAdapter):
    integration = "analytics"

    async def execute(self, operation: str, payload: Dict[str, Any]) -> SyncResult:
        sync_id = payload.get("sync_id", "")
        if operation != "export_aggregates":
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=f"unknown_operation:{operation}",
            )

        export_data = payload.get("export_data")
        if not export_data:
            export_data = await build_analytics_export()

        if not is_aggregate_export_safe(export_data):
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SKIPPED,
                skip_reason=SyncSkipReason.PII_BLOCKED,
                message="aggregate_export_contains_pii",
            )

        workspace_id = zoho_analytics_workspace_id()
        if not workspace_id:
            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SKIPPED,
                skip_reason=SyncSkipReason.NO_CREDENTIALS,
                message="analytics_workspace_not_configured_export_built_locally",
                metadata={"export": export_data},
            )

        path = f"/analytics/v2/workspaces/{workspace_id}/data"
        ok, data, err = await zoho_http_client.request(
            "POST",
            path,
            integration=self.integration,
            json_body={"data": export_data, "import_type": "append"},
        )
        if ok:
            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SUCCESS,
                message="analytics_export_delivered",
                metadata={"response": data or {}},
            )
        return SyncResult(
            success=False,
            sync_id=sync_id,
            integration=self.integration,
            operation=operation,
            status=SyncStatus.FAILED,
            message=err or "analytics_export_failed",
            metadata={"export": export_data},
        )
