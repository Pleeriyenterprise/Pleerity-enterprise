"""
Regression: Motor/MongoDB can return {} when a document exists but every projected field is missing.
`if not client` wrongly treats {} as falsy and reported 'Client not found' on mark done.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.onboarding_checklist_service import mark_item_complete, ITEM_ADD_PROPERTIES


@pytest.mark.asyncio
async def test_mark_item_complete_empty_projection_not_client_not_found():
    db = MagicMock()
    db.properties = MagicMock()
    db.properties.count_documents = AsyncMock(return_value=1)
    db.clients.find_one = AsyncMock(return_value={})
    db.clients.update_one = AsyncMock()

    with patch("services.onboarding_checklist_service.database.get_db", return_value=db):
        result = await mark_item_complete("client-1", ITEM_ADD_PROPERTIES)

    assert result.get("ok") is True
    db.clients.update_one.assert_called_once()
