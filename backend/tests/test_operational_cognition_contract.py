"""Tests for operational_cognition_contract dispatcher."""
from services.operational_cognition_contract import (
    attach_operational_cognition,
    cognition_contract_version,
    assert_read_only_envelope,
)
from services.operational_cognition_service import COGNITION_VERSION


def test_cognition_contract_version():
    assert cognition_contract_version() == COGNITION_VERSION


def test_attach_requirement_envelope():
    req = {
        "requirement_id": "r1",
        "property_id": "p1",
        "status": "ACTION_REQUIRED",
        "take_action": {"primary": {"label": "Upload evidence", "route": "/documents"}},
    }
    out = attach_operational_cognition("requirement", req)
    env = out.get("operational_cognition")
    assert env is not None
    assert env.get("cognition_version") == COGNITION_VERSION
    assert_read_only_envelope(env)


def test_unknown_entity_passthrough():
    payload = {"id": "x"}
    assert attach_operational_cognition("unknown", payload) == payload
