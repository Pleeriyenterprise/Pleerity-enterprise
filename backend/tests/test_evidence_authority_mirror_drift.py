from datetime import datetime, timezone, timedelta

from models import DocumentStatus
from services.requirement_evidence_authority import detect_requirement_mirror_drift, preview_authority


def _req(**kwargs):
    base = {
        "requirement_id": "r1",
        "client_id": "c1",
        "property_id": "p1",
        "applicability": "REQUIRED",
        "requirement_type": "GAS_SAFETY_CERT",
        "due_date": None,
        "status": "PENDING",
        "evidence_state": "MISSING",
    }
    base.update(kwargs)
    return base


def _doc(**kwargs):
    base = {
        "document_id": "d1",
        "client_id": "c1",
        "property_id": "p1",
        "authoritative_property_id": "p1",
        "evidence_scope_type": "PROPERTY",
        "evidence_scope_id": "p1",
        "requirement_id": "r1",
        "status": DocumentStatus.UPLOADED.value,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(kwargs)
    return base


def _assert_no_drift(requirement, docs):
    out = preview_authority(requirement, docs)
    merged = {
        **requirement,
        **out["mirror"],
        "evidence_authority": out["evidence_authority"],
        "evidence_authority_synced_at": datetime.now(timezone.utc).isoformat(),
    }
    drift = detect_requirement_mirror_drift(merged)
    assert drift["drift"] is False, drift


def test_upload_does_not_drift():
    _assert_no_drift(_req(), [_doc(status=DocumentStatus.UPLOADED.value)])


def test_verify_does_not_drift():
    future = (datetime.now(timezone.utc) + timedelta(days=180)).isoformat()
    _assert_no_drift(_req(), [_doc(status=DocumentStatus.VERIFIED.value, expiry_date=future)])


def test_reject_does_not_drift():
    _assert_no_drift(_req(), [_doc(status=DocumentStatus.REJECTED.value)])


def test_apply_extraction_pending_confirmation_does_not_drift():
    _assert_no_drift(_req(), [_doc(status=DocumentStatus.PENDING.value, extraction_status="extracted")])


def test_delete_does_not_drift():
    _assert_no_drift(_req(), [])


def test_unlink_does_not_drift():
    # unlinking leaves requirement without linked evidence
    _assert_no_drift(_req(), [])


def test_relink_does_not_drift():
    # relinking re-attaches a compatible document and remains synced
    _assert_no_drift(_req(), [_doc(status=DocumentStatus.UPLOADED.value, requirement_id="r1")])

