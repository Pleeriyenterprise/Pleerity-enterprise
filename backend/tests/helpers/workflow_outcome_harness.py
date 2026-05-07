from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from models import RequirementStatus
from services.compliance_evidence_record_service import (
    EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
    EVIDENCE_MODE_DOCUMENT_UPLOAD,
    EVIDENCE_MODE_STRUCTURED_DECLARATION,
    effective_evidence_resolution,
)
from services.reminder_truth_service import _requirement_state_key
from services.requirement_action_resolver import (
    enrich_take_action_envelope_for_client,
    resolve_take_action_envelope,
)
from services.requirement_evidence_authority import preview_authority
from services.requirement_truth import EVIDENCE_MISSING, EVIDENCE_VERIFIED, enrich_requirement_dict
from services.requirement_workflow_audit import (
    WC_DOCUMENT_UPLOAD,
    WC_EXTERNAL_ASSESSMENT_EVIDENCE,
    WC_GUIDED_DECLARATION,
    WC_MULTI_EVIDENCE,
    WC_REGISTRATION_TRACKING,
    WC_TENANT_DELIVERY,
    compute_workflow_mismatch_flags,
)
from services.workflow_behaviour_governance import CONDITION_STANDARD_ACTIVE_STANDARD


@dataclass(frozen=True)
class WorkflowScenario:
    key: str
    requirement_code: str
    requirement_type: str
    expected_workflow_class: str


DOCUMENT_UPLOAD_GAS = WorkflowScenario(
    key="document_upload_gas_safety",
    requirement_code="gas_safety",
    requirement_type="gas_safety",
    expected_workflow_class=WC_DOCUMENT_UPLOAD,
)
GUIDED_DECLARATION_TENANCY = WorkflowScenario(
    key="guided_declaration_tenancy_agreement",
    requirement_code="tenancy_agreement",
    requirement_type="tenancy_agreement",
    expected_workflow_class=WC_GUIDED_DECLARATION,
)
GUIDED_DECLARATION_DEPOSIT_PI = WorkflowScenario(
    key="guided_declaration_deposit_pi",
    requirement_code="deposit_pi",
    requirement_type="deposit_pi",
    expected_workflow_class=WC_GUIDED_DECLARATION,
)
EXTERNAL_ASSESSMENT_LEGIONELLA = WorkflowScenario(
    key="external_assessment_legionella",
    requirement_code="legionella",
    requirement_type="legionella",
    expected_workflow_class=WC_EXTERNAL_ASSESSMENT_EVIDENCE,
)
EXTERNAL_ASSESSMENT_LEAD = WorkflowScenario(
    key="external_assessment_lead_testing",
    requirement_code="lead_testing",
    requirement_type="lead_testing",
    expected_workflow_class=WC_EXTERNAL_ASSESSMENT_EVIDENCE,
)
CONDITION_STANDARD_FITNESS = WorkflowScenario(
    key="condition_standard_fitness_for_human_habitation",
    requirement_code="fitness_for_human_habitation",
    requirement_type="fitness_for_human_habitation",
    expected_workflow_class=CONDITION_STANDARD_ACTIVE_STANDARD,
)
CONDITION_STANDARD_REPAIRING = WorkflowScenario(
    key="condition_standard_repairing_standard",
    requirement_code="repairing_standard",
    requirement_type="repairing_standard",
    expected_workflow_class=CONDITION_STANDARD_ACTIVE_STANDARD,
)
MULTI_EVIDENCE_SMOKE_HEAT = WorkflowScenario(
    key="multi_evidence_smoke_heat_alarms",
    requirement_code="smoke_heat_alarms",
    requirement_type="smoke_heat_alarms",
    expected_workflow_class=WC_MULTI_EVIDENCE,
)
TENANT_DELIVERY_HOW_TO_RENT = WorkflowScenario(
    key="tenant_delivery_how_to_rent",
    requirement_code="how_to_rent",
    requirement_type="how_to_rent",
    expected_workflow_class=WC_TENANT_DELIVERY,
)
REGISTRATION_TRACKING_LANDLORD = WorkflowScenario(
    key="registration_tracking_landlord_registration",
    requirement_code="landlord_registration",
    requirement_type="landlord_registration",
    expected_workflow_class=WC_REGISTRATION_TRACKING,
)
REGISTRATION_TRACKING_RENT_SMART_WALES = WorkflowScenario(
    key="registration_tracking_rent_smart_wales",
    requirement_code="rent_smart_wales",
    requirement_type="rent_smart_wales",
    expected_workflow_class=WC_REGISTRATION_TRACKING,
)


def representative_workflow_scenarios() -> List[WorkflowScenario]:
    return [
        DOCUMENT_UPLOAD_GAS,
        GUIDED_DECLARATION_TENANCY,
        EXTERNAL_ASSESSMENT_LEGIONELLA,
    ]


def representative_phase2_workflow_scenarios() -> List[WorkflowScenario]:
    return [
        CONDITION_STANDARD_FITNESS,
        CONDITION_STANDARD_REPAIRING,
        MULTI_EVIDENCE_SMOKE_HEAT,
        TENANT_DELIVERY_HOW_TO_RENT,
        REGISTRATION_TRACKING_LANDLORD,
    ]


def build_two_property_requirements(
    scenario: WorkflowScenario, *, client_id: str = "client-wf-1"
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    base: Dict[str, Any] = {
        "client_id": client_id,
        "status": RequirementStatus.PENDING.value,
        "applicability": "REQUIRED",
        "jurisdiction": "England",
        "requirement_code": scenario.requirement_code,
        "requirement_type": scenario.requirement_type,
        "registry_metadata": {},
    }
    req_a = {
        **base,
        "property_id": "prop-A",
        "requirement_id": f"{scenario.key}-A",
    }
    req_b = {
        **base,
        "property_id": "prop-B",
        "requirement_id": f"{scenario.key}-B",
    }
    if scenario.expected_workflow_class in (WC_GUIDED_DECLARATION, WC_TENANT_DELIVERY):
        req_a["compliance_requirement_class"] = "OBLIGATION"
        req_a["engine_informational"] = True
        req_b["compliance_requirement_class"] = "OBLIGATION"
        req_b["engine_informational"] = True
    else:
        req_a["compliance_requirement_class"] = "DOCUMENT"
        req_b["compliance_requirement_class"] = "DOCUMENT"
    return req_a, req_b


def apply_phase2_scenario_defaults(scenario: WorkflowScenario, requirement: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(requirement)
    if scenario.requirement_code == "repairing_standard":
        out["jurisdiction"] = "Scotland"
    if scenario.requirement_code == "rent_smart_wales":
        out["jurisdiction"] = "Wales"
    if scenario.expected_workflow_class == CONDITION_STANDARD_ACTIVE_STANDARD:
        out["compliance_requirement_class"] = "OBLIGATION"
        out["engine_informational"] = True
    return out


def build_property_a_evidence_record(scenario: WorkflowScenario, requirement_a: Dict[str, Any]) -> Dict[str, Any]:
    base = {
        "evidence_record_id": f"cer-{scenario.key}-A",
        "client_id": requirement_a["client_id"],
        "property_id": requirement_a["property_id"],
        "requirement_id": requirement_a["requirement_id"],
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
    }
    if scenario.expected_workflow_class == WC_DOCUMENT_UPLOAD:
        return {
            **base,
            "evidence_mode": EVIDENCE_MODE_DOCUMENT_UPLOAD,
            "evidence_confidence_level": "HIGH",
            "linked_document_ids": ["doc-gas-a"],
            "evidence_payload": {"certificate_number": "GAS-CP12-A", "expiry_date": "2027-01-15"},
        }
    if scenario.expected_workflow_class == WC_GUIDED_DECLARATION:
        if scenario.requirement_code == "deposit_pi":
            return {
                **base,
                "evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
                "evidence_confidence_level": "MEDIUM",
                "evidence_payload": {
                    "declaration_statement": "Deposit prescribed information declaration (harness).",
                    "structured_fields": {
                        "deposit_taken": {"answer": True},
                        "prescribed_information_served": {"answer": True},
                        "declaration_confirmed": {"answer": True},
                    },
                },
                "linked_document_ids": [],
            }
        return {
            **base,
            "evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
            "evidence_confidence_level": "MEDIUM",
            "evidence_payload": {
                "declaration_statement": "Tenancy agreement has been provided to the tenant",
                "structured_fields": {
                    "agreement_exists": {"answer": True},
                    "signed_by_parties": {"answer": True},
                },
            },
            "linked_document_ids": [],
        }
    if scenario.expected_workflow_class == WC_REGISTRATION_TRACKING:
        return {
            **base,
            "evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
            "evidence_confidence_level": "MEDIUM",
            "evidence_payload": {
                "declaration_statement": "Registration details recorded (harness).",
                "structured_fields": {
                    "registration_number": {"answer": "REG-HARNESS-A"},
                    "issuing_authority": {"answer": "Harness issuing authority"},
                    "registration_status": {"answer": "active"},
                    "declaration_confirmed": {"answer": True},
                },
            },
            "linked_document_ids": [],
        }
    if scenario.expected_workflow_class == WC_TENANT_DELIVERY:
        return {
            **base,
            "evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
            "evidence_confidence_level": "MEDIUM",
            "evidence_payload": {
                "declaration_statement": "How to Rent delivery recorded (harness).",
                "structured_fields": {
                    "tenancy_start_date": {"answer": "2026-01-01"},
                    "guide_version_or_publication_date": {"answer": "2025 edition"},
                    "delivery_date": {"answer": "2026-01-02"},
                    "delivery_method": {"answer": "email"},
                    "tenant_recipient": {"answer": "Harness Tenant"},
                    "declaration_confirmed": {"answer": True},
                },
            },
            "linked_document_ids": [],
        }
    return {
        **base,
        "evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
        "evidence_confidence_level": "CONDITIONAL",
        "evidence_payload": {
            "declaration_statement": "Legionella assessment completed; follow-up actions are still required.",
            "structured_fields": {
                "actions_required": {"answer": True},
                "next_review_date": {"answer": "2027-03-01"},
            },
        },
        "linked_document_ids": ["doc-legionella-report-a"],
    }


def build_property_a_upload_only_record(scenario: WorkflowScenario, requirement_a: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "evidence_record_id": f"cer-{scenario.key}-upload-only-A",
        "client_id": requirement_a["client_id"],
        "property_id": requirement_a["property_id"],
        "requirement_id": requirement_a["requirement_id"],
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": EVIDENCE_MODE_DOCUMENT_UPLOAD,
        "evidence_confidence_level": "HIGH",
        "linked_document_ids": [f"doc-{scenario.requirement_code}-upload-A"],
        "evidence_payload": {"source": "phase2_upload_only_probe"},
    }


def build_property_a_partial_multi_evidence_record(requirement_a: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "evidence_record_id": "cer-multi-evidence-partial-A",
        "client_id": requirement_a["client_id"],
        "property_id": requirement_a["property_id"],
        "requirement_id": requirement_a["requirement_id"],
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
        "evidence_confidence_level": "MEDIUM",
        "linked_document_ids": [],
        "evidence_payload": {
            "component": "alarm_installation",
            "component_complete": True,
            "note": "partial multi-component evidence only",
        },
    }


def build_property_a_structured_record_for_registration_or_delivery(
    scenario: WorkflowScenario, requirement_a: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "evidence_record_id": f"cer-{scenario.key}-structured-A",
        "client_id": requirement_a["client_id"],
        "property_id": requirement_a["property_id"],
        "requirement_id": requirement_a["requirement_id"],
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
        "evidence_confidence_level": "MEDIUM",
        "linked_document_ids": [],
        "evidence_payload": {
            "structured_fields": {
                "served": {"answer": True},
                "record_reference": {"answer": "REC-PHASE2-A"},
            }
        },
    }


def build_property_a_verified_document(requirement_a: Dict[str, Any]) -> Dict[str, Any]:
    fut = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    return {
        "document_id": f"doc-{requirement_a['requirement_id']}-A",
        "client_id": requirement_a["client_id"],
        "property_id": requirement_a["property_id"],
        "requirement_id": requirement_a["requirement_id"],
        "status": "VERIFIED",
        "expiry_date": fut,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "authoritative_property_id": requirement_a["property_id"],
        "evidence_scope_type": "PROPERTY",
        "evidence_scope_id": requirement_a["property_id"],
    }


def build_property_a_verified_document_no_expiry(requirement_a: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(build_property_a_verified_document(requirement_a))
    d.pop("expiry_date", None)
    return d


def scoped_records_for_requirement(
    records: List[Dict[str, Any]], requirement: Dict[str, Any]
) -> List[Dict[str, Any]]:
    rid = str(requirement.get("requirement_id") or "")
    pid = str(requirement.get("property_id") or "")
    return [
        r
        for r in (records or [])
        if str(r.get("requirement_id") or "") == rid and str(r.get("property_id") or "") == pid
    ]


def preview_requirement_authority_with_scoped_records(
    requirement: Dict[str, Any], records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    policy = effective_evidence_resolution(requirement)
    scoped = scoped_records_for_requirement(records, requirement)
    return preview_authority(requirement, [], evidence_records=scoped, evidence_policy=policy)


def preview_requirement_authority_with_scoped_records_and_property_context(
    requirement: Dict[str, Any], records: List[Dict[str, Any]], property_context: Dict[str, Any]
) -> Dict[str, Any]:
    policy = effective_evidence_resolution(requirement)
    scoped = scoped_records_for_requirement(records, requirement)
    return preview_authority(
        requirement,
        [],
        property_doc=property_context,
        evidence_records=scoped,
        evidence_policy=policy,
    )


def enrich_requirement_projection(
    requirement: Dict[str, Any], authority_preview: Dict[str, Any], records: List[Dict[str, Any]], *, audience: str = "client"
) -> Dict[str, Any]:
    req = dict(requirement)
    ev_auth = authority_preview.get("evidence_authority")
    if isinstance(ev_auth, dict):
        req["evidence_authority"] = ev_auth
    mirror_status = str((authority_preview.get("mirror") or {}).get("status") or "").upper()
    live_state = EVIDENCE_VERIFIED if mirror_status == RequirementStatus.COMPLIANT.value else EVIDENCE_MISSING
    return enrich_requirement_dict(
        req,
        live_state,
        audience=audience,
        compliance_evidence_records=scoped_records_for_requirement(records, requirement),
    )


def resolver_projection(requirement: Dict[str, Any]) -> Dict[str, Any]:
    env = resolve_take_action_envelope(
        requirement,
        property_id=requirement.get("property_id"),
        property_jurisdiction=requirement.get("jurisdiction"),
    )
    return enrich_take_action_envelope_for_client(env, requirement)


def reminder_state_key_for_requirement(requirement: Dict[str, Any]) -> Dict[str, str]:
    return _requirement_state_key(requirement, "DAILY_COMPLIANCE_EXPIRY_EMAIL")


def workflow_mismatch_ids(enriched_admin_row: Dict[str, Any], expected_workflow_class: str) -> List[str]:
    flags = compute_workflow_mismatch_flags(
        enriched_admin_row,
        reference_class=expected_workflow_class,
        reference_source="phase1_harness",
    )
    return [str(f.get("id") or "") for f in flags]
