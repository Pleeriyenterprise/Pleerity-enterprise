"""Zoho Sign webhook processing adapter (outbound archive only)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from services.integrations.zoho.adapters.base import BaseZohoAdapter
from services.integrations.zoho.registry import SIGN_ALLOWED_CATEGORIES, SIGN_FORBIDDEN_CATEGORIES
from services.integrations.zoho.types import SyncResult, SyncStatus


class ZohoSignAdapter(BaseZohoAdapter):
    integration = "sign"

    async def execute(self, operation: str, payload: Dict[str, Any]) -> SyncResult:
        sync_id = payload.get("sync_id", "")

        if operation == "process_completion":
            category = str(payload.get("category") or payload.get("document_category") or "").lower()
            if category in SIGN_FORBIDDEN_CATEGORIES:
                return SyncResult(
                    success=False,
                    sync_id=sync_id,
                    integration=self.integration,
                    operation=operation,
                    status=SyncStatus.FAILED,
                    message=f"sign_forbidden_category:{category}",
                )
            if category and category not in SIGN_ALLOWED_CATEGORIES:
                return SyncResult(
                    success=False,
                    sync_id=sync_id,
                    integration=self.integration,
                    operation=operation,
                    status=SyncStatus.FAILED,
                    message=f"sign_unapproved_category:{category}",
                )

            audit_record = {
                "zoho_request_id": payload.get("request_id"),
                "document_name": payload.get("document_name"),
                "category": category or "b2b_agreement",
                "completed_at": payload.get("completed_at") or datetime.now(timezone.utc).isoformat(),
                "signed_document_url": payload.get("document_url"),
                "business_record_id": payload.get("business_record_id"),
                "integration": "zoho_sign",
            }
            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SUCCESS,
                message="sign_completion_recorded",
                metadata={"audit_record": audit_record},
            )

        return SyncResult(
            success=False,
            sync_id=sync_id,
            integration=self.integration,
            operation=operation,
            status=SyncStatus.FAILED,
            message=f"unknown_operation:{operation}",
        )
