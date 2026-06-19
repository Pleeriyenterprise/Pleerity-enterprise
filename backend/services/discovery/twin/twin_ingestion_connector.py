"""
Twin webhook/API ingestion connector — Stage Y (staging only).

Terminates at TwinProvider.ingest_async() when auto-ingest is enabled.
No LeadService, DiscoveryImportService, or CRM writes.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from services.discovery import discovery_config
from services.discovery.discovery_campaign_service import DiscoveryCampaignService
from services.discovery.discovery_models import (
    DiscoveryLawfulBasis,
    DiscoveryProviderId,
    DiscoveryRunStatus,
)
from services.discovery.discovery_run_service import CreateRunRequest, DiscoveryRunService
from services.discovery.providers.discovery_provider_protocol import IngestContext, IngestSource
from services.discovery.providers.twin_provider import TwinProvider
from services.discovery.twin.twin_api_client import TwinApiClient, TwinApiError
from services.discovery.twin.twin_connector_constants import TWIN_WEBHOOK_EVENTS_INGEST
from services.discovery.twin.twin_event_capture_service import TwinEventCaptureService
from services.discovery.twin.twin_run_event_extractor import extract_export_from_events
from services.discovery.twin.twin_webhook_receipt_service import TwinWebhookReceiptService
from services.discovery.twin.twin_webhook_verifier import (
    TwinWebhookVerificationError,
    validate_webhook_envelope,
    verify_timestamp_skew,
    verify_webhook_signature,
)

logger = logging.getLogger(__name__)


class TwinIngestionConnectorError(Exception):
    def __init__(self, code: str, message: str, *, http_status: int = 400):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


class TwinIngestionConnector:
    @staticmethod
    def connector_enabled() -> bool:
        return discovery_config.is_discovery_twin_webhook_ingest_enabled()

    @staticmethod
    def capture_only_mode() -> bool:
        return discovery_config.is_discovery_twin_event_capture_only()

    @staticmethod
    def auto_ingest_allowed() -> bool:
        return (
            not TwinIngestionConnector.capture_only_mode()
            and discovery_config.is_discovery_provider_twin_enabled()
            and discovery_config.is_discovery_module_enabled()
            and discovery_config.is_discovery_provider_layer_enabled()
        )

    @staticmethod
    async def process_webhook(
        *,
        raw_body: bytes,
        signature_header: Optional[str],
        header_event: Optional[str],
        webhook_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not TwinIngestionConnector.connector_enabled():
            raise TwinIngestionConnectorError(
                "CONNECTOR_DISABLED",
                "Twin webhook connector is disabled",
                http_status=404,
            )

        signing_secret = (os.environ.get("TWIN_WEBHOOK_SIGNING_SECRET") or "").strip()
        verify_webhook_signature(
            signing_secret=signing_secret,
            raw_body=raw_body,
            signature_header=signature_header,
        )

        allowed_agent = (os.environ.get("TWIN_DISCOVERY_AGENT_ID") or "").strip()
        envelope = validate_webhook_envelope(
            webhook_payload,
            allowed_agent_id=allowed_agent,
            header_event=header_event,
        )

        from services.discovery.twin.twin_connector_constants import twin_webhook_max_skew_seconds

        if envelope.get("timestamp"):
            verify_timestamp_skew(
                envelope["timestamp"],
                max_skew_seconds=twin_webhook_max_skew_seconds(),
            )

        receipt = await TwinWebhookReceiptService.create_receipt(
            twin_agent_id=envelope["agent_id"],
            twin_run_id=envelope["run_id"],
            event=envelope["event"],
            webhook_timestamp=envelope.get("timestamp") or "",
            webhook_payload=webhook_payload,
        )
        if receipt.get("status") not in ("received",):
            return {
                "status": "idempotent",
                "receipt_id": receipt["receipt_id"],
                "message": "Webhook already processed",
            }

        if envelope["event"] not in TWIN_WEBHOOK_EVENTS_INGEST:
            await TwinWebhookReceiptService.update_receipt(
                receipt["receipt_id"],
                status="skipped",
                error_code="EVENT_NOT_HANDLED",
                error_message=f"Event {envelope['event']} is logged only",
            )
            return {
                "status": "skipped",
                "receipt_id": receipt["receipt_id"],
                "event": envelope["event"],
            }

        if envelope["event"] == "run.failed":
            await TwinWebhookReceiptService.update_receipt(
                receipt["receipt_id"],
                status="skipped",
                error_code="RUN_FAILED",
                error_message="Twin run.failed — no ingest",
            )
            return {
                "status": "skipped",
                "receipt_id": receipt["receipt_id"],
                "reason": "run.failed",
            }

        outcome = envelope.get("outcome")
        if envelope["event"] == "run.completed" and outcome == "fail":
            await TwinWebhookReceiptService.update_receipt(
                receipt["receipt_id"],
                status="skipped",
                error_code="RUN_OUTCOME_FAIL",
                error_message="Twin run.completed with outcome=fail",
            )
            return {
                "status": "skipped",
                "receipt_id": receipt["receipt_id"],
                "reason": "outcome_fail",
            }

        return await TwinIngestionConnector._fetch_capture_and_maybe_ingest(
            receipt=receipt,
            envelope=envelope,
        )

    @staticmethod
    async def pull_run_events(
        *,
        twin_agent_id: str,
        twin_run_id: str,
        receipt_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not TwinIngestionConnector.connector_enabled():
            raise TwinIngestionConnectorError(
                "CONNECTOR_DISABLED",
                "Twin webhook connector is disabled",
                http_status=404,
            )

        envelope = {
            "agent_id": twin_agent_id,
            "run_id": twin_run_id,
            "event": "manual.pull",
        }
        receipt = None
        if receipt_id:
            from database import database
            from services.discovery.twin.twin_connector_constants import (
                DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION,
            )

            receipt = await database.get_db()[DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION].find_one(
                {"receipt_id": receipt_id},
                {"_id": 0},
            )
        if receipt is None:
            receipt = await TwinWebhookReceiptService.create_receipt(
                twin_agent_id=twin_agent_id,
                twin_run_id=twin_run_id,
                event="manual.pull",
                webhook_timestamp="",
                webhook_payload={"source": "manual_reconcile"},
            )

        return await TwinIngestionConnector._fetch_capture_and_maybe_ingest(
            receipt=receipt,
            envelope=envelope,
        )

    @staticmethod
    async def _fetch_capture_and_maybe_ingest(
        *,
        receipt: Dict[str, Any],
        envelope: Dict[str, Any],
    ) -> Dict[str, Any]:
        agent_id = envelope["agent_id"]
        run_id = envelope["run_id"]
        receipt_id = receipt["receipt_id"]

        api_key = (os.environ.get("TWIN_API_KEY") or "").strip()
        if not api_key:
            await TwinWebhookReceiptService.update_receipt(
                receipt_id,
                status="failed",
                error_code="MISSING_TWIN_API_KEY",
                error_message="TWIN_API_KEY not configured",
            )
            raise TwinIngestionConnectorError(
                "MISSING_TWIN_API_KEY",
                "TWIN_API_KEY is required to fetch run events",
                http_status=500,
            )

        client = TwinApiClient(api_key=api_key)
        try:
            twin_run = await client.get_run(agent_id, run_id)
            events = await client.list_run_events(agent_id, run_id)
        except TwinApiError as exc:
            await TwinWebhookReceiptService.update_receipt(
                receipt_id,
                status="failed",
                error_code=exc.code,
                error_message=exc.message,
            )
            raise TwinIngestionConnectorError(
                exc.code,
                exc.message,
                http_status=503 if exc.status in (429, 500, 502, 503, 504) else 502,
            ) from exc

        export_payload, diagnostics = extract_export_from_events(
            events,
            twin_run_id=run_id,
            twin_agent_id=agent_id,
        )
        capture = await TwinEventCaptureService.capture_run_events(
            receipt_id=receipt_id,
            twin_agent_id=agent_id,
            twin_run_id=run_id,
            events=events,
            twin_run_status=twin_run,
            extraction_diagnostics=diagnostics,
        )

        result: Dict[str, Any] = {
            "status": "captured",
            "receipt_id": receipt_id,
            "capture_id": capture["capture_id"],
            "event_count": capture["event_count"],
            "extraction_status": diagnostics.get("extraction_status"),
            "capture_only": TwinIngestionConnector.capture_only_mode(),
            "top_level_event_keys": diagnostics.get("top_level_event_keys"),
        }

        if TwinIngestionConnector.capture_only_mode():
            await TwinWebhookReceiptService.update_receipt(
                receipt_id,
                status="captured",
                capture_id=capture["capture_id"],
                ingest_summary={
                    "mode": "capture_only",
                    "extraction_status": diagnostics.get("extraction_status"),
                },
            )
            result["message"] = (
                "Run events captured for inspection. Ingest deferred until extraction is enabled."
            )
            return result

        if not export_payload:
            await TwinWebhookReceiptService.update_receipt(
                receipt_id,
                status="captured",
                capture_id=capture["capture_id"],
                error_code="EXPORT_NOT_EXTRACTED",
                error_message=diagnostics.get("extraction_note")
                or "Export extraction did not produce records[]",
                ingest_summary={"extraction_status": diagnostics.get("extraction_status")},
            )
            result["status"] = "captured_no_export"
            result["message"] = "Events captured; export extraction not available"
            return result

        if not TwinIngestionConnector.auto_ingest_allowed():
            await TwinWebhookReceiptService.update_receipt(
                receipt_id,
                status="captured",
                capture_id=capture["capture_id"],
                error_code="AUTO_INGEST_DISABLED",
                error_message="Provider flags or capture-only mode block ingest",
            )
            result["status"] = "captured_export_ready"
            result["message"] = "Export extracted but auto-ingest is disabled"
            return result

        ingest_out = await TwinIngestionConnector._ingest_export(
            export_payload=export_payload,
            twin_agent_id=agent_id,
            twin_run_id=run_id,
        )
        await TwinWebhookReceiptService.update_receipt(
            receipt_id,
            status="ingested",
            capture_id=capture["capture_id"],
            discovery_run_id=ingest_out["discovery_run_id"],
            ingest_summary=ingest_out,
        )
        result.update(
            {
                "status": "ingested",
                "discovery_run_id": ingest_out["discovery_run_id"],
                "accepted_count": ingest_out.get("accepted_count"),
                "rejected_count": ingest_out.get("rejected_count"),
                "duplicate_rows": ingest_out.get("duplicate_rows"),
            }
        )
        return result

    @staticmethod
    async def _ingest_export(
        *,
        export_payload: Dict[str, Any],
        twin_agent_id: str,
        twin_run_id: str,
    ) -> Dict[str, Any]:
        from services.discovery.twin.twin_connector_constants import (
            twin_discovery_campaign_id,
            twin_ingest_actor_email,
            twin_ingest_actor_id,
        )

        campaign_id = twin_discovery_campaign_id()
        if not campaign_id:
            raise TwinIngestionConnectorError(
                "MISSING_CAMPAIGN_ID",
                "TWIN_DISCOVERY_CAMPAIGN_ID is required for ingest",
                http_status=500,
            )

        campaign = await DiscoveryCampaignService.get_campaign(campaign_id)
        if not campaign:
            raise TwinIngestionConnectorError(
                "CAMPAIGN_NOT_FOUND",
                f"Campaign {campaign_id} not found",
                http_status=500,
            )

        lawful_basis_raw = campaign.get("lawful_basis") or DiscoveryLawfulBasis.CONSENT.value
        lawful_basis = DiscoveryLawfulBasis(lawful_basis_raw)

        discovery_run = await DiscoveryRunService.create_run(
            CreateRunRequest(
                provider=DiscoveryProviderId.TWIN,
                uploaded_by=twin_ingest_actor_id(),
                uploaded_by_email=twin_ingest_actor_email(),
                campaign_id=campaign_id,
                file_name=f"twin:{twin_agent_id}:{twin_run_id}",
            )
        )

        ctx = IngestContext(
            discovery_run_id=discovery_run["discovery_run_id"],
            discovery_campaign_id=campaign_id,
            actor_id=twin_ingest_actor_id(),
            actor_email=twin_ingest_actor_email(),
            lawful_basis=lawful_basis,
        )
        provider = TwinProvider()
        ingest_result = await provider.ingest_async(
            IngestSource(
                payload=export_payload,
                file_name=f"twin_export_{twin_run_id}.json",
            ),
            ctx,
        )

        if ingest_result.accepted_count > 0 and ingest_result.rejected_count == 0:
            run_status = DiscoveryRunStatus.COMPLETED
        elif ingest_result.accepted_count > 0:
            run_status = DiscoveryRunStatus.PARTIAL
        else:
            run_status = DiscoveryRunStatus.FAILED

        await DiscoveryRunService.update_run_status(
            discovery_run["discovery_run_id"],
            run_status,
        )

        return {
            "discovery_run_id": discovery_run["discovery_run_id"],
            "discovery_job_id": ingest_result.discovery_job_id,
            "accepted_count": ingest_result.accepted_count,
            "rejected_count": ingest_result.rejected_count,
            "duplicate_rows": ingest_result.duplicate_rows,
            "run_status": run_status.value,
        }

    @staticmethod
    async def health_status() -> Dict[str, Any]:
        return {
            "connector_enabled": TwinIngestionConnector.connector_enabled(),
            "capture_only_mode": TwinIngestionConnector.capture_only_mode(),
            "auto_ingest_allowed": TwinIngestionConnector.auto_ingest_allowed(),
            "provider_twin_enabled": discovery_config.is_discovery_provider_twin_enabled(),
            "discovery_module_enabled": discovery_config.is_discovery_module_enabled(),
            "twin_api_key_configured": bool((os.environ.get("TWIN_API_KEY") or "").strip()),
            "twin_webhook_secret_configured": bool(
                (os.environ.get("TWIN_WEBHOOK_SIGNING_SECRET") or "").strip()
            ),
            "twin_agent_id": (os.environ.get("TWIN_DISCOVERY_AGENT_ID") or "").strip() or None,
            "twin_campaign_id": (os.environ.get("TWIN_DISCOVERY_CAMPAIGN_ID") or "").strip() or None,
            "export_extraction_enabled": os.environ.get(
                "DISCOVERY_TWIN_EXPORT_EXTRACTION_ENABLED", "false"
            ).lower()
            in ("1", "true", "yes"),
        }
