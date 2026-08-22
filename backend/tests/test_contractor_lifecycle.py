"""Unit tests for contractor lifecycle helpers (no DB)."""
from services import contractor_service as cs


def test_assignable_requires_active_portal_vetted():
    base = {
        "status": "approved",
        "vetted": True,
        "email": "a@b.com",
        "portal_access_status": "enabled",
        "trade_types": ["plumbing"],
    }
    ok, _ = cs.contractor_is_assignable(base)
    assert ok is False
    base["status"] = "active"
    ok, msg = cs.contractor_is_assignable(base)
    assert ok is True, msg


def test_assignable_rejects_no_email():
    ok, msg = cs.contractor_is_assignable(
        {"status": "active", "vetted": True, "portal_access_status": "enabled", "email": ""}
    )
    assert ok is False
    assert "email" in msg.lower()


def test_trade_match():
    c = {"trade_types": ["Plumbing"]}
    assert cs.contractor_trade_matches_category(c, "plumbing_repair") is True
    assert cs.contractor_trade_matches_category(c, "electrical") is False
    assert cs.contractor_trade_matches_category(c, "general") is True
    assert cs.contractor_trade_matches_category({"trade_types": ["plumber"]}, "plumbing") is True
    assert cs.contractor_trade_matches_category({"trade_types": []}, "general") is False
    assert cs.contractor_trade_matches_category({"trade_types": ["plumbing", "electrical"]}, "heating") is False


def test_infer_maintenance_category_from_leak_description():
    assert cs.infer_maintenance_category("Leak under bathroom sink") == "plumbing"
    assert cs.infer_maintenance_category("socket sparking", "electrician") == "electrical"


def test_trade_mismatch_message_names_required_and_actual():
    msg = cs.contractor_trade_mismatch_message(
        {"company_name": "Hartley Plumbing Ltd", "trade_types": ["plumbing"]},
        "electrical",
    )
    assert "electrical" in msg.lower()
    assert "plumbing" in msg.lower()
    assert "Hartley Plumbing Ltd" in msg
    assert "Assignment failed" in msg


def test_postcode_outward_match():
    c = {"areas_served": ["SW1A 1AA"]}
    assert cs.contractor_location_matches_property(c, "SW1A 2BB") is True
    c2 = {"areas_served": ["M1 1AE"]}
    assert cs.contractor_location_matches_property(c2, "SW1A 2BB") is False


def test_portfolio_region_matches_jurisdiction_not_postcode():
    """England in region must match England job — not compared as postcode."""
    c = {"region": "England"}
    assert cs.contractor_location_matches_property(c, "B1 1AA", property_jurisdiction="England") is True
    assert cs.contractor_location_matches_property(c, "B1 1AA", property_jurisdiction="Scotland") is False


def test_free_text_region_is_informational():
    c = {"areas_served": ["London", "Greater Manchester"]}
    assert cs.contractor_location_matches_property(c, "B1 1AA", property_jurisdiction="England") is True


def test_postcode_only_without_property_postcode_permissive():
    c = {"areas_served": ["SW1A"]}
    assert cs.contractor_location_matches_property(c, None) is True


def test_property_scope():
    c = {"property_scope": ["p1", "p2"]}
    assert cs.contractor_property_scope_allows(c, "p1") is True
    assert cs.contractor_property_scope_allows(c, "p9") is False
