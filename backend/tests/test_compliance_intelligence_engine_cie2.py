"""CIE-2 recommendation + priority engine tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.compliance_graph_service.access import ActorContext
from services.compliance_intelligence_engine.constants import (
    DETERMINISTIC_VERSION,
    ENGINE_VERSION,
    PROVENANCE_ID_PREFIX,
)
from services.compliance_intelligence_engine.engines.priority.scoring import compute_priority_score
from services.compliance_intelligence_engine.engines.recommendation.templates import (
    match_gap_to_template,
    normalize_gaps,
)
from services.compliance_intelligence_engine.provenance_validation import validate_artefact_provenance_link
from services.compliance_intelligence_service import (
    explain_intelligence,
    generate_priority_assessment,
    generate_recommendations,
    get_intelligence,
    get_intelligence_provenance,
    list_intelligence,
)
from tests.test_compliance_intelligence_engine_cie1 import _tenant_actor

SAMPLE_GRAPH_ENV = {
    "insufficient_evidence": False,
    "payload": {
        "gaps": [
            {
                "decision_id": "dec_cie2_1",
                "missing": [{"code": "missing_evidence", "document_id": "doc_1"}],
            },
            {
                "decision_id": "dec_cie2_2",
                "missing": [{"code": "evidence_expired", "document_id": "doc_2"}],
            },
        ]
    },
}


class _FakeCollection:
    def __init__(self):
        self.docs: list = []
        self.find_one = AsyncMock(side_effect=self._find_one)
        self.insert_one = AsyncMock(side_effect=self._insert_one)
        self.find = MagicMock(side_effect=self._find)

    async def _insert_one(self, doc):
        self.docs.append(dict(doc))

    async def _find_one(self, query, projection=None, sort=None):
        candidates = list(reversed(self.docs))
        if sort:
            key, direction = sort[0]
            candidates = sorted(self.docs, key=lambda d: d.get(key) or "", reverse=direction < 0)
        for doc in candidates:
            if self._matches(doc, query):
                out = dict(doc)
                out.pop("_id", None)
                return out
        return None

    def _matches(self, doc, query):
        for k, v in query.items():
            if k == "lifecycle_state" and isinstance(v, dict) and "$nin" in v:
                if doc.get(k) in v["$nin"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def _find(self, query, projection=None):
        matches = [dict(d) for d in self.docs if self._matches(d, query)]

        class _Cursor:
            def __init__(self, items):
                self._items = items

            def sort(self, *args, **kwargs):
                if args:
                    if len(args) == 2 and isinstance(args[0], str):
                        key, direction = args[0], args[1]
                    else:
                        key, direction = args[0]
                    self._items = sorted(
                        self._items,
                        key=lambda d: d.get(key) or "",
                        reverse=direction < 0,
                    )
                return self

            def limit(self, n):
                self._items = self._items[:n]
                return self

            async def to_list(self, length):
                return self._items[:length]

        return _Cursor(matches)


class _FakeDB:
    def __init__(self):
        self.artefacts = _FakeCollection()
        self.provenance = _FakeCollection()

    def __getitem__(self, name: str):
        if "artefacts" in name:
            return self.artefacts
        return self.provenance


@pytest.fixture
def cie2_db():
    return _FakeDB()


@pytest.fixture
def cie2_patches(cie2_db, monkeypatch):
    monkeypatch.setenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", "enabled")
    with (
        patch(
            "services.compliance_intelligence_engine.engines.recommendation.engine.fetch_graph_envelope",
            new_callable=AsyncMock,
            return_value=SAMPLE_GRAPH_ENV,
        ),
        patch("services.compliance_intelligence_engine.storage.artefacts.database.get_db", return_value=cie2_db),
        patch("services.compliance_intelligence_engine.storage.provenance.database.get_db", return_value=cie2_db),
    ):
        yield cie2_db


# --- template matching ---


def test_match_gap_missing_evidence():
    tmpl = match_gap_to_template({"code": "missing_evidence"})
    assert tmpl is not None
    assert tmpl["recommendation_type"] == "upload_missing_document"


def test_normalize_gaps_extracts_candidates():
    gaps = normalize_gaps(SAMPLE_GRAPH_ENV)
    assert len(gaps) == 2
    assert gaps[0]["decision_id"] == "dec_cie2_1"


def test_priority_scoring_is_deterministic():
    factors = [
        {"factor_id": "regulatory_exposure", "raw_score": 95.0, "decision_ids": ["d1"], "evidence_refs": []},
        {"factor_id": "expiry_proximity", "raw_score": 30.0, "decision_ids": ["d1"], "evidence_refs": []},
        {"factor_id": "missing_evidence_criticality", "raw_score": 85.0, "decision_ids": ["d1"], "evidence_refs": []},
    ]
    score_a, _, band_a = compute_priority_score(factors=factors)
    score_b, _, band_b = compute_priority_score(factors=factors)
    assert score_a == score_b
    assert band_a == band_b
    assert 0 <= score_a <= 100


# --- recommendation engine ---


@pytest.mark.asyncio
async def test_generate_recommendations_persists_with_provenance(cie2_patches):
    result = await generate_recommendations(actor=_tenant_actor())
    assert result["engine_version"] == ENGINE_VERSION
    assert result["insufficient_evidence"] is False
    assert len(result["artefacts"]) == 2
    for artefact in result["artefacts"]:
        assert artefact["artefact_type"] == "recommendation"
        assert artefact["provenance_id"].startswith(PROVENANCE_ID_PREFIX)
        assert artefact["deterministic_version"] == DETERMINISTIC_VERSION
        assert artefact["lifecycle_state"] == "validated"
    assert len(cie2_patches.artefacts.docs) == 2
    assert len(cie2_patches.provenance.docs) == 2


@pytest.mark.asyncio
async def test_recommendation_idempotency_via_dedupe_key(cie2_patches):
    first = await generate_recommendations(actor=_tenant_actor())
    second = await generate_recommendations(actor=_tenant_actor())
    assert len(first["artefacts"]) == len(second["artefacts"])
    assert first["artefacts"][0]["artefact_id"] == second["artefacts"][0]["artefact_id"]
    assert len(cie2_patches.artefacts.docs) == 2


@pytest.mark.asyncio
async def test_provenance_artefact_linkage(cie2_patches):
    result = await generate_recommendations(actor=_tenant_actor())
    artefact = result["artefacts"][0]
    prov = next(p for p in cie2_patches.provenance.docs if p["artefact_id"] == artefact["artefact_id"])
    ok, errors = validate_artefact_provenance_link(artefact, prov)
    assert ok, errors
    assert prov["weight_set_version"] == "weights_v1.0.0"


# --- priority engine ---


@pytest.mark.asyncio
async def test_generate_priority_assessment_ranks_recommendations(cie2_patches):
    await generate_recommendations(actor=_tenant_actor())
    pri = await generate_priority_assessment(actor=_tenant_actor())
    assert pri["artefact_type"] == "priority_assessment"
    assert pri["insufficient_evidence"] is False
    assessment = pri["tier1"]
    assert assessment["items"]
    ranks = [i["priority_rank"] for i in assessment["items"]]
    assert ranks == sorted(ranks)
    scores = [i["priority_score"] for i in assessment["items"]]
    assert scores == sorted(scores, reverse=True)


# --- ISL reads ---


@pytest.mark.asyncio
async def test_list_and_get_intelligence(cie2_patches):
    gen = await generate_recommendations(actor=_tenant_actor())
    artefact_id = gen["artefacts"][0]["artefact_id"]
    listed = await list_intelligence(actor=_tenant_actor(), artefact_type="recommendation")
    assert listed["tier1"]["count"] >= 1
    fetched = await get_intelligence(artefact_id=artefact_id, actor=_tenant_actor())
    assert fetched["artefact_id"] == artefact_id
    assert fetched["artefacts"][0]["artefact_id"] == artefact_id


@pytest.mark.asyncio
async def test_explain_intelligence_deterministic(cie2_patches):
    gen = await generate_recommendations(actor=_tenant_actor())
    artefact_id = gen["artefacts"][0]["artefact_id"]
    explained = await explain_intelligence(artefact_id=artefact_id, actor=_tenant_actor())
    assert explained["tier1"]["deterministic"] is True
    assert explained["tier1"]["trace_hash"].startswith("sha256:")
    assert explained["tier1"]["weight_set_version"] == "weights_v1.0.0"


@pytest.mark.asyncio
async def test_get_intelligence_provenance_returns_record(cie2_patches):
    gen = await generate_recommendations(actor=_tenant_actor())
    artefact_id = gen["artefacts"][0]["artefact_id"]
    prov_env = await get_intelligence_provenance(artefact_id=artefact_id, actor=_tenant_actor())
    assert prov_env["provenance_id"].startswith(PROVENANCE_ID_PREFIX)
    assert prov_env["tier1"]["calculation_trace"]
