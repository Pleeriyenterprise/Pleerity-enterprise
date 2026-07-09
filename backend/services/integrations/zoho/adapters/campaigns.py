"""Zoho Campaigns audience and suppression export."""
from __future__ import annotations

from typing import Any, Dict, List

from database import database
from services.integrations.zoho.adapters.base import BaseZohoAdapter
from services.integrations.zoho.client import zoho_http_client
from services.integrations.zoho.types import SyncResult, SyncStatus


class ZohoCampaignsAdapter(BaseZohoAdapter):
    integration = "campaigns"

    async def execute(self, operation: str, payload: Dict[str, Any]) -> SyncResult:
        sync_id = payload.get("sync_id", "")

        if operation == "export_audience":
            contacts = await self._build_audience()
            ok, data, err = await zoho_http_client.request(
                "POST",
                "/campaigns/v1.1/addlistsubscribersinbulk",
                integration=self.integration,
                json_body={"contacts": contacts},
            )
            if ok:
                return SyncResult(
                    success=True,
                    sync_id=sync_id,
                    integration=self.integration,
                    operation=operation,
                    status=SyncStatus.SUCCESS,
                    message="audience_exported",
                    metadata={"count": len(contacts)},
                )
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=err or "campaigns_export_failed",
            )

        if operation == "export_suppression":
            suppressed = await self._build_suppression_list()
            ok, _, err = await zoho_http_client.request(
                "POST",
                "/campaigns/v1.1/suppresssubscribers",
                integration=self.integration,
                json_body={"emails": suppressed},
            )
            if ok:
                return SyncResult(
                    success=True,
                    sync_id=sync_id,
                    integration=self.integration,
                    operation=operation,
                    status=SyncStatus.SUCCESS,
                    message="suppression_exported",
                    metadata={"count": len(suppressed)},
                )
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=err or "suppression_export_failed",
            )

        return SyncResult(
            success=False,
            sync_id=sync_id,
            integration=self.integration,
            operation=operation,
            status=SyncStatus.FAILED,
            message=f"unknown_operation:{operation}",
        )

    async def _build_audience(self) -> List[Dict[str, str]]:
        db = database.get_db()
        subs = await db.newsletter_subscribers.find(
            {"marketing_consent": {"$ne": False}}, {"_id": 0, "email": 1}
        ).to_list(10000)
        return [{"email": s["email"]} for s in subs if s.get("email")]

    async def _build_suppression_list(self) -> List[str]:
        db = database.get_db()
        emails: List[str] = []
        opt_out = await db.newsletter_subscribers.find(
            {"$or": [{"marketing_consent": False}, {"unsubscribed": True}]}, {"_id": 0, "email": 1}
        ).to_list(10000)
        emails.extend(s["email"] for s in opt_out if s.get("email"))
        leads = await db.leads.find(
            {"followup_status": "opted_out"}, {"_id": 0, "email": 1}
        ).to_list(10000)
        emails.extend(l["email"] for l in leads if l.get("email"))
        return list({e.lower() for e in emails})
