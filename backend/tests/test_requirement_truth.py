"""Unit tests for requirement truth inference and presentation."""
import sys
from pathlib import Path

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def test_infer_date_source_verified_wins():
    from services.requirement_truth import (
        DATE_SOURCE_VERIFIED_DOCUMENT,
        EVIDENCE_VERIFIED,
        infer_date_source,
    )

    req = {"expiry_source": "NONE", "date_source": "SYSTEM_ESTIMATED"}
    assert infer_date_source(req, EVIDENCE_VERIFIED) == DATE_SOURCE_VERIFIED_DOCUMENT


def test_infer_date_source_confirmed_without_verified_doc():
    from services.requirement_truth import DATE_SOURCE_USER_PROVIDED, EVIDENCE_MISSING, infer_date_source

    req = {"expiry_source": "CONFIRMED"}
    assert infer_date_source(req, EVIDENCE_MISSING) == DATE_SOURCE_USER_PROVIDED


def test_build_date_presentation_system_estimated():
    from services.requirement_truth import DATE_SOURCE_SYSTEM_ESTIMATED, EVIDENCE_MISSING, build_date_presentation

    req = {"due_date": "2026-04-26T00:00:00+00:00"}
    label, helper = build_date_presentation(req, DATE_SOURCE_SYSTEM_ESTIMATED, EVIDENCE_MISSING)
    assert "Estimated renewal date" in label
    assert "26 Apr 2026" in label
    assert helper


def test_should_show_notice_only_for_applicable_estimated():
    from services.requirement_truth import should_show_compliance_estimates_notice

    rows = [
        {"applicability": "REQUIRED", "status": "PENDING", "confidence_state": "ESTIMATED"},
        {"applicability": "NOT_REQUIRED", "status": "NOT_REQUIRED", "confidence_state": "ESTIMATED"},
    ]
    assert should_show_compliance_estimates_notice(rows) is True

    rows2 = [
        {"applicability": "REQUIRED", "status": "COMPLIANT", "confidence_state": "VERIFIED"},
    ]
    assert should_show_compliance_estimates_notice(rows2) is False


@pytest.mark.asyncio
async def test_enrich_requirements_for_admin_uses_evidence_map(monkeypatch):
    from services import requirement_truth as rt

    async def fake_load(db, client_id, requirement_ids):
        return {requirement_ids[0]: rt.EVIDENCE_VERIFIED} if requirement_ids else {}

    monkeypatch.setattr(rt, "load_evidence_state_by_requirement_id", fake_load)

    rows = [
        {
            "requirement_id": "r1",
            "client_id": "c1",
            "requirement_type": "gas_safety",
            "status": "COMPLIANT",
            "due_date": "2026-12-01T00:00:00+00:00",
            "expiry_source": "NONE",
            "applicability": "REQUIRED",
        }
    ]
    out = await rt.enrich_requirements_for_admin(None, rows)
    assert len(out) == 1
    assert out[0]["display_label"]
    assert out[0]["status_label"]
    assert out[0]["date_source"] == rt.DATE_SOURCE_VERIFIED_DOCUMENT


def test_enrich_requirement_dict_adds_presentation():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    r = enrich_requirement_dict(
        {
            "requirement_type": "gas_safety",
            "due_date": "2026-04-01T00:00:00+00:00",
            "expiry_source": "NONE",
            "status": "PENDING",
            "applicability": "REQUIRED",
        },
        EVIDENCE_MISSING,
    )
    assert r["display_label"]
    assert r["date_source"] == "SYSTEM_ESTIMATED"
    assert "Estimated" in r["date_label"]
    assert r["evidence_badge_label"]
