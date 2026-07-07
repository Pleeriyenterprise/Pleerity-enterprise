"""P0 rent payment idempotency — service replay + index contract."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database import _IDEM_COMPOUND_PARTIAL


@pytest.mark.asyncio
async def test_record_payment_idempotent_replay_returns_prior():
    from services import rent_payment_service

    client_id = "c_idem_pay"
    idem = f"idem_pay_{uuid.uuid4().hex[:8]}"
    prior = {
        "payment_id": "rp_prior",
        "client_id": client_id,
        "idempotency_key": idem,
        "ledger_id": "rlp_1",
        "amount_minor": 50000,
    }
    mock_db = MagicMock()
    mock_db.rent_payments = MagicMock()
    mock_db.rent_payments.find_one = AsyncMock(return_value=prior)

    with patch("services.rent_payment_service.database.get_db", return_value=mock_db):
        out = await rent_payment_service.record_payment(
            client_id,
            {
                "amount_minor": 50000,
                "payment_date": "2026-06-04",
                "ledger_id": "rlp_1",
                "idempotency_key": idem,
            },
        )

    assert out.get("idempotent_replay") is True
    assert out["payments"][0]["payment_id"] == "rp_prior"
    mock_db.rent_payments.insert_one.assert_not_called()


def test_rent_payments_idempotency_index_partial_filter():
    """Compound idempotency index must only apply when idempotency_key is a string."""
    assert _IDEM_COMPOUND_PARTIAL == {"idempotency_key": {"$type": "string"}}


@pytest.mark.asyncio
async def test_ensure_compound_idempotency_index_creates_unique_partial_index():
    from database import database

    coll = MagicMock()
    coll.create_index = AsyncMock()
    coll.drop_index = AsyncMock()

    await database._ensure_compound_idempotency_index(coll, label="rent_payments_test")

    coll.create_index.assert_awaited_once()
    kwargs = coll.create_index.await_args.kwargs
    assert kwargs["unique"] is True
    assert kwargs["name"] == "client_id_1_idempotency_key_1"
    assert kwargs["partialFilterExpression"] == _IDEM_COMPOUND_PARTIAL
