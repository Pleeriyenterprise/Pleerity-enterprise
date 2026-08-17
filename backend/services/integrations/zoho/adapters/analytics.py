"""Zoho Analytics read-only export adapter — Analytics API V2 existing-table import."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from services.integrations.zoho.adapters.base import BaseZohoAdapter
from services.integrations.zoho.client import zoho_http_client
from services.integrations.zoho.config import (
    analytics_target_config_snapshot,
    zoho_analytics_api_base,
    zoho_analytics_org_id,
    zoho_analytics_view_id,
    zoho_analytics_workspace_id,
)
from services.integrations.zoho.metrics.analytics_export import (
    ANALYTICS_DAILY_AGGREGATE_COLUMNS,
    build_analytics_export,
    validate_analytics_export_payload,
)
from services.integrations.zoho.pii import is_aggregate_export_safe
from services.integrations.zoho.sync_store import zoho_sync_store
from services.integrations.zoho.types import SyncResult, SyncStatus, SyncSkipReason

# Stable table name for operator-created Phase B table (existing-table import uses view ID).
ANALYTICS_AGGREGATE_TABLE_NAME = "pleerity_daily_aggregates"

_ID_RE = re.compile(r"^\d{6,}$")


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


def validate_analytics_import_config() -> List[str]:
    """
    Local configuration / schema-contract checks before any Zoho call.

    Remote workspace/view existence requires Analytics metadata scopes not assumed
    for Phase B (data.create only). Operators still receive actionable diagnostics
    for missing/malformed IDs and the required column contract.
    """
    issues: List[str] = []
    target = analytics_target_config_snapshot()
    issues.extend(f"missing_config:{key}" for key in target.get("missing") or [])
    workspace = zoho_analytics_workspace_id()
    view = zoho_analytics_view_id()
    org = zoho_analytics_org_id()
    if workspace and not _ID_RE.match(workspace):
        issues.append("workspace_id_malformed_expected_numeric")
    if view and not _ID_RE.match(view):
        issues.append("view_id_malformed_expected_numeric")
    if org and not _ID_RE.match(org):
        issues.append("org_id_malformed_expected_numeric")
    if not zoho_analytics_api_base().startswith("https://"):
        issues.append("analytics_api_base_must_be_https")
    return issues


def _period_result_summary(export_data: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
    return {
        "period_start": export_data.get("period_start"),
        "period_end": export_data.get("period_end"),
        "payload_version": export_data.get("payload_version"),
        "export_type": export_data.get("export_type"),
        "table_name": ANALYTICS_AGGREGATE_TABLE_NAME,
        "import_type": "append",
        "column_count": len(ANALYTICS_DAILY_AGGREGATE_COLUMNS),
        **extra,
    }


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

        config_issues = validate_analytics_import_config()
        if config_issues:
            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SKIPPED,
                skip_reason=SyncSkipReason.CONFIG_INVALID,
                message="analytics_config_invalid:" + ";".join(config_issues),
                metadata={"config_issues": config_issues, "target": analytics_target_config_snapshot()},
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

        payload_issues = validate_analytics_export_payload(export_data)
        if payload_issues:
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SKIPPED,
                skip_reason=SyncSkipReason.PAYLOAD_INVALID,
                message="analytics_payload_invalid:" + ";".join(payload_issues),
                metadata={"payload_issues": payload_issues},
            )

        force_reexport = bool(payload.get("force_reexport"))
        period_start = str(export_data.get("period_start") or "")
        period_end = str(export_data.get("period_end") or "")
        if not force_reexport and period_start and period_end:
            prior = await zoho_sync_store.find_successful_analytics_period_export(
                period_start, period_end
            )
            if prior:
                return SyncResult(
                    success=True,
                    sync_id=sync_id,
                    integration=self.integration,
                    operation=operation,
                    status=SyncStatus.SKIPPED,
                    skip_reason=SyncSkipReason.DUPLICATE_PERIOD,
                    message=(
                        "period_already_exported:"
                        f"{prior.get('sync_id')}:use_force_reexport_true_to_override"
                    ),
                    metadata={
                        "prior_sync_id": prior.get("sync_id"),
                        "prior_completed_at": prior.get("completed_at"),
                        "result_summary": _period_result_summary(export_data),
                    },
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
        summary = _period_result_summary(
            export_data,
            force_reexport=force_reexport,
            workspace_configured=True,
            view_configured=True,
            org_configured=True,
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
                    "table_name": ANALYTICS_AGGREGATE_TABLE_NAME,
                    "import_type": "append",
                    "result_summary": summary,
                },
            )
        return SyncResult(
            success=False,
            sync_id=sync_id,
            integration=self.integration,
            operation=operation,
            status=SyncStatus.FAILED,
            message=err or "analytics_export_failed",
            metadata={
                "export_period_start": period_start,
                "export_period_end": period_end,
                "result_summary": summary,
            },
        )
