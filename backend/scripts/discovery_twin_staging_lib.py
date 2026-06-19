"""
Discovery Phase 1 — Twin staging operational validation helpers (Stage X).

Real MongoDB staging + real Twin export JSON (required for GREEN operational value).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "docs" / "audit" / "discovery_phase_1_launch_01"
TWIN_EXPORT_DIR = AUDIT_DIR / "twin_exports"
STAGE_V_RESULTS = AUDIT_DIR / "REAL_STAGING_VALIDATION_RESULTS.json"

STAGE_X_TAG = os.environ.get(
    "DISCOVERY_STAGE_X_TAG",
    datetime.now(timezone.utc).strftime("stage-x-%Y%m%d%H%M%S"),
)
EMAIL_DOMAIN = f"{STAGE_X_TAG}.twin.staging.pleerity.com"

TWIN_EXPORT_REQUIRED_FIELDS = (
    "email",
    "company_name",
    "provider_reference",
    "source_url",
    "provider_confidence",
)


@dataclass
class SectionResult:
    section: str
    passed: bool
    status: str
    checks: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    latency_ms: Dict[str, float] = field(default_factory=dict)


@dataclass
class StageXReport:
    authority: str = "STAGE-X-TWIN-STAGING-OPERATIONAL-VALIDATION-AUTHORITY-01"
    generated_at: str = ""
    environment: str = "pleerity_staging"
    branch: str = "develop"
    stage_tag: str = STAGE_X_TAG
    export_source: str = ""
    export_record_count: int = 0
    export_provenance: str = ""  # real_workspace | contract_cohort
    part_a_workspace: Optional[SectionResult] = None
    part_b_export: Optional[SectionResult] = None
    part_c_ingest: Optional[SectionResult] = None
    part_d_review: Optional[SectionResult] = None
    part_e_import: Optional[SectionResult] = None
    part_f_metrics: Optional[SectionResult] = None
    part_g_compliance: Optional[SectionResult] = None
    part_h_lifecycle: Optional[SectionResult] = None
    part_i_cost: Optional[SectionResult] = None
    part_j_comparison: Optional[SectionResult] = None
    part_k_failure_matrix: Optional[SectionResult] = None
    part_l_readiness: Optional[SectionResult] = None
    operational_recommendation: str = ""
    operational_recommendation_evidence: List[str] = field(default_factory=list)
    remaining_blockers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        def _s(s: Optional[SectionResult]) -> Optional[Dict[str, Any]]:
            return asdict(s) if s else None

        return {
            "authority": self.authority,
            "generated_at": self.generated_at,
            "environment": self.environment,
            "branch": self.branch,
            "stage_tag": self.stage_tag,
            "export_source": self.export_source,
            "export_record_count": self.export_record_count,
            "export_provenance": self.export_provenance,
            "part_a_workspace": _s(self.part_a_workspace),
            "part_b_export": _s(self.part_b_export),
            "part_c_ingest": _s(self.part_c_ingest),
            "part_d_review": _s(self.part_d_review),
            "part_e_import": _s(self.part_e_import),
            "part_f_metrics": _s(self.part_f_metrics),
            "part_g_compliance": _s(self.part_g_compliance),
            "part_h_lifecycle": _s(self.part_h_lifecycle),
            "part_i_cost": _s(self.part_i_cost),
            "part_j_comparison": _s(self.part_j_comparison),
            "part_k_failure_matrix": _s(self.part_k_failure_matrix),
            "part_l_readiness": _s(self.part_l_readiness),
            "operational_recommendation": self.operational_recommendation,
            "operational_recommendation_evidence": self.operational_recommendation_evidence,
            "remaining_blockers": self.remaining_blockers,
        }


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def classify_status(passed: bool, failures: Sequence[str], *, amber_ok: bool = False) -> str:
    if passed and not failures:
        return "GREEN"
    if amber_ok and not any("RED" in f for f in failures):
        return "AMBER"
    return "RED" if failures else "GREEN"


def load_twin_export(path: Path) -> Dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return {"export_id": path.stem, "records": raw, "provenance": "real_workspace"}
    if isinstance(raw, dict) and "records" in raw:
        out = dict(raw)
        out.setdefault("provenance", "real_workspace")
        return out
    raise ValueError("Twin export must be a list or object with records[]")


def load_workspace_manifest(path: Optional[Path]) -> Dict[str, Any]:
    if path and path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "workspace_id": os.environ.get("TWIN_WORKSPACE_ID", ""),
        "agent_id": os.environ.get("TWIN_AGENT_ID", ""),
        "agent_name": os.environ.get("TWIN_AGENT_NAME", ""),
        "export_format": "discovery_twin_provider_v1",
        "validated_at": iso_now(),
        "source": "env_fallback" if os.environ.get("TWIN_WORKSPACE_ID") else "missing",
    }


def load_csv_stage_v_baseline() -> Dict[str, Any]:
    if not STAGE_V_RESULTS.is_file():
        return {}
    data = json.loads(STAGE_V_RESULTS.read_text(encoding="utf-8"))
    part_b = data.get("part_b_datasets") or {}
    part_e = data.get("part_e_metrics") or {}
    ingest = (part_b.get("metadata") or {}).get("ingest_results") or {}
    cm = ((part_e.get("metadata") or {}).get("snapshot_excerpt") or {}).get(
        "campaign_metrics"
    ) or {}
    return {
        "prospects_ingested": cm.get("prospects_created", 192),
        "approval_rate_pct": round(
            (cm.get("approved", 0) / max(1, cm.get("prospects_created", 1))) * 100, 2
        ),
        "import_rate_pct": round(
            (cm.get("imported", 0) / max(1, cm.get("prospects_created", 1))) * 100, 2
        ),
        "duplicate_rate_pct": cm.get("duplicate_rate", 0) * 100
        if cm.get("duplicate_rate", 0) < 1
        else cm.get("duplicate_rate", 0),
        "avg_quality_score": cm.get("average_quality_score", 0),
        "ingest_latency_ms": {
            "dataset_a_50": ingest.get("dataset_a", {}).get("latency_ms"),
            "dataset_b_100": ingest.get("dataset_b", {}).get("latency_ms"),
        },
        "stage_v_tag": data.get("stage_tag"),
    }


async def timed_async(label: str, fn):
    start = time.perf_counter()
    outcome = await fn()
    elapsed = round((time.perf_counter() - start) * 1000.0, 2)
    return outcome, elapsed, label


def write_json_report(report: StageXReport, filename: str = "TWIN_STAGING_VALIDATION_RESULTS.json") -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / filename
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path


def validate_export_records(records: Sequence[Mapping[str, Any]]) -> SectionResult:
    checks: List[str] = []
    failures: List[str] = []
    field_coverage = {
        "provider_reference": 0,
        "source_url": 0,
        "company_name": 0,
        "provider_confidence": 0,
        "email": 0,
    }
    for idx, rec in enumerate(records, start=1):
        from services.discovery.providers.twin_provider import _coerce_row, _split_twin_fields

        row = _coerce_row(rec)
        mapped, extras, _ = _split_twin_fields(row)
        if not any(mapped.get(f) for f in ("email", "phone", "company_name", "website")):
            failures.append(f"record {idx}: missing identity fields")
        for field_name in field_coverage:
            if mapped.get(field_name):
                field_coverage[field_name] += 1
        if extras:
            checks.append(f"record {idx}: {len(extras)} twin-only fields isolated to payload")

    count = len(records)
    if count < 50:
        failures.append(f"export count {count} below minimum 50")
    else:
        checks.append(f"export count {count} meets minimum 50")

    for field_name, covered in field_coverage.items():
        pct = round((covered / max(1, count)) * 100, 1)
        checks.append(f"{field_name} populated on {covered}/{count} ({pct}%)")
        if field_name in TWIN_EXPORT_REQUIRED_FIELDS and pct < 80:
            failures.append(f"{field_name} coverage {pct}% below 80% threshold")

    passed = not failures
    return SectionResult(
        section="PART_B_EXPORT",
        passed=passed,
        status=classify_status(passed, failures),
        checks=checks,
        failures=failures,
        metadata={"field_coverage": field_coverage, "record_count": count},
    )


def build_contract_cohort(count: int = 100) -> Dict[str, Any]:
    """Twin-shaped cohort for adapter contract testing — NOT a real workspace export."""
    records: List[Dict[str, Any]] = []
    for i in range(1, count + 1):
        slug = f"prospect-{i:03d}"
        records.append(
            {
                "twin_id": f"twin-export-{STAGE_X_TAG}-{slug}",
                "email": f"{slug}@{EMAIL_DOMAIN}",
                "company_name": f"Twin Staging Landlord Co {i:03d}",
                "contact_name": f"Contact {i}",
                "website": f"https://{slug}.example.test",
                "linkedin_url": f"https://www.linkedin.com/company/{slug}",
                "confidence_score": 55 + (i % 40),
                "lawful_basis": "consent",
                "marketing_consent": True,
                "city": "London",
                "country": "GB",
                "business_type": "landlord",
                "workflow_id": "wf-compliance-vault-prospect",
                "twin_campaign_id": f"tc-{STAGE_X_TAG}",
                "export_batch_id": STAGE_X_TAG,
            }
        )
    return {
        "export_id": f"contract-cohort-{STAGE_X_TAG}",
        "workspace_id": "contract-only",
        "agent_id": "contract-only",
        "provenance": "contract_cohort",
        "records": records,
    }
