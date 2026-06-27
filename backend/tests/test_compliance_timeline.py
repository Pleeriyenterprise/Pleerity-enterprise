"""COMPLIANCE-TIMELINE-CURRENT-TRUTH-IMPLEMENTATION-01 tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from services.compliance_timeline import (
    AUTHORITY_AI_EXTRACTED,
    AUTHORITY_SYSTEM_ESTIMATE,
    AUTHORITY_UNKNOWN,
    AUTHORITY_USER_CONFIRMED,
    AUTHORITY_VERIFIED_DOCUMENT,
    build_compliance_timeline,
    calculate_compliance_timeline,
)
from services.compliance_evidence_record_service import EVIDENCE_MODE_STRUCTURED_DECLARATION
from services.requirement_evidence_authority import EA_VERIFIED_CURRENT
from services.requirement_truth import (
    DATE_SOURCE_SYSTEM_ESTIMATED,
    DATE_SOURCE_USER_PROVIDED,
    enrich_requirement_dict,
)


def _req(**kwargs):
    base = {
        "requirement_id": "req-1",
        "client_id": "c1",
        "property_id": "p1",
        "applicability": "REQUIRED",
        "status": "PENDING",
    }
    base.update(kwargs)
    return base


def _verified_gas(**overrides):
    expiry = (datetime.now(timezone.utc) + timedelta(days=180)).date().isoformat()
    ea = {
        "version": 1,
        "state": EA_VERIFIED_CURRENT,
        "effective_expiry_date": f"{expiry}T00:00:00+00:00",
        "effective_expiry_is_null": False,
        "effective_verified_document_id": "doc-primary",
        "expiry_source": "VERIFIED_DOCUMENT",
    }
    row = _req(
        requirement_type="gas_safety",
        requirement_code="gas_safety",
        evidence_authority=ea,
        evidence_authority_synced_at=datetime.now(timezone.utc).isoformat(),
        due_date=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        date_source=DATE_SOURCE_SYSTEM_ESTIMATED,
    )
    row.update(overrides)
    return row


def test_gas_safety_verified_certificate_expiry():
    row = _verified_gas()
    tl = calculate_compliance_timeline(row)
    assert tl["primary_date_source"] == AUTHORITY_VERIFIED_DOCUMENT
    assert tl["is_verified"] is True
    assert tl["is_estimated"] is False
    assert tl["primary_date_concept"] == "certificate_expiry"
    assert tl["expiry_date"] == tl["primary_date"]
    assert "Certificate expires" in tl["primary_date_label"]
    assert tl["timeline_category"] == "certificate_lifecycle"


def test_epc_ai_extracted_unverified():
    extracted = (datetime.now(timezone.utc) + timedelta(days=120)).isoformat()
    row = _req(
        requirement_type="epc",
        extracted_expiry_date=extracted,
        expiry_source="EXTRACTED",
        due_date=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        date_source=DATE_SOURCE_SYSTEM_ESTIMATED,
    )
    tl = calculate_compliance_timeline(row)
    assert tl["primary_date_source"] == AUTHORITY_AI_EXTRACTED
    assert tl["is_ai_extracted"] is True
    assert tl["is_verified"] is False
    assert tl["is_estimated"] is False


def test_eicr_user_confirmed_expiry():
    confirmed = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
    row = _req(
        requirement_type="eicr",
        confirmed_expiry_date=confirmed,
        expiry_source="CONFIRMED",
        date_source=DATE_SOURCE_USER_PROVIDED,
    )
    tl = calculate_compliance_timeline(row)
    assert tl["primary_date_source"] == AUTHORITY_USER_CONFIRMED
    assert tl["is_customer_supplied"] is True
    assert tl["is_verified"] is False


def test_legionella_assessment_and_next_review():
    assessment = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    next_review = (datetime.now(timezone.utc) + timedelta(days=700)).date().isoformat()
    cer = {
        "evidence_record_id": "cer-leg",
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
        "evidence_payload": {
            "structured_fields": {
                "assessment_date": {"answer": assessment},
                "next_review_date": {"answer": next_review},
            }
        },
    }
    row = _req(requirement_type="legionella", due_date=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat())
    tl = calculate_compliance_timeline(row, compliance_evidence_records=[cer])
    assert tl["timeline_category"] == "assessment_lifecycle"
    assert tl["primary_date"] == next_review
    assert tl["primary_date_concept"] == "next_assessment_due"
    assert tl["assessment_date"] == assessment
    assert tl["expiry_date"] is None


def test_smoke_heat_co_no_false_expiry():
    event = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
    cer = {
        "evidence_record_id": "cer-smoke",
        "verification_status": "VERIFIED",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
        "evidence_payload": {"structured_fields": {"event_date": {"answer": event}}},
    }
    row = _req(
        requirement_type="smoke_heat_alarms",
        due_date=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        date_source=DATE_SOURCE_SYSTEM_ESTIMATED,
    )
    tl = calculate_compliance_timeline(row, compliance_evidence_records=[cer])
    assert tl["expiry_date"] is None
    assert tl["primary_date"] == event
    assert tl["primary_date_concept"] == "event_date"
    assert tl["timeline_category"] == "event_lifecycle"


def test_tenancy_agreement_timeline():
    start = "2025-01-01"
    end = "2026-01-01"
    row = _req(
        requirement_type="tenancy_agreement",
        structured_declaration={"tenancy_start_date": start, "fixed_term_end_date": end},
    )
    tl = calculate_compliance_timeline(row)
    assert tl["timeline_category"] == "tenancy_lifecycle"
    assert tl["primary_date"] == start
    assert tl["tenancy_end_date"] == end
    assert tl["expiry_date"] is None


def test_how_to_rent_delivery_timeline():
    delivery = "2025-06-15"
    row = _req(
        requirement_type="how_to_rent",
        structured_declaration={"delivery_date": delivery},
    )
    tl = calculate_compliance_timeline(row)
    assert tl["timeline_category"] == "declaration_lifecycle"
    assert tl["primary_date"] == delivery
    assert "Guide delivery date" in tl["primary_date_label"]
    assert tl["expiry_date"] is None


def test_rent_smart_wales_registration_timeline():
    reg = "2024-03-01"
    next_rev = "2027-03-01"
    row = _req(
        requirement_type="rent_smart_wales",
        structured_declaration={"registration_date": reg, "next_review_date": next_rev},
    )
    tl = calculate_compliance_timeline(row)
    assert tl["timeline_category"] == "registration_lifecycle"
    assert tl["primary_date"] == reg
    assert tl["primary_date_concept"] == "registration_date"


def test_lead_testing_assessment_follow_up():
    assessment = "2025-02-01"
    follow_up = "2027-02-01"
    cer = {
        "evidence_record_id": "cer-lead",
        "verification_status": "PENDING",
        "included_in_active_compliance": True,
        "archived": False,
        "evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
        "evidence_payload": {
            "structured_fields": {
                "assessment_date": {"answer": assessment},
                "follow_up_date": {"answer": follow_up},
            }
        },
    }
    row = _req(requirement_type="lead_testing")
    tl = calculate_compliance_timeline(row, compliance_evidence_records=[cer])
    assert tl["primary_date"] == follow_up
    assert tl["assessment_date"] == assessment


def test_warning_days_due_date_is_estimated_not_authoritative():
    estimate_due = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    row = _req(
        requirement_type="gas_safety",
        due_date=estimate_due,
        date_source=DATE_SOURCE_SYSTEM_ESTIMATED,
    )
    tl = calculate_compliance_timeline(row)
    assert tl["primary_date_source"] == AUTHORITY_SYSTEM_ESTIMATE
    assert tl["is_estimated"] is True
    assert tl["primary_date_concept"] == "estimated_compliance_date"
    assert "Estimated compliance date" in tl["primary_date_label"]
    assert "renewal" not in tl["primary_date_label"].lower()


def test_verified_authority_beats_stale_estimate():
    verified_expiry = (datetime.now(timezone.utc) + timedelta(days=200)).date().isoformat()
    estimate_due = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    row = _verified_gas(due_date=estimate_due, date_source=DATE_SOURCE_SYSTEM_ESTIMATED)
    row["evidence_authority"]["effective_expiry_date"] = f"{verified_expiry}T00:00:00+00:00"
    tl = calculate_compliance_timeline(row)
    assert tl["primary_date"] == verified_expiry
    assert tl["primary_date_source"] == AUTHORITY_VERIFIED_DOCUMENT
    assert tl["is_estimated"] is False


def test_null_date_unknown():
    row = _req(requirement_type="gas_safety")
    tl = calculate_compliance_timeline(row)
    assert tl["primary_date"] is None
    assert tl["primary_date_source"] == AUTHORITY_UNKNOWN
    assert tl["primary_date_label"] == "No date on file"
    assert tl["timeline_reason"] == "no_authoritative_date"


def test_supporting_document_does_not_alter_timeline_authority():
    supporting_extracted = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    row = _verified_gas(
        extracted_expiry_date=supporting_extracted,
        expiry_source="EXTRACTED",
    )
    authority_expiry = row["evidence_authority"]["effective_expiry_date"][:10]
    tl = calculate_compliance_timeline(row)
    assert tl["primary_date"] == authority_expiry
    assert tl["primary_date_source"] == AUTHORITY_VERIFIED_DOCUMENT
    assert tl["primary_date"] != supporting_extracted[:10]


def test_enrich_adds_compliance_timeline_fields():
    row = _verified_gas()
    enriched = enrich_requirement_dict(row, live_evidence_state="VERIFIED", audience="client")
    assert "compliance_timeline" in enriched
    assert enriched["timeline_primary_date"] == enriched["compliance_timeline"]["primary_date"]
    assert enriched["timeline_primary_date_label"] == enriched["compliance_timeline"]["primary_date_label"]
    assert enriched["date_label"] is not None
    assert enriched.get("due_date") == row.get("due_date")


def test_timeline_does_not_mutate_requirement_input():
    row = _verified_gas()
    original_due = row["due_date"]
    calculate_compliance_timeline(row)
    assert row["due_date"] == original_due


def test_reminder_start_date_separate_from_primary():
    verified_expiry = (datetime.now(timezone.utc) + timedelta(days=60)).date().isoformat()
    row = _verified_gas()
    row["evidence_authority"]["effective_expiry_date"] = f"{verified_expiry}T00:00:00+00:00"
    tl = calculate_compliance_timeline(row, reminder_days_before=30)
    assert tl["reminder_window_days"] == 30
    assert tl["reminder_start_date"] is not None
    assert tl["reminder_start_date"] != tl["primary_date"]


def test_hmo_fire_risk_hybrid_expiry():
    expiry = (datetime.now(timezone.utc) + timedelta(days=365)).date().isoformat()
    row = _req(
        requirement_type="hmo_fire_risk",
        confirmed_expiry_date=f"{expiry}T00:00:00+00:00",
        expiry_source="CONFIRMED",
        date_source=DATE_SOURCE_USER_PROVIDED,
    )
    tl = calculate_compliance_timeline(row)
    assert tl["timeline_category"] == "hybrid_lifecycle"
    assert tl["expiry_date"] == expiry


def test_deposit_protection_declaration():
    protection = "2025-04-01"
    row = _req(
        requirement_type="deposit_pi",
        structured_declaration={"protection_date": protection},
    )
    tl = calculate_compliance_timeline(row)
    assert tl["primary_date"] == protection
    assert tl["expiry_date"] is None


def test_build_compliance_timeline_alias():
    row = _req(requirement_type="gas_safety")
    assert build_compliance_timeline(row) == calculate_compliance_timeline(row)


def test_timeline_service_does_not_invoke_scoring_or_mutate_row():
    """Phase 1 guard: timeline calculator is read-only; scoring migration is Phase 2."""
    row = _verified_gas()
    snapshot = dict(row)
    with patch(
        "services.compliance_scoring_service.recalculate_and_persist",
        new_callable=AsyncMock,
    ) as mock_recalc:
        calculate_compliance_timeline(row)
        mock_recalc.assert_not_called()
    assert row == snapshot


def test_pat_certificate_lifecycle():
    confirmed = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
    row = _req(
        requirement_type="portable_appliance_test",
        confirmed_expiry_date=confirmed,
        expiry_source="CONFIRMED",
    )
    tl = calculate_compliance_timeline(row)
    assert tl["timeline_category"] == "certificate_lifecycle"
    assert tl["primary_date_source"] == AUTHORITY_USER_CONFIRMED
