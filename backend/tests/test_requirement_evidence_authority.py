"""Unit tests for requirement evidence authority projection and scope rules."""
from datetime import datetime, timezone, timedelta

import pytest

from models import DocumentStatus, RequirementStatus
from services.requirement_evidence_authority import (
    EA_EXTRACTION_PENDING_CONFIRMATION,
    EA_MISMATCH_FLAGGED,
    EA_MISSING,
    EA_REJECTED,
    EA_VERIFIED_CURRENT,
    EA_VERIFIED_EXPIRED,
    SCOPE_INTAKE_STAGING,
    SCOPE_PORTFOLIO,
    SCOPE_PROPERTY,
    document_evidence_compatible_with_requirement,
    normalize_document_evidence_scope,
    preview_authority,
)


def _req(**kwargs):
    base = {
        "requirement_id": "r1",
        "client_id": "c1",
        "property_id": "p1",
        "applicability": "REQUIRED",
        "requirement_type": "GAS_SAFETY_CERT",
    }
    base.update(kwargs)
    return base


def _doc(**kwargs):
    base = {
        "document_id": "d1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "status": DocumentStatus.UPLOADED.value,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_scope_type": SCOPE_PROPERTY,
        "evidence_scope_id": "p1",
        "authoritative_property_id": "p1",
    }
    base.update(kwargs)
    return base


def test_normalize_property_scope():
    out = normalize_document_evidence_scope(property_id="p1", client_id="c1", evidence_scope_type="PROPERTY")
    assert out["evidence_scope_type"] == SCOPE_PROPERTY
    assert out["authoritative_property_id"] == "p1"
    assert out["property_id"] == "p1"


def test_normalize_portfolio_scope():
    out = normalize_document_evidence_scope(property_id=None, client_id="c1", evidence_scope_type="PORTFOLIO")
    assert out["evidence_scope_type"] == SCOPE_PORTFOLIO
    assert out["property_id"] is None


def test_normalize_intake_staging_requires_session():
    with pytest.raises(ValueError):
        normalize_document_evidence_scope(property_id=None, client_id="", evidence_scope_type="INTAKE_STAGING")
    out = normalize_document_evidence_scope(
        property_id=None,
        client_id="",
        evidence_scope_type="INTAKE_STAGING",
        intake_session_id="sess-1",
    )
    assert out["evidence_scope_type"] == SCOPE_INTAKE_STAGING
    assert out["evidence_scope_id"] == "sess-1"


def test_property_mismatch_not_compatible_with_requirement():
    doc = _doc(property_id="p2", authoritative_property_id="p2", evidence_scope_id="p2")
    assert document_evidence_compatible_with_requirement(doc, _req()) is False


def test_portfolio_doc_not_compatible_with_property_requirement():
    doc = _doc(
        property_id=None,
        authoritative_property_id=None,
        evidence_scope_type=SCOPE_PORTFOLIO,
        evidence_scope_id="c1",
    )
    assert document_evidence_compatible_with_requirement(doc, _req()) is False


def test_preview_missing_no_docs():
    out = preview_authority(_req(), [])
    assert out["evidence_authority"]["state"] == EA_MISSING


def test_preview_rejected_only():
    out = preview_authority(_req(), [_doc(status=DocumentStatus.REJECTED.value)])
    assert out["evidence_authority"]["state"] == EA_REJECTED


def test_preview_verified_expired():
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    out = preview_authority(
        _req(),
        [
            _doc(
                status=DocumentStatus.VERIFIED.value,
                expiry_date=past,
            )
        ],
    )
    assert out["evidence_authority"]["state"] == EA_VERIFIED_EXPIRED


def test_preview_verified_current():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    out = preview_authority(_req(), [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=fut)])
    assert out["evidence_authority"]["state"] == EA_VERIFIED_CURRENT


def test_preview_verified_current_naive_iso_string_expiry_mirror_days_no_typeerror():
    """Naive ISO strings (no offset) must normalize to UTC before (eff_expiry - now).days."""
    fut = datetime.now(timezone.utc) + timedelta(days=200)
    naive_str = fut.strftime("%Y-%m-%dT%H:%M:%S")
    out = preview_authority(_req(), [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=naive_str)])
    assert out["evidence_authority"]["state"] == EA_VERIFIED_CURRENT
    assert out["mirror"]["status"] in (
        RequirementStatus.COMPLIANT.value,
        RequirementStatus.EXPIRING_SOON.value,
    )


def test_preview_verified_current_timezone_aware_datetime_expiry():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).replace(microsecond=0)
    aware = fut.astimezone(timezone.utc)
    out = preview_authority(_req(), [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=aware)])
    assert out["evidence_authority"]["state"] == EA_VERIFIED_CURRENT
    assert out["mirror"]["status"] in (
        RequirementStatus.COMPLIANT.value,
        RequirementStatus.EXPIRING_SOON.value,
    )


def test_preview_pending_with_extraction():
    out = preview_authority(
        _req(),
        [_doc(status=DocumentStatus.PENDING.value, extraction_status="extracted")],
    )
    assert out["evidence_authority"]["state"] == EA_EXTRACTION_PENDING_CONFIRMATION


def test_preview_scope_mismatch_flags():
    bad = _doc(
        document_id="d2",
        property_id=None,
        authoritative_property_id=None,
        evidence_scope_type=SCOPE_PORTFOLIO,
        evidence_scope_id="c1",
    )
    out = preview_authority(_req(), [bad])
    assert out["evidence_authority"]["state"] == EA_MISMATCH_FLAGGED


def test_condition_standard_verified_document_stays_pending_when_operational_followup_open():
    fut = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    req = _req(
        requirement_type="fitness_for_human_habitation",
        requirement_code="fitness_for_human_habitation",
        active_standard_status_summary={
            "state": "active_issues_present",
            "signal_counts": {
                "open_issues": 1,
                "open_work_orders": 1,
                "open_risk_signals": 0,
                "open_compliance_gaps": 1,
            },
            "read_only": True,
        },
    )
    out = preview_authority(
        req,
        [
            _doc(
                status=DocumentStatus.VERIFIED.value,
                expiry_date=fut,
            )
        ],
        evidence_records=[],
    )
    assert out["evidence_authority"]["effective_verified_document_id"] == "d1"
    assert out["evidence_authority"]["state"] == "UPLOADED_UNCONFIRMED"
    assert out["evidence_authority"]["state_reason"] == "operational_followup_required_condition_standard"
    assert out["mirror"]["status"] == RequirementStatus.PENDING.value
