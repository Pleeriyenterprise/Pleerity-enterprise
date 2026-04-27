"""Legacy requirement_rules admin gate and read-only conflict summary."""
import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock

from models import UserRole
from services.legacy_requirement_rules_gate import (
    MAINTENANCE_ENV_VAR,
    MAINTENANCE_HEADER,
    assert_legacy_rule_mutations_allowed,
    build_requirement_rules_conflict_summary,
    legacy_maintenance_enabled_in_environment,
)


class _FakeCursor:
    def __init__(self, data):
        self._data = data

    def sort(self, *a, **k):
        return self

    def skip(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    async def to_list(self, _n):
        return self._data


class _FakeRules:
    def __init__(self, governed: list, ungov: list):
        self._governed = governed
        self._ungov = ungov

    def find(self, query, projection=None):
        if query.get("governed") is True:
            return _FakeCursor(self._governed)
        return _FakeCursor(self._ungov)


class _FakeDb:
    def __init__(self, governed, ungov):
        self.requirement_rules = _FakeRules(governed, ungov)


@pytest.mark.asyncio
async def test_conflict_summary_overlap_and_supplemental():
    db = _FakeDb(
        [{"rule_type": "gas_safety", "rule_id": "g1", "name": "G"}],
        [
            {
                "rule_type": "gas_safety",
                "rule_id": "u1",
                "name": "Legacy",
                "is_active": True,
                "governed": False,
            },
            {
                "rule_type": "custom_extra",
                "rule_id": "u2",
                "name": "Extra",
                "is_active": True,
            },
        ],
    )
    out = await build_requirement_rules_conflict_summary(db)
    assert out["governed_published_count"] == 1
    assert out["ungoverned_row_count"] == 2
    assert out["overlap_count"] == 1
    assert out["ungoverned_active_supplemental_count"] == 1
    assert "custom_extra" in (out["distinct_active_ungoverned_rule_types"] or [])


def test_assert_legacy_blocks_when_env_disabled(monkeypatch):
    monkeypatch.delenv(MAINTENANCE_ENV_VAR, raising=False)
    req = MagicMock()
    req.headers.get.return_value = "1"
    user = {"role": UserRole.ROLE_OWNER.value}
    with pytest.raises(HTTPException) as ei:
        assert_legacy_rule_mutations_allowed(req, user)
    assert ei.value.status_code == 403


def test_assert_legacy_blocks_non_owner_even_with_env(monkeypatch):
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "1")
    req = MagicMock()
    req.headers.get.return_value = "1"
    user = {"role": UserRole.ROLE_ADMIN.value}
    with pytest.raises(HTTPException) as ei:
        assert_legacy_rule_mutations_allowed(req, user)
    assert ei.value.status_code == 403


def test_assert_legacy_blocks_missing_header(monkeypatch):
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "1")
    req = MagicMock()
    req.headers.get.return_value = ""
    user = {"role": UserRole.ROLE_OWNER.value}
    with pytest.raises(HTTPException) as ei:
        assert_legacy_rule_mutations_allowed(req, user)
    assert ei.value.status_code == 403


def test_assert_legacy_allows_owner_with_env_and_header(monkeypatch):
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "1")
    req = MagicMock()
    req.headers.get = lambda k, d=None: "1" if k == MAINTENANCE_HEADER else d
    user = {"role": UserRole.ROLE_OWNER.value}
    assert_legacy_rule_mutations_allowed(req, user)


def test_maintenance_env_flag(monkeypatch):
    monkeypatch.delenv(MAINTENANCE_ENV_VAR, raising=False)
    assert legacy_maintenance_enabled_in_environment() is False
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "true")
    assert legacy_maintenance_enabled_in_environment() is True
