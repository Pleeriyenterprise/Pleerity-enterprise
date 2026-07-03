"""
Account Capability Enforcement (ILP-4 Phase 0–1).

Evaluates CAP_* grants from the Runtime Contract only.
Does not mutate data, replace middleware guards, or infer from legacy entitlement fields.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Mapping, Optional

from services.account_lifecycle_runtime_contract import (
    CONTRACT_VERSION,
    GRANT_ALLOW,
    GRANT_DENY,
    GRANT_HIDDEN,
    GRANT_LIMITED,
    GRANT_PLAN_GATED,
    GRANT_READ,
    _BASE_CAPABILITY_MATRIX,
    resolve_runtime_contract_for_client,
)

logger = logging.getLogger(__name__)

CapabilityAction = Literal["read", "write"]

# Enforcement semantics: contract READ maps to READ_ONLY (view permitted, mutation blocked).
SEMANTIC_READ_ONLY = "READ_ONLY"


class CapabilityReasonCode(str, Enum):
    ALLOWED = "allowed"
    READ_ONLY_BLOCKED = "read_only_blocked"
    DENIED = "denied"
    HIDDEN = "hidden"
    LIMITED_GRACE = "limited_grace"
    PLAN_DENIED = "plan_denied"
    UNKNOWN_CAPABILITY = "unknown_capability"
    RUNTIME_UNAVAILABLE = "runtime_unavailable"


@dataclass(frozen=True)
class CapabilityDecision:
    """Result of a single capability evaluation (no side effects)."""

    capability_id: str
    action: str
    grant: str
    effective_semantic: str
    allowed: bool
    source: str
    reason_code: str
    reason: str
    recovery_route: Optional[str] = None
    recovery_label: Optional[str] = None
    lifecycle_state: Optional[str] = None
    portal_mode: Optional[str] = None
    runtime_version: Optional[int] = None
    contract_version: Optional[str] = None
    warnings: tuple = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "action": self.action,
            "grant": self.grant,
            "effective_semantic": self.effective_semantic,
            "allowed": self.allowed,
            "source": self.source,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "recovery_route": self.recovery_route,
            "recovery_label": self.recovery_label,
            "lifecycle_state": self.lifecycle_state,
            "portal_mode": self.portal_mode,
            "runtime_version": self.runtime_version,
            "contract_version": self.contract_version,
            "warnings": list(self.warnings),
        }


class CapabilityDeniedError(Exception):
    """Raised when require_capability() blocks an action. Not wired to live routes in ILP-4 Phase 0–1."""

    def __init__(self, decision: CapabilityDecision):
        self.decision = decision
        super().__init__(decision.reason)

    def to_detail(self) -> dict[str, Any]:
        return {
            "error": "capability_denied",
            **self.decision.to_dict(),
        }


def normalize_grant_semantic(grant: str) -> str:
    if grant == GRANT_READ:
        return SEMANTIC_READ_ONLY
    return grant


def is_grant_action_allowed(grant: str, action: CapabilityAction) -> bool:
    """Map runtime grant to read/write permission without legacy inference."""
    if grant == GRANT_HIDDEN:
        return False
    if grant == GRANT_DENY:
        return False
    if grant == GRANT_PLAN_GATED:
        # Contract should pre-resolve PLAN_GATED; unresolved is deny-safe.
        return False
    if action == "read":
        return grant in (GRANT_ALLOW, GRANT_READ, GRANT_LIMITED)
    if action == "write":
        return grant in (GRANT_ALLOW, GRANT_LIMITED)
    return False


def _recovery_from_experience(customer_experience: Optional[Mapping[str, Any]]) -> tuple[Optional[str], Optional[str]]:
    if not customer_experience:
        return None, None
    primary = customer_experience.get("primary_cta") or {}
    route = primary.get("route")
    label = primary.get("label")
    return (str(route) if route else None, str(label) if label else None)


def _reason_for_denial(
    grant: str,
    action: CapabilityAction,
    *,
    capability_id: str,
) -> tuple[str, str]:
    semantic = normalize_grant_semantic(grant)
    if grant == GRANT_HIDDEN:
        return (
            CapabilityReasonCode.HIDDEN.value,
            f"{capability_id} is not available for your account status.",
        )
    if grant == GRANT_DENY or grant == GRANT_PLAN_GATED:
        code = CapabilityReasonCode.PLAN_DENIED.value if grant == GRANT_PLAN_GATED else CapabilityReasonCode.DENIED.value
        return (code, f"{capability_id} is not permitted for your account status.")
    if semantic == SEMANTIC_READ_ONLY and action == "write":
        return (
            CapabilityReasonCode.READ_ONLY_BLOCKED.value,
            f"{capability_id} is view-only for your account status. Changes are not permitted.",
        )
    return (CapabilityReasonCode.DENIED.value, f"{capability_id} is not permitted.")


class CapabilityEnforcementService:
    """Authoritative capability evaluator — consumes Runtime Contract only."""

    SOURCE = "runtime_contract"

    def __init__(self, db=None):
        self._db = db

    async def load_contract(self, client_id: str, *, include_audit: bool = False) -> Mapping[str, Any]:
        if not self._db:
            raise RuntimeError("CapabilityEnforcementService requires a database handle")
        return await resolve_runtime_contract_for_client(
            self._db,
            client_id,
            include_audit=include_audit,
        )

    def evaluate_from_contract(
        self,
        contract: Mapping[str, Any],
        capability_id: str,
        action: CapabilityAction = "write",
    ) -> CapabilityDecision:
        capabilities = contract.get("capabilities") or {}
        grant = capabilities.get(capability_id)
        customer_experience = contract.get("customer_experience") or {}
        recovery_route, recovery_label = _recovery_from_experience(customer_experience)
        warnings = tuple(contract.get("warnings") or ())
        base = {
            "capability_id": capability_id,
            "action": action,
            "lifecycle_state": contract.get("lifecycle_state"),
            "portal_mode": contract.get("portal_mode"),
            "runtime_version": contract.get("runtime_version"),
            "contract_version": contract.get("contract_version") or CONTRACT_VERSION,
            "warnings": warnings,
            "recovery_route": recovery_route,
            "recovery_label": recovery_label,
        }

        if grant is None:
            if capability_id in _BASE_CAPABILITY_MATRIX:
                grant = GRANT_DENY
            else:
                return CapabilityDecision(
                    **base,
                    grant=GRANT_HIDDEN,
                    effective_semantic=GRANT_HIDDEN,
                    allowed=False,
                    source=self.SOURCE,
                    reason_code=CapabilityReasonCode.UNKNOWN_CAPABILITY.value,
                    reason=(
                        f"{capability_id} is not present in the runtime contract capability map "
                        "(catalog gap — deferred enforcement)."
                    ),
                )

        semantic = normalize_grant_semantic(grant)
        allowed = is_grant_action_allowed(grant, action)

        if allowed:
            reason_code = CapabilityReasonCode.ALLOWED.value
            if grant == GRANT_LIMITED and action == "write":
                reason_code = CapabilityReasonCode.LIMITED_GRACE.value
            reason = f"{capability_id} permitted ({semantic})."
            return CapabilityDecision(
                **base,
                grant=grant,
                effective_semantic=semantic,
                allowed=True,
                source=self.SOURCE,
                reason_code=reason_code,
                reason=reason,
            )

        reason_code, reason = _reason_for_denial(grant, action, capability_id=capability_id)
        return CapabilityDecision(
            **base,
            grant=grant,
            effective_semantic=semantic,
            allowed=False,
            source=self.SOURCE,
            reason_code=reason_code,
            reason=reason,
        )

    async def evaluate(
        self,
        client_id: str,
        capability_id: str,
        action: CapabilityAction = "write",
        *,
        contract: Optional[Mapping[str, Any]] = None,
    ) -> CapabilityDecision:
        try:
            resolved = contract or await self.load_contract(client_id)
        except Exception as exc:
            logger.warning("capability enforcement contract load failed client_id=%s: %s", client_id, exc)
            return CapabilityDecision(
                capability_id=capability_id,
                action=action,
                grant=GRANT_DENY,
                effective_semantic=GRANT_DENY,
                allowed=False,
                source=self.SOURCE,
                reason_code=CapabilityReasonCode.RUNTIME_UNAVAILABLE.value,
                reason="Account capability status is temporarily unavailable.",
            )
        return self.evaluate_from_contract(resolved, capability_id, action)

    def evaluate_all_from_contract(self, contract: Mapping[str, Any]) -> list[CapabilityDecision]:
        """Evaluate read and write for every capability in the contract map (diagnostics)."""
        capabilities = contract.get("capabilities") or {}
        decisions: list[CapabilityDecision] = []
        for cap_id in sorted(capabilities.keys()):
            decisions.append(self.evaluate_from_contract(contract, cap_id, "read"))
            decisions.append(self.evaluate_from_contract(contract, cap_id, "write"))
        return decisions


def runtime_resolved_capability_ids() -> frozenset[str]:
    return frozenset(_BASE_CAPABILITY_MATRIX.keys())
