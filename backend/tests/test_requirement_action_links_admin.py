from services.requirement_action_links_admin_service import validate_action_links_override


def test_validate_unique_keys_and_max_two_per_region():
    links = [
        {"key": "a", "label": "A", "url": "https://a.example", "jurisdictions": ["ENGLAND"], "is_active": True, "priority": 1},
        {"key": "b", "label": "B", "url": "https://b.example", "jurisdictions": ["ENGLAND"], "is_active": True, "priority": 2},
        {"key": "c", "label": "C", "url": "https://c.example", "jurisdictions": ["ENGLAND"], "is_active": True, "priority": 3},
    ]
    err = validate_action_links_override(links)
    assert any("At most 2 active" in e for e in err)


def test_validate_duplicate_url_overlap():
    links = [
        {"key": "a", "label": "A", "url": "https://same.example/x", "jurisdictions": ["ENGLAND"], "is_active": True, "priority": 1},
        {"key": "b", "label": "B", "url": "https://same.example/x", "jurisdictions": ["ENGLAND"], "is_active": True, "priority": 2},
    ]
    err = validate_action_links_override(links)
    assert any("Duplicate active URL" in e for e in err)


def test_validate_ok_two_england():
    links = [
        {"key": "a", "label": "A", "url": "https://a.example", "jurisdictions": ["ENGLAND"], "is_active": True, "priority": 1},
        {"key": "b", "label": "B", "url": "https://b.example", "jurisdictions": ["ENGLAND"], "is_active": True, "priority": 2},
    ]
    assert validate_action_links_override(links) == []
