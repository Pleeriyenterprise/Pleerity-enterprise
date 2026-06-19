"""
Stage R — DiscoveryConsentService tests.

Compliance enforcement only — no TPS/CTPS, notifications, or LeadService changes.
"""
from __future__ import annotations

import hashlib
import re
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.discovery.discovery_consent_service import (
    SUPPRESSION_SOURCE_DISCOVERY_RECORD,
    SUPPRESSION_SOURCE_ERASED_PROSPECT,
    DiscoveryConsentService,
)
from services.discovery.discovery_import_service import (
    DiscoveryImportService,
    ImportAttribution,
)
from services.discovery.discovery_models import (
    DiscoveryErasureStatus,
    DiscoveryLawfulBasis,
    DiscoveryReviewStatus,
)

DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
LEAD_SERVICE_FILE = Path(__file__).resolve().parents[1] / "services" / "lead_service.py"
NOW = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)

ATTR = ImportAttribution(
    actor_id="compliance-1",
    actor_email="compliance@pleerity.com",
    timestamp=NOW,
)


def _hash_for(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _prospect(**overrides: Any) -> Dict[str, Any]:
    email = overrides.pop("email", "consent@example.com")
    base: Dict[str, Any] = {
        "prospect_id": "PROSP-R-1",
        "discovery_run_id": "DRUN-R-1",
        "email": email,
        "email_hash": _hash_for(email),
        "lawful_basis": DiscoveryLawfulBasis.CONSENT.value,
        "marketing_consent": False,
        "erasure_status": DiscoveryErasureStatus.ACTIVE.value,
        "review_status": DiscoveryReviewStatus.APPROVED.value,
        "origin_lineage": [
            {
                "provider": "manual",
                "discovery_run_id": "DRUN-R-1",
                "ingested_at": "2026-06-01T12:00:00Z",
                "content_hash": _hash_for("lineage"),
            }
        ],
        "content_hash": _hash_for("lineage"),
    }
    base.update(overrides)
    return base


class _FakeCollection:
    def __init__(self):
        self.docs: List[Dict[str, Any]] = []
        self.insert_one = AsyncMock(side_effect=self._insert_one)
        self.find_one = AsyncMock(side_effect=self._find_one)
        self.update_one = AsyncMock(side_effect=self._update_one)
        self.find = MagicMock(side_effect=self._find)

    async def _insert_one(self, doc):
        self.docs.append(dict(doc))

    async def _find_one(self, query, projection=None):
        for doc in self.docs:
            if self._match(doc, query):
                out = dict(doc)
                out.pop("_id", None)
                return out
        return None

    async def _update_one(self, query, update):
        for doc in self.docs:
            if self._match(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    def _find(self, query, projection=None):
        matches = [dict(d) for d in self.docs if self._match(d, query)]

        class _Cursor:
            def __init__(self, items):
                self._items = items

            async def to_list(self, length):
                return self._items[:length]

        return _Cursor(matches)

    def _match(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(self._match(doc, clause) for clause in expected):
                    return False
                continue
            if key == "$ne":
                continue
            if isinstance(expected, dict):
                if "$ne" in expected and doc.get(key) == expected["$ne"]:
                    return False
                continue
            if doc.get(key) != expected:
                return False
        if "$ne" in query:
            for field, val in query.items():
                if field.startswith("$"):
                    continue
                if doc.get(field) == query.get("$ne"):
                    return False
        return True


class _FakeDB:
    def __init__(self):
        self.discovery_prospects = _FakeCollection()
        self.discovery_suppression_records = _FakeCollection()
        self.discovery_audit_logs = _FakeCollection()

    def __getitem__(self, name: str):
        return getattr(self, name)


def _db_patch(db: _FakeDB):
    return patch(
        "services.discovery.discovery_consent_service.database.get_db",
        return_value=db,
    )


# --- Lawful basis ---


def test_consent_basis_valid():
    result = DiscoveryConsentService.validate_lawful_basis(_prospect())
    assert result.valid is True
    assert result.lawful_basis == "consent"


def test_consent_basis_invalid_unknown():
    result = DiscoveryConsentService.validate_lawful_basis(
        _prospect(lawful_basis=DiscoveryLawfulBasis.UNKNOWN.value)
    )
    assert result.valid is False


def test_consent_basis_invalid_unsupported():
    result = DiscoveryConsentService.validate_lawful_basis(
        _prospect(lawful_basis="made_up_basis")
    )
    assert result.valid is False


# --- Marketing consent ---


def test_marketing_consent_true_with_consent_basis():
    result = DiscoveryConsentService.validate_marketing_consent(
        _prospect(
            lawful_basis=DiscoveryLawfulBasis.CONSENT.value,
            marketing_consent=True,
        )
    )
    assert result.valid is True


def test_marketing_consent_true_without_consent_basis():
    result = DiscoveryConsentService.validate_marketing_consent(
        _prospect(
            lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
            marketing_consent=True,
        )
    )
    assert result.valid is False


def test_marketing_consent_true_with_valid_lia():
    result = DiscoveryConsentService.validate_marketing_consent(
        _prospect(
            lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
            marketing_consent=True,
            lia_reference="LIA-2026-01",
            lia_completed=True,
        )
    )
    assert result.valid is True


def test_contract_basis_blocks_marketing_consent_without_justification():
    result = DiscoveryConsentService.validate_marketing_consent(
        _prospect(lawful_basis="contract", marketing_consent=True)
    )
    assert result.valid is False


def test_contract_basis_allows_marketing_consent_when_justified():
    result = DiscoveryConsentService.validate_marketing_consent(
        _prospect(
            lawful_basis="contract",
            marketing_consent=True,
            marketing_consent_justified=True,
        )
    )
    assert result.valid is True


def test_legal_obligation_blocks_marketing_consent():
    result = DiscoveryConsentService.validate_marketing_consent(
        _prospect(lawful_basis="legal_obligation", marketing_consent=True)
    )
    assert result.valid is False


# --- LIA ---


def test_legitimate_interest_without_lia():
    result = DiscoveryConsentService.validate_legitimate_interest(
        _prospect(lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value)
    )
    assert result.required is True
    assert result.complete is False


def test_legitimate_interest_with_valid_lia():
    result = DiscoveryConsentService.validate_legitimate_interest(
        _prospect(
            lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
            lia_reference="LIA-2026-PILOT",
            lia_completed=True,
            lia_review_date="2026-01-01",
        )
    )
    assert result.required is True
    assert result.complete is True


# --- Suppression ---


@pytest.mark.asyncio
async def test_erased_prospect_suppression_blocks():
    db = _FakeDB()
    prospect = _prospect(erasure_status=DiscoveryErasureStatus.ERASED.value)
    with _db_patch(db):
        result = await DiscoveryConsentService.check_suppression_lists(prospect)
    assert result.status == "blocked"
    assert SUPPRESSION_SOURCE_ERASED_PROSPECT in result.matched_sources


@pytest.mark.asyncio
async def test_erased_hash_match_blocks_import():
    db = _FakeDB()
    email = "erased@example.com"
    email_h = _hash_for(email)
    await db.discovery_prospects.insert_one(
        {
            "prospect_id": "PROSP-ERASED",
            "email_hash": email_h,
            "erasure_status": DiscoveryErasureStatus.ERASED.value,
        }
    )
    prospect = _prospect(email=email, email_hash=email_h, prospect_id="PROSP-NEW")
    with _db_patch(db):
        result = await DiscoveryConsentService.check_suppression_lists(prospect)
    assert result.status == "blocked"
    assert SUPPRESSION_SOURCE_ERASED_PROSPECT in result.matched_sources


@pytest.mark.asyncio
async def test_suppression_record_blocks_import():
    db = _FakeDB()
    email = "blocked@example.com"
    email_h = _hash_for(email)
    await db.discovery_suppression_records.insert_one(
        {"active": True, "email_hash": email_h, "reason": "internal opt-out"}
    )
    prospect = _prospect(email=email, email_hash=email_h)
    with _db_patch(db):
        result = await DiscoveryConsentService.check_suppression_lists(prospect)
    assert result.status == "blocked"
    assert SUPPRESSION_SOURCE_DISCOVERY_RECORD in result.matched_sources


@pytest.mark.asyncio
async def test_suppression_match_blocks_import_compliance():
    db = _FakeDB()
    prospect = _prospect(erasure_status=DiscoveryErasureStatus.ERASED.value)
    with _db_patch(db):
        compliance = await DiscoveryConsentService.validate_import_compliance(prospect)
    assert compliance.compliant is False
    assert any(e["event_type"] == "SUPPRESSION_MATCH" for e in compliance.compliance_audit_events)


# --- Compliance summary ---


@pytest.mark.asyncio
async def test_compliance_summary_generation_pass():
    db = _FakeDB()
    with _db_patch(db):
        compliance = await DiscoveryConsentService.validate_import_compliance(_prospect())
    summary = DiscoveryConsentService.build_compliance_summary(compliance)
    assert "Lawful Basis:" in summary
    assert "Valid" in summary
    assert "Import Compliance:\nPASS" in summary


@pytest.mark.asyncio
async def test_compliance_summary_generation_fail():
    db = _FakeDB()
    prospect = _prospect(
        lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
        marketing_consent=True,
    )
    with _db_patch(db):
        compliance = await DiscoveryConsentService.validate_import_compliance(prospect)
    summary = DiscoveryConsentService.build_compliance_summary(compliance)
    assert "Import Compliance:\nFAIL" in summary


# --- Import eligibility integration ---


@pytest.mark.asyncio
async def test_import_eligibility_integration_blocks_lia_failure():
    db = _FakeDB()
    prospect = _prospect(
        lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
        marketing_consent=False,
    )
    with _db_patch(db):
        result = await DiscoveryImportService.validate_import_eligibility(prospect)
    assert result.eligible is False
    assert any("lia_reference" in r for r in result.blocking_reasons)


@pytest.mark.asyncio
async def test_import_eligibility_integration_passes_with_consent():
    db = _FakeDB()
    with _db_patch(db):
        result = await DiscoveryImportService.validate_import_eligibility(_prospect())
    assert result.eligible is True
    assert result.compliance_summary is not None


# --- Audit events on import block ---


@pytest.mark.asyncio
async def test_audit_events_created_on_consent_failure():
    from tests.test_discovery_import_service import (
        _approve,
        _db_patches,
        _seed_prospect,
        _FakeDB,
    )

    db = _FakeDB()
    with _db_patches(db):
        doc = await _seed_prospect(db)
        await _approve(db, doc["prospect_id"])
        await db.discovery_prospects.update_one(
            {"prospect_id": doc["prospect_id"]},
            {
                "$set": {
                    "lawful_basis": DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
                    "marketing_consent": True,
                }
            },
        )
        result = await DiscoveryImportService.import_prospect(
            doc["prospect_id"], ATTR
        )
    assert result["status"] == "blocked"
    event_types = [a["event_type"] for a in db.discovery_audit_logs.docs]
    assert "CONSENT_VALIDATION_FAILED" in event_types
    assert "IMPORT_BLOCKED" in event_types


@pytest.mark.asyncio
async def test_audit_events_created_on_lia_failure():
    from tests.test_discovery_import_service import (
        _approve,
        _db_patches,
        _seed_prospect,
        _FakeDB,
    )

    db = _FakeDB()
    with _db_patches(db):
        doc = await _seed_prospect(
            db,
            lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
            marketing_consent=False,
        )
        await _approve(db, doc["prospect_id"])
        result = await DiscoveryImportService.import_prospect(
            doc["prospect_id"], ATTR
        )
    assert result["status"] == "blocked"
    event_types = [a["event_type"] for a in db.discovery_audit_logs.docs]
    assert "LIA_VALIDATION_FAILED" in event_types


# --- Scope guards ---


def test_no_external_tps_calls_in_consent_service():
    text = (DISCOVERY_ROOT / "discovery_consent_service.py").read_text(encoding="utf-8")
    assert "tps" not in text.lower() or "SUPPRESSION_SOURCE_TPS" in text
    assert not re.search(r"https?://", text)
    assert "requests." not in text
    assert "httpx" not in text


def test_no_ctps_calls_in_consent_service():
    text = (DISCOVERY_ROOT / "discovery_consent_service.py").read_text(encoding="utf-8")
    assert "ctps" not in text.lower() or "SUPPRESSION_SOURCE_CTPS" in text


def test_no_notifications_in_consent_service():
    text = (DISCOVERY_ROOT / "discovery_consent_service.py").read_text(encoding="utf-8")
    assert "send_notification" not in text.lower()
    assert "notification_service" not in text.lower()


def test_no_leadservice_changes():
    assert LEAD_SERVICE_FILE.exists()
    text = LEAD_SERVICE_FILE.read_text(encoding="utf-8")
    assert "DiscoveryConsentService" not in text
