from services.compliance_status_authority import classify_compliance_status


def test_status_high_risk_for_critical_unresolved():
    rows = [
        {"status": "OVERDUE", "requirement_type": "gas_safety", "mandatory": True},
        {"status": "COMPLIANT", "requirement_type": "epc"},
    ]
    out = classify_compliance_status(rows)
    assert out.status == "HIGH RISK"


def test_status_action_required_for_mandatory_unresolved_noncritical():
    rows = [
        {"status": "OVERDUE", "requirement_type": "epc", "mandatory": True},
    ]
    out = classify_compliance_status(rows)
    assert out.status == "ACTION REQUIRED"


def test_status_partially_compliant_for_minor_pending_only():
    rows = [
        {"status": "EXPIRING_SOON", "requirement_type": "epc"},
        {"status": "COMPLIANT", "requirement_type": "pat_testing"},
    ]
    out = classify_compliance_status(rows)
    assert out.status == "PARTIALLY COMPLIANT"


def test_status_compliant_when_no_unresolved_obligations():
    rows = [
        {"status": "COMPLIANT", "requirement_type": "epc"},
        {"status": "COMPLIANT", "requirement_type": "eicr"},
    ]
    out = classify_compliance_status(rows)
    assert out.status == "COMPLIANT"

