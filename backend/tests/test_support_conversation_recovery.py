"""Frustration recovery and registry-backed plan comparisons."""
import pytest

from services.support_conversation_recovery import (
    build_registry_plan_comparison_reply,
    detect_plan_comparison_pair,
    is_frustration_or_correction_message,
    try_frustration_recovery_turn,
)


def test_detect_plan_pairs():
    assert detect_plan_comparison_pair("Professional vs Portfolio plans?") == ("professional", "portfolio")
    assert detect_plan_comparison_pair("difference between Solo and Portfolio") == ("solo", "portfolio")


def test_frustration_detection():
    assert is_frustration_or_correction_message("You are not answering my question. Are you confused?")
    assert not is_frustration_or_correction_message("What is the difference between Solo and Portfolio?")


def test_registry_comparison_has_prices():
    text = build_registry_plan_comparison_reply(("professional", "portfolio"))
    assert text
    assert "£79" in text
    assert "£39" in text
    assert "25" in text
    assert "10" in text


@pytest.mark.asyncio
async def test_frustration_recovery_plan_compare():
    ctx = {
        "recent_entities": [
            "What is the difference between Professional and Portfolio?",
            "You are not answering my question. Are you confused?",
        ]
    }
    out = try_frustration_recovery_turn(
        "You are not answering my question. Are you confused?",
        ctx,
        [
            {"role": "user", "content": "What is the difference between Professional and Portfolio?"},
            {"role": "assistant", "content": "Here is all pricing..."},
        ],
    )
    assert out is not None
    assert out["metadata"]["recovery_kind"] == "plan_comparison"
    assert "Professional" in out["response"]
    assert "Portfolio" in out["response"]
    assert out["metadata"].get("frustration_detected") is True
