"""Approval list/detail responses must be JSON-serializable (no raw Mongo _id)."""
from datetime import datetime, timezone

from bson import ObjectId

from services.approval_service import _invoice_for_api, _history_row_for_api


def test_invoice_for_api_strips_object_id_and_iso_dates():
    doc = {
        "_id": ObjectId(),
        "invoice_id": "inv-1",
        "status": "pending",
        "submitted_at": datetime(2026, 6, 4, 12, 0, 0, tzinfo=timezone.utc),
    }
    out = _invoice_for_api(doc)
    assert "_id" not in out
    assert out["invoice_id"] == "inv-1"
    assert out["submitted_at"] == "2026-06-04T12:00:00+00:00"


def test_history_row_for_api_strips_object_id():
    row = {"_id": ObjectId(), "action": "approved", "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    out = _history_row_for_api(row)
    assert "_id" not in out
    assert "2026" in out["created_at"]
