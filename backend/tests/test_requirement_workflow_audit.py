"""Tests for read-only requirement workflow class reference and drift detection."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def test_non_documented_alias_still_mismatch_medium():
    """e.g. cp12 → gas_safety: not a Phase-1 documented storage slug; still data hygiene flag."""
    from services.requirement_workflow_audit import compute_workflow_mismatch_flags, WC_DOCUMENT_UPLOAD

    enriched = {
        "requirement_code": "cp12",
        "requirement_type": "cp12",
        "workflow_class": "LEGACY_DOCUMENT_UPLOAD",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": ["DOCUMENT_UPLOAD"],
        "take_action": {"primary": {"intent": "upload_evidence", "kind": "navigate_document"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_DOCUMENT_UPLOAD,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "ALIAS_NOT_NORMALIZED" in ids


def test_documented_legacy_alias_low_severity_only():
    from services.requirement_workflow_audit import compute_workflow_mismatch_flags, WC_DOCUMENT_UPLOAD

    enriched = {
        "requirement_code": "fire_alarm",
        "requirement_type": "fire_alarm",
        "workflow_class": "LEGACY_DOCUMENT_UPLOAD",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": ["DOCUMENT_UPLOAD"],
        "take_action": {"primary": {"intent": "upload_evidence", "kind": "navigate_document"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_DOCUMENT_UPLOAD,
        reference_source="decision_record_fallback",
    )
    assert any(f.get("id") == "ALIAS_LEGACY_STORAGE_SLUG" and f.get("severity") == "LOW" for f in flags)
    assert not any(f.get("id") == "ALIAS_NOT_NORMALIZED" for f in flags)


def test_tenant_delivery_document_only_flag():
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import WC_TENANT_DELIVERY, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "how_to_rent",
        "requirement_type": "how_to_rent",
        "workflow_class": "LEGACY_DOCUMENT_UPLOAD",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {"primary": {"intent": "upload_evidence", "kind": "navigate"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_TENANT_DELIVERY,
        reference_source="decision_record_fallback",
    )
    assert any(f.get("id") == "TENANT_DELIVERY_DOCUMENT_ONLY" for f in flags)


def test_right_to_rent_guided_declaration_document_only_flag():
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import WC_GUIDED_DECLARATION, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "right_to_rent_checks",
        "requirement_type": "right_to_rent_checks",
        "workflow_class": "LEGACY_DOCUMENT_UPLOAD",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {"primary": {"intent": "upload_evidence", "kind": "navigate"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_GUIDED_DECLARATION,
        reference_source="decision_record_fallback",
    )
    assert any(f.get("id") == "RIGHT_TO_RENT_GUIDED_DECLARATION_DOCUMENT_ONLY" for f in flags)


def test_guided_declaration_runtime_family_aligns_reference():
    from services.compliance_evidence_record_service import (
        EVIDENCE_MODE_DOCUMENT_UPLOAD,
        EVIDENCE_MODE_STRUCTURED_DECLARATION,
    )
    from services.requirement_workflow_audit import WC_GUIDED_DECLARATION, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "right_to_rent",
        "workflow_class": "GUIDED_DECLARATION",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": [EVIDENCE_MODE_STRUCTURED_DECLARATION, EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {
            "primary": {"intent": "guided_evidence_resolution", "kind": "guided_evidence_resolution"},
        },
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_GUIDED_DECLARATION,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "RESOLVER_CTA_MISMATCH" not in ids
    assert "RIGHT_TO_RENT_GUIDED_DECLARATION_DOCUMENT_ONLY" not in ids


def test_tenant_delivery_enriched_guided_aligns_reference_family():
    """Runtime workflow_class TENANT_DELIVERY must map to guided family (no false document drift)."""
    from services.requirement_workflow_audit import WC_TENANT_DELIVERY, compute_workflow_mismatch_flags
    from services.compliance_evidence_record_service import (
        EVIDENCE_MODE_DOCUMENT_UPLOAD,
        EVIDENCE_MODE_STRUCTURED_DECLARATION,
    )

    enriched = {
        "requirement_code": "how_to_rent",
        "workflow_class": "TENANT_DELIVERY",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": [EVIDENCE_MODE_STRUCTURED_DECLARATION, EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {
            "primary": {"intent": "guided_evidence_resolution", "kind": "guided_evidence_resolution"},
        },
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_TENANT_DELIVERY,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "RESOLVER_CTA_MISMATCH" not in ids
    assert "TENANT_DELIVERY_DOCUMENT_ONLY" not in ids


def test_multi_evidence_document_only_flag():
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import compute_workflow_mismatch_flags, WC_MULTI_EVIDENCE

    enriched = {
        "requirement_code": "hmo_fire_risk",
        "requirement_type": "hmo_fire_risk",
        "workflow_class": "GUIDED_EVIDENCE_RESOLUTION",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {"primary": {"intent": "guided_evidence_resolution", "kind": "guided_evidence_resolution"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_MULTI_EVIDENCE,
        reference_source="decision_record_fallback",
    )
    assert any(f.get("id") == "MULTI_EVIDENCE_DOCUMENT_ONLY" for f in flags)


def test_domestic_alarm_family_suppresses_multi_evidence_document_only_noise():
    """smoke_heat_alarms canon + MULTI_EVIDENCE ref should not emit MULTI_EVIDENCE_DOCUMENT_ONLY."""
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import compute_workflow_mismatch_flags, WC_MULTI_EVIDENCE

    enriched = {
        "requirement_code": "smoke_alarms",
        "requirement_type": "smoke_alarms",
        "workflow_class": "GUIDED_EVIDENCE_RESOLUTION",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {"primary": {"intent": "guided_evidence_resolution", "kind": "guided_evidence_resolution"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_MULTI_EVIDENCE,
        reference_source="decision_record_fallback",
    )
    assert not any(f.get("id") == "MULTI_EVIDENCE_DOCUMENT_ONLY" for f in flags)


def test_resolver_family_aligns_job():
    from services.requirement_workflow_audit import compute_workflow_mismatch_flags, WC_REMEDIATION_JOB

    enriched = {
        "requirement_code": "emergency_lighting",
        "compliance_requirement_class": "JOB",
        "workflow_class": "EXTERNAL_ASSESSMENT_EVIDENCE",
        "action_type": "JOB",
        "allowed_evidence_modes": ["DOCUMENT_UPLOAD"],
        "take_action": {"primary": {"intent": "maintenance", "kind": "work_order"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_REMEDIATION_JOB,
        reference_source="decision_record_fallback",
    )
    assert not any(f.get("id") == "RESOLVER_CTA_MISMATCH" for f in flags)


def test_evidence_mode_mismatch_document_ref_with_multi_modes():
    from services.compliance_evidence_record_service import (
        EVIDENCE_MODE_DOCUMENT_UPLOAD,
        EVIDENCE_MODE_STRUCTURED_DECLARATION,
    )
    from services.requirement_workflow_audit import compute_workflow_mismatch_flags, WC_DOCUMENT_UPLOAD

    enriched = {
        "requirement_code": "gas_safety",
        "workflow_class": "GUIDED_EVIDENCE_RESOLUTION",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD, EVIDENCE_MODE_STRUCTURED_DECLARATION],
        "take_action": {"primary": {"intent": "guided_evidence_resolution", "kind": "guided_evidence_resolution"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_DOCUMENT_UPLOAD,
        reference_source="decision_record_fallback",
    )
    assert any(f.get("id") == "EVIDENCE_MODE_MISMATCH" for f in flags)


def test_registry_overrides_fallback():
    from services.requirement_workflow_audit import resolve_workflow_class_reference, WC_GUIDANCE_ONLY

    ref, src = resolve_workflow_class_reference(
        "gas_safety",
        published_entry={"client_workflow_class": WC_GUIDANCE_ONLY},
    )
    assert ref == WC_GUIDANCE_ONLY
    assert src == "registry"


@pytest.mark.asyncio
async def test_work_order_mismatch_list_empty_cursor():
    from services.requirement_workflow_audit import list_work_order_job_class_mismatches

    class _AI:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    chain = MagicMock()
    chain.sort.return_value = chain
    chain.limit.return_value = _AI()

    db = MagicMock()
    db.work_orders.find.return_value = chain

    out = await list_work_order_job_class_mismatches(db, published_entries=None, limit=10)
    assert out == []


def test_enrich_admin_includes_workflow_class_reference():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    r = enrich_requirement_dict(
        {
            "requirement_type": "gas_safety",
            "property_id": "p1",
            "due_date": "2026-04-01T00:00:00+00:00",
            "expiry_source": "NONE",
            "status": "PENDING",
            "applicability": "REQUIRED",
        },
        EVIDENCE_MISSING,
        audience="admin",
        published_registry_entries=None,
    )
    assert r.get("workflow_class_reference") == "DOCUMENT_UPLOAD"
    assert r.get("workflow_class_reference_source") == "decision_record_fallback"
    assert "workflow_runtime_behaviour" in r
    assert isinstance(r.get("workflow_mismatch_flags"), list)


def test_enrich_client_omits_workflow_diagnostics():
    from services.requirement_workflow_audit import WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    r = enrich_requirement_dict(
        {
            "requirement_type": "gas_safety",
            "property_id": "p1",
            "due_date": "2026-04-01T00:00:00+00:00",
            "expiry_source": "NONE",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "workflow_class_reference": "SHOULD_STRIP",
            "workflow_mismatch_flags": [{"id": "X"}],
        },
        EVIDENCE_MISSING,
        audience="client",
        published_registry_entries=None,
    )
    for k in WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS:
        assert k not in r


@pytest.mark.asyncio
async def test_enrich_requirements_for_client_omits_workflow_diagnostics(monkeypatch):
    from services import requirement_truth as rt
    from services.requirement_workflow_audit import WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS

    async def fake_load(db, client_id, requirement_ids):
        return {requirement_ids[0]: rt.EVIDENCE_MISSING} if requirement_ids else {}

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
            "property_id": "p1",
            "requirement_type": "gas_safety",
            "status": "PENDING",
            "due_date": "2026-12-01T00:00:00+00:00",
            "expiry_source": "NONE",
            "applicability": "REQUIRED",
        }
    ]
    class _EmptyProps:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    db_stub = MagicMock()
    db_stub.clients.find_one = AsyncMock(return_value=None)
    db_stub.properties.find = MagicMock(return_value=_EmptyProps())

    out, _ = await rt.enrich_requirements_for_client(db_stub, "c1", rows)
    assert len(out) == 1
    for k in WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS:
        assert k not in out[0]


@pytest.mark.asyncio
async def test_admin_requirement_workflow_audit_route(monkeypatch):
    from fastapi.testclient import TestClient

    from middleware import admin_route_guard
    from routes import requirement_workflow_audit_admin as rwa
    from server import app

    async def _guard():
        return {"portal_user_id": "adm1", "role": "ROLE_ADMIN"}

    app.dependency_overrides[admin_route_guard] = _guard

    fake_db = MagicMock()
    mc = MagicMock()
    mc.sort.return_value = mc
    mc.skip.return_value = mc
    mc.limit.return_value = mc
    mc.to_list = AsyncMock(return_value=[])
    fake_db.requirements.find.return_value = mc

    monkeypatch.setattr(rwa, "database", MagicMock(get_db=lambda: fake_db))

    with patch.object(rwa, "enrich_requirements_for_admin", new_callable=AsyncMock, return_value=[]):
        with patch.object(rwa, "fetch_active_published_registry_entries", new_callable=AsyncMock, return_value=None):
            with patch.object(rwa, "list_work_order_job_class_mismatches", new_callable=AsyncMock, return_value=[]):
                client = TestClient(app)
                res = client.get("/api/admin/requirement-workflow-audit")
                assert res.status_code == 200
                body = res.json()
                assert body.get("read_only") is True
                assert body.get("items") == []

    app.dependency_overrides.pop(admin_route_guard, None)
