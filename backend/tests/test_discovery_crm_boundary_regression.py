"""
Stage Q — Discovery CRM boundary regression authority.

Static and contract guards that fail if developers introduce bypass paths:
Provider → Prospect → Review → DiscoveryImportService → LeadService → CRM

No new business capabilities — enforcement tests only.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Set

import pytest

from services.discovery import discovery_config
from services.discovery.discovery_import_service import (
    DISCOVERY_IMPORT_TAG,
    DiscoveryImportService,
)
from services.discovery.discovery_metadata_contract import (
    example_valid_discovery_metadata,
    validate_discovery_source_metadata,
)
from services.discovery.discovery_models import DiscoveryProviderId
from services.discovery.discovery_provider_registry import DiscoveryProviderRegistry
from services.discovery.providers.discovery_provider_protocol import (
    PROHIBITED_PROVIDER_CAPABILITIES,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_ROOT = BACKEND_ROOT / "services" / "discovery"
PROVIDERS_ROOT = DISCOVERY_ROOT / "providers"
ADMIN_DISCOVERY_ROUTE = BACKEND_ROOT / "routes" / "admin_discovery.py"
IMPORT_SERVICE_FILE = DISCOVERY_ROOT / "discovery_import_service.py"
APPROVAL_QUEUE_FILE = DISCOVERY_ROOT / "discovery_approval_queue_service.py"

CREATE_LEAD_PATTERN = re.compile(r"LeadService\.create_lead\s*\(")
FIND_DUPLICATE_PATTERN = re.compile(r"LeadService\.find_duplicate\s*\(")
UPDATE_LEAD_PATTERN = re.compile(r"LeadService\.update_lead\s*\(")
DELETE_LEAD_PATTERN = re.compile(r"LeadService\.delete_lead\s*\(")
LEAD_SERVICE_IMPORT_PATTERN = re.compile(
    r"from\s+services\.lead_service\s+import|import\s+services\.lead_service"
)
LEAD_MODELS_IMPORT_PATTERN = re.compile(
    r"from\s+services\.lead_models\s+import|import\s+services\.lead_models"
)

CRM_WRITE_PATTERNS = (
    re.compile(r"""get_db\(\)\s*\[\s*['"]leads['"]\s*\]"""),
    re.compile(r"""\[\s*['"]leads['"]\s*\]"""),
    re.compile(r"\[LEADS_COLLECTION\]"),
    re.compile(r"\.leads\.(insert_one|update_one|replace_one|bulk_write)"),
    re.compile(r"leads_collection\.(insert_one|update_one|replace_one|bulk_write)"),
)

PROVIDER_SPECIFIC_PAYLOAD_MARKERS = (
    "csv_row",
    "raw_row",
    "apollo_",
    "clay_",
    "twin_",
    "crawler_",
    "provider_raw",
)

IMPORT_ROUTE_PATTERN = re.compile(
    r'@router\.(post|put|patch)\s*\(\s*["\'][^"\']*import',
    re.IGNORECASE,
)


def _strip_docstrings(text: str) -> str:
    return re.sub(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', "", text)


def _iter_py_files(root: Path) -> Iterable[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _discovery_py_files(*, exclude_import_service: bool = False) -> List[Path]:
    files = list(_iter_py_files(DISCOVERY_ROOT))
    if exclude_import_service:
        files = [p for p in files if p.name != "discovery_import_service.py"]
    return files


def _files_matching(pattern: re.Pattern[str], paths: Iterable[Path]) -> List[str]:
    hits: List[str] = []
    for path in paths:
        if pattern.search(_read(path)):
            hits.append(path.relative_to(BACKEND_ROOT).as_posix())
    return hits


# --- Part I: LeadService boundary guards ---


def test_only_discovery_import_service_calls_create_lead_in_discovery_tree():
    callers = _files_matching(CREATE_LEAD_PATTERN, _discovery_py_files())
    assert callers == ["services/discovery/discovery_import_service.py"], callers


def test_only_discovery_import_service_calls_find_duplicate_in_discovery_tree():
    callers = _files_matching(FIND_DUPLICATE_PATTERN, _discovery_py_files())
    assert callers == ["services/discovery/discovery_import_service.py"], callers


def test_discovery_tree_has_no_update_or_delete_lead_calls():
    for pattern in (UPDATE_LEAD_PATTERN, DELETE_LEAD_PATTERN):
        hits = _files_matching(pattern, _discovery_py_files())
        assert hits == [], f"unexpected {pattern.pattern}: {hits}"


def test_only_discovery_import_service_imports_lead_service_in_discovery_tree():
    importers = _files_matching(LEAD_SERVICE_IMPORT_PATTERN, _discovery_py_files())
    assert importers == ["services/discovery/discovery_import_service.py"], importers


def test_only_discovery_import_service_imports_lead_models_in_discovery_tree():
    importers = _files_matching(LEAD_MODELS_IMPORT_PATTERN, _discovery_py_files())
    assert importers == ["services/discovery/discovery_import_service.py"], importers


def test_providers_cannot_call_leadservice():
    for path in _iter_py_files(PROVIDERS_ROOT):
        text = _strip_docstrings(_read(path))
        assert not LEAD_SERVICE_IMPORT_PATTERN.search(text), path.name
        assert not CREATE_LEAD_PATTERN.search(text), path.name
        assert not FIND_DUPLICATE_PATTERN.search(text), path.name


def test_providers_do_not_reference_lead_models():
    for path in _iter_py_files(PROVIDERS_ROOT):
        text = _read(path)
        assert not LEAD_MODELS_IMPORT_PATTERN.search(text), path.name
        assert "LeadCreateRequest" not in text, path.name


def test_providers_prohibit_crm_write_capability():
    assert "CRM_WRITE" in PROHIBITED_PROVIDER_CAPABILITIES
    text = _read(PROVIDERS_ROOT / "discovery_provider_protocol.py")
    for cap in PROHIBITED_PROVIDER_CAPABILITIES:
        assert cap in text


def test_approval_queue_cannot_call_leadservice():
    text = _read(APPROVAL_QUEUE_FILE)
    assert "LeadService" not in text
    assert "DiscoveryImportService" not in text
    assert "import_prospect" not in text
    assert not CREATE_LEAD_PATTERN.search(text)
    assert not FIND_DUPLICATE_PATTERN.search(text)


def test_admin_discovery_routes_cannot_call_leadservice_or_import():
    text = _strip_docstrings(_read(ADMIN_DISCOVERY_ROUTE))
    assert not LEAD_SERVICE_IMPORT_PATTERN.search(text)
    assert not CREATE_LEAD_PATTERN.search(text)
    assert "import_prospect" not in text
    assert not re.search(
        r"from\s+services\.discovery\.discovery_import_service\s+import",
        text,
    )
    assert not IMPORT_ROUTE_PATTERN.search(text)


def test_no_discovery_route_imports_directly():
    routes_dir = BACKEND_ROOT / "routes"
    for path in _iter_py_files(routes_dir):
        text = _strip_docstrings(_read(path))
        if "discovery" not in path.name.lower():
            continue
        assert not re.search(
            r"from\s+services\.discovery\.discovery_import_service\s+import",
            text,
        ), path.name
        assert "import_prospect" not in text, path.name


def test_discovery_modules_cannot_write_leads_collection_directly():
    for path in _discovery_py_files():
        text = _read(path)
        for pattern in CRM_WRITE_PATTERNS:
            assert not pattern.search(text), (
                f"{path.relative_to(BACKEND_ROOT)} matched {pattern.pattern}"
            )


def test_discovery_modules_have_no_bulk_write_or_upsert_to_crm():
    forbidden = re.compile(r"(bulk_write|replace_one|upsert)", re.IGNORECASE)
    for path in _discovery_py_files():
        text = _read(path)
        if forbidden.search(text):
            # discovery collections only — reject leads coupling
            assert "leads" not in text.lower() or "imported_lead_id" in text, path.name


# --- Metadata contract and CRM payload neutrality ---


def test_metadata_contract_example_still_validates():
    payload = example_valid_discovery_metadata()
    ok, errors = validate_discovery_source_metadata(payload)
    assert ok, errors


def test_import_service_metadata_includes_version_and_required_fields():
    content_hash = "a" * 64
    prospect = {
        "prospect_id": "PROSP-Q-1",
        "discovery_run_id": "DRUN-Q-1",
        "provider": DiscoveryProviderId.CSV.value,
        "lawful_basis": "legitimate_interest_b2b",
        "content_hash": content_hash,
        "platform_quality_score": 80,
        "provider_confidence": 70,
        "risk_flags": [],
        "erasure_status": "active",
        "origin_lineage": [
            {
                "provider": DiscoveryProviderId.CSV.value,
                "discovery_run_id": "DRUN-Q-1",
                "ingested_at": "2026-06-01T12:00:00Z",
                "discovered_at": "2026-06-01T12:00:00Z",
                "content_hash": content_hash,
                "content_hash_version": "1",
                "hash_algorithm": "sha256",
            }
        ],
    }
    metadata = DiscoveryImportService.build_discovery_source_metadata(prospect)
    ok, errors = validate_discovery_source_metadata(metadata)
    assert ok, errors
    assert metadata.get("schema_version")
    assert metadata.get("origin_lineage")


def test_build_lead_create_payload_is_provider_neutral():
    base_prospect = {
        "prospect_id": "PROSP-Q-2",
        "discovery_run_id": "DRUN-Q-2",
        "contact_name": "Alex",
        "email": "alex@example.com",
        "company_name": "Acme",
        "marketing_consent": False,
        "lawful_basis": "legitimate_interest",
        "platform_quality_score": 50,
        "provider_confidence": 50,
        "risk_flags": [],
        "erasure_status": "active",
        "origin_lineage": [
            {
                "provider": "manual",
                "discovery_run_id": "DRUN-Q-2",
                "ingested_at": "2026-06-01T12:00:00Z",
                "content_hash": "def",
                "content_hash_version": "1",
                "hash_algorithm": "sha256",
            }
        ],
    }
    providers = (
        DiscoveryProviderId.CSV.value,
        DiscoveryProviderId.APOLLO.value,
        DiscoveryProviderId.CLAY.value,
        DiscoveryProviderId.TWIN.value,
        DiscoveryProviderId.INTERNAL_CRAWLER.value,
    )
    payloads = []
    for provider in providers:
        prospect = {**base_prospect, "provider": provider}
        prospect["origin_lineage"][0]["provider"] = provider
        metadata = DiscoveryImportService.build_discovery_source_metadata(prospect)
        req = DiscoveryImportService.build_lead_create_payload(
            prospect, discovery_metadata=metadata
        )
        payloads.append(req)

    field_sets = [
        {
            k: v
            for k, v in p.model_dump().items()
            if k not in ("tags", "admin_notes", "source_metadata")
        }
        for p in payloads
    ]
    assert len({str(fs) for fs in field_sets}) == 1

    for req in payloads:
        dumped = str(req.model_dump()).lower()
        for marker in PROVIDER_SPECIFIC_PAYLOAD_MARKERS:
            assert marker not in dumped
        discovery_meta = req.source_metadata.get("discovery", {})
        assert "raw_payload" not in discovery_meta
        assert DISCOVERY_IMPORT_TAG in req.tags
        assert any(t.startswith("discovery_run:") for t in req.tags)
        assert any(t.startswith("discovery_provider:") for t in req.tags)


# --- Provider registry neutrality ---


def test_provider_registry_entries_remain_provider_neutral():
    registry = DiscoveryProviderRegistry()
    for entry in registry.list_providers():
        violations = entry.capability_violations()
        assert violations == [], entry.provider_id.value
        assert entry.ingest_implemented is (
            entry.provider_id in (DiscoveryProviderId.CSV, DiscoveryProviderId.TWIN)
        )


def test_twin_registry_ingest_implemented():
    registry = DiscoveryProviderRegistry()
    twin = registry.get(DiscoveryProviderId.TWIN.value)
    assert twin.ingest_implemented is True
    assert twin.capabilities.supports_enrichment is False


@pytest.mark.parametrize(
    "provider_id",
    [
        DiscoveryProviderId.APOLLO.value,
        DiscoveryProviderId.CLAY.value,
        DiscoveryProviderId.INTERNAL_CRAWLER.value,
    ],
)
def test_future_provider_registry_entries_not_ingest_implemented(provider_id: str):
    registry = DiscoveryProviderRegistry()
    entry = registry.get(provider_id)
    assert entry.ingest_implemented is False
    assert entry.phase >= 2


# --- Production flags and import path uniqueness ---


def test_production_discovery_flags_default_false(monkeypatch):
    for name in (
        "DISCOVERY_MODULE_ENABLED",
        "DISCOVERY_PROVIDER_LAYER_ENABLED",
        "DISCOVERY_CSV_IMPORT_ENABLED",
        "DISCOVERY_PROVIDER_CSV_ENABLED",
        "DISCOVERY_PROVIDER_TWIN_ENABLED",
        "DISCOVERY_PROVIDER_APOLLO_ENABLED",
        "DISCOVERY_PROVIDER_CLAY_ENABLED",
        "DISCOVERY_PROVIDER_INTERNAL_CRAWLER_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)
    assert discovery_config.is_discovery_module_enabled() is False
    assert discovery_config.is_discovery_provider_layer_enabled() is False
    assert discovery_config.is_discovery_csv_import_enabled() is False
    assert discovery_config.is_provider_enabled("csv") is False
    assert discovery_config.is_provider_enabled("apollo") is False


def test_import_path_remains_unique_in_discovery_tree():
    importers: Set[str] = set()
    for path in _discovery_py_files():
        text = _read(path)
        if "import_prospect" in text and path.name != "discovery_import_service.py":
            importers.add(path.name)
    assert importers == set()


def test_discovery_import_service_is_sole_crm_crossing_documented():
    text = _read(IMPORT_SERVICE_FILE)
    assert "LeadService.create_lead" in text
    assert "DiscoveryImportService" in text


# --- Launch gate NG-026 / NG-027 enforceability hooks ---


def test_ng026_no_alternate_discovery_import_entrypoints():
    """NG-026: no discovery module other than import service orchestrates CRM import."""
    alternate_patterns = (
        re.compile(r"await\s+LeadService\.create_lead"),
        re.compile(r"DiscoveryImportService\.import_prospect"),
    )
    for path in _discovery_py_files(exclude_import_service=True):
        text = _read(path)
        for pattern in alternate_patterns:
            assert not pattern.search(text), (
                f"{path.name} matches {pattern.pattern}"
            )


def test_ng027_discovery_providers_and_approval_isolated_from_leadservice():
    """NG-027: providers and approval queue must not reference LeadService."""
    targets = list(_iter_py_files(PROVIDERS_ROOT)) + [APPROVAL_QUEUE_FILE]
    for path in targets:
        text = _strip_docstrings(_read(path))
        assert not LEAD_SERVICE_IMPORT_PATTERN.search(text), path.name
        assert not CREATE_LEAD_PATTERN.search(text), path.name
