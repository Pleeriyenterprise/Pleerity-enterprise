"""Phase 2 S5 — lifecycle confirm apply persistence and shadow telemetry tests."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest

from services.lifecycle_aware_confirm_config import get_effective_confirm_mode
from services.lifecycle_confirm_apply import (
    build_active_plan_apply_extraction_update,
    build_legacy_apply_extraction_update,
    observe_shadow_persistence_for_requirement,
)
from services.lifecycle_confirm_contract import build_contract_for_requirement
from services.lifecycle_extraction_profile_resolver import resolve_extraction_profile


def _req(code: str) -> dict:
    return {"requirement_id": "req-s5", "requirement_code": code}


def _parse_date(value) -> datetime:
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class TestActivePlanPersistenceMaps:
    @pytest.mark.parametrize(
        "code,field",
        [
            ("legionella", "assessment_date"),
            ("deposit_pi", "protection_date"),
            ("smoke_heat_alarms", "event_date"),
            ("tenancy_agreement", "tenancy_start_date"),
            ("right_to_rent", "check_date"),
            ("fitness_for_human_habitation", "completion_date"),
        ],
    )
    def test_non_expiry_writes_structured_declaration(self, code, field):
        requirement = _req(code)
        contract = build_contract_for_requirement(requirement)
        payload = {field: "2026-05-01", "expiry_date": "2027-01-01"}
        plan = build_active_plan_apply_extraction_update(
            requirement,
            payload,
            contract,
            parse_date=_parse_date,
        )
        assert "due_date" not in plan.update_fields
        assert "extracted_expiry_date" not in plan.update_fields
        assert "confirmed_expiry_date" not in plan.update_fields
        assert "expiry_source" not in plan.update_fields
        assert "status" not in plan.update_fields
        structured = plan.update_fields.get("structured_declaration") or {}
        assert structured.get(field) == "2026-05-01"

    def test_expiry_preserves_due_date(self):
        requirement = _req("gas_safety")
        contract = build_contract_for_requirement(requirement)
        plan = build_active_plan_apply_extraction_update(
            requirement,
            {"expiry_date": "2027-03-15"},
            contract,
            parse_date=_parse_date,
        )
        assert plan.update_fields["due_date"].startswith("2027-03-15")
        assert plan.update_fields["extracted_expiry_date"].startswith("2027-03-15")
        assert plan.update_fields["expiry_source"] == "EXTRACTED"
        assert plan.update_fields["status"] in ("COMPLIANT", "EXPIRING_SOON", "OVERDUE")

    def test_hmo_expiry_preserves_due_date(self):
        requirement = _req("hmo_license")
        contract = build_contract_for_requirement(requirement)
        plan = build_active_plan_apply_extraction_update(
            requirement,
            {"expiry_date": "2028-06-01"},
            contract,
            parse_date=_parse_date,
        )
        assert "due_date" in plan.update_fields


class TestShadowPersistenceTelemetry:
    def test_off_mode_no_shadow_log(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "off")
        with caplog.at_level(logging.INFO):
            out = observe_shadow_persistence_for_requirement(
                _req("tenancy_agreement"),
                {"expiry_date": "2027-01-01"},
                surface="apply_extraction",
                parse_date=_parse_date,
                requirement_id="req-s5",
            )
        assert out is None
        assert "lifecycle_confirm_shadow_would_skip_persistence" not in caplog.text

    def test_shadow_logs_would_skip_for_non_expiry(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "shadow")
        with caplog.at_level(logging.INFO):
            obs = observe_shadow_persistence_for_requirement(
                _req("legionella"),
                {"expiry_date": "2027-01-01"},
                surface="apply_extraction",
                parse_date=_parse_date,
                requirement_id="req-s5",
                document_id="doc-s5",
            )
        assert obs is not None
        assert "due_date" in obs.skipped_fields
        assert "lifecycle_confirm_shadow_would_skip_persistence" in caplog.text

    def test_shadow_does_not_change_legacy_plan(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "shadow")
        payload = {"expiry_date": "2027-06-15"}
        legacy = build_legacy_apply_extraction_update(payload, parse_date=_parse_date)
        observe_shadow_persistence_for_requirement(
            _req("tenancy_agreement"),
            payload,
            surface="apply_extraction",
            parse_date=_parse_date,
        )
        assert "due_date" in legacy.update_fields


class TestActiveModeBlocked:
    def test_active_without_preview_resolves_to_off(self, monkeypatch):
        monkeypatch.delenv("DEPLOYMENT_TIER", raising=False)
        monkeypatch.delenv("LIFECYCLE_AWARE_CONFIRM_PREVIEW_OVERRIDE", raising=False)
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "active")
        assert get_effective_confirm_mode() == "off"


class TestDepositPiDocumentContext:
    def test_deposit_pi_defaults_to_protection_profile(self):
        resolved = resolve_extraction_profile(_req("deposit_pi"))
        assert resolved.profile_id == "deposit_protection_v1"

    def test_deposit_pi_not_slug_mapped_to_prescribed_information(self):
        from services.lifecycle_extraction_profiles import profile_for_storage_slug

        assert profile_for_storage_slug("deposit_pi") == "deposit_protection_v1"

    def test_document_context_prescribed_information_for_pi_doc(self):
        resolved = resolve_extraction_profile(
            _req("deposit_pi"),
            document={"document_type": "deposit_prescribed_info"},
        )
        assert resolved.profile_id == "prescribed_information_v1"
        assert resolved.resolution_source == "document_context"

    def test_document_context_how_to_rent(self):
        resolved = resolve_extraction_profile(
            _req("deposit_pi"),
            document={"document_type": "how_to_rent"},
        )
        assert resolved.profile_id == "prescribed_information_v1"

    def test_registry_still_wins_over_document_context(self):
        registry_row = {
            "lifecycle": {
                "semantics": "DECLARATION_BASED",
                "extraction_profile_id": "deposit_protection_v1",
            }
        }
        resolved = resolve_extraction_profile(
            _req("deposit_pi"),
            registry_row=registry_row,
            document={"document_type": "how_to_rent"},
        )
        assert resolved.profile_id == "deposit_protection_v1"
        assert resolved.resolution_source == "registry"
