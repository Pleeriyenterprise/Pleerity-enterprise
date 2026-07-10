"""Zoho Analytics read-only export adapter — Analytics API V2 existing-table import."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from services.integrations.zoho.adapters.base import BaseZohoAdapter
from services.integrations.zoho.client import zoho_http_client
from services.integrations.zoho.config import (
    zoho_analytics_api_base,
    zoho_analytics_org_id,
    zoho_analytics_view_id,
    zoho_analytics_workspace_id,
)
from services.integrations.zoho.metrics.analytics_export import build_analytics_export
from services.integrations.zoho.pii import is_aggregate_export_safe
from services.integrations.zoho.types import SyncResult, SyncStatus, SyncSkipReason

# Stable table name for operator-created Phase B table (existing-table import uses view ID).
ANALYTICS_AGGREGATE_TABLE_NAME = "pleerity_daily_aggregates"


def build_analytics_import_config() -> Dict[str, str]:
    """CONFIG query JSON for Zoho Analytics existing-table import."""
    return {
        "importType": "append",
        "fileType": "json",
        "autoIdentify": "true",
    }


def build_analytics_import_data_string(export_data: Dict[str, Any]) -> str:
    """Zoho JSON import expects a JSON array of row objects."""
    return json.dumps([export_data], separators=(",", ":"))


def build_analytics_existing_table_import_path(workspace_id: str, view_id: str) -> str:
    return f"/restapi/v2/workspaces/{workspace_id}/views/{view_id}/data"


def resolve_analytics_import_target() -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Return (url, org_id, missing_keys).

    Existing-table import requires workspace ID, view ID, and Analytics org ID.
    """
    workspace_id = zoho_analytics_workspace_id()
    view_id = zoho_analytics_view_id()
    org_id = zoho_analytics_org_id()
    missing: List[str] = []
    if not workspace_id:
        missing.append("ZOHO_ANALYTICS_WORKSPACE_ID")
    if not view_id:
        missing.append("ZOHO_ANALYTICS_VIEW_ID")
    if not org_id:
        missing.append("ZOHO_ANALYTICS_ORG_ID")
    if missing:
        return None, None, missing
    path = build_analytics_existing_table_import_path(workspace_id, view_id)
    url = f"{zoho_analytics_api_base()}{path}"
    return url, org_id, []


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

        url, org_id, missing = resolve_analytics_import_target()
        if missing:
            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SKIPPED,
                skip_reason=SyncSkipReason.NO_CREDENTIALS,
                message="analytics_import_target_not_configured_export_built_locally",
                metadata={"export": export_data, "missing_config": missing},
            )

        assert url is not None and org_id is not None
        config = build_analytics_import_config()
        data_string = build_analytics_import_data_string(export_data)
        path = build_analytics_existing_table_import_path(
            zoho_analytics_workspace_id(),
            zoho_analytics_view_id(),
        )

        ok, data, err = await zoho_http_client.request(
            "POST",
            path,
            integration=self.integration,
            api_base=zoho_analytics_api_base(),
            params={"CONFIG": json.dumps(config, separators=(",", ":"))},
            form_data={"DATA": data_string},
            headers={"ZANALYTICS-ORGID": org_id},
        )
        if ok:
            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SUCCESS,
                message="analytics_export_delivered",
                metadata={
                    "response": data or {},
                    "import_url": url,
                    "table_name": ANALYTICS_AGGREGATE_TABLE_NAME,
                    "import_type": "append",
                },
            )
        return SyncResult(
            success=False,
            sync_id=sync_id,
            integration=self.integration,
            operation=operation,
            status=SyncStatus.FAILED,
            message=err or "analytics_export_failed",
            metadata={"export": export_data, "import_url": url},
        )
