"""Backfill / convergence for persisted compliance_gaps."""
from __future__ import annotations

from typing import Any, List

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_requirements_cursor(rows: List[Any]) -> MagicMock:
    """Motor-style chained find().skip().limit().to_list()."""
    m = MagicMock()
    m.skip.return_value = m
    m.limit.return_value = m
    m.to_list = AsyncMock(return_value=rows)
    return m

from services.compliance_gap_backfill import (
    build_requirements_query,
    inspect_proposed_gap_composition,
    preview_gap_persistence_delta,
    run_compliance_gaps_backfill,
    transition_counts,
)
from services.compliance_gap_engine import GAP_AUTHORITY_UNSYNCED, stable_gap_key
from services.requirement_evidence_authority import AUTHORITY_VERSION, EA_VERIFIED_CURRENT


def test_transition_counts_open_resolve_unchanged():
    o, r, u = transition_counts({"a", "b"}, {"b", "c"})
    assert o == 1  # c
    assert r == 1  # a
    assert u == 1  # b


def test_build_requirements_query_scoped():
    q = build_requirements_query(client_id="c1", property_id="p1")
    assert q["client_id"] == "c1"
    assert q["property_id"] == "p1"


@pytest.mark.asyncio
async def test_preview_first_backfill_creates_gaps():
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "EPC",
        "applicability": "REQUIRED",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": AUTHORITY_VERSION, "state": "MISSING"},
    }
    db = MagicMock()
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[])
    delta = await preview_gap_persistence_delta(db, req, property_doc=None)
    assert delta["gaps_opened"] >= 1
    assert delta["gaps_resolved"] == 0
    assert delta["unchanged_gaps"] == 0


@pytest.mark.asyncio
async def test_preview_rerun_idempotent_no_new_opens():
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "EPC",
        "applicability": "REQUIRED",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": AUTHORITY_VERSION, "state": "MISSING"},
    }
    from services.compliance_gap_engine import infer_compliance_gaps_for_requirement

    gaps = infer_compliance_gaps_for_requirement(req, property_doc=None)
    assert gaps
    gk = gaps[0].to_mongo(client_id="c1", property_id="p1", requirement_id="r1", requirement_code="EPC")["gap_key"]
    db = MagicMock()
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[{"gap_key": gk}])
    delta = await preview_gap_persistence_delta(db, req, property_doc=None)
    assert delta["gaps_opened"] == 0
    assert delta["gaps_resolved"] == 0
    assert delta["unchanged_gaps"] == 1


@pytest.mark.asyncio
async def test_preview_resolved_requirement_closes_gap():
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "EPC",
        "applicability": "REQUIRED",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {
            "version": AUTHORITY_VERSION,
            "state": EA_VERIFIED_CURRENT,
            "effective_expiry_date": "2028-01-01T00:00:00+00:00",
        },
    }
    old_key = stable_gap_key("c1", "p1", "r1", "MISSING_EVIDENCE")
    db = MagicMock()
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[{"gap_key": old_key}])
    with patch("services.compliance_gap_engine.resolve_expiring_soon_days_for_requirement", return_value=30):
        delta = await preview_gap_persistence_delta(db, req, property_doc=None)
    assert delta["gaps_resolved"] >= 1
    assert delta["gaps_opened"] == 0


@pytest.mark.asyncio
async def test_preview_authority_unsynced_flag():
    # Legacy bridge does not run for COMPLIANT; unsynced authority yields AUTHORITY_UNSYNCED gap.
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "EPC",
        "status": "COMPLIANT",
        "applicability": "REQUIRED",
    }
    db = MagicMock()
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[])
    delta = await preview_gap_persistence_delta(db, req, property_doc=None)
    assert delta["authority_unsynced"] is True
    assert any(str(k).endswith(f":{GAP_AUTHORITY_UNSYNCED}") for k in (delta.get("desired_gap_keys") or []))


@pytest.mark.asyncio
async def test_backfill_dry_run_scoped_calls_find_with_query():
    req = {
        "client_id": "c-scoped",
        "property_id": "p-scoped",
        "requirement_id": "r-scoped",
        "requirement_code": "EPC",
        "status": "MISSING",
        "applicability": "REQUIRED",
    }
    db = MagicMock()
    db.requirements.find = MagicMock(return_value=_mock_requirements_cursor([req]))
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[])
    db.properties.find_one = AsyncMock(return_value=None)

    summary = await run_compliance_gaps_backfill(
        db,
        client_id="c-scoped",
        property_id="p-scoped",
        dry_run=True,
        batch_size=50,
        limit=10,
    )
    assert summary["dry_run"] is True
    assert summary["requirements_scanned"] == 1
    assert summary["requirements_active"] == 1
    find_kwargs = db.requirements.find.call_args
    assert find_kwargs[0][0]["client_id"] == "c-scoped"
    assert find_kwargs[0][0]["property_id"] == "p-scoped"


@pytest.mark.asyncio
async def test_backfill_full_run_invokes_sync_once_per_active_row():
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "EPC",
        "status": "MISSING",
        "applicability": "REQUIRED",
    }
    db = MagicMock()
    db.requirements.find = MagicMock(return_value=_mock_requirements_cursor([req]))
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[])
    db.properties.find_one = AsyncMock(return_value=None)

    with patch(
        "services.compliance_gap_backfill.sync_compliance_gaps_for_requirement",
        new=AsyncMock(return_value={"rows": [], "errors": []}),
    ) as sync:
        summary = await run_compliance_gaps_backfill(
            db, dry_run=False, batch_size=50, limit=5, audit_lifecycle=False, run_operational_bridge=False
        )
    assert summary["dry_run"] is False
    assert sync.await_count == 1
    assert sync.await_args.kwargs.get("audit_lifecycle") is False
    assert sync.await_args.kwargs.get("run_operational_bridge") is False


@pytest.mark.asyncio
async def test_backfill_second_dry_run_zero_new_opens_when_persisted_matches():
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "EPC",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": AUTHORITY_VERSION, "state": "MISSING"},
        "applicability": "REQUIRED",
    }
    from services.compliance_gap_engine import infer_compliance_gaps_for_requirement

    gk = infer_compliance_gaps_for_requirement(req, property_doc=None)[0].to_mongo(
        client_id="c1", property_id="p1", requirement_id="r1", requirement_code="EPC"
    )["gap_key"]
    db = MagicMock()
    db.requirements.find = MagicMock(return_value=_mock_requirements_cursor([req]))
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[{"gap_key": gk}])
    db.properties.find_one = AsyncMock(return_value=None)
    s1 = await run_compliance_gaps_backfill(db, dry_run=True, batch_size=50, limit=5)
    s2 = await run_compliance_gaps_backfill(db, dry_run=True, batch_size=50, limit=5)
    assert s1["gaps_opened"] == 0
    assert s2["gaps_opened"] == 0
    assert s1["unchanged_gaps"] >= 1


@pytest.mark.asyncio
async def test_inspect_proposed_net_new_counts_gaps_not_already_open():
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "EPC",
        "applicability": "REQUIRED",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": AUTHORITY_VERSION, "state": "MISSING"},
    }
    db = MagicMock()
    db.requirements.find = MagicMock(return_value=_mock_requirements_cursor([req]))
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[])
    db.properties.find_one = AsyncMock(return_value={"property_id": "p1", "jurisdiction": "England", "nickname": "N1"})
    out = await inspect_proposed_gap_composition(db, net_new_only=True, batch_size=50, limit=10)
    assert out["inspect_mode"] == "net_new_only"
    assert out["proposed_gap_rows_total"] >= 1
    assert sum(out["by_gap_kind"].values()) == out["proposed_gap_rows_total"]
    assert out["by_jurisdiction"].get("England", 0) >= 1
    assert "MISSING_EVIDENCE" in out["by_gap_kind"]


@pytest.mark.asyncio
async def test_inspect_proposed_scoped_client_property():
    req = {
        "client_id": "c-scoped",
        "property_id": "p-scoped",
        "requirement_id": "r1",
        "requirement_code": "EPC",
        "applicability": "REQUIRED",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": AUTHORITY_VERSION, "state": "MISSING"},
    }
    db = MagicMock()
    db.requirements.find = MagicMock(return_value=_mock_requirements_cursor([req]))
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[])
    db.properties.find_one = AsyncMock(return_value=None)
    await inspect_proposed_gap_composition(
        db, client_id="c-scoped", property_id="p-scoped", batch_size=50, limit=10, net_new_only=True
    )
    q = db.requirements.find.call_args[0][0]
    assert q["client_id"] == "c-scoped"
    assert q["property_id"] == "p-scoped"


@pytest.mark.asyncio
async def test_inspect_all_inferred_includes_existing_open_keys():
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "EPC",
        "applicability": "REQUIRED",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": AUTHORITY_VERSION, "state": "MISSING"},
    }
    from services.compliance_gap_engine import infer_compliance_gaps_for_requirement

    gk = infer_compliance_gaps_for_requirement(req, property_doc=None)[0].to_mongo(
        client_id="c1", property_id="p1", requirement_id="r1", requirement_code="EPC"
    )["gap_key"]
    db = MagicMock()
    db.requirements.find = MagicMock(return_value=_mock_requirements_cursor([req]))
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[{"gap_key": gk}])
    db.properties.find_one = AsyncMock(return_value=None)
    net_new = await inspect_proposed_gap_composition(db, net_new_only=True, batch_size=50, limit=10)
    all_inf = await inspect_proposed_gap_composition(db, net_new_only=False, batch_size=50, limit=10)
    assert net_new["proposed_gap_rows_total"] == 0
    assert all_inf["proposed_gap_rows_total"] >= 1


@pytest.mark.asyncio
async def test_backfill_propagates_sync_upsert_errors_to_summary():
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "EPC",
        "status": "MISSING",
        "applicability": "REQUIRED",
    }
    db = MagicMock()
    db.requirements.find = MagicMock(return_value=_mock_requirements_cursor([req]))
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[])
    db.properties.find_one = AsyncMock(return_value=None)

    fake_err = {"stage": "upsert", "gap_key": "c1:p1:r1:MISSING_EVIDENCE", "error": "conflict"}
    with patch(
        "services.compliance_gap_backfill.sync_compliance_gaps_for_requirement",
        new=AsyncMock(return_value={"rows": [], "errors": [fake_err]}),
    ):
        summary = await run_compliance_gaps_backfill(db, dry_run=False, batch_size=50, limit=5)
    assert summary["error_count"] == 1
    assert summary["errors"][0]["stage"] == "upsert"
    assert summary["errors"][0]["gap_key"] == fake_err["gap_key"]


@pytest.mark.asyncio
async def test_backfill_suppress_lifecycle_emits_summary_when_configured():
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "EPC",
        "status": "MISSING",
        "applicability": "REQUIRED",
    }
    db = MagicMock()
    db.requirements.find = MagicMock(return_value=_mock_requirements_cursor([req]))
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[])
    db.properties.find_one = AsyncMock(return_value=None)

    with patch(
        "services.compliance_gap_backfill.sync_compliance_gaps_for_requirement",
        new=AsyncMock(return_value={"rows": [], "errors": []}),
    ), patch(
        "services.compliance_gap_backfill.create_audit_log", new=AsyncMock()
    ) as audit:
        await run_compliance_gaps_backfill(
            db,
            client_id="c1",
            dry_run=False,
            audit_lifecycle=False,
            emit_batch_summary_audit=True,
            batch_size=50,
            limit=5,
        )
    from models import AuditAction

    kinds = [c.kwargs.get("action") for c in audit.await_args_list]
    assert AuditAction.COMPLIANCE_GAP_BACKFILL_COMPLETED in kinds
