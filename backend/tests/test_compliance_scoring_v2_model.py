from datetime import datetime, timezone, timedelta

from services.compliance_scoring_v2 import compute_property_score_v2


def _base_property(jurisdiction="England"):
    return {
        "property_id": "p1",
        "jurisdiction": jurisdiction,
        "cert_gas_safety": "YES",
        "has_gas_supply": True,
    }


def test_v2_excludes_non_applicable_gas_from_denominator():
    result = compute_property_score_v2(
        property_doc={"property_id": "p1", "jurisdiction": "Scotland", "cert_gas_safety": "NO", "has_gas_supply": False},
        client_doc={"default_jurisdiction": "Scotland"},
        requirements=[],
        documents=[],
        open_issues_count=0,
        overdue_work_orders_count=0,
        open_risks_count=0,
        as_of=datetime.now(timezone.utc),
    )
    gas_row = next(r for r in result["requirement_breakdown"] if r["requirement_code"] == "GAS_SAFETY")
    assert gas_row["applies_if"] is False
    assert gas_row["applicable_points"] == 0.0


def test_v2_scores_valid_legal_docs_high():
    now = datetime.now(timezone.utc)
    docs = [
        {"requirement_code": "GAS_SAFETY", "document_type": "gas_safety", "expiry_date": (now + timedelta(days=180)).isoformat(), "status": "VERIFIED"},
        {"requirement_code": "EICR", "document_type": "eicr", "expiry_date": (now + timedelta(days=180)).isoformat(), "status": "VERIFIED"},
        {"requirement_code": "EPC", "document_type": "epc", "expiry_date": (now + timedelta(days=180)).isoformat(), "status": "VERIFIED"},
    ]
    result = compute_property_score_v2(
        property_doc=_base_property("England"),
        client_doc={"default_jurisdiction": "England"},
        requirements=[],
        documents=docs,
        open_issues_count=0,
        overdue_work_orders_count=0,
        open_risks_count=0,
        as_of=now,
    )
    assert result["score_0_100"] >= 70
    assert result["jurisdiction"] == "ENGLAND_WALES"
    assert result["applicable_points"] > 0


def test_v2_generates_top_actions_for_missing_critical():
    result = compute_property_score_v2(
        property_doc=_base_property("Scotland"),
        client_doc={"default_jurisdiction": "Scotland"},
        requirements=[],
        documents=[],
        open_issues_count=1,
        overdue_work_orders_count=0,
        open_risks_count=1,
        as_of=datetime.now(timezone.utc),
    )
    assert result["score_0_100"] < 60
    assert len(result["top_next_actions"]) > 0
    assert any("Upload and verify" in a["action"] for a in result["top_next_actions"])
