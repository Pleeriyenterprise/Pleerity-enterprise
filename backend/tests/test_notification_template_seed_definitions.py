"""Canonical notification seed ↔ admin runtime metadata registry (drift guard)."""

from notification_template_seed_definitions import (
    CORE_NOTIFICATION_TEMPLATE_SEED_DEFINITIONS,
    ADMIN_CLIENT_COMMUNICATION_NOTIFICATION_SEED_DEFINITIONS,
    email_template_keys_by_alias_from_notification_seed,
    iter_notification_email_template_key_alias_pairs,
    notification_template_seed_rows_with_timestamps,
)
from services.email_template_runtime_metadata import (
    TEMPLATE_KEYS_BY_ALIAS,
    get_email_alias_runtime_metadata,
)


def test_core_seed_template_keys_unique():
    keys = [r["template_key"] for r in CORE_NOTIFICATION_TEMPLATE_SEED_DEFINITIONS]
    assert len(keys) == len(set(keys)), f"duplicate template_key in core seed: {keys}"


def test_admin_client_seed_template_keys_unique():
    keys = [r["template_key"] for r in ADMIN_CLIENT_COMMUNICATION_NOTIFICATION_SEED_DEFINITIONS]
    assert len(keys) == len(set(keys))


def test_email_pairs_cover_all_email_rows_with_alias():
    """Every EMAIL row with an alias appears in iter_notification_email_template_key_alias_pairs."""
    pairs_set = set(iter_notification_email_template_key_alias_pairs())
    for row in CORE_NOTIFICATION_TEMPLATE_SEED_DEFINITIONS + ADMIN_CLIENT_COMMUNICATION_NOTIFICATION_SEED_DEFINITIONS:
        if row.get("channel") == "EMAIL" and row.get("email_template_alias"):
            assert (row["template_key"], row["email_template_alias"]) in pairs_set


def test_runtime_metadata_template_keys_match_canonical_seed_inversion():
    """Fails if email_template_runtime_metadata drifts from notification_template_seed_definitions."""
    assert TEMPLATE_KEYS_BY_ALIAS == email_template_keys_by_alias_from_notification_seed()


def test_seed_rows_with_timestamps_include_updated_at():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    rows = notification_template_seed_rows_with_timestamps(now)
    assert rows
    assert all(r.get("updated_at") is now for r in rows)


def test_payment_received_high_risk_empty_template_keys_from_seed():
    """Enum alias not in notification seed: keep explicit high-risk metadata; template_keys stay empty."""
    m = get_email_alias_runtime_metadata("payment-received")
    assert m["legal_or_financial_flow"] is True
    assert m["edit_risk_level"] == "high"
    assert m["admin_editable"] is True
    assert m["template_keys"] == []
