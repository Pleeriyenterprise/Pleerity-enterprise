"""Central Zoho integration service — single entry for all sync operations."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.integrations.zoho.adapters.registry import get_adapter
from services.integrations.zoho.audit_helper import log_zoho_sync_event
from services.integrations.zoho.config import (
    is_integration_enabled,
    zoho_credentials_configured,
    zoho_integration_enabled,
    zoho_kill_switch_active,
)
from services.integrations.zoho.sync_store import zoho_sync_store
from services.integrations.zoho.types import (
    SyncDirection,
    SyncResult,
    SyncSkipReason,
    SyncStatus,
)

logger = logging.getLogger(__name__)


class ZohoIntegrationService:
    async def run_sync(
        self,
        integration: str,
        operation: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        actor_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> SyncResult:
        payload = dict(payload or {})

        if not zoho_integration_enabled():
            return self._skipped(integration, operation, SyncSkipReason.DISABLED)

        if zoho_kill_switch_active():
            return self._skipped(integration, operation, SyncSkipReason.KILL_SWITCH)

        if not is_integration_enabled(integration):
            return self._skipped(integration, operation, SyncSkipReason.DISABLED)

        adapter = get_adapter(integration)
        if not adapter:
            sync_id = await zoho_sync_store.create_run(
                integration=integration,
                operation=operation,
                direction=SyncDirection.OUTBOUND,
            )
            await zoho_sync_store.complete_run(
                sync_id, status=SyncStatus.FAILED, error=f"unknown_integration:{integration}"
            )
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=f"unknown_integration:{integration}",
            )

        auth_err = adapter.authority_check_outbound(payload)
        if auth_err:
            sync_id = await zoho_sync_store.create_run(
                integration=integration,
                operation=operation,
                direction=SyncDirection.OUTBOUND,
                payload_summary={"blocked": auth_err},
            )
            await zoho_sync_store.complete_run(sync_id, status=SyncStatus.FAILED, error=auth_err)
            await log_zoho_sync_event(
                integration=integration,
                operation=operation,
                sync_id=sync_id,
                status="authority_denied",
                actor_id=actor_id,
                metadata={"error": auth_err},
            )
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=auth_err,
                skip_reason=SyncSkipReason.AUTHORITY_DENIED,
            )

        sync_id = await zoho_sync_store.create_run(
            integration=integration,
            operation=operation,
            direction=SyncDirection.OUTBOUND,
            payload_summary=self._payload_summary(payload),
            correlation_id=correlation_id,
        )
        payload["sync_id"] = sync_id

        if not zoho_credentials_configured() and integration not in ("sign",):
            await zoho_sync_store.complete_run(
                sync_id,
                status=SyncStatus.SKIPPED,
                message="no_credentials",
            )
            result = SyncResult(
                success=True,
                sync_id=sync_id,
                integration=integration,
                operation=operation,
                status=SyncStatus.SKIPPED,
                skip_reason=SyncSkipReason.NO_CREDENTIALS,
                message="no_credentials",
            )
            await self._audit(result, actor_id)
            return result

        await zoho_sync_store.mark_running(sync_id)
        try:
            result = await adapter.execute(operation, payload)
        except Exception as exc:
            logger.exception("Zoho sync failed: %s/%s", integration, operation)
            await zoho_sync_store.add_dead_letter(
                sync_id=sync_id,
                integration=integration,
                operation=operation,
                payload=payload,
                error=str(exc),
            )
            await log_zoho_sync_event(
                integration=integration,
                operation=operation,
                sync_id=sync_id,
                status="failed",
                actor_id=actor_id,
                metadata={"error": str(exc)},
            )
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=integration,
                operation=operation,
                status=SyncStatus.DEAD_LETTER,
                message=str(exc),
            )

        await zoho_sync_store.complete_run(
            sync_id,
            status=result.status,
            message=result.message,
            external_id=result.external_id,
            error=None if result.success else result.message,
        )
        await self._audit(result, actor_id)
        return result

    async def enqueue_sync(self, integration: str, operation: str, payload: Dict[str, Any]) -> str:
        if not zoho_integration_enabled() or zoho_kill_switch_active():
            return ""
        if not is_integration_enabled(integration):
            return ""
        return await zoho_sync_store.enqueue(integration, operation, payload)

    async def process_queue(self, integration: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        items = await zoho_sync_store.fetch_pending_queue(integration, limit)
        processed = 0
        failed = 0
        for item in items:
            result = await self.run_sync(
                item["integration"],
                item["operation"],
                item.get("payload") or {},
            )
            if result.success:
                await zoho_sync_store.mark_queue_done(item["queue_id"])
                processed += 1
            else:
                await zoho_sync_store.mark_queue_failed(item["queue_id"], result.message)
                failed += 1
        return {"processed": processed, "failed": failed, "total": len(items)}

    async def replay_dead_letter(self, dead_letter_id: str, *, actor_id: Optional[str] = None) -> SyncResult:
        dl = await zoho_sync_store.get_dead_letter(dead_letter_id)
        if not dl or dl.get("resolved"):
            return SyncResult(
                success=False,
                sync_id="",
                integration="",
                operation="replay",
                status=SyncStatus.FAILED,
                message="dead_letter_not_found",
            )
        return await self.run_sync(
            dl["integration"],
            dl["operation"],
            dl.get("payload") or {},
            actor_id=actor_id,
            correlation_id=dl.get("sync_id"),
        )

    def _skipped(self, integration: str, operation: str, reason: SyncSkipReason) -> SyncResult:
        return SyncResult(
            success=True,
            sync_id="",
            integration=integration,
            operation=operation,
            status=SyncStatus.SKIPPED,
            skip_reason=reason,
            message=reason.value,
        )

    def _payload_summary(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in payload.items() if k not in ("export_data", "raw_body")}

    async def _audit(self, result: SyncResult, actor_id: Optional[str]) -> None:
        await log_zoho_sync_event(
            integration=result.integration,
            operation=result.operation,
            sync_id=result.sync_id,
            status=result.status.value,
            actor_id=actor_id,
            metadata={"message": result.message, "external_id": result.external_id},
        )


zoho_integration_service = ZohoIntegrationService()
