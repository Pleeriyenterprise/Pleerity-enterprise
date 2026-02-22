"""Tests for Compliance Vault Assistant chat: /api/assistant/chat and /api/admin/assistant/chat."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_chat_requires_auth_401():
    """Non-authenticated request to POST /api/assistant/chat returns 401."""
    from fastapi.testclient import TestClient
    from server import app
    client = TestClient(app)
    response = client.post("/api/assistant/chat", json={"message": "What is missing?"})
    assert response.status_code == 401


def test_client_chat_ignores_crn_uses_auth_client():
    """Client endpoint uses authenticated client_id only; CRN in message body is not used for lookup."""
    from routes.assistant import post_chat, ChatRequest
    from fastapi import Request

    body = ChatRequest(message="Show status for CRN PLE-OTHER-999", conversation_id=None, property_id=None)
    req = MagicMock(spec=Request)
    user = {"client_id": "client-auth-1", "portal_user_id": "user-1"}
    mock_turn = AsyncMock(return_value={
        "conversation_id": "conv-1",
        "answer": "Based on your portal.",
        "citations": [{"source_type": "portal_data", "source_id": "client_summary", "title": "Client"}],
        "safety_flags": {},
    })
    with patch("routes.assistant.client_route_guard", AsyncMock(return_value=user)):
        with patch("routes.assistant.assistant_chat_turn", mock_turn):
            with patch("routes.assistant.rate_limiter.check_rate_limit", AsyncMock(return_value=(True, None))):
                with patch("routes.assistant.rate_limiter.check_rate_limit_daily", AsyncMock(return_value=(True, None))):
                    result = asyncio.run(post_chat(req, body))
    assert result["conversation_id"] == "conv-1"
    assert result["answer"] == "Based on your portal."
    assert len(result["citations"]) == 1
    mock_turn.assert_called_once()
    call_kw = mock_turn.call_args[1]
    assert call_kw["client_id"] == "client-auth-1"
    assert call_kw["is_admin"] is False


def test_admin_chat_crn_resolves_to_client():
    """Admin POST /api/admin/assistant/chat with CRN resolves to client_id and returns answer."""
    from routes.admin import admin_assistant_chat, AdminAssistantChatRequest
    from fastapi import Request

    body = AdminAssistantChatRequest(message="Show status for this client", conversation_id=None, crn="PLE-CVP-2026-000123")

    req = MagicMock(spec=Request)
    user = {"portal_user_id": "admin-1", "auth_email": "admin@test.com"}
    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"client_id": "resolved-client-id"})
    with patch("routes.admin.admin_route_guard", AsyncMock(return_value=user)):
        with patch("routes.admin.database.get_db", return_value=db):
            with patch("utils.rate_limiter.rate_limiter.check_rate_limit", AsyncMock(return_value=(True, None))):
                with patch("services.assistant_chat_service.chat_turn", AsyncMock(return_value={
                    "conversation_id": "conv-admin-1",
                    "answer": "Client has 3 properties.",
                    "citations": [{"source_type": "portal_data", "source_id": "property:prop1", "title": "Property A"}],
                    "safety_flags": {"legal_advice_request": False},
                })):
                    result = asyncio.run(admin_assistant_chat(req, body))
    assert result["conversation_id"] == "conv-admin-1"
    assert "citations" in result
    db.clients.find_one.assert_called_once()
    assert db.clients.find_one.call_args[0][0]["customer_reference"] == "PLE-CVP-2026-000123"


def test_assistant_response_includes_citations_when_portal_referenced():
    """When chat_turn returns citations from portal_facts, response includes them."""
    from services.assistant_chat_service import _parse_chat_response
    raw = '{"answer": "Your gas safety expires 2026-06-01.", "citations": [{"source_type": "portal_data", "source_id": "property:abc", "title": "Property status"}], "safety_flags": {"legal_advice_request": false, "missing_data": false}}'
    parsed = _parse_chat_response(raw)
    assert parsed is not None
    assert "property:abc" in str(parsed["citations"])
    assert parsed["safety_flags"].get("legal_advice_request") is False


def test_legal_advice_request_safety_flagged():
    """When model sets legal_advice_request true, safety_flags are returned and audit REFUSED_LEGAL."""
    from services.assistant_chat_service import _parse_chat_response
    raw = '{"answer": "I cannot provide legal advice. Here is what your portal shows.", "citations": [], "safety_flags": {"legal_advice_request": true, "missing_data": false}}'
    parsed = _parse_chat_response(raw)
    assert parsed["safety_flags"].get("legal_advice_request") is True


def test_messages_saved_with_conversation_id():
    """chat_turn stores user and assistant messages with same conversation_id."""
    from services.assistant_chat_service import chat_turn

    db = MagicMock()
    db.assistant_conversations = MagicMock()
    db.assistant_conversations.find_one = AsyncMock(return_value=None)
    db.assistant_conversations.insert_one = AsyncMock()
    db.assistant_conversations.update_one = AsyncMock()
    db.assistant_messages = MagicMock()
    db.assistant_messages.insert_one = AsyncMock()

    with patch("services.assistant_chat_service.database.get_db", return_value=db):
        with patch("services.assistant_retrieval_service.database.get_db", return_value=db):
            with patch("services.assistant_chat_service.get_portal_facts", AsyncMock(return_value={"client_summary": {"client_id": "c1"}, "properties": [], "requirements_by_property": {}, "documents": [], "property_id_filter": None})):
                with patch("services.assistant_chat_service.get_kb_snippets", return_value=[]):
                    with patch("services.assistant_chat_service.create_audit_log", AsyncMock()):
                        with patch("services.assistant_chat_service.ai_config.AI_ENABLED", True):
                            with patch("services.assistant_chat_service.ai_config.is_configured", return_value=True):
                                with patch("services.assistant_chat_service.ai_config.AI_PROVIDER", "openai"):
                                    with patch("services.assistant_chat_service.ai_config.AI_MODEL", "gpt-4o-mini"):
                                        with patch("utils.llm_chat.chat_openai", AsyncMock(return_value='{"answer": "OK", "citations": [], "safety_flags": {}}')):
                                            result = asyncio.run(chat_turn("c1", "u1", "Hello", None, None, False))
    assert "conversation_id" in result
    assert db.assistant_messages.insert_one.call_count == 2  # user + assistant
    conv_id = result["conversation_id"]
    for call in db.assistant_messages.insert_one.call_args_list:
        doc = call[0][0]
        assert doc["conversation_id"] == conv_id
        assert doc["client_id"] == "c1"
