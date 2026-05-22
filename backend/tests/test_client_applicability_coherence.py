"""Bounded client applicability / authority coherence tests."""

import pytest

from services.client_applicability_coherence import (
    apply_client_applicability_presentation_overlay,
    authority_applicability_not_required_disagrees_with_row,
    has_stale_not_required_authority_blob,
    legionella_operational_applicability_reconciliation_eligible,
    pipeline_not_required_disagrees_with_surfaced_row,
    reconcile_legionella_operational_applicability,
    reconcile_rent_smart_wales_operational_applicability,
    reconcile_scotland_landlord_registration_operational_applicability,
    rent_smart_wales_operational_applicability_reconciliation_eligible,
    reconcile_wales_occupation_operational_applicability,
    scotland_landlord_registration_operational_applicability_reconciliation_eligible,
    wales_occupation_operational_applicability_reconciliation_eligible,
    refresh_stale_authority_for_client_requirements,
)
from services.client_requirement_lifecycle import (
    ACTION_REQUIRED,
    NOT_APPLICABLE,
    derive_client_lifecycle_fields,
)
from services.requirement_evidence_authority import EA_MISSING, EA_NOT_REQUIRED


def _legionella_like_row(**kwargs):
    base = {
        "requirement_id": "537da91b-d80c-49b2-bc92-f32514b00a2a",
        "requirement_type": "legionella",
        "applicability": "UNKNOWN",
        "status": "PENDING",
        "client_surface_visible": True,
        "pipeline_applicability_state": "NOT_REQUIRED",
        "effective_applicability_state": "NOT_REQUIRED",
        "applicability_resolution_source": "PIPELINE",
        "evidence_authority": {
            "state": EA_NOT_REQUIRED,
            "state_reason": "applicability_not_required",
        },
    }
    base.update(kwargs)
    return base


def test_detects_stale_not_required_authority():
    row = _legionella_like_row()
    assert authority_applicability_not_required_disagrees_with_row(row)
    assert has_stale_not_required_authority_blob(row)
    assert pipeline_not_required_disagrees_with_surfaced_row(row)


def test_detects_split_applicability_state_column():
    """Pilot pattern: applicability_state NOT_REQUIRED + legacy applicability UNKNOWN."""
    row = _legionella_like_row(applicability_state="NOT_REQUIRED", applicability="UNKNOWN")
    assert authority_applicability_not_required_disagrees_with_row(row)
    assert has_stale_not_required_authority_blob(row)


def test_lifecycle_not_not_applicable_when_authority_stale():
    out = derive_client_lifecycle_fields(_legionella_like_row())
    assert out["client_lifecycle_state"] == ACTION_REQUIRED
    assert out["client_lifecycle_state"] != NOT_APPLICABLE


def test_presentation_overlay_reconciles_legionella_to_required():
    row = _legionella_like_row()
    out = apply_client_applicability_presentation_overlay(row)
    assert out["effective_applicability_state"] == "REQUIRED"
    assert out["applicability_state"] == "REQUIRED"
    assert out["applicability"] == "REQUIRED"
    rec = (out.get("applicability_provenance") or {}).get("operational_applicability_reconciliation") or {}
    assert rec.get("source") == "legionella_operational_surfaced_actionable_v1"


def test_legionella_reconciliation_eligible_for_pilot_pattern():
    row = _legionella_like_row(applicability_state="NOT_REQUIRED", applicability="UNKNOWN")
    assert legionella_operational_applicability_reconciliation_eligible(row)


def test_legionella_reconciliation_not_applied_when_hidden():
    row = _legionella_like_row(client_surface_visible=False)
    assert not legionella_operational_applicability_reconciliation_eligible(row)
    assert reconcile_legionella_operational_applicability(row) == row


def test_lead_testing_not_reconciled():
    row = _legionella_like_row(requirement_type="lead_testing", requirement_code="lead_testing")
    assert not legionella_operational_applicability_reconciliation_eligible(row)


def _wales_occupation_like_row(**kwargs):
    base = {
        "requirement_id": "488269bb-1be7-47e7-a030-98accf6dffc4",
        "requirement_type": "occupation_contract",
        "requirement_code": "occupation_contract",
        "jurisdiction": "Wales",
        "applicability": "UNKNOWN",
        "applicability_state": "UNKNOWN",
        "status": "PENDING",
        "client_surface_visible": True,
        "evidence_authority": {"state": EA_MISSING, "state_reason": "no_evidence_document"},
    }
    base.update(kwargs)
    return base


def test_wales_occupation_unknown_actionable_reconciles_to_required():
    row = _wales_occupation_like_row()
    assert wales_occupation_operational_applicability_reconciliation_eligible(row)
    out = reconcile_wales_occupation_operational_applicability(row)
    assert out["applicability_state"] == "REQUIRED"
    assert out["effective_applicability_state"] == "REQUIRED"


def test_occupation_contract_non_wales_not_reconciled():
    row = _wales_occupation_like_row(jurisdiction="England")
    assert not wales_occupation_operational_applicability_reconciliation_eligible(row)


def _scotland_landlord_reg_like_row(**kwargs):
    base = {
        "requirement_id": "3708620b-82fb-4d90-9f17-5b800777e554",
        "requirement_type": "scotland_landlord_registration",
        "requirement_code": "scotland_landlord_registration",
        "jurisdiction": "Scotland",
        "applicability": "UNKNOWN",
        "applicability_state": "UNKNOWN",
        "status": "PENDING",
        "client_surface_visible": True,
        "evidence_authority": {"state": EA_MISSING, "state_reason": "no_evidence_document"},
    }
    base.update(kwargs)
    return base


def test_scotland_landlord_registration_unknown_actionable_reconciles_to_required():
    row = _scotland_landlord_reg_like_row()
    assert scotland_landlord_registration_operational_applicability_reconciliation_eligible(row)
    out = reconcile_scotland_landlord_registration_operational_applicability(row)
    assert out["applicability_state"] == "REQUIRED"
    assert out["effective_applicability_state"] == "REQUIRED"
    rec = (out.get("applicability_provenance") or {}).get("operational_applicability_reconciliation") or {}
    assert rec.get("source") == "scotland_landlord_registration_operational_surfaced_actionable_v1"


def _rent_smart_wales_like_row(**kwargs):
    base = {
        "requirement_id": "7cc14ad8-034e-4062-8d28-0acb48e603c9",
        "requirement_type": "rent_smart_wales",
        "requirement_code": "rent_smart_wales",
        "jurisdiction": "Wales",
        "applicability": "UNKNOWN",
        "applicability_state": "UNKNOWN",
        "status": "PENDING",
        "client_surface_visible": True,
        "evidence_authority": {"state": EA_MISSING, "state_reason": "no_evidence_document"},
    }
    base.update(kwargs)
    return base


def test_rent_smart_wales_unknown_actionable_reconciles_to_required():
    row = _rent_smart_wales_like_row()
    assert rent_smart_wales_operational_applicability_reconciliation_eligible(row)
    out = reconcile_rent_smart_wales_operational_applicability(row)
    assert out["applicability_state"] == "REQUIRED"
    rec = (out.get("applicability_provenance") or {}).get("operational_applicability_reconciliation") or {}
    assert rec.get("source") == "rent_smart_wales_operational_surfaced_actionable_v1"


def test_scotland_landlord_registration_other_slug_not_reconciled():
    row = _scotland_landlord_reg_like_row(requirement_type="rent_smart_wales", requirement_code="rent_smart_wales")
    assert not scotland_landlord_registration_operational_applicability_reconciliation_eligible(row)


def test_true_not_required_stays_not_applicable():
    row = _legionella_like_row(
        applicability="NOT_REQUIRED",
        status="NOT_REQUIRED",
        evidence_authority={"state": EA_NOT_REQUIRED, "state_reason": "applicability_not_required"},
    )
    out = derive_client_lifecycle_fields(row)
    assert out["client_lifecycle_state"] == NOT_APPLICABLE
    assert not has_stale_not_required_authority_blob(row)


def test_fresh_missing_authority_action_required():
    row = _legionella_like_row(
        pipeline_applicability_state="UNKNOWN",
        effective_applicability_state="UNKNOWN",
        evidence_authority={"state": EA_MISSING, "state_reason": "no_evidence_document"},
    )
    out = derive_client_lifecycle_fields(row)
    assert out["client_lifecycle_state"] == ACTION_REQUIRED


def test_hidden_surface_not_stale():
    row = _legionella_like_row(client_surface_visible=False)
    assert not has_stale_not_required_authority_blob(row)


@pytest.mark.asyncio
async def test_refresh_syncs_only_stale_surfaced_rows(monkeypatch):
    stale = _legionella_like_row(requirement_id="stale-1")
    fresh = _legionella_like_row(
        requirement_id="fresh-1",
        evidence_authority={"state": EA_MISSING, "state_reason": "no_evidence_document"},
    )
    true_nr = _legionella_like_row(
        requirement_id="nr-1",
        applicability="NOT_REQUIRED",
        status="NOT_REQUIRED",
    )
    calls: list[str] = []

    async def _fake_sync(db, rid, **kwargs):
        calls.append(rid)

    class _Requirements:
        @staticmethod
        def find(*_a, **_k):
            class _Cur:
                async def __aiter__(self):
                    fixed = {
                        "stale-1": _legionella_like_row(
                            requirement_id="stale-1",
                            evidence_authority={
                                "state": EA_MISSING,
                                "state_reason": "no_evidence_document",
                            },
                        )
                    }
                    for rid in calls:
                        if rid in fixed:
                            yield fixed[rid]

            return _Cur()

    class _Db:
        requirements = _Requirements

    monkeypatch.setattr(
        "services.client_applicability_coherence.sync_requirement_evidence_authority",
        _fake_sync,
    )
    out = await refresh_stale_authority_for_client_requirements(
        _Db(), [stale, fresh, true_nr]
    )
    assert calls == ["stale-1"]
    assert (out[0].get("evidence_authority") or {}).get("state") == EA_MISSING


@pytest.mark.asyncio
async def test_refresh_idempotent_when_authority_already_coherent(monkeypatch):
    coherent = _legionella_like_row(
        evidence_authority={"state": EA_MISSING, "state_reason": "no_evidence_document"},
    )
    calls: list[str] = []

    async def _fake_sync(db, rid, **kwargs):
        calls.append(rid)

    monkeypatch.setattr(
        "services.client_applicability_coherence.sync_requirement_evidence_authority",
        _fake_sync,
    )
    await refresh_stale_authority_for_client_requirements(_DbStub(), [coherent])
    await refresh_stale_authority_for_client_requirements(_DbStub(), [coherent])
    assert calls == []


class _DbStub:
    class requirements:
        @staticmethod
        def find(*_a, **_k):
            class _Cur:
                async def __aiter__(self):
                    if False:
                        yield {}

            return _Cur()
