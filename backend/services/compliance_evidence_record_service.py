"""
Normalized compliance evidence records (non-document modes + document metadata).

Phase-1 evidence modes only; no workflow engine. Policy is driven by published registry
``registry_metadata.evidence_resolution`` with safe defaults when absent.
"""
from __future__ import annotations

from collections import defaultdict
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from services.requirement_code_registry import normalize_requirement_code

logger = logging.getLogger(__name__)

RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE = (
    "Enter a follow-up check date for time-limited Right to Rent checks."
)

EVIDENCE_MODE_DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
EVIDENCE_MODE_STRUCTURED_DECLARATION = "STRUCTURED_DECLARATION"

# Landlord registration–style obligations: structured registration details + optional supporting document.
REGISTRATION_TRACKING_WORKFLOW = "REGISTRATION_TRACKING"
REGISTRATION_TRACKING_REQUIREMENT_CODES = frozenset(
    {
        "landlord_registration",
        "scotland_landlord_registration",
        "landlord_registration_ni",
        "rent_smart_wales",
    }
)

# England & Wales How to Rent — structured delivery record + supporting proof (Phase 1).
TENANT_DELIVERY_WORKFLOW = "TENANT_DELIVERY"
# England Right to Rent — structured check record + supporting documents (Phase 1).
GUIDED_DECLARATION_WORKFLOW = "GUIDED_DECLARATION"
EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW = "EXTERNAL_ASSESSMENT_EVIDENCE"
EVIDENCE_MODE_CONTRACTOR_CONFIRMATION = "CONTRACTOR_CONFIRMATION"
EVIDENCE_MODE_INSPECTION_CHECKLIST = "INSPECTION_CHECKLIST"

ALL_EVIDENCE_MODES = frozenset(
    {
        EVIDENCE_MODE_DOCUMENT_UPLOAD,
        EVIDENCE_MODE_STRUCTURED_DECLARATION,
        EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
        EVIDENCE_MODE_INSPECTION_CHECKLIST,
    }
)

VERIFICATION_PENDING = "PENDING_REVIEW"
VERIFICATION_VERIFIED = "VERIFIED"
VERIFICATION_REJECTED = "REJECTED"
VERIFICATION_NOT_REQUIRED = "NOT_REQUIRED"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"
DEFAULT_ALLOWED_SUPPORTING_UPLOAD_TYPES = [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
]

# How to Rent — structured delivery fields (England & Wales leaflet duty; planner applicability governs exposure).
_HOW_TO_RENT_DELIVERY_SCHEMA: List[Dict[str, Any]] = [
    {"id": "tenancy_start_date", "label": "Tenancy start date", "answer_type": "DATE", "required": True},
    {
        "id": "guide_version_or_publication_date",
        "label": "Guide version or publication (date, edition, or description if date unknown)",
        "answer_type": "TEXT",
        "required": True,
    },
    {"id": "delivery_date", "label": "Delivery date", "answer_type": "DATE", "required": True},
    {
        "id": "delivery_method",
        "label": "Delivery method",
        "answer_type": "SELECT",
        "required": True,
        "choices": [
            {"value": "email", "label": "Email"},
            {"value": "hand_delivery", "label": "Hand delivery"},
            {"value": "post", "label": "Post"},
            {"value": "tenant_portal", "label": "Tenant portal"},
            {"value": "other", "label": "Other"},
        ],
    },
    {
        "id": "tenant_recipient",
        "label": "Tenant / recipient (name or description)",
        "answer_type": "TEXT",
        "required": True,
    },
    {
        "id": "proof_of_delivery",
        "label": "Proof of delivery — reference or notes (optional; attach a file using Upload delivery proof)",
        "answer_type": "TEXT",
        "required": False,
    },
    {
        "id": "declaration_confirmed",
        "label": "I confirm this delivery information is accurate to the best of my knowledge",
        "answer_type": "YES_NO",
        "required": True,
    },
]

# Right to Rent (England) — structured check record; `right_to_rent_checks` resolves via the same defaults.
_RIGHT_TO_RENT_CHECK_SCHEMA: List[Dict[str, Any]] = [
    {"id": "tenant_name", "label": "Tenant / occupier checked (name)", "answer_type": "TEXT", "required": True},
    {"id": "check_date", "label": "Check date", "answer_type": "DATE", "required": True},
    {
        "id": "document_type",
        "label": "Document type used for the check",
        "answer_type": "SELECT",
        "required": True,
        "choices": [
            {"value": "passport", "label": "Passport"},
            {"value": "biometric_residence_permit", "label": "Biometric residence permit"},
            {"value": "online_check_share_code", "label": "Home Office online check (share code)"},
            {"value": "driving_licence", "label": "Driving licence (where acceptable)"},
            {"value": "other", "label": "Other (describe in notes if needed)"},
        ],
    },
    {
        "id": "document_reference",
        "label": "Document reference (optional — e.g. share code, redacted ID reference)",
        "answer_type": "TEXT",
        "required": False,
    },
    {
        "id": "right_to_rent_status",
        "label": "Right to Rent outcome recorded",
        "answer_type": "SELECT",
        "required": True,
        "choices": [
            {"value": "unlimited", "label": "Unlimited right to rent"},
            {"value": "time_limited", "label": "Time-limited right to rent"},
            {"value": "not_verified", "label": "Not verified / no acceptable proof on file"},
        ],
    },
    {
        "id": "follow_up_required",
        "label": "Follow-up required (e.g. before permission ends)",
        "answer_type": "YES_NO",
        "required": True,
    },
    {
        "id": "follow_up_date",
        "label": "Follow-up date (if applicable)",
        "answer_type": "DATE",
        "required": False,
    },
    {
        "id": "declaration_confirmed",
        "label": "I confirm this check record is accurate to the best of my knowledge",
        "answer_type": "YES_NO",
        "required": True,
    },
]

# Client/API metadata: conditional structured-declaration rules (evaluated by modal + enforced for R2R on POST).
_RIGHT_TO_RENT_STRUCTURED_DECLARATION_CONDITIONAL_RULES: List[Dict[str, Any]] = [
    {
        "id": "follow_up_date_when_time_limited_or_follow_up",
        "when_any": [
            {"field": "right_to_rent_status", "equals": "time_limited"},
            {"field": "follow_up_required", "equals": True},
        ],
        "require_non_empty_fields": ["follow_up_date"],
        "message": RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE,
    },
]

# Tenancy deposit — Phase 1: protection + prescribed information in one structured record (UK applicability unchanged).
_DEPOSIT_COMPLIANCE_SCHEMA: List[Dict[str, Any]] = [
    {
        "id": "deposit_taken",
        "label": "Deposit taken from tenant",
        "answer_type": "YES_NO",
        "required": True,
    },
    {
        "id": "deposit_amount",
        "label": "Deposit amount",
        "answer_type": "TEXT",
        "required": False,
    },
    {
        "id": "deposit_received_date",
        "label": "Deposit received date",
        "answer_type": "DATE",
        "required": False,
    },
    {
        "id": "scheme_name",
        "label": "Protection scheme name",
        "answer_type": "TEXT",
        "required": False,
    },
    {
        "id": "scheme_reference",
        "label": "Scheme / custodial reference",
        "answer_type": "TEXT",
        "required": False,
    },
    {
        "id": "protection_date",
        "label": "Date deposit protected in scheme",
        "answer_type": "DATE",
        "required": False,
    },
    {
        "id": "protection_confirmed",
        "label": "I confirm the deposit is protected in an approved scheme as described",
        "answer_type": "YES_NO",
        "required": False,
    },
    {
        "id": "prescribed_information_served",
        "label": "Prescribed information served on the tenant",
        "answer_type": "YES_NO",
        "required": True,
    },
    {
        "id": "prescribed_information_served_date",
        "label": "Date prescribed information was served",
        "answer_type": "DATE",
        "required": False,
    },
    {
        "id": "served_to",
        "label": "Served to (tenant name or description)",
        "answer_type": "TEXT",
        "required": False,
    },
    {
        "id": "service_method",
        "label": "How prescribed information was served",
        "answer_type": "SELECT",
        "required": False,
        "choices": [
            {"value": "email", "label": "Email"},
            {"value": "hand_delivery", "label": "Hand delivery"},
            {"value": "post", "label": "Post"},
            {"value": "tenant_portal", "label": "Tenant portal"},
            {"value": "other", "label": "Other"},
        ],
    },
    {
        "id": "proof_of_service",
        "label": "Proof of service — reference or notes (optional; you can also upload a file below)",
        "answer_type": "TEXT",
        "required": False,
    },
    {
        "id": "declaration_confirmed",
        "label": "I confirm this deposit compliance record is accurate to the best of my knowledge",
        "answer_type": "YES_NO",
        "required": True,
    },
]

DEPOSIT_STRUCTURED_DECLARATION_INVALID = "DEPOSIT_STRUCTURED_DECLARATION_INVALID"
DEPOSIT_DECLARATION_CONFIRMATION_REQUIRED_MESSAGE = (
    "Confirm that your deposit compliance declaration is accurate to continue."
)
DEPOSIT_PROTECTION_FIELD_REQUIRED_MESSAGE = "Complete all deposit protection fields when a deposit is taken."
DEPOSIT_PROTECTION_CONFIRM_REQUIRED_MESSAGE = (
    "Confirm that the deposit is protected in an approved scheme when a deposit is taken."
)
DEPOSIT_PRESCRIBED_INFO_FIELD_REQUIRED_MESSAGE = (
    "Complete prescribed information service details when you confirm information was served."
)

# Wales occupation contract — Phase 1 guided declaration + supporting upload (Wales-only duty).
_WALES_OCCUPATION_CONTRACT_SCHEMA: List[Dict[str, Any]] = [
    {
        "id": "contract_type",
        "label": "Contract type",
        "answer_type": "TEXT",
        "required": False,
    },
    {
        "id": "occupation_contract_issued",
        "label": "Occupation contract issued to contract-holder",
        "answer_type": "YES_NO",
        "required": True,
    },
    {
        "id": "issue_date",
        "label": "Issue date",
        "answer_type": "DATE",
        "required": False,
    },
    {
        "id": "contract_holder_name",
        "label": "Contract-holder name",
        "answer_type": "TEXT",
        "required": False,
    },
    {
        "id": "service_method",
        "label": "How the occupation contract was provided",
        "answer_type": "SELECT",
        "required": False,
        "choices": [
            {"value": "email", "label": "Email"},
            {"value": "hand_delivery", "label": "Hand delivery"},
            {"value": "post", "label": "Post"},
            {"value": "tenant_portal", "label": "Tenant portal"},
            {"value": "other", "label": "Other"},
        ],
    },
    {
        "id": "proof_reference",
        "label": "Proof reference (optional)",
        "answer_type": "TEXT",
        "required": False,
    },
    {
        "id": "declaration_confirmed",
        "label": "I confirm this Wales occupation contract record is accurate to the best of my knowledge",
        "answer_type": "YES_NO",
        "required": True,
    },
]

WALES_OCCUPATION_CONTRACT_STRUCTURED_DECLARATION_INVALID = "WALES_OCCUPATION_CONTRACT_STRUCTURED_DECLARATION_INVALID"
WALES_OCCUPATION_CONTRACT_DECLARATION_REQUIRED_MESSAGE = (
    "Confirm that your Wales occupation contract declaration is accurate to continue."
)
WALES_OCCUPATION_CONTRACT_ISSUED_FIELD_REQUIRED_MESSAGE = (
    "Complete issue date, contract-holder name, and service method when the occupation contract is issued."
)
LEGIONELLA_DECLARATION_REQUIRED = "LEGIONELLA_DECLARATION_REQUIRED"
LEGIONELLA_ASSESSMENT_DATE_REQUIRED = "LEGIONELLA_ASSESSMENT_DATE_REQUIRED"
LEGIONELLA_RISK_LEVEL_REQUIRED = "LEGIONELLA_RISK_LEVEL_REQUIRED"
LEGIONELLA_CONTROL_MEASURES_REQUIRED = "LEGIONELLA_CONTROL_MEASURES_REQUIRED"
LEGIONELLA_ACTIONS_REQUIRED = "LEGIONELLA_ACTIONS_REQUIRED"
LEGIONELLA_NEXT_REVIEW_REQUIRED = "LEGIONELLA_NEXT_REVIEW_REQUIRED"
LEGIONELLA_DECLARATION_REQUIRED_MESSAGE = "Confirm that your Legionella assessment declaration is accurate to continue."
LEGIONELLA_ASSESSMENT_DATE_REQUIRED_MESSAGE = "Enter the assessment date when an assessment is completed."
LEGIONELLA_RISK_LEVEL_REQUIRED_MESSAGE = "Select the Legionella risk level for the completed assessment."
LEGIONELLA_CONTROL_MEASURES_REQUIRED_MESSAGE = "Confirm whether control measures are in place for the completed assessment."
LEGIONELLA_ACTIONS_REQUIRED_MESSAGE = "Confirm whether follow-up actions are required for the completed assessment."
LEGIONELLA_NEXT_REVIEW_REQUIRED_MESSAGE = "Enter the next review date when actions are required."

_LEGIONELLA_SCHEMA: List[Dict[str, Any]] = [
    {"id": "assessment_completed", "label": "Assessment completed", "answer_type": "YES_NO", "required": True},
    {"id": "assessment_date", "label": "Assessment date", "answer_type": "DATE", "required": True},
    {
        "id": "assessor_type",
        "label": "Assessor type",
        "answer_type": "SELECT",
        "required": True,
        "choices": [
            {"value": "self", "label": "Self"},
            {"value": "external", "label": "External"},
        ],
    },
    {"id": "assessor_name", "label": "Assessor name (optional)", "answer_type": "TEXT", "required": False},
    {
        "id": "risk_level",
        "label": "Risk level",
        "answer_type": "SELECT",
        "required": True,
        "choices": [
            {"value": "low", "label": "Low"},
            {"value": "medium", "label": "Medium"},
            {"value": "high", "label": "High"},
        ],
    },
    {"id": "control_measures_in_place", "label": "Control measures in place", "answer_type": "YES_NO", "required": True},
    {"id": "actions_required", "label": "Actions required", "answer_type": "YES_NO", "required": True},
    {"id": "next_review_date", "label": "Next review date", "answer_type": "DATE", "required": False},
    {
        "id": "declaration_confirmed",
        "label": "I confirm this Legionella assessment record is accurate to the best of my knowledge",
        "answer_type": "YES_NO",
        "required": True,
    },
]

# Product defaults until registry publishes explicit evidence_resolution (policy data, not UI).
DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE: Dict[str, Dict[str, Any]] = {
    "smoke_heat_alarms": {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
            EVIDENCE_MODE_STRUCTURED_DECLARATION,
            EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
            EVIDENCE_MODE_INSPECTION_CHECKLIST,
        ],
        "primary_resolution_workflow": "GUIDED_EVIDENCE_RESOLUTION",
        "guided_primary_cta_label": "Add compliance evidence",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
    },
    "right_to_rent": {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_STRUCTURED_DECLARATION,
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
        ],
        "primary_resolution_workflow": GUIDED_DECLARATION_WORKFLOW,
        "guided_primary_cta_label": "Record Right to Rent check",
        "modal_title": "Record Right to Rent check",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
        "supporting_upload_recommended": True,
        "client_evidence_disclosure": (
            "This records your Right to Rent check details for review on the platform. "
            "It is not Home Office verification and does not replace legal advice or statutory processes."
        ),
        "checklist_schema_by_mode": {
            EVIDENCE_MODE_STRUCTURED_DECLARATION: list(_RIGHT_TO_RENT_CHECK_SCHEMA),
        },
        "structured_declaration_conditional_rules": list(_RIGHT_TO_RENT_STRUCTURED_DECLARATION_CONDITIONAL_RULES),
    },
    "hmo_fire_risk": {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
            EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
            EVIDENCE_MODE_INSPECTION_CHECKLIST,
        ],
        "primary_resolution_workflow": "GUIDED_EVIDENCE_RESOLUTION",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
    },
    "hmo_fire_risk_evidence": {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
            EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
            EVIDENCE_MODE_INSPECTION_CHECKLIST,
        ],
        "primary_resolution_workflow": "GUIDED_EVIDENCE_RESOLUTION",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
    },
    "legionella": {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_STRUCTURED_DECLARATION,
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
        ],
        "primary_resolution_workflow": EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW,
        "guided_primary_cta_label": "Record Legionella risk assessment",
        "guided_secondary_upload_label": "Upload assessment report",
        "modal_title": "Record Legionella risk assessment",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
        "supporting_upload_recommended": True,
        "client_evidence_disclosure": (
            "This records your Legionella risk assessment for compliance tracking. "
            "It does not replace professional or legal verification."
        ),
        "checklist_schema_by_mode": {
            EVIDENCE_MODE_STRUCTURED_DECLARATION: list(_LEGIONELLA_SCHEMA),
        },
    },
    "how_to_rent": {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_STRUCTURED_DECLARATION,
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
        ],
        "primary_resolution_workflow": TENANT_DELIVERY_WORKFLOW,
        "guided_primary_cta_label": "Record How to Rent delivery",
        "modal_title": "Record How to Rent delivery",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
        "supporting_upload_recommended": True,
        "client_evidence_disclosure": (
            "This records your How to Rent delivery details for review on the platform. "
            "It does not verify service with government or a court, and does not replace legal advice."
        ),
        "checklist_schema_by_mode": {
            EVIDENCE_MODE_STRUCTURED_DECLARATION: list(_HOW_TO_RENT_DELIVERY_SCHEMA),
        },
    },
    "deposit_pi": {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_STRUCTURED_DECLARATION,
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
        ],
        "primary_resolution_workflow": GUIDED_DECLARATION_WORKFLOW,
        "guided_primary_cta_label": "Record deposit compliance",
        "guided_secondary_upload_label": "Upload deposit evidence",
        "modal_title": "Record deposit compliance",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
        "supporting_upload_recommended": True,
        "client_evidence_disclosure": (
            "This records your tenancy deposit protection and prescribed information details for review on the platform. "
            "It is not legal verification, scheme validation, or a substitute for legal advice."
        ),
        "checklist_schema_by_mode": {
            EVIDENCE_MODE_STRUCTURED_DECLARATION: list(_DEPOSIT_COMPLIANCE_SCHEMA),
        },
    },
    "wales_occupation_contract": {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_STRUCTURED_DECLARATION,
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
        ],
        "primary_resolution_workflow": GUIDED_DECLARATION_WORKFLOW,
        "guided_primary_cta_label": "Record Wales occupation contract",
        "guided_secondary_upload_label": "Upload occupation contract",
        "modal_title": "Record Wales occupation contract",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
        "supporting_upload_recommended": True,
        "client_evidence_disclosure": (
            "This records Wales occupation contract evidence for review on the platform. "
            "It does not represent legal verification or replace legal advice."
        ),
        "checklist_schema_by_mode": {
            EVIDENCE_MODE_STRUCTURED_DECLARATION: list(_WALES_OCCUPATION_CONTRACT_SCHEMA),
        },
    },
}

# Registration tracking defaults (per slug copy — safe for independent published-registry overrides).
_REG_TRACK_DECLARATION_SCHEMA: List[Dict[str, Any]] = [
    {
        "id": "registration_number",
        "label": "Registration number",
        "answer_type": "TEXT",
        "required": True,
    },
    {
        "id": "issuing_authority",
        "label": "Issuing authority",
        "answer_type": "TEXT",
        "required": True,
    },
    {
        "id": "issue_date",
        "label": "Issue date",
        "answer_type": "DATE",
        "required": False,
    },
    {
        "id": "expiry_date",
        "label": "Expiry date (if applicable)",
        "answer_type": "DATE",
        "required": False,
    },
    {
        "id": "registration_status",
        "label": "Registration status (active / pending / expired / unknown)",
        "answer_type": "TEXT",
        "required": True,
    },
    {
        "id": "declaration_confirmed",
        "label": "I confirm these registration details are accurate",
        "answer_type": "YES_NO",
        "required": True,
    },
]

for _reg_slug in REGISTRATION_TRACKING_REQUIREMENT_CODES:
    DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE[_reg_slug] = {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_STRUCTURED_DECLARATION,
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
        ],
        "primary_resolution_workflow": REGISTRATION_TRACKING_WORKFLOW,
        "guided_primary_cta_label": "Record registration details",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
        "supporting_upload_recommended": True,
        "checklist_schema_by_mode": {
            EVIDENCE_MODE_STRUCTURED_DECLARATION: list(_REG_TRACK_DECLARATION_SCHEMA),
        },
    }


def _norm_modes_list(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for x in raw:
        s = str(x or "").strip().upper()
        if s and s in ALL_EVIDENCE_MODES:
            out.append(s)
    return out


def _structured_field_answer(structured_fields: Optional[Dict[str, Any]], field_id: str) -> Any:
    if not isinstance(structured_fields, dict):
        return None
    row = structured_fields.get(field_id)
    if isinstance(row, dict):
        return row.get("answer")
    return None


def _truthy_yes_answer(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().upper() in ("YES", "TRUE", "1", "Y")
    return False


def validate_right_to_rent_structured_declaration_fields(
    structured_fields: Optional[Dict[str, Any]],
) -> Optional[str]:
    """
    Phase 1.1: require follow_up_date when status is time-limited or follow-up is required.
    Applies only to ``right_to_rent`` / ``right_to_rent_checks`` (canonical) — not other declarations.
    """
    status = str(_structured_field_answer(structured_fields, "right_to_rent_status") or "").strip().lower()
    follow_req = _truthy_yes_answer(_structured_field_answer(structured_fields, "follow_up_required"))
    need_date = status == "time_limited" or follow_req
    if not need_date:
        return None
    fu = _structured_field_answer(structured_fields, "follow_up_date")
    if fu is None:
        return RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE
    if isinstance(fu, str) and not fu.strip():
        return RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE
    return None


def _non_empty_structured_answer(structured_fields: Optional[Dict[str, Any]], field_id: str) -> bool:
    v = _structured_field_answer(structured_fields, field_id)
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return True
    return True


def validate_deposit_structured_declaration_fields(
    structured_fields: Optional[Dict[str, Any]],
) -> Optional[str]:
    """
    Phase 1 deposit guided declaration — conditional required fields. For new structured submissions only
    (POST); legacy document-only evidence is unchanged.
    """
    if not _truthy_yes_answer(_structured_field_answer(structured_fields, "declaration_confirmed")):
        return DEPOSIT_DECLARATION_CONFIRMATION_REQUIRED_MESSAGE
    deposit_taken = _truthy_yes_answer(_structured_field_answer(structured_fields, "deposit_taken"))
    if deposit_taken:
        for fid in (
            "deposit_amount",
            "deposit_received_date",
            "scheme_name",
            "scheme_reference",
            "protection_date",
        ):
            if not _non_empty_structured_answer(structured_fields, fid):
                return DEPOSIT_PROTECTION_FIELD_REQUIRED_MESSAGE
        if not _truthy_yes_answer(_structured_field_answer(structured_fields, "protection_confirmed")):
            return DEPOSIT_PROTECTION_CONFIRM_REQUIRED_MESSAGE
    served = _truthy_yes_answer(_structured_field_answer(structured_fields, "prescribed_information_served"))
    if served:
        for fid in ("prescribed_information_served_date", "served_to", "service_method"):
            if not _non_empty_structured_answer(structured_fields, fid):
                return DEPOSIT_PRESCRIBED_INFO_FIELD_REQUIRED_MESSAGE
    return None


def validate_wales_occupation_contract_structured_declaration_fields(
    structured_fields: Optional[Dict[str, Any]],
) -> Optional[str]:
    """
    Phase 1 Wales occupation contract — conditional required fields on new structured submissions.
    """
    if not _truthy_yes_answer(_structured_field_answer(structured_fields, "declaration_confirmed")):
        return WALES_OCCUPATION_CONTRACT_DECLARATION_REQUIRED_MESSAGE
    issued = _truthy_yes_answer(_structured_field_answer(structured_fields, "occupation_contract_issued"))
    if issued:
        for fid in ("issue_date", "contract_holder_name", "service_method"):
            if not _non_empty_structured_answer(structured_fields, fid):
                return WALES_OCCUPATION_CONTRACT_ISSUED_FIELD_REQUIRED_MESSAGE
    return None


def validate_legionella_structured_declaration_fields(
    structured_fields: Optional[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    if not _truthy_yes_answer(_structured_field_answer(structured_fields, "declaration_confirmed")):
        return {"code": LEGIONELLA_DECLARATION_REQUIRED, "message": LEGIONELLA_DECLARATION_REQUIRED_MESSAGE}

    assessment_completed = _truthy_yes_answer(_structured_field_answer(structured_fields, "assessment_completed"))
    if assessment_completed:
        if not _non_empty_structured_answer(structured_fields, "assessment_date"):
            return {"code": LEGIONELLA_ASSESSMENT_DATE_REQUIRED, "message": LEGIONELLA_ASSESSMENT_DATE_REQUIRED_MESSAGE}
        if not _non_empty_structured_answer(structured_fields, "risk_level"):
            return {"code": LEGIONELLA_RISK_LEVEL_REQUIRED, "message": LEGIONELLA_RISK_LEVEL_REQUIRED_MESSAGE}
        if _structured_field_answer(structured_fields, "control_measures_in_place") is None:
            return {
                "code": LEGIONELLA_CONTROL_MEASURES_REQUIRED,
                "message": LEGIONELLA_CONTROL_MEASURES_REQUIRED_MESSAGE,
            }
        if _structured_field_answer(structured_fields, "actions_required") is None:
            return {"code": LEGIONELLA_ACTIONS_REQUIRED, "message": LEGIONELLA_ACTIONS_REQUIRED_MESSAGE}

    actions_required = _truthy_yes_answer(_structured_field_answer(structured_fields, "actions_required"))
    if actions_required and not _non_empty_structured_answer(structured_fields, "next_review_date"):
        return {"code": LEGIONELLA_NEXT_REVIEW_REQUIRED, "message": LEGIONELLA_NEXT_REVIEW_REQUIRED_MESSAGE}
    return None


def _norm_structured_declaration_conditional_rules(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        iid = str(item.get("id") or "").strip()
        msg = str(item.get("message") or "").strip()
        when_any = item.get("when_any")
        req = item.get("require_non_empty_fields")
        if not iid or not msg or not isinstance(when_any, list) or not isinstance(req, list):
            continue
        wn: List[Dict[str, Any]] = []
        for w in when_any:
            if not isinstance(w, dict):
                continue
            f = str(w.get("field") or "").strip()
            if not f:
                continue
            wn.append({"field": f, "equals": w.get("equals")})
        rfs = [str(x).strip() for x in req if str(x).strip()]
        if wn and rfs:
            out.append({"id": iid, "when_any": wn, "require_non_empty_fields": rfs, "message": msg})
    return out


def normalize_evidence_resolution_dict(er: Dict[str, Any]) -> Dict[str, Any]:
    modes = _norm_modes_list(er.get("allowed_evidence_modes"))
    if not modes:
        modes = [EVIDENCE_MODE_DOCUMENT_UPLOAD]
    out: Dict[str, Any] = {
        "allowed_evidence_modes": modes,
        "primary_resolution_workflow": str(er.get("primary_resolution_workflow") or "").strip()
        or "GUIDED_EVIDENCE_RESOLUTION",
        "allow_medium_non_document_satisfaction": bool(er.get("allow_medium_non_document_satisfaction")),
        "allow_low_non_document_satisfaction": bool(er.get("allow_low_non_document_satisfaction")),
        "supporting_upload_required": bool(er.get("supporting_upload_required")),
        "supporting_upload_recommended": bool(er.get("supporting_upload_recommended")),
        "allowed_upload_types": _norm_upload_types(er.get("allowed_upload_types")),
        "checklist_schema_by_mode": _norm_checklist_schema_by_mode(er.get("checklist_schema_by_mode")),
        "verification_required": bool(er.get("verification_required")),
    }
    rrr = str(er.get("reviewer_role_required") or "").strip()
    if rrr:
        out["reviewer_role_required"] = rrr
    gpl = str(er.get("guided_primary_cta_label") or "").strip()
    if gpl:
        out["guided_primary_cta_label"] = gpl
    mt = str(er.get("modal_title") or "").strip()
    if mt:
        out["modal_title"] = mt
    ced = str(er.get("client_evidence_disclosure") or "").strip()
    if ced:
        out["client_evidence_disclosure"] = ced
    gsl = str(er.get("guided_secondary_upload_label") or "").strip()
    if gsl:
        out["guided_secondary_upload_label"] = gsl
    nrules = _norm_structured_declaration_conditional_rules(er.get("structured_declaration_conditional_rules"))
    if nrules:
        out["structured_declaration_conditional_rules"] = nrules
    return out


# Single source for guided selector copy (API + docs). Keys are ALL_EVIDENCE_MODES values.
GUIDED_EVIDENCE_MODE_UI_COPY: Dict[str, Dict[str, str]] = {
    EVIDENCE_MODE_DOCUMENT_UPLOAD: {
        "label": "Upload evidence document",
        "description": "Best for certificates, reports, licences, or official records.",
        "typical_confidence": "High when verified.",
        "verification_note": "Documents are reviewed before they can satisfy compliance.",
    },
    EVIDENCE_MODE_STRUCTURED_DECLARATION: {
        "label": "Submit compliance declaration",
        "description": "Use when compliance is confirmed by a structured signed declaration.",
        "typical_confidence": "Medium or low depending on supporting detail.",
        "verification_note": "Declarations are reviewed before they can satisfy compliance.",
    },
    EVIDENCE_MODE_CONTRACTOR_CONFIRMATION: {
        "label": "Add contractor confirmation",
        "description": "Use when a contractor or competent person has completed relevant work.",
        "typical_confidence": "Medium to high depending on detail.",
        "verification_note": "Confirmations are reviewed before they can satisfy compliance.",
    },
    EVIDENCE_MODE_INSPECTION_CHECKLIST: {
        "label": "Complete inspection checklist",
        "description": "Use when the obligation is evidenced by a structured inspection record.",
        "typical_confidence": "Medium.",
        "verification_note": "Checklists are reviewed before they can satisfy compliance.",
    },
}


def guided_method_ui_rows_for_modes(modes: Sequence[str]) -> List[Dict[str, Any]]:
    """Rich rows for GET evidence-resolution and clients (one source of truth for copy)."""
    rows: List[Dict[str, Any]] = []
    for m in modes or []:
        tok = str(m or "").strip().upper()
        if not tok or tok not in ALL_EVIDENCE_MODES:
            continue
        base = GUIDED_EVIDENCE_MODE_UI_COPY.get(tok, {})
        rows.append(
            {
                "evidence_mode": tok,
                "label": base.get("label") or tok.replace("_", " ").title(),
                "description": base.get("description") or "",
                "typical_confidence": base.get("typical_confidence") or "",
                "verification_note": base.get("verification_note") or "",
            }
        )
    return rows


def _norm_upload_types(raw: Any) -> List[str]:
    out: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            tok = str(item or "").strip().lower()
            if tok:
                out.append(tok)
    if out:
        return out
    return list(DEFAULT_ALLOWED_SUPPORTING_UPLOAD_TYPES)


def _norm_checklist_schema_by_mode(raw: Any) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    if not isinstance(raw, dict):
        return out
    for mode, rows in raw.items():
        mode_tok = str(mode or "").strip().upper()
        if mode_tok not in ALL_EVIDENCE_MODES:
            continue
        if not isinstance(rows, list):
            continue
        normal_rows: List[Dict[str, Any]] = []
        for idx, r in enumerate(rows):
            if not isinstance(r, dict):
                continue
            qid = str(r.get("id") or f"{mode_tok.lower()}_{idx+1}").strip()
            label = str(r.get("label") or "").strip()
            answer_type = str(r.get("answer_type") or "YES_NO").strip().upper()
            if not label:
                continue
            if answer_type not in {"YES_NO", "PASS_FAIL", "TEXT", "NUMERIC", "OBSERVATION", "DATE", "SELECT"}:
                answer_type = "YES_NO"
            row_dict: Dict[str, Any] = {
                "id": qid,
                "label": label,
                "answer_type": answer_type,
                "required": bool(r.get("required")),
            }
            if answer_type == "SELECT":
                choices_raw = r.get("choices") if isinstance(r.get("choices"), list) else []
                norm_choices: List[Dict[str, str]] = []
                for c in choices_raw:
                    if not isinstance(c, dict):
                        continue
                    v = str(c.get("value") or "").strip()
                    if not v:
                        continue
                    norm_choices.append(
                        {"value": v, "label": str(c.get("label") or "").strip() or v},
                    )
                row_dict["choices"] = norm_choices
            normal_rows.append(row_dict)
        if normal_rows:
            out[mode_tok] = normal_rows
    return out


def _default_evidence_resolution_lookup_keys(requirement_type: str, requirement_code: str) -> List[str]:
    """Try canonical storage slug first (alias normalization), then raw slug (read-time only)."""
    keys: List[str] = []
    seen: set[str] = set()
    for raw in (requirement_type, requirement_code):
        raw = str(raw or "").strip()
        if not raw:
            continue
        n = normalize_requirement_code(raw)
        candidates = []
        if n:
            candidates.append(n)
        slug = raw.lower().replace(" ", "_")
        if slug and slug not in candidates:
            candidates.append(slug)
        for k in candidates:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    return keys


def effective_evidence_resolution(requirement: Dict[str, Any]) -> Dict[str, Any]:
    meta = requirement.get("registry_metadata") if isinstance(requirement.get("registry_metadata"), dict) else {}
    er = meta.get("evidence_resolution")
    if isinstance(er, dict) and _norm_modes_list(er.get("allowed_evidence_modes")):
        return normalize_evidence_resolution_dict(er)
    rt = str(requirement.get("requirement_type") or "").strip()
    rc = str(requirement.get("requirement_code") or "").strip()
    for key in _default_evidence_resolution_lookup_keys(rt, rc):
        if key in DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE:
            return normalize_evidence_resolution_dict(DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE[key])
    # Wales-only safe aliasing for legacy/storage variants: occupation_contract uses Wales policy only in Wales context.
    occ_slug = (normalize_requirement_code(rt) or normalize_requirement_code(rc) or "").strip().lower()
    req_jur = str(requirement.get("jurisdiction") or requirement.get("property_jurisdiction") or "").strip().lower()
    if occ_slug == "occupation_contract" and req_jur == "wales":
        return normalize_evidence_resolution_dict(DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE["wales_occupation_contract"])
    return normalize_evidence_resolution_dict(
        {
            "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
            "primary_resolution_workflow": "LEGACY_DOCUMENT_UPLOAD",
            "allow_medium_non_document_satisfaction": False,
            "allow_low_non_document_satisfaction": False,
        }
    )


def checklist_schema_for_mode(requirement: Dict[str, Any], mode: str) -> Dict[str, Any]:
    policy = effective_evidence_resolution(requirement)
    mode_tok = str(mode or "").strip().upper()
    by_mode = policy.get("checklist_schema_by_mode") if isinstance(policy.get("checklist_schema_by_mode"), dict) else {}
    schema = by_mode.get(mode_tok) if isinstance(by_mode.get(mode_tok), list) else None
    if schema:
        return {"items": schema, "fallback_used": False}
    rt_raw = str(requirement.get("requirement_type") or requirement.get("requirement_code") or "").strip().lower()
    rt_eff = normalize_requirement_code(rt_raw) or rt_raw
    return {
        "items": _default_checklist_schema_for_requirement(rt_eff, mode_tok),
        "fallback_used": True,
    }


def _default_checklist_schema_for_requirement(requirement_type: str, mode: str) -> List[Dict[str, Any]]:
    if mode == EVIDENCE_MODE_INSPECTION_CHECKLIST and (
        requirement_type == "smoke_heat_alarms"
        or normalize_requirement_code(requirement_type) == "smoke_heat_alarms"
    ):
        return [
            {"id": "alarm_present", "label": "Alarm present in required location", "answer_type": "PASS_FAIL", "required": True},
            {"id": "alarm_tested", "label": "Alarm tested and operating", "answer_type": "PASS_FAIL", "required": True},
            {"id": "test_count", "label": "Number of alarms tested", "answer_type": "NUMERIC", "required": False},
            {"id": "observations", "label": "Observations", "answer_type": "OBSERVATION", "required": False},
        ]
    if mode == EVIDENCE_MODE_INSPECTION_CHECKLIST:
        return [
            {"id": "check_passed", "label": "Inspection checklist passed", "answer_type": "PASS_FAIL", "required": True},
            {"id": "notes", "label": "Inspection notes", "answer_type": "TEXT", "required": False},
            {"id": "observations", "label": "Observations", "answer_type": "OBSERVATION", "required": False},
        ]
    if mode == EVIDENCE_MODE_STRUCTURED_DECLARATION:
        return [
            {"id": "declaration_confirmed", "label": "I confirm this declaration is accurate", "answer_type": "YES_NO", "required": True},
            {"id": "supporting_summary", "label": "Supporting details", "answer_type": "TEXT", "required": False},
            {"id": "observations", "label": "Observations", "answer_type": "OBSERVATION", "required": False},
        ]
    return []


def evidence_mode_allowed_for_requirement(requirement: Dict[str, Any], mode: str) -> bool:
    policy = effective_evidence_resolution(requirement)
    m = str(mode or "").strip().upper()
    return m in set(policy.get("allowed_evidence_modes") or [])


def assign_confidence_for_new_record(
    *,
    evidence_mode: str,
    verification_status: str,
    payload: Dict[str, Any],
) -> str:
    """Initial confidence at creation time (may change after verification)."""
    mode = str(evidence_mode or "").strip().upper()
    vs = str(verification_status or "").strip().upper()
    if mode == EVIDENCE_MODE_DOCUMENT_UPLOAD:
        return CONFIDENCE_HIGH if vs == VERIFICATION_VERIFIED else CONFIDENCE_MEDIUM
    if mode == EVIDENCE_MODE_CONTRACTOR_CONFIRMATION:
        return CONFIDENCE_HIGH if vs == VERIFICATION_VERIFIED else CONFIDENCE_MEDIUM
    if mode == EVIDENCE_MODE_STRUCTURED_DECLARATION:
        if _structured_declaration_well_supported(payload):
            return CONFIDENCE_MEDIUM
        return CONFIDENCE_LOW
    if mode == EVIDENCE_MODE_INSPECTION_CHECKLIST:
        if _inspection_checklist_complete(payload):
            return CONFIDENCE_MEDIUM
        return CONFIDENCE_LOW
    return CONFIDENCE_MEDIUM


def _structured_declaration_well_supported(payload: Dict[str, Any]) -> bool:
    fields = payload.get("structured_fields") if isinstance(payload.get("structured_fields"), dict) else {}
    stmt = str(payload.get("declaration_statement") or "").strip()
    return len(stmt) >= 20 and len(fields) >= 1


def _inspection_checklist_complete(payload: Dict[str, Any]) -> bool:
    answers = payload.get("checklist_answers")
    if not isinstance(answers, dict) or not answers:
        return False
    return bool(str(payload.get("responsible_person") or "").strip()) and bool(
        str(payload.get("inspection_date") or "").strip()
    )


def recompute_confidence_for_record(rec: Dict[str, Any]) -> str:
    return assign_confidence_for_new_record(
        evidence_mode=str(rec.get("evidence_mode") or ""),
        verification_status=str(rec.get("verification_status") or ""),
        payload=rec.get("evidence_payload") if isinstance(rec.get("evidence_payload"), dict) else {},
    )


def active_sorted_evidence_candidates(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Non-archived, active compliance, not rejected — newest first within tiers."""
    active: List[Dict[str, Any]] = []
    for r in records or []:
        if not isinstance(r, dict):
            continue
        if r.get("archived") is True:
            continue
        if r.get("included_in_active_compliance") is False:
            continue
        if str(r.get("verification_status") or "").upper() == VERIFICATION_REJECTED:
            continue
        active.append(r)

    def tier(rec: Dict[str, Any]) -> Tuple[int, int, str]:
        vs = str(rec.get("verification_status") or "").upper()
        v_rank = 2 if vs == VERIFICATION_VERIFIED else (1 if vs == VERIFICATION_PENDING else 0)
        lvl = str(rec.get("evidence_confidence_level") or "").upper()
        c_rank = 3 if lvl == CONFIDENCE_HIGH else (2 if lvl == CONFIDENCE_MEDIUM else 1)
        ca = str(rec.get("created_at") or "")
        return (v_rank, c_rank, ca)

    active.sort(key=tier, reverse=True)
    return active


def non_document_record_satisfies_policy(
    *,
    record: Dict[str, Any],
    requirement: Dict[str, Any],
    policy: Dict[str, Any],
    is_critical_obligation: bool,
) -> bool:
    if str(record.get("verification_status") or "").upper() != VERIFICATION_VERIFIED:
        return False
    mode = str(record.get("evidence_mode") or "").upper()
    allowed = set(str(x).upper() for x in (policy.get("allowed_evidence_modes") or []) if x)
    if mode not in allowed:
        return False
    if mode == EVIDENCE_MODE_DOCUMENT_UPLOAD:
        return False
    level = str(record.get("evidence_confidence_level") or "").upper()
    if level == CONFIDENCE_HIGH:
        return True
    if level == CONFIDENCE_MEDIUM:
        if is_critical_obligation:
            return bool(policy.get("allow_medium_non_document_satisfaction"))
        return True
    if level == CONFIDENCE_LOW:
        if is_critical_obligation:
            return False
        return bool(policy.get("allow_low_non_document_satisfaction"))
    return False


def _evidence_coll(db: Any):
    """Motor accepts attribute access for this collection name."""
    return db.compliance_evidence_records


async def ensure_compliance_evidence_indexes(db) -> None:
    coll = _evidence_coll(db)
    await coll.create_index("evidence_record_id", unique=True)
    await coll.create_index([("client_id", 1), ("property_id", 1), ("requirement_id", 1)])
    await coll.create_index([("requirement_id", 1), ("archived", 1)])


async def batch_list_evidence_records_for_requirements(
    db,
    *,
    client_id: str,
    requirement_ids: List[str],
    include_archived: bool = False,
) -> Dict[str, List[Dict[str, Any]]]:
    """Map requirement_id -> evidence rows (read-only; used for completeness hints)."""
    if not requirement_ids:
        return {}
    q: Dict[str, Any] = {"client_id": client_id, "requirement_id": {"$in": list(set(requirement_ids))}}
    if not include_archived:
        q["archived"] = {"$ne": True}
    cur = _evidence_coll(db).find(q, {"_id": 0}).sort("created_at", -1).limit(2000)
    rows = await cur.to_list(2000)
    out: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for doc in rows:
        rid = doc.get("requirement_id")
        if rid:
            out[str(rid)].append(doc)
    return dict(out)


async def list_evidence_records_for_requirement(
    db,
    *,
    client_id: str,
    requirement_id: str,
    include_archived: bool = False,
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"client_id": client_id, "requirement_id": requirement_id}
    if not include_archived:
        q["archived"] = {"$ne": True}
    cur = _evidence_coll(db).find(q, {"_id": 0}).sort("created_at", -1).limit(500)
    return await cur.to_list(500)


async def create_compliance_evidence_record(
    db,
    *,
    requirement: Dict[str, Any],
    evidence_mode: str,
    created_by_user_id: str,
    evidence_payload: Dict[str, Any],
    linked_document_ids: Optional[List[str]] = None,
    verification_status: str = VERIFICATION_PENDING,
) -> Dict[str, Any]:
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

    mode = str(evidence_mode or "").strip().upper()
    if mode not in ALL_EVIDENCE_MODES or mode == EVIDENCE_MODE_DOCUMENT_UPLOAD:
        raise ValueError("invalid_evidence_mode_for_this_endpoint")

    client_id = str(requirement.get("client_id") or "")
    property_id = str(requirement.get("property_id") or "")
    req_id = str(requirement.get("requirement_id") or "")
    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    property_doc = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 0})
    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=[requirement],
        client_doc=client_doc,
        properties=[property_doc] if property_doc else [],
    )
    if not filtered:
        raise ValueError("requirement_not_eligible_for_runtime_evidence")

    if not evidence_mode_allowed_for_requirement(requirement, mode):
        raise ValueError("evidence_mode_not_allowed_for_requirement")

    vs = str(verification_status or "").strip().upper()
    if vs not in {VERIFICATION_PENDING, VERIFICATION_VERIFIED, VERIFICATION_NOT_REQUIRED}:
        raise ValueError("invalid_verification_status")

    if not isinstance(evidence_payload, dict):
        raise ValueError("evidence_payload_required")
    _validate_payload_for_mode(mode, evidence_payload)

    confidence = assign_confidence_for_new_record(
        evidence_mode=mode, verification_status=vs, payload=evidence_payload
    )
    now = datetime.now(timezone.utc).isoformat()
    eid = f"cer_{uuid.uuid4().hex}"
    doc = {
        "evidence_record_id": eid,
        "requirement_id": req_id,
        "client_id": client_id,
        "property_id": property_id,
        "evidence_mode": mode,
        "created_at": now,
        "created_by_user_id": created_by_user_id,
        "verification_status": vs,
        "verified_by_user_id": None,
        "verified_at": None,
        "evidence_confidence_level": confidence,
        "evidence_payload": evidence_payload,
        "linked_document_ids": [str(x) for x in (linked_document_ids or []) if x],
        "audit_metadata": {"created_via": "client_compliance_evidence_api"},
        "included_in_active_compliance": True,
        "archived": False,
        "archived_reason": None,
    }
    await _evidence_coll(db).insert_one(doc)
    out = {k: v for k, v in doc.items() if k != "_id"}
    return out


def _validate_payload_for_mode(mode: str, payload: Dict[str, Any]) -> None:
    if mode == EVIDENCE_MODE_STRUCTURED_DECLARATION:
        if not str(payload.get("declaration_statement") or "").strip():
            raise ValueError("declaration_statement_required")
        if not isinstance(payload.get("structured_fields"), dict):
            raise ValueError("structured_fields_object_required")
    elif mode == EVIDENCE_MODE_CONTRACTOR_CONFIRMATION:
        for k in ("contractor_name", "completion_date", "work_summary"):
            if not str(payload.get(k) or "").strip():
                raise ValueError(f"{k}_required")
        summary = str(payload.get("work_summary") or "").strip()
        if len(summary) < 8:
            raise ValueError("work_summary_too_short")
        payload["completion_date"] = _normalize_iso_date(payload.get("completion_date"), reject_future=True)
    elif mode == EVIDENCE_MODE_INSPECTION_CHECKLIST:
        raw_date = str(payload.get("inspection_date") or "").strip()
        if not raw_date:
            raise ValueError("inspection_date_required")
        payload["inspection_date"] = _normalize_iso_date(raw_date, reject_future=False)
        if not isinstance(payload.get("checklist_answers"), dict) or not payload.get("checklist_answers"):
            raise ValueError("checklist_answers_required")
        if not str(payload.get("responsible_person") or "").strip():
            raise ValueError("responsible_person_required")
        _validate_checklist_answers(payload.get("checklist_answers") or {})


def _validate_checklist_answers(answers: Dict[str, Any]) -> None:
    for key, val in answers.items():
        item_key = str(key or "").strip()
        if not item_key:
            raise ValueError("checklist_answer_key_invalid")
        if isinstance(val, bool):
            continue
        if isinstance(val, (int, float)):
            continue
        if isinstance(val, str):
            continue
        if isinstance(val, dict):
            ans = val.get("answer")
            if isinstance(ans, (bool, int, float, str)):
                continue
        raise ValueError("checklist_answer_value_invalid")


def _normalize_iso_date(value: Any, *, reject_future: bool) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("date_required")
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as e:
        try:
            dt = datetime.fromisoformat(f"{raw}T00:00:00+00:00")
        except ValueError:
            raise ValueError("invalid_date_format") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    today = datetime.now(timezone.utc).date()
    if reject_future and dt.date() > today:
        raise ValueError("date_cannot_be_in_future")
    return dt.date().isoformat()


async def apply_verification_decision(
    db,
    *,
    evidence_record_id: str,
    client_id: str,
    decision: str,
    actor_user_id: str,
) -> Optional[Dict[str, Any]]:
    decision_u = str(decision or "").strip().upper()
    if decision_u not in {"VERIFY", "REJECT"}:
        raise ValueError("invalid_decision")
    coll = _evidence_coll(db)
    existing = await coll.find_one({"evidence_record_id": evidence_record_id, "client_id": client_id}, {"_id": 0})
    if not existing:
        return None
    now = datetime.now(timezone.utc).isoformat()
    if decision_u == "VERIFY":
        new_status = VERIFICATION_VERIFIED
    else:
        new_status = VERIFICATION_REJECTED
    payload = existing.get("evidence_payload") if isinstance(existing.get("evidence_payload"), dict) else {}
    conf = assign_confidence_for_new_record(
        evidence_mode=str(existing.get("evidence_mode")),
        verification_status=new_status,
        payload=payload,
    )
    await coll.update_one(
        {"evidence_record_id": evidence_record_id, "client_id": client_id},
        {
            "$set": {
                "verification_status": new_status,
                "verified_by_user_id": actor_user_id,
                "verified_at": now,
                "evidence_confidence_level": conf,
            }
        },
    )
    out = {**existing, "verification_status": new_status, "verified_by_user_id": actor_user_id, "verified_at": now}
    out["evidence_confidence_level"] = conf
    return out


async def load_records_for_requirement_sync(db, requirement_id: str, client_id: str) -> List[Dict[str, Any]]:
    return await _evidence_coll(db).find(
        {"requirement_id": requirement_id, "client_id": client_id},
        {"_id": 0},
    ).to_list(500)


async def upsert_document_upload_evidence_for_linked_document(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_id: str,
    document_id: str,
    actor_user_id: Optional[str] = None,
    filename: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    When a document is stored with requirement_id, ensure a DOCUMENT_UPLOAD compliance_evidence_records
    row exists and references the document (idempotent per document_id).
    """
    doc_id = str(document_id or "").strip()
    rid = str(requirement_id or "").strip()
    cid = str(client_id or "").strip()
    if not doc_id or not rid or not cid:
        return None
    coll = _evidence_coll(db)
    existing = await coll.find_one(
        {
            "client_id": cid,
            "requirement_id": rid,
            "evidence_mode": EVIDENCE_MODE_DOCUMENT_UPLOAD,
            "linked_document_ids": doc_id,
            "archived": {"$ne": True},
        },
        {"_id": 0},
    )
    if existing:
        return existing
    requirement = await db.requirements.find_one({"requirement_id": rid, "client_id": cid}, {"_id": 0})
    if not requirement:
        return None
    pid = str(property_id or requirement.get("property_id") or "").strip()
    payload: Dict[str, Any] = {"document_id": doc_id, "source": "linked_document_upload"}
    if filename:
        payload["filename"] = str(filename)
    confidence = assign_confidence_for_new_record(
        evidence_mode=EVIDENCE_MODE_DOCUMENT_UPLOAD,
        verification_status=VERIFICATION_PENDING,
        payload=payload,
    )
    now = datetime.now(timezone.utc).isoformat()
    eid = f"cer_{uuid.uuid4().hex}"
    rec = {
        "evidence_record_id": eid,
        "requirement_id": rid,
        "client_id": cid,
        "property_id": pid,
        "evidence_mode": EVIDENCE_MODE_DOCUMENT_UPLOAD,
        "created_at": now,
        "created_by_user_id": str(actor_user_id or ""),
        "verification_status": VERIFICATION_PENDING,
        "verified_by_user_id": None,
        "verified_at": None,
        "evidence_confidence_level": confidence,
        "evidence_payload": payload,
        "linked_document_ids": [doc_id],
        "audit_metadata": {"created_via": "document_upload_normalization"},
        "included_in_active_compliance": True,
        "archived": False,
        "archived_reason": None,
    }
    await coll.insert_one(rec)
    return {k: v for k, v in rec.items() if k != "_id"}


async def safe_upsert_document_upload_evidence_for_linked_document(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_id: str,
    document_id: str,
    actor_user_id: Optional[str] = None,
    filename: Optional[str] = None,
    context: str = "document_link",
) -> None:
    """
    Same normalized DOCUMENT_UPLOAD evidence row as upsert_document_upload_evidence_for_linked_document,
    but swallows errors so upload/link flows never fail on evidence-record normalization.
    """
    try:
        await upsert_document_upload_evidence_for_linked_document(
            db,
            client_id=client_id,
            property_id=property_id,
            requirement_id=requirement_id,
            document_id=document_id,
            actor_user_id=actor_user_id,
            filename=filename,
        )
    except Exception as e:
        logger.warning(
            "DOCUMENT_UPLOAD evidence normalization skipped [%s] document_id=%s requirement_id=%s: %s",
            context,
            document_id,
            requirement_id,
            e,
        )
