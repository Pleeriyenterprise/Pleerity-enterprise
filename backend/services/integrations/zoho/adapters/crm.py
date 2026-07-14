"""Zoho CRM one-way outbound sync adapter — governed Pleerity → Zoho replica."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from database import database
from services.integrations.zoho.adapters.base import BaseZohoAdapter
from services.integrations.zoho.client import zoho_http_client
from services.integrations.zoho.config import crm_target_config_snapshot, zoho_crm_module
from services.integrations.zoho.registry import (
    map_lead_to_zoho_crm,
    validate_crm_outbound_payload,
    validate_inbound_crm_fields,
)
from services.integrations.zoho.sync_store import zoho_sync_store
from services.integrations.zoho.types import (
    CRM_EVENT_CONVERTED,
    CRM_EVENT_CREATED,
    CRM_EVENT_LOST,
    CRM_EVENT_STAGE_CHANGED,
    CRM_EVENT_UPDATED,
    CRM_OPERATION_UPSERT,
    SyncResult,
    SyncSkipReason,
    SyncStatus,
)
from services.integrations.zoho.version import DEFAULT_MAPPING_VERSION, DEFAULT_PAYLOAD_VERSION

SUPPORTED_CRM_OPERATIONS = frozenset(
    {
        CRM_EVENT_CREATED,
        CRM_EVENT_UPDATED,
        CRM_EVENT_STAGE_CHANGED,
        CRM_EVENT_CONVERTED,
        CRM_EVENT_LOST,
        CRM_OPERATION_UPSERT,
    }
)


def _extract_zoho_record_id(data: Optional[Dict[str, Any]]) -> Optional[str]:
    if not data or not isinstance(data, dict):
        return None
    rows = data.get("data")
    if isinstance(rows, list) and rows:
        first = rows[0] if isinstance(rows[0], dict) else {}
        details = first.get("details") if isinstance(first.get("details"), dict) else {}
        candidate = details.get("id") or first.get("id")
        if candidate:
            return str(candidate)
    # Search responses also use data[].id
    return None


def build_pleerity_lead_id_search_criteria(lead_id: str) -> str:
    """Exact Pleerity_Lead_ID criteria only — never email/name/heuristic."""
    # Escape parentheses / backslash per Zoho criteria conventions for literal values.
    safe = (
        str(lead_id)
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )
    return f"(Pleerity_Lead_ID:equals:{safe})"


async def lookup_zoho_id_by_pleerity_lead_id(lead_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve existing Zoho Lead by Pleerity_Lead_ID only.

    Returns (zoho_id | None, error | None). None+None means not found.
    """
    module = zoho_crm_module()
    criteria = build_pleerity_lead_id_search_criteria(lead_id)
    path = f"/crm/v6/{module}/search"
    ok, data, err = await zoho_http_client.request(
        "GET",
        path,
        integration="crm",
        params={"criteria": criteria},
    )
    if not ok:
        return None, err or "crm_identity_lookup_failed"
    rows = (data or {}).get("data") if isinstance(data, dict) else None
    if not rows:
        return None, None
    if not isinstance(rows, list):
        return None, "crm_identity_lookup_malformed"
    # Deterministic: if multiple matches exist, prefer first but surface as conflict metadata upstream.
    first = rows[0] if isinstance(rows[0], dict) else {}
    zoho_id = first.get("id")
    if not zoho_id:
        return None, "crm_identity_lookup_missing_id"
    return str(zoho_id), None


def _result_summary(
    *,
    lead_id: str,
    zoho_id: Optional[str],
    method: str,
    identity_source: str,
    **extra: Any,
) -> Dict[str, Any]:
    return {
        "lead_id": lead_id,
        "external_id": zoho_id,
        "http_method": method,
        "identity_source": identity_source,
        "module": zoho_crm_module(),
        "payload_version": DEFAULT_PAYLOAD_VERSION,
        "mapping_version": DEFAULT_MAPPING_VERSION,
        "identity_field": "Pleerity_Lead_ID",
        **extra,
    }


class ZohoCrmAdapter(BaseZohoAdapter):
    integration = "crm"

    async def execute(self, operation: str, payload: Dict[str, Any]) -> SyncResult:
        sync_id = payload.get("sync_id", "")

        if operation == "inbound_rejected":
            blocked = validate_inbound_crm_fields(payload.get("fields") or {})
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=f"inbound_authority_denied:{blocked}",
            )

        if operation not in SUPPORTED_CRM_OPERATIONS:
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=f"unknown_operation:{operation}",
            )

        config = crm_target_config_snapshot()
        if not config.get("target_complete"):
            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SKIPPED,
                skip_reason=SyncSkipReason.CONFIG_INVALID,
                message="crm_config_invalid:" + ";".join(config.get("missing") or []),
                metadata={"config": config},
            )

        lead_id = payload.get("lead_id")
        if not lead_id:
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message="missing_lead_id",
            )

        db = database.get_db()
        lead = await db.leads.find_one({"lead_id": lead_id}, {"_id": 0})
        if not lead:
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message="lead_not_found",
            )

        mapped = map_lead_to_zoho_crm(lead)
        payload_issues = validate_crm_outbound_payload(mapped, lead=lead)
        if payload_issues:
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SKIPPED,
                skip_reason=SyncSkipReason.PAYLOAD_INVALID,
                message="crm_payload_invalid:" + ";".join(payload_issues),
                metadata={"payload_issues": payload_issues},
            )

        module = zoho_crm_module()
        zoho_body = {"data": [mapped]}

        # Identity resolution order (authoritative):
        # 1) local external key → 2) Pleerity_Lead_ID lookup → 3) create → 4) persist key
        identity_source = "external_key"
        duplicate_create_prevented = False
        existing_zoho_id = await zoho_sync_store.get_external_key("crm", lead_id)

        if not existing_zoho_id:
            looked_up, lookup_err = await lookup_zoho_id_by_pleerity_lead_id(str(lead_id))
            if lookup_err:
                return SyncResult(
                    success=False,
                    sync_id=sync_id,
                    integration=self.integration,
                    operation=operation,
                    status=SyncStatus.FAILED,
                    message=lookup_err,
                    metadata={
                        "result_summary": _result_summary(
                            lead_id=str(lead_id),
                            zoho_id=None,
                            method="GET",
                            identity_source="pleerity_lead_id_lookup",
                            lookup_error=lookup_err,
                        )
                    },
                )
            if looked_up:
                existing_zoho_id = looked_up
                identity_source = "pleerity_lead_id_lookup"
                duplicate_create_prevented = True
                await zoho_sync_store.store_external_key("crm", str(lead_id), str(looked_up))

        if existing_zoho_id:
            path = f"/crm/v6/{module}/{existing_zoho_id}"
            method = "PUT"
            ok, data, err = await zoho_http_client.request(
                method, path, integration=self.integration, json_body=zoho_body
            )
            if not ok:
                return SyncResult(
                    success=False,
                    sync_id=sync_id,
                    integration=self.integration,
                    operation=operation,
                    status=SyncStatus.FAILED,
                    message=err or "crm_update_failed",
                    metadata={
                        "result_summary": _result_summary(
                            lead_id=str(lead_id),
                            zoho_id=str(existing_zoho_id),
                            method=method,
                            identity_source=identity_source,
                            duplicate_create_prevented=duplicate_create_prevented,
                        )
                    },
                )
            # Confirm key remains persisted (immutable after first bind).
            await zoho_sync_store.store_external_key("crm", str(lead_id), str(existing_zoho_id))
            summary = _result_summary(
                lead_id=str(lead_id),
                zoho_id=str(existing_zoho_id),
                method=method,
                identity_source=identity_source,
                duplicate_create_prevented=duplicate_create_prevented,
                operation=operation,
            )
            return SyncResult(
                success=True,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.SUCCESS,
                message="crm_outbound_update_ok",
                external_id=str(existing_zoho_id),
                metadata={"result_summary": summary},
            )

        # Create path — success requires extracted + persisted external ID.
        path = f"/crm/v6/{module}"
        method = "POST"
        ok, data, err = await zoho_http_client.request(
            method, path, integration=self.integration, json_body=zoho_body
        )
        if not ok:
            # Recoverable duplicate conflict: bind via Pleerity_Lead_ID lookup then update.
            err_l = (err or "").lower()
            if "duplicate" in err_l:
                looked_up, lookup_err = await lookup_zoho_id_by_pleerity_lead_id(str(lead_id))
                if looked_up and not lookup_err:
                    await zoho_sync_store.store_external_key("crm", str(lead_id), str(looked_up))
                    put_ok, _, put_err = await zoho_http_client.request(
                        "PUT",
                        f"/crm/v6/{module}/{looked_up}",
                        integration=self.integration,
                        json_body=zoho_body,
                    )
                    if put_ok:
                        summary = _result_summary(
                            lead_id=str(lead_id),
                            zoho_id=str(looked_up),
                            method="PUT",
                            identity_source="duplicate_conflict_lookup",
                            duplicate_create_prevented=True,
                            operation=operation,
                        )
                        return SyncResult(
                            success=True,
                            sync_id=sync_id,
                            integration=self.integration,
                            operation=operation,
                            status=SyncStatus.SUCCESS,
                            message="crm_outbound_bound_after_duplicate",
                            external_id=str(looked_up),
                            metadata={"result_summary": summary},
                        )
                    return SyncResult(
                        success=False,
                        sync_id=sync_id,
                        integration=self.integration,
                        operation=operation,
                        status=SyncStatus.FAILED,
                        message=put_err or "crm_duplicate_recovery_update_failed",
                    )
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message=err or "crm_create_failed",
                metadata={
                    "result_summary": _result_summary(
                        lead_id=str(lead_id),
                        zoho_id=None,
                        method=method,
                        identity_source="create",
                    )
                },
            )

        zoho_id = _extract_zoho_record_id(data)
        if not zoho_id:
            return SyncResult(
                success=False,
                sync_id=sync_id,
                integration=self.integration,
                operation=operation,
                status=SyncStatus.FAILED,
                message="crm_create_external_id_not_extracted",
                metadata={
                    "result_summary": _result_summary(
                        lead_id=str(lead_id),
                        zoho_id=None,
                        method=method,
                        identity_source="create",
                        response_keys=list((data or {}).keys()) if isinstance(data, dict) else [],
                    ),
                    "recoverable": True,
                },
            )

        await zoho_sync_store.store_external_key("crm", str(lead_id), str(zoho_id))
        summary = _result_summary(
            lead_id=str(lead_id),
            zoho_id=str(zoho_id),
            method=method,
            identity_source="create",
            operation=operation,
            external_key_persisted=True,
        )
        return SyncResult(
            success=True,
            sync_id=sync_id,
            integration=self.integration,
            operation=operation,
            status=SyncStatus.SUCCESS,
            message="crm_outbound_create_ok",
            external_id=str(zoho_id),
            metadata={"result_summary": summary},
        )
