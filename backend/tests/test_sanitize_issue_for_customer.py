"""Issue API sanitisation for client portal."""
from services.customer_operational_language_service import sanitize_issue_for_customer

_LEGACY_MISSING = (
    "No acceptable evidence is linked for Gas Safety Certificate (CP12) at this property.\n\n"
    "Gap: MISSING_EVIDENCE (HIGH). Key: "
    "10b2ddba-e952-4484-91d1-a8f0299d0824:fedac677-cd2b-41fe-b5b8-b00f00ddfe67:5b1bb"
)


def test_sanitize_issue_strips_gap_language():
    issue = {
        "issue_id": "iss-1",
        "description": _LEGACY_MISSING,
        "source": "system",
        "created_from": "compliance",
        "triggering_rule": "compliance_gap:MISSING_EVIDENCE",
        "operational_root_key": "gap:key",
        "severity": "HIGH",
    }
    out = sanitize_issue_for_customer(issue)
    assert "MISSING_EVIDENCE" not in out["description"]
    assert "Gap:" not in out["description"]
    assert "operational_root_key" not in out
    assert "triggering_rule" not in out
    assert out["source_display"] == "Compliance follow-up"
