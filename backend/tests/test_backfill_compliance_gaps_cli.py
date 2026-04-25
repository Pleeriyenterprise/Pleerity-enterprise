"""CLI exit behaviour for backfill_compliance_gaps script."""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


def test_cli_exits_nonzero_when_result_contains_sync_errors():
    import scripts.backfill_compliance_gaps as mod

    with patch.object(
        sys,
        "argv",
        ["backfill_compliance_gaps.py", "--limit", "1"],
    ), patch(
        "scripts.backfill_compliance_gaps.asyncio.run",
        return_value={
            "dry_run": False,
            "requirements_scanned": 1,
            "errors": [{"stage": "upsert", "gap_key": "c:p:r:MISSING_EVIDENCE", "error": "failed"}],
        },
    ), pytest.raises(SystemExit) as ei:
        mod.main()
    assert ei.value.code == 1


def test_cli_exits_zero_when_no_errors():
    import scripts.backfill_compliance_gaps as mod

    with patch.object(
        sys,
        "argv",
        ["backfill_compliance_gaps.py", "--dry-run", "--limit", "1"],
    ), patch(
        "scripts.backfill_compliance_gaps.asyncio.run",
        return_value={"dry_run": True, "requirements_scanned": 1, "errors": []},
    ):
        mod.main()
