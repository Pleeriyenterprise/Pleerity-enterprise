"""Admin confirmation token and governed action enforcement."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from services import admin_action_governance as gov
from services.admin_confirmation_token_service import (
    consume_admin_confirmation_token,
    issue_admin_confirmation_token,
)


@pytest.mark.asyncio
async def test_confirmation_token_single_use():
    stored = {}

    async def insert_one(doc):
        stored.clear()
        stored.update(doc)

    async def find_one(q):
        if q.get("token_hash") == stored.get("token_hash"):
            return dict(stored)
        return None

    async def update_one(q, upd):
        stored.update(upd.get("$set", {}))

    collection = AsyncMock()
    collection.insert_one = insert_one
    collection.find_one = find_one
    collection.update_one = update_one
    collection.delete_one = AsyncMock()

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=collection)

    with patch("database.database.get_db", return_value=mock_db):
        token = await issue_admin_confirmation_token("admin1", "resolve_unresolved_scope", reason="test reason")
        await consume_admin_confirmation_token(token, "admin1", "resolve_unresolved_scope")
        with pytest.raises(HTTPException) as exc:
            await consume_admin_confirmation_token(token, "admin1", "resolve_unresolved_scope")
        assert exc.value.status_code == 403


def test_ensure_action_reason_requires_min_length():
    with pytest.raises(HTTPException):
        gov.ensure_action_reason("resolve_unresolved_scope", "short")


@pytest.mark.asyncio
async def test_enforce_governed_requires_confirmation_header():
    request = AsyncMock()
    request.headers = {}
    user = {"portal_user_id": "admin1"}
    with pytest.raises(HTTPException) as exc:
        await gov.enforce_governed_admin_action(
            request,
            user,
            "resolve_unresolved_scope",
            reason="Valid support reason here",
            resource_key="doc1",
        )
    assert exc.value.status_code == 403
