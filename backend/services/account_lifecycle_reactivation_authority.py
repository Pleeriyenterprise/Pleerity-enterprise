"""
Account Lifecycle Reactivation Authority (ILP-8).

Central orchestration metadata for account reactivation and recovery journeys.
Consumes Runtime Contract reactivation_policy — does not execute billing/Stripe.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from services.account_lifecycle_runtime_contract import (
    CONTRACT_VERSION,
    resolve_runtime_contract_for_client,
)

logger = logging.getLogger(__name__)

POLICY_VERSION = "account_lifecycle_reactivation_v1"


class ReactivationOutcome(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True)
class RecoveryStep:
    step_id: str
    label: str
    route: Optional[str] = None
    action: Optional[str] = None
    required: bool = True


@dataclass(frozen=True)
class RecoveryJourney:
    journey_id: str
    label: str
    eligible: bool
    steps: List[RecoveryStep]
    completion_condition: str
    next_lifecycle_hint: str
    cta_label: str
    cta_route: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "journey_id": self.journey_id,
            "label": self.label,
            "eligible": self.eligible,
            "steps": [
                {
                    "step_id": s.step_id,
                    "label": s.label,
                    "route": s.route,
                    "action": s.action,
                    "required": s.required,
                }
                for s in self.steps
            ],
            "completion_condition": self.completion_condition,
            "next_lifecycle_hint": self.next_lifecycle_hint,
            "cta_label": self.cta_label,
            "cta_route": self.cta_route,
        }


_RECOVERY_JOURNEYS: Dict[str, Dict[str, Any]] = {
    "complete_payment": {
        "label": "Complete payment",
        "steps": [
            {"step_id": "review_billing", "label": "Review billing status", "route": "/settings/billing", "action": "view_billing"},
            {"step_id": "update_payment", "label": "Update payment method", "route": "/settings/billing", "action": "update_payment_method"},
            {"step_id": "confirm_subscription", "label": "Confirm subscription", "route": "/settings/billing", "action": "reactivate_subscription"},
        ],
        "completion_condition": "subscription_active",
        "next_lifecycle_hint": "ACTIVE",
        "cta_label": "Manage billing",
        "cta_route": "/settings/billing",
    },
    "reactivate_account": {
        "label": "Reactivate account",
        "steps": [
            {"step_id": "choose_plan", "label": "Choose a plan", "route": "/settings/billing", "action": "reactivate_account"},
            {"step_id": "refresh_runtime", "label": "Refresh account status", "route": "/today", "action": "refresh_runtime"},
        ],
        "completion_condition": "portal_mode_full_access",
        "next_lifecycle_hint": "ACTIVE",
        "cta_label": "Subscribe to edit",
        "cta_route": "/settings/billing",
    },
    "undo_scheduled_cancellation": {
        "label": "Resume subscription",
        "steps": [
            {"step_id": "billing", "label": "Review cancellation", "route": "/settings/billing", "action": "resume_subscription"},
        ],
        "completion_condition": "cancel_at_period_end_cleared",
        "next_lifecycle_hint": "ACTIVE",
        "cta_label": "Manage billing",
        "cta_route": "/settings/billing",
    },
    "contact_support": {
        "label": "Contact support",
        "steps": [
            {"step_id": "support", "label": "Contact support", "route": "/support", "action": "contact_support"},
        ],
        "completion_condition": "manual_reinstatement",
        "next_lifecycle_hint": "ACTIVE",
        "cta_label": "Contact support",
        "cta_route": "/support",
    },
    "review_invoices": {
        "label": "Review invoices",
        "steps": [
            {"step_id": "invoices", "label": "View invoices", "route": "/settings/billing", "action": "view_invoices"},
        ],
        "completion_condition": "payment_resolved",
        "next_lifecycle_hint": "ACTIVE",
        "cta_label": "View invoices",
        "cta_route": "/settings/billing",
    },
}


def _default_journey_for_contract(contract: Mapping[str, Any]) -> str:
    ls = str(contract.get("lifecycle_state") or "UNKNOWN").upper()
    pm = str(contract.get("portal_mode") or "")
    if pm in ("BILLING_RECOVERY", "PAYMENT_REQUIRED") or ls in ("CANCELLED_IMMEDIATE", "SUBSCRIPTION_EXPIRED", "GRACE_PERIOD"):
        return "complete_payment"
    if ls == "READ_ONLY" or pm == "READ_ONLY":
        return "reactivate_account"
    if ls == "CANCELLATION_SCHEDULED":
        return "undo_scheduled_cancellation"
    if ls in ("SUSPENDED", "ARCHIVED", "ACCOUNT_DELETED") or pm == "SUSPENDED":
        return "contact_support"
    return "complete_payment"


@dataclass(frozen=True)
class ReactivationPlan:
    eligible: bool
    outcome: str
    lifecycle_state: str
    portal_mode: str
    paths: List[str]
    restoration_scope: str
    recovery_journey: RecoveryJourney
    resume_background: bool
    resume_communications: bool
    refresh_session_runtime: bool
    runtime_version: Optional[Any] = None
    policy_version: str = POLICY_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eligible": self.eligible,
            "outcome": self.outcome,
            "lifecycle_state": self.lifecycle_state,
            "portal_mode": self.portal_mode,
            "paths": list(self.paths),
            "restoration_scope": self.restoration_scope,
            "recovery_journey": self.recovery_journey.to_dict(),
            "resume_background": self.resume_background,
            "resume_communications": self.resume_communications,
            "refresh_session_runtime": self.refresh_session_runtime,
            "runtime_version": self.runtime_version,
            "policy_version": self.policy_version,
        }


class LifecycleReactivationAuthority:
    """Governed reactivation and recovery journey metadata from Runtime Contract."""

    @staticmethod
    def recovery_journey(
        journey_id: str,
        *,
        contract: Mapping[str, Any],
        eligible_override: Optional[bool] = None,
    ) -> RecoveryJourney:
        spec = _RECOVERY_JOURNEYS.get(journey_id) or _RECOVERY_JOURNEYS["contact_support"]
        reactivation = dict(contract.get("reactivation_policy") or {})
        eligible = eligible_override if eligible_override is not None else bool(reactivation.get("eligible"))
        cx = dict(contract.get("customer_experience") or {})
        primary = cx.get("primary_cta") or {}
        steps = [
            RecoveryStep(
                step_id=str(s["step_id"]),
                label=str(s["label"]),
                route=s.get("route"),
                action=s.get("action"),
            )
            for s in spec.get("steps") or []
        ]
        return RecoveryJourney(
            journey_id=journey_id,
            label=str(spec.get("label") or journey_id),
            eligible=eligible,
            steps=steps,
            completion_condition=str(spec.get("completion_condition") or ""),
            next_lifecycle_hint=str(spec.get("next_lifecycle_hint") or "ACTIVE"),
            cta_label=str(primary.get("label") or spec.get("cta_label") or ""),
            cta_route=str(primary.get("route") or spec.get("cta_route") or "/support"),
        )

    @staticmethod
    def reactivation_plan(
        contract: Mapping[str, Any],
        *,
        journey_id: Optional[str] = None,
    ) -> ReactivationPlan:
        reactivation = dict(contract.get("reactivation_policy") or {})
        eligible = bool(reactivation.get("eligible"))
        paths = list(reactivation.get("paths") or [])
        scope = str(reactivation.get("restoration_scope") or "MANUAL_REVIEW")
        lifecycle_state = str(contract.get("lifecycle_state") or "UNKNOWN")
        portal_mode = str(contract.get("portal_mode") or "")

        jid = journey_id or _default_journey_for_contract(contract)
        journey = LifecycleReactivationAuthority.recovery_journey(jid, contract=contract, eligible_override=eligible)

        if not eligible:
            outcome = ReactivationOutcome.INELIGIBLE.value
        elif scope == "MANUAL_REVIEW":
            outcome = ReactivationOutcome.MANUAL_REVIEW.value
        else:
            outcome = ReactivationOutcome.ELIGIBLE.value

        bg = dict(contract.get("background_policy") or {})
        resume_bg = eligible and any(str(v).upper() == "CONTINUE" for v in bg.values())
        comm = dict(contract.get("communication_policy") or {})
        resume_comms = eligible and any(
            comm.get(k) for k in ("email_operational", "email_billing", "sms", "portal_notifications")
        )

        return ReactivationPlan(
            eligible=eligible,
            outcome=outcome,
            lifecycle_state=lifecycle_state,
            portal_mode=portal_mode,
            paths=paths,
            restoration_scope=scope,
            recovery_journey=journey,
            resume_background=resume_bg,
            resume_communications=resume_comms,
            refresh_session_runtime=eligible,
            runtime_version=contract.get("runtime_version"),
        )


async def resolve_reactivation_plan_for_client(
    db,
    client_id: str,
    *,
    journey_id: Optional[str] = None,
    contract: Optional[Mapping[str, Any]] = None,
) -> ReactivationPlan:
    if contract is None:
        contract = await resolve_runtime_contract_for_client(db, client_id)
    plan = LifecycleReactivationAuthority.reactivation_plan(contract, journey_id=journey_id)
    log_reactivation_plan(client_id, plan)
    return plan


def log_reactivation_plan(client_id: str, plan: ReactivationPlan) -> None:
    logger.info(
        "reactivation_plan client_id=%s eligible=%s outcome=%s journey=%s lifecycle=%s runtime_version=%s policy=%s",
        client_id,
        plan.eligible,
        plan.outcome,
        plan.recovery_journey.journey_id,
        plan.lifecycle_state,
        plan.runtime_version,
        POLICY_VERSION,
    )
