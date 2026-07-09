"""CIE-1.5 provenance foundation tests."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.compliance_graph_service.access import ActorContext
from services.compliance_intelligence_engine.constants import (
    COLLECTION_CONSTRAINT_REGISTRY,
    COLLECTION_PROVENANCE,
    COLLECTION_STRATEGY_REGISTRY,
    COLLECTION_WEIGHT_REGISTRY,
    ENGINE_VERSION,
    PROVENANCE_ID_PREFIX,
)
from services.compliance_intelligence_engine.registry.versions import CONSTRAINT_SET_V1, WEIGHT_SET_V1
from services.compliance_intelligence_engine.hashing import provenance_record_hash, trace_hash
from services.compliance_intelligence_engine.provenance_schema import IntelligenceProvenanceBase
from services.compliance_intelligence_engine.provenance_trace import build_stub_trace, compute_trace_hash_from_stages
from services.compliance_intelligence_engine.provenance_validation import (
    validate_all_registry_seeds_v1,
    validate_artefact_provenance_link,
    validate_artefact_requires_provenance_id,
    validate_provenance_dict,
)
from services.compliance_intelligence_engine.registry import constraints as constraint_registry
from services.compliance_intelligence_engine.registry import strategies as strategy_registry
from services.compliance_intelligence_engine.registry import weights as weight_registry
from services.compliance_intelligence_engine.registry.seeds_v1 import (
    all_registry_seeds_v1,
    constraint_seed_v1,
    strategy_seed_v1,
    weight_seed_v1,
)
from services.compliance_intelligence_engine.registry.versions import REC_STRATEGY_V1
from services.compliance_intelligence_engine.replay import dispatch_replay
from services.compliance_intelligence_engine.comparison import dispatch_compare
from services.compliance_intelligence_engine.storage import provenance as provenance_storage
from services.compliance_intelligence_service import (
    compare_intelligence,
    get_intelligence_provenance,
    replay_intelligence,
)
from tests.test_compliance_intelligence_engine_cie1 import _sample_artefact_dict, _sample_scope, _tenant_actor


def _sample_provenance_dict(*, artefact_id: str = "cia_sample", provenance_id: str = "cip_sample") -> dict:
    scope = _sample_scope()
    artefact = _sample_artefact_dict()
    artefact["artefact_id"] = artefact_id
    artefact["provenance_id"] = provenance_id
    artefact["response_hash"] = artefact.get("response_hash")
    trace = build_stub_trace(inputs_hash=artefact["inputs_hash"])
    th = compute_trace_hash_from_stages(trace)
    prov = {
        "provenance_id": provenance_id,
        "artefact_id": artefact_id,
        "artefact_type": "recommendation",
        "client_id": "client-cie1",
        "inputs_hash": artefact["inputs_hash"],
        "response_hash": artefact["response_hash"],
        "trace_hash": th,
        "constraint_set_version": CONSTRAINT_SET_V1,
        "weight_set_version": WEIGHT_SET_V1,
        "recommendation_strategy_version": REC_STRATEGY_V1,
        "calculation_trace": trace,
        "scope": scope,
        "insufficient_evidence": True,
    }
    return prov, artefact


# --- provenance schema ---


def test_provenance_schema_validates_sample():
    prov, _ = _sample_provenance_dict()
    model = IntelligenceProvenanceBase.model_validate(prov)
    assert model.constraint_set_version == CONSTRAINT_SET_V1
    assert model.engine_version == ENGINE_VERSION


def test_provenance_schema_requires_trace_hash_prefix():
    prov, _ = _sample_provenance_dict()
    prov["trace_hash"] = "bad"
    with pytest.raises(Exception):
        IntelligenceProvenanceBase.model_validate(prov)


def test_validate_provenance_dict_helper():
    prov, _ = _sample_provenance_dict()
    ok, errors = validate_provenance_dict(prov)
    assert ok and errors == []


def test_artefact_requires_provenance_id():
    data = _sample_artefact_dict()
    del data["provenance_id"]
    ok, errors = validate_artefact_requires_provenance_id(data)
    assert not ok
    assert "provenance_id_required" in errors


def test_artefact_provenance_link_validates():
    prov, artefact = _sample_provenance_dict()
    artefact["response_hash"] = artefact.get("response_hash")
    ok, errors = validate_artefact_provenance_link(artefact, prov)
    assert ok and errors == []


def test_artefact_provenance_link_rejects_hash_mismatch():
    prov, artefact = _sample_provenance_dict()
    artefact["inputs_hash"] = "sha256:deadbeef"
    ok, errors = validate_artefact_provenance_link(artefact, prov)
    assert not ok
    assert "inputs_hash_mismatch" in errors


# --- hashing ---


def test_trace_hash_deterministic():
    prov, _ = _sample_provenance_dict()
    h1 = trace_hash(prov["calculation_trace"])
    h2 = trace_hash(prov["calculation_trace"])
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_provenance_record_hash_excludes_identity_fields():
    prov, _ = _sample_provenance_dict()
    h = provenance_record_hash(prov)
    assert h.startswith("sha256:")


# --- registry seeds ---


def test_registry_v1_strategy_seeds_validate():
    for seed in strategy_seed_v1():
        assert seed["content_hash"].startswith("sha256:")
        assert seed["strategy_id"]


def test_registry_v1_weight_seed_validates():
    seed = weight_seed_v1()
    assert seed["weight_set_id"] == WEIGHT_SET_V1
    assert abs(sum(seed["weights"].values()) - 1.0) < 0.001


def test_registry_v1_constraint_seed_validates():
    seed = constraint_seed_v1()
    assert seed["constraint_set_id"] == CONSTRAINT_SET_V1


def test_all_registry_seeds_v1_bundle():
    ok, errors = validate_all_registry_seeds_v1()
    assert ok, errors
    bundle = all_registry_seeds_v1()
    assert len(bundle["strategies"]) == 4


# --- immutability stubs ---


@pytest.mark.asyncio
async def test_provenance_storage_insert_requires_dict():
    with pytest.raises(TypeError):
        await provenance_storage.insert_provenance(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_provenance_storage_update_forbidden():
    with pytest.raises(NotImplementedError, match="immutable"):
        await provenance_storage.update_provenance(None, "cip_x", {})


@pytest.mark.asyncio
async def test_strategy_registry_update_forbidden():
    with pytest.raises(NotImplementedError, match="immutable"):
        await strategy_registry.update_strategy_version(None, "rec_strategy_v1.0.0", {})


@pytest.mark.asyncio
async def test_weight_registry_update_forbidden():
    with pytest.raises(NotImplementedError, match="immutable"):
        await weight_registry.update_weight_set(None, WEIGHT_SET_V1, {})


@pytest.mark.asyncio
async def test_constraint_registry_update_forbidden():
    with pytest.raises(NotImplementedError, match="immutable"):
        await constraint_registry.update_constraint_set(None, CONSTRAINT_SET_V1, {})


def test_collection_names():
    assert provenance_storage.collection_name() == COLLECTION_PROVENANCE
    assert strategy_registry.collection_name() == COLLECTION_STRATEGY_REGISTRY
    assert weight_registry.collection_name() == COLLECTION_WEIGHT_REGISTRY
    assert constraint_registry.collection_name() == COLLECTION_CONSTRAINT_REGISTRY


def test_provenance_id_prefix_constant():
    assert PROVENANCE_ID_PREFIX == "cip_"


# --- replay stubs ---


@pytest.mark.asyncio
async def test_replay_stub_disabled(monkeypatch):
    monkeypatch.delenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", raising=False)
    result = await dispatch_replay(replay_type="exact", provenance_id="cip_test")
    assert result["enabled"] is False
    assert result["reason"] == "COMPLIANCE_INTELLIGENCE_ENGINE_MODE_DISABLED"
    assert result["requires_historical_inputs"] is True
    assert result["prohibits_current_state_substitution"] is True
    assert result["response_hash"].startswith("sha256:")


@pytest.mark.asyncio
async def test_replay_stub_requires_provenance_for_exact(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", "enabled")
    result = await dispatch_replay(replay_type="exact", provenance_id=None)
    assert result["reason"] == "CIE_REPLAY_PROVENANCE_ID_REQUIRED"


@pytest.mark.asyncio
async def test_replay_stub_requires_as_of_for_point_in_time(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", "enabled")
    result = await dispatch_replay(replay_type="point_in_time", as_of=None)
    assert result["reason"] == "CIE_REPLAY_AS_OF_REQUIRED"


@pytest.mark.asyncio
async def test_isl_replay_stub(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", "enabled")
    result = await replay_intelligence(
        actor=_tenant_actor(),
        replay_type="exact",
        provenance_id="cip_gate",
        as_of="2026-06-17T00:00:00Z",
    )
    assert result["reason"] == "CIE_PROVENANCE_REPLAY_NOT_IMPLEMENTED"


# --- comparison stubs ---


@pytest.mark.asyncio
async def test_compare_stub_enabled(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", "enabled")
    result = await dispatch_compare(left_id="cia_a", right_id="cia_b")
    assert result["reason"] == "CIE_PROVENANCE_COMPARE_NOT_IMPLEMENTED"
    assert result["requires_provenance_references"] is True
    assert result["prohibits_current_state_substitution"] is True
    assert result["response_hash"].startswith("sha256:")


@pytest.mark.asyncio
async def test_isl_compare_stub(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", "enabled")
    result = await compare_intelligence(left_id="cia_a", right_id="cia_b", actor=_tenant_actor())
    assert result["reason"] == "CIE_PROVENANCE_COMPARE_NOT_IMPLEMENTED"


@pytest.mark.asyncio
async def test_get_intelligence_provenance_not_found_when_missing(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", "enabled")
    db = MagicMock()
    col = MagicMock()
    col.find_one = AsyncMock(return_value=None)
    db.__getitem__ = MagicMock(return_value=col)
    with patch("services.compliance_intelligence_engine.storage.artefacts.database.get_db", return_value=db):
        result = await get_intelligence_provenance(artefact_id="cia_x", actor=_tenant_actor())
    assert result["reason"] == "ARTEFACT_NOT_FOUND"
