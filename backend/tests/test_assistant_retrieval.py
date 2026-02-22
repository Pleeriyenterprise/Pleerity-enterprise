"""Tests for assistant KB loader, ranking, and citations in chat response."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_kb_loader_returns_snippets():
    """load_kb_snippets returns a list of Snippet with source_id, title, content, score."""
    from services.assistant_retrieval_service import load_kb_snippets

    result = load_kb_snippets("upload document")
    assert isinstance(result, list)
    for s in result:
        assert "source_id" in s
        assert "title" in s
        assert "content" in s
        assert "score" in s
        assert s["source_id"].startswith("assistant_kb/")
        assert s["source_id"].endswith(".md")


def test_kb_ranking_returns_relevant_snippets_for_upload_query():
    """For a query about uploading, top snippets should include how_to_upload (keyword overlap)."""
    from services.assistant_retrieval_service import load_kb_snippets

    snippets = load_kb_snippets("how do I upload a document")
    assert len(snippets) <= 3
    source_ids = [s["source_id"] for s in snippets]
    # "upload" and "document" appear in how_to_upload.md
    upload_snippet = next((s for s in snippets if "how_to_upload" in s["source_id"]), None)
    assert upload_snippet is not None, "how_to_upload.md should be in top 3 for upload-related query"
    assert upload_snippet["score"] >= 0


def test_kb_citations_included_in_response_payload():
    """When kb snippets are passed and model returns answer, response citations include KB entries."""
    from services.assistant_chat_service import chat_turn

    db = MagicMock()
    db.assistant_conversations = MagicMock()
    db.assistant_conversations.find_one = AsyncMock(return_value=None)
    db.assistant_conversations.insert_one = AsyncMock()
    db.assistant_conversations.update_one = AsyncMock()
    db.assistant_messages = MagicMock()
    db.assistant_messages.insert_one = AsyncMock()

    kb_snippets_with_content = [
        {"source_id": "assistant_kb/how_to_upload.md", "title": "How to upload documents", "content": "Upload from Documents page."},
    ]
    # Model returns answer but omits KB citation; our code should still add it
    model_response = '{"answer": "You can upload from the Documents page.", "citations": [], "safety_flags": {"legal_advice_request": false, "missing_data": false}}'

    with patch("services.assistant_chat_service.database.get_db", return_value=db):
        with patch("services.assistant_retrieval_service.database.get_db", return_value=db):
            with patch("services.assistant_chat_service.get_portal_facts", AsyncMock(return_value={"client_summary": {"client_id": "c1"}, "properties": [], "requirements_by_property": {}, "documents": [], "property_id_filter": None})):
                with patch("services.assistant_chat_service.get_kb_snippets", return_value=kb_snippets_with_content):
                    with patch("services.assistant_chat_service.create_audit_log", AsyncMock()):
                        with patch("services.assistant_chat_service.ai_config.AI_ENABLED", True):
                            with patch("services.assistant_chat_service.ai_config.is_configured", return_value=True):
                                with patch("services.assistant_chat_service.ai_config.AI_PROVIDER", "openai"):
                                    with patch("services.assistant_chat_service.ai_config.AI_MODEL", "gpt-4o-mini"):
                                        with patch("utils.llm_chat.chat_openai", AsyncMock(return_value=model_response)):
                                            result = asyncio.run(chat_turn("c1", "u1", "How do I upload?", None, None, False))
    assert "citations" in result
    assert len(result["citations"]) >= 1
    kb_citations = [c for c in result["citations"] if c.get("source_type") == "kb"]
    assert len(kb_citations) >= 1, "Response should include at least one KB citation when kb snippets were passed"
    assert any(c.get("source_id") == "assistant_kb/how_to_upload.md" for c in kb_citations)
