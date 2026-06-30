"""DOCUMENT-LINKAGE-LIFECYCLE-AUTHORITY-01 regression tests."""
from __future__ import annotations

import pytest

from services.document_linkage_lifecycle_authority import (
    AUTHORITY_ID,
    AUTO_RESOLVE_GAP_KINDS,
    RESOLUTION_SOURCE_GAP_RESOLVED,
    RESOLUTION_SOURCE_REQUIREMENT_LINKED,
    document_linkage_exception_resolved,
    gap_kind_from_issue,
    is_open_issue_status,
    is_terminal_issue_status,
    issue_eligible_for_linkage_auto_resolve,
    resolution_note_for_source,
)
from services.compliance_gap_engine import stable_gap_key


class TestDocumentLinkageLifecycleAuthority:
    def test_linkage_exception_resolved_when_linked(self):
        doc = {"document_id": "d1", "requirement_id": "r1", "document_linkage_state": "LINKED"}
        assert document_linkage_exception_resolved(doc, runtime_requirement_ids=["r1"]) is True

    def test_linkage_exception_not_resolved_when_reconciliation_required(self):
        doc = {"document_id": "d1", "requirement_id": None, "document_linkage_state": "RECONCILIATION_REQUIRED"}
        assert document_linkage_exception_resolved(doc, runtime_requirement_ids=["r1"]) is False

    def test_issue_eligible_for_auto_resolve_mismatched_evidence(self):
        issue = {
            "status": "triaged",
            "created_from": "compliance",
            "triggering_rule": "compliance_gap:MISMATCHED_EVIDENCE",
            "operational_root_key": "c:p:r1:MISMATCHED_EVIDENCE",
        }
        assert issue_eligible_for_linkage_auto_resolve(issue) is True

    def test_terminal_issue_not_eligible(self):
        issue = {
            "status": "resolved",
            "created_from": "compliance",
            "triggering_rule": "compliance_gap:MISMATCHED_EVIDENCE",
        }
        assert issue_eligible_for_linkage_auto_resolve(issue) is False

    def test_manual_issue_not_eligible(self):
        issue = {"status": "triaged", "created_from": "manual", "description": "Leaking tap"}
        assert issue_eligible_for_linkage_auto_resolve(issue) is False

    def test_gap_kind_from_issue(self):
        assert gap_kind_from_issue({"triggering_rule": "compliance_gap:MISMATCHED_EVIDENCE"}) == "MISMATCHED_EVIDENCE"

    def test_resolution_note_requirement_linked(self):
        note = resolution_note_for_source(
            RESOLUTION_SOURCE_REQUIREMENT_LINKED,
            requirement_id="r1",
            document_id="d1",
        )
        assert "linked to requirement" in note
        assert "r1" in note

    def test_resolution_note_gap_resolved(self):
        note = resolution_note_for_source(RESOLUTION_SOURCE_GAP_RESOLVED, gap_kind="MISMATCHED_EVIDENCE")
        assert "MISMATCHED_EVIDENCE" in note

    def test_open_and_terminal_status_helpers(self):
        assert is_terminal_issue_status("resolved") is True
        assert is_open_issue_status("triaged") is True
        assert is_open_issue_status("resolved") is False

    def test_stable_gap_key_format(self):
        gk = stable_gap_key("c1", "p1", "r1", "MISMATCHED_EVIDENCE")
        assert gk == "c1:p1:r1:MISMATCHED_EVIDENCE"
        assert "MISMATCHED_EVIDENCE" in AUTO_RESOLVE_GAP_KINDS


@pytest.mark.asyncio
async def test_auto_resolve_issues_by_operational_root_keys(monkeypatch):
    from services import maintenance_issues_service as mis

    updates = []

    class FakeCol:
        def find(self, q, proj):
            return self

        async def to_list(self, n):
            return [
                {
                    "issue_id": "iss-1",
                    "status": "triaged",
                    "operational_root_key": "c:p:r:MISMATCHED_EVIDENCE",
                    "risk_signal_id": None,
                }
            ]

        async def update_one(self, q, u):
            updates.append(u)
            return type("R", (), {"modified_count": 1})()

    class FakeDb:
        maintenance_issues = FakeCol()

    monkeypatch.setattr(mis, "database", type("D", (), {"get_db": staticmethod(lambda: FakeDb())})())

    async def noop_audit(*a, **k):
        return None

    async def noop_p2(*a, **k):
        return None

    monkeypatch.setattr("utils.audit.create_audit_log", noop_audit)
    monkeypatch.setattr(
        "services.compliance_evidence_graph.producers.ceg_dispatch.try_dispatch_p2",
        noop_p2,
    )

    resolved = await mis.auto_resolve_issues_by_operational_root_keys(
        "c",
        ["c:p:r:MISMATCHED_EVIDENCE"],
        resolution_note="test",
        resolution_source=RESOLUTION_SOURCE_GAP_RESOLVED,
        resolution_authority=AUTHORITY_ID,
        resolution_metadata={"requirement_id": "r", "document_id": "d"},
    )
    assert resolved == ["iss-1"]
    assert updates[0]["$set"]["status"] == "resolved"
    assert updates[0]["$set"]["auto_resolved"] is True
    assert updates[0]["$set"]["resolution_linked_requirement_id"] == "r"
