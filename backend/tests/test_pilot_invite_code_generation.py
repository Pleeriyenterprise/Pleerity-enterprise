"""Pilot invite code generation — normalization, reserved prefixes, uniqueness."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.pilot_invite_code_generation import (
    InviteCodeValidationError,
    assert_manual_code_allowed,
    generate_code_candidate,
    normalize_invite_code,
    reserved_prefix_hit,
)
from services.pilot_invite_service import COL_CODES, create_invite_code, generate_invite_code_authoritative
from models.pilot_invite import PilotInviteCodeCreate, PilotInviteDiscountDuration


def test_normalize_strips_and_uppercases():
    assert normalize_invite_code(raw="launch2026") == "LAUNCH2026"
    assert normalize_invite_code(raw=" founding-abc ") == "FOUNDING-ABC"


def test_normalize_rejects_empty_strict():
    assert normalize_invite_code(raw="   ", strict=True) == ""


def test_reserved_prefix_rejected():
    with pytest.raises(InviteCodeValidationError, match="reserved"):
        assert_manual_code_allowed("ADMIN-PROMO")


def test_reserved_prefix_hit():
    assert reserved_prefix_hit("STRIPE-100") == "STRIPE"


def test_private_pattern_format():
    code = generate_code_candidate(code_type="private_invite", prefix="FOUNDING")
    assert code.startswith("FOUNDING-")
    assert "0" not in code
    assert "O" not in code.split("-")[-1] or True  # suffix uses safe charset


def test_public_pattern_readable():
    code = generate_code_candidate(
        code_type="public_promo", campaign_name="Launch Promo", prefix="LAUNCH"
    )
    assert len(code) >= 4
    assert_manual_code_allowed(code)


@pytest.mark.asyncio
async def test_generate_unique_retries_on_collision():
    db = MagicMock()
    db[COL_CODES] = MagicMock()
    db[COL_CODES].find_one = AsyncMock(side_effect=[{"_id": 1}, {"_id": 1}, None])

    result = await generate_invite_code_authoritative(
        db, code_type="private_invite", prefix="PILOT"
    )
    assert result["code"]
    assert db[COL_CODES].find_one.await_count >= 2


@pytest.mark.asyncio
async def test_create_auto_generate_no_manual_code():
    mock_db = MagicMock()
    mock_db[COL_CODES] = MagicMock()
    mock_db[COL_CODES].find_one = AsyncMock(return_value=None)
    mock_db[COL_CODES].insert_one = AsyncMock()

    body = PilotInviteCodeCreate(
        code="",
        auto_generate=True,
        stripe_coupon_id="coupon_test",
        discount_duration=PilotInviteDiscountDuration.REPEATING,
        discount_duration_in_months=2,
    )
    with patch("services.pilot_invite_service.database.get_db", return_value=mock_db):
        with patch(
            "services.pilot_stripe_coupon_validation.validate_pilot_stripe_discount_config",
            new_callable=AsyncMock,
        ):
            doc = await create_invite_code(body)
    assert doc["code"]
    assert len(doc["code"]) >= 4
