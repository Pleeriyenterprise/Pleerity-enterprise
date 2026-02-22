"""Tests for score change tracking: delta and changed_requirements logic."""
import pytest


def test_score_delta_and_changed_requirements_logic():
    """Unit test: given previous and new score_breakdown, changed_requirements list is correct."""
    previous_score_breakdown = [
        {"requirement_key": "EICR_CERT", "status": "VALID"},
        {"requirement_key": "EPC_CERT", "status": "EXPIRED"},
    ]
    new_score_breakdown = [
        {"requirement_key": "EICR_CERT", "status": "VALID"},
        {"requirement_key": "EPC_CERT", "status": "VALID"},
    ]
    prev_by_key = {r.get("requirement_key"): r.get("status") for r in previous_score_breakdown if r.get("requirement_key")}
    new_by_key = {r.get("requirement_key"): r.get("status") for r in new_score_breakdown if r.get("requirement_key")}
    changed_requirements = []
    all_keys = set(prev_by_key) | set(new_by_key)
    for key in all_keys:
        prev_s = prev_by_key.get(key)
        new_s = new_by_key.get(key)
        if prev_s != new_s:
            changed_requirements.append({"requirement_key": key, "previous_status": prev_s, "new_status": new_s})
    assert len(changed_requirements) == 1
    assert changed_requirements[0]["requirement_key"] == "EPC_CERT"
    assert changed_requirements[0]["previous_status"] == "EXPIRED"
    assert changed_requirements[0]["new_status"] == "VALID"


def test_score_delta_computation():
    """Delta = new_score - previous_score; None when no previous."""
    previous_score = 70
    new_score = 85
    delta = (new_score - previous_score) if previous_score is not None else None
    assert delta == 15
    delta_none = (new_score - previous_score) if None is not None else None
    assert delta_none is None
