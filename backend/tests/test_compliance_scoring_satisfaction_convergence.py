"""Tests for satisfaction-aware compliance scoring convergence."""
from datetime import datetime, timezone

from services.compliance_scoring_v2 import (
    ESTIMATED_DATE_LEGAL_CORE_MULTIPLIER,
    STATUS_ASSURANCE_PENDING,
    STATUS_SATISFIED_UNVERIFIED,
    SATISFIED_SELF_RECORDED_FRACTION,
    compute_property_score_v2,
)
from services.requirement_evidence_authority import (
    AUTHORITY_VERSION,
    EA_PENDING_ADMIN_REVIEW,
    EA_UPLOADED_UNCONFIRMED,
)


def _base_property():
    return {
        "property_id": "p1",
        "jurisdiction": "England",
        "cert_gas_safety": "NO",
        "has_gas_supply": False,
    }


def _needs_review_req(**extra):
    base = {
        "requirement_code": "LEGIONELLA",
        "requirement_satisfied": True,
        "missing_required_document": False,
        "document_upload_required": False,
        "truth_presentation_stage": "assessment_recorded",
        "satisfaction_source": "self_certified_record",
        "governance_family": "SELF_CERTIFIED",
        "evidence_authority": {
            "version": AUTHORITY_VERSION,
            "state": EA_UPLOADED_UNCONFIRMED,
        },
        "evidence_authority_synced_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(extra)
    return base


def test_satisfied_self_recorded_uses_assurance_fraction_not_missing():
    now = datetime.now(timezone.utc)
    result = compute_property_score_v2(
        property_doc=_base_property(),
        client_doc={"default_jurisdiction": "England"},
        requirements=[_needs_review_req()],
        documents=[],
        open_issues_count=0,
        overdue_work_orders_count=0,
        open_risks_count=0,
        as_of=now,
    )
    leg = next(r for r in result["requirement_breakdown"] if r["requirement_code"] == "LEGIONELLA")
    assert leg["status"] == STATUS_SATISFIED_UNVERIFIED
    expected = round(10.0 * SATISFIED_SELF_RECORDED_FRACTION * ESTIMATED_DATE_LEGAL_CORE_MULTIPLIER, 2)
    assert leg["earned_points"] == expected
    assert leg["earned_points"] > round(10.0 * 0.5, 2)


def test_platform_review_pending_with_linked_doc_assurance_pending():
    now = datetime.now(timezone.utc)
    req = _needs_review_req(
        requirement_code="FIRE_DETECTION",
        document_id="doc-1",
        truth_presentation_stage="platform_verification_pending",
        satisfaction_source="platform_verification",
        evidence_authority={
            "version": AUTHORITY_VERSION,
            "state": EA_PENDING_ADMIN_REVIEW,
        },
    )
    result = compute_property_score_v2(
        property_doc=_base_property(),
        client_doc={"default_jurisdiction": "England"},
        requirements=[req],
        documents=[{"document_id": "doc-1", "document_type": "fire_safety", "status": "PENDING_REVIEW"}],
        open_issues_count=0,
        overdue_work_orders_count=0,
        open_risks_count=0,
        as_of=now,
    )
    fire = next(r for r in result["requirement_breakdown"] if r["requirement_code"] == "FIRE_DETECTION")
    assert fire["status"] == STATUS_ASSURANCE_PENDING
    fire_actions = [a for a in result["top_next_actions"] if a["requirement_code"] == "FIRE_DETECTION"]
    assert fire_actions
    assert "Upload and verify" not in fire_actions[0]["action"]
    assert "awaiting platform verification" in fire_actions[0]["action"].lower()


def test_top_actions_never_upload_for_satisfied_unverified():
    now = datetime.now(timezone.utc)
    result = compute_property_score_v2(
        property_doc=_base_property(),
        client_doc={"default_jurisdiction": "England"},
        requirements=[_needs_review_req(requirement_code="LEGIONELLA")],
        documents=[],
        open_issues_count=0,
        overdue_work_orders_count=0,
        open_risks_count=0,
        as_of=now,
    )
    leg_actions = [a for a in result["top_next_actions"] if a["requirement_code"] == "LEGIONELLA"]
    assert leg_actions
    assert "Upload and verify" not in leg_actions[0]["action"]


def test_documentation_bucket_counts_satisfied_non_verified():
    now = datetime.now(timezone.utc)
    result = compute_property_score_v2(
        property_doc=_base_property(),
        client_doc={"default_jurisdiction": "England"},
        requirements=[_needs_review_req()],
        documents=[],
        open_issues_count=0,
        overdue_work_orders_count=0,
        open_risks_count=0,
        as_of=now,
    )
    docs_pct = result["bucket_breakdown"]["documentation_completeness"]["percent"]
    assert docs_pct > 0
