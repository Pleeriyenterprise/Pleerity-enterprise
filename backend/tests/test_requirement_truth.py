"""Unit tests for requirement truth inference and presentation."""
import sys
from pathlib import Path

import pytest
from unittest.mock import AsyncMock

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
    monkeypatch.setattr(
        rt,
        "fetch_active_published_registry_entries",
        AsyncMock(return_value=None),
    )

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
    assert "workflow_class_reference" in out[0]
    assert "workflow_mismatch_flags" in out[0]


def test_enrich_requirement_dict_adds_presentation():
    from services.requirement_workflow_audit import WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS
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
    rd = r.get("requirement_display")
    assert isinstance(rd, dict)
    assert rd.get("canonical_name") == "Gas Safety Certificate (CP12)"
    assert rd.get("short_name") == "Gas Safety"
    assert rd.get("primary_cta_label")
    assert r["date_source"] == "SYSTEM_ESTIMATED"
    assert "Estimated" in r["date_label"]
    assert r["evidence_badge_label"]
    for k in WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS:
        assert k not in r


def test_enrich_requirement_dict_passes_through_authority_semantic_state():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    r = enrich_requirement_dict(
        {
            "requirement_id": "r-semantics-1",
            "property_id": "p1",
            "requirement_type": "gas_safety",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "evidence_authority": {"state": "UPLOADED_UNCONFIRMED", "semantic_state": "EXPIRY_REVIEW_REQUIRED"},
        },
        EVIDENCE_MISSING,
        audience="client",
    )
    assert r.get("semantic_state") == "EXPIRY_REVIEW_REQUIRED"


def test_enrich_right_to_rent_client_guided_declaration_disclosure():
    from services.compliance_evidence_record_service import GUIDED_DECLARATION_WORKFLOW
    from services.requirement_workflow_audit import WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    r = enrich_requirement_dict(
        {
            "requirement_id": "r1",
            "property_id": "p1",
            "requirement_type": "right_to_rent",
            "requirement_code": "right_to_rent",
            "compliance_requirement_class": "OBLIGATION",
            "due_date": "2026-04-01T00:00:00+00:00",
            "expiry_source": "NONE",
            "status": "PENDING",
            "applicability": "REQUIRED",
        },
        EVIDENCE_MISSING,
        audience="client",
    )
    assert r.get("workflow_class") == GUIDED_DECLARATION_WORKFLOW
    assert "home office" in str(r.get("client_evidence_disclosure") or "").lower()
    for k in WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS:
        assert k not in r


def test_enrich_how_to_rent_client_includes_disclosure_no_audit_diagnostics():
    from services.requirement_workflow_audit import WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    r = enrich_requirement_dict(
        {
            "requirement_id": "r1",
            "property_id": "p1",
            "requirement_type": "how_to_rent",
            "requirement_code": "how_to_rent",
            "compliance_requirement_class": "OBLIGATION",
            "due_date": "2026-04-01T00:00:00+00:00",
            "expiry_source": "NONE",
            "status": "PENDING",
            "applicability": "REQUIRED",
        },
        EVIDENCE_MISSING,
        audience="client",
    )
    assert r.get("workflow_class") == "TENANT_DELIVERY"
    assert r.get("client_evidence_disclosure")
    assert "legal advice" in str(r.get("client_evidence_disclosure") or "").lower()
    for k in WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS:
        assert k not in r


def test_enrich_tenancy_agreement_projects_status_text_from_structured_record():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    r = enrich_requirement_dict(
        {
            "requirement_id": "r-ta",
            "property_id": "p1",
            "requirement_type": "tenancy_agreement",
            "requirement_code": "tenancy_agreement",
            "compliance_requirement_class": "OBLIGATION",
            "status": "COMPLIANT",
            "applicability": "REQUIRED",
        },
        EVIDENCE_MISSING,
        audience="client",
        compliance_evidence_records=[
            {
                "evidence_mode": "STRUCTURED_DECLARATION",
                "status": "SUBMITTED",
                "evidence_payload": {
                    "structured_fields": {
                        "agreement_exists": {"answer": True},
                        "signed_by_parties": {"answer": False},
                    }
                },
            }
        ],
    )
    assert r.get("workflow_class") == "GUIDED_DECLARATION"
    assert r.get("tenancy_agreement_status_text") == "Supporting agreement not uploaded"


def test_enrich_active_standard_includes_disclosure_and_read_only_summary():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    r = enrich_requirement_dict(
        {
            "requirement_id": "r-active-1",
            "property_id": "p1",
            "requirement_type": "fitness_for_human_habitation",
            "requirement_code": "fitness_for_human_habitation",
            "compliance_requirement_class": "OBLIGATION",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "active_standard_status_summary": {
                "state": "active_issues_present",
                "signal_counts": {
                    "open_issues": 2,
                    "open_work_orders": 1,
                    "open_risk_signals": 1,
                    "open_compliance_gaps": 1,
                },
            },
        },
        EVIDENCE_MISSING,
        audience="client",
    )
    assert "single uploaded document does not prove this standard is met" in str(
        r.get("client_evidence_disclosure") or ""
    ).lower()
    summary = r.get("active_standard_status_summary") or {}
    assert summary.get("state") == "active_issues_present"
    assert summary.get("read_only") is True


def test_enrich_active_standard_unresolved_uses_operational_wording_not_verified_language():
    from services.requirement_truth import EVIDENCE_VERIFIED, enrich_requirement_dict

    r = enrich_requirement_dict(
        {
            "requirement_id": "r-active-2",
            "property_id": "p1",
            "requirement_type": "fitness_for_human_habitation",
            "requirement_code": "fitness_for_human_habitation",
            "compliance_requirement_class": "OBLIGATION",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "active_standard_status_summary": {
                "state": "active_issues_present",
                "signal_counts": {
                    "open_issues": 1,
                    "open_work_orders": 1,
                    "open_risk_signals": 0,
                    "open_compliance_gaps": 1,
                },
            },
        },
        EVIDENCE_VERIFIED,
        audience="client",
    )
    lower = " ".join(
        [
            str(r.get("status_label") or ""),
            str(r.get("evidence_badge_label") or ""),
        ]
    ).lower()
    assert "review" in lower or "follow-up" in lower
    for forbidden in ("verified", "compliant", "safe", "resolved", "remediated"):
        assert forbidden not in lower


def test_enrich_multi_evidence_incomplete_uses_partial_wording_not_completion_terms():
    from services.requirement_truth import EVIDENCE_VERIFIED, enrich_requirement_dict

    r = enrich_requirement_dict(
        {
            "requirement_id": "r-multi-1",
            "property_id": "p1",
            "requirement_type": "smoke_heat_alarms",
            "requirement_code": "smoke_heat_alarms",
            "compliance_requirement_class": "DOCUMENT",
            "status": "COMPLIANT",
            "applicability": "REQUIRED",
            "registry_metadata": {"evidence_resolution": {"co_alarm_required": True}},
        },
        EVIDENCE_VERIFIED,
        audience="client",
        property_doc={"has_fuel_burning_appliance": True},
        compliance_evidence_records=[
            {
                "evidence_mode": "CONTRACTOR_CONFIRMATION",
                "status": "SUBMITTED",
                "evidence_payload": {"component": "smoke_alarm", "notes": "smoke alarm tested"},
            }
        ],
    )
    lower = " ".join(
        [
            str(r.get("status_label") or ""),
            str(r.get("evidence_badge_label") or ""),
            str((r.get("evidence_completeness") or {}).get("summary_label") or ""),
        ]
    ).lower()
    assert "incomplete" in lower or "required" in lower or "partial" in lower
    for forbidden_phrase in (" evidence complete", "fully complete", "compliant", "verified", "resolved"):
        assert forbidden_phrase not in lower


@pytest.mark.asyncio
async def test_enrich_requirements_for_client_active_standard_signal_projection(monkeypatch):
    from services import requirement_truth as rt

    async def fake_load(db, client_id, requirement_ids):
        return {rid: rt.EVIDENCE_MISSING for rid in requirement_ids}

    monkeypatch.setattr(rt, "load_evidence_state_by_requirement_id", fake_load)
    monkeypatch.setattr(rt, "fetch_active_published_registry_entries", AsyncMock(return_value=None))

    class _Cursor:
        def __init__(self, rows):
            self._rows = list(rows)

        async def to_list(self, _n):
            return list(self._rows)

        def __aiter__(self):
            self._it = iter(self._rows)
            return self

        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    class _CountDB:
        def __init__(self):
            self.clients = type("C", (), {"find_one": AsyncMock(return_value={"default_jurisdiction": "England"})})()
            self.documents = type("D", (), {"find": lambda *a, **k: _Cursor([])})()
            self.properties = type(
                "P",
                (),
                {
                    "find": lambda *a, **k: _Cursor(
                        [{"property_id": "p1", "client_id": "c1", "jurisdiction": "England"}]
                    )
                },
            )()
            self.maintenance_issues = type("MI", (), {"count_documents": AsyncMock(return_value=1)})()
            self.work_orders = type("WO", (), {"count_documents": AsyncMock(return_value=0)})()
            self.risk_signals = type("RS", (), {"count_documents": AsyncMock(return_value=0)})()
            self.compliance_gaps = type("CG", (), {"count_documents": AsyncMock(return_value=0)})()

    db = _CountDB()
    rows = [
        {
            "client_id": "c1",
            "property_id": "p1",
            "requirement_id": "r1",
            "requirement_type": "fitness_for_human_habitation",
            "requirement_code": "fitness_for_human_habitation",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "compliance_requirement_class": "OBLIGATION",
        }
    ]
    enriched, _meta = await rt.enrich_requirements_for_client(db, "c1", rows)
    assert enriched
    summary = enriched[0].get("active_standard_status_summary") or {}
    assert summary.get("state") == "active_issues_present"


def test_evidence_state_awaiting_user_confirm_when_extraction_not_approved():
    from services.requirement_truth import EVIDENCE_AWAITING_USER_CONFIRM, evidence_state_from_documents

    docs = [
        {
            "status": "UPLOADED",
            "requirement_evidence_mismatch": False,
            "ai_extraction": {"status": "completed", "review_status": "AWAITING_USER_CONFIRM", "data": {"expiry_date": "2027-01-01"}},
        }
    ]
    assert evidence_state_from_documents(docs) == EVIDENCE_AWAITING_USER_CONFIRM


def test_evidence_state_mismatch_overrides_awaiting_confirm():
    from services.requirement_truth import EVIDENCE_MISMATCH_FLAGGED, evidence_state_from_documents

    docs = [
        {
            "status": "UPLOADED",
            "requirement_evidence_mismatch": True,
            "ai_extraction": {"status": "completed", "review_status": "AWAITING_USER_CONFIRM", "data": {}},
        }
    ]
    assert evidence_state_from_documents(docs) == EVIDENCE_MISMATCH_FLAGGED


def test_detect_requirement_document_mismatch_epc_vs_gas():
    from services.document_requirement_evidence import detect_requirement_document_mismatch

    req = {
        "requirement_id": "req-mm-1",
        "requirement_type": "gas_safety",
        "requirement_code": "GAS_SAFETY",
    }
    extracted = {"document_type": "Energy Performance Certificate (EPC)"}
    is_mm, reason = detect_requirement_document_mismatch(req, extracted)
    # Current matcher treats this as low-signal UNKNOWN_TYPE (quarantine) rather than hard mismatch.
    assert is_mm is False
    assert reason is None


def test_detect_requirement_document_mismatch_no_false_positive_when_type_blank():
    from services.document_requirement_evidence import detect_requirement_document_mismatch

    req = {"requirement_type": "gas_safety"}
    is_mm, reason = detect_requirement_document_mismatch(req, {"document_type": ""})
    assert is_mm is False
    assert reason is None


def test_requirement_negative_actionability_excludes_valid_without_deadlines():
    from services.requirement_truth import requirement_has_active_negative_actionability

    row = {
        "status": "VALID",
        "evidence_state": "VERIFIED",
        "due_date": None,
        "follow_up_date": None,
    }
    assert requirement_has_active_negative_actionability(row, expiring_window_days=60) is False


def test_requirement_negative_actionability_includes_expired_and_due_soon_followup():
    from datetime import datetime, timedelta, timezone
    from services.requirement_truth import requirement_has_active_negative_actionability

    now = datetime.now(timezone.utc)
    expired = {"status": "EXPIRED"}
    assert requirement_has_active_negative_actionability(expired, now=now, expiring_window_days=60) is True

    followup_due_soon = {
        "status": "VALID",
        "evidence_state": "VERIFIED",
        "follow_up_date": (now + timedelta(days=10)).isoformat(),
    }
    assert requirement_has_active_negative_actionability(followup_due_soon, now=now, expiring_window_days=30) is True

    followup_future = {
        "status": "VALID",
        "evidence_state": "VERIFIED",
        "follow_up_date": (now + timedelta(days=90)).isoformat(),
    }
    assert requirement_has_active_negative_actionability(followup_future, now=now, expiring_window_days=30) is False


def _legionella_structured_cer(*, actions_required: bool = False) -> dict:
    return {
        "evidence_record_id": "cer-leg-1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r-leg",
        "archived": False,
        "evidence_mode": "STRUCTURED_DECLARATION",
        "evidence_confidence_level": "HIGH",
        "evidence_payload": {
            "structured_fields": {
                "actions_required": {"answer": actions_required},
                "assessment_completed": {"answer": True},
                "declaration_confirmed": {"answer": True},
                "risk_level": {"answer": "low"},
            }
        },
    }


def test_enrich_requirement_dict_legionella_closed_followup_no_false_badge():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    req = {
        "requirement_id": "r-leg",
        "property_id": "p1",
        "client_id": "c1",
        "requirement_type": "legionella",
        "requirement_code": "legionella",
        "status": "PENDING",
        "evidence_authority": {
            "primary_evidence_record_id": "cer-leg-1",
            "version": 1,
        },
    }
    out = enrich_requirement_dict(
        req,
        EVIDENCE_MISSING,
        audience="client",
        compliance_evidence_records=[_legionella_structured_cer(actions_required=False)],
    )
    assert out["status_label"] == "Assessment recorded"
    assert out["evidence_badge_label"] == "Assessment on file"
    assert "follow-up" not in out["evidence_badge_label"].lower()


def test_enrich_requirement_dict_legionella_empty_cer_keeps_followup_uncertainty():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    req = {
        "requirement_id": "r-leg",
        "property_id": "p1",
        "requirement_type": "legionella",
        "status": "PENDING",
    }
    out = enrich_requirement_dict(req, EVIDENCE_MISSING, audience="client", compliance_evidence_records=[])
    assert out["evidence_badge_label"] == "Remediation or follow-up may remain open"
    assert "follow-up" in out["status_label"].lower()


def test_enrich_requirement_dict_legionella_open_followup_when_actions_required():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    req = {
        "requirement_id": "r-leg",
        "property_id": "p1",
        "requirement_type": "legionella",
        "status": "PENDING",
    }
    out = enrich_requirement_dict(
        req,
        EVIDENCE_MISSING,
        audience="client",
        compliance_evidence_records=[_legionella_structured_cer(actions_required=True)],
    )
    assert out["evidence_badge_label"] == "Remediation or follow-up may remain open"
    assert "follow-up" in out["status_label"].lower()


@pytest.mark.asyncio
async def test_enrich_requirements_for_client_batch_loads_legionella_cer(monkeypatch):
    from services import requirement_truth as rt

    captured_rids: list = []

    async def fake_batch(db, client_id, requirement_ids):
        captured_rids.extend(requirement_ids)
        return {rid: [_legionella_structured_cer()] for rid in requirement_ids}

    async def fake_load(db, client_id, requirement_ids):
        return {rid: rt.EVIDENCE_MISSING for rid in requirement_ids}

    monkeypatch.setattr(
        "services.compliance_evidence_record_service.batch_list_evidence_records_for_requirements",
        fake_batch,
    )
    monkeypatch.setattr(rt, "load_evidence_state_by_requirement_id", fake_load)
    monkeypatch.setattr(rt, "fetch_active_published_registry_entries", AsyncMock(return_value=None))
    monkeypatch.setattr(rt, "load_linked_primary_documents_for_client_requirements", AsyncMock(return_value={}))

    class _Cursor:
        def __init__(self, rows):
            self._rows = list(rows)

        async def to_list(self, _n):
            return list(self._rows)

        def __aiter__(self):
            self._it = iter(self._rows)
            return self

        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    class _CountDB:
        def __init__(self):
            self.clients = type("C", (), {"find_one": AsyncMock(return_value={"default_jurisdiction": "Wales"})})()
            self.documents = type("D", (), {"find": lambda *a, **k: _Cursor([])})()
            self.properties = type(
                "P",
                (),
                {
                    "find": lambda *a, **k: _Cursor(
                        [{"property_id": "p1", "client_id": "c1", "jurisdiction": "Wales"}]
                    )
                },
            )()
            self.maintenance_issues = type("MI", (), {"count_documents": AsyncMock(return_value=0)})()
            self.work_orders = type("WO", (), {"count_documents": AsyncMock(return_value=0)})()
            self.risk_signals = type("RS", (), {"count_documents": AsyncMock(return_value=0)})()
            self.compliance_gaps = type("CG", (), {"count_documents": AsyncMock(return_value=0)})()

    rows = [
        {
            "client_id": "c1",
            "property_id": "p1",
            "requirement_id": "r-leg",
            "requirement_type": "legionella",
            "requirement_code": "legionella",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "evidence_authority": {"primary_evidence_record_id": "cer-leg-1", "version": 1},
        }
    ]
    enriched, _ = await rt.enrich_requirements_for_client(_CountDB(), "c1", rows)
    assert "r-leg" in captured_rids
    leg = enriched[0]
    assert leg["evidence_badge_label"] == "Assessment on file"
    assert leg["status_label"] == "Assessment recorded"
