"""Integration: commercial entitlement expiry transition (requires MONGO_URL)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from database import database
from services.commercial_entitlement_expiry_service import process_commercial_entitlement_expiry
from services.commercial_entitlement_service import (
    COL_GOVERNANCE,
    GOVERNANCE_STATUS_ACTIVE,
    GOVERNANCE_STATUS_EXPIRED,
    derive_customer_access_state,
    get_active_governance,
    load_client_billing_signals,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expiry_job_expires_backdated_grace_row():
    if database.get_db() is None:
        try:
            await database.connect()
        except Exception as exc:
            pytest.skip(f"MongoDB not available: {exc}")

    db = database.get_db()
    client_id = f"expiry_int_{uuid.uuid4().hex[:8]}"
    await db.clients.insert_one(
        {
            "client_id": client_id,
            "email": f"{client_id}@example.com",
            "subscription_status": "ACTIVE",
            "billing_lifecycle_state": "active",
        }
    )
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    gid = str(uuid.uuid4())
    await db[COL_GOVERNANCE].insert_one(
        {
            "governance_id": gid,
            "client_id": client_id,
            "entitlement_state": "GRACE_PERIOD",
            "exception_type": "grace_extension",
            "entitlement_reason": "integration test",
            "entitlement_scope": "account",
            "entitlement_expiry_at": past,
            "entitlement_review_required": False,
            "access_policy": "full_access",
            "effective_access_reason": "Grace period until 2026-01-01",
            "status": GOVERNANCE_STATUS_ACTIVE,
            "created_at": past,
            "updated_at": past,
        }
    )
    signals = await load_client_billing_signals(client_id)
    signals["active_governance"] = await get_active_governance(client_id)
    before = derive_customer_access_state(signals)
    assert before.get("governance_applied") is True

    result = await process_commercial_entitlement_expiry(limit=50)
    assert result["expired_count"] >= 1

    row = await db[COL_GOVERNANCE].find_one({"governance_id": gid})
    assert row["status"] == GOVERNANCE_STATUS_EXPIRED
    assert row.get("expired_at")

    signals2 = await load_client_billing_signals(client_id)
    signals2["active_governance"] = await get_active_governance(client_id)
    after = derive_customer_access_state(signals2)
    assert after.get("governance_applied") is False

    audit = await db.commercial_entitlement_audit.find_one(
        {"governance_id": gid, "event_type": "commercial_expired"}
    )
    assert audit is not None

    result2 = await process_commercial_entitlement_expiry(limit=50)
    assert result2["expired_count"] == 0

    await db.clients.delete_one({"client_id": client_id})
    await db[COL_GOVERNANCE].delete_many({"client_id": client_id})
    await db.commercial_entitlement_audit.delete_many({"client_id": client_id})
