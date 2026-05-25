"""Rent attention projection into Today / Command Centre."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.rent_attention_projection import (
    append_rent_to_command_center_urgent,
    list_rent_attention_tasks,
    merge_rent_into_today_payload,
)


@pytest.mark.asyncio
async def test_list_rent_attention_tasks_when_flag_on():
    mock_db = MagicMock()
    periods = MagicMock()
    periods.find = MagicMock(
        return_value=MagicMock(
            sort=MagicMock(
                return_value=MagicMock(
                    limit=MagicMock(
                        return_value=MagicMock(
                            to_list=AsyncMock(
                                return_value=[
                                    {
                                        "ledger_id": "rlp_1",
                                        "property_id": "p1",
                                        "tenancy_id": "pty_1",
                                        "tenant_name": "A",
                                        "period_key": "2026-05",
                                        "due_date": "2026-05-01",
                                        "outstanding_balance_minor": 50000,
                                        "status": "OVERDUE",
                                        "is_overdue": True,
                                    }
                                ]
                            )
                        )
                    )
                )
            )
        )
    )
    mock_db.rent_ledger_periods = periods
    with patch(
        "services.rent_attention_projection.get_effective_flags",
        new_callable=AsyncMock,
        return_value={"RENT_OPERATIONS": True},
    ), patch("services.rent_attention_projection.database.get_db", return_value=mock_db):
        tasks = await list_rent_attention_tasks("c1")
    assert len(tasks) == 1
    assert tasks[0]["id"] == "rent_ledger_rlp_1"


def test_merge_rent_into_today_payload_dedupes():
    payload = {"tasks": {"urgent": []}, "items": []}
    rent_tasks = [{"id": "rent_ledger_x", "title": "Rent overdue", "business_actions": []}]
    out = merge_rent_into_today_payload(payload, rent_tasks)
    assert out["rent_attention_count"] == 1
    assert any(i["id"] == "rent_ledger_x" for i in out["items"])


def test_append_rent_command_center_dedupes():
    urgent = [{"id": "other"}]
    rent = [{"id": "rent_ledger_x", "title": "Rent", "primary_action_url": "/operations/rent"}]
    out = append_rent_to_command_center_urgent(urgent, rent)
    assert len(out) == 2
