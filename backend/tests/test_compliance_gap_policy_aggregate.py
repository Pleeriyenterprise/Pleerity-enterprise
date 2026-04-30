from unittest.mock import MagicMock

import pytest

from services.compliance_gap_policy_aggregate import aggregate_policy_gap_counts_for_client


class _Cur:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, _n):
        return self._rows


@pytest.mark.asyncio
async def test_policy_aggregate_returns_bounded_shape():
    db = MagicMock()
    captured = []

    def _agg(pipeline):
        captured.append(pipeline)
        if any("$unwind" in st for st in pipeline):
            return _Cur([{"_id": "UNRESOLVED_HIGH_RISK_GAP", "c": 12}])
        if any("$group" in st and st["$group"].get("_id") == "$policy_classification_version" for st in pipeline):
            return _Cur([{"_id": "v1", "c": 10}])
        return _Cur(
            [
                {
                    "_id": None,
                    "critical_mandatory_breach_count": 1,
                    "high_risk_gap_count": 2,
                    "attention_only_gap_count": 3,
                    "unknown_or_stale_signal_count": 1,
                    "policy_fields_present_count": 9,
                    "total_open": 10,
                }
            ]
        )

    db.compliance_gaps.aggregate = _agg
    out = await aggregate_policy_gap_counts_for_client(db, "c1", property_id="p1")
    assert out["critical_mandatory_breach_count"] == 1
    assert out["high_risk_gap_count"] == 2
    assert out["policy_coverage_percent"] == 90.0
    assert out["top_reason_codes"]["UNRESOLVED_HIGH_RISK_GAP"] == 12
    assert out["policy_versions"]["v1"] == 10
    # Tenant scope proof: every pipeline starts with client-scoped match.
    for p in captured:
        m = p[0]["$match"]
        assert m["client_id"] == "c1"
        assert m["status"] == "open"
        assert m["property_id"] == "p1"
