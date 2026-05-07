"""
Machine-readable workflow behaviour governance (read-only).

Purpose: prevent accidental collapse of distinct obligation mechanics into a single
“upload document ⇒ compliant” mental model. Covers workflow classes, evidence/reporting
semantics, **execution & system-behaviour contracts** (recalculation / completion / audit
expectations — descriptive only), and additive audit flags. Does **not** enforce runtime
outcomes, alter scoring, wire engines to execution metadata, or substitute resolver/evidence
authority.

See docs/WORKFLOW_BEHAVIOUR_GOVERNANCE.md for human-readable policy.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, Optional

from services.compliance_evidence_record_service import (
    EVIDENCE_MODE_DOCUMENT_UPLOAD,
    EVIDENCE_MODE_STRUCTURED_DECLARATION,
)
from services.requirement_code_registry import normalize_requirement_code
from services.requirement_evidence_completeness import requirement_status_appears_satisfied_top_level

# --- Workflow class keys (aligned with requirement_workflow_audit WC_* strings) ---
WC_DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
WC_GUIDED_DECLARATION = "GUIDED_DECLARATION"
WC_TENANT_DELIVERY = "TENANT_DELIVERY"
WC_REGISTRATION_TRACKING = "REGISTRATION_TRACKING"
WC_EXTERNAL_ASSESSMENT_EVIDENCE = "EXTERNAL_ASSESSMENT_EVIDENCE"
WC_MULTI_EVIDENCE = "MULTI_EVIDENCE"
WC_GUIDANCE_ONLY = "GUIDANCE_ONLY"
# Presentation-derived: condition / active standards (fitness, repairing) — runtime workflow_class stays GUIDANCE_ONLY.
CONDITION_STANDARD_ACTIVE_STANDARD = "CONDITION_STANDARD_ACTIVE_STANDARD"

# Score impact taxonomy (descriptive; does not change scoring code paths).
SCORE_MODEL_DIRECT_CERTIFICATE = "direct_certificate"
SCORE_MODEL_DECLARATION_CONFIDENCE = "declaration_confidence"
SCORE_MODEL_DELIVERY_RECORD = "delivery_record"
SCORE_MODEL_REGISTRATION_RECORD = "registration_record"
SCORE_MODEL_ASSESSMENT_CONDITIONAL = "assessment_conditional"
SCORE_MODEL_MULTI_COMPONENT = "multi_component"
SCORE_MODEL_GUIDANCE_ONLY = "guidance_only"
SCORE_MODEL_OPERATIONAL_CONVERGENCE = "operational_convergence"

# Primary CTA families (resolver primary intent / kind — inferred client-side parity).
CTA_DOCUMENT_UPLOAD_PRIMARY = "DOCUMENT_UPLOAD_PRIMARY"
CTA_GUIDED_EVIDENCE_RESOLUTION = "GUIDED_EVIDENCE_RESOLUTION"
CTA_DIRECT_EVIDENCE_ACTION = "DIRECT_EVIDENCE_ACTION"
CTA_VIEW_GUIDANCE = "VIEW_GUIDANCE"
CTA_MAINTENANCE = "MAINTENANCE"
CTA_COORDINATE_INSPECTION = "COORDINATE_INSPECTION_EVIDENCE"
CTA_GUIDED_UNAVAILABLE = "GUIDED_EVIDENCE_UNAVAILABLE"

AUDIT_ROLE_CERTIFICATE_EVIDENCE = "certificate_style_evidence_of_record"
AUDIT_ROLE_STRUCTURED_DECLARATION = "structured_declaration_record"
AUDIT_ROLE_DELIVERY_PROOF = "tenant_delivery_record"
AUDIT_ROLE_REGISTRATION_RECORD = "registration_or_scheme_record"
AUDIT_ROLE_ASSESSMENT_AND_ACTIONS = "external_assessment_conditional_closure"
AUDIT_ROLE_COMPONENT_COMPLETENESS = "multi_component_completeness"
AUDIT_ROLE_INFORMATIONAL = "guidance_informational_only"
AUDIT_ROLE_OPERATIONAL_SIGNALS = "operational_convergence_and_remediation"

# Semantic governance (documentation / diagnostics only — not scoring authority).
UPLOAD_SUFFICIENCY_PRIMARY_AUTHORITATIVE = "primary_upload_may_authoritatively_close_obligation_where_registry_accepts"
UPLOAD_SUFFICIENCY_SUPPORTING_ONLY = "upload_supporting_only_not_sole_proof_of_obligation"
UPLOAD_SUFFICIENCY_NEVER_SOLE_STANDARD_CLOSURE = "upload_must_not_solely_close_condition_or_guidance_obligation"
UPLOAD_SUFFICIENCY_COMPONENTS_REQUIRED = "single_generic_upload_must_not_stand_in_for_all_components"

# Reporting surfaces (taxonomy for reporting_visibility — informational only; does not drive exports).
REPORT_SURFACE_COMPLIANCE_REPORTS = "compliance_reports"
REPORT_SURFACE_AUDIT_EXPORTS = "audit_exports"
REPORT_SURFACE_LENDER_TRIBUNAL_EXPORTS = "lender_tribunal_exports"
REPORT_SURFACE_OPERATIONAL_REMEDIATION_REPORTS = "operational_remediation_reports"
REPORT_SURFACE_RISK_SUMMARIES = "risk_summaries"
REPORT_SURFACE_EXPIRY_REPORTS = "expiry_reports"
REPORT_SURFACE_EVIDENCE_COMPLETENESS_REPORTS = "evidence_completeness_reports"

# --- Execution & system-behaviour contracts (governance / tooling only; engines must not consume yet) ---
COMPLETION_AUTHORITY_MAY_DIRECT_SATISFY = "MAY_DIRECT_SATISFY"
COMPLETION_AUTHORITY_MAY_SATISFY_CONDITIONAL = "MAY_SATISFY_CONDITIONAL"
COMPLETION_AUTHORITY_MUST_NOT_UPLOAD_ONLY = "MUST_NOT_COMPLETE_FROM_UPLOAD_ONLY"
COMPLETION_AUTHORITY_INFORMATIONAL = "INFORMATIONAL_NO_DIRECT_CERTIFICATE_SATISFACTION"
COMPLETION_AUTHORITY_COMPONENT_AWARE = "COMPONENT_AWARE_SATISFACTION"

SCORE_IMPACT_STRENGTH_HIGH_DIRECT = "HIGH_DIRECT"
SCORE_IMPACT_STRENGTH_MODERATE_CONTEXTUAL = "MODERATE_CONTEXTUAL"
SCORE_IMPACT_STRENGTH_CONDITIONAL = "CONDITIONAL"
SCORE_IMPACT_STRENGTH_DISTRIBUTED_OPERATIONAL = "DISTRIBUTED_OPERATIONAL"
SCORE_IMPACT_STRENGTH_LOW_INFORMATIONAL = "LOW_INFORMATIONAL"
SCORE_IMPACT_STRENGTH_MULTI_COMPONENT = "MULTI_COMPONENT"

EFFECT_EVIDENCE_AUTHORITY_UPDATE = "evidence_authority_update"
EFFECT_REQUIREMENT_TRUTH_RECALC = "requirement_truth_recalculation"
EFFECT_GAP_REGENERATION = "compliance_gap_regeneration"
EFFECT_ATTENTION_REGENERATION = "attention_task_regeneration"
EFFECT_RISK_REGENERATION = "risk_projection_regeneration"
EFFECT_SCORE_RECALC = "compliance_score_recalculation"
EFFECT_REPORT_REFRESH = "reporting_surface_refresh"
EFFECT_AUDIT_APPEND = "audit_timeline_append"
EFFECT_EXPIRY_LIFECYCLE = "expiry_reminder_lifecycle"
EFFECT_OPERATIONAL_CONVERGENCE = "operational_convergence_recalculation"
EFFECT_EVIDENCE_COMPLETENESS = "evidence_completeness_recalculation"

# High-assurance wording (forbidden or tightly conditioned on workflow — audit heuristics only).
FORBIDDEN_ASSURANCE_TERMS = frozenset(
    {
        "fully compliant",
        "statutorily compliant",
        "audit ready",
        "audit-ready",
        "operationally safe",
        "legally resolved",
        "completely safe",
    }
)

# Machine-readable: restricted language governance (documentation + tooling; not runtime blocking).
FORBIDDEN_REPRESENTATION_GOVERNANCE: Dict[str, Any] = {
    "restricted_terms": frozenset({"compliant", "verified", "resolved", "safe", "audit-ready", "audit ready"}),
    "minimum_assurance_threshold": "Terms above require certificate-style or regulator-verified context; declarations and assessments may not use them as headline CTAs without qualification.",
    "forbidden_primary_label_contexts": frozenset(
        {
            "GUIDED_DECLARATION:unqualified_verified_or_compliant",
            "EXTERNAL_ASSESSMENT_EVIDENCE:operationally_safe_or_resolved",
            "CONDITION_STANDARD:active_standard:upload_complete_language",
        }
    ),
    "allowed_usage_conditions": (
        "DOCUMENT_UPLOAD primary CTA may use certificate-oriented labels when registry/evidence authority accepts; "
        "always pair declaration flows with platform-side disclosure copy elsewhere."
    ),
}


def _caps(**kwargs: Any) -> Dict[str, Any]:
    return dict(kwargs)


WORKFLOW_CLASS_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    WC_DOCUMENT_UPLOAD: _caps(
        can_directly_satisfy_requirement=True,
        can_directly_raise_score_confidence=True,
        score_impact_model=SCORE_MODEL_DIRECT_CERTIFICATE,
        requires_structured_payload=False,
        supports_document_upload_as_primary=True,
        supports_document_upload_as_supporting=True,
        supports_expiry_tracking=True,
        supports_follow_up=True,
        may_leave_remediation_open=False,
        must_not_complete_from_document_only=False,
        allowed_primary_cta_families=frozenset(
            {
                CTA_DOCUMENT_UPLOAD_PRIMARY,
                CTA_COORDINATE_INSPECTION,
                CTA_GUIDED_EVIDENCE_RESOLUTION,
            }
        ),
        prohibited_primary_cta_families=frozenset({CTA_VIEW_GUIDANCE}),
        audit_report_role=AUDIT_ROLE_CERTIFICATE_EVIDENCE,
    ),
    WC_GUIDED_DECLARATION: _caps(
        can_directly_satisfy_requirement=True,
        can_directly_raise_score_confidence=True,
        score_impact_model=SCORE_MODEL_DECLARATION_CONFIDENCE,
        requires_structured_payload=True,
        supports_document_upload_as_primary=False,
        supports_document_upload_as_supporting=True,
        supports_expiry_tracking=True,
        supports_follow_up=True,
        may_leave_remediation_open=True,
        must_not_complete_from_document_only=True,
        allowed_primary_cta_families=frozenset(
            {CTA_GUIDED_EVIDENCE_RESOLUTION, CTA_DIRECT_EVIDENCE_ACTION}
        ),
        prohibited_primary_cta_families=frozenset({CTA_DOCUMENT_UPLOAD_PRIMARY}),
        audit_report_role=AUDIT_ROLE_STRUCTURED_DECLARATION,
    ),
    WC_TENANT_DELIVERY: _caps(
        can_directly_satisfy_requirement=True,
        can_directly_raise_score_confidence=True,
        score_impact_model=SCORE_MODEL_DELIVERY_RECORD,
        requires_structured_payload=True,
        supports_document_upload_as_primary=False,
        supports_document_upload_as_supporting=True,
        supports_expiry_tracking=False,
        supports_follow_up=False,
        may_leave_remediation_open=False,
        must_not_complete_from_document_only=True,
        allowed_primary_cta_families=frozenset(
            {CTA_GUIDED_EVIDENCE_RESOLUTION, CTA_DIRECT_EVIDENCE_ACTION}
        ),
        prohibited_primary_cta_families=frozenset({CTA_DOCUMENT_UPLOAD_PRIMARY}),
        audit_report_role=AUDIT_ROLE_DELIVERY_PROOF,
    ),
    WC_REGISTRATION_TRACKING: _caps(
        can_directly_satisfy_requirement=True,
        can_directly_raise_score_confidence=True,
        score_impact_model=SCORE_MODEL_REGISTRATION_RECORD,
        requires_structured_payload=True,
        supports_document_upload_as_primary=False,
        supports_document_upload_as_supporting=True,
        supports_expiry_tracking=True,
        supports_follow_up=True,
        may_leave_remediation_open=False,
        must_not_complete_from_document_only=True,
        allowed_primary_cta_families=frozenset(
            {CTA_GUIDED_EVIDENCE_RESOLUTION, CTA_DIRECT_EVIDENCE_ACTION}
        ),
        prohibited_primary_cta_families=frozenset({CTA_DOCUMENT_UPLOAD_PRIMARY}),
        audit_report_role=AUDIT_ROLE_REGISTRATION_RECORD,
    ),
    WC_EXTERNAL_ASSESSMENT_EVIDENCE: _caps(
        can_directly_satisfy_requirement=True,
        can_directly_raise_score_confidence=True,
        score_impact_model=SCORE_MODEL_ASSESSMENT_CONDITIONAL,
        requires_structured_payload=True,
        supports_document_upload_as_primary=False,
        supports_document_upload_as_supporting=True,
        supports_expiry_tracking=True,
        supports_follow_up=True,
        may_leave_remediation_open=True,
        must_not_complete_from_document_only=True,
        allowed_primary_cta_families=frozenset(
            {CTA_GUIDED_EVIDENCE_RESOLUTION, CTA_DIRECT_EVIDENCE_ACTION}
        ),
        prohibited_primary_cta_families=frozenset({CTA_DOCUMENT_UPLOAD_PRIMARY}),
        audit_report_role=AUDIT_ROLE_ASSESSMENT_AND_ACTIONS,
    ),
    WC_MULTI_EVIDENCE: _caps(
        can_directly_satisfy_requirement=True,
        can_directly_raise_score_confidence=True,
        score_impact_model=SCORE_MODEL_MULTI_COMPONENT,
        requires_structured_payload=False,
        supports_document_upload_as_primary=False,
        supports_document_upload_as_supporting=True,
        supports_expiry_tracking=True,
        supports_follow_up=True,
        may_leave_remediation_open=True,
        must_not_complete_from_document_only=True,
        allowed_primary_cta_families=frozenset(
            {
                CTA_GUIDED_EVIDENCE_RESOLUTION,
                CTA_DOCUMENT_UPLOAD_PRIMARY,
                CTA_DIRECT_EVIDENCE_ACTION,
            }
        ),
        prohibited_primary_cta_families=frozenset(),
        audit_report_role=AUDIT_ROLE_COMPONENT_COMPLETENESS,
    ),
    WC_GUIDANCE_ONLY: _caps(
        can_directly_satisfy_requirement=False,
        can_directly_raise_score_confidence=False,
        score_impact_model=SCORE_MODEL_GUIDANCE_ONLY,
        requires_structured_payload=False,
        supports_document_upload_as_primary=False,
        supports_document_upload_as_supporting=True,
        supports_expiry_tracking=False,
        supports_follow_up=True,
        may_leave_remediation_open=True,
        must_not_complete_from_document_only=True,
        allowed_primary_cta_families=frozenset(
            {CTA_VIEW_GUIDANCE, CTA_MAINTENANCE, CTA_COORDINATE_INSPECTION}
        ),
        prohibited_primary_cta_families=frozenset({CTA_DOCUMENT_UPLOAD_PRIMARY}),
        audit_report_role=AUDIT_ROLE_INFORMATIONAL,
    ),
    CONDITION_STANDARD_ACTIVE_STANDARD: _caps(
        can_directly_satisfy_requirement=False,
        can_directly_raise_score_confidence=False,
        score_impact_model=SCORE_MODEL_OPERATIONAL_CONVERGENCE,
        requires_structured_payload=False,
        supports_document_upload_as_primary=False,
        supports_document_upload_as_supporting=True,
        supports_expiry_tracking=False,
        supports_follow_up=True,
        may_leave_remediation_open=True,
        must_not_complete_from_document_only=True,
        allowed_primary_cta_families=frozenset(
            {CTA_VIEW_GUIDANCE, CTA_MAINTENANCE, CTA_COORDINATE_INSPECTION}
        ),
        prohibited_primary_cta_families=frozenset({CTA_DOCUMENT_UPLOAD_PRIMARY}),
        audit_report_role=AUDIT_ROLE_OPERATIONAL_SIGNALS,
    ),
}

# Normative semantic contracts (governance / tooling only). Merged into get_workflow_capabilities().
WORKFLOW_SEMANTIC_METADATA: Dict[str, Dict[str, Any]] = {
    WC_DOCUMENT_UPLOAD: {
        "workflow_meaning": "Certificate-style obligation where an authoritative uploaded artefact is the primary evidence of compliance when registry and evidence authority accept it.",
        "completion_semantics": "Obligation completion aligns with valid linked certificate/report evidence under engine rules — separate from unrelated remediation work.",
        "risk_resolution_semantics": "Does not itself resolve operational hazards unless explicitly tied to inspection/remediation workflows elsewhere.",
        "score_confidence_semantics": "Typically strong direct confidence where scoring treats satisfied certificate obligations as first-class inputs (no numeric weights defined here).",
        "upload_sufficiency": UPLOAD_SUFFICIENCY_PRIMARY_AUTHORITATIVE,
        "audit_reporting_expectation": "Append certificate evidence events to audit timeline as evidence-of-record; expiry and renewal may generate attention independently.",
        "forbidden_collapses": frozenset(
            {
                "document_presence_implies_all_other_workflows",
                "single_upload_implies_operational_risk_resolved",
            }
        ),
        "reporting_visibility": frozenset(
            {
                REPORT_SURFACE_COMPLIANCE_REPORTS,
                REPORT_SURFACE_AUDIT_EXPORTS,
                REPORT_SURFACE_LENDER_TRIBUNAL_EXPORTS,
                REPORT_SURFACE_RISK_SUMMARIES,
                REPORT_SURFACE_EXPIRY_REPORTS,
                REPORT_SURFACE_EVIDENCE_COMPLETENESS_REPORTS,
            }
        ),
        "reporting_narrative": (
            "Strong compliance-report and expiry visibility; certificate-centric evidence packs where policy allows; "
            "distinguish evidence recorded from unrelated operational remediation closure."
        ),
        "supports_lender_export": True,
        "supports_operational_risk_reporting": False,
        "supports_expiry_reporting": True,
        "supports_evidence_pack_export": True,
        "requires_remediation_context_in_reports": False,
    },
    WC_GUIDED_DECLARATION: {
        "workflow_meaning": "Landlord/user-declared structured facts captured for compliance tracking — not independent statutory or court verification.",
        "completion_semantics": "Complete when required declaration fields and policy completeness rules are met — not equivalent to external verification.",
        "risk_resolution_semantics": "Does not extinguish operational risk by itself; risk signals and remediation lifecycles remain distinct.",
        "score_confidence_semantics": "Moderate / contextual confidence — declaration quality and completeness gates matter; not equivalent to third-party attestation.",
        "upload_sufficiency": UPLOAD_SUFFICIENCY_SUPPORTING_ONLY,
        "audit_reporting_expectation": "Structured submission and amendments append to audit history as declared records with disclosure that verification is platform-side.",
        "forbidden_collapses": frozenset(
            {
                "declaration_equals_statutory_verification",
                "structured_payload_optional_if_pdf_uploaded",
            }
        ),
        "reporting_visibility": frozenset(
            {
                REPORT_SURFACE_COMPLIANCE_REPORTS,
                REPORT_SURFACE_AUDIT_EXPORTS,
                REPORT_SURFACE_LENDER_TRIBUNAL_EXPORTS,
                REPORT_SURFACE_RISK_SUMMARIES,
                REPORT_SURFACE_EVIDENCE_COMPLETENESS_REPORTS,
            }
        ),
        "reporting_narrative": (
            "Declaration-centric reporting: actor, timestamp, supporting evidence, unresolved follow-ups; "
            "lender/tribunal packs must label declarations as platform records — not statutory verification."
        ),
        "supports_lender_export": True,
        "supports_operational_risk_reporting": False,
        "supports_expiry_reporting": False,
        "supports_evidence_pack_export": True,
        "requires_remediation_context_in_reports": True,
    },
    WC_TENANT_DELIVERY: {
        "workflow_meaning": "Record of how prescribed information was delivered to tenants — delivery duty tracking, not adjudication of legal compliance outcomes.",
        "completion_semantics": "Delivery record complete per schema; not equivalent to proof of lawful tenancy outcomes.",
        "risk_resolution_semantics": "Does not resolve unrelated operational or hazard risk.",
        "score_confidence_semantics": "Delivery-record confidence separate from certificate confidence models.",
        "upload_sufficiency": UPLOAD_SUFFICIENCY_SUPPORTING_ONLY,
        "audit_reporting_expectation": "Delivery declarations append as audit events; supporting uploads are corroboration only.",
        "forbidden_collapses": frozenset({"delivery_upload_equals_legal_verdict", "leaflet_presence_equals_delivery"}),
        "reporting_visibility": frozenset(
            {
                REPORT_SURFACE_COMPLIANCE_REPORTS,
                REPORT_SURFACE_AUDIT_EXPORTS,
                REPORT_SURFACE_LENDER_TRIBUNAL_EXPORTS,
                REPORT_SURFACE_RISK_SUMMARIES,
                REPORT_SURFACE_EVIDENCE_COMPLETENESS_REPORTS,
            }
        ),
        "reporting_narrative": (
            "Delivery-duty posture distinct from certificates; audit exports show structured delivery and corroboration; "
            "avoid certificate-style compliant language."
        ),
        "supports_lender_export": True,
        "supports_operational_risk_reporting": False,
        "supports_expiry_reporting": False,
        "supports_evidence_pack_export": True,
        "requires_remediation_context_in_reports": False,
    },
    WC_REGISTRATION_TRACKING: {
        "workflow_meaning": "Structured capture of registration/scheme facts as declared records — not automatic confirmation with external registers.",
        "completion_semantics": "Fields complete per policy; platform does not substitute regulator confirmation.",
        "risk_resolution_semantics": "Operational remediation remains distinct from registration evidence.",
        "score_confidence_semantics": "Registration-record confidence — contextual, not certificate-equivalent unless registry explicitly models it elsewhere.",
        "upload_sufficiency": UPLOAD_SUFFICIENCY_SUPPORTING_ONLY,
        "audit_reporting_expectation": "Structured registration events append to audit timeline; proofs are secondary.",
        "forbidden_collapses": frozenset({"registration_document_equals_enrolment_confirmed"}),
        "reporting_visibility": frozenset(
            {
                REPORT_SURFACE_COMPLIANCE_REPORTS,
                REPORT_SURFACE_AUDIT_EXPORTS,
                REPORT_SURFACE_LENDER_TRIBUNAL_EXPORTS,
                REPORT_SURFACE_RISK_SUMMARIES,
                REPORT_SURFACE_EXPIRY_REPORTS,
                REPORT_SURFACE_EVIDENCE_COMPLETENESS_REPORTS,
            }
        ),
        "reporting_narrative": (
            "Registration facts as declared records; expiry/review where modelled; lender exports disclose lack of live regulator confirmation."
        ),
        "supports_lender_export": True,
        "supports_operational_risk_reporting": False,
        "supports_expiry_reporting": True,
        "supports_evidence_pack_export": True,
        "requires_remediation_context_in_reports": False,
    },
    WC_EXTERNAL_ASSESSMENT_EVIDENCE: {
        "workflow_meaning": "Professional assessment captured structurally; supporting report upload is secondary to the assessment record.",
        "completion_semantics": "Assessment fields may be complete while follow-up actions or completeness layers remain open.",
        "risk_resolution_semantics": "Unresolved assessment actions may leave hazard/remediation posture incomplete independent of obligation row headline.",
        "score_confidence_semantics": "Conditional — completeness gaps or open actions must not be read as automatic score uplift from a single upload.",
        "upload_sufficiency": UPLOAD_SUFFICIENCY_SUPPORTING_ONLY,
        "audit_reporting_expectation": "Assessment structured events and report linkage append to audit history; findings trail remediation separately.",
        "forbidden_collapses": frozenset(
            {
                "report_upload_equals_remediation_closed",
                "assessment_record_equals_operational_risk_cleared",
            }
        ),
        "reporting_visibility": frozenset(
            {
                REPORT_SURFACE_COMPLIANCE_REPORTS,
                REPORT_SURFACE_AUDIT_EXPORTS,
                REPORT_SURFACE_LENDER_TRIBUNAL_EXPORTS,
                REPORT_SURFACE_OPERATIONAL_REMEDIATION_REPORTS,
                REPORT_SURFACE_RISK_SUMMARIES,
                REPORT_SURFACE_EXPIRY_REPORTS,
                REPORT_SURFACE_EVIDENCE_COMPLETENESS_REPORTS,
            }
        ),
        "reporting_narrative": (
            "Operational risk and remediation narrative emphasis: findings, unresolved actions, review dates, assessor details; "
            "assessment completion must not read as remediation completion in reporting surfaces."
        ),
        "supports_lender_export": True,
        "supports_operational_risk_reporting": True,
        "supports_expiry_reporting": True,
        "supports_evidence_pack_export": True,
        "requires_remediation_context_in_reports": True,
    },
    WC_MULTI_EVIDENCE: {
        "workflow_meaning": "Multiple evidence components or modes required — completeness is component-aware.",
        "completion_semantics": "Top-level requirement status may diverge from evidence completeness until all required components are satisfied.",
        "risk_resolution_semantics": "Component gaps may correlate with residual operational exposure — not inferred solely from one upload.",
        "score_confidence_semantics": "Multi-component confidence — must not treat one generic document as satisfying every component.",
        "upload_sufficiency": UPLOAD_SUFFICIENCY_COMPONENTS_REQUIRED,
        "audit_reporting_expectation": "Completeness evaluation surfaces audit visibility without substituting scoring authority.",
        "forbidden_collapses": frozenset({"single_document_satisfies_all_components", "headline_status_equals_component_completeness"}),
        "reporting_visibility": frozenset(
            {
                REPORT_SURFACE_COMPLIANCE_REPORTS,
                REPORT_SURFACE_AUDIT_EXPORTS,
                REPORT_SURFACE_LENDER_TRIBUNAL_EXPORTS,
                REPORT_SURFACE_OPERATIONAL_REMEDIATION_REPORTS,
                REPORT_SURFACE_RISK_SUMMARIES,
                REPORT_SURFACE_EXPIRY_REPORTS,
                REPORT_SURFACE_EVIDENCE_COMPLETENESS_REPORTS,
            }
        ),
        "reporting_narrative": (
            "Headline vs component completeness; evidence completeness reports are primary; lender packs must enumerate components."
        ),
        "supports_lender_export": True,
        "supports_operational_risk_reporting": True,
        "supports_expiry_reporting": True,
        "supports_evidence_pack_export": True,
        "requires_remediation_context_in_reports": True,
    },
    WC_GUIDANCE_ONLY: {
        "workflow_meaning": "Guidance and navigation obligation — informational posture, not certificate closure.",
        "completion_semantics": "Not equivalent to certificate satisfaction; may remain ‘addressed’ via operational routes without upload closure.",
        "risk_resolution_semantics": "Does not directly resolve operational risk; separate signals apply.",
        "score_confidence_semantics": "Guidance-only semantic lane — not interchangeable with certificate confidence.",
        "upload_sufficiency": UPLOAD_SUFFICIENCY_NEVER_SOLE_STANDARD_CLOSURE,
        "audit_reporting_expectation": "Guidance views and acknowledgements may append as interactions — not compliance proofs.",
        "forbidden_collapses": frozenset({"guidance_viewed_equals_obligation_satisfied", "upload_equals_guidance_completion"}),
        "reporting_visibility": frozenset(
            {
                REPORT_SURFACE_COMPLIANCE_REPORTS,
                REPORT_SURFACE_AUDIT_EXPORTS,
            }
        ),
        "reporting_narrative": (
            "Informational compliance and interaction audit trails only; exclude from lender proof packs unless explicitly scoped; "
            "no certificate-compliant wording."
        ),
        "supports_lender_export": False,
        "supports_operational_risk_reporting": False,
        "supports_expiry_reporting": False,
        "supports_evidence_pack_export": False,
        "requires_remediation_context_in_reports": False,
    },
    CONDITION_STANDARD_ACTIVE_STANDARD: {
        "workflow_meaning": "Condition standards monitored via operational convergence (issues, remediation, signals) — not single-document proof.",
        "completion_semantics": "Closure semantics follow operational convergence — not document presence alone.",
        "risk_resolution_semantics": "Hazard/issue/work-order posture informs risk; documents alone do not clear operational risk.",
        "score_confidence_semantics": "Confidence derives from operational convergence signals — uploads alone must not imply resolved posture.",
        "upload_sufficiency": UPLOAD_SUFFICIENCY_NEVER_SOLE_STANDARD_CLOSURE,
        "audit_reporting_expectation": "Operational summaries and remediation history drive audit narrative; uploads are supplementary.",
        "forbidden_collapses": frozenset(
            {
                "document_presence_equals_standard_met",
                "certificate_semantics_applied_to_condition_standard",
            }
        ),
        "reporting_visibility": frozenset(
            {
                REPORT_SURFACE_COMPLIANCE_REPORTS,
                REPORT_SURFACE_AUDIT_EXPORTS,
                REPORT_SURFACE_LENDER_TRIBUNAL_EXPORTS,
                REPORT_SURFACE_OPERATIONAL_REMEDIATION_REPORTS,
                REPORT_SURFACE_RISK_SUMMARIES,
                REPORT_SURFACE_EVIDENCE_COMPLETENESS_REPORTS,
            }
        ),
        "reporting_narrative": (
            "Longitudinal operational reporting: issue history, remediation progress, unresolved hazards, work orders, repeat incidents; "
            "uploads alone must not produce resolved/compliant reporting language."
        ),
        "supports_lender_export": True,
        "supports_operational_risk_reporting": True,
        "supports_expiry_reporting": False,
        "supports_evidence_pack_export": False,
        "requires_remediation_context_in_reports": True,
    },
}

# Execution / recalculation semantics (merged in get_workflow_capabilities; not consumed by runtime engines).
EXECUTION_SEMANTICS_METADATA: Dict[str, Dict[str, Any]] = {
    WC_DOCUMENT_UPLOAD: {
        "execution_triggers": "Authoritative certificate/report uploaded or replaced when evidence authority accepts the document path; optional inspection coordination.",
        "system_execution_effects": frozenset(
            {
                EFFECT_EVIDENCE_AUTHORITY_UPDATE,
                EFFECT_REQUIREMENT_TRUTH_RECALC,
                EFFECT_GAP_REGENERATION,
                EFFECT_SCORE_RECALC,
                EFFECT_EXPIRY_LIFECYCLE,
                EFFECT_ATTENTION_REGENERATION,
                EFFECT_AUDIT_APPEND,
                EFFECT_REPORT_REFRESH,
                EFFECT_RISK_REGENERATION,
            }
        ),
        "may_trigger_score_recalculation": True,
        "may_trigger_risk_regeneration": True,
        "may_trigger_gap_regeneration": True,
        "may_trigger_attention_regeneration": True,
        "may_trigger_report_refresh": True,
        "may_append_audit_timeline": True,
        "completion_authority": COMPLETION_AUTHORITY_MAY_DIRECT_SATISFY,
        "score_impact_strength": SCORE_IMPACT_STRENGTH_HIGH_DIRECT,
        "supports_direct_requirement_satisfaction": True,
        "requires_operational_followup": False,
        "non_equivalence_rules": frozenset(
            {
                "certificate_upload_does_not_close_unrelated_remediation",
                "certificate_row_does_not_imply_tenant_delivery_complete",
            }
        ),
    },
    WC_GUIDED_DECLARATION: {
        "execution_triggers": "Structured declaration submitted or amended with optional supporting uploads.",
        "system_execution_effects": frozenset(
            {
                EFFECT_EVIDENCE_AUTHORITY_UPDATE,
                EFFECT_REQUIREMENT_TRUTH_RECALC,
                EFFECT_EVIDENCE_COMPLETENESS,
                EFFECT_GAP_REGENERATION,
                EFFECT_ATTENTION_REGENERATION,
                EFFECT_AUDIT_APPEND,
                EFFECT_REPORT_REFRESH,
                EFFECT_SCORE_RECALC,
            }
        ),
        "may_trigger_score_recalculation": True,
        "may_trigger_risk_regeneration": False,
        "may_trigger_gap_regeneration": True,
        "may_trigger_attention_regeneration": True,
        "may_trigger_report_refresh": True,
        "may_append_audit_timeline": True,
        "completion_authority": COMPLETION_AUTHORITY_MAY_SATISFY_CONDITIONAL,
        "score_impact_strength": SCORE_IMPACT_STRENGTH_MODERATE_CONTEXTUAL,
        "supports_direct_requirement_satisfaction": True,
        "requires_operational_followup": False,
        "non_equivalence_rules": frozenset(
            {
                "declaration_not_external_legal_verification",
                "declaration_not_statutory_authority_confirmation",
                "declaration_not_independently_verified_compliance",
            }
        ),
    },
    WC_TENANT_DELIVERY: {
        "execution_triggers": "Structured delivery record saved with optional delivery proof upload.",
        "system_execution_effects": frozenset(
            {
                EFFECT_EVIDENCE_AUTHORITY_UPDATE,
                EFFECT_REQUIREMENT_TRUTH_RECALC,
                EFFECT_EVIDENCE_COMPLETENESS,
                EFFECT_GAP_REGENERATION,
                EFFECT_ATTENTION_REGENERATION,
                EFFECT_AUDIT_APPEND,
                EFFECT_REPORT_REFRESH,
                EFFECT_SCORE_RECALC,
            }
        ),
        "may_trigger_score_recalculation": True,
        "may_trigger_risk_regeneration": False,
        "may_trigger_gap_regeneration": True,
        "may_trigger_attention_regeneration": True,
        "may_trigger_report_refresh": True,
        "may_append_audit_timeline": True,
        "completion_authority": COMPLETION_AUTHORITY_MAY_SATISFY_CONDITIONAL,
        "score_impact_strength": SCORE_IMPACT_STRENGTH_MODERATE_CONTEXTUAL,
        "supports_direct_requirement_satisfaction": True,
        "requires_operational_followup": False,
        "non_equivalence_rules": frozenset({"delivery_record_not_court_adjudication", "upload_not_sole_proof_of_service"}),
    },
    WC_REGISTRATION_TRACKING: {
        "execution_triggers": "Registration/scheme structured fields submitted or amended with optional proof upload.",
        "system_execution_effects": frozenset(
            {
                EFFECT_EVIDENCE_AUTHORITY_UPDATE,
                EFFECT_REQUIREMENT_TRUTH_RECALC,
                EFFECT_GAP_REGENERATION,
                EFFECT_ATTENTION_REGENERATION,
                EFFECT_AUDIT_APPEND,
                EFFECT_REPORT_REFRESH,
                EFFECT_SCORE_RECALC,
                EFFECT_EXPIRY_LIFECYCLE,
            }
        ),
        "may_trigger_score_recalculation": True,
        "may_trigger_risk_regeneration": False,
        "may_trigger_gap_regeneration": True,
        "may_trigger_attention_regeneration": True,
        "may_trigger_report_refresh": True,
        "may_append_audit_timeline": True,
        "completion_authority": COMPLETION_AUTHORITY_MAY_SATISFY_CONDITIONAL,
        "score_impact_strength": SCORE_IMPACT_STRENGTH_MODERATE_CONTEXTUAL,
        "supports_direct_requirement_satisfaction": True,
        "requires_operational_followup": False,
        "non_equivalence_rules": frozenset({"registration_record_not_regulator_live_confirmation"}),
    },
    WC_EXTERNAL_ASSESSMENT_EVIDENCE: {
        "execution_triggers": "Assessment structured outcome recorded; supporting report may attach; follow-up actions captured.",
        "system_execution_effects": frozenset(
            {
                EFFECT_EVIDENCE_AUTHORITY_UPDATE,
                EFFECT_REQUIREMENT_TRUTH_RECALC,
                EFFECT_EVIDENCE_COMPLETENESS,
                EFFECT_RISK_REGENERATION,
                EFFECT_ATTENTION_REGENERATION,
                EFFECT_GAP_REGENERATION,
                EFFECT_AUDIT_APPEND,
                EFFECT_REPORT_REFRESH,
                EFFECT_SCORE_RECALC,
                EFFECT_EXPIRY_LIFECYCLE,
            }
        ),
        "may_trigger_score_recalculation": True,
        "may_trigger_risk_regeneration": True,
        "may_trigger_gap_regeneration": True,
        "may_trigger_attention_regeneration": True,
        "may_trigger_report_refresh": True,
        "may_append_audit_timeline": True,
        "completion_authority": COMPLETION_AUTHORITY_MAY_SATISFY_CONDITIONAL,
        "score_impact_strength": SCORE_IMPACT_STRENGTH_CONDITIONAL,
        "supports_direct_requirement_satisfaction": True,
        "requires_operational_followup": True,
        "non_equivalence_rules": frozenset(
            {
                "assessment_complete_not_remediation_complete",
                "assessment_uploaded_not_operationally_compliant",
                "assessment_recorded_not_risk_resolved",
            }
        ),
    },
    WC_MULTI_EVIDENCE: {
        "execution_triggers": "Evidence submitted per mode/component until completeness gates satisfied.",
        "system_execution_effects": frozenset(
            {
                EFFECT_EVIDENCE_AUTHORITY_UPDATE,
                EFFECT_REQUIREMENT_TRUTH_RECALC,
                EFFECT_EVIDENCE_COMPLETENESS,
                EFFECT_GAP_REGENERATION,
                EFFECT_ATTENTION_REGENERATION,
                EFFECT_AUDIT_APPEND,
                EFFECT_REPORT_REFRESH,
                EFFECT_SCORE_RECALC,
                EFFECT_RISK_REGENERATION,
            }
        ),
        "may_trigger_score_recalculation": True,
        "may_trigger_risk_regeneration": True,
        "may_trigger_gap_regeneration": True,
        "may_trigger_attention_regeneration": True,
        "may_trigger_report_refresh": True,
        "may_append_audit_timeline": True,
        "completion_authority": COMPLETION_AUTHORITY_COMPONENT_AWARE,
        "score_impact_strength": SCORE_IMPACT_STRENGTH_MULTI_COMPONENT,
        "supports_direct_requirement_satisfaction": True,
        "requires_operational_followup": True,
        "non_equivalence_rules": frozenset(
            {"single_component_not_all_components", "headline_status_not_component_completeness"}
        ),
    },
    WC_GUIDANCE_ONLY: {
        "execution_triggers": "User views guidance or navigates to operational routes; no certificate submission.",
        "system_execution_effects": frozenset(
            {
                EFFECT_AUDIT_APPEND,
                EFFECT_ATTENTION_REGENERATION,
            }
        ),
        "may_trigger_score_recalculation": False,
        "may_trigger_risk_regeneration": False,
        "may_trigger_gap_regeneration": False,
        "may_trigger_attention_regeneration": True,
        "may_trigger_report_refresh": False,
        "may_append_audit_timeline": True,
        "completion_authority": COMPLETION_AUTHORITY_INFORMATIONAL,
        "score_impact_strength": SCORE_IMPACT_STRENGTH_LOW_INFORMATIONAL,
        "supports_direct_requirement_satisfaction": False,
        "requires_operational_followup": False,
        "non_equivalence_rules": frozenset({"guidance_viewed_not_certificate_satisfied"}),
    },
    CONDITION_STANDARD_ACTIVE_STANDARD: {
        "execution_triggers": "Operational signals updated (issues, work orders, remediation); supplementary uploads optional.",
        "system_execution_effects": frozenset(
            {
                EFFECT_OPERATIONAL_CONVERGENCE,
                EFFECT_RISK_REGENERATION,
                EFFECT_ATTENTION_REGENERATION,
                EFFECT_REQUIREMENT_TRUTH_RECALC,
                EFFECT_GAP_REGENERATION,
                EFFECT_SCORE_RECALC,
                EFFECT_AUDIT_APPEND,
                EFFECT_REPORT_REFRESH,
            }
        ),
        "may_trigger_score_recalculation": True,
        "may_trigger_risk_regeneration": True,
        "may_trigger_gap_regeneration": True,
        "may_trigger_attention_regeneration": True,
        "may_trigger_report_refresh": True,
        "may_append_audit_timeline": True,
        "completion_authority": COMPLETION_AUTHORITY_MUST_NOT_UPLOAD_ONLY,
        "score_impact_strength": SCORE_IMPACT_STRENGTH_DISTRIBUTED_OPERATIONAL,
        "supports_direct_requirement_satisfaction": False,
        "requires_operational_followup": True,
        "non_equivalence_rules": frozenset(
            {
                "document_upload_not_condition_standard_met",
                "inspection_upload_not_hazard_resolved",
                "closed_task_not_operationally_safe_without_signals",
            }
        ),
    },
}

_ACTIVE_STANDARD_CANONICAL = frozenset({"fitness_for_human_habitation", "repairing_standard"})


def _slug_raw_code(raw: str) -> str:
    return str(raw or "").strip().lower().replace(" ", "_")


def _canon_or_storage_slug(enriched: Dict[str, Any]) -> str:
    """Prefer registry-normalised code; fall back to slug so fitness/repairing rows match governance."""
    raw = str(enriched.get("requirement_code") or enriched.get("requirement_type") or "").strip()
    return normalize_requirement_code(raw) or _slug_raw_code(raw) or ""


def get_workflow_capabilities(workflow_class: Optional[str]) -> Dict[str, Any]:
    """Return capability + semantic + execution governance dict for a workflow class key; unknown classes get {}."""
    k = str(workflow_class or "").strip().upper()
    base = dict(WORKFLOW_CLASS_CAPABILITIES.get(k, {}))
    sem = dict(WORKFLOW_SEMANTIC_METADATA.get(k, {}))
    base.update(sem)
    exe = dict(EXECUTION_SEMANTICS_METADATA.get(k, {}))
    base.update(exe)
    return base


def list_governance_workflow_keys() -> FrozenSet[str]:
    """All workflow keys that define capability + semantic metadata (tests / diagnostics)."""
    return frozenset(WORKFLOW_CLASS_CAPABILITIES.keys())


def list_governance_execution_keys() -> FrozenSet[str]:
    """Keys with execution-semantics contracts (must align with capability matrix keys)."""
    return frozenset(EXECUTION_SEMANTICS_METADATA.keys())


def workflow_supports_primary_document_upload(workflow_class: Optional[str]) -> bool:
    c = get_workflow_capabilities(workflow_class)
    return bool(c.get("supports_document_upload_as_primary"))


def workflow_requires_structured_payload(workflow_class: Optional[str]) -> bool:
    c = get_workflow_capabilities(workflow_class)
    return bool(c.get("requires_structured_payload"))


def workflow_may_directly_satisfy_requirement(workflow_class: Optional[str]) -> bool:
    """Governance: whether the workflow profile may directly satisfy the obligation row (read-only)."""
    c = get_workflow_capabilities(workflow_class)
    if "supports_direct_requirement_satisfaction" in c:
        return bool(c.get("supports_direct_requirement_satisfaction"))
    return bool(c.get("can_directly_satisfy_requirement"))


def workflow_may_trigger_score_recalculation(workflow_class: Optional[str]) -> bool:
    c = get_workflow_capabilities(workflow_class)
    return bool(c.get("may_trigger_score_recalculation"))


def workflow_requires_operational_followup(workflow_class: Optional[str]) -> bool:
    c = get_workflow_capabilities(workflow_class)
    return bool(c.get("requires_operational_followup"))


def workflow_requires_gap_regeneration(workflow_class: Optional[str]) -> bool:
    """Governance expectation: evidence changes should drive gap/completeness regeneration (read-only)."""
    c = get_workflow_capabilities(workflow_class)
    return bool(c.get("may_trigger_gap_regeneration"))


def workflow_may_trigger_risk_regeneration(workflow_class: Optional[str]) -> bool:
    c = get_workflow_capabilities(workflow_class)
    return bool(c.get("may_trigger_risk_regeneration"))


def workflow_may_trigger_attention_regeneration(workflow_class: Optional[str]) -> bool:
    c = get_workflow_capabilities(workflow_class)
    return bool(c.get("may_trigger_attention_regeneration"))


def workflow_may_trigger_report_refresh(workflow_class: Optional[str]) -> bool:
    c = get_workflow_capabilities(workflow_class)
    return bool(c.get("may_trigger_report_refresh"))


def workflow_may_append_audit_timeline(workflow_class: Optional[str]) -> bool:
    c = get_workflow_capabilities(workflow_class)
    return bool(c.get("may_append_audit_timeline"))


def workflow_supports_expiry_tracking(workflow_class: Optional[str]) -> bool:
    c = get_workflow_capabilities(workflow_class)
    return bool(c.get("supports_expiry_tracking"))


def workflow_non_equivalence_rules(workflow_class: Optional[str]) -> FrozenSet[str]:
    c = get_workflow_capabilities(workflow_class)
    ne = c.get("non_equivalence_rules")
    if isinstance(ne, frozenset):
        return ne
    fc = c.get("forbidden_collapses")
    if isinstance(fc, frozenset):
        return fc
    return frozenset()


def workflow_completion_authority(workflow_class: Optional[str]) -> str:
    c = get_workflow_capabilities(workflow_class)
    return str(c.get("completion_authority") or "").strip()


def workflow_score_impact_strength(workflow_class: Optional[str]) -> str:
    c = get_workflow_capabilities(workflow_class)
    return str(c.get("score_impact_strength") or "").strip()


def workflow_document_only_is_governance_violation(workflow_class: Optional[str]) -> bool:
    """True when document-only completion path conflicts with governance (structured-first workflows)."""
    c = get_workflow_capabilities(workflow_class)
    return bool(c.get("must_not_complete_from_document_only"))


def workflow_allows_primary_cta_family(workflow_class: Optional[str], cta_family: Optional[str]) -> bool:
    if not cta_family:
        return True
    c = get_workflow_capabilities(workflow_class)
    allowed: FrozenSet[str] = c.get("allowed_primary_cta_families") or frozenset()
    if not allowed:
        return True
    return str(cta_family).strip().upper() in {x.upper() for x in allowed}


def infer_primary_cta_family(enriched: Dict[str, Any]) -> Optional[str]:
    """
    Map resolver primary take_action to a coarse CTA family for governance checks.
    Uses the same intent strings as requirement_action_resolver.
    """
    take = enriched.get("take_action") if isinstance(enriched.get("take_action"), dict) else {}
    pri = take.get("primary") if isinstance(take.get("primary"), dict) else {}
    intent = str(pri.get("intent") or "").strip().lower()
    kind = str(pri.get("kind") or "").strip().lower()
    handler = str(pri.get("handler") or "").strip().lower()

    if handler == "guided_evidence_unavailable" or intent == "guided_evidence_unavailable":
        return CTA_GUIDED_UNAVAILABLE
    if kind in ("guided_evidence_resolution",) or intent == "guided_evidence_resolution":
        return CTA_GUIDED_EVIDENCE_RESOLUTION
    if kind == "direct_evidence_action" or intent == "direct_evidence_action":
        return CTA_DIRECT_EVIDENCE_ACTION
    if intent == "upload_evidence":
        return CTA_DOCUMENT_UPLOAD_PRIMARY
    if intent == "view_guidance":
        return CTA_VIEW_GUIDANCE
    if intent == "maintenance":
        return CTA_MAINTENANCE
    if intent in ("coordinate_inspection_evidence", "book_inspection"):
        return CTA_COORDINATE_INSPECTION
    return None


def resolve_governance_capability_key(
    *,
    reference_class: str,
    enriched: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Choose capability profile: condition/active standards use CONDITION_STANDARD_ACTIVE_STANDARD
    even though runtime workflow_class may remain GUIDANCE_ONLY.
    """
    ref = str(reference_class or "").strip().upper()
    if enriched:
        slug = _canon_or_storage_slug(enriched)
        if slug in _ACTIVE_STANDARD_CANONICAL:
            return CONDITION_STANDARD_ACTIVE_STANDARD
    return ref


def governance_augment_mismatch_flags(
    enriched: Dict[str, Any],
    *,
    reference_class: str,
    existing_flag_ids: FrozenSet[str],
) -> list[Dict[str, Any]]:
    """
    Add governance umbrella flags (additive). Caller merges into workflow_mismatch_flags.
    Read-only diagnostics; does not mutate enriched.
    """
    extra: list[Dict[str, Any]] = []
    ref_upper = str(reference_class or "").strip().upper()
    key = resolve_governance_capability_key(reference_class=reference_class, enriched=enriched)
    caps = get_workflow_capabilities(key)
    semantic_collapse_risk = bool(existing_flag_ids and "MULTI_EVIDENCE_DOCUMENT_ONLY" in existing_flag_ids)
    reporting_drift = False
    emit_forbidden_compliance_representation = False
    completion_exec_drift = any(
        x in existing_flag_ids
        for x in (
            "ASSESSMENT_COMPLETED_WITH_UNRESOLVED_ACTIONS",
            "CONDITION_STANDARD_DOCUMENT_COMPLETION_VIOLATION",
            "CONDITION_STANDARD_MARKED_COMPLETE_WITHOUT_OPERATIONAL_SIGNALS",
        )
    )
    score_exec_drift = False

    modes = enriched.get("allowed_evidence_modes") or []
    if not isinstance(modes, list):
        modes = []
    norm_modes = [str(m or "").strip().upper() for m in modes if m]
    doc_only = len(norm_modes) == 1 and norm_modes[0] == EVIDENCE_MODE_DOCUMENT_UPLOAD
    has_structured = EVIDENCE_MODE_STRUCTURED_DECLARATION in norm_modes

    ec_raw = enriched.get("evidence_completeness")
    ec: Dict[str, Any] = ec_raw if isinstance(ec_raw, dict) else {}

    primary_family = infer_primary_cta_family(enriched)
    allowed_primary_families: FrozenSet[str] = caps.get("allowed_primary_cta_families") or frozenset()
    runtime_primary_cta_allowed = bool(
        primary_family and allowed_primary_families and primary_family in allowed_primary_families
    )

    # Umbrella: document-only where governance forbids treating upload as sufficient completion path.
    # When the resolver already exposes an allowed primary CTA family (e.g. condition-standard issues primary,
    # multi-evidence guided primary), legacy document-only *policy modes* must not emit a HIGH collapse signal.
    if doc_only and caps.get("must_not_complete_from_document_only") and not runtime_primary_cta_allowed:
        semantic_collapse_risk = True
        extra.append(
            {
                "id": "WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION",
                "severity": "HIGH",
                "detail": (
                    f"governance key={key}: evidence_modes allow document-only completion path "
                    "but this workflow class requires structured-first resolution"
                ),
            }
        )

    # Guided / structured workflows published without structured declaration mode.
    if (
        ref_upper == WC_GUIDED_DECLARATION
        and norm_modes
        and not has_structured
        and EVIDENCE_MODE_DOCUMENT_UPLOAD in norm_modes
    ):
        extra.append(
            {
                "id": "GUIDED_DECLARATION_WITHOUT_STRUCTURED_PAYLOAD",
                "severity": "HIGH",
                "detail": "GUIDED_DECLARATION reference but allowed_evidence_modes lacks STRUCTURED_DECLARATION",
            }
        )
        completion_exec_drift = True

    # Certificate-style reference with no document upload mode configured.
    if (
        ref_upper == WC_DOCUMENT_UPLOAD
        and norm_modes
        and EVIDENCE_MODE_DOCUMENT_UPLOAD not in norm_modes
    ):
        extra.append(
            {
                "id": "CERTIFICATE_WORKFLOW_WITHOUT_DOCUMENT_MODE",
                "severity": "MEDIUM",
                "detail": f"DOCUMENT_UPLOAD reference but allowed_evidence_modes={norm_modes}",
            }
        )

    family = primary_family
    prohibited: FrozenSet[str] = caps.get("prohibited_primary_cta_families") or frozenset()
    if family and prohibited and family in prohibited:
        semantic_collapse_risk = True
        extra.append(
            {
                "id": "WORKFLOW_PRIMARY_CTA_GOVERNANCE_VIOLATION",
                "severity": "HIGH",
                "detail": f"primary_cta_family={family} prohibited for governance key={key}",
            }
        )

    take = enriched.get("take_action") if isinstance(enriched.get("take_action"), dict) else {}
    pri = take.get("primary") if isinstance(take.get("primary"), dict) else {}
    primary_label = str(pri.get("label") or "").strip().lower()
    status_upper = str(enriched.get("status") or "").strip().upper()
    slug = _canon_or_storage_slug(enriched)
    wf_rt = str(enriched.get("workflow_class") or "").strip().upper()

    # Declaration copy implying external verification (heuristic — audit-only).
    if ref_upper == WC_GUIDED_DECLARATION:
        risky_verification_wording = (
            "statutory verification",
            "home office",
            "government verification",
            "court verification",
            "legally verified",
            "official verification",
        )
        if any(w in primary_label for w in risky_verification_wording):
            emit_forbidden_compliance_representation = True
            extra.append(
                {
                    "id": "DECLARATION_PRESENTED_AS_VERIFIED_PROOF",
                    "severity": "MEDIUM",
                    "detail": "primary label wording suggests external verification beyond structured declaration semantics",
                }
            )
            extra.append(
                {
                    "id": "DECLARATION_PRESENTED_AS_EXTERNALLY_VERIFIED",
                    "severity": "MEDIUM",
                    "detail": "execution semantics: declarations must not be presented as externally verified proof",
                }
            )
            extra.append(
                {
                    "id": "DECLARATION_REPORTED_AS_EXTERNALLY_VERIFIED",
                    "severity": "MEDIUM",
                    "detail": "reporting surfaces must not label declarations as externally verified without verification authority",
                }
            )
            completion_exec_drift = True
            reporting_drift = True
        if "audit ready" in primary_label or "audit-ready" in primary_label.replace(" ", ""):
            emit_forbidden_compliance_representation = True
            extra.append(
                {
                    "id": "DECLARATION_PRESENTED_AS_AUDIT_READY",
                    "severity": "MEDIUM",
                    "detail": "primary label uses audit-ready assurance language incompatible with guided declaration semantics",
                }
            )
            completion_exec_drift = True
        if "verification passed" in primary_label and "platform" not in primary_label:
            emit_forbidden_compliance_representation = True
            extra.append(
                {
                    "id": "UNVERIFIED_WORKFLOW_PRESENTED_AS_VERIFIED",
                    "severity": "MEDIUM",
                    "detail": "declaration primary label implies verification outcome beyond platform record semantics",
                }
            )
            completion_exec_drift = True

    if wf_rt == WC_EXTERNAL_ASSESSMENT_EVIDENCE:
        if "operationally safe" in primary_label or "completely safe" in primary_label:
            emit_forbidden_compliance_representation = True
            extra.append(
                {
                    "id": "ASSESSMENT_PRESENTED_AS_OPERATIONALLY_SAFE",
                    "severity": "MEDIUM",
                    "detail": "assessment workflow must not present operational safety as proven by assessment alone",
                }
            )
            completion_exec_drift = True

    # Condition standard: document-only treated as equivalence to compliance closure.
    if (
        slug in _ACTIVE_STANDARD_CANONICAL
        and doc_only
        and (
            requirement_status_appears_satisfied_top_level(enriched)
            or status_upper in ("COMPLIANT", "VALID")
        )
    ):
        semantic_collapse_risk = True
        extra.append(
            {
                "id": "CONDITION_STANDARD_DOCUMENT_EQUIVALENCE",
                "severity": "HIGH",
                "detail": "condition-standard context with document-only modes and satisfied-appearing row risks document≈standard semantics",
            }
        )
        extra.append(
            {
                "id": "CONDITION_STANDARD_PRESENTED_AS_UPLOAD_COMPLETE",
                "severity": "HIGH",
                "detail": "execution semantics: condition-standard must not be presented as satisfied from upload-only posture",
            }
        )
        extra.append(
            {
                "id": "CONDITION_STANDARD_REPORTED_AS_DOCUMENT_COMPLIANT",
                "severity": "HIGH",
                "detail": "reporting must not treat uploads or headline status as condition-standard compliance closure",
            }
        )
        completion_exec_drift = True
        reporting_drift = True

    if (
        wf_rt == WC_EXTERNAL_ASSESSMENT_EVIDENCE
        and family == CTA_DOCUMENT_UPLOAD_PRIMARY
        and (
            requirement_status_appears_satisfied_top_level(enriched)
            or status_upper in ("COMPLIANT", "VALID")
        )
    ):
        semantic_collapse_risk = True
        extra.append(
            {
                "id": "ASSESSMENT_TREATED_AS_REMEDIATION",
                "severity": "MEDIUM",
                "detail": "external assessment workflow with upload-primary CTA while row appears satisfied — risk of equating report upload with remediation closure",
            }
        )
        extra.append(
            {
                "id": "ASSESSMENT_PRESENTED_AS_REMEDIATED",
                "severity": "MEDIUM",
                "detail": "execution semantics: assessment completion must not be presented as remediation completion",
            }
        )
        completion_exec_drift = True

    satisfied_appearing = requirement_status_appears_satisfied_top_level(enriched) or status_upper in (
        "COMPLIANT",
        "VALID",
    )
    if wf_rt == WC_EXTERNAL_ASSESSMENT_EVIDENCE and satisfied_appearing:
        if family == CTA_DOCUMENT_UPLOAD_PRIMARY or (
            ec.get("evaluated") is True and ec.get("is_complete") is False
        ):
            extra.append(
                {
                    "id": "ASSESSMENT_REPORTED_AS_REMEDIATED",
                    "severity": "MEDIUM",
                    "detail": "reporting surfaces may flatten assessment/remediation semantics — disclose open actions and completeness",
                }
            )
            completion_exec_drift = True
            reporting_drift = True

    # Condition standard: satisfied appearance without operational convergence signals.
    if slug in _ACTIVE_STANDARD_CANONICAL:
        summary = (
            enriched.get("active_standard_status_summary")
            if isinstance(enriched.get("active_standard_status_summary"), dict)
            else {}
        )
        if (
            requirement_status_appears_satisfied_top_level(enriched)
            or status_upper in ("COMPLIANT", "VALID")
        ) and str(summary.get("state") or "").strip().lower() in ("", "unknown"):
            extra.append(
                {
                    "id": "CONDITION_STANDARD_DOCUMENT_COMPLETION_VIOLATION",
                    "severity": "HIGH",
                    "detail": "condition standard appears satisfied but operational signal summary is unknown",
                }
            )

    # External assessment: satisfied requirement row while completeness still incomplete (proxy for open actions).
    if (
        wf_rt == WC_EXTERNAL_ASSESSMENT_EVIDENCE
        and ec.get("evaluated") is True
        and ec.get("is_complete") is False
        and requirement_status_appears_satisfied_top_level(enriched)
    ):
        extra.append(
            {
                "id": "ASSESSMENT_COMPLETED_WITH_UNRESOLVED_ACTIONS",
                "severity": "MEDIUM",
                "detail": ec.get("completeness_reason")
                or "requirement appears satisfied while evidence completeness reports incomplete components",
            }
        )
        completion_exec_drift = True
        score_exec_drift = True

    if (
        ref_upper == WC_DOCUMENT_UPLOAD
        and satisfied_appearing
        and wf_rt in (WC_DOCUMENT_UPLOAD, "LEGACY_DOCUMENT_UPLOAD")
        and not (
            enriched.get("expiry_date")
            or enriched.get("certificate_expiry_date")
            or enriched.get("next_inspection_due")
            or enriched.get("valid_until")
        )
    ):
        extra.append(
            {
                "id": "DOCUMENT_WORKFLOW_MISSING_EXPIRY_SEMANTICS",
                "severity": "LOW",
                "detail": "certificate-style row appears satisfied but no expiry/due fields present on payload — verify expiry lifecycle semantics",
            }
        )
        score_exec_drift = True

    if doc_only and satisfied_appearing and ref_upper in (WC_MULTI_EVIDENCE, WC_EXTERNAL_ASSESSMENT_EVIDENCE):
        score_exec_drift = True

    if emit_forbidden_compliance_representation:
        extra.append(
            {
                "id": "FORBIDDEN_COMPLIANCE_REPRESENTATION",
                "severity": "MEDIUM",
                "detail": "primary CTA label uses high-assurance or compliance language outside allowed workflow context (see FORBIDDEN_REPRESENTATION_GOVERNANCE)",
            }
        )

    if reporting_drift:
        extra.append(
            {
                "id": "WORKFLOW_REPORTING_SEMANTIC_DRIFT",
                "severity": "HIGH",
                "detail": (
                    "heuristic: obligation shape risks flattening distinct reporting semantics "
                    "(see WORKFLOW_BEHAVIOUR_GOVERNANCE.md — Reporting and Audit Surface Semantics)"
                ),
            }
        )

    if completion_exec_drift:
        extra.append(
            {
                "id": "WORKFLOW_COMPLETION_SEMANTIC_DRIFT",
                "severity": "HIGH",
                "detail": "heuristic: completion / obligation / remediation meanings may be conflated (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md — Workflow Execution & System Behaviour Semantics)",
            }
        )

    if score_exec_drift:
        extra.append(
            {
                "id": "WORKFLOW_SCORE_SEMANTIC_DRIFT",
                "severity": "MEDIUM",
                "detail": "heuristic: evidence shape vs score-confidence semantics may be misaligned (governance-only; does not alter scoring)",
            }
        )

    if semantic_collapse_risk:
        extra.append(
            {
                "id": "WORKFLOW_SEMANTIC_COLLAPSE_RISK",
                "severity": "HIGH",
                "detail": "heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)",
            }
        )

    # Dedupe against existing IDs from legacy audit to avoid duplicate umbrella rows when identical.
    seen = set(existing_flag_ids)
    out = []
    for row in extra:
        rid = str(row.get("id") or "")
        if rid and rid not in seen:
            seen.add(rid)
            out.append(row)
    return out
