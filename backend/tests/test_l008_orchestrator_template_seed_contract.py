"""L-008e: orchestrator ``template_key`` literals and lifecycle registry ⊆ canonical notification seed."""

from __future__ import annotations

from notification_orchestrator_send_template_key_audit import (
    PRODUCTION_ORCHESTRATOR_SEND_TEMPLATE_KEY_LITERALS,
)
from notification_template_seed_definitions import all_notification_template_keys_from_seed
from services.email_event_registry import EMAIL_EVENTS, LANDLORD_ONBOARDING_EVENT_IDS, get_template_key_for_event


def test_production_orchestrator_send_literals_are_seeded():
    seed_keys = all_notification_template_keys_from_seed()
    missing = sorted(PRODUCTION_ORCHESTRATOR_SEND_TEMPLATE_KEY_LITERALS - seed_keys)
    assert not missing, (
        "notification_orchestrator.send template_key literals not in seed definitions: "
        + ", ".join(missing)
    )


def test_email_event_registry_template_keys_are_seeded():
    seed_keys = all_notification_template_keys_from_seed()
    missing: list[str] = []
    for event_id, meta in EMAIL_EVENTS.items():
        tk = meta.get("template_key")
        if isinstance(tk, str) and tk not in seed_keys:
            missing.append(f"{event_id} -> {tk}")
    assert not missing, "EMAIL_EVENTS template_key not in seed: " + "; ".join(missing)


def test_landlord_onboarding_sequence_maps_to_seeded_template_keys():
    seed_keys = all_notification_template_keys_from_seed()
    for event_id in LANDLORD_ONBOARDING_EVENT_IDS:
        tk = get_template_key_for_event(event_id)
        assert tk, f"missing template for {event_id}"
        assert tk in seed_keys, f"{event_id} -> {tk} not in seed"
