"""
PRELAUNCH-CER-AUTHORITY-GOVERNANCE-DECISION-01 — governance design only.

Defines authoritative CER governance model before convergence implementation.
Does NOT mutate runtime behaviour.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "docs/audit/prelaunch_cer_authority_governance_decision_01"
PROGRAMME = "PRELAUNCH-CER-AUTHORITY-GOVERNANCE-DECISION-01"
PRIOR_AUDIT = "PRELAUNCH-NONDOCUMENT-EVIDENCE-AUTHORITY-AUDIT-01"

# Governance family keys (PART 1)
GF_SELF = "SELF_CERTIFIED"
GF_ORG = "ORG_ADMIN_REVIEWED"
GF_PLATFORM_OPT = "PLATFORM_OVERSIGHT_OPTIONAL"
GF_PLATFORM_VER = "PLATFORM_VERIFIED"
GF_ESCALATION = "ESCALATION_REVIEW_ONLY"

DOCUMENT_PRIMARY_TYPES = (
    "gas_safety",
    "eicr",
    "epc",
    "fire_alarm",
    "portable_appliance_test",
    "pat",
    "electrical_installation_condition_report",
    "energy_performance_certificate",
    "hmo_licence",
    "selective_licence",
    "asbestos",
    "oil_tank",
    "emergency_lighting",
    "fire_door",
    "lift_inspection",
)

# Explicit CER / non-document governance assignments (product decision record)
CER_GOVERNANCE_BY_TYPE: Dict[str, Dict[str, Any]] = {
    "smoke_heat_alarms": {
        "governance_family": GF_SELF,
        "governance_family_secondary": GF_PLATFORM_OPT,
        "rationale": "Multi-component checklist/declaration can self-close when completeness guards pass; platform oversight only on escalation or low-confidence paths.",
        "authority_owner": "landlord_self_attestation",
        "verification_required": "conditional",
        "review_visibility": "org_internal_optional",
        "operational_closure_mode": "governance_guard_auto_close",
        "score_authority_mode": "multi_component_conditional",
        "escalation_conditions": ["multi_evidence_components_incomplete", "manual_review_flag", "repeated_rejection"],
        "stale_rules": "no_stale_without_review_owner",
        "admin_visibility": "none_primary; escalation_queue_only",
        "acceptable_evidence_types": ["STRUCTURED_DECLARATION", "INSPECTION_CHECKLIST", "CONTRACTOR_CONFIRMATION", "DOCUMENT_UPLOAD"],
    },
    "legionella": {
        "governance_family": GF_PLATFORM_OPT,
        "rationale": "External assessment with follow-up remediation; platform may sample-review but primary closure is operational follow-up resolution.",
        "authority_owner": "landlord_with_platform_oversight_optional",
        "verification_required": "operational_followup_not_human_review_default",
        "review_visibility": "platform_oversight_sample",
        "operational_closure_mode": "external_assessment_followup_guard",
        "score_authority_mode": "assessment_conditional",
        "escalation_conditions": ["external_assessment_remediation_unresolved", "manual_review_flag", "contradiction_detected"],
        "stale_rules": "stale_on_unresolved_followup_not_generic_review",
        "admin_visibility": "oversight_queue_sampled; not document pending-verification",
        "acceptable_evidence_types": ["STRUCTURED_DECLARATION", "DOCUMENT_UPLOAD"],
    },
    "lead_testing": {
        "governance_family": GF_PLATFORM_OPT,
        "rationale": "Same family as legionella — assessment + follow-up.",
        "authority_owner": "landlord_with_platform_oversight_optional",
        "verification_required": "operational_followup_not_human_review_default",
        "review_visibility": "platform_oversight_sample",
        "operational_closure_mode": "external_assessment_followup_guard",
        "score_authority_mode": "assessment_conditional",
        "escalation_conditions": ["external_assessment_remediation_unresolved", "manual_review_flag"],
        "stale_rules": "stale_on_unresolved_followup_not_generic_review",
        "admin_visibility": "oversight_queue_sampled",
        "acceptable_evidence_types": ["STRUCTURED_DECLARATION", "DOCUMENT_UPLOAD"],
    },
    "right_to_rent": {
        "governance_family": GF_ORG,
        "rationale": "Organisation records statutory check; org admin may verify internally; not platform certificate verification.",
        "authority_owner": "org_admin",
        "verification_required": "org_admin_optional",
        "review_visibility": "org_admin_queue",
        "operational_closure_mode": "declaration_recorded_plus_org_verify_optional",
        "score_authority_mode": "declaration_confidence",
        "escalation_conditions": ["guided_declaration_low_confidence", "manual_review_flag", "contradiction_detected"],
        "stale_rules": "no_platform_stale_review",
        "admin_visibility": "org_queue_future; not platform pending-verification",
        "acceptable_evidence_types": ["STRUCTURED_DECLARATION", "DOCUMENT_UPLOAD"],
    },
    "how_to_rent": {
        "governance_family": GF_SELF,
        "rationale": "Tenant delivery attestation; tenant_delivery_record_guard closes operationally without platform human review.",
        "authority_owner": "landlord_self_attestation",
        "verification_required": False,
        "review_visibility": "none",
        "operational_closure_mode": "tenant_delivery_record_guard",
        "score_authority_mode": "delivery_record",
        "escalation_conditions": ["manual_review_flag", "contradiction_detected"],
        "stale_rules": "none",
        "admin_visibility": "none",
        "acceptable_evidence_types": ["STRUCTURED_DECLARATION", "DOCUMENT_UPLOAD"],
    },
    "deposit_pi": {
        "governance_family": GF_ORG,
        "rationale": "Organisation-managed deposit compliance record.",
        "authority_owner": "org_admin",
        "verification_required": "org_admin_optional",
        "review_visibility": "org_admin_queue",
        "operational_closure_mode": "declaration_recorded_plus_org_verify_optional",
        "score_authority_mode": "declaration_confidence",
        "escalation_conditions": ["manual_review_flag", "contradiction_detected"],
        "stale_rules": "no_platform_stale_review",
        "admin_visibility": "org_queue_future",
        "acceptable_evidence_types": ["STRUCTURED_DECLARATION", "DOCUMENT_UPLOAD"],
    },
    "wales_occupation_contract": {
        "governance_family": GF_ORG,
        "authority_owner": "org_admin",
        "verification_required": "org_admin_optional",
        "review_visibility": "org_admin_queue",
        "operational_closure_mode": "declaration_recorded_plus_org_verify_optional",
        "score_authority_mode": "declaration_confidence",
        "escalation_conditions": ["manual_review_flag"],
        "stale_rules": "no_platform_stale_review",
        "admin_visibility": "org_queue_future",
        "acceptable_evidence_types": ["STRUCTURED_DECLARATION", "DOCUMENT_UPLOAD"],
    },
    "tenancy_agreement": {
        "governance_family": GF_ORG,
        "authority_owner": "org_admin",
        "verification_required": "org_admin_optional",
        "review_visibility": "org_admin_queue",
        "operational_closure_mode": "declaration_recorded_plus_org_verify_optional",
        "score_authority_mode": "declaration_confidence",
        "escalation_conditions": ["manual_review_flag"],
        "stale_rules": "no_platform_stale_review",
        "admin_visibility": "org_queue_future",
        "acceptable_evidence_types": ["STRUCTURED_DECLARATION", "DOCUMENT_UPLOAD"],
    },
    "hmo_fire_risk": {
        "governance_family": GF_PLATFORM_OPT,
        "authority_owner": "landlord_with_platform_oversight_optional",
        "verification_required": "conditional",
        "review_visibility": "platform_oversight_sample",
        "operational_closure_mode": "multi_evidence_governance_guard",
        "score_authority_mode": "multi_component_conditional",
        "escalation_conditions": ["multi_evidence_components_incomplete", "manual_review_flag"],
        "stale_rules": "no_stale_without_review_owner",
        "admin_visibility": "oversight_queue_sampled",
        "acceptable_evidence_types": ["DOCUMENT_UPLOAD", "CONTRACTOR_CONFIRMATION", "INSPECTION_CHECKLIST"],
    },
    "hmo_fire_risk_evidence": {
        "governance_family": GF_PLATFORM_OPT,
        "authority_owner": "landlord_with_platform_oversight_optional",
        "verification_required": "conditional",
        "review_visibility": "platform_oversight_sample",
        "operational_closure_mode": "multi_evidence_governance_guard",
        "score_authority_mode": "multi_component_conditional",
        "escalation_conditions": ["multi_evidence_components_incomplete", "manual_review_flag"],
        "stale_rules": "no_stale_without_review_owner",
        "admin_visibility": "oversight_queue_sampled",
        "acceptable_evidence_types": ["DOCUMENT_UPLOAD", "CONTRACTOR_CONFIRMATION", "INSPECTION_CHECKLIST"],
    },
    "fire_risk_assessment": {
        "governance_family": GF_PLATFORM_OPT,
        "authority_owner": "landlord_with_platform_oversight_optional",
        "verification_required": "conditional",
        "review_visibility": "platform_oversight_sample",
        "operational_closure_mode": "multi_evidence_governance_guard",
        "score_authority_mode": "multi_component_conditional",
        "escalation_conditions": ["multi_evidence_components_incomplete", "manual_review_flag"],
        "stale_rules": "no_stale_without_review_owner",
        "admin_visibility": "oversight_queue_sampled",
        "acceptable_evidence_types": ["DOCUMENT_UPLOAD", "CONTRACTOR_CONFIRMATION", "INSPECTION_CHECKLIST"],
    },
}

for _reg in ("landlord_registration", "scotland_landlord_registration", "landlord_registration_ni", "rent_smart_wales"):
    CER_GOVERNANCE_BY_TYPE[_reg] = {
        "governance_family": GF_ORG,
        "rationale": "Registration tracking — org attestation with optional supporting document.",
        "authority_owner": "org_admin",
        "verification_required": "org_admin_optional",
        "review_visibility": "org_admin_queue",
        "operational_closure_mode": "registration_tracking_record_guard",
        "score_authority_mode": "registration_record",
        "escalation_conditions": ["manual_review_flag", "registration_contradiction"],
        "stale_rules": "no_platform_stale_review",
        "admin_visibility": "org_queue_future",
        "acceptable_evidence_types": ["STRUCTURED_DECLARATION", "DOCUMENT_UPLOAD"],
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _document_primary_row(code: str) -> Dict[str, Any]:
    return {
        "requirement_code": code,
        "governance_family": GF_PLATFORM_VER,
        "governance_family_label": "Platform verified (certificate)",
        "authority_owner": "platform_admin",
        "verification_required": True,
        "review_visibility": "platform_admin_documents_queue",
        "operational_closure_mode": "admin_document_verify_plus_authority_sync",
        "score_authority_mode": "direct_certificate",
        "escalation_conditions": ["mismatch_flagged", "manual_review_flag", "extraction_low_confidence", "repeated_rejection"],
        "stale_rules": "stale_on_pending_admin_review_with_owner",
        "admin_visibility": "GET /api/admin/documents/pending-verification",
        "acceptable_evidence_types": ["DOCUMENT_UPLOAD"],
        "cer_applicable": False,
        "notes": "Document-primary; not CER governance path unless supporting upload only.",
    }


def build_cer_governance_matrix() -> Dict[str, Any]:
    from services.compliance_evidence_record_service import (
        DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE,
        effective_evidence_resolution,
    )

    rows: List[Dict[str, Any]] = []
    seen = set()

    for code, gov in sorted(CER_GOVERNANCE_BY_TYPE.items()):
        pol = DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE.get(code, {})
        rows.append(
            {
                "requirement_code": code,
                "governance_family": gov["governance_family"],
                "governance_family_secondary": gov.get("governance_family_secondary"),
                "governance_family_labels": {
                    GF_SELF: "Self-certified (automated governance closure)",
                    GF_ORG: "Organisation admin reviewed",
                    GF_PLATFORM_OPT: "Platform oversight optional",
                    GF_PLATFORM_VER: "Platform verified certificate",
                    GF_ESCALATION: "Escalation review only (overlay)",
                },
                "rationale": gov.get("rationale"),
                "authority_owner": gov["authority_owner"],
                "verification_required": gov["verification_required"],
                "review_visibility": gov["review_visibility"],
                "operational_closure_mode": gov["operational_closure_mode"],
                "score_authority_mode": gov["score_authority_mode"],
                "escalation_conditions": gov["escalation_conditions"],
                "stale_rules": gov["stale_rules"],
                "admin_visibility": gov["admin_visibility"],
                "acceptable_evidence_types": gov["acceptable_evidence_types"],
                "primary_resolution_workflow": pol.get("primary_resolution_workflow"),
                "cer_applicable": True,
            }
        )
        seen.add(code)

    for code in sorted(set(DOCUMENT_PRIMARY_TYPES) | set(DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE.keys())):
        if code in seen:
            continue
        pol = DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE.get(code, {})
        wf = str(pol.get("primary_resolution_workflow") or "LEGACY_DOCUMENT_UPLOAD").upper()
        if wf in ("LEGACY_DOCUMENT_UPLOAD", "DOCUMENT_UPLOAD") or code in DOCUMENT_PRIMARY_TYPES:
            rows.append(_document_primary_row(code))
            seen.add(code)

    rows.sort(key=lambda r: r["requirement_code"])
    families = {GF_SELF: [], GF_ORG: [], GF_PLATFORM_OPT: [], GF_PLATFORM_VER: [], GF_ESCALATION: []}
    for r in rows:
        fam = r["governance_family"]
        if fam in families:
            families[fam].append(r["requirement_code"])

    return {
        "programme": PROGRAMME,
        "prior_audit": PRIOR_AUDIT,
        "generated_at": _utc_now(),
        "governance_families": {
            "A_SELF_CERTIFIED": {
                "key": GF_SELF,
                "description": "Landlord attestation closes via governance guards; no default human review queue.",
                "requirement_codes": families[GF_SELF],
            },
            "B_ORG_ADMIN_REVIEWED": {
                "key": GF_ORG,
                "description": "Organisation admin may verify; platform admin not default reviewer.",
                "requirement_codes": families[GF_ORG],
            },
            "C_PLATFORM_OVERSIGHT_OPTIONAL": {
                "key": GF_PLATFORM_OPT,
                "description": "Operational follow-up / sample platform oversight; not certificate verification.",
                "requirement_codes": families[GF_PLATFORM_OPT],
            },
            "D_PLATFORM_VERIFIED": {
                "key": GF_PLATFORM_VER,
                "description": "Official certificates verified by platform admin document queue.",
                "requirement_codes": families[GF_PLATFORM_VER],
            },
            "E_ESCALATION_REVIEW_ONLY": {
                "key": GF_ESCALATION,
                "description": "Cross-cutting overlay — not a primary family; triggered by risk signals.",
                "trigger_conditions": [
                    "manual_review_flag",
                    "evidence_mismatch",
                    "repeated_rejection",
                    "contradiction_pattern",
                    "abuse_signal",
                    "low_confidence_extraction",
                ],
                "applies_to": "any family when triggered",
            },
        },
        "requirements": rows,
        "inventory_count": len(rows),
    }


def build_truth_surface_language_matrix() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "generated_at": _utc_now(),
        "principle": "Every user-visible state MUST name the authority owner or operational gap. Generic review language forbidden without queue owner.",
        "forbidden_generic_labels": [
            {"label": "Awaiting review", "reason": "Implies reviewer exists; often false for CER"},
            {"label": "Review pending", "reason": "Same — no owner specified"},
            {"label": "Authoritative submission on file — awaiting review", "reason": "Collapses operational incompleteness into fake review"},
        ],
        "authoritative_replacements": [
            {
                "authority_state_or_stage": "SELF_CERTIFIED_SUBMITTED",
                "governance_family": GF_SELF,
                "primary_label": "Declaration recorded",
                "secondary_label": "Compliance steps complete",
                "subline": "Your submission is recorded. No platform review is required for this obligation.",
                "forbidden": ["Awaiting review"],
            },
            {
                "authority_state_or_stage": "OPERATIONAL_INCOMPLETE",
                "governance_family": GF_SELF,
                "primary_label": "Additional action still required",
                "secondary_label": "Incomplete compliance steps remain",
                "subline": "Some required evidence components are still missing.",
                "semantic_triggers": ["multi_evidence_components_incomplete", "declaration_incomplete"],
            },
            {
                "authority_state_or_stage": "FOLLOWUP_REQUIRED",
                "governance_family": GF_PLATFORM_OPT,
                "primary_label": "Follow-up evidence required",
                "secondary_label": "Remediation or follow-up may remain open",
                "subline": "Complete remaining assessment or remediation steps to close this obligation.",
                "semantic_triggers": ["external_assessment_remediation_or_followup_unresolved", "ASSESSMENT_FOLLOWUP_REQUIRED"],
            },
            {
                "authority_state_or_stage": "ORG_REVIEW_PENDING",
                "governance_family": GF_ORG,
                "primary_label": "Organisation review pending",
                "secondary_label": "Record on file — organisation verification optional",
                "subline": "Your organisation admin can verify this record when required.",
                "queue_owner": "org_admin",
            },
            {
                "authority_state_or_stage": "PLATFORM_VERIFICATION_PENDING",
                "governance_family": GF_PLATFORM_VER,
                "primary_label": "Platform verification pending",
                "secondary_label": "Document submitted — Pleerity review in progress",
                "subline": "Our team will verify your uploaded certificate.",
                "queue_owner": "platform_admin",
            },
            {
                "authority_state_or_stage": "PLATFORM_OVERSIGHT_SAMPLE",
                "governance_family": GF_PLATFORM_OPT,
                "primary_label": "Assessment recorded",
                "secondary_label": "Operational review may apply",
                "subline": "Your assessment is on file. Complete any open follow-up actions.",
                "queue_owner": "none_default",
            },
            {
                "authority_state_or_stage": "SUPPORTING_UPLOAD_ONLY",
                "governance_family": "any",
                "primary_label": "Supporting evidence uploaded",
                "secondary_label": "Formal submission not yet complete",
                "subline": "Supporting files alone do not complete this obligation.",
            },
            {
                "authority_state_or_stage": "ESCALATION_REVIEW",
                "governance_family": GF_ESCALATION,
                "primary_label": "Escalated for platform review",
                "secondary_label": "Manual review required",
                "subline": "This submission was flagged for Pleerity review.",
                "queue_owner": "platform_admin_escalation",
            },
            {
                "authority_state_or_stage": "VERIFIED",
                "governance_family": "any",
                "primary_label": "Verified",
                "secondary_label": "Requirement satisfied",
            },
            {
                "authority_state_or_stage": "EVIDENCE_RECORDED_UNVERIFIED",
                "governance_family": GF_ORG,
                "primary_label": "Evidence recorded",
                "secondary_label": "Not independently verified",
                "subline": "Recorded for compliance tracking; not platform certificate verification.",
            },
        ],
        "presentation_rules": {
            "single_primary_badge": True,
            "tier_badge_must_not_duplicate_primary": True,
            "stale_label_requires_owner": True,
            "cognition_recommended_step_must_name_owner": True,
        },
        "migration_from_current": {
            "clientPersistedSubmissionPresentation.FRONTEND_SUBMISSION_ON_FILE": "Replace with semantic_state-driven label from matrix",
            "operational_cognition.submitted_pending_review": "Rename stage to owner-qualified stage ids",
        },
    }


def build_convergence_rules() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "generated_at": _utc_now(),
        "single_source_of_truth": "requirements.evidence_authority (synced via sync_requirement_evidence_authority)",
        "mandatory_convergence_rules": [
            {
                "id": "CR-01",
                "rule": "Frontend labels MUST derive from evidence_authority.state + semantic_state + governance_family — never override to generic review without owner.",
                "surfaces": ["RequirementsPage", "PropertyDetailPage", "PropertyOperatingHub", "Today", "Command Centre"],
            },
            {
                "id": "CR-02",
                "rule": "Stale escalation ONLY when review_visibility names an active queue owner OR operational follow-up is overdue with defined owner.",
                "forbidden": "stale_review on submitted_pending_review without queue",
            },
            {
                "id": "CR-03",
                "rule": "compliance_score MUST use map_authority_to_scoring_status only — no parallel score writers.",
            },
            {
                "id": "CR-04",
                "rule": "client_lifecycle_state MUST NOT contradict evidence_authority.state after sync; presentation layer may not upgrade ACTION_REQUIRED to PENDING_REVIEW.",
            },
            {
                "id": "CR-05",
                "rule": "CER verification_status transitions MUST propagate through propagate_requirement_evidence_outcome.",
            },
            {
                "id": "CR-06",
                "rule": "Admin queue entries MUST include queue_owner and governance_family; no orphan PENDING_REVIEW rows.",
            },
            {
                "id": "CR-07",
                "rule": "operational_cognition workflow_stage vocabulary MUST align with truth_surface_language_matrix stage ids.",
            },
            {
                "id": "CR-08",
                "rule": "Forbidden labels (Awaiting review, Review pending) MUST NOT render unless queue_owner is platform_admin or org_admin and item is enqueued.",
            },
        ],
        "forbidden_patterns": [
            "duplicate semantic meanings across status chip and tier badge",
            "queue-less review states in UI or cognition",
            "stale escalation without authority owner",
            "second authority model parallel to evidence_authority",
            "score fraction diverging from authority state without documented governance exception",
        ],
    }


def build_score_governance() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "generated_at": _utc_now(),
        "principle": "Score, UI, Today, and Command Centre MUST converge from evidence_authority.state via map_authority_to_scoring_status and governance_family policy.",
        "authority_to_score": {
            "SELF_CERTIFIED_CLOSED": {"authority_states": ["VERIFIED_CURRENT"], "score": "VALID (1.0)", "ui_must_match": True},
            "SELF_CERTIFIED_PARTIAL": {"authority_states": ["UPLOADED_UNCONFIRMED"], "score": "NEEDS_REVIEW (0.5)", "ui_label": "Additional action still required"},
            "ORG_RECORDED": {"authority_states": ["UPLOADED_UNCONFIRMED"], "score": "NEEDS_REVIEW (0.5)", "ui_label": "Evidence recorded / Organisation review pending"},
            "PLATFORM_PENDING": {"authority_states": ["PENDING_ADMIN_REVIEW"], "score": "NEEDS_REVIEW (0.5)", "ui_label": "Platform verification pending"},
            "MISSING": {"authority_states": ["MISSING"], "score": "MISSING (0)", "ui_label": "Action required"},
            "FOLLOWUP_UNRESOLVED": {"authority_states": ["UPLOADED_UNCONFIRMED"], "semantic_state": "ASSESSMENT_FOLLOWUP_REQUIRED", "score": "NEEDS_REVIEW (0.5)", "ui_label": "Follow-up evidence required"},
            "VERIFIED": {"authority_states": ["VERIFIED_CURRENT"], "score": "VALID (1.0)", "ui_label": "Verified"},
            "EXPIRED": {"authority_states": ["VERIFIED_EXPIRED"], "score": "EXPIRED", "ui_label": "Expired — renewal required"},
        },
        "score_authority_modes_by_family": {
            GF_SELF: "Governance guard closure → VERIFIED_CURRENT; partial → NEEDS_REVIEW until complete",
            GF_ORG: "Declaration recorded → NEEDS_REVIEW until org verify or auto-accept policy",
            GF_PLATFORM_OPT: "Follow-up resolved → VERIFIED_CURRENT; unresolved → NEEDS_REVIEW",
            GF_PLATFORM_VER: "PENDING_ADMIN_REVIEW → NEEDS_REVIEW; verified doc → VALID",
            GF_ESCALATION: "Escalated → NEEDS_REVIEW until platform escalation resolved",
        },
        "divergence_prevention": [
            "Ban frontend score-adjacent labels that imply VALID when authority is NEEDS_REVIEW",
            "Today hero counts use same map_authority_to_scoring_status",
            "Command Centre task severity derives from authority + governance_family stale rules",
        ],
    }


def build_classifications() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "generated_at": _utc_now(),
        "classification": "GOVERNANCE_DESIGN_COMPLETE",
        "sub_classifications": [],
        "unresolved_items": [
            {
                "id": "GOV-U1",
                "topic": "Org admin queue UX scope",
                "status": "deferred_to_implementation",
                "note": "API exists (client verify); org-facing queue UI not yet designed",
            },
            {
                "id": "GOV-U2",
                "topic": "Platform oversight sampling rate for PLATFORM_OVERSIGHT_OPTIONAL",
                "status": "product_policy",
                "note": "Default: no human review unless escalation trigger",
            },
        ],
        "implementation_approved": False,
        "prior_audit": PRIOR_AUDIT,
    }


def _write_json(name: str, payload: Dict[str, Any]) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_markdown_artifacts(matrix: Dict[str, Any]) -> None:
    (OUT_DIR / "review_authority_decision_report.md").write_text(_review_authority_report(matrix), encoding="utf-8")
    (OUT_DIR / "operational_completion_governance.md").write_text(_operational_completion_md(), encoding="utf-8")
    (OUT_DIR / "admin_governance_topology.md").write_text(_admin_topology_md(), encoding="utf-8")
    (OUT_DIR / "escalation_cognition_governance.md").write_text(_escalation_cognition_md(), encoding="utf-8")
    (OUT_DIR / "safe_implementation_roadmap.md").write_text(_implementation_roadmap_md(), encoding="utf-8")
    (OUT_DIR / "risk_assessment.md").write_text(_risk_assessment_md(), encoding="utf-8")
    (OUT_DIR / "REPORT.md").write_text(_final_report_md(matrix), encoding="utf-8")


def _review_authority_report(matrix: Dict[str, Any]) -> str:
    return f"""# Review authority decision report

**Programme:** {PROGRAMME}  
**Generated:** {_utc_now()}

## Decision summary

| Review type | Owner | Mechanism | Requirement families |
|-------------|-------|-----------|---------------------|
| Certificate verification | **Pleerity platform admin** | `GET /api/admin/documents/pending-verification` + verify | D — PLATFORM_VERIFIED |
| Organisation internal verify | **Landlord org admin** (admin-like client role) | `POST .../compliance-evidence/{{id}}/verification` | B — ORG_ADMIN_REVIEWED |
| Automated governance closure | **System governance guards** | `sync_requirement_evidence_authority` + guards | A — SELF_CERTIFIED |
| Operational follow-up closure | **Landlord + guard resolution** | external_assessment / multi_evidence guards | C — PLATFORM_OVERSIGHT_OPTIONAL |
| Risk-triggered review | **Pleerity platform admin (escalation queue)** | manual_review_flag, mismatch, abuse | E — ESCALATION overlay |
| No review required | **N/A** | Record-on-file satisfies when guards pass | A subset (e.g. how_to_rent delivery) |

## Explicit non-decisions (current drift — to be fixed in implementation)

- CER `PENDING_REVIEW` MUST NOT imply platform admin review unless governance_family = D or E trigger active.
- Generic "Awaiting review" MUST NOT appear for families A, C default path, or B without org queue enrollment.

## Scalability

| Path | Scale implication |
|------|-------------------|
| Platform verified (D) | Bounded by certificate upload volume — existing ops model |
| Self-certified (A) | Scales horizontally — no human queue |
| Org reviewed (B) | Scales with customer orgs — platform not in path |
| Platform oversight optional (C) | Default no queue; sample/escalation only — avoids review overload |
| Escalation (E) | Small queue — high-signal only |

## Staffing

- **Platform ops:** Document verification (existing) + escalation queue (new, small).
- **No platform staffing** for default CER self-cert or org-review paths.
- **Org admins:** Optional verify for B-family; customer-managed.

## Trust implications

- Self-certified paths MUST disclose "not independent verification" (already in client_evidence_disclosure).
- Platform verified (D) remains highest trust tier for certificates.
- Org-reviewed (B) trust boundary is organisation, not Pleerity legal attestation.

## Abuse risks

- Self-certified without guards → score inflation. **Mitigation:** governance guards mandatory before VERIFIED_CURRENT.
- Fake org verify → **Mitigation:** audit trail on verify actor; escalation on contradiction.
- Supporting upload only → perceived completion. **Mitigation:** truth labels (Supporting evidence uploaded).

## Legal exposure

- UI must not imply Home Office / professional verification where product disclosure says otherwise (right_to_rent, legionella).
- "Platform verification pending" only for D-family and E-escalation.

## Families inventory

- **A ({len(matrix['governance_families']['A_SELF_CERTIFIED']['requirement_codes'])} types):** {', '.join(matrix['governance_families']['A_SELF_CERTIFIED']['requirement_codes']) or '—'}
- **B ({len(matrix['governance_families']['B_ORG_ADMIN_REVIEWED']['requirement_codes'])} types):** {', '.join(matrix['governance_families']['B_ORG_ADMIN_REVIEWED']['requirement_codes']) or '—'}
- **C ({len(matrix['governance_families']['C_PLATFORM_OVERSIGHT_OPTIONAL']['requirement_codes'])} types):** {', '.join(matrix['governance_families']['C_PLATFORM_OVERSIGHT_OPTIONAL']['requirement_codes']) or '—'}
- **D ({len(matrix['governance_families']['D_PLATFORM_VERIFIED']['requirement_codes'])} types):** document-primary certificates (see cer_governance_matrix.json)
"""


def _operational_completion_md() -> str:
    return f"""# Operational completion governance

**Programme:** {PROGRAMME}

## Completion states (authoritative)

| State | Definition | Score typical | Legal completeness |
|-------|------------|---------------|-------------------|
| **Missing** | No authoritative submission | MISSING (0) | Not met |
| **Evidence-submitted-only** | CER or doc exists but guards incomplete | NEEDS_REVIEW (0.5) | Not met |
| **Partially complete** | Multi-component / follow-up open | NEEDS_REVIEW (0.5) | Not met |
| **Awaiting follow-up** | Assessment remediation unresolved | NEEDS_REVIEW (0.5) | Not met |
| **Operationally complete** | All governance guards pass; may be unverified | NEEDS_REVIEW or VALID per family | May be met for self-cert |
| **Formally verified** | VERIFIED_CURRENT or platform doc verified | VALID (1.0) | Met per product scope |

## Distinctions (mandatory)

1. **Evidence presence** — `primary_evidence_record_id` or document on file. Necessary not sufficient.
2. **Operational completion** — governance guards satisfied (`evidence_completeness.is_complete`, follow-up resolved).
3. **Verification completion** — human or platform verify action OR auto-close policy for self-cert family.
4. **Score contribution** — `map_authority_to_scoring_status` only.
5. **Legal completeness** — landlord statutory duty; product tracks evidence not legal advice.

## Closure modes by family

- **A:** `governance_guard_auto_close` — no human verify default.
- **B:** `registration_tracking_record_guard` / declaration recorded; org verify optional.
- **C:** `external_assessment_followup_guard` — follow-up must resolve.
- **D:** `admin_document_verify_plus_authority_sync`.
- **E:** Escalation queue resolution overlay.

## Forbidden conflation

- MUST NOT treat CER submit as operational complete when components incomplete.
- MUST NOT treat supporting vault upload as submission.
- MUST NOT show "verified" language when authority is UPLOADED_UNCONFIRMED unless label says "Evidence recorded".
"""


def _admin_topology_md() -> str:
    return f"""# Admin governance topology

**Programme:** {PROGRAMME}

## Queue topology (target state)

```
┌─────────────────────────────────────────────────────────────┐
│ PLATFORM ADMIN (Pleerity ops)                                │
├─────────────────────────────────────────────────────────────┤
│ 1. Document verification queue (EXISTING)                    │
│    - documents.status=UPLOADED                               │
│    - Family D only                                           │
│ 2. Escalation review queue (NEW — design only)               │
│    - manual_review_flag, mismatch, abuse, repeat rejection   │
│    - Family E overlay on any type                            │
│ 3. Oversight sample queue (OPTIONAL — low volume)            │
│    - Family C flagged for sample only                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ ORGANISATION ADMIN (client portal)                           │
├─────────────────────────────────────────────────────────────┤
│ Org compliance review queue (NEW UX — design only)             │
│    - CER PENDING_REVIEW where governance_family=B            │
│    - Uses existing verify API                                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ NO QUEUE (by design)                                         │
├─────────────────────────────────────────────────────────────┤
│ Family A default path — automated guard closure              │
│ Family C default path — follow-up driven, not review queue   │
└─────────────────────────────────────────────────────────────┘
```

## Anti-patterns prevented

- **Fake pending queues:** No UI "awaiting review" without queue enrollment.
- **Review overload:** A and C default paths exclude platform human review.
- **Invisible workflows:** Every queued item exposes queue_owner in admin/org UI.
- **Operational deadlocks:** Follow-up states route to landlord action, not orphan review.

## Current vs target gap (from prior audit)

| Queue | Current | Target |
|-------|---------|--------|
| Platform doc verify | Exists | Keep |
| Platform CER review | Missing (drift) | Only E + optional C sample |
| Org CER review | API only, no queue UI | Org queue for family B |
| Escalation | Ad hoc flags | Dedicated escalation queue |
"""


def _escalation_cognition_md() -> str:
    return f"""# Escalation + cognition governance

**Programme:** {PROGRAMME}

## Stale rules (revised — design)

| Condition | Allowed stale? | Owner | Label |
|-----------|----------------|-------|-------|
| Platform doc PENDING_ADMIN_REVIEW | Yes (7d) | platform_admin | Platform verification pending (stale) |
| Org review enqueued | Yes (7d) | org_admin | Organisation review pending (stale) |
| Follow-up unresolved | Yes (configurable) | landlord | Follow-up evidence required (overdue) |
| Self-cert incomplete components | No generic stale | landlord | Additional action still required |
| CER pending, no queue owner | **Forbidden** | — | Must NOT escalate as "stale review" |

## Escalation ownership

| Escalation | Owner | Entry condition |
|------------|-------|-----------------|
| STALE_PLATFORM_VERIFY | platform_admin | EA_PENDING_ADMIN_REVIEW + 7d |
| STALE_ORG_VERIFY | org_admin | B-family + enqueued + 7d |
| FOLLOWUP_OVERDUE | landlord | semantic ASSESSMENT_FOLLOWUP_REQUIRED + due date passed |
| MANUAL_REVIEW | platform_admin_escalation | manual_review_flag |
| OVERDUE_REQUIREMENT | landlord | statutory due date — not review stale |

## Cognition vocabulary migration

Replace `_workflow_stage` values that imply review without owner:

| Current stage | Target stage | Owner |
|---------------|--------------|-------|
| submitted_pending_review | recorded_pending_closure | governance-dependent |
| awaiting_review | platform_verify_pending OR org_verify_pending OR **forbidden** | must resolve owner |

## Today / Command Centre

- STALE_REVIEW flag ONLY when stale rules table permits.
- recommended_next_step MUST name actor: "Complete remaining checklist items" not "Wait for reviewer".
"""


def _implementation_roadmap_md() -> str:
    return f"""# Safe implementation roadmap (proposal — NOT approved)

**Programme:** {PROGRAMME}

## Sequence (mandatory order)

1. **Frontend label convergence** — truth_surface_language_matrix; remove FRONTEND_SUBMISSION_ON_FILE override; dedupe badges.
2. **Governance family metadata** — expose governance_family on enriched requirement payloads (read-only field).
3. **Stale / cognition alignment** — _stale_review_active owner-aware; rename workflow stages.
4. **Admin queue extension** — escalation queue + optional org queue UX; NOT blanket CER pending-verification.
5. **CER authority convergence** — map PENDING_REVIEW to correct authority state per family; no orphan states.
6. **Lifecycle migration** — backfill semantic_state labels; optional data migration for misclassified rows.
7. **Score truth convergence** — verify Today/CC use map_authority_to_scoring_status exclusively.

## Migrations required

- Presentation layer only: phase 1 (no DB).
- Optional: re-sync requirements with governance_family-aware authority promotion.
- Cognition copy: server-side guidance_v1 template updates.

## Unsafe shortcuts (forbidden)

- Auto-verify all CER on submit.
- Add CER to document pending-verification without family filter.
- New review_state collection parallel to evidence_authority.
- Disable governance guards to reduce "stuck" rows.

## Backwards compatibility

- Landlords may see label changes — intentional trust repair.
- Admin ops gain escalation queue — no removal of document queue.
- API verify endpoint unchanged; queue UX added.

## Trust risks if sequence violated

- Implementing admin queue before label fix → ops review items that should self-close.
- Authority migration before family metadata → wrong queue routing.
"""


def _risk_assessment_md() -> str:
    return f"""# Risk assessment

**Programme:** {PROGRAMME}

| Risk | Severity | Mitigation |
|------|----------|------------|
| Duplicate authority model | HIGH | Single writer: sync_requirement_evidence_authority |
| Review overload | HIGH | Family A/C default no platform queue |
| False pending persists during rollout | MEDIUM | Phase 1 label convergence first |
| Org admin confusion | MEDIUM | Clear B-family disclosure + org queue UX |
| Legal misrepresentation | HIGH | Truth labels + existing disclosures |
| Score inflation via self-cert | HIGH | Guards before VERIFIED_CURRENT |
| Migration breaks staging rows | MEDIUM | Re-sync harness + family-aware promotion |

**Overall:** Governance design is **VERIFIED_GOVERNANCE_CONVERGENCE**-ready pending implementation approval.
"""


def _final_report_md(matrix: Dict[str, Any]) -> str:
    fam = matrix["governance_families"]
    return f"""# {PROGRAMME} — Final governance architecture

**Classification:** `GOVERNANCE_DESIGN_COMPLETE`  
**Implementation:** NOT APPROVED  
**Prior audit:** {PRIOR_AUDIT}

## 1. CER governance matrix

See `cer_governance_matrix.json` — {matrix['inventory_count']} requirement types across families A–E.

## 2. Review ownership

See `review_authority_decision_report.md`.

- Platform admin: certificates (D) + escalation (E)
- Org admin: B-family optional verify
- Automated: A-family guard closure
- Landlord: C-family follow-up completion

## 3. Truth-language system

See `truth_surface_language_matrix.json` — generic "Awaiting review" forbidden without queue owner.

## 4. Operational completion model

See `operational_completion_governance.md`.

## 5. Score governance

See `score_authority_governance.json` — single mapper, family-aware UI convergence.

## 6. Admin queue topology

See `admin_governance_topology.md`.

## 7. Escalation ownership

See `escalation_cognition_governance.md`.

## 8. Convergence rules

See `convergence_rules.json`.

## 9. Safe implementation roadmap

See `safe_implementation_roadmap.md`.

## 10. Recommended final architecture

```
Landlord submit → CER + sync_requirement_evidence_authority
       ↓
governance_family policy (A/B/C/D/E)
       ↓
┌──────────────┬─────────────┬──────────────────┐
│ A: auto-close│ B: org queue│ C: follow-up     │
│ (guards)     │ (optional)  │ (landlord action)│
├──────────────┴─────────────┴──────────────────┤
│ D: platform doc verify (existing)              │
│ E: escalation overlay → platform escalation Q  │
└────────────────────────────────────────────────┘
       ↓
truth_surface_language_matrix → UI / Today / CC
       ↓
map_authority_to_scoring_status → compliance score
```

**Primary issue addressed:** governance drift — review semantics decoupled from queue owners.  
**Not implemented:** runtime fixes await explicit approval after governance sign-off.

Harness: `backend/tmp_prelaunch_cer_authority_governance_decision_01.py`
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    matrix = build_cer_governance_matrix()
    _write_json("cer_governance_matrix.json", matrix)
    _write_json("truth_surface_language_matrix.json", build_truth_surface_language_matrix())
    _write_json("convergence_rules.json", build_convergence_rules())
    _write_json("score_authority_governance.json", build_score_governance())
    _write_json("classifications.json", build_classifications())
    _write_json("00_run_meta.json", {
        "programme": PROGRAMME,
        "generated_at": _utc_now(),
        "method": "governance_design_static",
        "implementation": "NONE",
        "prior_audit": PRIOR_AUDIT,
    })
    write_markdown_artifacts(matrix)
    print(json.dumps({"written": str(OUT_DIR), "types": matrix["inventory_count"]}, indent=2))


if __name__ == "__main__":
    main()
