"""Governance: static bounded DOCUMENT_UPLOAD observability registry (gas_safety / eicr / epc only)."""

import pytest

from routes import documents as documents_routes


def test_bounded_registry_keys_and_order_are_static_three_slices_only():
    assert set(documents_routes._BOUND_DOCUMENT_UPLOAD_ACTIVATION_SLICES.keys()) == {
        "gas_safety",
        "eicr",
        "epc",
    }
    assert documents_routes._BOUND_DOCUMENT_UPLOAD_ACTIVATION_SLICE_ORDER == (
        "gas_safety",
        "eicr",
        "epc",
    )
    for key, meta in documents_routes._BOUND_DOCUMENT_UPLOAD_ACTIVATION_SLICES.items():
        codes = meta.get("canonical_codes")
        assert isinstance(codes, frozenset)
        assert len(codes) == 1
        assert next(iter(codes)) == key


def test_downstream_observation_allowlist_unchanged():
    expected = frozenset(
        {
            "compliance_gap_sync.sync_compliance_gaps_for_requirement",
            "requirement_state_transition.core_backbone.authority_sync",
            "compliance_recalc_queue.enqueue_compliance_recalc",
            "risk_signal_regen_queue.enqueue_risk_signal_regen",
        }
    )
    assert documents_routes._DOCUMENT_UPLOAD_BOUND_SLICE_ACTIVATION_DOWNSTREAM_ALLOWLIST == expected


@pytest.mark.parametrize(
    "req_code,req_type",
    [
        ("pat", "portable_appliance_test"),
        ("legionella", "legionella"),
        ("deposit_pi", "deposit_pi"),
        ("rent_smart_wales", "rent_smart_wales"),
    ],
)
def test_pat_legionella_and_other_obligations_resolve_no_bounded_slice(req_code, req_type):
    req = {"requirement_id": "r1", "requirement_code": req_code, "requirement_type": req_type}
    assert documents_routes._resolve_bound_document_upload_activation_obligation_slice(req) is None


def test_slice_precedence_matches_legacy_gas_before_eicr_on_mismatched_fields():
    """If type normalizes to gas_safety but code to eicr, gas slice wins (legacy if/elif order)."""
    req = {
        "requirement_id": "r1",
        "requirement_code": "eicr",
        "requirement_type": "gas_safety",
    }
    assert documents_routes._resolve_bound_document_upload_activation_obligation_slice(req) == "gas_safety"


def test_only_three_canonical_codes_produce_non_none_resolution():
    from routes.documents import _resolve_bound_document_upload_activation_obligation_slice

    assert _resolve_bound_document_upload_activation_obligation_slice(None) is None
    assert _resolve_bound_document_upload_activation_obligation_slice({}) is None
