"""PR4: operator applicability commands (service-level)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.applicability_operator_actions import (
    ApplicabilityOperatorActionError,
    MARK_NOT_REQUIRED,
    MARK_REQUIRED,
    REVOKE_OVERRIDE,
    execute_applicability_operator_command,
)
from services.applicability_provenance_backfill import pipeline_from_legacy_requirement
from services.applicability_provenance_selector import build_provenance_mongo_set


def _actor():
    return {"type": "user", "id": "admin-1", "email": "a@example.com"}


def _pipeline_snapshot_only(row: dict) -> str:
    if row.get("pipeline_applicability_state"):
        return str(row["pipeline_applicability_state"]).strip().upper()
    nested = row.get("applicability_provenance")
    if isinstance(nested, dict) and nested.get("pipeline_applicability_state"):
        return str(nested.get("pipeline_applicability_state")).strip().upper()
    return pipeline_from_legacy_requirement(row)


def _merged_after_mark(
    initial: dict,
    *,
    operator_override_applicability_state: str,
    resolution_reason_code: str,
    actor: dict,
    notes: str | None,
) -> dict:
    pipe = _pipeline_snapshot_only(initial)
    prov_patch = build_provenance_mongo_set(
        pipeline_applicability_state=pipe,
        operator_override_active=True,
        operator_override_applicability_state=operator_override_applicability_state,
    )
    prov_patch["applicability_state"] = prov_patch["effective_applicability_state"]
    ov = prov_patch["applicability_provenance"]["operator_override"]
    ov["resolution_reason_code"] = str(resolution_reason_code).strip().upper()
    if notes and str(notes).strip():
        ov["resolution_notes"] = str(notes).strip()
    ov["actor"] = dict(actor)
    return {**initial, **prov_patch}


def _merged_after_revoke(initial: dict) -> dict:
    pipe = _pipeline_snapshot_only(initial)
    prov_patch = build_provenance_mongo_set(
        pipeline_applicability_state=pipe,
        operator_override_active=False,
        operator_override_applicability_state=None,
    )
    prov_patch["applicability_state"] = prov_patch["effective_applicability_state"]
    return {**initial, **prov_patch}


@pytest.mark.asyncio
async def test_mark_required_sets_effective_audits_and_syncs_gaps_quietly() -> None:
    initial = {
        "client_id": "c1",
        "requirement_id": "r1",
        "property_id": "p1",
        "pipeline_applicability_state": "UNKNOWN",
    }
    post = _merged_after_mark(
        initial,
        operator_override_applicability_state="REQUIRED",
        resolution_reason_code="MANUAL_LEGAL_REVIEW",
        actor=_actor(),
        notes="confirmed",
    )
    with patch(
        "services.applicability_operator_actions.sync_compliance_gaps_for_requirement",
        new_callable=AsyncMock,
    ) as m_sync:
        m_sync.return_value = {"rows": [], "errors": []}
        db = MagicMock()
        db.requirements.find_one = AsyncMock(side_effect=[initial, post])
        db.requirements.update_one = AsyncMock()
        db.properties.find_one = AsyncMock(return_value={"property_id": "p1", "jurisdiction": "England"})
        db.applicability_resolution_audit = MagicMock(insert_one=AsyncMock())
        out = await execute_applicability_operator_command(
            db,
            client_id="c1",
            requirement_id="r1",
            command=MARK_REQUIRED,
            resolution_reason_code="MANUAL_LEGAL_REVIEW",
            actor=_actor(),
            notes="confirmed",
        )
        assert out["effective_applicability_state"] == "REQUIRED"
        assert out["pipeline_applicability_state"] == "UNKNOWN"
        db.requirements.update_one.assert_awaited_once()
        db.applicability_resolution_audit.insert_one.assert_awaited_once()
        args, _kwargs = db.requirements.update_one.await_args
        assert args[0] == {"client_id": "c1", "requirement_id": "r1"}
        mongo_set = args[1]["$set"]
        assert mongo_set["applicability_state"] == "REQUIRED"
        assert mongo_set["operator_override_active"] is True
        assert (
            mongo_set["applicability_provenance"]["operator_override"]["resolution_reason_code"]
            == "MANUAL_LEGAL_REVIEW"
        )
        m_sync.assert_awaited_once()
        c_kw = m_sync.await_args.kwargs
        assert c_kw.get("audit_lifecycle") is False
        assert c_kw.get("run_operational_bridge") is False
        assert m_sync.await_args.args[1] is post
        db.properties.find_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_not_required_syncs_gaps_quietly() -> None:
    initial = {
        "client_id": "c1",
        "requirement_id": "r1",
        "property_id": "p1",
        "pipeline_applicability_state": "UNKNOWN",
    }
    post = _merged_after_mark(
        initial,
        operator_override_applicability_state="NOT_REQUIRED",
        resolution_reason_code="PROPERTY_TYPE_EXEMPT",
        actor=_actor(),
        notes=None,
    )
    with patch(
        "services.applicability_operator_actions.sync_compliance_gaps_for_requirement",
        new_callable=AsyncMock,
    ) as m_sync:
        m_sync.return_value = {"rows": [], "errors": []}
        db = MagicMock()
        db.requirements.find_one = AsyncMock(side_effect=[initial, post])
        db.requirements.update_one = AsyncMock()
        db.properties.find_one = AsyncMock(return_value=None)
        db.applicability_resolution_audit = MagicMock(insert_one=AsyncMock())
        out = await execute_applicability_operator_command(
            db,
            client_id="c1",
            requirement_id="r1",
            command=MARK_NOT_REQUIRED,
            resolution_reason_code="PROPERTY_TYPE_EXEMPT",
            actor=_actor(),
        )
        assert out["effective_applicability_state"] == "NOT_REQUIRED"
        m_sync.assert_awaited_once()
        assert m_sync.await_args.kwargs.get("audit_lifecycle") is False
        assert m_sync.await_args.kwargs.get("run_operational_bridge") is False


@pytest.mark.asyncio
async def test_revoke_returns_effective_to_pipeline_and_syncs_gaps_quietly() -> None:
    initial = {
        "client_id": "c1",
        "requirement_id": "r1",
        "property_id": "p1",
        "pipeline_applicability_state": "REQUIRED",
        "effective_applicability_state": "NOT_REQUIRED",
        "operator_override_active": True,
        "applicability_provenance": {
            "operator_override": {"active": True, "applicability_state": "NOT_REQUIRED"},
            "pipeline_applicability_state": "REQUIRED",
        },
    }
    post = _merged_after_revoke(initial)
    with patch(
        "services.applicability_operator_actions.sync_compliance_gaps_for_requirement",
        new_callable=AsyncMock,
    ) as m_sync:
        m_sync.return_value = {"rows": [], "errors": []}
        db = MagicMock()
        db.requirements.find_one = AsyncMock(side_effect=[initial, post])
        db.requirements.update_one = AsyncMock()
        db.properties.find_one = AsyncMock(return_value=None)
        db.applicability_resolution_audit = MagicMock(insert_one=AsyncMock())
        out = await execute_applicability_operator_command(
            db,
            client_id="c1",
            requirement_id="r1",
            command=REVOKE_OVERRIDE,
            resolution_reason_code="DATA_CORRECTION_PENDING",
            actor=_actor(),
        )
        assert out["effective_applicability_state"] == "REQUIRED"
        assert out["pipeline_applicability_state"] == "REQUIRED"
        uargs, _ = db.requirements.update_one.await_args
        mongo_set = uargs[1]["$set"]
        assert mongo_set["operator_override_active"] is False
        assert mongo_set["applicability_state"] == "REQUIRED"
        m_sync.assert_awaited_once()
        assert m_sync.await_args.kwargs.get("audit_lifecycle") is False
        assert m_sync.await_args.kwargs.get("run_operational_bridge") is False


@pytest.mark.asyncio
async def test_invalid_reason_400() -> None:
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value={"client_id": "c1", "requirement_id": "r1"})
    with pytest.raises(ApplicabilityOperatorActionError) as ei:
        await execute_applicability_operator_command(
            db,
            client_id="c1",
            requirement_id="r1",
            command=MARK_REQUIRED,
            resolution_reason_code="NOT_A_REAL_CODE",
            actor=_actor(),
        )
    assert ei.value.status_code == 400


@pytest.mark.asyncio
async def test_not_found_404() -> None:
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=None)
    with pytest.raises(ApplicabilityOperatorActionError) as ei:
        await execute_applicability_operator_command(
            db,
            client_id="c1",
            requirement_id="r1",
            command=MARK_REQUIRED,
            resolution_reason_code="MANUAL_LEGAL_REVIEW",
            actor=_actor(),
        )
    assert ei.value.status_code == 404


@pytest.mark.asyncio
async def test_actor_id_required_for_user() -> None:
    db = MagicMock()
    with pytest.raises(ApplicabilityOperatorActionError):
        await execute_applicability_operator_command(
            db,
            client_id="c1",
            requirement_id="r1",
            command=MARK_REQUIRED,
            resolution_reason_code="MANUAL_LEGAL_REVIEW",
            actor={"type": "user", "id": ""},
        )
