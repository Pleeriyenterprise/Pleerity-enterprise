"""In-app notifications for work-order quote/visit workflow (landlord portal)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from database import database

logger = logging.getLogger(__name__)


async def _client_portal_recipient_ids(client_id: str) -> list[str]:
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "portal_user_id": 1, "contact_email": 1, "email": 1})
    if not client:
        return []
    ids: list[str] = []
    pu = (client.get("portal_user_id") or "").strip()
    if pu:
        ids.append(pu)
    em = (client.get("contact_email") or client.get("email") or "").strip()
    if em and em not in ids:
        ids.append(em)
    return ids


async def notify_client_work_order_event(
    *,
    client_id: str,
    work_order_id: str,
    title: str,
    message: str,
    notification_type: str,
    cta_label: str = "Open job",
    cta_path: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Create in-app notification(s) for landlord portal users."""
    if not client_id or not work_order_id:
        return
    path = cta_path or f"/operations/jobs/{work_order_id}"
    try:
        from services.order_service import create_in_app_notification
    except Exception as exc:
        logger.warning("In-app notify import failed: %s", exc)
        return
    meta = {"work_order_id": work_order_id, **(metadata or {})}
    for rid in await _client_portal_recipient_ids(client_id):
        try:
            await create_in_app_notification(
                recipient_id=rid,
                title=title,
                message=message,
                notification_type=notification_type,
                link=path,
                metadata=meta,
                severity="medium",
                notification_category="operations",
                related_entity_type="work_order",
                related_entity_id=work_order_id,
                primary_cta_label=cta_label,
                primary_cta_path=path,
            )
        except Exception as exc:
            logger.warning("In-app WO notify failed for %s: %s", rid, exc)
