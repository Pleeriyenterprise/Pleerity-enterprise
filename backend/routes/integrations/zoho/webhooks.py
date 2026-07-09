"""Inbound Zoho webhook routes — validated, governed, flag-gated."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request, status

from services.integrations.zoho.config import zoho_integration_enabled, zoho_webhook_secret
from services.integrations.zoho.webhooks.handlers import (
    handle_campaigns_unsubscribe,
    handle_sign_completion,
    reject_books_inbound,
    reject_crm_inbound,
)
from services.integrations.zoho.webhooks.verifier import (
    ZohoWebhookVerificationError,
    verify_zoho_webhook_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["zoho-webhooks"])


def _guard() -> None:
    if not zoho_integration_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.post("/api/internal/integrations/zoho/webhooks/sign")
async def zoho_sign_webhook(
    request: Request,
    x_zoho_signature: Optional[str] = Header(default=None, alias="X-Zoho-Signature"),
) -> Dict[str, Any]:
    _guard()
    raw = await request.body()
    try:
        verify_zoho_webhook_signature(raw, x_zoho_signature, zoho_webhook_secret("sign"))
    except ZohoWebhookVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    return await handle_sign_completion(payload)


@router.post("/api/internal/integrations/zoho/webhooks/campaigns")
async def zoho_campaigns_webhook(
    request: Request,
    x_zoho_signature: Optional[str] = Header(default=None, alias="X-Zoho-Signature"),
) -> Dict[str, Any]:
    _guard()
    raw = await request.body()
    try:
        verify_zoho_webhook_signature(raw, x_zoho_signature, zoho_webhook_secret("campaigns"))
    except ZohoWebhookVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    payload = json.loads(raw.decode("utf-8"))
    event = str(payload.get("event") or payload.get("type") or "").lower()
    if "unsubscribe" in event:
        return await handle_campaigns_unsubscribe(payload)
    return {"accepted": False, "reason": "unsupported_event"}


@router.post("/api/internal/integrations/zoho/webhooks/crm")
async def zoho_crm_webhook(
    request: Request,
    x_zoho_signature: Optional[str] = Header(default=None, alias="X-Zoho-Signature"),
) -> Dict[str, Any]:
    """All CRM inbound writes are rejected — Pleerity is SoR."""
    _guard()
    raw = await request.body()
    try:
        verify_zoho_webhook_signature(raw, x_zoho_signature, zoho_webhook_secret("crm"))
    except ZohoWebhookVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    payload = json.loads(raw.decode("utf-8"))
    return await reject_crm_inbound(payload if isinstance(payload, dict) else {})


@router.post("/api/internal/integrations/zoho/webhooks/books")
async def zoho_books_webhook(request: Request) -> Dict[str, Any]:
    """Books inbound writes forbidden — Stripe/Pleerity remain billing SoR."""
    _guard()
    return await reject_books_inbound()
