from unittest.mock import MagicMock, patch

import pytest

from services.compliance_gap_sync import aggregate_gap_counts_for_client


class _Cur:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, _n):
        return self._rows


@pytest.mark.asyncio
async def test_aggregate_gap_counts_preserves_legacy_and_adds_policy():
    db = MagicMock()
    db.compliance_gaps.aggregate = MagicMock(
        return_value=_Cur(
            [
                {"_id": {"kind": "EXPIRED", "sev": "HIGH"}, "c": 4},
                {"_id": {"kind": "MISSING_EVIDENCE", "sev": "MEDIUM"}, "c": 3},
            ]
        )
    )
    with patch(
        "services.compliance_gap_sync.aggregate_policy_gap_counts_for_client",
        return_value={
            "critical_mandatory_breach_count": 1,
            "high_risk_gap_count": 2,
            "attention_only_gap_count": 0,
            "unknown_or_stale_signal_count": 0,
            "policy_fields_present_count": 7,
            "policy_coverage_percent": 100.0,
            "top_reason_codes": {"UNRESOLVED_HIGH_RISK_GAP": 2},
            "policy_versions": {"v1": 7},
            "total_open": 7,
        },
    ):
        out = await aggregate_gap_counts_for_client(db, "c1")
    assert out["by_kind"]["EXPIRED"] == 4
    assert out["by_severity"]["HIGH"] == 4
    assert out["total_open"] == 7
    assert out["policy"]["high_risk_gap_count"] == 2
    assert "by_kind" in out and "by_severity" in out
