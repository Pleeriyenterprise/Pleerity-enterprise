"""Phase 5 P5-S6 — lifecycle KPI breakdown exposure in reporting surfaces + hardening guards."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Set, Tuple

import pytest

from services.lifecycle_kpi_gates import (
    LIFECYCLE_KPI_BREAKDOWN_KEYS,
    attach_additive_lifecycle_kpi_fields,
    lifecycle_kpi_breakdown_report_entries,
)
from services.monthly_digest_operational_intelligence import _build_lifecycle_attention_breakdown
from services.report_compliance_summary_executive import build_compliance_summary_executive_model
from services.reporting_service import ReportingService
from services.requirement_client_runtime_surface import compute_client_portal_requirement_stats

BACKEND_ROOT = Path(__file__).resolve().parent.parent

_AUTHORITATIVE_KEYS: Tuple[str, ...] = (
    "total_requirements",
    "compliant",
    "satisfied",
    "status_valid",
    "pending",
    "missing_evidence",
    "expiring_soon",
    "overdue",
)

_VALID_EFFECTIVE_MODES: FrozenSet[str] = frozenset({"off", "shadow", "active"})

_REPORTING_P5_S6_MODULES: Tuple[str, ...] = (
    "services/reporting_service.py",
    "services/professional_reports.py",
    "services/report_compliance_summary_executive.py",
    "services/monthly_digest_assembly_service.py",
    "services/monthly_digest_operational_intelligence.py",
    "services/monthly_digest_pdf_service.py",
    "email_templates/unified/scheduled_report_digest.py",
    "services/pdf_report_builder.py",
)

_REPORTING_ATTACH_CONSUMERS: FrozenSet[str] = frozenset(
    {
        "services/reporting_service.py",
        "services/professional_reports.py",
    }
)

_REPORTING_PASS_THROUGH_CONSUMERS: FrozenSet[str] = frozenset(
    {
        "services/monthly_digest_assembly_service.py",
        "services/report_compliance_summary_executive.py",
        "services/monthly_digest_operational_intelligence.py",
        "services/monthly_digest_pdf_service.py",
        "email_templates/unified/scheduled_report_digest.py",
        "services/pdf_report_builder.py",
    }
)

_ALLOWED_REPORTING_LIFECYCLE_IMPORTS: FrozenSet[str] = frozenset(
    {
        "attach_additive_lifecycle_kpi_fields",
        "lifecycle_kpi_breakdown_report_entries",
        "lifecycle_kpi_report_framing_note",
    }
)

_FORBIDDEN_REPORTING_LIFECYCLE_SYMBOLS: Tuple[str, ...] = (
    "resolve_lifecycle_semantics(",
    "compute_lifecycle_kpi_stats(",
    "lifecycle_kpi_breakdown_api_payload(",
    "lifecycle_kpi_breakdown_for_portal_rows(",
    "attention_kind_buckets",
    "_empty_attention_kind_buckets",
    "_ATTENTION_KIND_BUCKETS",
    "_ATTENTION_KIND_TO_API_KEY",
    "lifecycle_kpi_breakdown_api_payload",
)

_P5_S6_ALLOWED_CHANGED_PATHS: FrozenSet[str] = frozenset(
    {
        "backend/docs/STREAM_B_SCORING_AUTHORITY_MATRIX.md",
        "backend/docs/audit/REQUIREMENT_LIFECYCLE_MASTER_IMPLEMENTATION_TRACKER.md",
        "backend/email_templates/unified/scheduled_report_digest.py",
        "backend/services/compliance_score.py",
        "backend/services/lifecycle_kpi_gates.py",
        "backend/services/monthly_digest_assembly_service.py",
        "backend/services/monthly_digest_operational_intelligence.py",
        "backend/services/monthly_digest_pdf_service.py",
        "backend/services/pdf_report_builder.py",
        "backend/services/professional_reports.py",
        "backend/services/report_compliance_summary_executive.py",
        "backend/services/reporting_service.py",
        "backend/tests/test_lifecycle_kpis_p5_s3_authority_regression.py",
        "backend/tests/test_lifecycle_kpis_p5_s6.py",
    }
)

_P5_S6_FORBIDDEN_CHANGED_PREFIXES: Tuple[str, ...] = (
    "frontend/",
    "backend/routes/",
    "backend/services/requirement_client_runtime_surface.py",
    "render.staging.yaml",
    "render.production.yaml",
    "backend/services/lifecycle_aware_kpis_config.py",
    "backend/scripts/deployment_governance_ci_gate.py",
    "backend/server.py",
)


def _relative_backend_path(path: Path) -> str:
    return path.relative_to(BACKEND_ROOT).as_posix()


def _iter_backend_python_modules() -> Iterable[Path]:
    for root in (BACKEND_ROOT / "services", BACKEND_ROOT / "routes", BACKEND_ROOT / "email_templates"):
        if root.is_dir():
            yield from root.rglob("*.py")


def _read_reporting_module(rel: str) -> str:
    path = BACKEND_ROOT / rel.replace("/", os.sep)
    return path.read_text(encoding="utf-8", errors="replace")


def _expiring_soon_row(requirement_code: str) -> dict:
    return {
        "requirement_code": requirement_code,
        "status": "EXPIRING_SOON",
        "requirement_satisfied": False,
    }


class TestReportingLifecycleAttachHelper:
    def test_off_mode_omits_lifecycle_fields(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_KPIS", raising=False)
        target: Dict[str, object] = {}
        rows = [_expiring_soon_row("legionella")]
        attach_additive_lifecycle_kpi_fields(target, rows)
        assert "lifecycle_kpi_breakdown" not in target
        assert "lifecycle_kpi_effective_mode" not in target

    def test_shadow_mode_attaches_breakdown(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        target: Dict[str, object] = {}
        rows = [_expiring_soon_row("legionella")]
        attach_additive_lifecycle_kpi_fields(target, rows)
        assert target.get("lifecycle_kpi_effective_mode") == "shadow"
        breakdown = target.get("lifecycle_kpi_breakdown")
        assert isinstance(breakdown, dict)
        assert breakdown["review_due"] == 1
        assert set(breakdown.keys()) == set(LIFECYCLE_KPI_BREAKDOWN_KEYS)

    def test_active_preview_attaches_breakdown(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        target: Dict[str, object] = {}
        rows = [_expiring_soon_row("legionella")]
        attach_additive_lifecycle_kpi_fields(target, rows)
        assert target.get("lifecycle_kpi_effective_mode") == "active"
        assert target["lifecycle_kpi_breakdown"]["review_due"] == 1


class TestBreakdownKeyContract:
    @pytest.mark.parametrize(
        "kpi_mode,tier",
        [
            ("shadow", "staging"),
            ("active", "preview"),
        ],
    )
    def test_breakdown_has_exactly_six_canonical_keys(self, monkeypatch, kpi_mode, tier):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", kpi_mode)
        monkeypatch.setenv("DEPLOYMENT_TIER", tier)
        target: Dict[str, object] = {}
        rows = [_expiring_soon_row("legionella"), _expiring_soon_row("gas_safety")]
        attach_additive_lifecycle_kpi_fields(target, rows)
        breakdown = target["lifecycle_kpi_breakdown"]
        assert isinstance(breakdown, dict)
        assert set(breakdown.keys()) == set(LIFECYCLE_KPI_BREAKDOWN_KEYS)
        assert set(breakdown.keys()) == {
            "certificate_expiring",
            "review_due",
            "event_action_required",
            "tenancy_term_ending",
            "occupancy_review_due",
            "operational_action_required",
        }
        for value in breakdown.values():
            assert isinstance(value, int)
            assert value >= 0


class TestEffectiveModeContract:
    @pytest.mark.parametrize(
        "kpi_mode,tier,expected",
        [
            ("shadow", "staging", "shadow"),
            ("active", "preview", "active"),
        ],
    )
    def test_attached_effective_mode_is_canonical(self, monkeypatch, kpi_mode, tier, expected):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", kpi_mode)
        monkeypatch.setenv("DEPLOYMENT_TIER", tier)
        target: Dict[str, object] = {}
        attach_additive_lifecycle_kpi_fields(target, [_expiring_soon_row("legionella")])
        mode = target.get("lifecycle_kpi_effective_mode")
        assert mode in _VALID_EFFECTIVE_MODES
        assert mode == expected

    def test_off_mode_omits_effective_mode(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_KPIS", raising=False)
        target: Dict[str, object] = {}
        attach_additive_lifecycle_kpi_fields(target, [_expiring_soon_row("legionella")])
        assert "lifecycle_kpi_effective_mode" not in target


class TestReportingAdditiveContract:
    def test_attach_does_not_mutate_eight_key_totals(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        rows = [_expiring_soon_row("legionella"), {"status": "OVERDUE"}]
        counts = compute_client_portal_requirement_stats(rows)
        before = {k: counts[k] for k in _AUTHORITATIVE_KEYS}
        attach_additive_lifecycle_kpi_fields(counts, rows)
        for key in _AUTHORITATIVE_KEYS:
            assert counts[key] == before[key]
        assert "lifecycle_kpi_breakdown" in counts

    def test_legacy_requirements_breakdown_fields_unchanged_in_csv_off_mode(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_KPIS", raising=False)
        svc = ReportingService()
        data = {
            "report_type": "Compliance Status Summary",
            "generated_at": "2026-06-02T00:00:00+00:00",
            "client": {"name": "Test"},
            "summary": {
                "total_properties": 1,
                "compliance_rate": 100,
                "compliance_breakdown": {"green": 1, "amber": 0, "red": 0},
                "total_requirements": 1,
                "requirements_breakdown": {
                    "compliant": 1,
                    "pending": 0,
                    "overdue": 0,
                    "expiring_soon": 0,
                },
                "expiring_next_30_days": 0,
                "expiring_next_60_days": 0,
                "expiring_next_90_days": 0,
            },
            "reporting_semantics": {"counts": {}},
        }
        content = svc._generate_compliance_csv(data)["content"]
        assert "Total Requirements,1" in content
        assert "Overdue,0" in content
        assert "Expiring Soon,0" in content
        assert "LIFECYCLE ATTENTION BREAKDOWN" not in content


class TestReportingServiceCsvExposure:
    def test_off_csv_unchanged_no_lifecycle_section(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_KPIS", raising=False)
        svc = ReportingService()
        data = {
            "report_type": "Compliance Status Summary",
            "generated_at": "2026-06-02T00:00:00+00:00",
            "client": {"name": "Test"},
            "summary": {
                "total_properties": 1,
                "compliance_rate": 100,
                "compliance_breakdown": {"green": 1, "amber": 0, "red": 0},
                "total_requirements": 1,
                "requirements_breakdown": {
                    "compliant": 1,
                    "pending": 0,
                    "overdue": 0,
                    "expiring_soon": 0,
                },
                "expiring_next_30_days": 0,
                "expiring_next_60_days": 0,
                "expiring_next_90_days": 0,
            },
            "reporting_semantics": {"counts": {}},
        }
        out = svc._generate_compliance_csv(data)
        content = out["content"]
        assert "LIFECYCLE ATTENTION BREAKDOWN" not in content
        assert "lifecycle_kpi_effective_mode" not in content

    def test_shadow_csv_includes_lifecycle_section(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        rows = [_expiring_soon_row("legionella")]
        counts = compute_client_portal_requirement_stats(rows)
        summary: Dict[str, object] = {
            "total_properties": 1,
            "compliance_rate": 0,
            "compliance_breakdown": {"green": 0, "amber": 1, "red": 0},
            "total_requirements": counts["total_requirements"],
            "requirements_breakdown": {
                "compliant": counts["compliant"],
                "pending": counts["pending"],
                "overdue": counts["overdue"],
                "expiring_soon": counts["expiring_soon"],
            },
            "expiring_next_30_days": 0,
            "expiring_next_60_days": 0,
            "expiring_next_90_days": 0,
        }
        attach_additive_lifecycle_kpi_fields(summary, rows)
        svc = ReportingService()
        data = {
            "report_type": "Compliance Status Summary",
            "generated_at": "2026-06-02T00:00:00+00:00",
            "client": {"name": "Test"},
            "summary": summary,
            "reporting_semantics": {"counts": {}},
        }
        content = svc._generate_compliance_csv(data)["content"]
        assert "=== LIFECYCLE ATTENTION BREAKDOWN (SUPPLEMENTAL) ===" in content
        assert "lifecycle_kpi_effective_mode,shadow" in content
        assert "Review due,1" in content
        assert "Expiring Soon," in content


class TestExecutiveModelPassThrough:
    def test_executive_model_includes_lifecycle_from_counts(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        rows = [_expiring_soon_row("legionella")]
        counts = compute_client_portal_requirement_stats(rows)
        attach_additive_lifecycle_kpi_fields(counts, rows)
        model = build_compliance_summary_executive_model(
            requirements=rows,
            properties=[],
            client_doc={},
            matrix_rows=[],
            readiness={},
            counts=counts,
            total_props=0,
            green=0,
            amber=0,
            red=0,
        )
        assert model.get("lifecycle_kpi_effective_mode") == "shadow"
        assert model["lifecycle_kpi_breakdown"]["review_due"] == 1
        metrics = model.get("portfolio_metrics") or {}
        assert metrics.get("overdue") == counts["overdue"]


class TestDigestPassThrough:
    def test_digest_intelligence_lifecycle_block_from_model(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        rows = [_expiring_soon_row("legionella")]
        summary: Dict[str, object] = {}
        attach_additive_lifecycle_kpi_fields(summary, rows)
        block = _build_lifecycle_attention_breakdown(summary)
        assert block is not None
        assert block["lifecycle_kpi_effective_mode"] == "shadow"
        assert block["entries"] == [{"label": "Review due", "count": 1}]


class TestSingleAttachPointVerification:
    def test_attach_helper_defined_once_in_lifecycle_kpi_gates(self):
        definitions: List[str] = []
        for path in _iter_backend_python_modules():
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"^def attach_additive_lifecycle_kpi_fields\b", text, re.MULTILINE):
                definitions.append(_relative_backend_path(path))
        assert definitions == ["services/lifecycle_kpi_gates.py"]

    def test_reporting_attach_consumers_delegate_to_canonical_helper(self):
        missing: List[str] = []
        for rel in sorted(_REPORTING_ATTACH_CONSUMERS):
            text = _read_reporting_module(rel)
            if "attach_additive_lifecycle_kpi_fields" not in text:
                missing.append(rel)
        assert missing == []

    def test_pass_through_consumers_do_not_call_attach_helper(self):
        violations: List[str] = []
        for rel in sorted(_REPORTING_PASS_THROUGH_CONSUMERS):
            text = _read_reporting_module(rel)
            if "attach_additive_lifecycle_kpi_fields" in text:
                violations.append(rel)
        assert violations == []

    def test_pass_through_consumers_do_not_recompute_breakdown(self):
        """Pass-through/presentation modules must not call lifecycle aggregation APIs."""
        for rel in sorted(_REPORTING_PASS_THROUGH_CONSUMERS):
            text = _read_reporting_module(rel)
            for forbidden in _FORBIDDEN_REPORTING_LIFECYCLE_SYMBOLS:
                assert forbidden not in text, f"{rel} must not use {forbidden}"

    def test_pass_through_chain_references_breakdown_or_intelligence_block(self):
        """Consumers must read pre-computed breakdown (direct or via digest intelligence)."""
        signals = {
            "services/monthly_digest_assembly_service.py": ("lifecycle_kpi_breakdown",),
            "services/report_compliance_summary_executive.py": ("lifecycle_kpi_breakdown",),
            "services/monthly_digest_operational_intelligence.py": (
                "lifecycle_kpi_breakdown",
                "lifecycle_attention_breakdown",
            ),
            "services/monthly_digest_pdf_service.py": ("lifecycle_attention_breakdown",),
            "email_templates/unified/scheduled_report_digest.py": ("lifecycle_kpi_breakdown",),
            "services/pdf_report_builder.py": ("lifecycle_kpi_breakdown",),
        }
        for rel, needles in signals.items():
            text = _read_reporting_module(rel)
            assert any(n in text for n in needles), f"{rel} must consume pass-through breakdown"


class TestReportingStaticAuthorityProtection:
    def test_breakdown_attach_only_on_allowlisted_modules(self):
        from tests.test_lifecycle_kpis_p5_s3_authority_regression import (
            _ALLOWED_LIFECYCLE_KPI_BREAKDOWN_ATTACH_MODULES,
        )

        violations: List[str] = []
        for path in _iter_backend_python_modules():
            rel = _relative_backend_path(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            if "attach_additive_lifecycle_kpi_fields" not in text:
                continue
            if rel not in _ALLOWED_LIFECYCLE_KPI_BREAKDOWN_ATTACH_MODULES:
                violations.append(rel)
        assert violations == []

    def test_reporting_modules_forbidden_lifecycle_aggregation_symbols(self):
        violations: List[Tuple[str, str]] = []
        for rel in _REPORTING_P5_S6_MODULES:
            text = _read_reporting_module(rel)
            for symbol in _FORBIDDEN_REPORTING_LIFECYCLE_SYMBOLS:
                if symbol in text:
                    violations.append((rel, symbol))
        assert violations == []

    def test_reporting_modules_only_import_allowed_lifecycle_gate_symbols(self):
        import_pattern = re.compile(
            r"from services\.lifecycle_kpi_gates import \(([^)]+)\)|"
            r"from services\.lifecycle_kpi_gates import (\w+)",
            re.MULTILINE | re.DOTALL,
        )
        violations: List[str] = []
        for rel in _REPORTING_P5_S6_MODULES:
            text = _read_reporting_module(rel)
            for match in import_pattern.finditer(text):
                block = match.group(1) or match.group(2) or ""
                names = {n.strip() for n in re.split(r"[,\s]+", block) if n.strip()}
                disallowed = names - _ALLOWED_REPORTING_LIFECYCLE_IMPORTS
                if disallowed:
                    violations.append(f"{rel}: {sorted(disallowed)}")
        assert violations == []

    def test_no_duplicate_attach_helper_implementations(self):
        duplicates: List[str] = []
        for path in _iter_backend_python_modules():
            rel = _relative_backend_path(path)
            if rel == "services/lifecycle_kpi_gates.py":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(
                r"def attach_additive_lifecycle_kpi_fields\b|"
                r"def lifecycle_kpi_breakdown_for_portal_rows\b",
                text,
            ):
                duplicates.append(rel)
        assert duplicates == []


class TestP5S6OutOfScopeFrozen:
    def test_p5_s6_changed_files_within_allowed_set(self):
        """Regression guard: P5-S6 must not touch forbidden surfaces."""
        repo_root = BACKEND_ROOT.parent
        import subprocess

        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        changed: Set[str] = set()
        for line in (result.stdout or "").splitlines():
            line = line.strip().replace("\\", "/")
            if line:
                changed.add(line)
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        for line in (untracked.stdout or "").splitlines():
            line = line.strip().replace("\\", "/")
            if line:
                changed.add(line)

        if not changed:
            pytest.skip("no local diff to verify")

        unexpected = sorted(changed - _P5_S6_ALLOWED_CHANGED_PATHS)
        assert unexpected == [], f"unexpected changed files: {unexpected}"

        for path in changed:
            for prefix in _P5_S6_FORBIDDEN_CHANGED_PREFIXES:
                assert not path.startswith(prefix) and path != prefix.lstrip("/"), (
                    f"forbidden path changed: {path}"
                )
