"""
Stage V — real staging validation pytest entry (optional).

Skipped unless DISCOVERY_RUN_REAL_STAGING=1 and MONGO_URL/MONGO_URI is configured.
Primary evidence: scripts/discovery_phase_1_real_staging_validate.py
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("DISCOVERY_RUN_REAL_STAGING") != "1",
    reason="Set DISCOVERY_RUN_REAL_STAGING=1 to run against real staging MongoDB",
)


@pytest.mark.asyncio
async def test_real_staging_validation_green():
    from scripts.discovery_phase_1_real_staging_validate import run_validation

    report = await run_validation()
    assert report.part_k_go_no_go is not None
    assert report.part_k_go_no_go.status == "GREEN", report.part_k_go_no_go.metadata
    assert "YES" in report.twin_onboarding_answer
