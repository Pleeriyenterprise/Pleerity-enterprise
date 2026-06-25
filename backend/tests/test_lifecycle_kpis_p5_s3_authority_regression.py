"""
P5-S3 KPI authority regression guards.

Prevents accidental mixing of legacy and lifecycle KPI authority, and detects
parallel KPI aggregation entry points introduced outside the canonical switch.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Iterable, List

import pytest

from services.lifecycle_aware_kpis_config import get_effective_kpi_mode
from services.lifecycle_kpi_gates import (
    compute_lifecycle_kpi_stats,
    lifecycle_stats_authoritative_payload,
)
from services.requirement_client_runtime_surface import (
    _compute_legacy_portal_requirement_stats,
    compute_client_portal_requirement_stats,
)

BACKEND_ROOT = Path(__file__).resolve().parent.parent

_AUTHORITATIVE_KEYS: tuple[str, ...] = (
    "total_requirements",
    "compliant",
    "satisfied",
    "status_valid",
    "pending",
    "missing_evidence",
    "expiring_soon",
    "overdue",
)

_ALLOWED_COMPUTE_LIFECYCLE_KPI_STATS_MODULES = frozenset(
    {
        "services/lifecycle_kpi_gates.py",
        "services/requirement_client_runtime_surface.py",
    }
)

_ALLOWED_LIFECYCLE_STATS_PAYLOAD_MODULES = frozenset(
    {
        "services/lifecycle_kpi_gates.py",
        "services/requirement_client_runtime_surface.py",
    }
)

_ALLOWED_LIFECYCLE_KPI_BREAKDOWN_MODULES = frozenset(
    {
        "services/lifecycle_kpi_gates.py",
        "services/compliance_score.py",
        "services/reporting_service.py",
        "services/professional_reports.py",
    }
)

_ALLOWED_LIFECYCLE_KPI_BREAKDOWN_ATTACH_MODULES = frozenset(
    {
        "services/lifecycle_kpi_gates.py",
        "services/compliance_score.py",
        "services/reporting_service.py",
        "services/professional_reports.py",
    }
)


def _expiring_soon_row(requirement_code: str) -> dict:
    return {
        "requirement_code": requirement_code,
        "status": "EXPIRING_SOON",
        "requirement_satisfied": False,
    }


# Rows where legacy and lifecycle authority diverge on expiring_soon (and total_requirements).
_DIVERGENT_ROWS: List[dict] = [
    _expiring_soon_row("legionella"),
    _expiring_soon_row("gas_safety"),
    {"status": "PENDING"},
    {"status": "OVERDUE"},
]


def _relative_backend_path(path: Path) -> str:
    return path.relative_to(BACKEND_ROOT).as_posix()


def _iter_backend_python_modules() -> Iterable[Path]:
    for root in (BACKEND_ROOT / "services", BACKEND_ROOT / "routes"):
        if root.is_dir():
            yield from root.rglob("*.py")


def _forbidden_single_key_hybrids(
    legacy: Dict[str, int],
    lifecycle: Dict[str, int],
) -> List[Dict[str, int]]:
    """Hybrids that mix one legacy value with lifecycle values on another key."""
    hybrids: List[Dict[str, int]] = []
    for key in _AUTHORITATIVE_KEYS:
        if legacy[key] == lifecycle[key]:
            continue
        hybrid = dict(legacy)
        hybrid[key] = lifecycle[key]
        if hybrid != legacy and hybrid != lifecycle:
            hybrids.append(hybrid)
    return hybrids


def _assert_payload_contract(stats: Dict[str, int]) -> None:
    assert set(stats.keys()) == set(_AUTHORITATIVE_KEYS)
    assert len(stats) == len(_AUTHORITATIVE_KEYS)
    for key in _AUTHORITATIVE_KEYS:
        assert isinstance(stats[key], int)


class TestKpiAuthorityAtomicity:
    """Returned KPI payload must come from exactly one authority — never mixed."""

    @pytest.fixture
    def divergent_authorities(self):
        legacy = _compute_legacy_portal_requirement_stats(_DIVERGENT_ROWS)
        lifecycle = lifecycle_stats_authoritative_payload(
            compute_lifecycle_kpi_stats(_DIVERGENT_ROWS),
        )
        assert legacy != lifecycle, "fixture must produce divergent legacy vs lifecycle"
        return legacy, lifecycle

    def test_off_returns_only_legacy_never_lifecycle(self, monkeypatch, divergent_authorities):
        monkeypatch.delenv("LIFECYCLE_AWARE_KPIS", raising=False)
        legacy, lifecycle = divergent_authorities
        stats = compute_client_portal_requirement_stats(_DIVERGENT_ROWS)
        assert get_effective_kpi_mode() == "off"
        assert stats == legacy
        assert stats != lifecycle
        for hybrid in _forbidden_single_key_hybrids(legacy, lifecycle):
            assert stats != hybrid

    def test_shadow_returns_only_legacy_never_lifecycle(self, monkeypatch, divergent_authorities):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        legacy, lifecycle = divergent_authorities
        stats = compute_client_portal_requirement_stats(_DIVERGENT_ROWS)
        assert get_effective_kpi_mode() == "shadow"
        assert stats == legacy
        assert stats != lifecycle
        for hybrid in _forbidden_single_key_hybrids(legacy, lifecycle):
            assert stats != hybrid

    def test_shadow_may_compute_and_log_lifecycle(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        with caplog.at_level(logging.INFO):
            compute_client_portal_requirement_stats(_DIVERGENT_ROWS)
        assert "lifecycle_kpi_shadow_complete" in caplog.text

    def test_active_returns_only_lifecycle_never_legacy(self, monkeypatch, divergent_authorities):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        legacy, lifecycle = divergent_authorities
        stats = compute_client_portal_requirement_stats(_DIVERGENT_ROWS)
        assert get_effective_kpi_mode() == "active"
        assert stats == lifecycle
        assert stats != legacy
        for hybrid in _forbidden_single_key_hybrids(legacy, lifecycle):
            assert stats != hybrid

    def test_active_each_key_from_lifecycle_authority_only(self, monkeypatch, divergent_authorities):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        legacy, lifecycle = divergent_authorities
        stats = compute_client_portal_requirement_stats(_DIVERGENT_ROWS)
        for key in _AUTHORITATIVE_KEYS:
            assert stats[key] == lifecycle[key]
            if legacy[key] != lifecycle[key]:
                assert stats[key] != legacy[key]


class TestKpiPayloadContract:
    @pytest.mark.parametrize(
        "env",
        [
            pytest.param({"LIFECYCLE_AWARE_KPIS": "off"}, id="off"),
            pytest.param(
                {"LIFECYCLE_AWARE_KPIS": "shadow", "DEPLOYMENT_TIER": "staging"},
                id="shadow",
            ),
            pytest.param(
                {"LIFECYCLE_AWARE_KPIS": "active", "DEPLOYMENT_TIER": "preview"},
                id="active",
            ),
        ],
    )
    def test_exact_eight_key_payload(self, monkeypatch, env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        stats = compute_client_portal_requirement_stats(_DIVERGENT_ROWS)
        _assert_payload_contract(stats)


class TestSingleKpiAuthorityEntryPoint:
    def test_compute_client_portal_requirement_stats_defined_once(self):
        definitions: List[str] = []
        pattern = re.compile(r"^def compute_client_portal_requirement_stats\b", re.MULTILINE)
        for path in _iter_backend_python_modules():
            text = path.read_text(encoding="utf-8", errors="replace")
            if pattern.search(text):
                definitions.append(_relative_backend_path(path))
        assert definitions == ["services/requirement_client_runtime_surface.py"]

    def test_compute_lifecycle_kpi_stats_not_used_outside_authority_switch(self):
        violations: List[str] = []
        for path in _iter_backend_python_modules():
            rel = _relative_backend_path(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            if "compute_lifecycle_kpi_stats" not in text:
                continue
            if rel not in _ALLOWED_COMPUTE_LIFECYCLE_KPI_STATS_MODULES:
                violations.append(rel)
        assert violations == []

    def test_lifecycle_stats_authoritative_payload_not_used_outside_authority_switch(self):
        violations: List[str] = []
        for path in _iter_backend_python_modules():
            rel = _relative_backend_path(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            if "lifecycle_stats_authoritative_payload" not in text:
                continue
            if rel not in _ALLOWED_LIFECYCLE_STATS_PAYLOAD_MODULES:
                violations.append(rel)
        assert violations == []

    def test_lifecycle_kpi_breakdown_not_used_outside_exposure_points(self):
        violations: List[str] = []
        for path in _iter_backend_python_modules():
            rel = _relative_backend_path(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            if "lifecycle_kpi_breakdown_for_portal_rows" not in text:
                continue
            if rel not in _ALLOWED_LIFECYCLE_KPI_BREAKDOWN_MODULES:
                violations.append(rel)
        assert violations == []

    def test_lifecycle_kpi_breakdown_attach_only_on_allowlisted_modules(self):
        violations: List[str] = []
        for path in _iter_backend_python_modules():
            rel = _relative_backend_path(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            if "attach_additive_lifecycle_kpi_fields" not in text:
                continue
            if rel not in _ALLOWED_LIFECYCLE_KPI_BREAKDOWN_ATTACH_MODULES:
                violations.append(rel)
        assert violations == []

    def test_no_parallel_portal_kpi_aggregation_helpers(self):
        """Reject new public KPI aggregators alongside the canonical switch."""
        forbidden = re.compile(
            r"^def (compute_(?!client_portal_requirement_stats)"
            r".*portal.*stats|aggregate_.*kpi.*stats)\b",
            re.MULTILINE | re.IGNORECASE,
        )
        violations: List[str] = []
        for path in _iter_backend_python_modules():
            rel = _relative_backend_path(path)
            if rel == "services/requirement_client_runtime_surface.py":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if forbidden.search(text):
                violations.append(rel)
        assert violations == []
