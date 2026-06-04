"""REPORTING-ENTERPRISE-PRESENTATION-PHASE-02 — layout governance unit tests."""

from datetime import datetime, timezone

from services.report_layout_governance import (
    GovernancePdfContext,
    assurance_tier_chip,
    collect_unresolved_obligations,
    date_confidence_label,
    governance_chip_line,
    is_unresolved_row,
    matrix_continuation_stats,
    MATRIX_MAX_PROPERTIES_DISPLAY,
    MATRIX_MAX_ROWS_PER_PROPERTY,
)
from services.reporting_semantics_v1 import EXPORT_DETERMINISM_LIVE_REGENERATED, GRADE_CLIENT_PRESENTATION


def test_date_confidence_estimated_from_authority():
    row = {"evidence_authority": {"effective_expiry_is_estimated": True}, "due_date": "2026-01-01"}
    assert date_confidence_label(row) == "EST"


def test_assurance_tier_self_recorded():
    assert assurance_tier_chip({"assurance_tier": "SELF_RECORDED"}) == "Self-recorded assurance"


def test_governance_chip_includes_review_when_pending():
    line = governance_chip_line({"client_lifecycle_state": "PENDING_REVIEW"})
    assert "Awaiting review" in line or "review" in line.lower()


def test_unresolved_collects_action_required():
    props = [{"property_id": "p1", "address_line_1": "1 High St"}]
    reqs = [
        {
            "property_id": "p1",
            "client_lifecycle_state": "ACTION_REQUIRED",
            "description": "Gas safety",
        }
    ]
    rows, total = collect_unresolved_obligations(reqs, props, {})
    assert total == 1
    assert len(rows) == 1
    assert rows[0]["reason"]


def test_matrix_continuation_stats_omitted_rows():
    props = [{"property_id": f"p{i}"} for i in range(MATRIX_MAX_PROPERTIES_DISPLAY + 3)]
    reqs = []
    for i, p in enumerate(props):
        for j in range(30 if i == 0 else 5):
            reqs.append({"property_id": p["property_id"], "requirement_type": f"r{i}_{j}"})
    stats = matrix_continuation_stats(props, reqs)
    assert stats["properties_omitted"] == 3
    assert stats["requirement_rows_omitted"] > 0


def test_live_regenerated_ctx():
    ctx = GovernancePdfContext(
        export_grade=GRADE_CLIENT_PRESENTATION,
        export_grade_label="Client presentation",
        generated_at=datetime.now(timezone.utc),
        determinism=EXPORT_DETERMINISM_LIVE_REGENERATED,
        original_generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        regenerated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    assert ctx.is_live_regenerated


def test_is_unresolved_verified_false():
    row = {"client_lifecycle_state": "VERIFIED", "status": "COMPLIANT"}
    assert not is_unresolved_row(row, property_doc=None, client_doc={})
