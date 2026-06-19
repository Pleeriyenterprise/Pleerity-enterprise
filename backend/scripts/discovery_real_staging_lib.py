"""
Discovery Phase 1 — real staging validation helpers (Stage V).

Shared dataset generation, Mongo index checks, and report structures.
Uses real MongoDB staging only — not the synthetic in-memory harness.
"""
from __future__ import annotations

import csv
import io
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "docs" / "audit" / "discovery_phase_1_launch_01"
DATASET_DIR = AUDIT_DIR / "datasets"

STAGE_V_TAG = os.environ.get(
    "DISCOVERY_STAGE_V_TAG",
    datetime.now(timezone.utc).strftime("stage-v-%Y%m%d%H%M%S"),
)
EMAIL_DOMAIN = f"{STAGE_V_TAG}.staging.pleerity.com"
CSV_HEADER = (
    "email,company_name,website,contact_name,lawful_basis,marketing_consent,provider_reference"
)

REQUIRED_COLLECTIONS = (
    "discovery_prospects",
    "discovery_runs",
    "discovery_campaigns",
    "discovery_jobs",
    "discovery_audit_logs",
    "discovery_metrics",
    "discovery_suppression_records",
)


@dataclass
class SectionResult:
    section: str
    passed: bool
    status: str  # GREEN | AMBER | RED
    checks: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    latency_ms: Dict[str, float] = field(default_factory=dict)


@dataclass
class StageVReport:
    authority: str = "STAGE-V-REAL-STAGING-VALIDATION-AND-PROVIDER-EXPANSION-READINESS-AUTHORITY-01"
    generated_at: str = ""
    environment: str = "pleerity_staging"
    branch: str = "develop"
    database_name: str = ""
    stage_tag: str = STAGE_V_TAG
    part_a_database: Optional[SectionResult] = None
    part_b_datasets: Optional[SectionResult] = None
    part_c_review: Optional[SectionResult] = None
    part_d_import: Optional[SectionResult] = None
    part_e_metrics: Optional[SectionResult] = None
    part_f_lifecycle: Optional[SectionResult] = None
    part_g_performance: Optional[SectionResult] = None
    part_h_mf07: Optional[SectionResult] = None
    part_i_provider_readiness: Optional[SectionResult] = None
    part_j_failure_matrix: Optional[SectionResult] = None
    part_k_go_no_go: Optional[SectionResult] = None
    twin_onboarding_answer: str = ""
    twin_onboarding_evidence: List[str] = field(default_factory=list)
    remaining_blockers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        def _section(s: Optional[SectionResult]) -> Optional[Dict[str, Any]]:
            return asdict(s) if s else None

        return {
            "authority": self.authority,
            "generated_at": self.generated_at,
            "environment": self.environment,
            "branch": self.branch,
            "database_name": self.database_name,
            "stage_tag": self.stage_tag,
            "part_a_database": _section(self.part_a_database),
            "part_b_datasets": _section(self.part_b_datasets),
            "part_c_review": _section(self.part_c_review),
            "part_d_import": _section(self.part_d_import),
            "part_e_metrics": _section(self.part_e_metrics),
            "part_f_lifecycle": _section(self.part_f_lifecycle),
            "part_g_performance": _section(self.part_g_performance),
            "part_h_mf07": _section(self.part_h_mf07),
            "part_i_provider_readiness": _section(self.part_i_provider_readiness),
            "part_j_failure_matrix": _section(self.part_j_failure_matrix),
            "part_k_go_no_go": _section(self.part_k_go_no_go),
            "twin_onboarding_answer": self.twin_onboarding_answer,
            "twin_onboarding_evidence": self.twin_onboarding_evidence,
            "remaining_blockers": self.remaining_blockers,
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def _csv_row(
    *,
    email: str,
    company: str,
    lawful_basis: str = "consent",
    marketing_consent: str = "true",
    provider_reference: str = "",
    website: str = "",
    contact_name: str = "",
) -> str:
    if not website:
        slug = email.split("@")[0].replace(".", "-")
        website = f"https://{slug}.example.test"
    if not contact_name:
        contact_name = f"Contact {company}"
    if not provider_reference:
        slug = email.split("@")[0]
        provider_reference = f"csv:{STAGE_V_TAG}-{slug}"
    return (
        f"{email},{company},{website},{contact_name},"
        f"{lawful_basis},{marketing_consent},{provider_reference}"
    )


def build_dataset_a() -> str:
    lines = [CSV_HEADER]
    for i in range(1, 51):
        email = f"dataset-a-{i:03d}@{EMAIL_DOMAIN}"
        lines.append(
            _csv_row(email=email, company=f"Stage V Co A{i:03d}")
        )
    return "\n".join(lines) + "\n"


def build_dataset_b() -> str:
    lines = [CSV_HEADER]
    for i in range(1, 101):
        email = f"dataset-b-{i:03d}@{EMAIL_DOMAIN}"
        lines.append(
            _csv_row(email=email, company=f"Stage V Co B{i:03d}")
        )
    return "\n".join(lines) + "\n"


def build_dataset_c(*, duplicate_emails: Sequence[str]) -> str:
    lines = [CSV_HEADER]
    for idx, email in enumerate(duplicate_emails[:15], start=1):
        lines.append(
            _csv_row(
                email=email,
                company=f"Dup Co {idx}",
                provider_reference=f"csv:{STAGE_V_TAG}-dup-{idx}",
            )
        )
    for i in range(1, 16):
        email = f"dataset-c-new-{i:03d}@{EMAIL_DOMAIN}"
        lines.append(
            _csv_row(email=email, company=f"Stage V Co C{i:03d}")
        )
    # In-batch duplicate idempotency (same provider_reference + content)
    dup_email = f"dataset-c-batch-dup@{EMAIL_DOMAIN}"
    ref = f"csv:{STAGE_V_TAG}-batch-dup"
    lines.append(_csv_row(email=dup_email, company="Batch Dup Co", provider_reference=ref))
    lines.append(_csv_row(email=dup_email, company="Batch Dup Co", provider_reference=ref))
    return "\n".join(lines) + "\n"


def build_dataset_d() -> str:
    lines = [CSV_HEADER]
    lines.append(
        _csv_row(
            email=f"dataset-d-unknown@{EMAIL_DOMAIN}",
            company="Unknown Basis Co",
            lawful_basis="unknown",
            marketing_consent="false",
        )
    )
    lines.append(
        _csv_row(
            email=f"dataset-d-consent-mismatch@{EMAIL_DOMAIN}",
            company="Consent Mismatch Co",
            lawful_basis="legitimate_interest_b2b",
            marketing_consent="true",
        )
    )
    lines.append(
        "bad@example.com,Bad URL Co,not-a-url,Bad Contact,consent,true,bad-url-ref"
    )
    lines.append(
        _csv_row(
            email=f"dataset-d-valid@{EMAIL_DOMAIN}",
            company="Valid D Co",
        )
    )
    return "\n".join(lines) + "\n"


def build_dataset_e() -> str:
    lines = [CSV_HEADER]
    for i in range(1, 11):
        email = f"dataset-e-good-{i:03d}@{EMAIL_DOMAIN}"
        lines.append(_csv_row(email=email, company=f"Mixed Good {i}"))
    lines.append(",Missing Identity,,,consent,false,empty-identity")
    lines.append(
        _csv_row(
            email=f"dataset-e-bad-basis@{EMAIL_DOMAIN}",
            company="Mixed Bad Basis",
            lawful_basis="invalid_basis",
            marketing_consent="false",
        )
    )
    for i in range(11, 21):
        email = f"dataset-e-good-{i:03d}@{EMAIL_DOMAIN}"
        lines.append(_csv_row(email=email, company=f"Mixed Good {i}"))
    return "\n".join(lines) + "\n"


def write_datasets(
    *,
    duplicate_emails: Optional[Sequence[str]] = None,
) -> Dict[str, Path]:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    dup = duplicate_emails or [f"dataset-a-001@{EMAIL_DOMAIN}"]
    mapping = {
        "dataset_a_50.csv": build_dataset_a(),
        "dataset_b_100.csv": build_dataset_b(),
        "dataset_c_duplicates.csv": build_dataset_c(duplicate_emails=dup),
        "dataset_d_compliance_failures.csv": build_dataset_d(),
        "dataset_e_mixed_quality.csv": build_dataset_e(),
    }
    paths: Dict[str, Path] = {}
    for name, content in mapping.items():
        path = DATASET_DIR / name
        path.write_text(content, encoding="utf-8")
        paths[name] = path
    return paths


async def timed_async(label: str, fn: Callable):
    start = time.perf_counter()
    outcome = await fn()
    elapsed = round((time.perf_counter() - start) * 1000.0, 2)
    return outcome, elapsed, label


def index_key_signature(keys: Any) -> Tuple:
    if isinstance(keys, str):
        return ((keys, 1),)
    if isinstance(keys, list):
        return tuple(keys)
    return (("unknown", 0),)


async def validate_discovery_indexes(db) -> Tuple[List[str], List[str], Dict[str, Any]]:
    from services.discovery.discovery_indexes import DISCOVERY_INDEX_INVENTORY

    checks: List[str] = []
    failures: List[str] = []
    inventory: Dict[str, Any] = {"collections": {}, "missing_indexes": []}

    for collection_name in REQUIRED_COLLECTIONS:
        names = await db.list_collection_names()
        exists = collection_name in names
        count = await db[collection_name].count_documents({}) if exists else 0
        inventory["collections"][collection_name] = {
            "exists": exists,
            "document_count": count,
        }
        if not exists:
            failures.append(f"collection missing: {collection_name}")
        else:
            checks.append(f"{collection_name} present (count={count})")

    for collection_name, keys, kwargs in DISCOVERY_INDEX_INVENTORY:
        coll = db[collection_name]
        indexes = await coll.list_indexes().to_list(length=200)
        expected_sig = index_key_signature(keys)
        matched = False
        for idx in indexes:
            idx_keys = tuple(idx.get("key", {}).items())
            if idx_keys == expected_sig:
                matched = True
                if kwargs.get("unique") and not idx.get("unique"):
                    failures.append(
                        f"{collection_name} index {keys} exists but unique flag mismatch"
                    )
                break
        if not matched:
            inventory["missing_indexes"].append(
                {"collection": collection_name, "keys": keys, "kwargs": kwargs}
            )
            failures.append(f"missing index on {collection_name}: {keys}")
        else:
            checks.append(f"index verified {collection_name} {keys}")

    # Suppression collection has no dedicated index spec — note as AMBER gap
    if "discovery_suppression_records" not in [
        spec[0] for spec in DISCOVERY_INDEX_INVENTORY
    ]:
        inventory["suppression_index_gap"] = (
            "discovery_suppression_records not in DISCOVERY_INDEX_INVENTORY"
        )

    return checks, failures, inventory


async def fetch_stage_v_prospects(db, campaign_id: str) -> List[Dict[str, Any]]:
    cursor = db["discovery_prospects"].find(
        {"campaign_id": campaign_id},
        {"_id": 0},
    )
    return await cursor.to_list(length=5000)


async def fetch_stage_v_audit_logs(db, campaign_id: str) -> List[Dict[str, Any]]:
    cursor = db["discovery_audit_logs"].find(
        {"campaign_id": campaign_id},
        {"_id": 0},
    )
    return await cursor.to_list(length=10000)


def classify_status(passed: bool, failures: Sequence[str], *, amber_ok: bool = False) -> str:
    if passed and not failures:
        return "GREEN"
    if amber_ok and len(failures) <= 2:
        return "AMBER"
    return "RED"


def write_json_report(report: StageVReport, filename: str = "REAL_STAGING_VALIDATION_RESULTS.json") -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / filename
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path
