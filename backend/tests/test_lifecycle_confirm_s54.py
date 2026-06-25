"""Phase 2 S5.4 — preview-only active enforcement tests."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from scripts.deployment_governance_ci_gate import check_production_blueprints_lifecycle_active
from services.lifecycle_aware_confirm_config import (
    get_effective_confirm_mode,
    is_lifecycle_aware_confirm_active,
    validate_lifecycle_confirm_boot,
)
from services.lifecycle_confirm_apply import (
    build_legacy_apply_extraction_update,
    resolve_confirm_persistence_update,
    strip_forbidden_contract_fields,
)
from services.lifecycle_confirm_contract import build_contract_for_requirement
from services.lifecycle_confirm_validation import (
    enforce_lifecycle_confirm_or_raise,
    validate_confirm_payload_against_contract,
)


def _req(code: str) -> dict:
    return {"requirement_id": "req-s54", "requirement_code": code}


def _parse_date(value) -> datetime:
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _active_preview_env(monkeypatch) -> None:
    monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "active")
    monkeypatch.setenv("DEPLOYMENT_TIER", "preview")


class TestConfirmModeConfig:
    def test_preview_active_allowed(self, monkeypatch):
        _active_preview_env(monkeypatch)
        assert get_effective_confirm_mode() == "active"
        assert is_lifecycle_aware_confirm_active() is True

    def test_preview_override_allows_active(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM_PREVIEW_OVERRIDE", "1")
        assert get_effective_confirm_mode() == "active"

    def test_staging_active_downgrades_to_shadow(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert get_effective_confirm_mode() == "shadow"
        assert is_lifecycle_aware_confirm_active() is False

    def test_production_active_downgrades_to_off(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        assert get_effective_confirm_mode() == "off"

    def test_production_boot_guard_never_active(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        monkeypatch.delenv("PYTEST_RUNNING", raising=False)
        with caplog.at_level(logging.CRITICAL):
            effective = validate_lifecycle_confirm_boot()
        assert effective == "off"
        assert is_lifecycle_aware_confirm_active() is False
        assert "lifecycle_confirm_boot_guard" in caplog.text

    def test_shadow_unchanged_on_staging(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert get_effective_confirm_mode() == "shadow"


class TestCiGovernanceLifecycleActive:
    def test_production_blueprint_rejects_active(self):
        errors = check_production_blueprints_lifecycle_active()
        assert errors == []


class TestEnforceLifecycleConfirm:
    def test_off_mode_noop(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "off")
        out = enforce_lifecycle_confirm_or_raise(
            _req("gas_safety"),
            {"expiry_date": "2027-01-01"},
            surface="apply_extraction",
        )
        assert out["expiry_date"] == "2027-01-01"

    def test_shadow_mode_does_not_block(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        out = enforce_lifecycle_confirm_or_raise(
            _req("tenancy_agreement"),
            {"expiry_date": "2027-01-01"},
            surface="apply_extraction",
        )
        assert out["expiry_date"] == "2027-01-01"

    def test_active_rejects_tenancy_expiry_only(self, monkeypatch):
        _active_preview_env(monkeypatch)
        with pytest.raises(HTTPException) as exc:
            enforce_lifecycle_confirm_or_raise(
                _req("tenancy_agreement"),
                {"expiry_date": "2027-01-01"},
                surface="apply_extraction",
            )
        assert exc.value.status_code == 422
        detail = exc.value.detail
        assert detail["code"] == "LIFECYCLE_CONFIRM_REJECTED"
        assert detail["lifecycle_semantics"] == "TENANCY_LIFECYCLE"
        assert any(v["field"] == "expiry_date" for v in detail["violations"])

    def test_active_accepts_semantic_tenancy_payload(self, monkeypatch):
        _active_preview_env(monkeypatch)
        out = enforce_lifecycle_confirm_or_raise(
            _req("tenancy_agreement"),
            {"tenancy_start_date": "2026-01-01"},
            surface="apply_extraction",
        )
        assert out["tenancy_start_date"] == "2026-01-01"

    @pytest.mark.parametrize(
        "code,payload",
        [
            ("deposit_pi", {"expiry_date": "2027-01-01"}),
            ("right_to_rent", {"expiry_date": "2027-01-01"}),
            ("legionella", {"expiry_date": "2027-01-01"}),
            ("smoke_heat_alarms", {"expiry_date": "2027-01-01"}),
            ("fitness_for_human_habitation", {"expiry_date": "2027-01-01"}),
        ],
    )
    def test_active_rejects_expiry_on_non_expiry(self, monkeypatch, code, payload):
        _active_preview_env(monkeypatch)
        with pytest.raises(HTTPException) as exc:
            enforce_lifecycle_confirm_or_raise(
                _req(code),
                payload,
                surface="apply_extraction",
            )
        assert exc.value.status_code == 422

    def test_active_gas_certificate_success(self, monkeypatch):
        _active_preview_env(monkeypatch)
        out = enforce_lifecycle_confirm_or_raise(
            _req("gas_safety"),
            {"expiry_date": "2027-03-15"},
            surface="apply_extraction",
        )
        assert out.get("expiry_date") == "2027-03-15"

    def test_active_hmo_success(self, monkeypatch):
        _active_preview_env(monkeypatch)
        out = enforce_lifecycle_confirm_or_raise(
            _req("hmo_license"),
            {"expiry_date": "2028-06-01"},
            surface="apply_extraction",
        )
        assert out.get("expiry_date") == "2028-06-01"

    def test_active_logs_enforced_reject(self, monkeypatch, caplog):
        _active_preview_env(monkeypatch)
        with caplog.at_level(logging.INFO):
            with pytest.raises(HTTPException):
                enforce_lifecycle_confirm_or_raise(
                    _req("deposit_pi"),
                    {"expiry_date": "2027-01-01"},
                    surface="apply_extraction",
                )
        assert "lifecycle_confirm_enforced_reject" in caplog.text

    def test_active_contract_unavailable_409(self, monkeypatch):
        _active_preview_env(monkeypatch)
        with patch(
            "services.lifecycle_confirm_validation.try_resolve_lifecycle_confirm_contract",
            return_value=None,
        ):
            with pytest.raises(HTTPException) as exc:
                enforce_lifecycle_confirm_or_raise(
                    _req("gas_safety"),
                    {"expiry_date": "2027-01-01"},
                    surface="apply_extraction",
                )
        assert exc.value.status_code == 409
        assert exc.value.detail["error_code"] == "LIFECYCLE_CONTRACT_UNAVAILABLE"


class TestPersistenceGating:
    def test_off_uses_legacy(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "off")
        plan = resolve_confirm_persistence_update(
            _req("tenancy_agreement"),
            {"expiry_date": "2027-06-15"},
            surface="apply_extraction",
            parse_date=_parse_date,
        )
        assert "due_date" in plan.update_fields

    def test_shadow_uses_legacy(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        plan = resolve_confirm_persistence_update(
            _req("legionella"),
            {"expiry_date": "2027-06-15"},
            surface="apply_extraction",
            parse_date=_parse_date,
        )
        assert "due_date" in plan.update_fields

    def test_active_non_expiry_structured_only(self, monkeypatch):
        _active_preview_env(monkeypatch)
        plan = resolve_confirm_persistence_update(
            _req("legionella"),
            {"assessment_date": "2026-05-01"},
            surface="apply_extraction",
            parse_date=_parse_date,
        )
        assert "due_date" not in plan.update_fields
        assert "status" not in plan.update_fields
        structured = plan.update_fields.get("structured_declaration") or {}
        assert structured.get("assessment_date") == "2026-05-01"

    def test_active_expiry_preserves_certificate_writes(self, monkeypatch):
        _active_preview_env(monkeypatch)
        plan = resolve_confirm_persistence_update(
            _req("gas_safety"),
            {"expiry_date": "2027-03-15"},
            surface="apply_extraction",
            parse_date=_parse_date,
        )
        assert plan.update_fields["due_date"].startswith("2027-03-15")
        assert plan.update_fields["expiry_source"] == "EXTRACTED"

    def test_strip_forbidden_before_active_persist(self):
        contract = build_contract_for_requirement(_req("deposit_pi"))
        stripped = strip_forbidden_contract_fields(
            {"protection_date": "2026-05-01", "expiry_date": "2027-01-01"},
            contract,
        )
        assert "expiry_date" not in stripped
        assert stripped["protection_date"] == "2026-05-01"

    def test_active_never_falls_back_to_legacy_for_non_expiry(self, monkeypatch):
        _active_preview_env(monkeypatch)
        plan = resolve_confirm_persistence_update(
            _req("tenancy_agreement"),
            {"tenancy_start_date": "2026-01-01", "expiry_date": "2027-01-01"},
            surface="apply_extraction",
            parse_date=_parse_date,
        )
        legacy = build_legacy_apply_extraction_update(
            {"expiry_date": "2027-01-01"},
            parse_date=_parse_date,
        )
        assert "due_date" not in plan.update_fields
        assert "due_date" in legacy.update_fields


class TestSemanticPayloadAcceptance:
    @pytest.mark.parametrize(
        "code,field,value",
        [
            ("legionella", "assessment_date", "2026-05-01"),
            ("deposit_pi", "protection_date", "2026-05-01"),
            ("smoke_heat_alarms", "event_date", "2026-05-01"),
            ("tenancy_agreement", "tenancy_start_date", "2026-01-01"),
            ("right_to_rent", "check_date", "2026-05-01"),
            ("fitness_for_human_habitation", "completion_date", "2026-05-01"),
        ],
    )
    def test_validate_accepts_semantic_fields(self, code, field, value):
        contract = build_contract_for_requirement(_req(code))
        ok, violations = validate_confirm_payload_against_contract(
            {field: value},
            contract,
        )
        assert ok is True
        assert violations == []
