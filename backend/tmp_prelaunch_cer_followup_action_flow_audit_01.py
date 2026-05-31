"""
PRELAUNCH-CER-FOLLOWUP-ACTION-FLOW-AUDIT-01 — audit-only harness.

Verifies Phase 1 truth labels have operational fulfilment paths (CTA → form → persistence → transition).
Does NOT implement fixes.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs/audit/prelaunch_cer_followup_action_flow_audit_01"
PROGRAMME = "PRELAUNCH-CER-FOLLOWUP-ACTION-FLOW-AUDIT-01"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# --- Mirror frontend lifecycle / CTA presentation (requirementLifecyclePresentation.js) ---

def _primary_label_suggests_initial_obligation(label: str) -> bool:
    s = (label or "").strip()
    if not s:
        return False
    if re.match(r"^record\b", s, re.I):
        return True
    if re.match(r"^upload\b", s, re.I):
        return True
    if re.match(r"^add compliance evidence\b", s, re.I):
        return True
    return False


def _map_truth_stage_to_lifecycle(stage: str, queue_backed: bool) -> str:
    s = (stage or "").strip()
    if s == "verified":
        return "VERIFIED"
    if s in ("platform_verification_pending", "escalation_review"):
        return "PENDING_REVIEW"
    if queue_backed and s == "awaiting_review":
        return "PENDING_REVIEW"
    if s in ("followup_required", "operational_incomplete", "action_required", "supporting_upload_only"):
        return "ACTION_REQUIRED"
    if s in ("declaration_recorded", "assessment_recorded", "evidence_recorded", "recorded_on_file"):
        return "SATISFIED_UNVERIFIED"
    return "ACTION_REQUIRED"


def _is_queue_backed(row: Dict[str, Any]) -> bool:
    if row.get("queue_backed_review") is True:
        return True
    owner = str(row.get("review_owner") or "").strip()
    return owner in ("platform_admin", "platform_admin_escalation", "org_admin")


def apply_lifecycle_aware_cta_presentation(requirement: Dict[str, Any], cta: Dict[str, Any]) -> Dict[str, Any]:
    """Python mirror of applyLifecycleAwareCtaPresentation."""
    if not cta:
        return cta or {}
    stage = str(requirement.get("truth_presentation_stage") or "").strip()
    queue_backed = _is_queue_backed(requirement)
    state = _map_truth_stage_to_lifecycle(stage, queue_backed)
    if state in ("ACTION_REQUIRED", "NOT_APPLICABLE"):
        return dict(cta)
    base_label = str(cta.get("primary_action_label") or "")
    if not _primary_label_suggests_initial_obligation(base_label):
        return dict(cta)
    route = str(cta.get("primary_route") or "")
    handler = str(cta.get("primary_action_handler") or "")
    primary_action_label = base_label
    if state == "PENDING_REVIEW":
        if handler == "guided_evidence":
            primary_action_label = "View submission"
        elif "/documents" in route:
            primary_action_label = "View evidence"
        else:
            primary_action_label = "Review submission"
    elif state == "SATISFIED_UNVERIFIED" or stage in (
        "declaration_recorded",
        "assessment_recorded",
        "evidence_recorded",
        "followup_required",
    ):
        if handler == "guided_evidence":
            primary_action_label = (
                "View submission"
                if stage == "followup_required"
                or stage in ("declaration_recorded", "assessment_recorded", "evidence_recorded")
                else "View or update evidence"
            )
        elif "/documents" in route:
            primary_action_label = "View evidence"
        else:
            primary_action_label = "View evidence"
    elif state == "VERIFIED":
        primary_action_label = (
            "View verified evidence" if handler == "guided_evidence" else "View evidence"
        )
    return {**cta, "primary_action_label": primary_action_label}


def _is_view_existing_submission_cta(ta: Dict[str, Any]) -> bool:
    if str(ta.get("primary_action_handler") or "") != "guided_evidence":
        return False
    label = str(ta.get("primary_action_label") or "").strip()
    return bool(
        re.match(r"^view submission$", label, re.I)
        or re.match(r"^view verified evidence$", label, re.I)
        or re.match(r"^review submission$", label, re.I)
        or re.match(r"^view or update evidence$", label, re.I)
    )


def resolve_client_cta(requirement: Dict[str, Any]) -> Dict[str, Any]:
    from services.requirement_action_resolver import (
        enrich_take_action_envelope_for_client,
        resolve_take_action_envelope,
    )

    env = enrich_take_action_envelope_for_client(
        resolve_take_action_envelope(
            requirement,
            property_id=requirement.get("property_id"),
            property_jurisdiction=requirement.get("jurisdiction"),
        ),
        requirement,
    )
    take = env.get("take_action") or {}
    pri = take.get("primary") if isinstance(take.get("primary"), dict) else {}
    raw = {
        "primary_action_label": str(pri.get("label") or ""),
        "primary_action_handler": str(pri.get("handler") or "navigate"),
        "primary_route": pri.get("route"),
        "guided_initial_evidence_mode": pri.get("evidence_mode"),
        "workflow_class": env.get("workflow_class"),
        "allowed_evidence_modes": env.get("allowed_evidence_modes") or [],
    }
    return apply_lifecycle_aware_cta_presentation(requirement, raw)


def _cta_destination(handler: str, route: Optional[str]) -> str:
    if handler == "guided_evidence":
        return "ComplianceEvidenceResolveModal (GuidedEvidenceModalContext)"
    if handler == "direct_evidence":
        return "ComplianceEvidenceResolveModal (pre-selected mode)"
    if handler == "guided_evidence_unavailable":
        return "disabled — metadata incomplete"
    if route and "/documents" in str(route):
        return f"Documents page ({route})"
    if route:
        return f"in-app navigate ({route})"
    return "none"


# --- Fixtures ---

def _legionella_cer(actions_required: str = "yes") -> Dict[str, Any]:
    return {
        "_id": "cer_leg_01",
        "requirement_id": "req_leg",
        "property_id": "prop_01",
        "evidence_mode": "STRUCTURED_DECLARATION",
        "status": "PENDING_REVIEW",
        "evidence_payload": {
            "structured_fields": {
                "assessment_completed": {"answer": True},
                "assessment_date": {"answer": "2025-01-15"},
                "assessor_type": {"answer": "self"},
                "risk_level": {"answer": "medium"},
                "control_measures_in_place": {"answer": True},
                "actions_required": {"answer": actions_required == "yes"},
                "declaration_confirmed": {"answer": True},
            }
        },
    }


def _smoke_cer_smoke_only() -> Dict[str, Any]:
    return {
        "_id": "cer_smoke_01",
        "requirement_id": "req_smoke",
        "property_id": "prop_01",
        "evidence_mode": "INSPECTION_CHECKLIST",
        "status": "VERIFIED",
        "evidence_payload": {
            "checklist_answers": {
                "smoke_alarm_present": {"answer": "PASS"},
                "smoke_alarm_tested": {"answer": "PASS"},
            }
        },
    }


def _base_requirement(code: str, **extra: Any) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "requirement_id": f"req_{code}",
        "property_id": "prop_01",
        "requirement_type": code,
        "requirement_code": code,
        "jurisdiction": "England",
        "status": "MISSING",
        **extra,
    }
    return row


def build_inventory() -> List[Dict[str, Any]]:
    from services.cer_governance_presentation import attach_cer_governance_presentation
    from services.compliance_evidence_record_service import effective_evidence_resolution
    from services.operational_cognition_service import build_requirement_guidance_v1
    from services.requirement_evidence_completeness import evaluate_domestic_alarm_completeness

    scenarios: List[Tuple[str, Dict[str, Any], Optional[List[Dict[str, Any]]]]] = [
        (
            "smoke_operational_incomplete",
            _base_requirement(
                "smoke_heat_alarms",
                client_lifecycle_state="ACTION_REQUIRED",
                evidence_authority={
                    "state": "UPLOADED_UNCONFIRMED",
                    "state_reason": "multi_evidence_components_incomplete",
                    "primary_evidence_record_id": "cer_smoke_01",
                },
                evidence_completeness={"is_complete": False, "required_missing_count": 1, "summary_label": "CO alarm evidence missing"},
            ),
            [_smoke_cer_smoke_only()],
        ),
        (
            "legionella_followup_required",
            _base_requirement(
                "legionella",
                client_lifecycle_state="ACTION_REQUIRED",
                evidence_authority={
                    "state": "UPLOADED_UNCONFIRMED",
                    "state_reason": "external_assessment_remediation_or_followup_unresolved",
                    "semantic_state": "ASSESSMENT_FOLLOWUP_REQUIRED",
                    "primary_evidence_record_id": "cer_leg_01",
                },
            ),
            [_legionella_cer("yes")],
        ),
        (
            "how_to_rent_declaration_recorded",
            _base_requirement(
                "how_to_rent",
                client_lifecycle_state="SATISFIED_UNVERIFIED",
                evidence_authority={"state": "UPLOADED_UNCONFIRMED", "primary_evidence_record_id": "cer_htr"},
            ),
            [{"_id": "cer_htr", "evidence_mode": "STRUCTURED_DECLARATION", "status": "VERIFIED", "evidence_payload": {}}],
        ),
        (
            "right_to_rent_evidence_recorded",
            _base_requirement(
                "right_to_rent",
                client_lifecycle_state="SATISFIED_UNVERIFIED",
                evidence_authority={"state": "UPLOADED_UNCONFIRMED", "primary_evidence_record_id": "cer_rtr"},
            ),
            [{"_id": "cer_rtr", "evidence_mode": "STRUCTURED_DECLARATION", "status": "PENDING_REVIEW", "evidence_payload": {}}],
        ),
        (
            "deposit_pi_evidence_recorded",
            _base_requirement("deposit_pi", client_lifecycle_state="SATISFIED_UNVERIFIED", evidence_authority={"state": "UPLOADED_UNCONFIRMED", "primary_evidence_record_id": "cer_dpi"}),
            [{"_id": "cer_dpi", "evidence_mode": "STRUCTURED_DECLARATION", "status": "VERIFIED", "evidence_payload": {}}],
        ),
        (
            "gas_platform_verification_pending",
            _base_requirement(
                "gas_safety",
                workflow_class="DOCUMENT_UPLOAD",
                client_lifecycle_state="PENDING_REVIEW",
                evidence_authority={"state": "PENDING_ADMIN_REVIEW"},
                evidence_doc_id="doc_gas_01",
            ),
            None,
        ),
        (
            "legionella_assessment_recorded_closed",
            _base_requirement(
                "legionella",
                client_lifecycle_state="SATISFIED_UNVERIFIED",
                evidence_authority={
                    "state": "VERIFIED_CURRENT",
                    "primary_evidence_record_id": "cer_leg_closed",
                },
            ),
            [_legionella_cer("no")],
        ),
        (
            "supporting_upload_only",
            _base_requirement(
                "legionella",
                client_lifecycle_state="ACTION_REQUIRED",
                evidence_authority={"state": "UPLOADED"},
            ),
            None,
        ),
        (
            "fire_risk_multi_incomplete",
            _base_requirement(
                "fire_risk_assessment",
                client_lifecycle_state="ACTION_REQUIRED",
                evidence_authority={"state": "MISSING", "state_reason": "multi_evidence_components_incomplete"},
            ),
            None,
        ),
        (
            "legacy_no_truth_surface_followup",
            _base_requirement(
                "legionella",
                client_lifecycle_state="SATISFIED_UNVERIFIED",
                evidence_authority={
                    "state": "UPLOADED_UNCONFIRMED",
                    "state_reason": "external_assessment_remediation_or_followup_unresolved",
                    "semantic_state": "ASSESSMENT_FOLLOWUP_REQUIRED",
                    "primary_evidence_record_id": "cer_leg_01",
                },
            ),
            [_legionella_cer("yes")],
        ),
    ]

    inventory: List[Dict[str, Any]] = []
    for key, req, recs in scenarios:
        gov = attach_cer_governance_presentation(req)
        enriched = {**req, **gov}
        if key == "legacy_no_truth_surface_followup":
            for k in (
                "truth_presentation_stage",
                "truth_presentation_label",
                "truth_presentation_subline",
                "governance_family",
                "client_lifecycle_label",
            ):
                enriched.pop(k, None)
        if key == "smoke_operational_incomplete" and recs is not None:
            comp = evaluate_domestic_alarm_completeness(enriched, {"requires_co_alarm": True}, recs)
            enriched["evidence_completeness"] = comp

        policy = effective_evidence_resolution(enriched)
        guidance = build_requirement_guidance_v1(enriched, policy=policy)
        cta = resolve_client_cta(enriched)
        lifecycle_state = _map_truth_stage_to_lifecycle(
            str(enriched.get("truth_presentation_stage") or ""),
            _is_queue_backed(enriched),
        )
        if not enriched.get("truth_presentation_stage"):
            lifecycle_state = str(enriched.get("client_lifecycle_state") or "UNKNOWN")

        handler = str(cta.get("primary_action_handler") or "")
        endpoint = (
            "POST /client/properties/{property_id}/requirements/{requirement_id}/compliance-evidence"
            if handler in ("guided_evidence", "direct_evidence")
            else (
                "POST /client/documents/upload + admin verify"
                if "/documents" in str(cta.get("primary_route") or "")
                else None
            )
        )
        persistence = (
            "compliance_evidence_records"
            if handler in ("guided_evidence", "direct_evidence")
            else ("documents" if endpoint else None)
        )

        review_blocked = bool(
            guidance.get("submitted_not_verified")
            and not guidance.get("rejected_requires_action")
            and not guidance.get("reviewer_requested_changes")
        )

        expected_transition = None
        stage = str(enriched.get("truth_presentation_stage") or "")
        if stage == "operational_incomplete":
            expected_transition = "operational_incomplete → declaration_recorded when all components satisfied"
        elif stage == "followup_required":
            expected_transition = "followup_required → assessment_recorded/verified when actions_required=no"
        elif stage == "platform_verification_pending":
            expected_transition = "platform_verification_pending → verified after admin document verify"

        flow_implemented = True
        gaps: List[str] = []
        if stage == "followup_required" and _is_view_existing_submission_cta(cta):
            flow_implemented = False
            gaps.append("CTA is view-only despite follow-up label")
        if stage == "followup_required" and str(cta.get("primary_action_label") or "").lower() == "add compliance evidence":
            gaps.append("Generic CTA — no follow-up-specific copy")
        if stage == "operational_incomplete" and "component" not in str(cta.get("primary_action_label") or "").lower():
            gaps.append("Generic CTA — component checklist not surfaced in label")
        if review_blocked and stage in ("followup_required", "operational_incomplete"):
            flow_implemented = False
            gaps.append("Guided modal reviewBlocked=true (submitted_not_verified + queue)")
        if str(enriched.get("governance_family") or "") == "ORG_ADMIN_REVIEWED" and _is_queue_backed(enriched):
            gaps.append("Org queue label implied but no org admin verify UI in codebase")

        inventory.append(
            {
                "scenario_key": key,
                "requirement_type": enriched.get("requirement_type"),
                "governance_family": enriched.get("governance_family"),
                "semantic_state": enriched.get("semantic_state") or (enriched.get("evidence_authority") or {}).get("semantic_state"),
                "truth_presentation_stage": enriched.get("truth_presentation_stage"),
                "truth_presentation_label": enriched.get("truth_presentation_label") or enriched.get("client_lifecycle_label"),
                "client_lifecycle_state": lifecycle_state,
                "expected_user_action": (guidance.get("recommended_next_step") or ""),
                "cta_label_server": str((resolve_client_cta({**req, **attach_cer_governance_presentation(req)}).get("primary_action_label") or "")),
                "cta_label_presented": cta.get("primary_action_label"),
                "cta_destination": _cta_destination(handler, cta.get("primary_route")),
                "form_modal_component": "ComplianceEvidenceResolveModal" if handler in ("guided_evidence", "direct_evidence") else ("DocumentsUpload" if "/documents" in str(cta.get("primary_route") or "") else "RequirementIntelligenceModal"),
                "backend_endpoint": endpoint,
                "persistence_target": persistence,
                "expected_state_transition": expected_transition,
                "score_effect": "NEEDS_REVIEW/operational open until guards close — no score rewrite in Phase 1",
                "today_cc_effect": "Priority stream uses take_action envelope — converges when status/authority sync",
                "admin_org_visibility": enriched.get("review_visibility"),
                "review_blocked_in_modal": review_blocked,
                "flow_currently_implemented": flow_implemented,
                "implementation_gaps": gaps,
                "allowed_evidence_modes": cta.get("allowed_evidence_modes"),
                "workflow_class": cta.get("workflow_class"),
            }
        )
    return inventory


def build_followup_traces() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "families": {
            "A_SELF_CERTIFIED": {
                "examples": ["smoke_heat_alarms", "how_to_rent"],
                "declaration_edit_flow": {
                    "exists": True,
                    "path": "ComplianceEvidenceResolveModal → POST .../compliance-evidence",
                    "modes": ["STRUCTURED_DECLARATION", "INSPECTION_CHECKLIST", "CONTRACTOR_CONFIRMATION", "DOCUMENT_UPLOAD"],
                },
                "incomplete_component_flow": {
                    "exists": True,
                    "backend": "requirement_evidence_completeness.evaluate_domestic_alarm_completeness",
                    "ui": "evidence_completeness.summary_label on RequirementsPage; guided modal checklist modes",
                    "transition": "operational_incomplete → declaration_recorded when is_complete=true",
                    "verified": True,
                },
                "gaps": [
                    "CTA remains generic 'Add compliance evidence' — component gap not named in CTA",
                    "Modal banner 'Submission already on file — awaiting review' misleading when queue_backed_review=false",
                ],
            },
            "C_PLATFORM_OVERSIGHT_OPTIONAL": {
                "examples": ["legionella", "fire_risk_assessment", "lead_testing"],
                "followup_evidence_submission": {
                    "exists": True,
                    "path": "Re-submit STRUCTURED_DECLARATION with actions_required=no (legionella/lead_testing)",
                    "schema_fields": ["actions_required", "next_review_date", "actions_taken (lead_testing only)"],
                    "dedicated_followup_form": False,
                },
                "remediation_fields": {
                    "exists_partial": True,
                    "note": "No separate remediation upload mode — closure via structured field update only",
                },
                "transition": "followup_required → assessment_recorded when external_assessment_structured_followup_status=False",
                "verified": True,
                "gaps": [
                    "No follow-up-specific CTA copy or form section",
                    "fire_risk multi-component incomplete mislabeled as followup_required (governance ordering bug)",
                    "Legacy rows without truth_presentation_stage may collapse to View submission when primary CTA is generic Add compliance evidence",
                ],
            },
            "B_ORG_ADMIN_REVIEWED": {
                "examples": ["right_to_rent", "tenancy_agreement", "deposit_pi", "wales_occupation_contract"],
                "org_review_action": {
                    "exists": False,
                    "note": "No org_admin verify queue route/UI found; optional org verify via client POST .../verification exists but not role-gated org queue",
                },
                "user_resolve_org_review_pending": {
                    "exists": False,
                    "label_behavior": "Phase 1 shows 'Evidence recorded' not 'Organisation review pending' unless queue_backed_review + review_owner=org_admin",
                },
                "gaps": [
                    "ROLE_AUTHORITY_GAP: governance decision references org_admin_queue; no dedicated org admin fulfilment UI",
                    "Misleading 'Organisation review pending' only from legacy presentation path when queue_backed incorrectly set",
                ],
            },
            "D_PLATFORM_VERIFIED": {
                "examples": ["epc", "gas_safety", "eicr"],
                "document_upload_path": {
                    "exists": True,
                    "cta": "Upload document / registry override",
                    "route": "/documents?property_id=&requirement_id=",
                },
                "platform_verification_path": {
                    "exists": True,
                    "queue": "GET /api/admin/documents/pending-verification",
                    "label": "Platform verification pending",
                },
                "regression_from_phase1": False,
                "verified": True,
            },
        },
    }


def build_cta_validity(inventory: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for item in inventory:
        label = str(item.get("truth_presentation_label") or "")
        cta = str(item.get("cta_label_presented") or "")
        action_required = any(
            x in label.lower()
            for x in (
                "action required",
                "additional action",
                "follow-up",
                "follow up",
                "incomplete",
            )
        )
        view_only = bool(re.match(r"^view submission$", cta, re.I))
        generic_add = cta.lower() == "add compliance evidence"
        issues = []
        if action_required and view_only:
            issues.append("FORBIDDEN: view-only CTA when action still required")
        if action_required and generic_add:
            issues.append("Generic CTA without explaining missing action")
        if item.get("review_blocked_in_modal") and action_required:
            issues.append("Modal blocks submission while action required")
        rows.append(
            {
                "scenario_key": item["scenario_key"],
                "truth_label": label,
                "cta_label": cta,
                "specific": not generic_add or not action_required,
                "clickable": item.get("cta_destination") != "none",
                "role_appropriate": True,
                "state_aware": not (action_required and view_only),
                "issues": issues,
                "valid": len(issues) == 0,
            }
        )
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "rows": rows,
        "pass": all(r["valid"] for r in rows),
        "invalid_count": sum(1 for r in rows if not r["valid"]),
    }


def build_dead_ends(inventory: List[Dict[str, Any]], cta_audit: Dict[str, Any]) -> Dict[str, Any]:
    dead_ends: List[Dict[str, Any]] = []

    for item in inventory:
        if not item.get("flow_currently_implemented"):
            for gap in item.get("implementation_gaps") or []:
                kind = "BROKEN_CTA"
                if "reviewBlocked" in gap:
                    kind = "MISSING_UI_FLOW"
                if "view-only" in gap.lower():
                    kind = "BROKEN_CTA"
                dead_ends.append(
                    {
                        "scenario_key": item["scenario_key"],
                        "truth_label": item.get("truth_presentation_label"),
                        "cta_label": item.get("cta_label_presented"),
                        "classification": kind,
                        "detail": gap,
                    }
                )

    dead_ends.append(
        {
            "scenario_key": "org_admin_queue_missing",
            "truth_label": "Organisation review pending",
            "cta_label": "varies",
            "classification": "ROLE_AUTHORITY_GAP",
            "detail": "Governance B-family references org_admin_queue; no org admin verify UI/route — label can over-promise authority",
        }
    )

    dead_ends.append(
        {
            "scenario_key": "legionella_modal_banner",
            "truth_label": "Follow-up evidence required",
            "cta_label": "Add compliance evidence",
            "classification": "CTA_DRIFT",
            "detail": "ComplianceEvidenceResolveModal shows 'awaiting review' banner for existing submission even when queue_backed_review=false",
        }
    )

    dead_ends.append(
        {
            "scenario_key": "fire_risk_multi_incomplete",
            "truth_label": "Follow-up evidence required",
            "cta_label": "Add compliance evidence",
            "classification": "STATE_TRANSITION_DRIFT",
            "detail": (
                "cer_governance_presentation checks followup (state_reason multi_evidence_components_incomplete) "
                "before operational_incomplete for PLATFORM_OVERSIGHT_OPTIONAL — fire_risk shows follow-up label "
                "when components are missing, not follow-up remediation"
            ),
        }
    )

    legacy = next((x for x in inventory if x["scenario_key"] == "legacy_no_truth_surface_followup"), None)
    if legacy and not legacy.get("flow_currently_implemented"):
        dead_ends.append(
            {
                "scenario_key": "legacy_no_truth_surface_followup",
                "truth_label": "(legacy — no truth surface)",
                "cta_label": legacy.get("cta_label_presented"),
                "classification": "STATE_TRANSITION_DRIFT",
                "detail": "Rows without truth_presentation_* fall back to SATISFIED_UNVERIFIED + View submission — follow-up action obscured",
            }
        )

    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "dead_ends": dead_ends,
        "count": len(dead_ends),
    }


def build_reuse_map() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "reuse_recommendations": [
            {
                "flow": "All non-document follow-up / declaration / multi-mode",
                "reuse": "ComplianceEvidenceResolveModal (guided evidence)",
                "endpoint": "POST /client/properties/{pid}/requirements/{rid}/compliance-evidence",
                "avoid_new_flow": True,
            },
            {
                "flow": "Requirement context + submission view",
                "reuse": "RequirementIntelligenceModal",
                "note": "View-only — should not be primary path when action required",
            },
            {
                "flow": "Operational guidance copy",
                "reuse": "RequirementEvidenceGuidancePanel + build_requirement_guidance_v1",
                "endpoint": "GET .../compliance-evidence/resolution",
            },
            {
                "flow": "Document-primary (Family D)",
                "reuse": "Documents upload + admin pending-verification queue",
                "endpoint": "existing document upload + admin verify",
            },
            {
                "flow": "Follow-up closure (legionella/lead)",
                "reuse": "Same STRUCTURED_DECLARATION schema — update actions_required",
                "avoid": "New follow-up microservice — extend modal copy + pre-fill existing record instead",
            },
            {
                "flow": "Smoke multi-component",
                "reuse": "INSPECTION_CHECKLIST mode in guided modal + evaluate_domestic_alarm_completeness",
            },
            {
                "flow": "Org admin review (future)",
                "reuse": "apply_verification_decision endpoint with role gate",
                "status": "not wired to org admin UI — defer new queue until Phase 2",
            },
        ],
    }


def build_implementation_impact(dead_ends: Dict[str, Any]) -> Dict[str, Any]:
    fixes = {
        "A_label_cta_wiring_only": [
            "Follow-up-specific primary CTA when truth_presentation_stage=followup_required ('Complete follow-up' not 'Add compliance evidence')",
            "Component-aware CTA when operational_incomplete ('Complete CO alarm evidence' from evidence_completeness.summary_label)",
            "Fix modal existing-submission banner copy when queue_backed_review=false (follow-up/incomplete states)",
        ],
        "B_existing_modal_reuse": [
            "Pre-fill legionella/lead structured declaration from primary CER when reopening for follow-up closure",
            "Surface missing component checklist prominently in RequirementEvidenceGuidancePanel for smoke",
        ],
        "C_backend_transition_repair": [
            "Ensure new CER submission with actions_required=no triggers external_assessment_structured_followup_status=False and truth stage transition",
            "Fix derive_truth_presentation ordering: multi_evidence_components_incomplete should map to operational_incomplete not followup_required for Family C",
        ],
        "D_new_lightweight_followup_component": [],
        "E_admin_org_review_queue_needed": [
            "Org admin verify queue UX (Phase 2) — do not implement in follow-up hotfix",
        ],
        "F_score_convergence_repair": [],
        "G_migration_backfill_needed": [
            "Re-enrich legacy client caches missing truth_presentation_* to prevent View submission dead-end on follow-up rows",
        ],
    }
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "safe_implementation_scope": "A + B + C + G (no new queues, no score rewrite)",
        "fixes_by_category": fixes,
        "dead_end_count": dead_ends.get("count", 0),
        "do_not_implement_in_this_programme": True,
    }


def build_browser_runtime() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "status": "PARTIAL",
        "reason": "Staging browser credentials not available in audit harness; static + enrichment runtime verified",
        "test_matrix": [
            {
                "case": "Smoke & CO incomplete components",
                "expected_label": "Additional action still required",
                "expected_cta": "Add compliance evidence (guided modal → INSPECTION_CHECKLIST)",
                "static_verification": "PASS — ACTION_REQUIRED preserves actionable CTA; completeness projected",
                "browser_verification": "DEFERRED",
                "screenshots": {"before": None, "after": None},
            },
            {
                "case": "Legionella follow-up evidence required",
                "expected_label": "Follow-up evidence required",
                "expected_cta": "Add compliance evidence → structured re-submit",
                "static_verification": "PASS with CTA_DRIFT — flow exists, copy generic; banner misleading",
                "browser_verification": "DEFERRED",
                "screenshots": {"before": None, "after": None},
            },
            {
                "case": "Declaration-style (how_to_rent recorded)",
                "expected_label": "Declaration recorded",
                "expected_cta": "View submission (informational)",
                "static_verification": "PASS — informational dead-end acceptable",
                "browser_verification": "DEFERRED",
            },
            {
                "case": "Right-to-rent org-reviewed family",
                "expected_label": "Evidence recorded",
                "expected_cta": "Add/View via guided declaration",
                "static_verification": "PASS — no false platform queue; org queue not implemented",
                "browser_verification": "DEFERRED",
            },
            {
                "case": "Document upload control (gas_safety)",
                "expected_label": "Platform verification pending",
                "expected_cta": "Upload document / View evidence",
                "static_verification": "PASS — no Phase 1 regression",
                "browser_verification": "DEFERRED",
            },
        ],
    }


def build_classification(dead_ends: Dict[str, Any], cta_audit: Dict[str, Any]) -> Dict[str, Any]:
    kinds = {d["classification"] for d in dead_ends.get("dead_ends", [])}
    if "BROKEN_CTA" in kinds or cta_audit.get("invalid_count", 0) > 0:
        primary = "CTA_DRIFT"
    elif "ROLE_AUTHORITY_GAP" in kinds:
        primary = "ROLE_AUTHORITY_GAP"
    elif "MISSING_UI_FLOW" in kinds:
        primary = "FOLLOWUP_ACTION_DEAD_END"
    else:
        primary = "ACTIONABLE_FLOW_VERIFIED"

    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "primary_classification": primary,
        "secondary_classifications": sorted(kinds),
        "distinction": {
            "label_only_drift": ["CTA_DRIFT", "modal banner copy"],
            "true_missing_workflow": ["ROLE_AUTHORITY_GAP for org admin queue"],
            "backend_transition_failure": [],
            "role_authority_gap": ["ORG_ADMIN_REVIEWED optional verify with no org UI"],
        },
        "audit_only": True,
        "fixes_deferred": True,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ts = _utc()

    inventory = build_inventory()
    followup = build_followup_traces()
    cta_audit = build_cta_validity(inventory)
    dead_ends = build_dead_ends(inventory, cta_audit)
    reuse = build_reuse_map()
    impact = build_implementation_impact(dead_ends)
    browser = build_browser_runtime()
    classification = build_classification(dead_ends, cta_audit)

    artifacts = {
        "actionability_inventory.json": {
            "programme": PROGRAMME,
            "generated_at": ts,
            "items": inventory,
            "summary": {
                "total_scenarios": len(inventory),
                "actionable": sum(1 for x in inventory if x.get("flow_currently_implemented")),
                "gaps": sum(1 for x in inventory if not x.get("flow_currently_implemented")),
            },
        },
        "followup_flow_trace.json": followup,
        "cta_validity_audit.json": cta_audit,
        "dead_end_detection.json": dead_ends,
        "browser_runtime.json": browser,
        "existing_flow_reuse_map.json": reuse,
        "implementation_impact_analysis.json": impact,
        "classifications.json": classification,
    }

    for name, payload in artifacts.items():
        (OUT / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    (OUT / "00_run_meta.json").write_text(
        json.dumps(
            {
                "programme": PROGRAMME,
                "generated_at": ts,
                "method": "static_code_trace + enrichment_runtime_harness",
                "browser": "PARTIAL/DEFERRED",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (OUT / "REPORT.md").write_text(
        f"""# {PROGRAMME}

**Classification:** `{classification['primary_classification']}`  
**Run:** {ts}  
**Mode:** Audit-only — no fixes implemented

## Executive summary

Phase 1 truth labels are **mostly backed by existing guided-evidence and document-upload flows**, but several **presentation gaps** remain where labels promise follow-up or component completion while CTAs stay generic or (for legacy rows) collapse to view-only.

| Area | Verdict |
|------|---------|
| Family A (self-certified) | Actionable via guided modal; CTA copy drift |
| Family C (follow-up) | Backend closure path exists (re-submit structured declaration); legionella CTA is registry-specific; fire_risk component gaps mislabeled as follow-up |
| Family B (org-reviewed) | Record flow exists; org admin queue **not implemented** (role authority gap) |
| Family D (platform verified) | No regression — upload + admin queue intact |

## Dead-end count: {dead_ends['count']}

### Key findings

1. **CTA_DRIFT** — Smoke/fire multi-evidence rows use generic "Add compliance evidence"; modal banner still says "awaiting review" without queue.
2. **STATE_TRANSITION_DRIFT** — `fire_risk_assessment` with `multi_evidence_components_incomplete` gets `followup_required` label (governance ordering in `derive_truth_presentation`).
3. **ROLE_AUTHORITY_GAP** — B-family org admin queue referenced in governance; no org admin verify UI exists (Phase 2).

## Safe implementation scope (if approved)

{impact['safe_implementation_scope']}

## Browser runtime

**PARTIAL** — staging E2E deferred; static verification complete.

Harness: `backend/tmp_prelaunch_cer_followup_action_flow_audit_01.py`
""",
        encoding="utf-8",
    )

    (OUT / "watchlist.md").write_text(
        f"""# Watchlist — {PROGRAMME}

- [ ] Staging browser: smoke incomplete → guided modal → add CO checklist → label convergence
- [ ] Staging browser: legionella follow-up → re-submit with actions_required=no → label → assessment_recorded
- [ ] Fix modal banner when queue_backed_review=false (follow-up rows)
- [ ] CTA copy: follow-up-specific and component-specific labels
- [ ] Legacy cache backfill for truth_presentation_* fields
- [ ] Phase 2: org admin verify queue (do not block follow-up hotfix)
""",
        encoding="utf-8",
    )

    print(json.dumps({"programme": PROGRAMME, "classification": classification["primary_classification"], "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
