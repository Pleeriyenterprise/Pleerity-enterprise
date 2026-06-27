"""Phase 2 consumer migration — Compliance Timeline presentation consistency."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.compliance_timeline_presentation import (
    build_date_presentation_from_timeline,
    timeline_report_date_display,
    timeline_sort_date_iso,
)
from services.requirement_evidence_authority import EA_VERIFIED_CURRENT
from services.requirement_truth import (
    DATE_SOURCE_SYSTEM_ESTIMATED,
    enrich_requirement_dict,
)


def _verified_gas():
    expiry = (datetime.now(timezone.utc) + timedelta(days=180)).date().isoformat()
    return {
        "requirement_id": "req-1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "applicability": "REQUIRED",
        "status": "COMPLIANT",
        "evidence_authority": {
            "version": 1,
            "state": EA_VERIFIED_CURRENT,
            "effective_expiry_date": f"{expiry}T00:00:00+00:00",
            "effective_expiry_is_null": False,
        },
        "evidence_authority_synced_at": datetime.now(timezone.utc).isoformat(),
        "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "date_source": DATE_SOURCE_SYSTEM_ESTIMATED,
    }


def test_enrich_date_label_matches_timeline():
    row = _verified_gas()
    enriched = enrich_requirement_dict(row, live_evidence_state="VERIFIED", audience="client")
    assert enriched["date_label"] == enriched["timeline_primary_date_label"]
    assert enriched["timeline_primary_date"] == enriched["compliance_timeline"]["primary_date"]
    assert "Certificate expires" in enriched["date_label"]


def test_build_date_presentation_from_timeline_uses_projection():
    row = _verified_gas()
    from services.compliance_timeline import build_compliance_timeline

    timeline = build_compliance_timeline(row)
    row = {**row, **{
        "compliance_timeline": timeline,
        "timeline_primary_date": timeline["primary_date"],
        "timeline_primary_date_label": timeline["primary_date_label"],
        "timeline_primary_date_confidence": timeline["primary_date_confidence"],
    }}
    label, helper = build_date_presentation_from_timeline(row, "VERIFIED_DOCUMENT", "VERIFIED")
    assert label == timeline["primary_date_label"]
    assert helper is None


def test_timeline_sort_date_prefers_primary():
    row = _verified_gas()
    from services.compliance_timeline import build_compliance_timeline

    timeline = build_compliance_timeline(row)
    row = {
        **row,
        "compliance_timeline": timeline,
        "timeline_primary_date": timeline["primary_date"],
    }
    iso = timeline_sort_date_iso(row)
    assert iso == timeline["primary_date"]


def test_report_display_never_says_renewal_for_estimate():
    row = {
        "requirement_type": "gas_safety",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "date_source": DATE_SOURCE_SYSTEM_ESTIMATED,
    }
    from services.compliance_timeline import build_compliance_timeline

    timeline = build_compliance_timeline(row)
    enriched = {
        **row,
        "compliance_timeline": timeline,
        "timeline_primary_date_label": timeline["primary_date_label"],
    }
    display = timeline_report_date_display(enriched)
    assert "Estimated compliance date" in display
    assert "renewal" not in display.lower()


def test_cross_surface_label_consistency_after_enrich():
    row = _verified_gas()
    enriched = enrich_requirement_dict(row, live_evidence_state="VERIFIED", audience="client")
    report_display = timeline_report_date_display(enriched)
    assert report_display == enriched["timeline_primary_date_label"]
    assert enriched["date_label"] == report_display


def test_matrix_rows_include_timeline_expiry_display():
    from datetime import datetime, timezone
    from services.report_pdf_templates import build_matrix_rows

    row = _verified_gas()
    rows = build_matrix_rows(
        requirements=[row],
        properties=[{"property_id": "p1", "address_line_1": "1 Test St"}],
        client_doc={},
        now=datetime.now(timezone.utc),
    )
    assert len(rows) == 1
    assert rows[0]["expiry_display"]
    assert "Certificate expires" in rows[0]["expiry_display"]
    assert rows[0]["expiry"] != "—"


def test_human_operational_renewal_matches_enriched_label():
    from services.report_human_language_v1 import human_operational_renewal_date

    row = _verified_gas()
    enriched = enrich_requirement_dict(row, live_evidence_state="VERIFIED", audience="client")
    assert human_operational_renewal_date(enriched) == enriched["timeline_primary_date_label"]


def test_calendar_events_use_timeline_anchor():
    from datetime import datetime, timezone, timedelta
    from services.client_calendar_timeline_service import build_requirement_timeline_events
    from services.compliance_timeline import build_compliance_timeline

    row = _verified_gas()
    timeline = build_compliance_timeline(row)
    row = {
        **row,
        "compliance_timeline": timeline,
        "timeline_primary_date": timeline["primary_date"],
    }
    anchor = datetime.fromisoformat(f"{timeline['primary_date'][:10]}T00:00:00+00:00")
    start = anchor - timedelta(days=1)
    end = anchor + timedelta(days=2)
    events = build_requirement_timeline_events(
        [row],
        {"p1": {"property_id": "p1", "address_line_1": "1 Test St"}},
        start,
        end,
    )
    assert len(events) == 1
    assert events[0]["date"] == timeline["primary_date"][:10]


def test_scheduled_email_rows_use_timeline_renewal_wording():
    from services.report_requirements_operational import build_requirements_scheduled_email_rows

    enriched = [{
        "property": "1 Test St",
        "obligation": "Gas Safety Certificate",
        "status": "Compliant",
        "renewal": "Certificate expires: 15 Jun 2027",
        "urgency": "Routine",
        "triage_bucket": "monitoring",
        "recommended_action": "Monitor",
        "cluster": "Gas safety",
    }]
    rows = build_requirements_scheduled_email_rows(enriched)
    assert rows[0]["due_date"] == "Certificate expires: 15 Jun 2027"
    assert rows[0]["renewal_date"] == "Certificate expires: 15 Jun 2027"
