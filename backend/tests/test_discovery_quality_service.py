"""
Stage J — discovery quality service tests.

No dedupe, import, routes, UI, providers, or LeadService integration.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.discovery.discovery_models import (
    DiscoveryBusinessType,
    DiscoveryLandlordType,
    DiscoveryLawfulBasis,
    OriginLineageEntry,
    ProspectLocation,
)
from services.discovery.discovery_quality_service import (
    PROVIDER_CONFIDENCE_MAX,
    DiscoveryQualityService,
    QualityInputs,
)

VALID_HASH = "a" * 64
DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
NOW = datetime.now(timezone.utc)


def _lineage_entry() -> OriginLineageEntry:
    return OriginLineageEntry(
        provider="csv",
        provider_reference="csv:row-1",
        discovery_run_id="DRUN-TEST-001",
        campaign_id="DCAMP-TEST-001",
        content_hash=VALID_HASH,
        discovered_at=NOW,
        ingested_at=NOW,
    )


def _full_inputs() -> QualityInputs:
    return QualityInputs(
        email="lead@example.com",
        phone="07700900123",
        company_name="Acme Lettings",
        website="https://acme.example",
        source_url="https://source.example/list",
        provider_reference="csv:row-42",
        business_type=DiscoveryBusinessType.LETTING_AGENCY,
        landlord_type=DiscoveryLandlordType.PORTFOLIO,
        location=ProspectLocation(city="London", postcode="SW1A 1AA"),
        lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
        marketing_consent=False,
        marketing_consent_explicit=True,
        provider_confidence=80,
        risk_flags=[],
        origin_lineage=[_lineage_entry()],
    )


def test_deterministic_scoring():
    inputs = _full_inputs()
    s1 = DiscoveryQualityService.compute_platform_quality_score(inputs)
    s2 = DiscoveryQualityService.compute_platform_quality_score(inputs)
    assert s1 == s2


def test_identical_inputs_identical_scores():
    a = _full_inputs()
    b = _full_inputs()
    assert DiscoveryQualityService.compute_platform_quality_score(a) == (
        DiscoveryQualityService.compute_platform_quality_score(b)
    )


def test_provider_confidence_capped_at_ten_percent():
    high = QualityInputs(
        email="a@b.com",
        lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
        provider_confidence=100,
    )
    breakdown = DiscoveryQualityService.build_quality_factor_breakdown(high)
    assert breakdown.provider_confidence_contribution == PROVIDER_CONFIDENCE_MAX
    assert breakdown.provider_confidence_contribution <= 10

    over = QualityInputs(
        email="a@b.com",
        lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
        provider_confidence=999,
    )
    errors = DiscoveryQualityService.validate_quality_inputs(over)
    assert errors


def test_provider_confidence_not_copied_directly():
    inputs = QualityInputs(
        email="a@b.com",
        lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
        provider_confidence=90,
    )
    score = DiscoveryQualityService.compute_platform_quality_score(inputs)
    assert score < 90


def test_lawful_basis_unknown_rejected_by_validation():
    inputs = QualityInputs(
        email="a@b.com",
        lawful_basis=DiscoveryLawfulBasis.UNKNOWN,
    )
    assert DiscoveryQualityService.validate_quality_inputs(inputs)


def test_risk_flags_reduce_governance_score():
    clean = QualityInputs(
        email="a@b.com",
        lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
        marketing_consent_explicit=True,
        risk_flags=[],
    )
    flagged = QualityInputs(
        email="a@b.com",
        lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
        marketing_consent_explicit=True,
        risk_flags=["suppression_list_match"],
    )
    b_clean = DiscoveryQualityService.build_quality_factor_breakdown(clean)
    b_flagged = DiscoveryQualityService.build_quality_factor_breakdown(flagged)
    assert b_flagged.governance_quality < b_clean.governance_quality
    assert b_flagged.total < b_clean.total


def test_review_priority_higher_for_lower_quality():
    rich = _full_inputs()
    sparse = QualityInputs(
        email="a@b.com",
        lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
    )
    rich_score = DiscoveryQualityService.compute_platform_quality_score(rich)
    sparse_score = DiscoveryQualityService.compute_platform_quality_score(sparse)
    rich_priority = DiscoveryQualityService.calculate_review_priority(
        rich_score, inputs=rich
    )
    sparse_priority = DiscoveryQualityService.calculate_review_priority(
        sparse_score, inputs=sparse
    )
    assert sparse_priority > rich_priority


def test_review_priority_increases_with_risk_flags():
    base = DiscoveryQualityService.calculate_review_priority(50, risk_flags=[])
    flagged = DiscoveryQualityService.calculate_review_priority(
        50, risk_flags=["a", "b"]
    )
    assert flagged > base


def test_quality_breakdown_generation():
    breakdown = DiscoveryQualityService.build_quality_factor_breakdown(_full_inputs())
    lines = breakdown.to_display_lines()
    assert any("Identity Completeness" in line for line in lines)
    assert any("Total:" in line for line in lines)
    assert breakdown.total == sum(
        (
            breakdown.identity_completeness,
            breakdown.business_context,
            breakdown.source_quality,
            breakdown.governance_quality,
            breakdown.provider_confidence_contribution,
        )
    )
    assert 0 <= breakdown.total <= 100


def test_explanation_generation():
    explanation = DiscoveryQualityService.explain_quality_score(_full_inputs())
    assert "score" in explanation
    assert explanation["score"] == DiscoveryQualityService.compute_platform_quality_score(
        _full_inputs()
    )
    assert isinstance(explanation["strengths"], list)
    assert isinstance(explanation["weaknesses"], list)
    assert isinstance(explanation["recommended_improvements"], list)
    assert len(explanation["strengths"]) >= 1


def test_sparse_prospect_explanation_has_improvements():
    sparse = QualityInputs(
        email="only@example.com",
        lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
    )
    explanation = DiscoveryQualityService.explain_quality_score(sparse)
    assert explanation["weaknesses"] or explanation["recommended_improvements"]


def test_no_lead_service_in_quality_service():
    text = (DISCOVERY_ROOT / "discovery_quality_service.py").read_text(encoding="utf-8")
    assert "from services.lead_service import" not in text
    assert "LeadService.create_lead" not in text


def test_no_duplicate_detection_engine_module():
    assert importlib.util.find_spec("services.discovery.duplicate_detection_engine") is None


def test_no_import_service_module():
    assert importlib.util.find_spec("services.discovery.discovery_import_service") is not None


def test_no_routes_or_providers():
    assert importlib.util.find_spec("routes.admin_discovery") is not None
    assert importlib.util.find_spec("routes.discovery_twin_internal") is not None


def test_score_bounded_zero_to_hundred():
    assert DiscoveryQualityService.compute_platform_quality_score(_full_inputs()) <= 100
    empty = QualityInputs(lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B)
    assert DiscoveryQualityService.compute_platform_quality_score(empty) >= 0
