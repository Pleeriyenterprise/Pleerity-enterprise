from services.agreement_commercial_snapshot import commercial_snapshots_match


def test_commercial_snapshots_match_equal():
    a = {
        "client_full_name": "Jane",
        "client_company_name": "",
        "client_address": "1 High St, G1 1AA",
        "client_email": "j@ex.com",
        "selected_plan_code": "PLAN_1_SOLO",
        "plan_label": "Solo",
        "billing_amount_minor": 1900,
        "billing_interval": "month",
        "onboarding_fee_minor": 4900,
        "currency": "GBP",
        "agreement_template_id": "t1",
        "agreement_template_version_id": "v1",
    }
    ok, mm = commercial_snapshots_match(a, dict(a))
    assert ok and not mm


def test_commercial_snapshots_mismatch_on_plan():
    a = {"selected_plan_code": "PLAN_1_SOLO", "billing_amount_minor": 1900}
    b = {"selected_plan_code": "PLAN_2_PORTFOLIO", "billing_amount_minor": 1900}
    ok, mm = commercial_snapshots_match({**{k: "" for k in [
        "client_full_name", "client_company_name", "client_address", "client_email",
        "plan_label", "billing_interval", "onboarding_fee_minor", "currency",
        "agreement_template_id", "agreement_template_version_id",
    ]}, **a}, {**{k: "" for k in [
        "client_full_name", "client_company_name", "client_address", "client_email",
        "plan_label", "billing_interval", "onboarding_fee_minor", "currency",
        "agreement_template_id", "agreement_template_version_id",
    ]}, **b})
    assert not ok
    assert "selected_plan_code" in mm
