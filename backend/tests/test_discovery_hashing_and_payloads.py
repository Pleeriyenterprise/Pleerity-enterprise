"""
Stage H/I — content hash, idempotency, lineage, and raw payload store tests.

No routes, UI, CSV provider, duplicate engine, import workflow, or LeadService.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.discovery.discovery_hashing import (
    CANONICAL_HASH_FIELD_ORDER,
    build_discovery_idempotency_key,
    compute_canonical_content_hash,
    compute_content_hash,
    content_hash_exposes_pii,
    normalize_provider_reference,
    validate_content_hash_hex,
    validate_discovery_idempotency_key,
    validate_origin_lineage,
    validate_origin_lineage_entry,
)
from services.discovery.discovery_models import OriginLineageEntry
from services.discovery.discovery_payload_store import (
    InMemoryRawPayloadStore,
    RawPayloadStoreError,
    build_raw_payload_reference,
    validate_raw_payload_reference,
)
from services.discovery.discovery_prospect_service import (
    DiscoveryProspectService,
    INLINE_PAYLOAD_KEYS,
)

DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
VALID_HASH = "a" * 64


def _canonical_base() -> dict:
    return {
        "provider": "csv",
        "provider_reference": "csv:row-42",
        "source_url": "https://example.com/list",
        "company_name": "Acme Lettings",
        "contact_name": "Jane Doe",
        "email": "Jane@Example.com",
        "phone": "07700 900123",
        "website": "https://acme.example",
        "location": {"city": "London", "postcode": "SW1A 1AA"},
        "business_type": "lettings",
        "landlord_type": "private",
        "campaign_id": "DCAMP-001",
        "discovery_run_id": "DRUN-001",
    }


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------
def test_content_hash_deterministic_for_identical_canonical_content():
    data = _canonical_base()
    assert compute_canonical_content_hash(data) == compute_content_hash(dict(data))


def test_field_order_does_not_affect_hash():
    data_a = _canonical_base()
    data_b = {k: data_a[k] for k in reversed(CANONICAL_HASH_FIELD_ORDER) if k in data_a}
    data_b.update(
        {
            "created_at": datetime.now(timezone.utc),
            "review_status": "needs_review",
        }
    )
    assert compute_canonical_content_hash(data_a) == compute_canonical_content_hash(data_b)


def test_normalisation_email_phone_whitespace():
    base = _canonical_base()
    variant = dict(base)
    variant["email"] = "  JANE@EXAMPLE.COM "
    variant["phone"] = "07700 900 123"
    variant["company_name"] = "  Acme Lettings  "
    assert compute_canonical_content_hash(base) == compute_canonical_content_hash(variant)


def test_volatile_fields_ignored():
    base = _canonical_base()
    polluted = dict(base)
    polluted.update(
        {
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2099-01-01T00:00:00Z",
            "review_status": "approved",
            "reviewer_id": "admin-1",
            "provider_confidence": 99,
            "platform_quality_score": 10,
            "raw_payload_reference": "payload://discovery/csv/DRUN-001/" + VALID_HASH,
            "audit_id": "audit-xyz",
        }
    )
    assert compute_canonical_content_hash(base) == compute_canonical_content_hash(polluted)


def test_identity_source_field_changes_alter_hash():
    base = _canonical_base()
    changed = dict(base)
    changed["company_name"] = "Other Co"
    assert compute_canonical_content_hash(base) != compute_canonical_content_hash(changed)


def test_content_hash_does_not_expose_pii():
    data = _canonical_base()
    digest = compute_canonical_content_hash(data)
    assert validate_content_hash_hex(digest) == []
    assert not content_hash_exposes_pii(digest)
    assert "@" not in digest
    assert "jane" not in digest.lower()


# ---------------------------------------------------------------------------
# Idempotency key
# ---------------------------------------------------------------------------
def test_idempotency_key_stable_across_retry():
    key1 = build_discovery_idempotency_key("csv", "row-42", VALID_HASH)
    key2 = build_discovery_idempotency_key("csv", "row-42", VALID_HASH)
    assert key1 == key2


def test_idempotency_key_validates():
    key = build_discovery_idempotency_key("manual", "ref-1", VALID_HASH)
    assert validate_discovery_idempotency_key(key) == []


def test_idempotency_key_does_not_expose_pii():
    key = build_discovery_idempotency_key(
        "csv",
        "contact@evil.example",
        VALID_HASH,
    )
    assert "@" not in key
    assert validate_discovery_idempotency_key(key) == []


def test_invalid_idempotency_key_rejected():
    assert validate_discovery_idempotency_key("")
    assert validate_discovery_idempotency_key("bad-key")


# ---------------------------------------------------------------------------
# Provider reference normalization
# ---------------------------------------------------------------------------
def test_provider_reference_normalized_and_namespaced():
    assert normalize_provider_reference("csv", "row-7") == "csv:row-7"
    assert normalize_provider_reference("csv", "csv:row-7") == "csv:row-7"
    long_ref = "x" * 300
    assert len(normalize_provider_reference("csv", long_ref)) <= 256


# ---------------------------------------------------------------------------
# Origin lineage
# ---------------------------------------------------------------------------
def _valid_lineage_entry() -> OriginLineageEntry:
    now = datetime.now(timezone.utc)
    return OriginLineageEntry(
        provider="csv",
        provider_reference="csv:row-1",
        discovery_run_id="DRUN-001",
        campaign_id="DCAMP-001",
        content_hash=VALID_HASH,
        discovered_at=now,
        ingested_at=now,
    )


def test_origin_lineage_valid():
    entry = _valid_lineage_entry()
    assert validate_origin_lineage_entry(entry) == []
    assert validate_origin_lineage([entry]) == []


def test_invalid_origin_lineage_rejected():
    bad = {"provider": "csv", "discovery_run_id": "DRUN-1"}
    assert validate_origin_lineage_entry(bad)
    assert validate_origin_lineage([])


def test_origin_lineage_append_only_enforced():
    first = _valid_lineage_entry()
    second = _valid_lineage_entry()
    second.discovery_run_id = "DRUN-002"
    errors = validate_origin_lineage([first, second], previous=[first])
    assert any("cannot be mutated" in e or "append-only" in e for e in errors) is False
    mutated = _valid_lineage_entry()
    mutated.content_hash = "b" * 64
    errors_mut = validate_origin_lineage([mutated], previous=[first])
    assert any("cannot be mutated" in e for e in errors_mut)


# ---------------------------------------------------------------------------
# Raw payload reference + store
# ---------------------------------------------------------------------------
def test_raw_payload_reference_validates():
    ref = build_raw_payload_reference(
        provider="csv",
        discovery_run_id="DRUN-001",
        content_hash=VALID_HASH,
    )
    assert validate_raw_payload_reference(ref) == []
    ref_alt = build_raw_payload_reference(
        provider="csv",
        discovery_run_id="DRUN-001",
        content_hash=VALID_HASH,
        style="ref_token",
    )
    assert validate_raw_payload_reference(ref_alt) == []


def test_invalid_raw_payload_reference_rejected():
    assert validate_raw_payload_reference("payload://bad")
    assert validate_raw_payload_reference("ref:discovery:csv:run:short")
    assert validate_raw_payload_reference("payload://discovery/csv/run/user@evil.com/" + VALID_HASH)


def test_raw_payload_reference_does_not_expose_pii():
    ref = build_raw_payload_reference(
        provider="csv",
        discovery_run_id="DRUN-001",
        content_hash=VALID_HASH,
    )
    assert "@" not in ref
    assert "jane" not in ref.lower()


def test_in_memory_payload_store_put_get_delete():
    store = InMemoryRawPayloadStore()
    payload = {"row": {"name": "secret"}, "email": "pii@example.com"}
    ref = store.put(
        payload,
        {
            "provider": "csv",
            "discovery_run_id": "DRUN-001",
            "content_hash": VALID_HASH,
        },
    )
    assert store.get(ref) == payload
    store.delete(ref)
    with pytest.raises(RawPayloadStoreError):
        store.get(ref)


def test_raw_payload_not_inline_in_prospect_document():
    from services.discovery.discovery_models import DiscoveryProspectDocument

    fields = set(DiscoveryProspectDocument.model_fields.keys())
    for key in INLINE_PAYLOAD_KEYS:
        assert key not in fields


# ---------------------------------------------------------------------------
# Scope guards
# ---------------------------------------------------------------------------
def test_authorized_discovery_routes_exist():
    assert importlib.util.find_spec("routes.admin_discovery") is not None
    assert importlib.util.find_spec("routes.discovery_twin_internal") is not None


def test_no_duplicate_detection_engine():
    assert importlib.util.find_spec("services.discovery.duplicate_detection_engine") is None


def test_discovery_import_service_exists():
    assert importlib.util.find_spec("services.discovery.discovery_import_service") is not None


def test_no_production_payload_store_backends():
    discovery_dir = DISCOVERY_ROOT
    forbidden_modules = ("s3_payload", "gridfs_payload", "boto3_store")
    for path in discovery_dir.rglob("*.py"):
        if path.name in forbidden_modules:
            pytest.fail(f"production storage module present: {path}")
        if path.name == "discovery_payload_store.py":
            text = path.read_text(encoding="utf-8")
            assert "class InMemoryRawPayloadStore" in text
            assert "import boto3" not in text
            assert "from gridfs" not in text


def test_no_lead_service_modification_in_discovery_services():
    authorized = {"discovery_import_service.py"}
    for path in DISCOVERY_ROOT.rglob("*.py"):
        if path.name in authorized:
            continue
        text = path.read_text(encoding="utf-8")
        assert "from services.lead_service import" not in text, path.name
        assert "LeadService.create_lead" not in text, path.name


def test_prospect_service_delegates_raw_payload_validation():
    legacy_ref = "payload://PROSP-REF-001"
    assert DiscoveryProspectService.validate_raw_payload_reference(legacy_ref) == []
