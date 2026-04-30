"""Applicability resolution queue (internal ops)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.applicability_operator_resolution_reasons import APPLICABILITY_OPERATOR_REASON_CODES
from services.applicability_resolution_queue import (
    build_applicability_queue_operator_action_wiring,
    build_queue_mongo_filter,
    classify_applicability_unknown_root_causes,
    compute_priority_band,
    list_applicability_resolution_queue_page,
    recommended_next_action_from_root_causes,
)


def test_queue_filter_pipeline_unknown_and_high_impact():
    flt = build_queue_mongo_filter(client_id="c1")
    assert flt["client_id"] == "c1"
    assert flt["pipeline_applicability_state"] == "UNKNOWN"
    assert "$or" in flt


def test_classifier_provenance_and_jurisdiction():
    req = {
        "jurisdiction": "",
        "registry_metadata": {},
        "property_id": "p1",
    }
    codes = classify_applicability_unknown_root_causes(req, property_doc=None)
    assert "PROVENANCE_NOT_INITIALISED" in codes
    assert "MISSING_JURISDICTION" in codes
    assert "REGISTRY_METADATA_MISSING" in codes
    assert "PROPERTY_CONTEXT_UNAVAILABLE" in codes


def test_recommended_next_action_follows_root_cause_priority_not_sort_order():
    # Alphabetical classifier order would put MISSING before PROVENANCE; ops priority prefers provenance first.
    codes = sorted(["PROVENANCE_NOT_INITIALISED", "MISSING_JURISDICTION"])
    assert recommended_next_action_from_root_causes(codes).startswith("Run applicability provenance")
    assert recommended_next_action_from_root_causes(["PROPERTY_TYPE_MISSING"]).startswith("Set property_type")
    assert "Review pipeline" in recommended_next_action_from_root_causes([])


def test_mark_needs_review_appears_when_supported_by_operator_commands(monkeypatch):
    import services.applicability_resolution_queue as arq

    monkeypatch.setattr(
        arq,
        "OPERATOR_COMMANDS",
        frozenset({"MARK_REQUIRED", "MARK_NOT_REQUIRED", "MARK_NEEDS_REVIEW", "REVOKE_OVERRIDE"}),
    )
    w = arq.build_applicability_queue_operator_action_wiring(operator_override_active=False)
    cmds = [a["command"] for a in w["actions"]]
    assert cmds.index("MARK_NEEDS_REVIEW") > cmds.index("MARK_NOT_REQUIRED")
    assert "MARK_NEEDS_REVIEW" in cmds


def test_operator_action_wiring_revoke_only_when_override_active():
    w_off = build_applicability_queue_operator_action_wiring(operator_override_active=False)
    w_on = build_applicability_queue_operator_action_wiring(operator_override_active=True)
    cmds_off = [a["command"] for a in w_off["actions"]]
    cmds_on = [a["command"] for a in w_on["actions"]]
    assert "MARK_REQUIRED" in cmds_off
    assert "MARK_NOT_REQUIRED" in cmds_off
    assert "MARK_NEEDS_REVIEW" not in cmds_off
    revoke_off = next(a for a in w_off["actions"] if a["command"] == "REVOKE_OVERRIDE")
    revoke_on = next(a for a in w_on["actions"] if a["command"] == "REVOKE_OVERRIDE")
    assert revoke_off["available"] is False
    assert revoke_on["available"] is True
    for a in w_on["actions"]:
        assert a["requires_resolution_reason_code"] is True
        assert a["resolution_reason_code_options"] == sorted(APPLICABILITY_OPERATOR_REASON_CODES)
    assert w_on["applicability_operator_method"] == "POST"
    assert "{client_id}" in w_on["applicability_operator_path_template"]
    assert "{requirement_id}" in w_on["applicability_operator_path_template"]


def test_compute_priority_band_model():
    assert compute_priority_band(hiua_open_gap_count=1, open_gap_count=5, is_mandatory=True, policy_criticality="HIGH") == "P0"
    assert compute_priority_band(hiua_open_gap_count=0, open_gap_count=2, is_mandatory=True, policy_criticality="HIGH") == "P1"
    assert compute_priority_band(hiua_open_gap_count=0, open_gap_count=1, is_mandatory=False, policy_criticality="LOW") == "P2"
    assert compute_priority_band(hiua_open_gap_count=0, open_gap_count=0, is_mandatory=True, policy_criticality="CRITICAL") == "P3"


def test_classifier_property_doc_signals():
    req = {
        "jurisdiction": "England",
        "registry_metadata": {"x": 1},
        "property_id": "p1",
        "pipeline_applicability_state": "UNKNOWN",
        "effective_applicability_state": "UNKNOWN",
    }
    prop = {"property_id": "p1", "property_type": "", "jurisdiction": ""}
    codes = classify_applicability_unknown_root_causes(req, property_doc=prop)
    assert "PROPERTY_JURISDICTION_MISSING" in codes
    assert "PROPERTY_TYPE_MISSING" in codes


@pytest.mark.asyncio
async def test_list_queue_page_pagination():
    r1 = {
        "client_id": "c1",
        "requirement_id": "a",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "requirement_code_normalized": "gas_safety",
        "pipeline_applicability_state": "UNKNOWN",
        "effective_applicability_state": "UNKNOWN",
        "applicability_resolution_source": "PIPELINE",
        "jurisdiction": "England",
        "registry_metadata": {"k": 1},
        "is_mandatory": True,
        "policy_criticality": "HIGH",
    }
    r2 = dict(r1)
    r2["requirement_id"] = "b"

    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows

        def sort(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        async def to_list(self, n):
            return list(self._rows)[:n]

    class FakeReq:
        def __init__(self, rows):
            self._rows = rows
            self.filters: list = []

        def find(self, flt, projection=None):  # noqa: ANN001
            self.filters.append(flt)
            return FakeCursor(self._rows)

    class FakeProps:
        def __init__(self, props):
            self._props = props

        def find(self, flt, projection=None):  # noqa: ANN001
            return _PropCursor(self._props)

    class FakeGapsAgg:
        def __init__(self, docs):
            self._docs = docs

        def __aiter__(self):
            self._i = 0
            return self

        async def __anext__(self):
            if self._i >= len(self._docs):
                raise StopAsyncIteration
            d = self._docs[self._i]
            self._i += 1
            return d

    class FakeGaps:
        def __init__(self, agg_docs, find_rows):
            self.agg_docs = agg_docs
            self.find_rows = find_rows

        def aggregate(self, pipeline):  # noqa: ANN001
            return FakeGapsAgg(self.agg_docs)

        def find(self, flt, projection=None):  # noqa: ANN001
            return FakeCursor(self.find_rows)

    class _PropCursor:
        def __init__(self, props):
            self._props = props

        def __aiter__(self):
            self._i = 0
            return self

        async def __anext__(self):
            if self._i >= len(self._props):
                raise StopAsyncIteration
            p = self._props[self._i]
            self._i += 1
            return p

    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1"})
    db.requirements = FakeReq([r1, r2])
    db.properties = FakeProps([{"property_id": "p1", "property_type": "house", "jurisdiction": "England"}])
    db.compliance_gaps = FakeGaps(agg_docs=[{"_id": "a", "n": 2}], find_rows=[])

    out = await list_applicability_resolution_queue_page(db, client_id="c1", limit=1, after_requirement_id=None)
    assert out["has_more"] is True
    assert out["next_cursor"] == "a"
    assert len(out["items"]) == 1
    assert out["items"][0]["pipeline_applicability_state"] == "UNKNOWN"
    assert out["items"][0]["effective_applicability_state"] == "UNKNOWN"
    assert out["items"][0]["open_gap_count"] == 2
    assert out["items"][0]["priority_band"] == "P1"
    assert out["items"][0]["hiua_active"] is False
    assert "recommended_next_action" in out["items"][0]
    assert out["queue_operational_scan_truncated"] is False
    assert out["priority_band_order"] == ["P0", "P1", "P2", "P3"]
    assert "operator_action_wiring" in out["items"][0]
    assert out["items"][0]["operator_action_wiring"]["actions"]

    await list_applicability_resolution_queue_page(db, client_id="c1", limit=1, after_requirement_id="a")
    assert len(db.requirements.filters) == 2
    assert "$and" in db.requirements.filters[-1]


@pytest.mark.asyncio
async def test_queue_page_hiua_and_truncation(monkeypatch):
    import services.applicability_resolution_queue as arq

    monkeypatch.setattr(arq, "derive_hiua_signal_for_open_gap", lambda g: bool(g.get("requirement_id") == "a"))
    monkeypatch.setattr(arq, "MAX_GAP_DOCS_FOR_QUEUE_HIUA_EVAL", 2)

    r1 = {
        "client_id": "c1",
        "requirement_id": "a",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "requirement_code_normalized": "gas_safety",
        "pipeline_applicability_state": "UNKNOWN",
        "effective_applicability_state": "UNKNOWN",
        "applicability_resolution_source": "PIPELINE",
        "jurisdiction": "England",
        "registry_metadata": {"k": 1},
        "is_mandatory": True,
        "policy_criticality": "HIGH",
        "updated_at": "2024-01-02T00:00:00Z",
        "evidence_state_normalized": "MISSING",
    }

    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows

        def sort(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        async def to_list(self, n):
            return list(self._rows)[:n]

    class FakeReq:
        def __init__(self, rows):
            self._rows = rows

        def find(self, flt, projection=None):  # noqa: ANN001
            return FakeCursor(self._rows)

    class FakeProps:
        def find(self, flt, projection=None):  # noqa: ANN001
            return _EmptyPropCursor()

    class _EmptyPropCursor:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    class FakeGapsAgg:
        def __init__(self, docs):
            self._docs = docs

        def __aiter__(self):
            self._i = 0
            return self

        async def __anext__(self):
            if self._i >= len(self._docs):
                raise StopAsyncIteration
            d = self._docs[self._i]
            self._i += 1
            return d

    class FakeGaps:
        def __init__(self, agg_docs, find_rows):
            self.agg_docs = agg_docs
            self.find_rows = find_rows

        def aggregate(self, pipeline):  # noqa: ANN001
            return FakeGapsAgg(self.agg_docs)

        def find(self, flt, projection=None):  # noqa: ANN001
            return FakeCursor(self.find_rows)

    find_rows = [
        {"requirement_id": "a", "status": "open", "gap_kind": "X"},
        {"requirement_id": "a", "status": "open", "gap_kind": "Y"},
        {"requirement_id": "a", "status": "open", "gap_kind": "Z"},
    ]
    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1"})
    db.requirements = FakeReq([r1])
    db.properties = FakeProps()
    db.compliance_gaps = FakeGaps(agg_docs=[{"_id": "a", "n": 3}], find_rows=find_rows)

    out = await list_applicability_resolution_queue_page(db, client_id="c1", limit=10, after_requirement_id=None)
    assert out["items"][0]["open_gap_count"] == 3
    assert out["items"][0]["hiua_open_gap_count"] == 2
    assert out["items"][0]["hiua_active"] is True
    assert out["items"][0]["priority_band"] == "P0"
    assert out["queue_operational_scan_truncated"] is True
    assert out["items"][0]["last_updated_at"] is not None
    assert out["items"][0]["age_seconds"] is not None
    assert out["items"][0]["evidence_state"] == "MISSING"
