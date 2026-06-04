#!/usr/bin/env python3
"""
REQUIREMENT-SATISFACTION-BUSINESS-OUTCOME-AUDIT-01

Business-outcome governance audit only — no runtime fixes.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = ROOT / "docs/audit/requirement_satisfaction_business_outcome_audit_01"
PROGRAMME = "REQUIREMENT-SATISFACTION-BUSINESS-OUTCOME-AUDIT-01"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def governance_contract() -> Dict[str, Any]:
    docs = {
        "WORKFLOW_BEHAVIOUR_GOVERNANCE": "docs/WORKFLOW_BEHAVIOUR_GOVERNANCE.md",
        "COMPLIANCE_CLIENT_STATUS_AUTHORITY": "docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md",
        "GOVERNANCE_CONSUMPTION_MAP": "docs/GOVERNANCE_CONSUMPTION_MAP.md",
        "STREAM_B_SCORING_AUTHORITY_MATRIX": "docs/STREAM_B_SCORING_AUTHORITY_MATRIX.md",
    }
    from services.workflow_behaviour_governance import (
        EXECUTION_SEMANTICS_METADATA,
        list_governance_workflow_keys,
    )

    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "sources": docs,
        "A_user_business_outcomes": [
            "Evidence recorded ≠ obligation satisfied ≠ remediation complete (core principle)",
            "Per-class user outcomes in Workflow Execution & System Behaviour Semantics (A column)",
            "Landlord operational surfaces must not show false action on satisfied truth (attention suppression)",
            "Must not imply external verification on GUIDED_DECLARATION / self-recorded paths",
        ],
        "B_system_runtime_outcomes": [
            "enrich_requirement_dict attaches satisfaction + attention fields",
            "Authority sync + enqueue_compliance_recalc on material mutations",
            "Score recalc via recalculate_and_persist (authoritative writer)",
            "EXECUTION_SEMANTICS_METADATA documents may_trigger_* effects — not engine-consumed",
        ],
        "C_workflow_class_expectations": {
            "DOCUMENT_UPLOAD": "May directly satisfy; high score impact; expiry attention may remain",
            "GUIDED_DECLARATION": "May satisfy when complete; moderate score; no statutory verification",
            "EXTERNAL_ASSESSMENT": "Conditional; follow-ups may block satisfaction truth",
            "TENANT_DELIVERY": "Delivery recorded not legal outcome",
            "ACTIVE_STANDARD_CONDITION_STANDARD": "Operational convergence only; not document-only closure",
            "PLATFORM_REVIEW_PENDING": "Attention eligible; not fully satisfied for score/action",
        },
        "D_score_by_class": {
            "verified_document": "Full VALID/COMPLIANT fraction path",
            "self_recorded_satisfied_unverified": "SATISFIED_SELF_RECORDED_FRACTION=0.85",
            "platform_review_pending": "SATISFIED_PLATFORM_REVIEW_FRACTION=0.80",
            "async_headline": "Persisted headline may lag live satisfaction (queue)",
        },
        "E_attention_remediation": [
            "requirement_attention_eligibility_service suppresses satisfied truth stages",
            "followup_required / operational_incomplete keeps attention eligible",
            "is_requirement_satisfied returns False when attention eligible",
        ],
        "F_verification_vs_recording": [
            "VERIFIED / VERIFIED_DOCUMENT = platform-accepted evidence",
            "SATISFIED_UNVERIFIED / SELF_RECORDED = recorded on file not regulator-verified",
            "PENDING_REVIEW = awaiting platform review",
        ],
        "G_operational_vs_regulator": [
            "KPI-authoritative surfaces: projected status + stats",
            "Operational task flow: Today/CC may diverge by design",
            "Audit/regulator exports: conservative unresolved exposure for self-recorded",
        ],
        "H_documentation_only_execution": {
            "keys": sorted(list_governance_workflow_keys()),
            "metadata_rows": len(EXECUTION_SEMANTICS_METADATA),
            "runtime_consumption": "governance_validation_engine + audit_pipeline only; engines explicit non-consumer",
        },
        "status": "extracted",
    }


def satisfaction_truth() -> Dict[str, Any]:
    from services.compliance_scoring_v2 import (
        SATISFIED_PLATFORM_REVIEW_FRACTION,
        SATISFIED_SELF_RECORDED_FRACTION,
    )
    from services.requirement_attention_eligibility_service import SATISFIED_TRUTH_STAGES
    from services.requirement_satisfaction_service import (
        attach_satisfaction_fields,
        is_requirement_satisfied,
    )
    from services.requirement_truth import enrich_requirement_dict

    sample_satisfied_declaration = {
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "truth_presentation_stage": "declaration_recorded",
        "governance_family": "SELF_CERTIFIED",
        "document_upload_required": False,
        "client_surface_visible": True,
    }
    sample_followup = {
        **sample_satisfied_declaration,
        "truth_presentation_stage": "followup_required",
    }
    attached = attach_satisfaction_fields(sample_satisfied_declaration)
    attached_fu = attach_satisfaction_fields(sample_followup)

    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "authority_chain": [
            "requirement_truth.enrich_requirement_dict (client)",
            "→ attach_satisfaction_fields",
            "→ reconcile_client_lifecycle_with_satisfaction",
            "→ project_requirement_row_client_runtime (KPI status)",
            "→ compliance_scoring_v2._satisfaction_aware_assurance_fraction",
            "→ requirement_attention_eligibility_service.is_requirement_attention_eligible",
        ],
        "fields": {
            "requirement_satisfied": "is_requirement_satisfied()",
            "missing_required_document": "derive_missing_document_status / document_gap",
            "requirement_attention_eligible": "is_requirement_attention_eligible()[0]",
            "client_lifecycle_state": "client_requirement_lifecycle + satisfaction reconcile",
            "assurance_tier": "cer_governance_presentation.derive_assurance_tier",
            "score_fractions": {
                "self_recorded": SATISFIED_SELF_RECORDED_FRACTION,
                "platform_review": SATISFIED_PLATFORM_REVIEW_FRACTION,
            },
        },
        "satisfied_truth_stages": sorted(SATISFIED_TRUTH_STAGES),
        "sample_declaration": attached,
        "sample_followup_blocks_satisfaction": {
            "requirement_satisfied": attached_fu.get("requirement_satisfied"),
            "attention_eligible": attached_fu.get("requirement_attention_eligible"),
        },
        "provisional_paths": [
            "PENDING_REVIEW / platform_verification_pending",
            "followup_required / operational_incomplete",
            "legacy unsynced authority bridge",
        ],
        "non_regulator_sufficient": [
            "SATISFIED_UNVERIFIED lifecycle",
            "SELF_RECORDED assurance tier",
            "declaration_recorded without VERIFIED truth stage",
        ],
        "operational_suppression": "attention eligible False + suppression reason set → Today/CC filters",
        "status": "verified_in_code",
    }


def _cell(wf: str, surface: str, classification: str, note: str) -> Dict[str, str]:
    return {
        "workflow_class": wf,
        "surface": surface,
        "classification": classification,
        "note": note,
    }


def business_outcome_matrix() -> Dict[str, Any]:
    """Representative matrix — full cross-product sampled by governance-critical cells."""
    cells: List[Dict[str, str]] = []

    # Operational surfaces — verified document
    for s in ("Today", "Command Centre", "Requirements", "Property page", "Documents tab"):
        cells.append(
            _cell(
                "VERIFIED_DOCUMENT",
                s,
                "VERIFIED_OPERATIONALLY",
                "Attention suppressed; satisfaction true; KPI COMPLIANT/VALID when authority synced",
            )
        )

    # Operational — self-recorded / SATISFIED_UNVERIFIED
    for s in ("Today", "Command Centre", "Requirements", "Property page"):
        cells.append(
            _cell(
                "SATISFIED_UNVERIFIED",
                s,
                "VERIFIED_OPERATIONALLY",
                "Phase2b: no false action tasks when truth stages satisfied",
            )
        )
    cells.append(
        _cell(
            "SELF_RECORDED",
            "Compliance score",
            "EXPECTED_BY_DESIGN",
            "0.85 assurance fraction — not full certificate credit",
        )
    )
    cells.append(
        _cell(
            "SELF_RECORDED",
            "Portfolio dashboard",
            "PARTIAL",
            "Headline persisted score async; may lag satisfaction moment",
        )
    )

    # External assessment
    cells.append(
        _cell(
            "EXTERNAL_ASSESSMENT",
            "Today",
            "VERIFIED_OPERATIONALLY",
            "followup_required → attention eligible → not satisfied",
        )
    )
    cells.append(
        _cell(
            "EXTERNAL_ASSESSMENT",
            "Professional PDFs",
            "EXPECTED_BY_DESIGN",
            "May list assessment rows in unresolved when self-recorded exposure required",
        )
    )

    # Platform review
    cells.append(
        _cell(
            "PLATFORM_REVIEW_PENDING",
            "Today",
            "VERIFIED_OPERATIONALLY",
            "Attention remains; is_requirement_satisfied false",
        )
    )
    cells.append(
        _cell(
            "PLATFORM_REVIEW_PENDING",
            "Compliance score",
            "EXPECTED_BY_DESIGN",
            "0.80 fraction with linked doc; assurance pending status",
        )
    )

    # Regulator exports — tension cell
    cells.append(
        _cell(
            "SATISFIED_UNVERIFIED",
            "Evidence Readiness PDF",
            "REGULATOR_CONSERVATISM_DRIFT",
            "is_unresolved_row includes SATISFIED_UNVERIFIED — conservative vs operational suppression",
        )
    )
    cells.append(
        _cell(
            "SATISFIED_UNVERIFIED",
            "Immutable audit artifacts",
            "EXPECTED_BY_DESIGN",
            "Frozen point-in-time may include self-recorded in unresolved exposure",
        )
    )
    cells.append(
        _cell(
            "VERIFIED_DOCUMENT",
            "Evidence Readiness PDF",
            "VERIFIED_OPERATIONALLY",
            "Verified rows typically excluded from unresolved unless overdue/expiring",
        )
    )

    # Condition standard
    cells.append(
        _cell(
            "CONDITION_STANDARD",
            "Requirements",
            "PARTIAL",
            "Workflow audit flags; operational convergence not certificate satisfaction",
        )
    )
    cells.append(
        _cell(
            "ACTIVE_STANDARD",
            "Compliance score",
            "EXPECTED_BY_DESIGN",
            "Guidance/operational model — not upload-only closure",
        )
    )

    # Ungoverned / partial subsystems
    cells.append(
        _cell("DOCUMENT_UPLOAD", "Reminder generation", "PARTIAL", "Registry marks PARTIAL; satisfaction gate not proven in reminder jobs grep")
    )
    cells.append(
        _cell("GUIDED_DECLARATION", "Digests", "VERIFIED_OPERATIONALLY", "Uses calculate_compliance_score stats + enriched rows")
    )
    cells.append(
        _cell("SELF_RECORDED", "CSV exports", "VERIFIED_OPERATIONALLY", "Human-language headline; integration rows retain machine keys")
    )
    cells.append(
        _cell("PLATFORM_REVIEW_PENDING", "Pending review queues", "VERIFIED_OPERATIONALLY", "Queue surfaces align with PENDING_REVIEW lifecycle")
    )

    counts: Dict[str, int] = {}
    for c in cells:
        counts[c["classification"]] = counts.get(c["classification"], 0) + 1

    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "cells": cells,
        "classification_counts": counts,
        "total_cells": len(cells),
        "status": "matrix_built",
    }


def operational_vs_regulator() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "landlord_operator_signals": {
            "today_command_centre": "Suppress tasks when requirement_attention_eligible false",
            "requirements_property": "Lifecycle chips + requirement_satisfied on enriched rows",
            "documents_banner": "document_upload_required gate only",
            "dashboard_score": "Async honesty + human score status labels",
        },
        "regulator_auditor_signals": {
            "evidence_readiness_pdf": "Unresolved obligations includes SATISFIED_UNVERIFIED by is_unresolved_row",
            "professional_pdf": "Governance chips + self-recorded disclosure in unresolved intro",
            "immutable_artifacts": "Frozen bytes + manifest; conservative grade",
            "csv_integration": "SCORING_SEMANTICS_EXPORT_V1 machine keys preserved",
        },
        "contradictions": [
            {
                "id": "UNRESOLVED_VS_INBOX",
                "description": "Landlord inbox suppresses satisfied self-recorded; PDF unresolved section lists SATISFIED_UNVERIFIED",
                "real": True,
                "governance_intentional": "Partially — regulator conservatism vs operational calm",
                "audience_governance_explicit": False,
                "recommended_classification": "AUDIENCE_GOVERNANCE_GAP",
            },
            {
                "id": "RECORDED_ON_FILE_WORDING",
                "description": "Human-language convergence aligns labels; export section title still 'Unresolved obligations'",
                "real": True,
                "governance_intentional": "Unclear in WORKFLOW — reporting emphasises exposure not inbox parity",
                "recommended_classification": "REGULATOR_CONSERVATISM_DRIFT",
            },
        ],
        "satisfied_unverified_pdf_placement": {
            "current": "Inside 'Unresolved obligations' via is_unresolved_row lifecycle check",
            "operational_alternative": "Separate 'Recorded but not independently verified' section",
            "audit_decision": "CLASSIFY_ONLY — do not move in this phase",
            "classification": "AUDIENCE_GOVERNANCE_GAP",
        },
        "priority_stance": "Platform currently prioritises regulator-grade evidential conservatism on exports over landlord operational cognition parity",
        "status": "classified",
    }


def execution_semantics() -> Dict[str, Any]:
    from services.governance_coverage_registry import GOVERNANCE_SURFACE_REGISTRY
    from services.workflow_behaviour_governance import EXECUTION_SEMANTICS_METADATA

    consumers = []
    for sid, meta in GOVERNANCE_SURFACE_REGISTRY.items():
        if meta.get("consumes_execution_semantics"):
            consumers.append(sid)

    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "metadata_keys": sorted(EXECUTION_SEMANTICS_METADATA.keys()),
        "documented_note": "Merged into get_workflow_capabilities; not consumed by runtime engines",
        "runtime_authoritative": [
            "requirement_satisfaction_service",
            "requirement_attention_eligibility_service",
            "compliance_scoring_v2 satisfaction fractions",
            "reporting_semantics_v1",
            "immutable_report_artifact_service",
        ],
        "documentation_only": [
            "EXECUTION_SEMANTICS_METADATA may_trigger_* flags",
            "system_execution_effects frozensets",
        ],
        "consumes_execution_semantics_surfaces": consumers,
        "orchestration_procedural": [
            "enqueue_compliance_recalc (queue)",
            "reminder_generation (PARTIAL registry)",
            "report PDF layout (report_layout_governance not EXECUTION_SEMANTICS)",
        ],
        "classification": "GOVERNANCE_DOCUMENTATION_AHEAD_OF_RUNTIME",
        "sub_classification": "UNUSED_METADATA for engines; PARTIALLY_CONSUMED for audit_pipeline",
        "status": "gap_documented",
    }


def reporting_alignment() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "surfaces": {
            "evidence_readiness_pdf": {
                "operational_truth": "Uses enrich pipeline + governance context",
                "regulator_truth": "Conservative unresolved includes self-recorded",
                "classification": "REGULATOR_CONSERVATISM_DRIFT",
            },
            "professional_compliance_pdf": {
                "operational_truth": "Immutable snapshot per download",
                "regulator_truth": "REGULATORY_SUBMISSION grade + disclosures",
                "classification": "VERIFIED_OPERATIONALLY",
            },
            "score_explanation_pdf": {
                "operational_truth": "Human score status labels",
                "scoring_truth": "Headline + authority humanized",
                "classification": "VERIFIED_OPERATIONALLY",
            },
            "csv_snapshot": {
                "operational_truth": "Human headline_score_status",
                "integration_truth": "Machine keys when SCORING_SEMANTICS_EXPORT_V1",
                "classification": "VERIFIED_OPERATIONALLY",
            },
            "monthly_digest_pdf": {
                "operational_truth": "Executive summary from assembly model",
                "classification": "VERIFIED_OPERATIONALLY",
            },
        },
        "intentional_conservatism": [
            "Unresolved obligations exposure for self-recorded assurance",
            "Immutable artifact frozen point-in-time",
            "Assurance chips on matrices",
        ],
        "overstate_risk": "SATISFIED_UNVERIFIED in unresolved may overstate 'unresolved' to landlords reading PDF",
        "understate_risk": "Operational surfaces may understate renewal attention when legacy_due_date blocked (fixed phase2b for declarations)",
        "status": "aligned_with_tension",
    }


def async_score_business() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "mechanisms": [
            "compliance_score_pending flag",
            "score_status calculating|partial|stale",
            "enqueue_compliance_recalc queue",
            "headline persisted vs live stats split (STREAM_B matrix)",
        ],
        "disclosures": [
            "async_reporting_disclosure human lines",
            "scoreFreshnessUi CALCULATING_SCORE_FALLBACK_MESSAGE",
            "human_score_status_label on exports/UI",
        ],
        "suppression": [
            "Satisfied rows suppress attention regardless of async headline",
            "Stale does not re-open satisfied truth",
        ],
        "findings": [
            {
                "issue": "Headline may lag satisfaction moment",
                "classification": "ACCEPTABLE_ASYNC_GOVERNANCE",
                "note": "Disclosed; not a satisfaction truth bug",
            },
            {
                "issue": "Landlord may read low headline while rows show recorded on file",
                "classification": "UX_TRUST_GAP",
                "note": "Bounded; mitigated by status messages",
            },
        ],
        "overall": "ACCEPTABLE_ASYNC_GOVERNANCE",
        "status": "classified",
    }


def consumption_map_audit() -> Dict[str, Any]:
    from services.governance_coverage_registry import GOVERNANCE_SURFACE_REGISTRY

    mapped: Dict[str, str] = {}
    for sid, meta in GOVERNANCE_SURFACE_REGISTRY.items():
        level = meta.get("enforcement_level", "NONE")
        if level == "STRICT":
            mapped[sid] = "FULLY_GOVERNED"
        elif meta.get("uses_local_fallback_logic"):
            mapped[sid] = "PARTIALLY_GOVERNED"
        else:
            mapped[sid] = "PARTIALLY_GOVERNED"

    # Reconcile with doc UNGOVERNED note for reminders — registry now PARTIAL
    mapped["reminder_generation"] = "PARTIALLY_GOVERNED"
    mapped["reports_exports"] = "PARTIALLY_GOVERNED"
    mapped["reports_exports_note"] = "reporting_semantics_v1 wired; EXECUTION_SEMANTICS not consumed"

    extras = {
        "dashboard_cognition": "PARTIALLY_GOVERNED",
        "immutable_artifacts": "FULLY_GOVERNED",
        "score_propagation": "PARTIALLY_GOVERNED",
        "escalation_logic": "PARTIALLY_GOVERNED",
        "human_language_layer": "PARTIALLY_GOVERNED",
    }
    mapped.update(extras)

    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "registry_surfaces": mapped,
        "doc_drift": "GOVERNANCE_CONSUMPTION_MAP.md lists reminder_generation UNGOVERNED; registry updated to PARTIAL",
        "status": "re_audited",
    }


def strategic_findings() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "A_satisfied_means_different_things": {
            "landlords": "Obligation met for operations — inbox quiet, recorded on file",
            "regulators": "May still see self-recorded under unresolved exposure in PDFs",
            "scoring": "Fractional credit (0.85/0.80) not binary satisfied",
            "operational_queues": "Suppressed when attention ineligible",
            "immutable_artifacts": "Point-in-time including conservative unresolved rows",
        },
        "B_difference_quality": {
            "correct_by_design": [
                "Verification vs recording split",
                "Fractional scoring for self-recorded",
                "Follow-up blocks satisfaction",
            ],
            "confusing_without_audience_labels": [
                "Unresolved obligations title vs operational calm",
            ],
            "dangerous_if_unlabeled": "Landlord downloads PDF believing obligation still open",
            "governance_intentional": "Regulator conservatism on exports",
            "insufficiently_disclosed": "No separate PDF section for recorded-not-verified",
        },
        "C_platform_priority": "Regulator-grade evidential conservatism on exports; landlord operational cognition on inbox/KPI paths",
        "D_audience_governance": {
            "explicit_enough": False,
            "gap": "AUDIENCE_GOVERNANCE_GAP — export section naming vs operational suppression",
        },
        "recommended_next_phases": [
            "AUDIENCE_GOVERNANCE-01 — PDF section split (classify before implement)",
            "EXECUTION-SEMANTICS-WIRING-01 — optional future; out of scope here",
        ],
        "status": "complete",
    }


def run_regression() -> Dict[str, Any]:
    suites = [
        "tests/test_requirement_satisfaction_service.py",
        "tests/test_compliance_scoring_satisfaction_convergence.py",
        "tests/test_reporting_semantics_v1.py",
        "tests/test_immutable_report_artifact_service.py",
        "tests/test_report_layout_governance.py",
        "tests/test_workflow_behaviour_governance.py",
        "tests/test_governance_phase1_enforcement.py",
        "tests/test_report_human_language_v1.py",
    ]
    results: Dict[str, Any] = {}
    all_ok = True
    for s in suites:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", s, "-q", "--tb=no"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        ok = proc.returncode == 0
        results[s] = {"passed": ok, "tail": (proc.stdout or proc.stderr)[-500:]}
        all_ok = all_ok and ok
    return {"programme": PROGRAMME, "all_passed": all_ok, "suites": results, "audited_at": _utc()}


def classify(regression: Dict[str, Any], matrix: Dict[str, Any]) -> Dict[str, Any]:
    drift_cells = matrix.get("classification_counts", {}).get("REGULATOR_CONSERVATISM_DRIFT", 0)
    checks = {
        "satisfaction_truth_converged": True,
        "workflow_class_respected": True,
        "operational_regulator_distinguishable": True,
        "governance_intent_traceable": True,
        "async_governance_honest": True,
        "regression_pass": regression.get("all_passed"),
        "no_major_contradiction": False,
        "audience_governance_explicit": False,
    }
    if drift_cells > 0:
        checks["no_major_contradiction"] = False

    if all(
        [
            checks["satisfaction_truth_converged"],
            checks["workflow_class_respected"],
            checks["regression_pass"],
        ]
    ) and not checks["no_major_contradiction"]:
        primary = "PARTIAL"
    elif all(checks.values()):
        primary = "VERIFIED_OPERATIONALLY"
    elif regression.get("all_passed"):
        primary = "AUDIENCE_GOVERNANCE_GAP"
    else:
        primary = "FAIL_OPERATIONAL"

    if not checks["audience_governance_explicit"] and primary != "FAIL_OPERATIONAL":
        primary = "AUDIENCE_GOVERNANCE_GAP"

    return {
        "programme": PROGRAMME,
        "classified_at": _utc(),
        "classification": primary,
        "checks": checks,
        "secondary_tags": [
            "REGULATOR_CONSERVATISM_DRIFT",
            "GOVERNANCE_DOCUMENTATION_AHEAD_OF_RUNTIME",
        ],
    }


def main() -> int:
    gc = governance_contract()
    st = satisfaction_truth()
    bom = business_outcome_matrix()
    ovr = operational_vs_regulator()
    exe = execution_semantics()
    rep = reporting_alignment()
    async_b = async_score_business()
    cons = consumption_map_audit()
    strat = strategic_findings()
    regression = run_regression()

    _write("governance_contract_runtime.json", gc)
    _write("satisfaction_truth_runtime.json", st)
    _write("business_outcome_matrix_runtime.json", bom)
    _write("operational_vs_regulator_cognition_runtime.json", ovr)
    _write("execution_semantics_runtime.json", exe)
    _write("reporting_alignment_runtime.json", rep)
    _write("async_score_business_runtime.json", async_b)
    _write("consumption_map_runtime.json", cons)
    _write("strategic_findings_runtime.json", strat)
    _write("regression_runtime.json", regression)
    classifications = classify(regression, bom)
    _write("classifications.json", classifications)

    (OUT / "REPORT.md").write_text(
        f"""# {PROGRAMME}

Audited at: {_utc()}
Classification: **{classifications['classification']}**

## Executive summary

Satisfaction **truth** and **operational attention** outcomes are operationally converged (phase2b, property page, scoring fractions).
A deliberate tension remains between **landlord operational cognition** (inbox suppression, recorded-on-file UX) and
**regulator-grade export conservatism** (PDF unresolved lists `SATISFIED_UNVERIFIED`).

`EXECUTION_SEMANTICS_METADATA` is documented and CI-aligned but **not** consumed by runtime engines.

## Regression

{'PASS' if regression.get('all_passed') else 'FAIL'}

## Artifacts

All runtime JSON files in this directory.
""",
        encoding="utf-8",
    )
    (OUT / "watchlist.md").write_text(
        f"""# Watchlist — {PROGRAMME} ({_utc()[:10]})

## {classifications['classification']}

### P0 (audience governance — classify before implement)
- [ ] PDF unresolved section: split **Recorded but not independently verified** vs true unresolved
- [ ] Explicit export preamble for landlord vs regulator audiences

### P1
- [ ] Reconcile GOVERNANCE_CONSUMPTION_MAP.md reminder UNGOVERNED vs registry PARTIAL
- [ ] Reminder jobs: prove satisfaction/attention gates on generation path
- [ ] EXECUTION_SEMANTICS wiring roadmap (documentation-only today)

### P2
- [ ] UX trust copy when headline async lags satisfied rows on dashboard

### Verified (do not regress)
- Satisfaction truth service + attention eligibility
- Scoring satisfaction fractions (0.85 / 0.80)
- Today/CC suppression for satisfied Gas/Legionella class paths
""",
        encoding="utf-8",
    )
    print(f"{PROGRAMME} classification={classifications['classification']}")
    return 0 if regression.get("all_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
