"""CIE-1 foundation tests — hashing, flags, schema, lifecycle, envelopes, ISL stubs."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch

from services.compliance_graph_service.access import ActorContext
from services.compliance_intelligence_engine.artefact_types import ALL_ARTEFACT_TYPES, is_registered_artefact_type
from services.compliance_intelligence_engine.config import (
    intelligence_engine_enabled,
    intelligence_engine_mode,
    intelligence_engine_operational_effects,
    intelligence_engine_shadow_validation,
)
from services.compliance_intelligence_engine.constants import (
    COLLECTION_ARTEFACTS,
    COLLECTION_TRANSITIONS,
    DETERMINISTIC_VERSION,
    ENGINE_VERSION,
    TEMPLATE_VERSION_DEFAULT,
)
from services.compliance_intelligence_engine.hashing import (
    artefact_response_hash,
    canonical_json,
    envelope_hash,
    inputs_hash,
    sha256_digest,
)
from services.compliance_intelligence_engine.lifecycle import (
    BASE_LIFECYCLE_STATES,
    LIFECYCLE_GENERATED,
    LIFECYCLE_PUBLISHED,
    validate_transition,
)
from services.compliance_intelligence_engine.orchestrator import dispatch_generate
from services.compliance_intelligence_engine.schema import IntelligenceArtefactBase, IntelligenceScope
from services.compliance_intelligence_engine.storage import artefacts as artefact_storage
from services.compliance_intelligence_engine.storage import transitions as transition_storage
from services.compliance_intelligence_engine.validation import validate_artefact_dict, validate_transition_dict
from services.compliance_intelligence_service import (
    generate_intelligence,
    generate_recommendations,
    get_intelligence,
)
from services.compliance_intelligence_service.access import enforce_tenant_access, resolve_client_id
from services.compliance_intelligence_service.envelopes import build_envelope, not_implemented_envelope, unavailable_envelope


def _sample_scope() -> dict:
    return {
        "client_id": "client-cie1",
        "property_id": None,
        "requirement_id": None,
        "portfolio_root": True,
        "as_of": None,
    }


def _sample_artefact_dict(*, insufficient: bool = True) -> dict:
    scope = _sample_scope()
    ih = inputs_hash(
        artefact_type="recommendation",
        scope=scope,
        source_decision_ids=[],
        source_snapshot_ids=[],
        template_version=TEMPLATE_VERSION_DEFAULT,
        deterministic_version=DETERMINISTIC_VERSION,
        engine_version=ENGINE_VERSION,
    )
    body = {
        "artefact_type": "recommendation",
        "provenance_id": "cip_sample_cie1",
        "client_id": "client-cie1",
        "scope": scope,
        "inputs_hash": ih,
        "insufficient_evidence": insufficient,
        "payload": {},
    }
    body["response_hash"] = artefact_response_hash(body)
    return body


def _tenant_actor() -> ActorContext:
    return ActorContext(is_admin=False, client_id="client-cie1")


# --- hashing ---


def test_sha256_digest_is_deterministic():
    payload = {"b": 2, "a": 1}
    assert sha256_digest(payload) == sha256_digest(payload)
    assert sha256_digest(payload).startswith("sha256:")


def test_canonical_json_sorts_keys():
    assert canonical_json({"z": 1, "a": 2}) == '{"a":2,"z":1}'


def test_inputs_hash_stable_across_source_order():
    scope = _sample_scope()
    kwargs = dict(
        artefact_type="recommendation",
        scope=scope,
        template_version=TEMPLATE_VERSION_DEFAULT,
        deterministic_version=DETERMINISTIC_VERSION,
        engine_version=ENGINE_VERSION,
    )
    h1 = inputs_hash(source_decision_ids=["d2", "d1"], source_snapshot_ids=["s2", "s1"], **kwargs)
    h2 = inputs_hash(source_decision_ids=["d1", "d2"], source_snapshot_ids=["s1", "s2"], **kwargs)
    assert h1 == h2


def test_envelope_hash_excludes_response_hash_field():
    env = build_envelope(service="test", enabled=False, insufficient_evidence=True)
    assert env["response_hash"].startswith("sha256:")
    copy = dict(env)
    del copy["response_hash"]
    assert envelope_hash(copy) == env["response_hash"]


# --- feature flags ---


def test_intelligence_engine_mode_defaults_disabled(monkeypatch):
    monkeypatch.delenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", raising=False)
    assert intelligence_engine_mode() == "disabled"
    assert not intelligence_engine_enabled()
    assert not intelligence_engine_operational_effects()
    assert not intelligence_engine_shadow_validation()


def test_intelligence_engine_mode_invalid_falls_back_to_disabled(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", "bogus")
    assert intelligence_engine_mode() == "disabled"


@pytest.mark.parametrize(
    "mode,enabled,operational,shadow",
    [
        ("disabled", False, False, False),
        ("shadow", True, False, True),
        ("enabled", True, True, False),
    ],
)
def test_intelligence_engine_mode_matrix(monkeypatch, mode, enabled, operational, shadow):
    monkeypatch.setenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", mode)
    assert intelligence_engine_enabled() is enabled
    assert intelligence_engine_operational_effects() is operational
    assert intelligence_engine_shadow_validation() is shadow


# --- artefact types ---


def test_artefact_type_registry_count():
    assert len(ALL_ARTEFACT_TYPES) == 15


def test_artefact_type_registry_membership():
    assert is_registered_artefact_type("recommendation")
    assert not is_registered_artefact_type("unknown_type")


# --- lifecycle ---


def test_lifecycle_base_states():
    assert LIFECYCLE_GENERATED in BASE_LIFECYCLE_STATES
    assert validate_transition(LIFECYCLE_GENERATED, LIFECYCLE_PUBLISHED) == (True, "ok")
    assert validate_transition(LIFECYCLE_PUBLISHED, LIFECYCLE_GENERATED)[0] is False


# --- artefact schema ---


def test_artefact_schema_validates_sample():
    data = _sample_artefact_dict()
    artefact = IntelligenceArtefactBase.model_validate(data)
    assert artefact.artefact_type == "recommendation"
    assert artefact.engine_version == ENGINE_VERSION


def test_artefact_schema_rejects_bad_hash():
    data = _sample_artefact_dict()
    data["inputs_hash"] = "bad"
    with pytest.raises(Exception):
        IntelligenceArtefactBase.model_validate(data)


def test_artefact_schema_rejects_missing_provenance_id():
    data = _sample_artefact_dict()
    del data["provenance_id"]
    with pytest.raises(Exception):
        IntelligenceArtefactBase.model_validate(data)


def test_validate_artefact_dict_helper():
    ok, errors = validate_artefact_dict(_sample_artefact_dict(insufficient=True))
    assert ok and errors == []


def test_validate_transition_dict_helper():
    data = {
        "artefact_id": "cia_test",
        "artefact_type": "recommendation",
        "from_state": "generated",
        "to_state": "published",
        "reason_code": "test",
        "client_id": "client-cie1",
    }
    ok, errors = validate_transition_dict(data)
    assert ok and errors == []


# --- response envelopes ---


def test_unavailable_envelope_shape():
    env = unavailable_envelope("generate_recommendations", artefact_type="recommendation")
    assert env["enabled"] is False
    assert env["reason"] == "COMPLIANCE_INTELLIGENCE_ENGINE_MODE_DISABLED"
    assert env["insufficient_evidence"] is True
    assert env["artefacts"] == []


def test_not_implemented_envelope_shape():
    env = not_implemented_envelope("generate_recommendations", artefact_type="recommendation")
    assert env["enabled"] is True
    assert env["reason"] == "CIE_DOMAIN_ENGINE_NOT_IMPLEMENTED"


# --- storage stubs ---


@pytest.mark.asyncio
async def test_artefact_storage_insert_requires_dict():
    with pytest.raises(TypeError):
        await artefact_storage.insert_artefact(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_transition_storage_insert_requires_dict():
    with pytest.raises(TypeError):
        await transition_storage.insert_transition(None)  # type: ignore[arg-type]


def test_collection_names():
    assert artefact_storage.collection_name() == COLLECTION_ARTEFACTS
    assert transition_storage.collection_name() == COLLECTION_TRANSITIONS


# --- ISL access ---


def test_resolve_client_id_tenant():
    assert resolve_client_id(_tenant_actor(), None) == "client-cie1"


def test_enforce_tenant_access_denies_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        enforce_tenant_access(_tenant_actor(), client_id="other-client")
    assert exc.value.status_code == 403


# --- ISL stub dispatch ---


@pytest.mark.asyncio
async def test_isl_returns_unavailable_when_disabled(monkeypatch):
    monkeypatch.delenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", raising=False)
    result = await generate_recommendations(actor=_tenant_actor())
    assert result["enabled"] is False
    assert result["reason"] == "COMPLIANCE_INTELLIGENCE_ENGINE_MODE_DISABLED"
    assert result["response_hash"].startswith("sha256:")


@pytest.mark.asyncio
async def test_isl_generates_recommendations_when_enabled(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", "enabled")
    graph_env = {
        "insufficient_evidence": False,
        "payload": {
            "gaps": [
                {
                    "decision_id": "dec_cie2_1",
                    "missing": [{"code": "missing_evidence", "document_id": "doc_1"}],
                }
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
            for doc in reversed(self.docs):
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

    artefacts = _FakeCollection()
    provenance = _FakeCollection()
    db = MagicMock()
    db.__getitem__ = MagicMock(side_effect=lambda name: artefacts if "artefacts" in name else provenance)

    with (
        patch(
            "services.compliance_intelligence_engine.engines.recommendation.engine.fetch_graph_envelope",
            new_callable=AsyncMock,
            return_value=graph_env,
        ),
        patch("services.compliance_intelligence_engine.storage.artefacts.database.get_db", return_value=db),
        patch("services.compliance_intelligence_engine.storage.provenance.database.get_db", return_value=db),
    ):
        result = await generate_recommendations(actor=_tenant_actor())
    assert result["enabled"] is True
    assert result["insufficient_evidence"] is False
    assert len(result["artefacts"]) == 1
    assert result["artefacts"][0]["artefact_type"] == "recommendation"
    assert result["artefacts"][0]["provenance_id"].startswith("cip_")
    assert result["response_hash"].startswith("sha256:")


@pytest.mark.asyncio
async def test_orchestrator_dispatch_disabled(monkeypatch):
    monkeypatch.delenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", raising=False)
    scope = IntelligenceScope(client_id="client-cie1")
    result = await dispatch_generate(service="generate_intelligence", artefact_type="recommendation", scope=scope)
    assert result["enabled"] is False


@pytest.mark.asyncio
async def test_generate_intelligence_stub(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", "enabled")
    result = await generate_intelligence(
        artefact_type="portfolio_insight",
        actor=_tenant_actor(),
    )
    assert result["artefact_type"] == "portfolio_insight"
    assert result["reason"] == "CIE_DOMAIN_ENGINE_NOT_IMPLEMENTED"


@pytest.mark.asyncio
async def test_get_intelligence_stub_disabled(monkeypatch):
    monkeypatch.delenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", raising=False)
    result = await get_intelligence(artefact_id="cia_x", actor=_tenant_actor())
    assert result["enabled"] is False
