"""Bounded client applicability / authority coherence tests."""

import pytest

from services.client_applicability_coherence import (
    apply_client_applicability_presentation_overlay,
    authority_applicability_not_required_disagrees_with_row,
    has_stale_not_required_authority_blob,
    pipeline_not_required_disagrees_with_surfaced_row,
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


def test_presentation_overlay_aligns_effective_applicability():
    row = _legionella_like_row()
    out = apply_client_applicability_presentation_overlay(row)
    assert out["effective_applicability_state"] == "UNKNOWN"
    assert out["applicability_state"] == "UNKNOWN"


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
