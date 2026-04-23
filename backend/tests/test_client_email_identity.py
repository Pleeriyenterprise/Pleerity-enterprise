"""Unit tests for canonical client email and duplicate-key classification."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from utils.client_email import (
    canonical_client_email,
    client_email_taken,
    classify_clients_duplicate_key_error,
)


def test_canonical_client_email_trims_and_lowercases():
    assert canonical_client_email("  User@Example.COM \t") == "user@example.com"
    assert canonical_client_email(None) == ""


@pytest.mark.asyncio
async def test_client_email_taken_hits_exact_canonical_index_path():
    db = MagicMock()

    async def find_one(filt, proj=None):
        if filt == {"email": "user@example.com"}:
            return {"_id": "x"}
        raise AssertionError("unexpected filter")

    db.clients.find_one = AsyncMock(side_effect=find_one)
    assert await client_email_taken(db, "User@Example.COM") is True


@pytest.mark.asyncio
async def test_client_email_taken_falls_back_to_expr_for_legacy_casing():
    db = MagicMock()
    calls = []

    async def find_one(filt, proj=None):
        calls.append(filt)
        if isinstance(filt, dict) and filt.get("email") == "user@example.com":
            return None
        if isinstance(filt, dict) and "$expr" in filt:
            return {"_id": "legacy"}
        return None

    db.clients.find_one = AsyncMock(side_effect=find_one)
    assert await client_email_taken(db, "user@example.com") is True
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_client_email_taken_false_when_no_match():
    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value=None)
    assert await client_email_taken(db, "new@example.com") is False
    assert db.clients.find_one.call_count == 2


def test_classify_duplicate_key_email_from_keypattern():
    class _Err(Exception):
        pass

    e = _Err("dup")
    e.details = {"code": 11000, "keyPattern": {"email": 1}, "errmsg": "E11000 duplicate key"}
    assert classify_clients_duplicate_key_error(e) == "email"


def test_classify_duplicate_key_email_from_errmsg_only():
    class _Err(Exception):
        pass

    e = _Err("x")
    e.details = {
        "code": 11000,
        "errmsg": 'E11000 duplicate key error collection: test.clients index: email_1 dup key: { email: "a@b.com" }',
    }
    assert classify_clients_duplicate_key_error(e) == "email"


def test_classify_duplicate_key_customer_reference():
    class _Err(Exception):
        pass

    e = _Err("x")
    e.details = {"code": 11000, "keyPattern": {"customer_reference": 1}}
    assert classify_clients_duplicate_key_error(e) == "customer_reference"
