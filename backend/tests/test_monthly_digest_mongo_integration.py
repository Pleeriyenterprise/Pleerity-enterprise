"""
Mongo-backed integration checks for monthly digest: assembly, PDF on disk,
digest_logs, and snapshot comparison on a second send.

Skips when MongoDB is unreachable. Orchestrator send is mocked (no Postmark).
"""
from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database import database


@pytest.mark.integration
@pytest.mark.asyncio
async def test_monthly_digest_mongo_pdf_snapshot_and_second_send_delta(tmp_path):
    """
    Phase A (B/D): overdue + missing evidence → digest_log, snapshot, PDF file.
    Phase C: update requirements → second send → deltas.has_prior_snapshot and score_delta present.
    """
    if database.get_db() is None:
        try:
            await database.connect()
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"MongoDB not available: {exc}")

    db = database.get_db()
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)

    cid = f"digest_int_{uuid.uuid4().hex[:12]}"
    pid = str(uuid.uuid4())
    crn = f"CRN-{uuid.uuid4().hex[:10]}"

    brand = MagicMock()
    brand.company_name = "Pleerity Enterprise Ltd"
    brand.tagline = "AI-Driven Solutions & Compliance"
    brand.primary_color = "#0B1D3A"
    brand.product_display_name = "Compliance Vault Pro"
    brand.logo_path = None
    brand.include_pleerity_attribution = True
    brand.powered_by_text = "Powered by Pleerity"

    from services.notification_orchestrator import NotificationResult

    async def fake_send(*_a, **_kw):
        return NotificationResult(
            outcome="sent",
            message_id=str(uuid.uuid4()),
            details={"provider_message_id": f"pm-{uuid.uuid4().hex[:6]}"},
        )

    async def seed_two_reqs():
        await db.requirements.delete_many({"client_id": cid})
        now = datetime.now(timezone.utc).isoformat()
        await db.requirements.insert_many(
            [
                {
                    "requirement_id": str(uuid.uuid4()),
                    "client_id": cid,
                    "property_id": pid,
                    "requirement_type": "GAS_SAFETY",
                    "code": "gas_safety",
                    "description": "Gas Safety Certificate",
                    "frequency_days": 365,
                    "due_date": "2019-06-01T00:00:00+00:00",
                    "status": "OVERDUE",
                    "applicability": "REQUIRED",
                    "evidence_state": "VERIFIED",
                    "date_source": "VERIFIED_DOCUMENT",
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "requirement_id": str(uuid.uuid4()),
                    "client_id": cid,
                    "property_id": pid,
                    "requirement_type": "EICR",
                    "code": "eicr",
                    "description": "EICR",
                    "frequency_days": 1825,
                    "due_date": "2027-01-15T00:00:00+00:00",
                    "status": "PENDING",
                    "applicability": "REQUIRED",
                    "evidence_state": "MISSING",
                    "date_source": "SYSTEM_ESTIMATED",
                    "created_at": now,
                    "updated_at": now,
                },
            ]
        )

    async def seed_compliant_only():
        await db.requirements.delete_many({"client_id": cid})
        now = datetime.now(timezone.utc).isoformat()
        await db.requirements.insert_one(
            {
                "requirement_id": str(uuid.uuid4()),
                "client_id": cid,
                "property_id": pid,
                "requirement_type": "EPC",
                "code": "epc",
                "description": "EPC",
                "frequency_days": 3650,
                "due_date": "2030-06-01T00:00:00+00:00",
                "status": "COMPLIANT",
                "applicability": "REQUIRED",
                "evidence_state": "VERIFIED",
                "created_at": now,
                "updated_at": now,
            }
        )

    try:
        await db.clients.insert_one(
            {
                "client_id": cid,
                "email": "digest-mongo-int@test.example",
                "full_name": "Mongo Digest Landlord",
                "subscription_status": "ACTIVE",
                "entitlement_status": "ENABLED",
                "customer_reference": crn,
            }
        )
        await db.notification_preferences.insert_one(
            {
                "client_id": cid,
                "monthly_digest": True,
                "digest_day_of_month": 1,
                "reporting_notifications_enabled": True,
                "quiet_hours_enabled": False,
            }
        )
        await db.properties.insert_one(
            {
                "property_id": pid,
                "client_id": cid,
                "is_active": True,
                "nickname": "Integration House",
                "address_line_1": "99 Test Lane",
                "postcode": "SW1A 1AA",
                "compliance_score": 62,
                "compliance_breakdown": {
                    "status_score": 60,
                    "expiry_score": 65,
                    "document_score": 60,
                    "overdue_penalty_score": 55,
                    "risk_score": 70,
                },
            }
        )

        await seed_two_reqs()

        with patch.dict(os.environ, {"DATA_DIR": data_dir}):
            with patch(
                "services.notification_orchestrator.notification_orchestrator.send",
                new_callable=AsyncMock,
                side_effect=fake_send,
            ):
                with patch(
                    "services.branding_resolver_service.resolve_branding",
                    new_callable=AsyncMock,
                    return_value=brand,
                ):
                    with patch("services.webhook_service.fire_digest_sent", new_callable=AsyncMock):
                        from services.jobs import JobScheduler

                        scheduler = JobScheduler()
                        scheduler.db = db
                        out1 = await scheduler.send_monthly_digest_for_client(cid, force=True)

        assert out1.get("outcome_status") == "success", out1

        _rows = await db.digest_logs.find({"client_id": cid}, {"_id": 0}).sort("created_at", -1).limit(1).to_list(1)
        log1 = _rows[0] if _rows else None
        assert log1 is not None
        assert log1.get("delivery_status") == "sent"
        assert "Monthly Compliance Summary" in (log1.get("email_subject") or "")
        assert log1.get("pdf_storage_relpath")

        c1 = log1.get("content") or {}
        assert int(c1.get("overdue") or 0) >= 1
        assert int(c1.get("missing_evidence_count") or 0) >= 1
        assert (c1.get("deltas") or {}).get("has_prior_snapshot") is False

        rel = log1["pdf_storage_relpath"].replace("\\", "/")
        assert os.path.isfile(os.path.join(data_dir, rel))
        assert open(os.path.join(data_dir, rel), "rb").read(5).startswith(b"%PDF")

        snap1 = await db.monthly_compliance_snapshots.find_one({"client_id": cid}, {"_id": 0})
        assert snap1 is not None
        assert len(snap1.get("requirement_fingerprints") or {}) >= 1

        # Update property score upward and replace requirements with a single compliant item
        await db.properties.update_one(
            {"property_id": pid},
            {
                "$set": {
                    "compliance_score": 92,
                    "compliance_breakdown": {
                        "status_score": 95,
                        "expiry_score": 90,
                        "document_score": 90,
                        "overdue_penalty_score": 90,
                        "risk_score": 90,
                    },
                }
            },
        )
        await seed_compliant_only()

        with patch.dict(os.environ, {"DATA_DIR": data_dir}):
            with patch(
                "services.notification_orchestrator.notification_orchestrator.send",
                new_callable=AsyncMock,
                side_effect=fake_send,
            ):
                with patch(
                    "services.branding_resolver_service.resolve_branding",
                    new_callable=AsyncMock,
                    return_value=brand,
                ):
                    with patch("services.webhook_service.fire_digest_sent", new_callable=AsyncMock):
                        from services.jobs import JobScheduler

                        scheduler = JobScheduler()
                        scheduler.db = db
                        out2 = await scheduler.send_monthly_digest_for_client(cid, force=True)

        assert out2.get("outcome_status") == "success", out2

        logs = await db.digest_logs.find({"client_id": cid}, {"_id": 0}).sort("created_at", -1).to_list(5)
        assert len(logs) >= 2
        latest = logs[0]
        d2 = (latest.get("content") or {}).get("deltas") or {}
        assert d2.get("has_prior_snapshot") is True
        assert d2.get("score_delta") is not None

    finally:
        await db.requirements.delete_many({"client_id": cid})
        await db.properties.delete_many({"client_id": cid})
        await db.notification_preferences.delete_many({"client_id": cid})
        await db.digest_logs.delete_many({"client_id": cid})
        await db.monthly_compliance_snapshots.delete_many({"client_id": cid})
        await db.clients.delete_one({"client_id": cid})
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_monthly_digest_email_failure_logs_and_keeps_pdf(tmp_path):
    """
    Scenario F: provider send fails → digest_logs shows failed_email, PDF remains on disk, no snapshot.
    """
    if database.get_db() is None:
        try:
            await database.connect()
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"MongoDB not available: {exc}")
    else:
        # Motor binds to the asyncio loop; a prior async test closes the loop while the client stays open.
        try:
            await database.close()
        except Exception:
            pass
        try:
            await database.connect()
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"MongoDB not available: {exc}")

    db = database.get_db()
    data_dir = str(tmp_path / "fail_data")
    os.makedirs(data_dir, exist_ok=True)

    cid = f"digest_fail_{uuid.uuid4().hex[:12]}"
    pid = str(uuid.uuid4())
    crn = f"CRN-{uuid.uuid4().hex[:10]}"

    brand = MagicMock()
    brand.company_name = "Pleerity Enterprise Ltd"
    brand.tagline = "Tag"
    brand.primary_color = "#0B1D3A"
    brand.product_display_name = "CVP"
    brand.logo_path = None
    brand.include_pleerity_attribution = True
    brand.powered_by_text = ""

    from services.notification_orchestrator import NotificationResult

    async def fake_send_fail(*_a, **_kw):
        return NotificationResult(outcome="failed", error_message="Simulated provider failure")

    now = datetime.now(timezone.utc).isoformat()
    try:
        await db.clients.insert_one(
            {
                "client_id": cid,
                "email": "digest-fail@test.example",
                "full_name": "Fail Test",
                "subscription_status": "ACTIVE",
                "entitlement_status": "ENABLED",
                "customer_reference": crn,
            }
        )
        await db.notification_preferences.insert_one(
            {
                "client_id": cid,
                "monthly_digest": True,
                "reporting_notifications_enabled": True,
                "quiet_hours_enabled": False,
            }
        )
        await db.properties.insert_one(
            {
                "property_id": pid,
                "client_id": cid,
                "is_active": True,
                "nickname": "P",
                "address_line_1": "1 St",
                "postcode": "E1",
                "compliance_score": 70,
                "compliance_breakdown": {
                    "status_score": 70,
                    "expiry_score": 70,
                    "document_score": 70,
                    "overdue_penalty_score": 70,
                    "risk_score": 70,
                },
            }
        )
        await db.requirements.insert_one(
            {
                "requirement_id": str(uuid.uuid4()),
                "client_id": cid,
                "property_id": pid,
                "requirement_type": "EPC",
                "code": "epc",
                "description": "EPC",
                "frequency_days": 3650,
                "due_date": "2030-01-01T00:00:00+00:00",
                "status": "COMPLIANT",
                "applicability": "REQUIRED",
                "evidence_state": "VERIFIED",
                "created_at": now,
                "updated_at": now,
            }
        )

        with patch.dict(os.environ, {"DATA_DIR": data_dir}):
            with patch(
                "services.notification_orchestrator.notification_orchestrator.send",
                new_callable=AsyncMock,
                side_effect=fake_send_fail,
            ):
                with patch("services.branding_resolver_service.resolve_branding", new_callable=AsyncMock, return_value=brand):
                    with patch("services.webhook_service.fire_digest_sent", new_callable=AsyncMock):
                        from services.jobs import JobScheduler

                        scheduler = JobScheduler()
                        scheduler.db = db
                        out = await scheduler.send_monthly_digest_for_client(cid, force=True)

        assert out.get("outcome_status") == "failed"
        log = await db.digest_logs.find_one({"client_id": cid}, {"_id": 0})
        assert log is not None
        assert log.get("delivery_status") == "failed_email"
        assert log.get("failure_reason")
        rel = (log.get("pdf_storage_relpath") or "").replace("\\", "/")
        assert rel
        assert os.path.isfile(os.path.join(data_dir, rel))

        snap = await db.monthly_compliance_snapshots.find_one({"client_id": cid})
        assert snap is None

    finally:
        await db.requirements.delete_many({"client_id": cid})
        await db.properties.delete_many({"client_id": cid})
        await db.notification_preferences.delete_many({"client_id": cid})
        await db.digest_logs.delete_many({"client_id": cid})
        await db.monthly_compliance_snapshots.delete_many({"client_id": cid})
        await db.clients.delete_one({"client_id": cid})
        shutil.rmtree(data_dir, ignore_errors=True)
