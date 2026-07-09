"""Phase 5 Compliance Intelligence Layer tests."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from services.compliance_graph_service.access import ActorContext
from services.compliance_intelligence.config import intelligence_enabled, intelligence_narration_enabled
from services.compliance_intelligence.hashing import envelope_hash
from services.compliance_intelligence.investigate import investigate
from services.compliance_intelligence.post_validator import validate_and_strip_narration

SAMPLE_ENVELOPE = {
    "service": "explain_decision",
    "insufficient_evidence": False,
    "authoritative_references": {"decision_id": "dec_p5_1", "snapshot_id": "snap_p5_1"},
    "payload": {
        "executive_summary": "Test summary",
        "decision": {"decision_id": "dec_p5_1", "decision_outcome": "VALID"},
    },
}


def test_envelope_hash_is_deterministic():
    h1 = envelope_hash(SAMPLE_ENVELOPE)
    h2 = envelope_hash(SAMPLE_ENVELOPE)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_post_validator_strips_uncited_paragraphs():
    narration = {
        "paragraphs": [
            {
                "text": "Valid claim.",
                "authoritative_references": {"decision_id": "dec_p5_1"},
            },
            {
                "text": "Fabricated claim.",
                "authoritative_references": {"decision_id": "dec_other"},
            },
        ],
        "insufficient_evidence": False,
        "graph_service_response_hash": "sha256:abc",
    }
    out = validate_and_strip_narration(narration, SAMPLE_ENVELOPE)
    assert len(out["paragraphs"]) == 1
    assert out["paragraphs"][0]["text"] == "Valid claim."


def test_post_validator_marks_insufficient_when_all_stripped():
    narration = {
        "paragraphs": [
            {"text": "Bad.", "authoritative_references": {"decision_id": "dec_other"}},
        ],
        "insufficient_evidence": False,
        "graph_service_response_hash": "sha256:abc",
    }
    out = validate_and_strip_narration(narration, SAMPLE_ENVELOPE)
    assert out["paragraphs"] == []
    assert out["insufficient_evidence"] is True


@pytest.mark.asyncio
async def test_investigate_disabled_when_graph_disabled(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "disabled")
    result = await investigate(
        method="explain_decision",
        params={"decision_id": "dec_p5_1"},
        actor=ActorContext(is_admin=True),
    )
    assert result["enabled"] is False
    assert result["insufficient_evidence"] is True


@pytest.mark.asyncio
async def test_investigate_tier1_only_when_insufficient(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "enabled")
    with patch(
        "services.compliance_intelligence.investigate.dispatch_graph_method",
        new_callable=AsyncMock,
        return_value={
            "service": "explain_decision",
            "insufficient_evidence": True,
            "payload": {"reason": "missing"},
        },
    ):
        result = await investigate(
            method="explain_decision",
            params={"decision_id": "dec_missing"},
            actor=ActorContext(is_admin=True),
            narrate=True,
        )
    assert result["tier1"]["insufficient_evidence"] is True
    assert result["tier2"]["insufficient_evidence"] is True
    assert result["tier2"]["paragraphs"] == []


@pytest.mark.asyncio
async def test_investigate_tier1_without_narration(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "enabled")
    monkeypatch.delenv("COMPLIANCE_INTELLIGENCE_NARRATION_ENABLED", raising=False)
    with patch(
        "services.compliance_intelligence.investigate.dispatch_graph_method",
        new_callable=AsyncMock,
        return_value=SAMPLE_ENVELOPE,
    ):
        result = await investigate(
            method="explain_decision",
            params={"decision_id": "dec_p5_1"},
            actor=ActorContext(is_admin=True),
            narrate=False,
        )
    assert result["graph_service_response_hash"].startswith("sha256:")
    assert result["tier1"] == SAMPLE_ENVELOPE
    assert result["tier2"] is None


@pytest.mark.asyncio
async def test_investigate_narration_stores_audit_record(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "enabled")
    monkeypatch.setenv("COMPLIANCE_INTELLIGENCE_NARRATION_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    llm_json = """{
      "paragraphs": [
        {
          "text": "The decision outcome was VALID.",
          "authoritative_references": {"decision_id": "dec_p5_1"},
          "confidence": 95
        },
        {
          "text": "Uncited speculation.",
          "authoritative_references": {"decision_id": "dec_fake"},
          "confidence": 50
        }
      ],
      "insufficient_evidence": false
    }"""

    with patch(
        "services.compliance_intelligence.investigate.dispatch_graph_method",
        new_callable=AsyncMock,
        return_value=SAMPLE_ENVELOPE,
    ), patch(
        "services.compliance_intelligence.investigate.intelligence_narration_enabled",
        return_value=True,
    ), patch(
        "utils.llm_chat.chat_openai",
        new_callable=AsyncMock,
        return_value=llm_json,
    ), patch(
        "utils.ai_config.AI_MODEL",
        "gpt-4o-mini",
    ), patch(
        "services.compliance_intelligence.investigate.store_narration",
        new_callable=AsyncMock,
        return_value="nar_test_1",
    ) as mock_store:
        result = await investigate(
            method="explain_decision",
            params={"decision_id": "dec_p5_1", "client_id": "client-1"},
            actor=ActorContext(is_admin=True, client_id="client-1"),
            client_id="client-1",
            narrate=True,
        )

    assert result["narration_id"] == "nar_test_1"
    assert len(result["tier2"]["paragraphs"]) == 1
    mock_store.assert_awaited_once()


def test_intelligence_flags(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "shadow")
    assert intelligence_enabled() is False

    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "enabled")
    assert intelligence_enabled() is True

    monkeypatch.setenv("AI_ENABLED", "false")
    assert intelligence_narration_enabled() is False
