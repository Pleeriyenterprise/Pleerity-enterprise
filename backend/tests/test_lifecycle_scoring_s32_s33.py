"""Phase 3 S3.2 + S3.3 — lifecycle-aware scoring shadow telemetry and active gates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.compliance_scoring_v2 import (
    ESTIMATED_DATE_LEGAL_CORE_MULTIPLIER,
    SATISFIED_SELF_RECORDED_FRACTION,
    STATUS_SATISFIED_UNVERIFIED,
    compute_property_score_v2,
)
from services.customer_status_projector_v2 import project_customer_status
from services.document_status_service import STATUS_NEEDS_REVIEW, STATUS_TO_FRACTION
from services.lifecycle_aware_scoring_config import get_effective_scoring_mode
from services.requirement_evidence_authority import AUTHORITY_VERSION, EA_UPLOADED_UNCONFIRMED


def _base_property():
    return {
        "property_id": "p1",
        "jurisdiction": "England",
        "cert_gas_safety": "YES",
        "has_gas_supply": True,
    }


def _legionella_satisfied_req(**extra):
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
    }
    base.update(extra)
    return base


class TestLifecycleScoringShadow:
    def test_shadow_logs_divergence_for_review_based_due_date(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        now = datetime.now(timezone.utc)
        due = (now + timedelta(days=15)).date().isoformat()
        result = compute_property_score_v2(
            property_doc=_base_property(),
            client_doc={"default_jurisdiction": "England"},
            requirements=[
                {
                    "requirement_code": "LEGIONELLA",
                    "status": "COMPLIANT",
                    "due_date": due,
                }
            ],
            documents=[],
            open_issues_count=0,
            overdue_work_orders_count=0,
            open_risks_count=0,
            as_of=now,
        )
        leg = next(r for r in result["requirement_breakdown"] if r["requirement_code"] == "LEGIONELLA")
        assert leg["status"] == "EXPIRING_SOON"
        assert get_effective_scoring_mode() == "shadow"
        assert "lifecycle_scoring_shadow_complete" in caplog.text
        assert "lifecycle_scoring_shadow_divergence" in caplog.text

    def test_shadow_keeps_legacy_fraction_authoritative(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        now = datetime.now(timezone.utc)
        due = (now + timedelta(days=15)).date().isoformat()
        req = [{"requirement_code": "LEGIONELLA", "status": "COMPLIANT", "due_date": due}]
        shadow = compute_property_score_v2(
            property_doc=_base_property(),
            client_doc={"default_jurisdiction": "England"},
            requirements=req,
            documents=[],
            open_issues_count=0,
            overdue_work_orders_count=0,
            open_risks_count=0,
            as_of=now,
        )
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "off")
        off = compute_property_score_v2(
            property_doc=_base_property(),
            client_doc={"default_jurisdiction": "England"},
            requirements=req,
            documents=[],
            open_issues_count=0,
            overdue_work_orders_count=0,
            open_risks_count=0,
            as_of=now,
        )
        assert shadow["score_0_100"] == off["score_0_100"]
        shadow_leg = next(
            r for r in shadow["requirement_breakdown"] if r["requirement_code"] == "LEGIONELLA"
        )
        off_leg = next(r for r in off["requirement_breakdown"] if r["requirement_code"] == "LEGIONELLA")
        assert shadow_leg["earned_points"] == off_leg["earned_points"]


class TestLifecycleScoringActiveGates:
    def _active_preview(self, monkeypatch) -> None:
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")

    def test_active_suppresses_review_based_due_date_expiring_soon(self, monkeypatch):
        self._active_preview(monkeypatch)
        now = datetime.now(timezone.utc)
        due = (now + timedelta(days=15)).date().isoformat()
        result = compute_property_score_v2(
            property_doc=_base_property(),
            client_doc={"default_jurisdiction": "England"},
            requirements=[
                {"requirement_code": "LEGIONELLA", "status": "COMPLIANT", "due_date": due}
            ],
            documents=[],
            open_issues_count=0,
            overdue_work_orders_count=0,
            open_risks_count=0,
            as_of=now,
        )
        leg = next(r for r in result["requirement_breakdown"] if r["requirement_code"] == "LEGIONELLA")
        assert leg["status"] == "VALID"
        assert leg["earned_points"] > 7.0

    def test_active_gas_missing_expiry_still_needs_review_penalty(self, monkeypatch):
        self._active_preview(monkeypatch)
        now = datetime.now(timezone.utc)
        docs = [
            {
                "requirement_code": "GAS_SAFETY",
                "document_type": "gas_safety",
                "status": "VERIFIED",
            }
        ]
        result = compute_property_score_v2(
            property_doc=_base_property(),
            client_doc={"default_jurisdiction": "England"},
            requirements=[],
            documents=docs,
            open_issues_count=0,
            overdue_work_orders_count=0,
            open_risks_count=0,
            as_of=now,
        )
        gas = next(r for r in result["requirement_breakdown"] if r["requirement_code"] == "GAS_SAFETY")
        assert gas["status"] == STATUS_NEEDS_REVIEW
        assert gas["earned_points"] == pytest.approx(15.0 * STATUS_TO_FRACTION[STATUS_NEEDS_REVIEW])

    def test_active_legionella_satisfied_at_least_point_eight_fraction(self, monkeypatch):
        self._active_preview(monkeypatch)
        now = datetime.now(timezone.utc)
        result = compute_property_score_v2(
            property_doc=_base_property(),
            client_doc={"default_jurisdiction": "England"},
            requirements=[_legionella_satisfied_req()],
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

    def test_off_mode_unchanged_for_review_based_due_date(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "off")
        now = datetime.now(timezone.utc)
        due = (now + timedelta(days=15)).date().isoformat()
        result = compute_property_score_v2(
            property_doc=_base_property(),
            client_doc={"default_jurisdiction": "England"},
            requirements=[
                {"requirement_code": "LEGIONELLA", "status": "COMPLIANT", "due_date": due}
            ],
            documents=[],
            open_issues_count=0,
            overdue_work_orders_count=0,
            open_risks_count=0,
            as_of=now,
        )
        leg = next(r for r in result["requirement_breakdown"] if r["requirement_code"] == "LEGIONELLA")
        assert leg["status"] == "EXPIRING_SOON"


class TestLifecycleScoringProjectorOverlay:
    def _row(self):
        return {
            "requirement_id": "req-leg",
            "requirement_code": "legionella",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "evidence_authority": {
                "state": "EA_UPLOADED_UNCONFIRMED",
                "state_reason": "document_upload_missing_required_expiry_semantics",
            },
            "governance_family": "SELF_CERTIFIED",
        }

    def test_active_scoring_suppresses_expiry_needed_for_review_based(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        out = project_customer_status(self._row())
        assert out["customer_status_key"] != "expiry_date_needed"

    def test_shadow_scoring_keeps_legacy_expiry_needed_overlay(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        out = project_customer_status(self._row())
        assert out["customer_status_key"] == "expiry_date_needed"

    def test_active_scoring_keeps_expiry_needed_for_gas(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        row = {
            "requirement_id": "req-gas",
            "requirement_code": "gas_safety",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "evidence_authority": {
                "state": "EA_UPLOADED_UNCONFIRMED",
                "state_reason": "document_upload_missing_required_expiry_semantics",
            },
            "governance_family": "PLATFORM_VERIFIED",
        }
        out = project_customer_status(row)
        assert out["customer_status_key"] == "expiry_date_needed"
