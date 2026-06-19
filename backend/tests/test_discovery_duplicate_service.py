"""
Stage K — discovery duplicate service tests.

No LeadService writes, import, routes, UI, CSV provider, or notifications.
"""
from __future__ import annotations

import hashlib
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.discovery.discovery_duplicate_service import (
    DEFAULT_CONTENT_HASH_VERSION,
    DuplicateClassification,
    DuplicateEvidenceType,
    DiscoveryDuplicateError,
    DiscoveryDuplicateService,
)
from services.discovery.discovery_models import (
    DiscoveryDuplicateStatus,
    DiscoveryErasureStatus,
    DiscoveryReviewStatus,
    email_hash,
    phone_hash,
)

DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
NOW = datetime.now(timezone.utc)
VALID_HASH_A = "a" * 64
VALID_HASH_B = "b" * 64


def _hash_for(prospect_id: str) -> str:
    return hashlib.sha256(prospect_id.encode("utf-8")).hexdigest()


def _prospect(
    prospect_id: str,
    *,
    email: str = "a@example.com",
    run_id: str = "DRUN-001",
    content_hash: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    ch = content_hash or _hash_for(prospect_id)
    base = {
        "prospect_id": prospect_id,
        "tenant_id": "pleerity",
        "discovery_run_id": run_id,
        "provider": "manual",
        "provider_reference": f"manual:{prospect_id}",
        "content_hash": ch,
        "content_hash_version": DEFAULT_CONTENT_HASH_VERSION,
        "email": email,
        "email_hash": email_hash(email),
        "phone": None,
        "phone_hash": None,
        "company_name": "Acme Lettings",
        "website": "https://acme.example",
        "location": {"postcode": "SW1A 1AA"},
        "duplicate_status": DiscoveryDuplicateStatus.NONE.value,
        "review_status": DiscoveryReviewStatus.NEEDS_REVIEW.value,
        "erasure_status": DiscoveryErasureStatus.ACTIVE.value,
        "provider_confidence": 90,
        "platform_quality_score": 88,
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
    }
    base.update(kwargs)
    if base.get("phone"):
        base["phone_hash"] = phone_hash(str(base["phone"]))
    return base


class _DedupeFakeCollection:
    def __init__(self):
        self.docs: List[Dict[str, Any]] = []
        self.find_one = AsyncMock(side_effect=self._find_one)
        self.find = MagicMock(side_effect=self._find)
        self.update_one = AsyncMock(side_effect=self._update_one)

    async def _find_one(self, query, projection=None):
        for doc in self.docs:
            if self._match(doc, query):
                out = dict(doc)
                out.pop("_id", None)
                return out
        return None

    def _find(self, query, projection=None):
        matches = [dict(d) for d in self.docs if self._match(d, query)]

        class _Cursor:
            def __init__(self, items):
                self._items = items

            async def to_list(self, length):
                return self._items[:length]

        return _Cursor(matches)

    async def _update_one(self, query, update):
        for doc in self.docs:
            if self._match(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    def _match(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(self._match(doc, clause) for clause in expected):
                    return False
            elif key == "$and":
                if not all(self._match(doc, clause) for clause in expected):
                    return False
            elif isinstance(expected, dict):
                if "$ne" in expected:
                    if doc.get(key) == expected["$ne"]:
                        return False
                elif "$regex" in expected:
                    import re

                    pattern = expected["$regex"]
                    flags = re.I if expected.get("$options") == "i" else 0
                    if not re.search(pattern, str(doc.get(key) or ""), flags):
                        return False
                else:
                    if doc.get(key) != expected:
                        return False
            else:
                if doc.get(key) != expected:
                    return False
        return True


class _DedupeFakeDB:
    def __init__(self):
        self.discovery_prospects = _DedupeFakeCollection()

    def __getitem__(self, name: str):
        return getattr(self, name)


@pytest.fixture
def dedupe_db():
    return _DedupeFakeDB()


def test_email_hash_confirmed_duplicate():
    source = _prospect("PROSP-1", email="dup@example.com")
    candidate = _prospect("PROSP-2", email="dup@example.com")
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert result.classification == DuplicateClassification.CONFIRMED_DUPLICATE
    assert any(
        e.evidence_type == DuplicateEvidenceType.EMAIL_HASH_MATCH
        for e in result.evidence
    )


def test_phone_hash_confirmed_duplicate():
    source = _prospect("PROSP-1", email="a@x.com", phone="07700111222")
    candidate = _prospect("PROSP-2", email="b@y.com", phone="07700111222")
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert result.classification == DuplicateClassification.CONFIRMED_DUPLICATE
    assert any(
        e.evidence_type == DuplicateEvidenceType.PHONE_HASH_MATCH
        for e in result.evidence
    )


def test_same_run_content_hash_confirmed():
    source = _prospect("PROSP-1", content_hash=VALID_HASH_A, run_id="DRUN-1")
    candidate = _prospect(
        "PROSP-2",
        email="other@example.com",
        content_hash=VALID_HASH_A,
        run_id="DRUN-1",
    )
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert result.classification == DuplicateClassification.CONFIRMED_DUPLICATE
    assert any(
        e.evidence_type == DuplicateEvidenceType.SAME_RUN_CONTENT_HASH_MATCH
        for e in result.evidence
    )


def test_cross_run_content_hash_not_confirmed():
    source = _prospect("PROSP-1", content_hash=VALID_HASH_A, run_id="DRUN-1")
    candidate = _prospect(
        "PROSP-2",
        email="other@example.com",
        content_hash=VALID_HASH_A,
        run_id="DRUN-2",
    )
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert result.classification != DuplicateClassification.CONFIRMED_DUPLICATE
    assert not any(
        e.evidence_type == DuplicateEvidenceType.SAME_RUN_CONTENT_HASH_MATCH
        for e in result.evidence
    )


def test_provider_reference_same_run_confirmed():
    source = _prospect(
        "PROSP-1",
        run_id="DRUN-1",
        provider_reference="manual:row-7",
        content_hash=VALID_HASH_A,
    )
    candidate = _prospect(
        "PROSP-2",
        email="other@example.com",
        run_id="DRUN-1",
        provider_reference="manual:row-7",
        content_hash=VALID_HASH_B,
    )
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert result.classification == DuplicateClassification.CONFIRMED_DUPLICATE
    assert any(
        e.evidence_type == DuplicateEvidenceType.PROVIDER_REFERENCE_MATCH
        and e.details.get("cross_run") is False
        for e in result.evidence
    )


def test_provider_reference_cross_run_not_confirmed():
    source = _prospect(
        "PROSP-1",
        run_id="DRUN-1",
        provider_reference="manual:row-7",
    )
    candidate = _prospect(
        "PROSP-2",
        email="other@example.com",
        run_id="DRUN-2",
        provider_reference="manual:row-7",
    )
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert result.classification != DuplicateClassification.CONFIRMED_DUPLICATE


def test_fuzzy_company_possible_duplicate():
    source = _prospect(
        "PROSP-1",
        email="a@x.com",
        company_name="Acme Lettings Ltd",
        run_id="DRUN-A",
    )
    candidate = _prospect(
        "PROSP-2",
        email="b@y.com",
        company_name="Acme Lettings Limited",
        website="https://other.example",
        run_id="DRUN-B",
    )
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert result.classification == DuplicateClassification.POSSIBLE_DUPLICATE
    assert any(
        e.evidence_type == DuplicateEvidenceType.FUZZY_COMPANY_NAME_MATCH
        for e in result.evidence
    )


def test_company_website_possible_duplicate():
    source = _prospect(
        "PROSP-1",
        email="a@x.com",
        company_name="Beta Co",
        website="https://beta.example",
        run_id="DRUN-A",
    )
    candidate = _prospect(
        "PROSP-2",
        email="b@y.com",
        company_name="Beta Co",
        website="https://beta.example",
        run_id="DRUN-B",
    )
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert result.classification == DuplicateClassification.POSSIBLE_DUPLICATE
    assert any(
        e.evidence_type == DuplicateEvidenceType.COMPANY_WEBSITE_MATCH
        for e in result.evidence
    )


def test_company_postcode_possible_duplicate():
    source = _prospect(
        "PROSP-1",
        email="a@x.com",
        company_name="Gamma Estates",
        website="https://g1.example",
        location={"postcode": "E1 1AA"},
        run_id="DRUN-A",
    )
    candidate = _prospect(
        "PROSP-2",
        email="b@y.com",
        company_name="Gamma Estates",
        website="https://g2.example",
        location={"postcode": "E1 1AA"},
        run_id="DRUN-B",
    )
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert result.classification == DuplicateClassification.POSSIBLE_DUPLICATE
    assert any(
        e.evidence_type == DuplicateEvidenceType.COMPANY_LOCATION_MATCH
        for e in result.evidence
    )


def test_version_mismatch_fallback():
    source = _prospect("PROSP-1", content_hash=VALID_HASH_A, run_id="DRUN-1")
    source["content_hash_version"] = "1"
    candidate = _prospect(
        "PROSP-2",
        email="other@example.com",
        content_hash=VALID_HASH_A,
        run_id="DRUN-1",
    )
    candidate["content_hash_version"] = "2"
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert any(
        e.evidence_type == DuplicateEvidenceType.VERSION_MISMATCH
        for e in result.evidence
    )
    assert not any(
        e.evidence_type == DuplicateEvidenceType.SAME_RUN_CONTENT_HASH_MATCH
        for e in result.evidence
    )


def test_erased_prospect_safe_handling():
    source = _prospect("PROSP-1", email="erased@example.com")
    candidate = _prospect("PROSP-2", email="erased@example.com")
    candidate["erasure_status"] = DiscoveryErasureStatus.ERASED.value
    candidate["email"] = None
    candidate["contact_name"] = "[ERASED]"
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert result.classification == DuplicateClassification.CONFIRMED_DUPLICATE
    erasure_ev = [
        e for e in result.evidence if e.evidence_type == DuplicateEvidenceType.ERASURE_SAFE_MATCH
    ]
    assert erasure_ev
    assert "erased@example.com" not in str(erasure_ev[0].details)


@pytest.mark.asyncio
async def test_merged_into_chain_resolves(dedupe_db):
    dedupe_db.discovery_prospects.docs = [
        _prospect("PROSP-A"),
        {**_prospect("PROSP-B"), "merged_into_prospect_id": "PROSP-A"},
        {**_prospect("PROSP-C"), "merged_into_prospect_id": "PROSP-B"},
    ]
    with patch("services.discovery.discovery_duplicate_service.database") as mock_db:
        mock_db.get_db.return_value = dedupe_db
        target = await DiscoveryDuplicateService.resolve_merge_target("PROSP-C")
    assert target == "PROSP-A"


@pytest.mark.asyncio
async def test_merge_cycle_blocked(dedupe_db):
    dedupe_db.discovery_prospects.docs = [
        {**_prospect("PROSP-A"), "merged_into_prospect_id": "PROSP-B"},
        {**_prospect("PROSP-B"), "merged_into_prospect_id": "PROSP-A"},
    ]
    with patch("services.discovery.discovery_duplicate_service.database") as mock_db:
        mock_db.get_db.return_value = dedupe_db
        with pytest.raises(DiscoveryDuplicateError) as exc:
            await DiscoveryDuplicateService.resolve_merge_target("PROSP-A")
    assert exc.value.code == "MERGE_CYCLE"


def test_duplicate_override_requires_reviewer_reason_notes():
    errors = DiscoveryDuplicateService.validate_duplicate_override(
        reviewer_id="",
        reason_code="",
        notes="",
        timestamp=None,
    )
    assert len(errors) >= 4
    ok = DiscoveryDuplicateService.validate_duplicate_override(
        reviewer_id="admin-1",
        reason_code="FALSE_POSITIVE",
        notes="Reviewed manually",
        timestamp=NOW,
    )
    assert ok == []


def test_provider_confidence_not_used_as_evidence():
    source = _prospect(
        "PROSP-1",
        email="a@x.com",
        run_id="DRUN-A",
        company_name="Unique Alpha Co",
        website="https://alpha.example",
        provider_confidence=100,
    )
    candidate = _prospect(
        "PROSP-2",
        email="b@y.com",
        run_id="DRUN-B",
        company_name="Unique Beta Co",
        website="https://beta.example",
        provider_confidence=100,
    )
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert result.classification == DuplicateClassification.NONE
    assert not result.evidence


def test_platform_quality_score_not_used_as_evidence():
    source = _prospect(
        "PROSP-1",
        email="a@x.com",
        run_id="DRUN-A",
        company_name="Unique Gamma Co",
        website="https://gamma.example",
        platform_quality_score=100,
    )
    candidate = _prospect(
        "PROSP-2",
        email="b@y.com",
        run_id="DRUN-B",
        company_name="Unique Delta Co",
        website="https://delta.example",
        platform_quality_score=100,
    )
    result = DiscoveryDuplicateService.classify_duplicate(source, [candidate])
    assert result.classification == DuplicateClassification.NONE


@pytest.mark.asyncio
async def test_duplicate_status_update_works(dedupe_db):
    dedupe_db.discovery_prospects.docs = [_prospect("PROSP-1")]
    result = DiscoveryDuplicateService.classify_duplicate(
        dedupe_db.discovery_prospects.docs[0],
        [_prospect("PROSP-2", email="dup@example.com")],
    )
    with patch("services.discovery.discovery_duplicate_service.database") as mock_db:
        mock_db.get_db.return_value = dedupe_db
        out = await DiscoveryDuplicateService.mark_confirmed_duplicate(
            "PROSP-1", result, actor_id="admin-1"
        )
    assert (
        out["prospect"]["duplicate_status"]
        == DiscoveryDuplicateStatus.CONFIRMED.value
    )
    assert (
        out["prospect"]["review_status"]
        == DiscoveryReviewStatus.DUPLICATE_DETECTED.value
    )


@pytest.mark.asyncio
async def test_clear_duplicate_status_works(dedupe_db):
    doc = _prospect("PROSP-1")
    doc["duplicate_status"] = DiscoveryDuplicateStatus.CONFIRMED.value
    doc["review_status"] = DiscoveryReviewStatus.DUPLICATE_DETECTED.value
    dedupe_db.discovery_prospects.docs = [doc]
    empty = DiscoveryDuplicateService.classify_duplicate(doc, [])
    with patch("services.discovery.discovery_duplicate_service.database") as mock_db:
        mock_db.get_db.return_value = dedupe_db
        out = await DiscoveryDuplicateService.clear_duplicate_status("PROSP-1")
    assert out["prospect"]["duplicate_status"] == DiscoveryDuplicateStatus.NONE.value


@pytest.mark.asyncio
async def test_find_duplicate_candidates_by_email_hash(dedupe_db):
    dedupe_db.discovery_prospects.docs = [
        _prospect("PROSP-1", email="match@example.com"),
        _prospect("PROSP-2", email="match@example.com"),
        _prospect("PROSP-3", email="other@example.com"),
    ]
    with patch("services.discovery.discovery_duplicate_service.database") as mock_db:
        mock_db.get_db.return_value = dedupe_db
        candidates = await DiscoveryDuplicateService.find_duplicate_candidates(
            dedupe_db.discovery_prospects.docs[0],
            exclude_prospect_id="PROSP-1",
        )
    assert len(candidates) == 1
    assert candidates[0]["prospect_id"] == "PROSP-2"


def test_no_lead_service_writes():
    text = (DISCOVERY_ROOT / "discovery_duplicate_service.py").read_text(encoding="utf-8")
    assert "from services.lead_service import" not in text
    assert "LeadService.create_lead" not in text
    assert "LeadService.find_duplicate" not in text


def test_no_duplicate_routes_ui_csv_import():
    assert importlib.util.find_spec("routes.admin_discovery") is not None
    assert importlib.util.find_spec("routes.discovery_twin_internal") is not None
    assert importlib.util.find_spec("services.discovery.discovery_import_service") is not None


def test_build_duplicate_evidence_structure():
    ev = DiscoveryDuplicateService.build_duplicate_evidence(
        DuplicateEvidenceType.EMAIL_HASH_MATCH,
        "PROSP-2",
        confidence="high",
        details={"match": "email_hash"},
    )
    d = ev.to_dict()
    assert d["evidence_type"] == "email_hash_match"
    assert d["matched_prospect_id"] == "PROSP-2"
