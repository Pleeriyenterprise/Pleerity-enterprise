from services.published_registry_client_truth_migration_service import (
    LEGACY_STATE_HIDDEN_DEPRECATED,
    LEGACY_STATE_UNMAPPED_READONLY,
    _has_links,
    _state_payload,
)


def test_has_links_detects_any_linkage():
    assert _has_links({"documents": 0, "work_orders": 0, "reminders": 0, "invoices": 0}) is False
    assert _has_links({"documents": 1, "work_orders": 0, "reminders": 0, "invoices": 0}) is True


def test_state_payload_for_unmapped_readonly_sets_review_flags():
    out = _state_payload(
        legacy_state=LEGACY_STATE_UNMAPPED_READONLY,
        canonical_code="gas_safety",
        mapped_code=None,
        counts={"documents": 1, "work_orders": 0, "reminders": 0, "invoices": 0},
        source="legacy_readonly",
    )
    assert out["legacy_readonly_visible"] is True
    assert out["legacy_review_required"] is True
    assert out["legacy_canonical_requirement_code"] == "gas_safety"


def test_state_payload_for_hidden_deprecated_hides_from_readonly():
    out = _state_payload(
        legacy_state=LEGACY_STATE_HIDDEN_DEPRECATED,
        canonical_code=None,
        mapped_code=None,
        counts={"documents": 0, "work_orders": 0, "reminders": 0, "invoices": 0},
        source="baseline",
    )
    assert out["legacy_readonly_visible"] is False
    assert out["legacy_review_required"] is False

