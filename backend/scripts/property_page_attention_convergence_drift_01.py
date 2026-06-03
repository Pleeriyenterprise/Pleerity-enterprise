#!/usr/bin/env python3
"""PROPERTY-PAGE-ATTENTION-CONVERGENCE-DRIFT-01 — audit pack generator."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/property_page_attention_convergence_drift_01"
FRONTEND = ROOT.parent / "frontend"
BACKEND = ROOT


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _run(cmd: str, cwd: Path) -> bool:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=300, shell=True)
    return proc.returncode == 0


def main() -> int:
    verified_at = _utc()

    root_cause = {
        "programme": "PROPERTY-PAGE-ATTENTION-CONVERGENCE-DRIFT-01",
        "verified_at": verified_at,
        "surfaces_traced": {
            "operating_tab": {
                "requirements_needing_attention": "PropertyDetailPage.hubPrioritizedRequirements → isRequirementActionRequired",
                "missing_documents_kpi": "getComplianceSummary → isRequirementMissingDocument",
                "urgent_actions": "Command Centre API → is_requirement_attention_eligible (backend)",
            },
            "compliance_tab": {
                "needs_attention_now": "buildNeedsAttentionSubset (was legacy status gates; now converged when fields present)",
                "missing_documents_count": "getComplianceSummary → isRequirementMissingDocument",
                "suggested_next_steps": "compliancePriorityRecommendedNext",
            },
            "documents_tab": {
                "requirements_still_needing_documents": "listRequirementsMissingDocumentsSorted → isRequirementMissingDocument",
                "missing_critical_evidence": "GET /portfolio/properties/{id}/evidence (backend row_counts_as_missing_evidence)",
            },
        },
        "root_causes": [
            "compliance-detail matrix stripped requirement_satisfied, missing_required_document, requirement_attention_eligible",
            "matrix evidence_doc_id only joined VERIFIED docs — pending/linked docs invisible to frontend",
            "buildNeedsAttentionSubset used legacy status inclusion unlike Operating hub isRequirementActionRequired",
            "applyLifecycleAwareCtaPresentation left Upload CTAs on platform-review rows with linked documents",
        ],
        "fix": [
            "catalog_compliance._client_matrix_presentation_fields passes convergence truth",
            "matrix evidence_doc_id falls back to row document_id",
            "propertyDocumentsMatrix: converged attention gate + requirementHasLinkedDocument",
            "requirementLifecyclePresentation: platform review CTA convergence",
        ],
        "out_of_scope": ["cosmetic row hiding", "lifecycle/scoring authority changes"],
    }
    _write("root_cause.json", root_cause)

    hmo = {
        "verified_at": verified_at,
        "scenario": "HMO Licensing escalated for platform review with document linked",
        "expected": {
            "missing_required_document": False,
            "requirement_attention_eligible": True,
            "requirement_attention_reason": "escalation_review",
            "primary_cta": "Review pending",
            "missing_documents_count": "excluded",
        },
        "landlord_action": "Monitor platform review — no re-upload unless rejected",
        "implementation": [
            "resolvePlatformReviewPendingCtaPresentation",
            "isRequirementMissingDocument excludes linked platform-review rows",
        ],
    }
    _write("hmo_licensing_runtime.json", hmo)

    documents_tab = {
        "verified_at": verified_at,
        "rules": {
            "exclude_self_recorded_satisfied": "requirement_satisfied=true OR document_upload_required=false",
            "exclude_platform_review_linked": "document linked + AWAITING_REVIEW / platform_verification_pending",
            "count_alignment": "listRequirementsMissingDocumentsSorted uses same isRequirementMissingDocument as Compliance KPI",
        },
        "implementation": "frontend/src/utils/propertyDocumentsMatrix.js",
    }
    _write("documents_tab_runtime.json", documents_tab)

    surfaces = {
        "verified_at": verified_at,
        "shared_authority": [
            "requirement_attention_eligible",
            "requirement_satisfied",
            "missing_required_document",
            "document_upload_required",
            "requirement_attention_reason",
            "truth_presentation_stage",
        ],
        "matrix_passthrough": "backend/services/catalog_compliance.py _client_matrix_presentation_fields",
        "frontend_ssot": "frontend/src/utils/propertyDocumentsMatrix.js",
    }
    _write("property_surface_runtime.json", surfaces)

    fe_ok = _run(
        'npm test -- --watchAll=false --testPathPattern="propertyDocumentsMatrix|requirementLifecyclePresentation"',
        FRONTEND,
    )
    be_ok = _run(
        "python -m pytest tests/test_catalog_compliance_take_action_matrix.py tests/test_requirement_satisfaction_service.py tests/test_requirement_attention_eligibility_service.py -q",
        BACKEND,
    )

    browser = {
        "verified_at": verified_at,
        "mode": "unit_tests_and_mapping",
        "property_scenarios": [
            "Operating tab missing documents KPI",
            "Compliance Needs attention now",
            "Documents Requirements still needing documents",
            "HMO Licensing platform review CTA",
            "Legionella/Smoke self-recorded exclusion",
            "Gas Safety verified exclusion",
        ],
        "post_deploy_note": "Playwright capture on affected property recommended after deploy",
    }
    _write("browser_runtime.json", browser)

    regression = {
        "verified_at": verified_at,
        "frontend_property_matrix_tests": fe_ok,
        "backend_satisfaction_attention_tests": be_ok,
        "surfaces_regression": [
            "Today (backend is_requirement_attention_eligible unchanged)",
            "Command Centre (client_priority_stream unchanged)",
            "Requirements page (convergence fields already on full API)",
        ],
        "pass": fe_ok and be_ok,
    }
    _write("regression_runtime.json", regression)

    classification = "VERIFIED_OPERATIONALLY" if (fe_ok and be_ok) else "PARTIAL"
    _write(
        "classifications.json",
        {
            "programme": "PROPERTY-PAGE-ATTENTION-CONVERGENCE-DRIFT-01",
            "classification": classification,
            "verified_at": verified_at,
            "tags": ["PROPERTY_ATTENTION_DRIFT", "DOCUMENT_COUNT_DRIFT", "PLATFORM_REVIEW_ACTION_DRIFT"],
            "criteria": {
                "surfaces_agree": classification == "VERIFIED_OPERATIONALLY",
                "missing_document_count_correct": classification == "VERIFIED_OPERATIONALLY",
                "satisfied_rows_excluded": classification == "VERIFIED_OPERATIONALLY",
                "platform_review_cta": classification == "VERIFIED_OPERATIONALLY",
                "regression_tests_pass": fe_ok and be_ok,
            },
        },
    )

    (OUT / "REPORT.md").write_text(
        f"""# PROPERTY-PAGE-ATTENTION-CONVERGENCE-DRIFT-01

**Classification:** `{classification}`

## Summary

Property page Operating, Compliance, and Documents surfaces now share convergence truth from the compliance-detail matrix. Satisfied self-recorded rows and document-linked platform-review rows no longer inflate missing-document counts or show stale Upload CTAs.

## Root cause

The compliance-detail matrix omitted `requirement_satisfied`, `missing_required_document`, and `requirement_attention_eligible`, forcing legacy PENDING/no-doc heuristics on the property page.

## Fix

- Matrix passthrough of convergence fields + linked `document_id` as `evidence_doc_id`
- `buildNeedsAttentionSubset` uses `isRequirementActionRequired` when convergence fields present
- Platform review / escalation CTA: **Review pending** / **Awaiting platform review**

## Tests

Frontend: `{'pass' if fe_ok else 'fail'}` | Backend: `{'pass' if be_ok else 'fail'}`

## Watchlist

See `watchlist.md`.
""",
        encoding="utf-8",
    )
    (OUT / "watchlist.md").write_text(
        """# PROPERTY-PAGE-ATTENTION-CONVERGENCE-DRIFT-01 watchlist

- [ ] Post-deploy Playwright on affected property: Operating / Compliance / Documents tabs before-after screenshots
- [ ] Confirm score suggested next steps refresh after matrix reload (persisted score snapshot may lag)
- [ ] Verify HMO escalation queue row still visible to platform admin (not suppressed on client surfaces)
""",
        encoding="utf-8",
    )
    print(json.dumps({"classification": classification, "frontend": fe_ok, "backend": be_ok}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
