"""Zoho WorkDrive internal document archive — never customer compliance evidence."""
from __future__ import annotations

from typing import Any, Dict

from services.integrations.zoho.adapters.base import BaseZohoAdapter
from services.integrations.zoho.client import zoho_http_client
from services.integrations.zoho.config import zoho_workdrive_folder_id
from services.integrations.zoho.registry import WORKDRIVE_ALLOWED_CATEGORIES, WORKDRIVE_FORBIDDEN_CATEGORIES
from services.integrations.zoho.types import SyncResult, SyncStatus


class ZohoWorkdriveAdapter(BaseZohoAdapter):
    integration = "workdrive"

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

        category = str(payload.get("category") or "").lower()
        if category in WORKDRIVE_FORBIDDEN_CATEGORIES:
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=f"workdrive_forbidden_category:{category}",
            )
        if category and category not in WORKDRIVE_ALLOWED_CATEGORIES:
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=f"workdrive_unapproved_category:{category}",
            )

        if operation != "archive_document":
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=f"unknown_operation:{operation}",
            )

        folder_id = zoho_workdrive_folder_id()
        if not folder_id:
            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SUCCESS,
                message="workdrive_archive_skipped_no_folder",
                metadata={"document": payload.get("document_name")},
            )

        ok, data, err = await zoho_http_client.request(
            "POST",
            f"/workdrive/api/v1/upload",
            integration=self.integration,
            json_body={
                "folder_id": folder_id,
                "file_name": payload.get("document_name"),
                "file_url": payload.get("document_url"),
                "category": category or "internal",
            },
        )
        if ok:
            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SUCCESS,
                message="workdrive_archive_ok",
                external_id=str((data or {}).get("file_id")),
            )
        return SyncResult(
            success=False,
            sync_id=sync_id,
            integration=self.integration,
            operation=operation,
            status=SyncStatus.FAILED,
            message=err or "workdrive_archive_failed",
        )
