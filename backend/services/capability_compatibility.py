"""
Legacy feature_key → CAP_* compatibility mapping (ILP-4 Phase 0–1).

Wrappers delegate to CapabilityEnforcementService without changing legacy call sites yet.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from services.account_capability_enforcement import (
    CapabilityAction,
    CapabilityDecision,
    CapabilityEnforcementService,
)

# Governed mapping from ACCOUNT_FEATURE_CAPABILITY_MATRIX.md (+ ops flags).
FEATURE_KEY_TO_CAPABILITIES: Dict[str, Tuple[str, ...]] = {
    "compliance_dashboard": ("CAP_DASHBOARD_VIEW",),
    "compliance_score": ("CAP_SCORE_VIEW", "CAP_SCORE_EXPLAIN"),
    "compliance_calendar": ("CAP_CALENDAR_VIEW",),
    "expiry_calendar": ("CAP_CALENDAR_VIEW",),
    "email_notifications": ("CAP_NOTIF_EMAIL",),
    "document_upload_single": ("CAP_DOC_UPLOAD",),
    "multi_file_upload": ("CAP_DOC_MULTI_UPLOAD",),
    "score_trending": ("CAP_SCORE_TREND",),
    "ai_extraction_basic": ("CAP_AI_EXTRACTION_BASIC",),
    "ai_extraction_advanced": ("CAP_AI_EXTRACTION_ADVANCED",),
    "extraction_review_ui": ("CAP_AI_REVIEW",),
    "ai_review_interface": ("CAP_AI_REVIEW",),
    "document_upload_bulk_zip": ("CAP_DOC_BULK_ZIP",),
    "zip_upload": ("CAP_DOC_BULK_ZIP",),
    "reports_pdf": ("CAP_REPORT_GENERATE_PDF", "CAP_REPORT_DOWNLOAD"),
    "reports_csv": ("CAP_REPORT_GENERATE_CSV", "CAP_EXPORT_CSV"),
    "scheduled_reports": ("CAP_REPORT_SCHEDULE",),
    "sms_reminders": ("CAP_NOTIF_SMS",),
    "sms_notifications": ("CAP_NOTIF_SMS",),
    "tenant_portal": ("CAP_TENANT_PORTAL", "CAP_TENANT_MANAGE"),
    "tenant_portal_access": ("CAP_TENANT_PORTAL",),
    "webhooks": ("CAP_INTEGRATION_WEBHOOKS", "CAP_INTEGRATION_READ_API"),
    "white_label_reports": ("CAP_BRANDING_WHITE_LABEL", "CAP_BRANDING_EDIT"),
    "audit_log_export": ("CAP_AUDIT_LOG_EXPORT", "CAP_REPORT_AUDIT_PACK"),
    "maintenance_workflows": ("CAP_OPS_ISSUES_VIEW", "CAP_OPS_MAINTENANCE"),
    "predictive_maintenance": ("CAP_OPS_PREDICTIVE", "CAP_RISK_VIEW"),
    "contractor_network": ("CAP_OPS_CONTRACTORS",),
    "compliance_engine": ("CAP_OPS_APPROVALS", "CAP_OPS_COMPLIANCE_REVIEW", "CAP_REQ_RESOLVE"),
    "ai_assistant": ("CAP_AI_ASSISTANT",),
    "invoicing": ("CAP_OPS_APPROVALS",),
    "rent_operations": ("CAP_OPS_RENT",),
}

CAPABILITY_TO_FEATURE_KEYS: Dict[str, Tuple[str, ...]] = {}
_rev: Dict[str, List[str]] = {}
for _feature, _caps in FEATURE_KEY_TO_CAPABILITIES.items():
    for _cap in _caps:
        _rev.setdefault(_cap, []).append(_feature)
CAPABILITY_TO_FEATURE_KEYS = {k: tuple(sorted(set(v))) for k, v in _rev.items()}


def feature_key_to_capabilities(feature_key: str) -> Tuple[str, ...]:
    return FEATURE_KEY_TO_CAPABILITIES.get(feature_key, ())


def primary_capability_for_feature(feature_key: str) -> Optional[str]:
    caps = feature_key_to_capabilities(feature_key)
    return caps[0] if caps else None


def capability_to_feature_keys(capability_id: str) -> Tuple[str, ...]:
    return CAPABILITY_TO_FEATURE_KEYS.get(capability_id, ())


async def evaluate_feature_via_capability(
    service: CapabilityEnforcementService,
    client_id: str,
    feature_key: str,
    action: CapabilityAction = "write",
    *,
    contract=None,
) -> CapabilityDecision:
    """
    Compatibility evaluation for legacy feature_key callers.
    Uses the most restrictive mapped capability (all must allow for composite features).
    """
    caps = feature_key_to_capabilities(feature_key)
    if not caps:
        return CapabilityDecision(
            capability_id=f"feature:{feature_key}",
            action=action,
            grant="DENY",
            effective_semantic="DENY",
            allowed=False,
            source="compatibility_unmapped",
            reason_code="unmapped_feature_key",
            reason=f"No CAP_* mapping for feature_key '{feature_key}'.",
        )

    decisions: List[CapabilityDecision] = []
    for cap_id in caps:
        decisions.append(await service.evaluate(client_id, cap_id, action, contract=contract))

    blocked = [d for d in decisions if not d.allowed]
    if not blocked:
        return decisions[0]

    # Return the first blocking decision for governed messaging.
    return blocked[0]


def list_unmapped_plan_features(plan_feature_keys: Sequence[str]) -> List[str]:
    return sorted(k for k in plan_feature_keys if k not in FEATURE_KEY_TO_CAPABILITIES)


def contract_feature_enabled(
    contract: Mapping[str, Any] | None,
    feature_key: str,
    action: CapabilityAction = "read",
) -> bool:
    """True when every mapped CAP_* for feature_key allows action on the attached contract."""
    if not contract:
        return False
    caps = feature_key_to_capabilities(feature_key)
    if not caps:
        return False
    service = CapabilityEnforcementService(None)
    return all(
        service.evaluate_from_contract(contract, cap_id, action).allowed for cap_id in caps
    )


async def feature_enabled_for_client(
    db,
    client_id: str,
    feature_key: str,
    action: CapabilityAction = "read",
) -> bool:
    """Load Runtime Contract once and evaluate feature_key (background jobs / services without request scope)."""
    from services.account_lifecycle_runtime_contract import resolve_runtime_contract_for_client

    contract = await resolve_runtime_contract_for_client(db, client_id, emit_events=False)
    return contract_feature_enabled(contract, feature_key, action)


def contract_features_from_runtime(
    contract: Mapping[str, Any] | None,
    feature_keys: Sequence[str],
    action: CapabilityAction = "read",
) -> Dict[str, bool]:
    return {key: contract_feature_enabled(contract, key, action) for key in feature_keys}
