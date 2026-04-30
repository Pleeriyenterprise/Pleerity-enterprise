from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.compliance_policy_backfill_service import (
    discover_tenant_ids,
    run_policy_backfill_for_tenants,
)


class _Cur:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, _n):
        return self._rows


@pytest.mark.asyncio
async def test_discover_tenants_from_authoritative_clients_with_bounds():
    db = MagicMock()
    db.clients.find = MagicMock(return_value=_Cur([{"client_id": "c001"}, {"client_id": "c002"}]))
    out = await discover_tenant_ids(
        db,
        all_tenants=True,
        limit=2,
        resume_from="c000",
        include_test_tenants=False,
        dry_run=True,
    )
    assert out["source"] == "clients"
    assert out["filters"]["all_tenants"] is True
    assert out["tenant_ids"] == ["c001", "c002"]
    q = db.clients.find.call_args[0][0]
    assert q["is_deleted"] == {"$ne": True}
    assert q["is_test_like"] == {"$ne": True}
    assert q["client_id"]["$gt"] == "c000"


@pytest.mark.asyncio
async def test_orchestrator_dry_run_returns_convergence_shape():
    db = MagicMock()
    with patch(
        "services.compliance_policy_backfill_service.get_tenant_policy_convergence_status",
        new=AsyncMock(
            return_value={
                "client_id": "c1",
                "requirement_coverage_percent": 100.0,
                "gap_coverage_percent": 100.0,
                "last_checkpoint_state": {},
                "eligible_for_pr5": True,
            }
        ),
    ):
        out = await run_policy_backfill_for_tenants(
            db,
            tenant_ids=["c1"],
            dry_run=True,
            max_tenants=10,
        )
    tr = out["tenant_results"]["c1"]
    assert tr["mode"] == "dry_run"
    assert "status" in tr
    assert tr["eligible_for_pr5"] is True


@pytest.mark.asyncio
async def test_orchestrator_skips_converged_unless_force():
    db = MagicMock()
    with patch(
        "services.compliance_policy_backfill_service.get_tenant_policy_convergence_status",
        new=AsyncMock(
            return_value={
                "client_id": "c1",
                "requirement_coverage_percent": 100.0,
                "gap_coverage_percent": 100.0,
                "last_checkpoint_state": {},
                "eligible_for_pr5": True,
            }
        ),
    ), patch(
        "services.compliance_policy_backfill_service.run_tenant_requirement_policy_backfill",
        new=AsyncMock(return_value={}),
    ) as req_job, patch(
        "services.compliance_policy_backfill_service.run_tenant_gap_policy_reconciliation",
        new=AsyncMock(return_value={}),
    ) as gap_job:
        out = await run_policy_backfill_for_tenants(db, tenant_ids=["c1"], force=False, dry_run=False)
    assert out["tenant_results"]["c1"]["mode"] == "skipped_converged"
    assert req_job.await_count == 0
    assert gap_job.await_count == 0


@pytest.mark.asyncio
async def test_orchestrator_force_executes_converged_tenant():
    db = MagicMock()
    with patch(
        "services.compliance_policy_backfill_service.get_tenant_policy_convergence_status",
        new=AsyncMock(
            side_effect=[
                {
                    "client_id": "c1",
                    "requirement_coverage_percent": 100.0,
                    "gap_coverage_percent": 100.0,
                    "last_checkpoint_state": {},
                    "eligible_for_pr5": True,
                },
                {
                    "client_id": "c1",
                    "requirement_coverage_percent": 100.0,
                    "gap_coverage_percent": 100.0,
                    "last_checkpoint_state": {},
                    "eligible_for_pr5": True,
                },
            ]
        ),
    ), patch(
        "services.compliance_policy_backfill_service.run_tenant_requirement_policy_backfill",
        new=AsyncMock(return_value={"processed": 1, "updated": 0, "failed": 0}),
    ) as req_job, patch(
        "services.compliance_policy_backfill_service.run_tenant_gap_policy_reconciliation",
        new=AsyncMock(return_value={"processed": 1, "updated": 0, "failed": 0}),
    ) as gap_job:
        out = await run_policy_backfill_for_tenants(db, tenant_ids=["c1"], force=True, dry_run=False)
    assert out["tenant_results"]["c1"]["mode"] == "executed"
    assert req_job.await_count == 1
    assert gap_job.await_count == 1
