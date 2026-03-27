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


def test_postcode_outward_match():
    c = {"areas_served": ["SW1A 1AA"]}
    assert cs.contractor_location_matches_property(c, "SW1A 2BB") is True
    c2 = {"areas_served": ["M1 1AE"]}
    assert cs.contractor_location_matches_property(c2, "SW1A 2BB") is False


def test_property_scope():
    c = {"property_scope": ["p1", "p2"]}
    assert cs.contractor_property_scope_allows(c, "p1") is True
    assert cs.contractor_property_scope_allows(c, "p9") is False
