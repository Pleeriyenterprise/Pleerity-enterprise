"""
Account Lifecycle Response Authority (ILP-7).

Single generator for customer-facing lifecycle-aware API responses.
Routes and middleware must not assemble lifecycle payloads locally.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from services.account_capability_enforcement import (
    CapabilityDecision,
    CapabilityReasonCode,
)
from services.account_lifecycle_runtime_contract import (
    CONTRACT_VERSION,
    _customer_experience_for_mode,
    resolve_navigation_policy,
    resolve_reactivation_policy,
)

logger = logging.getLogger(__name__)

POLICY_VERSION = "account_lifecycle_response_v1"

# Governed redirect surfaces (route prefix → surface id)
_ROUTE_SURFACE: Dict[str, str] = {
    "/settings/billing": "billing",
    "/settings/profile": "profile",
    "/settings": "settings",
    "/support": "support",
    "/today": "today",
    "/dashboard": "dashboard",
    "/documents": "documents",
    "/properties": "portal",
    "/onboarding-status": "portal",
    "/reports": "portal",
}


class LifecycleResponseType(str, Enum):
    CAPABILITY_DENIED = "capability_denied"
    LIFECYCLE_DENIED = "lifecycle_denied"
    READ_ONLY = "read_only"
    BILLING_RECOVERY = "billing_recovery"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
    DELETED = "deleted"
    UNKNOWN_LIFECYCLE = "unknown_lifecycle"
    AUTHENTICATION_EXPIRED = "authentication_expired"
    SESSION_REFRESH_REQUIRED = "session_refresh_required"
    RETRY_LATER = "retry_later"
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"
    SUPPORT_REQUIRED = "support_required"
    BACKGROUND_PAUSED = "background_paused"


def _redirect_surface(route: Optional[str]) -> str:
    path = str(route or "").strip()
    if not path:
        return "portal"
    for prefix, surface in sorted(_ROUTE_SURFACE.items(), key=lambda x: -len(x[0])):
        if path.startswith(prefix):
            return surface
    return "portal"


def _recovery_action(portal_mode: Optional[str], lifecycle_state: Optional[str]) -> str:
    pm = str(portal_mode or "").upper()
    ls = str(lifecycle_state or "").upper()
    if pm in ("BILLING_RECOVERY", "PAYMENT_REQUIRED") or ls in (
        "CANCELLED_IMMEDIATE",
        "SUBSCRIPTION_EXPIRED",
        "GRACE_PERIOD",
        "PAYMENT_FAILED",
        "PAYMENT_PENDING",
        "TRIAL_EXPIRED",
    ):
        return "complete_payment"
    if ls == "SUSPENDED" or pm == "SUSPENDED":
        return "contact_support"
    if ls in ("ARCHIVED", "ACCOUNT_DELETED"):
        return "contact_support"
    if pm == "READ_ONLY" or ls == "READ_ONLY":
        return "reactivate_account"
    return "continue"


def _response_type_for_capability(decision: CapabilityDecision) -> LifecycleResponseType:
    code = str(decision.reason_code or "")
    pm = str(decision.portal_mode or "")
    ls = str(decision.lifecycle_state or "")
    if code == CapabilityReasonCode.READ_ONLY_BLOCKED.value:
        return LifecycleResponseType.READ_ONLY
    if ls == "READ_ONLY" or pm == "READ_ONLY":
        return LifecycleResponseType.READ_ONLY
    if code == CapabilityReasonCode.RUNTIME_UNAVAILABLE.value:
        return LifecycleResponseType.TEMPORARY_UNAVAILABLE
    if pm == "BILLING_RECOVERY" or ls in ("CANCELLED_IMMEDIATE", "SUBSCRIPTION_EXPIRED"):
        return LifecycleResponseType.BILLING_RECOVERY
    if pm == "SUSPENDED" or ls == "SUSPENDED":
        return LifecycleResponseType.SUSPENDED
    if ls == "ARCHIVED":
        return LifecycleResponseType.ARCHIVED
    if ls == "ACCOUNT_DELETED":
        return LifecycleResponseType.DELETED
    if ls == "UNKNOWN":
        return LifecycleResponseType.UNKNOWN_LIFECYCLE
    if code == CapabilityReasonCode.PLAN_DENIED.value:
        return LifecycleResponseType.CAPABILITY_DENIED
    return LifecycleResponseType.CAPABILITY_DENIED


def _response_type_for_lifecycle(lifecycle_state: str, portal_mode: str) -> LifecycleResponseType:
    ls = str(lifecycle_state or "UNKNOWN").upper()
    pm = str(portal_mode or "")
    if ls == "UNKNOWN":
        return LifecycleResponseType.UNKNOWN_LIFECYCLE
    if ls == "ACCOUNT_DELETED":
        return LifecycleResponseType.DELETED
    if ls == "ARCHIVED":
        return LifecycleResponseType.ARCHIVED
    if ls == "SUSPENDED" or pm == "SUSPENDED":
        return LifecycleResponseType.SUSPENDED
    if ls == "READ_ONLY" or pm == "READ_ONLY":
        return LifecycleResponseType.READ_ONLY
    if pm in ("BILLING_RECOVERY", "PAYMENT_REQUIRED") or ls in (
        "CANCELLED_IMMEDIATE",
        "SUBSCRIPTION_EXPIRED",
    ):
        return LifecycleResponseType.BILLING_RECOVERY
    return LifecycleResponseType.LIFECYCLE_DENIED


def _safe_customer_experience(
    portal_mode: Optional[str],
    lifecycle_state: Optional[str],
    contract: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if contract and contract.get("customer_experience"):
        cx = dict(contract.get("customer_experience") or {})
    else:
        cx = dict(
            _customer_experience_for_mode(
                str(portal_mode or "FULL_ACCESS"),
                str(lifecycle_state or "UNKNOWN"),
                {},
            )
        )
    primary = cx.get("primary_cta") or {}
    return {
        "heading": cx.get("heading") or "",
        "explanation": cx.get("explanation") or "",
        "current_state_label": cx.get("current_state_label") or lifecycle_state,
        "primary_cta": {
            "label": primary.get("label"),
            "route": primary.get("route"),
        },
    }


def _build_redirect(
    route: Optional[str],
    label: Optional[str],
    portal_mode: Optional[str],
) -> Dict[str, Any]:
    navigation = resolve_navigation_policy(str(portal_mode or "BILLING_RECOVERY"))
    effective_route = route or navigation.get("landing_route") or "/support"
    effective_label = label or "Continue"
    return {
        "route": effective_route,
        "label": effective_label,
        "surface": _redirect_surface(effective_route),
    }


def _build_recovery(
    route: Optional[str],
    label: Optional[str],
    portal_mode: Optional[str],
    lifecycle_state: Optional[str],
    contract: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    reactivation = (
        dict(contract.get("reactivation_policy") or {})
        if contract
        else resolve_reactivation_policy(str(lifecycle_state or "UNKNOWN"), str(portal_mode or ""))
    )
    return {
        "route": route,
        "label": label,
        "action": _recovery_action(portal_mode, lifecycle_state),
        "eligible": bool(reactivation.get("eligible")),
        "paths": list(reactivation.get("paths") or []),
        "restoration_scope": reactivation.get("restoration_scope"),
    }


def _support_reference(
    *,
    runtime_version: Optional[Any],
    capability_id: Optional[str],
    response_type: str,
) -> str:
    cap = (capability_id or "lifecycle").replace("CAP_", "")[:24]
    rv = runtime_version if runtime_version is not None else 0
    return f"ALR-{rv}-{response_type}-{cap}"[:64]


@dataclass(frozen=True)
class LifecycleResponsePayload:
    """Canonical lifecycle-aware HTTP response body (typically FastAPI `detail`)."""

    error: str
    error_code: str
    message: str
    lifecycle_state: Optional[str] = None
    portal_mode: Optional[str] = None
    response_type: str = LifecycleResponseType.CAPABILITY_DENIED.value
    customer_experience: Dict[str, Any] = field(default_factory=dict)
    recovery: Optional[Dict[str, Any]] = None
    lifecycle_redirect: Dict[str, Any] = field(default_factory=dict)
    runtime_version: Optional[Any] = None
    contract_version: Optional[str] = None
    policy_version: str = POLICY_VERSION
    capability: Optional[str] = None
    grant: Optional[str] = None
    reason: str = ""
    support_reference: Optional[str] = None
    safe_to_retry: bool = False
    action: Optional[str] = None
    effective_semantic: Optional[str] = None

    def to_http_detail(self) -> Dict[str, Any]:
        """Serialize for HTTP 403/401 JSON `detail` — includes ILP-4 compatibility fields."""
        out: Dict[str, Any] = {
            "error": self.error,
            "error_code": self.error_code,
            "reason_code": self.error_code,
            "message": self.message,
            "reason": self.reason or self.message,
            "lifecycle_state": self.lifecycle_state,
            "portal_mode": self.portal_mode,
            "response_type": self.response_type,
            "customer_experience": dict(self.customer_experience),
            "recovery": dict(self.recovery) if self.recovery else None,
            "lifecycle_redirect": dict(self.lifecycle_redirect),
            "runtime_version": self.runtime_version,
            "contract_version": self.contract_version or CONTRACT_VERSION,
            "policy_version": self.policy_version,
            "capability": self.capability,
            "capability_id": self.capability,
            "grant": self.grant,
            "support_reference": self.support_reference,
            "safe_to_retry": self.safe_to_retry,
        }
        if self.action is not None:
            out["action"] = self.action
        if self.effective_semantic is not None:
            out["effective_semantic"] = self.effective_semantic
        return out


class LifecycleResponseAuthority:
    """Generate governed lifecycle responses from Runtime Contract material."""

    @staticmethod
    def from_capability_decision(
        decision: CapabilityDecision,
        *,
        contract: Optional[Mapping[str, Any]] = None,
    ) -> LifecycleResponsePayload:
        response_type = _response_type_for_capability(decision)
        portal_mode = decision.portal_mode or (contract or {}).get("portal_mode")
        lifecycle_state = decision.lifecycle_state or (contract or {}).get("lifecycle_state")
        cx = _safe_customer_experience(portal_mode, lifecycle_state, contract)
        route = decision.recovery_route or (cx.get("primary_cta") or {}).get("route")
        label = decision.recovery_label or (cx.get("primary_cta") or {}).get("label")
        redirect = _build_redirect(route, label, portal_mode)
        recovery = _build_recovery(route, label, portal_mode, lifecycle_state, contract)
        safe_to_retry = decision.reason_code == CapabilityReasonCode.RUNTIME_UNAVAILABLE.value
        return LifecycleResponsePayload(
            error="capability_denied",
            error_code=decision.reason_code,
            message=decision.reason,
            lifecycle_state=lifecycle_state,
            portal_mode=portal_mode,
            response_type=response_type.value,
            customer_experience=cx,
            recovery=recovery,
            lifecycle_redirect=redirect,
            runtime_version=decision.runtime_version or (contract or {}).get("runtime_version"),
            contract_version=decision.contract_version or (contract or {}).get("contract_version"),
            capability=decision.capability_id,
            grant=decision.grant,
            reason=decision.reason,
            support_reference=_support_reference(
                runtime_version=decision.runtime_version,
                capability_id=decision.capability_id,
                response_type=response_type.value,
            ),
            safe_to_retry=safe_to_retry,
            action=decision.action,
            effective_semantic=decision.effective_semantic,
        )

    @staticmethod
    def from_contract_lifecycle_denial(
        contract: Mapping[str, Any],
        *,
        message: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> LifecycleResponsePayload:
        lifecycle_state = str(contract.get("lifecycle_state") or "UNKNOWN")
        portal_mode = str(contract.get("portal_mode") or "BILLING_RECOVERY")
        response_type = _response_type_for_lifecycle(lifecycle_state, portal_mode)
        cx = _safe_customer_experience(portal_mode, lifecycle_state, contract)
        primary = cx.get("primary_cta") or {}
        route = primary.get("route")
        label = primary.get("label")
        redirect = _build_redirect(route, label, portal_mode)
        recovery = _build_recovery(route, label, portal_mode, lifecycle_state, contract)
        msg = message or cx.get("explanation") or cx.get("heading") or "This action is not available for your account."
        return LifecycleResponsePayload(
            error=response_type.value,
            error_code=error_code or "lifecycle_access_denied",
            message=msg,
            lifecycle_state=lifecycle_state,
            portal_mode=portal_mode,
            response_type=response_type.value,
            customer_experience=cx,
            recovery=recovery,
            lifecycle_redirect=redirect,
            runtime_version=contract.get("runtime_version"),
            contract_version=contract.get("contract_version"),
            reason=msg,
            support_reference=_support_reference(
                runtime_version=contract.get("runtime_version"),
                capability_id=None,
                response_type=response_type.value,
            ),
            safe_to_retry=False,
        )

    @staticmethod
    def authentication_expired(*, message: Optional[str] = None) -> LifecycleResponsePayload:
        msg = message or "Your session has expired. Please sign in again."
        redirect = _build_redirect("/login", "Sign in", None)
        return LifecycleResponsePayload(
            error=LifecycleResponseType.AUTHENTICATION_EXPIRED.value,
            error_code="authentication_expired",
            message=msg,
            response_type=LifecycleResponseType.AUTHENTICATION_EXPIRED.value,
            lifecycle_redirect=redirect,
            recovery={"route": "/login", "label": "Sign in", "action": "sign_in", "eligible": True},
            reason=msg,
            safe_to_retry=False,
            support_reference=_support_reference(
                runtime_version=None,
                capability_id=None,
                response_type=LifecycleResponseType.AUTHENTICATION_EXPIRED.value,
            ),
        )

    @staticmethod
    def session_refresh_required(
        *,
        runtime_version: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> LifecycleResponsePayload:
        msg = message or "Your account status has changed. Refresh to continue."
        return LifecycleResponsePayload(
            error=LifecycleResponseType.SESSION_REFRESH_REQUIRED.value,
            error_code="session_refresh_required",
            message=msg,
            response_type=LifecycleResponseType.SESSION_REFRESH_REQUIRED.value,
            lifecycle_redirect=_build_redirect("/today", "Refresh", "FULL_ACCESS"),
            runtime_version=runtime_version,
            reason=msg,
            safe_to_retry=True,
            support_reference=_support_reference(
                runtime_version=runtime_version,
                capability_id=None,
                response_type=LifecycleResponseType.SESSION_REFRESH_REQUIRED.value,
            ),
        )


def capability_denied_http_detail(
    decision: CapabilityDecision,
    *,
    contract: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Compatibility wrapper — all capability denials use Lifecycle Response Authority."""
    payload = LifecycleResponseAuthority.from_capability_decision(decision, contract=contract)
    return payload.to_http_detail()


async def lifecycle_denial_for_client(
    db,
    client_id: str,
    *,
    message: Optional[str] = None,
    error_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Build governed lifecycle denial from live Runtime Contract."""
    from services.account_lifecycle_runtime_contract import resolve_runtime_contract_for_client

    contract = await resolve_runtime_contract_for_client(db, client_id)
    payload = LifecycleResponseAuthority.from_contract_lifecycle_denial(
        contract,
        message=message,
        error_code=error_code,
    )
    log_lifecycle_response_generated(
        client_id=client_id,
        response_type=payload.response_type,
        lifecycle_state=payload.lifecycle_state,
        runtime_version=payload.runtime_version,
    )
    return payload.to_http_detail()


def log_lifecycle_response_generated(
    *,
    client_id: Optional[str] = None,
    route: Optional[str] = None,
    response_type: Optional[str] = None,
    lifecycle_state: Optional[str] = None,
    capability: Optional[str] = None,
    grant: Optional[str] = None,
    runtime_version: Optional[Any] = None,
) -> None:
    logger.info(
        "lifecycle_response_generated client_id=%s route=%s response_type=%s lifecycle=%s "
        "capability=%s grant=%s runtime_version=%s policy=%s",
        client_id or "-",
        route or "-",
        response_type or "-",
        lifecycle_state or "-",
        capability or "-",
        grant or "-",
        runtime_version,
        POLICY_VERSION,
    )
