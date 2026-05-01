"""
Freeze `compliance_outcome_engine.ALL_EVENTS` branching (Stream E — outcome coverage).

When adding an event to ALL_EVENTS or changing apply_action_outcome pre-recalc branches,
update EXPECTED_ALL_EVENTS and OUTCOME_COVERAGE_EXPECTATIONS, and the matrix appendix
in STREAM_E_MUTATION_FANOUT_MATRIX.md.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Must match services.compliance_outcome_engine.ALL_EVENTS — intentional duplication to force
# an explicit edit when a new event is added.
EXPECTED_ALL_EVENTS = frozenset(
    {
        "certificate_uploaded",
        "certificate_verified",
        "issue_created",
        "issue_resolved",
        "work_order_completed",
        "requirement_completed",
        "risk_signal_acknowledged",
        "risk_signal_resolved",
    }
)


def test_all_events_frozen_set_matches_engine():
    from services.compliance_outcome_engine import ALL_EVENTS

    assert ALL_EVENTS == EXPECTED_ALL_EVENTS, (
        "ALL_EVENTS changed — update EXPECTED_ALL_EVENTS, OUTCOME_COVERAGE_EXPECTATIONS, "
        "and STREAM_E_MUTATION_FANOUT_MATRIX.md appendix."
    )


async def _run_engine_with_mocks(
    *,
    event: Dict[str, Any],
    authority_matches: list[dict],
) -> Dict[str, Any]:
    """Run apply_action_outcome with shared DB stubs; returns call counters."""
    from services import compliance_outcome_engine as coe

    db = MagicMock()
    db.compliance_activity_log.find_one = AsyncMock(return_value=None)
    db.compliance_activity_log.insert_one = AsyncMock()
    db.properties.find_one = AsyncMock(
        side_effect=[
            {"compliance_score": 50, "compliance_status": "RED"},
            {"compliance_score": 52, "compliance_status": "RED"},
        ]
    )
    db.properties.update_one = AsyncMock()
    db.requirements.update_many = AsyncMock()
    req_find = MagicMock()
    req_find.to_list = AsyncMock(return_value=authority_matches)
    db.requirements.find = MagicMock(return_value=req_find)
    db.risk_signals.count_documents = AsyncMock(return_value=0)
    db.risk_signals.update_many = AsyncMock()

    sync_mock = AsyncMock()
    recalc_mock = AsyncMock()

    with (
        patch("services.compliance_outcome_engine.database.get_db", return_value=db),
        patch("services.requirement_evidence_authority.sync_requirement_evidence_authority", sync_mock),
        patch("services.compliance_outcome_engine.recalculate_and_persist", recalc_mock),
        patch.object(coe, "_count_active_risk_signals", new_callable=AsyncMock, return_value=0),
        patch.object(coe, "_sync_regenerate_risks_and_operational", new_callable=AsyncMock),
    ):
        await coe.apply_action_outcome(event)

    return {
        "requirements_update_many": db.requirements.update_many.await_count,
        "requirements_find": db.requirements.find.call_count,
        "authority_sync": sync_mock.await_count,
        "risk_update_many": db.risk_signals.update_many.await_count,
        "recalc": recalc_mock.await_count,
    }


def _base_event(event_type: str, **extra: Any) -> Dict[str, Any]:
    return {
        "event_type": event_type,
        "client_id": "c_cov",
        "property_id": "p_cov",
        "source_id": f"src_{event_type}",
        "dedupe_key": f"cov:{event_type}:{extra.get('_suffix', 'default')}",
        "actor_id": "u_cov",
        "actor_role": "SYSTEM",
        **{k: v for k, v in extra.items() if not str(k).startswith("_")},
    }


# Canonical payloads and expected call counts (non-idempotent path).
OUTCOME_COVERAGE_EXPECTATIONS: list[tuple[str, Dict[str, Any], Dict[str, int]]] = [
    (
        "certificate_uploaded",
        _base_event("certificate_uploaded", requirement_type="GAS_SAFETY", _suffix="a"),
        {
            "requirements_update_many": 0,
            "requirements_find": 0,
            "authority_sync": 0,
            "risk_update_many": 0,
            "recalc": 1,
        },
    ),
    (
        "certificate_verified_with_requirement_type",
        _base_event("certificate_verified", requirement_type="GAS_SAFETY", _suffix="b"),
        {
            "requirements_update_many": 1,
            "requirements_find": 1,
            "authority_sync": 2,
            "risk_update_many": 1,
            "recalc": 1,
        },
    ),
    (
        "requirement_completed_with_requirement_type",
        _base_event("requirement_completed", requirement_type="EICR", _suffix="c"),
        {
            "requirements_update_many": 1,
            "requirements_find": 1,
            "authority_sync": 2,
            "risk_update_many": 1,
            "recalc": 1,
        },
    ),
    (
        "issue_created",
        _base_event("issue_created", _suffix="d"),
        {
            "requirements_update_many": 0,
            "requirements_find": 0,
            "authority_sync": 0,
            "risk_update_many": 0,
            "recalc": 1,
        },
    ),
    (
        "issue_resolved",
        _base_event("issue_resolved", _suffix="e"),
        {
            "requirements_update_many": 0,
            "requirements_find": 0,
            "authority_sync": 0,
            "risk_update_many": 1,
            "recalc": 1,
        },
    ),
    (
        "work_order_completed_without_flag",
        _base_event("work_order_completed", _suffix="f"),
        {
            "requirements_update_many": 0,
            "requirements_find": 0,
            "authority_sync": 0,
            "risk_update_many": 0,
            "recalc": 1,
        },
    ),
    (
        "work_order_completed_with_resolve_risks",
        _base_event(
            "work_order_completed",
            requirement_type="GAS_SAFETY",
            metadata={"resolve_linked_compliance_risks": True},
            _suffix="g",
        ),
        {
            "requirements_update_many": 0,
            "requirements_find": 0,
            "authority_sync": 0,
            "risk_update_many": 1,
            "recalc": 1,
        },
    ),
    (
        "risk_signal_acknowledged",
        _base_event("risk_signal_acknowledged", _suffix="h"),
        {
            "requirements_update_many": 0,
            "requirements_find": 0,
            "authority_sync": 0,
            "risk_update_many": 1,
            "recalc": 1,
        },
    ),
    (
        "risk_signal_resolved",
        _base_event("risk_signal_resolved", _suffix="i"),
        {
            "requirements_update_many": 0,
            "requirements_find": 0,
            "authority_sync": 0,
            "risk_update_many": 1,
            "recalc": 1,
        },
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario,event,expected", OUTCOME_COVERAGE_EXPECTATIONS)
async def test_outcome_engine_branching_matches_frozen_expectations(
    scenario: str,
    event: Dict[str, Any],
    expected: Dict[str, int],
):
    authority_rows = [{"requirement_id": "r_a"}, {"requirement_id": "r_b"}]
    actual = await _run_engine_with_mocks(event=event, authority_matches=authority_rows)
    assert actual == expected, f"scenario={scenario} actual={actual} expected={expected}"


@pytest.mark.asyncio
async def test_certificate_verified_empty_requirement_type_still_resolves_risk_no_authority():
    """Document empty requirement_type: no compliant-set sync, but risk resolve still runs."""
    from services import compliance_outcome_engine as coe

    event = _base_event("certificate_verified", requirement_type="", _suffix="empty")
    actual = await _run_engine_with_mocks(event=event, authority_matches=[])
    assert actual == {
        "requirements_update_many": 0,
        "requirements_find": 0,
        "authority_sync": 0,
        "risk_update_many": 1,
        "recalc": 1,
    }
