"""Non-blocking hooks from platform services into Zoho sync queue."""
from __future__ import annotations

import logging

from services.integrations.zoho.config import zoho_crm_sync_enabled
from services.integrations.zoho.service import zoho_integration_service

logger = logging.getLogger(__name__)


async def maybe_enqueue_crm_sync(lead_id: str, event: str) -> None:
    """Enqueue CRM one-way sync — never blocks lead operations."""
    if not zoho_crm_sync_enabled():
        return
    try:
        await zoho_integration_service.enqueue_sync(
            "crm",
            event,
            {"lead_id": lead_id},
        )
    except Exception as exc:
        logger.warning("Zoho CRM enqueue failed for %s: %s", lead_id, exc)
