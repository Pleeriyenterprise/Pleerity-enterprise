"""
End-to-end: pipeline UNKNOWN queue row -> MARK_REQUIRED -> effective REQUIRED,
pipeline unchanged, OPERATOR_OVERRIDE source, audit, queue read-back, HIUA off
when gap reflects effective applicability (denormalised sync).
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

import pytest

from services.applicability_operator_actions import MARK_REQUIRED, execute_applicability_operator_command
from services.applicability_resolution_queue import list_applicability_resolution_queue_page
from services.hiua_operational_uncertainty import derive_hiua_signal_for_open_gap


def _gap_hiua_eligible_pre_operator() -> Dict[str, Any]:
    return {
        "client_id": "c1",
        "requirement_id": "r-e2e-1",
        "property_id": "p1",
        "status": "open",
        "gap_kind": "MISSING_EVIDENCE",
        "requirement_code": "gas_safety",
        "requirement_code_normalized": "gas_safety",
        "requirement_type": "gas_safety",
        "applicability_state": "UNKNOWN",
        "pipeline_applicability_state": "UNKNOWN",
        "effective_applicability_state": "UNKNOWN",
        "applicability_resolution_source": "PIPELINE",
        "is_mandatory": True,
        "policy_criticality": "HIGH",
        "evidence_state_normalized": "MISSING",
        "evidence_authority": {},
        "high_risk_gap": False,
        "critical_mandatory_breach": False,
    }


def _initial_requirement() -> Dict[str, Any]:
    return {
        "client_id": "c1",
        "requirement_id": "r-e2e-1",
        "property_id": "p1",
        "pipeline_applicability_state": "UNKNOWN",
        "effective_applicability_state": "UNKNOWN",
        "applicability_resolution_source": "PIPELINE",
        "applicability_state": "UNKNOWN",
        "operator_override_active": False,
        "requirement_type": "gas_safety",
        "requirement_code_normalized": "gas_safety",
        "is_mandatory": True,
        "policy_criticality": "HIGH",
        "jurisdiction": "England",
        "registry_metadata": {"k": 1},
        "applicability_provenance": {
            "pipeline_applicability_state": "UNKNOWN",
            "effective_applicability_state": "UNKNOWN",
            "applicability_resolution_source": "PIPELINE",
            "operator_override": {"active": False, "applicability_state": None},
        },
    }


def _apply_set(target: Dict[str, Any], set_fields: Dict[str, Any]) -> None:
    for k, v in set_fields.items():
        target[k] = copy.deepcopy(v)


def _sync_gaps_from_requirement(requirement: Dict[str, Any], gaps: List[Dict[str, Any]]) -> None:
    rid = str(requirement.get("requirement_id") or "")
    eff = str(requirement.get("effective_applicability_state") or "").strip().upper()
    src = str(requirement.get("applicability_resolution_source") or "").strip().upper()
    for g in gaps:
        if str(g.get("requirement_id") or "") != rid:
            continue
        g["effective_applicability_state"] = eff
        g["applicability_resolution_source"] = src
        g["applicability_state"] = eff


class _AggCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = docs

    def __aiter__(self) -> "_AggCursor":
        self._i = 0
        return self

    async def __anext__(self) -> Dict[str, Any]:
        if self._i >= len(self._docs):
            raise StopAsyncIteration
        d = self._docs[self._i]
        self._i += 1
        return d


class _GapFindCursor:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def limit(self, *_a: Any, **_k: Any) -> "_GapFindCursor":
        return self

    async def to_list(self, n: int) -> List[Dict[str, Any]]:
        return list(self._rows)[:n]


class _ReqCursor:
    def __init__(self, store: "ApplicabilityE2EStore"):
        self._store = store

    def sort(self, *_a: Any, **_k: Any) -> "_ReqCursor":
        return self

    def limit(self, *_a: Any, **_k: Any) -> "_ReqCursor":
        return self

    async def to_list(self, n: int) -> List[Dict[str, Any]]:
        return [copy.deepcopy(self._store.requirement)][:n]


class _PropCursor:
    def __init__(self, props: List[Dict[str, Any]]):
        self._props = props

    def __aiter__(self) -> "_PropCursor":
        self._i = 0
        return self

    async def __anext__(self) -> Dict[str, Any]:
        if self._i >= len(self._props):
            raise StopAsyncIteration
        p = self._props[self._i]
        self._i += 1
        return p


class ApplicabilityE2EStore:
    """Minimal in-memory persistence for requirements, gaps, and audit."""

    def __init__(self) -> None:
        self.requirement = _initial_requirement()
        self.gaps: List[Dict[str, Any]] = [_gap_hiua_eligible_pre_operator()]
        self.audit_docs: List[Dict[str, Any]] = []

    def _open_gap_group_counts(self, requirement_ids: List[str]) -> List[Dict[str, Any]]:
        out: Dict[str, int] = {}
        for g in self.gaps:
            if str(g.get("client_id")) != "c1":
                continue
            if str(g.get("status") or "").lower() != "open":
                continue
            rid = str(g.get("requirement_id") or "")
            if rid not in requirement_ids:
                continue
            out[rid] = out.get(rid, 0) + 1
        return [{"_id": k, "n": v} for k, v in sorted(out.items())]

    def build_db(self) -> Any:
        store = self

        class _Requirements:
            def __init__(self, st: "ApplicabilityE2EStore") -> None:
                self._store = st

            def find(self, flt: Dict[str, Any], projection: Any = None) -> _ReqCursor:  # noqa: ANN001
                return _ReqCursor(self._store)

            async def find_one(self, q: Dict[str, Any], projection: Any = None) -> Dict[str, Any]:  # noqa: ANN001
                if q.get("client_id") == "c1" and q.get("requirement_id") == "r-e2e-1":
                    return copy.deepcopy(self._store.requirement)
                return {}

            async def update_one(self, q: Dict[str, Any], upd: Dict[str, Any]) -> None:
                if q.get("client_id") == "c1" and q.get("requirement_id") == "r-e2e-1":
                    s = upd.get("$set") or {}
                    _apply_set(self._store.requirement, s)

        class _Properties:
            def find(self, flt: Dict[str, Any], projection: Any = None) -> _PropCursor:  # noqa: ANN001
                return _PropCursor(
                    [{"property_id": "p1", "property_type": "house", "jurisdiction": "England"}]
                )

            async def find_one(self, flt: Dict[str, Any], projection: Any = None) -> Dict[str, Any]:  # noqa: ANN001
                if flt.get("client_id") == "c1" and flt.get("property_id") == "p1":
                    return {
                        "property_id": "p1",
                        "property_type": "house",
                        "jurisdiction": "England",
                    }
                return {}

        class _Gaps:
            def aggregate(self, pipeline: List[Dict[str, Any]]) -> _AggCursor:
                match = pipeline[0].get("$match", {}) if pipeline else {}
                rids = match.get("requirement_id", {}).get("$in", [])
                if not isinstance(rids, list):
                    rids = []
                docs = store._open_gap_group_counts([str(x) for x in rids])
                return _AggCursor(docs)

            def find(self, flt: Dict[str, Any], projection: Any = None) -> _GapFindCursor:  # noqa: ANN001
                cid = str(flt.get("client_id") or "")
                rids = flt.get("requirement_id", {}).get("$in", [])
                if not isinstance(rids, list):
                    rids = []
                rset = {str(x) for x in rids}
                rows = [
                    copy.deepcopy(g)
                    for g in store.gaps
                    if str(g.get("client_id")) == cid
                    and str(g.get("requirement_id") or "") in rset
                    and str(g.get("status") or "").lower() == "open"
                ]
                return _GapFindCursor(rows)

        class _Audit:
            async def insert_one(self, doc: Dict[str, Any]) -> Any:
                store.audit_docs.append(copy.deepcopy(doc))
                class _R:
                    inserted_id = "e2e-audit"

                return _R()

        class _Db:
            def __init__(self) -> None:
                self.requirements = _Requirements(store)
                self.properties = _Properties()
                self.compliance_gaps = _Gaps()
                self.applicability_resolution_audit = _Audit()

        return _Db()


@pytest.mark.asyncio
async def test_e2e_queue_mark_required_pipeline_backlog_operator_override_hiua(monkeypatch) -> None:
    store = ApplicabilityE2EStore()

    async def _operator_gap_sync(db: Any, requirement: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        _sync_gaps_from_requirement(requirement, store.gaps)
        return {"rows": [], "errors": []}

    monkeypatch.setattr(
        "services.applicability_operator_actions.sync_compliance_gaps_for_requirement",
        _operator_gap_sync,
    )

    gap0 = store.gaps[0]
    assert derive_hiua_signal_for_open_gap(gap0) is True

    db = store.build_db()

    q1 = await list_applicability_resolution_queue_page(db, client_id="c1", limit=10, after_requirement_id=None)
    assert len(q1["items"]) == 1
    item1 = q1["items"][0]
    assert item1["pipeline_applicability_state"] == "UNKNOWN"
    assert item1["effective_applicability_state"] == "UNKNOWN"
    assert item1["priority_band"] in ("P0", "P1")
    assert item1["open_gap_count"] == 1
    assert item1["hiua_open_gap_count"] >= 1
    wiring = item1.get("operator_action_wiring") or {}
    cmds = [a["command"] for a in wiring.get("actions", [])]
    assert "MARK_REQUIRED" in cmds
    assert "REVOKE_OVERRIDE" in cmds
    assert all(a.get("resolution_reason_code_options") for a in wiring.get("actions", []))

    out = await execute_applicability_operator_command(
        db,
        client_id="c1",
        requirement_id="r-e2e-1",
        command=MARK_REQUIRED,
        resolution_reason_code="MANUAL_LEGAL_REVIEW",
        actor={"type": "user", "id": "admin-e2e", "email": "ops@example.com"},
        notes="e2e confirm",
    )
    assert out["effective_applicability_state"] == "REQUIRED"
    assert out["pipeline_applicability_state"] == "UNKNOWN"

    req_final = store.requirement
    assert req_final["pipeline_applicability_state"] == "UNKNOWN"
    assert req_final["effective_applicability_state"] == "REQUIRED"
    assert str(req_final.get("applicability_resolution_source") or "").upper() == "OPERATOR_OVERRIDE"
    assert req_final["applicability_state"] == "REQUIRED"
    assert req_final.get("operator_override_active") is True

    assert len(store.audit_docs) == 1
    aud = store.audit_docs[0]
    assert aud["event_type"] == "OPERATOR_MARK_REQUIRED"
    assert aud["pipeline_applicability_state"] == "UNKNOWN"
    assert aud["effective_applicability_state"] == "REQUIRED"
    assert str(aud.get("applicability_resolution_source") or "").upper() == "OPERATOR_OVERRIDE"
    assert aud["resolution_reason_code"] == "MANUAL_LEGAL_REVIEW"
    assert aud["requirement_id"] == "r-e2e-1"

    q2 = await list_applicability_resolution_queue_page(db, client_id="c1", limit=10, after_requirement_id=None)
    item2 = q2["items"][0]
    assert item2["pipeline_applicability_state"] == "UNKNOWN"
    assert item2["effective_applicability_state"] == "REQUIRED"
    assert str(item2.get("applicability_resolution_source") or "").upper() == "OPERATOR_OVERRIDE"
    assert item2["priority_band"] == "P1"
    assert item2["open_gap_count"] == 1
    assert item2["hiua_open_gap_count"] == 0
    assert item2["hiua_active"] is False

    assert derive_hiua_signal_for_open_gap(store.gaps[0]) is False
