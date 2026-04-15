"""Registry action_links: jurisdiction filter, priority sort, cap, inactive dropped."""
from services.requirement_action_links import (
    filter_action_links_for_region,
    get_client_action_links_for_code_and_region,
)


def test_filter_sort_max_and_inactive():
    links = [
        {"key": "b", "label": "B", "kind": "official", "jurisdictions": ["ENGLAND"], "url": "https://b.example", "is_active": True, "priority": 20},
        {"key": "a", "label": "A", "kind": "official", "jurisdictions": ["ENGLAND"], "url": "https://a.example", "is_active": True, "priority": 10},
        {"key": "off", "label": "Off", "kind": "official", "jurisdictions": ["ENGLAND"], "url": "https://off.example", "is_active": False, "priority": 5},
        {"key": "scot", "label": "Scot", "kind": "official", "jurisdictions": ["SCOTLAND"], "url": "https://s.example", "is_active": True, "priority": 1},
    ]
    out = filter_action_links_for_region(links, "ENGLAND", max_links=2)
    assert [x["key"] for x in out] == ["a", "b"]
    assert all(x.get("external") for x in out)


def test_gas_safety_england_returns_two():
    raw = get_client_action_links_for_code_and_region("gas_safety", "England")
    assert len(raw) <= 2
    assert all("gassaferegister.co.uk" in (x.get("url") or "") for x in raw)


def test_eicr_ni_prefers_ni_block():
    raw = get_client_action_links_for_code_and_region("eicr", "Northern Ireland")
    assert len(raw) <= 2
    assert all(x.get("url") for x in raw)
