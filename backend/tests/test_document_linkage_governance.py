"""Document linkage governance — post-ingestion reconciliation states."""
from services.document_linkage_governance import (
    DocumentLinkageState,
    attach_document_linkage_projection,
    derive_document_linkage_state,
    linkage_matrix_passes_g5,
    persist_fields_for_intentionally_unlinked,
    persist_fields_for_linked_requirement,
    persist_fields_for_new_other_upload,
    suggest_requirement_ids_for_document,
)

RUNTIME = {"r-active", "r-other"}


def test_intentionally_unlinked_persisted_not_orphan():
    doc = {
        "document_id": "d1",
        "evidence_scope_type": "PROPERTY",
        "document_linkage_state": DocumentLinkageState.INTENTIONALLY_UNLINKED.value,
    }
    assert derive_document_linkage_state(doc, runtime_requirement_ids=RUNTIME) == DocumentLinkageState.INTENTIONALLY_UNLINKED.value
    ok, kind = linkage_matrix_passes_g5(doc, runtime_requirement_ids=RUNTIME)
    assert ok is True
    assert kind is None


def test_reconciliation_required_when_unlinked_without_intent():
    doc = {
        "document_id": "d2",
        "evidence_scope_type": "PROPERTY",
        "requirement_id": None,
    }
    assert derive_document_linkage_state(doc, runtime_requirement_ids=RUNTIME) == DocumentLinkageState.RECONCILIATION_REQUIRED.value
    ok, kind = linkage_matrix_passes_g5(doc, runtime_requirement_ids=RUNTIME)
    assert ok is False
    assert kind == "RECONCILIATION_REQUIRED"


def test_broken_linkage_when_stale_requirement():
    doc = {
        "document_id": "d3",
        "evidence_scope_type": "PROPERTY",
        "requirement_id": "r-stale",
    }
    assert derive_document_linkage_state(doc, runtime_requirement_ids=RUNTIME) == DocumentLinkageState.BROKEN_LINKAGE.value
    ok, kind = linkage_matrix_passes_g5(doc, runtime_requirement_ids=RUNTIME)
    assert ok is False
    assert kind == "BROKEN_LINKAGE"


def test_linked_when_requirement_in_runtime_set():
    doc = {
        "document_id": "d4",
        "evidence_scope_type": "PROPERTY",
        "requirement_id": "r-active",
        "evidence_review_state": "UPLOADED",
    }
    assert derive_document_linkage_state(doc, runtime_requirement_ids=RUNTIME) == DocumentLinkageState.LINKED.value


def test_other_upload_sets_intentional_fields():
    fields = persist_fields_for_new_other_upload()
    assert fields["document_linkage_state"] == DocumentLinkageState.INTENTIONALLY_UNLINKED.value
    assert fields["linkage_intent"] == "INTENTIONAL"


def test_manual_link_persist_fields():
    fields = persist_fields_for_linked_requirement(
        "r-active",
        actor_user_id="u1",
        reason="G5 reconcile",
        prior_requirement_id="r-stale",
    )
    assert fields["requirement_id"] == "r-active"
    assert fields["document_linkage_state"] == DocumentLinkageState.LINKED.value
    assert fields["linkage_reconciliation_action"] == "link_requirement"


def test_intentional_unlink_clears_requirement():
    fields = persist_fields_for_intentionally_unlinked(actor_user_id="u1", reason="misc file")
    assert fields["requirement_id"] is None
    assert fields["document_linkage_state"] == DocumentLinkageState.INTENTIONALLY_UNLINKED.value


def test_projection_surfaces_reconciliation_required():
    doc = {"document_id": "d5", "evidence_scope_type": "PROPERTY"}
    attach_document_linkage_projection(doc, runtime_requirement_ids=RUNTIME, runtime_requirements=[])
    assert doc["linkage_reconciliation_required"] is True
    assert doc["document_linkage_state"] == DocumentLinkageState.RECONCILIATION_REQUIRED.value


def test_suggested_requirements_for_action_required():
    doc = {"property_id": "p1", "document_type": "EPC"}
    reqs = [
        {"requirement_id": "r-epc", "property_id": "p1", "requirement_type": "epc", "client_lifecycle_state": "ACTION_REQUIRED", "allowed_evidence_modes": ["DOCUMENT_UPLOAD"]},
        {"requirement_id": "r-gas", "property_id": "p1", "requirement_type": "gas_safety", "client_lifecycle_state": "VERIFIED", "allowed_evidence_modes": ["DOCUMENT_UPLOAD"]},
    ]
    suggested = suggest_requirement_ids_for_document(doc, reqs)
    assert "r-epc" in suggested


def test_upload_not_equal_verified_preserved_in_link_fields():
    fields = persist_fields_for_linked_requirement("r-active", actor_user_id="u1")
    assert "EVIDENCE_VERIFIED" not in str(fields.values())
