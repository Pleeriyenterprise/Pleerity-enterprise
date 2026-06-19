"""
Internal Twin discovery webhook routes — Stage Y (staging only).

POST /api/internal/discovery/twin/webhooks
GET  /api/internal/discovery/twin/health
POST /api/internal/discovery/twin/reconcile
GET  /api/internal/discovery/twin/captures/{capture_id}
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from services.discovery.twin.twin_event_capture_service import TwinEventCaptureService
from services.discovery.twin.twin_ingestion_connector import (
    TwinIngestionConnector,
    TwinIngestionConnectorError,
)
from services.discovery.twin.twin_webhook_verifier import TwinWebhookVerificationError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["discovery-twin-internal"])


def _optional_bearer_ok(authorization: Optional[str]) -> bool:
    token = (os.environ.get("DISCOVERY_TWIN_WEBHOOK_TOKEN") or "").strip()
    if not token:
        return True
    if not authorization or not authorization.startswith("Bearer "):
        return False
    return authorization.removeprefix("Bearer ").strip() == token


def _connector_guard() -> None:
    if not TwinIngestionConnector.connector_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


class TwinReconcileBody(BaseModel):
    agent_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    receipt_id: Optional[str] = None


@router.get("/api/internal/discovery/twin/health")
async def twin_connector_health() -> Dict[str, Any]:
    _connector_guard()
    if not _optional_bearer_ok(None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return await TwinIngestionConnector.health_status()


@router.post("/api/internal/discovery/twin/webhooks")
async def twin_discovery_webhook(
    request: Request,
    x_cobb_signature: Optional[str] = Header(default=None, alias="X-Cobb-Signature"),
    x_cobb_event: Optional[str] = Header(default=None, alias="X-Cobb-Event"),
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    _connector_guard()
    if not _optional_bearer_ok(authorization):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    raw_body = await request.body()
    if len(raw_body) > 65536:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook body must be an object")

    try:
        return await TwinIngestionConnector.process_webhook(
            raw_body=raw_body,
            signature_header=x_cobb_signature,
            header_event=x_cobb_event,
            webhook_payload=payload,
        )
    except TwinWebhookVerificationError as exc:
        logger.warning("Twin webhook verification failed: %s", exc.code)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.message) from exc
    except TwinIngestionConnectorError as exc:
        logger.error("Twin webhook connector error: %s — %s", exc.code, exc.message)
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc


@router.post("/api/internal/discovery/twin/reconcile")
async def twin_reconcile_run(
    body: TwinReconcileBody,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Manual backfill: fetch Twin run events and capture (same path as webhook)."""
    _connector_guard()
    if not _optional_bearer_ok(authorization):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    allowed_agent = (os.environ.get("TWIN_DISCOVERY_AGENT_ID") or "").strip()
    if allowed_agent and body.agent_id != allowed_agent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent not allowlisted")

    try:
        return await TwinIngestionConnector.pull_run_events(
            twin_agent_id=body.agent_id,
            twin_run_id=body.run_id,
            receipt_id=body.receipt_id,
        )
    except TwinIngestionConnectorError as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc


@router.get("/api/internal/discovery/twin/captures/{capture_id}")
async def twin_get_capture(
    capture_id: str,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Inspect captured Twin run events (ops / schema lock-in)."""
    _connector_guard()
    if not _optional_bearer_ok(authorization):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    capture = await TwinEventCaptureService.get_capture(capture_id)
    if not capture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capture not found")
    return capture
