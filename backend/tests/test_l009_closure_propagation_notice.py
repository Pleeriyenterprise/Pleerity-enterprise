"""L-009f–j closure: bulk/zip finalize helper + propagation_notice merge semantics."""

from __future__ import annotations

from routes.documents import _finalize_bulk_zip_results_propagation_notices
from services.client_propagation_notice import (
    NOTICE_AUTHORITY_SYNC_DEFERRED,
    NOTICE_RECALC_ENQUEUE_DEFERRED,
)


def test_finalize_bulk_zip_per_row_and_top_merge_precedence():
    """Results order for merge; authority-deferred in a later row wins over earlier recalc-deferred."""
    fo_recalc_first: dict = {
        "rst_core_backbone_activation": {"permitted": True},
        "downstream_trigger_targets": [
            {
                "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                "propagation_stage": "x:rst_core_backbone_blocked_skip_enqueue",
            }
        ],
    }
    fo_auth_second: dict = {"rst_core_backbone_activation": {"permitted": False, "activation_reason": "test"}}

    results = [
        {
            "filename": "a.pdf",
            "document_id": "d1",
            "status": "uploaded",
            "matched_requirement": "r1",
        },
        {
            "filename": "b.pdf",
            "document_id": "d2",
            "status": "uploaded",
            "matched_requirement": "r2",
        },
    ]
    fanouts = {"d1": fo_recalc_first, "d2": fo_auth_second}

    top = _finalize_bulk_zip_results_propagation_notices(results, fanouts)

    assert top is not None
    assert top.get("code") == NOTICE_AUTHORITY_SYNC_DEFERRED
    assert (results[0].get("propagation_notice") or {}).get("code") == NOTICE_RECALC_ENQUEUE_DEFERRED
    assert (results[1].get("propagation_notice") or {}).get("code") == NOTICE_AUTHORITY_SYNC_DEFERRED


def test_finalize_bulk_zip_skips_failed_rows():
    results = [
        {"filename": "bad.pdf", "status": "failed", "error": "x"},
        {
            "filename": "ok.pdf",
            "document_id": "dok",
            "status": "uploaded",
            "matched_requirement": "r1",
        },
    ]
    fo: dict = {"rst_core_backbone_activation": {"permitted": False, "activation_reason": "t"}}
    top = _finalize_bulk_zip_results_propagation_notices(results, {"dok": fo})
    assert top is not None
    assert top.get("code") == NOTICE_AUTHORITY_SYNC_DEFERRED
    assert "propagation_notice" not in results[0]
