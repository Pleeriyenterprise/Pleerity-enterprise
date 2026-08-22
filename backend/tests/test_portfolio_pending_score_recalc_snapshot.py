"""Unit tests for portfolio pending score recalc honesty fields on compliance score payloads."""

from services.compliance_score import portfolio_pending_score_recalc_snapshot


def test_pending_snapshot_zero_when_none_pending():
    props = [
        {"property_id": "p1", "compliance_score": 80, "compliance_score_pending": False},
        {"property_id": "p2", "compliance_score": 70},
    ]
    snap = portfolio_pending_score_recalc_snapshot(props)
    assert snap["properties_pending_score_recalc_count"] == 0
    assert snap["portfolio_score_recalc_pending_note"] is None


def test_pending_snapshot_counts_and_note():
    props = [
        {"property_id": "p1", "compliance_score": 80, "compliance_score_pending": True},
        {"property_id": "p2", "compliance_score": 70, "compliance_score_pending": False},
        {"property_id": "p3", "compliance_score": 90, "compliance_score_pending": True},
    ]
    snap = portfolio_pending_score_recalc_snapshot(props)
    assert snap["properties_pending_score_recalc_count"] == 2
    assert snap["portfolio_score_recalc_pending_note"]
    assert "2" in snap["portfolio_score_recalc_pending_note"]
    assert "headline" in snap["portfolio_score_recalc_pending_note"].lower()


def test_pending_snapshot_ignores_parked_debt():
    snap = portfolio_pending_score_recalc_snapshot(
        [
            {
                "property_id": "p1",
                "compliance_score": 80,
                "compliance_score_pending": True,
                "compliance_score_recalc_state": "parked",
            }
        ],
    )
    assert snap["properties_pending_score_recalc_count"] == 0
    assert snap["portfolio_score_recalc_pending_note"] is None
    assert snap["properties_parked_score_recalc_count"] == 1


def test_pending_snapshot_singular_note():
    snap = portfolio_pending_score_recalc_snapshot(
        [{"property_id": "p1", "compliance_score": 80, "compliance_score_pending": True}],
    )
    assert snap["properties_pending_score_recalc_count"] == 1
    assert "property has" in snap["portfolio_score_recalc_pending_note"]
