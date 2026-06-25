"""
Phase 2 S5/S5.4 — lifecycle-aware confirm persistence authority.

Off: legacy persistence. Shadow: legacy + telemetry. Active (preview): active plan.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.lifecycle_aware_confirm_config import (
    get_effective_confirm_mode,
    is_lifecycle_aware_confirm_off,
    is_lifecycle_aware_confirm_shadow,
)
from services.lifecycle_confirm_contract import build_contract_for_requirement
from services.lifecycle_semantics_types import LifecycleSemantics

logger = logging.getLogger(__name__)

TARGET_STRUCTURED_DECLARATION = "requirement.structured_declaration"

_EXPIRY_PROXY_FIELDS = frozenset(
    {"expiry_date", "confirmed_expiry_date", "extracted_expiry_date"}
)
_CERT_EXPIRY_PERSISTENCE_FIELDS = frozenset(
    {
        "due_date",
        "extracted_expiry_date",
        "confirmed_expiry_date",
        "expiry_source",
    }
)

_SEMANTICS_STRUCTURED_FIELD_NAMES: Dict[LifecycleSemantics, Tuple[str, ...]] = {
    "REVIEW_BASED": (
        "assessment_date",
        "review_date",
        "next_review_date",
        "risk_level",
        "registration_number",
        "issuing_authority",
        "registration_status",
        "assessor_type",
        "control_measures_summary",
    ),
    "DECLARATION_BASED": (
        "protection_date",
        "served_date",
        "delivery_date",
        "scheme_name",
        "scheme_reference",
        "deposit_amount",
        "deposit_received_date",
        "served_to",
        "service_method",
        "guide_version",
    ),
    "EVENT_BASED": (
        "event_date",
        "event_type",
        "completion_notes",
        "installer_name",
    ),
    "TENANCY_LIFECYCLE": (
        "tenancy_start_date",
        "fixed_term_end_date",
        "tenancy_end_date",
        "tenant_name",
        "landlord_name",
        "agreement_type",
        "rent_amount",
    ),
    "OCCUPANCY_LIFECYCLE": (
        "check_date",
        "follow_up_date",
        "document_type",
        "tenant_name",
        "right_to_rent_status",
        "follow_up_required",
    ),
    "OPERATIONAL": (
        "completion_date",
        "responsible_person",
        "work_summary",
    ),
}


@dataclass
class PersistencePlan:
    """Requirement $set fields for a confirm surface (excludes route-specific truth fields)."""

    update_fields: Dict[str, Any] = field(default_factory=dict)
    changes_made: List[str] = field(default_factory=list)


@dataclass
class ShadowPersistenceObservation:
    skipped_fields: List[str] = field(default_factory=list)
    rerouted_fields: Dict[str, str] = field(default_factory=dict)
    target_store: str = ""
    lifecycle_semantics: str = ""
    extraction_profile_id: str = ""


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _existing_structured_declaration(requirement: Dict[str, Any]) -> Dict[str, Any]:
    existing = requirement.get("structured_declaration")
    if isinstance(existing, dict):
        return dict(existing)
    return {}


def _collect_semantic_values(payload: Dict[str, Any], semantics: LifecycleSemantics) -> Dict[str, Any]:
    names = _SEMANTICS_STRUCTURED_FIELD_NAMES.get(semantics, ())
    out: Dict[str, Any] = {}
    for name in names:
        if _is_present(payload.get(name)):
            out[name] = payload.get(name)
    return out


def _cert_status_from_expiry(expiry_dt: datetime) -> Tuple[str, str]:
    now = datetime.now(timezone.utc)
    if expiry_dt < now:
        return "OVERDUE", "Status set to OVERDUE (past due date)"
    if expiry_dt < now + timedelta(days=30):
        return "EXPIRING_SOON", "Status set to EXPIRING_SOON (expires within 30 days)"
    return "COMPLIANT", "Status set to COMPLIANT (valid certificate)"


def build_legacy_apply_extraction_update(
    payload: Dict[str, Any],
    *,
    parse_date: Callable[[Any], datetime],
) -> PersistencePlan:
    """
    Legacy apply-extraction / admin-confirm requirement update (cert-centric expiry pipeline).
    """
    plan = PersistencePlan()
    expiry_date = payload.get("expiry_date")
    if not _is_present(expiry_date):
        return plan

    expiry_dt = parse_date(expiry_date)
    plan.update_fields["due_date"] = expiry_dt.isoformat()
    plan.update_fields["extracted_expiry_date"] = expiry_dt.isoformat()
    plan.update_fields["expiry_source"] = "EXTRACTED"
    plan.changes_made.append(f"Due date set to {expiry_dt.strftime('%Y-%m-%d')}")

    conf = (
        payload.get("confidence_scores", {}).get("overall")
        if isinstance(payload.get("confidence_scores"), dict)
        else payload.get("confidence")
    )
    if conf is not None:
        try:
            plan.update_fields["extraction_confidence"] = float(conf)
        except (TypeError, ValueError):
            pass

    status, status_msg = _cert_status_from_expiry(expiry_dt)
    plan.update_fields["status"] = status
    plan.changes_made.append(status_msg)
    return plan


def build_legacy_patch_requirement_update(
    *,
    confirmed_expiry_date: Optional[str] = None,
    issue_date: Optional[str] = None,
    certificate_number: Optional[str] = None,
    parse_iso: Callable[[str], datetime],
) -> PersistencePlan:
    plan = PersistencePlan()
    if confirmed_expiry_date is not None:
        parsed = parse_iso(confirmed_expiry_date)
        plan.update_fields["confirmed_expiry_date"] = parsed.isoformat()
        plan.update_fields["expiry_source"] = "CONFIRMED"
        plan.update_fields["due_date"] = parsed.isoformat()
        plan.update_fields["date_source"] = "USER_PROVIDED"
        plan.update_fields["confidence_state"] = "PARTIALLY_CONFIRMED"
    if issue_date is not None:
        parsed = parse_iso(issue_date)
        plan.update_fields["issue_date"] = parsed.isoformat()
    if certificate_number is not None:
        plan.update_fields["certificate_number"] = (certificate_number or "").strip() or None
    return plan


def build_active_plan_apply_extraction_update(
    requirement: Dict[str, Any],
    payload: Dict[str, Any],
    contract: Dict[str, Any],
    *,
    parse_date: Callable[[Any], datetime],
) -> PersistencePlan:
    semantics = str(contract.get("lifecycle_semantics") or "")
    plan = PersistencePlan()

    if semantics == "EXPIRY_BASED":
        expiry_val = payload.get("expiry_date") or payload.get("confirmed_expiry_date")
        if _is_present(expiry_val):
            expiry_plan = build_legacy_apply_extraction_update(
                {"expiry_date": expiry_val, **payload},
                parse_date=parse_date,
            )
            plan.update_fields.update(expiry_plan.update_fields)
            plan.changes_made.extend(expiry_plan.changes_made)
        if _is_present(payload.get("issue_date")):
            try:
                issue_dt = parse_date(payload["issue_date"])
                plan.update_fields["issue_date"] = issue_dt.isoformat()
            except ValueError:
                pass
        cert = payload.get("certificate_number") or payload.get("licence_number")
        if _is_present(cert):
            field_name = "licence_number" if _is_present(payload.get("licence_number")) else "certificate_number"
            plan.update_fields[field_name] = str(cert).strip()
        return plan

    structured = _collect_semantic_values(payload, semantics)  # type: ignore[arg-type]
    if structured:
        merged = {**_existing_structured_declaration(requirement), **structured}
        plan.update_fields["structured_declaration"] = merged
        for key in structured:
            plan.changes_made.append(f"{key} recorded in structured_declaration")

    if _is_present(payload.get("issue_date")) and semantics == "REVIEW_BASED":
        try:
            issue_dt = parse_date(payload["issue_date"])
            plan.update_fields["issue_date"] = issue_dt.isoformat()
        except ValueError:
            pass

    return plan


def build_active_plan_patch_requirement_update(
    requirement: Dict[str, Any],
    payload: Dict[str, Any],
    contract: Dict[str, Any],
    *,
    parse_iso: Callable[[str], datetime],
) -> PersistencePlan:
    semantics = str(contract.get("lifecycle_semantics") or "")
    plan = PersistencePlan()

    if semantics == "EXPIRY_BASED":
        return build_legacy_patch_requirement_update(
            confirmed_expiry_date=payload.get("confirmed_expiry_date"),
            issue_date=payload.get("issue_date"),
            certificate_number=payload.get("certificate_number"),
            parse_iso=parse_iso,
        )

    structured = _collect_semantic_values(payload, semantics)  # type: ignore[arg-type]
    if _is_present(payload.get("confirmed_expiry_date")):
        structured = dict(structured)
    if structured:
        merged = {**_existing_structured_declaration(requirement), **structured}
        plan.update_fields["structured_declaration"] = merged

    if payload.get("issue_date") is not None and semantics == "REVIEW_BASED":
        parsed = parse_iso(str(payload["issue_date"]))
        plan.update_fields["issue_date"] = parsed.isoformat()
    if payload.get("certificate_number") is not None and semantics == "EXPIRY_BASED":
        plan.update_fields["certificate_number"] = (payload.get("certificate_number") or "").strip() or None

    return plan


def _diff_legacy_vs_active(
    legacy: PersistencePlan,
    active: PersistencePlan,
    contract: Dict[str, Any],
) -> ShadowPersistenceObservation:
    semantics = str(contract.get("lifecycle_semantics") or "")
    obs = ShadowPersistenceObservation(
        lifecycle_semantics=semantics,
        extraction_profile_id=str(contract.get("extraction_profile_id") or ""),
        target_store=(
            "requirement.top_level_cert_fields"
            if semantics == "EXPIRY_BASED"
            else TARGET_STRUCTURED_DECLARATION
        ),
    )

    if semantics == "EXPIRY_BASED":
        return obs

    for field_name in sorted(_CERT_EXPIRY_PERSISTENCE_FIELDS):
        if field_name in legacy.update_fields and field_name not in active.update_fields:
            obs.skipped_fields.append(field_name)

    if legacy.update_fields.get("status") in ("OVERDUE", "EXPIRING_SOON", "COMPLIANT"):
        if active.update_fields.get("status") != legacy.update_fields.get("status"):
            obs.skipped_fields.append("status")

    if active.update_fields.get("structured_declaration"):
        for key in active.update_fields["structured_declaration"]:
            if key in legacy.update_fields or key in _EXPIRY_PROXY_FIELDS:
                obs.rerouted_fields[key] = TARGET_STRUCTURED_DECLARATION
            elif key not in obs.rerouted_fields:
                obs.rerouted_fields[key] = TARGET_STRUCTURED_DECLARATION

    for proxy in _EXPIRY_PROXY_FIELDS:
        if proxy in legacy.update_fields or (
            proxy == "expiry_date" and "due_date" in legacy.update_fields
        ):
            if proxy not in obs.skipped_fields and proxy != "expiry_date":
                obs.skipped_fields.append(proxy)
    if "due_date" in legacy.update_fields and "due_date" not in active.update_fields:
        if "due_date" not in obs.skipped_fields:
            obs.skipped_fields.append("due_date")

    return obs


def observe_shadow_persistence_for_requirement(
    requirement: Dict[str, Any],
    payload: Dict[str, Any],
    *,
    surface: str,
    parse_date: Callable[[Any], datetime],
    parse_iso: Optional[Callable[[str], datetime]] = None,
    registry_row: Optional[Dict[str, Any]] = None,
    document: Optional[Dict[str, Any]] = None,
    requirement_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> Optional[ShadowPersistenceObservation]:
    """
    Shadow-only: log fields legacy persistence would write that active plan would skip/reroute.
    Does not mutate persistence.
    """
    if is_lifecycle_aware_confirm_off() or not is_lifecycle_aware_confirm_shadow():
        return None

    contract = build_contract_for_requirement(
        requirement,
        registry_row=registry_row,
        document=document,
    )
    iso_parser = parse_iso or (
        lambda raw: datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    )

    if surface == "patch_requirement":
        legacy = build_legacy_patch_requirement_update(
            confirmed_expiry_date=payload.get("confirmed_expiry_date"),
            issue_date=payload.get("issue_date"),
            certificate_number=payload.get("certificate_number"),
            parse_iso=iso_parser,
        )
        active = build_active_plan_patch_requirement_update(
            requirement,
            payload,
            contract,
            parse_iso=iso_parser,
        )
    else:
        legacy = build_legacy_apply_extraction_update(payload, parse_date=parse_date)
        active = build_active_plan_apply_extraction_update(
            requirement,
            payload,
            contract,
            parse_date=parse_date,
        )

    obs = _diff_legacy_vs_active(legacy, active, contract)
    if not obs.skipped_fields and not obs.rerouted_fields:
        return obs

    logger.info(
        "lifecycle_confirm_shadow_would_skip_persistence",
        extra={
            "surface": surface,
            "requirement_id": requirement_id or requirement.get("requirement_id"),
            "document_id": document_id,
            "lifecycle_semantics": obs.lifecycle_semantics,
            "extraction_profile_id": obs.extraction_profile_id,
            "skipped_fields": obs.skipped_fields,
            "rerouted_fields": obs.rerouted_fields,
            "target_store": obs.target_store,
        },
    )
    return obs


def strip_forbidden_contract_fields(
    payload: Dict[str, Any],
    contract: Dict[str, Any],
) -> Dict[str, Any]:
    """Remove contract-forbidden keys before active-mode persistence."""
    forbidden = set(contract.get("forbidden_fields") or [])
    semantics = str(contract.get("lifecycle_semantics") or "")
    if semantics != "EXPIRY_BASED":
        forbidden |= _EXPIRY_PROXY_FIELDS | _CERT_EXPIRY_PERSISTENCE_FIELDS | {"status"}
    return {k: v for k, v in payload.items() if k not in forbidden}


def resolve_confirm_persistence_update(
    requirement: Dict[str, Any],
    payload: Dict[str, Any],
    *,
    surface: str,
    parse_date: Callable[[Any], datetime],
    parse_iso: Optional[Callable[[str], datetime]] = None,
    registry_row: Optional[Dict[str, Any]] = None,
    document: Optional[Dict[str, Any]] = None,
    requirement_id: Optional[str] = None,
    document_id: Optional[str] = None,
    confirmed_expiry_date: Optional[str] = None,
    issue_date: Optional[str] = None,
    certificate_number: Optional[str] = None,
) -> PersistencePlan:
    """
    Mode matrix:
    - off → legacy persistence
    - shadow → legacy persistence + shadow telemetry
    - active → active persistence plan (forbidden fields stripped)
    """
    mode = get_effective_confirm_mode()
    iso_parser = parse_iso or (
        lambda raw: datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    )

    if surface == "patch_requirement":
        patch_payload = dict(payload)
        if confirmed_expiry_date is not None:
            patch_payload.setdefault("confirmed_expiry_date", confirmed_expiry_date)
        if issue_date is not None:
            patch_payload.setdefault("issue_date", issue_date)
        if certificate_number is not None:
            patch_payload.setdefault("certificate_number", certificate_number)
    else:
        patch_payload = payload

    if mode == "shadow":
        observe_shadow_persistence_for_requirement(
            requirement,
            patch_payload if surface == "patch_requirement" else payload,
            surface=surface,
            parse_date=parse_date,
            parse_iso=iso_parser,
            registry_row=registry_row,
            document=document,
            requirement_id=requirement_id,
            document_id=document_id,
        )

    if mode != "active":
        if surface == "patch_requirement":
            return build_legacy_patch_requirement_update(
                confirmed_expiry_date=confirmed_expiry_date,
                issue_date=issue_date,
                certificate_number=certificate_number,
                parse_iso=iso_parser,
            )
        return build_legacy_apply_extraction_update(payload, parse_date=parse_date)

    contract = build_contract_for_requirement(
        requirement,
        registry_row=registry_row,
        document=document,
    )
    semantics = str(contract.get("lifecycle_semantics") or "")
    if surface == "patch_requirement":
        active_payload = strip_forbidden_contract_fields(patch_payload, contract)
        return build_active_plan_patch_requirement_update(
            requirement,
            active_payload,
            contract,
            parse_iso=iso_parser,
        )

    active_payload = strip_forbidden_contract_fields(payload, contract)
    return build_active_plan_apply_extraction_update(
        requirement,
        active_payload,
        contract,
        parse_date=parse_date,
    )


def get_apply_extraction_requirement_update(
    requirement: Dict[str, Any],
    payload: Dict[str, Any],
    *,
    parse_date: Callable[[Any], datetime],
    surface: str = "apply_extraction",
    registry_row: Optional[Dict[str, Any]] = None,
    document: Optional[Dict[str, Any]] = None,
    requirement_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> PersistencePlan:
    """
    Returns persistence plan for apply-extraction / admin-confirm surfaces.
    """
    return resolve_confirm_persistence_update(
        requirement,
        payload,
        surface=surface,
        parse_date=parse_date,
        registry_row=registry_row,
        document=document,
        requirement_id=requirement_id,
        document_id=document_id,
    )


def get_patch_requirement_update(
    requirement: Dict[str, Any],
    *,
    confirmed_expiry_date: Optional[str] = None,
    issue_date: Optional[str] = None,
    certificate_number: Optional[str] = None,
    parse_iso: Callable[[str], datetime],
    requirement_id: Optional[str] = None,
    registry_row: Optional[Dict[str, Any]] = None,
    document: Optional[Dict[str, Any]] = None,
) -> PersistencePlan:
    payload: Dict[str, Any] = {}
    if confirmed_expiry_date is not None:
        payload["confirmed_expiry_date"] = confirmed_expiry_date
    if issue_date is not None:
        payload["issue_date"] = issue_date
    if certificate_number is not None:
        payload["certificate_number"] = certificate_number

    return resolve_confirm_persistence_update(
        requirement,
        payload,
        surface="patch_requirement",
        parse_date=lambda v: parse_iso(str(v)),
        parse_iso=parse_iso,
        registry_row=registry_row,
        document=document,
        requirement_id=requirement_id,
        confirmed_expiry_date=confirmed_expiry_date,
        issue_date=issue_date,
        certificate_number=certificate_number,
    )
