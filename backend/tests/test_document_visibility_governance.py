"""Document client visibility governance — operational queue vs evidence registry."""
from datetime import date, timedelta

from services.document_linkage_governance import DocumentLinkageState
from services.document_operational_state import DocumentOperationalState
from services.document_visibility_governance import (
    DocumentClientVisibilityState,
    DocumentRegistrySection,
    attach_document_visibility_projection,
    derive_document_visibility_projection,
    filter_documents_by_visibility,
    get_document_expiry_resurface_days,
    group_documents_by_registry_section,
)


def _base_doc(**overrides):
    doc = {
        "document_id": "d1",
        "evidence_scope_type": "PROPERTY",
        "requirement_id": "r1",
        "document_linkage_state": DocumentLinkageState.LINKED.value,
        "document_operational_state": DocumentOperationalState.EVIDENCE_VERIFIED.value,
        "evidence_review_state": "VERIFIED",
        "status": "VERIFIED",
    }
    doc.update(overrides)
    return doc


def test_intentionally_unlinked_is_operational_attachment():
    doc = _base_doc(
        requirement_id=None,
        document_linkage_state=DocumentLinkageState.INTENTIONALLY_UNLINKED.value,
    )
    out = derive_document_visibility_projection(doc)
    assert out["document_client_visibility_state"] == DocumentClientVisibilityState.OPERATIONAL_ATTACHMENT.value
    assert out["document_attention_required"] is False
    assert out["document_registry_section"] == DocumentRegistrySection.OPERATIONAL_ATTACHMENTS.value


def test_reconciliation_required_is_attention():
    doc = _base_doc(
        requirement_id=None,
        document_linkage_state=DocumentLinkageState.RECONCILIATION_REQUIRED.value,
        linkage_reconciliation_required=True,
        document_operational_state=DocumentOperationalState.UPLOADED_AWAITING_REVIEW.value,
    )
    out = derive_document_visibility_projection(doc)
    assert out["document_client_visibility_state"] == DocumentClientVisibilityState.ATTENTION_REQUIRED.value
    assert out["document_registry_section"] == DocumentRegistrySection.RECONCILIATION_REQUIRED.value


def test_settled_linked_evidence_is_active():
    doc = _base_doc()
    out = derive_document_visibility_projection(doc, primary_document_ids={"d1"})
    assert out["document_client_visibility_state"] == DocumentClientVisibilityState.ACTIVE_EVIDENCE.value
    assert out["document_attention_required"] is False


def test_expiry_resurface_promotes_to_attention():
    soon = (date.today() + timedelta(days=30)).isoformat()
    doc = _base_doc(expiry_date=soon)
    req = {"requirement_id": "r1", "confirmed_expiry_date": soon}
    out = derive_document_visibility_projection(doc, requirement=req, resurface_days=90, primary_document_ids={"d1"})
    assert out["document_client_visibility_state"] == DocumentClientVisibilityState.ATTENTION_REQUIRED.value
    assert out["document_expiry_resurface"] is True
    assert out["document_registry_section"] == DocumentRegistrySection.EXPIRING_SOON.value


def test_superseded_non_primary_is_historical():
    doc = _base_doc(
        document_id="d-old",
        document_operational_state=DocumentOperationalState.EVIDENCE_SUPERSEDED.value,
    )
    out = derive_document_visibility_projection(doc, primary_document_ids={"d-new"})
    assert out["document_client_visibility_state"] == DocumentClientVisibilityState.HISTORICAL_OR_SUPERSEDED.value


def test_filter_attention_queue():
    docs = [
        attach_document_visibility_projection(_base_doc(document_id="a")),
        attach_document_visibility_projection(
            _base_doc(
                document_id="b",
                requirement_id=None,
                document_linkage_state=DocumentLinkageState.RECONCILIATION_REQUIRED.value,
                linkage_reconciliation_required=True,
                document_operational_state=DocumentOperationalState.UPLOADED_AWAITING_REVIEW.value,
            )
        ),
    ]
    filtered = filter_documents_by_visibility(docs, "ATTENTION_REQUIRED")
    assert len(filtered) == 1
    assert filtered[0]["document_id"] == "b"


def test_registry_grouping():
    docs = [
        attach_document_visibility_projection(_base_doc(document_id="a"), primary_document_ids={"a"}),
        attach_document_visibility_projection(
            _base_doc(
                document_id="b",
                requirement_id=None,
                document_linkage_state=DocumentLinkageState.INTENTIONALLY_UNLINKED.value,
            )
        ),
    ]
    grouped = group_documents_by_registry_section(docs)
    assert len(grouped["active_evidence"]) == 1
    assert len(grouped["operational_attachments"]) == 1


def test_default_resurface_window_is_90():
    assert get_document_expiry_resurface_days() == 90
