"""Admin manual job scope validation (P0/P1)."""
from unittest.mock import AsyncMock, patch

import pytest

from services.job_scope_registry import (
    get_job_run_scope,
    validate_manual_job_scope,
    validate_property_ids_belong_to_client,
)


def test_monthly_digest_accepts_client_id_only():
    s = get_job_run_scope("monthly_digest")
    assert s.accepts_client_id is True
    assert s.accepts_property_id is False
    assert s.accepts_property_ids_filter is True


def test_daily_reminders_accepts_client_id():
    s = get_job_run_scope("daily_reminders")
    assert s.accepts_client_id is True
    assert s.accepts_property_id is False


def test_compliance_recalc_enqueue_accepts_property_only():
    s = get_job_run_scope("compliance_recalc_enqueue_property")
    assert s.accepts_property_id is True
    assert s.manual_requires_property_id is True


def test_validate_rejects_client_id_for_global_job():
    err = validate_manual_job_scope("pending_verification_digest", client_id="c1", property_id=None)
    assert err is not None
    assert validate_manual_job_scope("pending_verification_digest", client_id=None, property_id=None) is None


def test_validate_rejects_property_id_for_monthly_digest():
    err = validate_manual_job_scope("monthly_digest", client_id="c1", property_id="p1")
    assert err is not None
    assert "property_id" in err


def test_validate_property_ids_requires_client():
    err = validate_manual_job_scope("monthly_digest", client_id=None, property_ids=["p1"])
    assert err is not None


def test_validate_monthly_digest_with_property_ids_ok():
    assert validate_manual_job_scope("monthly_digest", client_id="c1", property_ids=["p1", "p2"]) is None


@pytest.mark.asyncio
async def test_validate_property_ids_belong_to_client_rejects_orphan():
    mock_db = AsyncMock()

    def fake_find(q, proj):
        class Cursor:
            async def to_list(self, n):
                return [{"property_id": "p1"}]

        return Cursor()

    mock_db.properties.find = fake_find
    with patch("database.database.get_db", return_value=mock_db):
        err = await validate_property_ids_belong_to_client("c1", ["p1", "p_other"])
    assert err is not None
    assert "p_other" in err


@pytest.mark.asyncio
async def test_validate_property_ids_belong_to_client_ok():
    mock_db = AsyncMock()

    def fake_find(q, proj):
        class Cursor:
            async def to_list(self, n):
                return [{"property_id": "p1"}, {"property_id": "p2"}]

        return Cursor()

    mock_db.properties.find = fake_find
    with patch("database.database.get_db", return_value=mock_db):
        err = await validate_property_ids_belong_to_client("c1", ["p1", "p2"])
    assert err is None


def test_validate_rejects_property_ids_for_daily():
    err = validate_manual_job_scope("daily_reminders", client_id="c1", property_ids=["p1"])
    assert err is not None


def test_validate_monthly_digest_client_only_ok():
    assert validate_manual_job_scope("monthly_digest", client_id="c1", property_id=None) is None
    assert validate_manual_job_scope("monthly_digest", client_id=None, property_id=None) is None
