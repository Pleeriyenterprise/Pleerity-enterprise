"""
Stage X — Twin staging operational validation pytest entry (optional).

Skipped unless DISCOVERY_RUN_TWIN_STAGING=1 and MongoDB staging is configured.
Primary evidence: scripts/discovery_phase_1_twin_staging_validate.py
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("DISCOVERY_RUN_TWIN_STAGING") != "1",
    reason="Set DISCOVERY_RUN_TWIN_STAGING=1 to run against real staging MongoDB",
)


@pytest.mark.asyncio
async def test_twin_staging_validation_contract_cohort():
    from scripts.discovery_phase_1_twin_staging_validate import run_validation

    report = await run_validation(
        twin_export_path=None,
        workspace_manifest_path=None,
        allow_contract_cohort=True,
    )
    assert report.part_c_ingest is not None
    assert report.part_c_ingest.passed, report.part_c_ingest.failures
    assert report.part_l_readiness is not None
    assert report.part_l_readiness.status in ("GREEN", "AMBER")
    assert report.export_provenance == "contract_cohort"
