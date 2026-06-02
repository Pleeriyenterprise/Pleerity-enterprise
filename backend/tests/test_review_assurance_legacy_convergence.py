"""REVIEW-ASSURANCE-POST-DEPLOY-CLEANUP-01 legacy convergence tests."""
from __future__ import annotations

from services.cer_governance_presentation import ASSURANCE_SELF_RECORDED, cognition_next_step_for_requirement
from services.review_assurance_legacy_convergence import (
    CLASS_HARMLESS,
    CLASS_MIGRATABLE,
    CLASS_ORPHANED,
    audit_legacy_org_review_batch,
    classify_legacy_org_review_artifact,
    normalize_legacy_truth_stage,
)


def test_normalize_legacy_org_stage():
    assert normalize_legacy_truth_stage("org_verification_pending") == "declaration_recorded"


def test_legacy_org_admin_raw_row_migratable_at_enrich():
    row = {
        "requirement_type": "right_to_rent",
        "governance_family": "ORG_ADMIN_REVIEWED",
        "review_owner": "org_admin",
        "queue_backed_review": True,
        "evidence_authority": {
            "state": "UPLOADED_UNCONFIRMED",
            "primary_evidence_record_id": "cer-1",
        },
    }
    assert classify_legacy_org_review_artifact(row) == CLASS_MIGRATABLE


def test_clean_self_recorded_harmless():
    row = {
        "requirement_type": "deposit_pi",
        "evidence_authority": {
            "state": "UPLOADED_UNCONFIRMED",
            "primary_evidence_record_id": "cer-d",
        },
    }
    from services.cer_governance_presentation import attach_cer_governance_presentation

    enriched = attach_cer_governance_presentation(row)
    assert enriched["assurance_tier"] == ASSURANCE_SELF_RECORDED
    assert classify_legacy_org_review_artifact(enriched) == CLASS_HARMLESS


def test_cognition_org_stage_compat_wording():
    title, subline, steps = cognition_next_step_for_requirement(
        {"truth_presentation_stage": "org_verification_pending"}
    )
    assert "Organisation" not in title
    assert "Recorded on file" in title
    assert steps == []


def test_audit_batch_no_forbidden_phrases():
    rows = [
        {
            "requirement_type": "right_to_rent",
            "evidence_authority": {
                "primary_evidence_record_id": "x",
                "state": "UPLOADED_UNCONFIRMED",
            },
        }
    ]
    audit = audit_legacy_org_review_batch(rows)
    assert audit["pass"] is True
    assert audit["counts"][CLASS_ORPHANED] == 0
