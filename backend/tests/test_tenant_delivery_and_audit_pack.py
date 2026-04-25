"""Tenant delivery proof + governed compliance audit pack (services + HTTP surfaces)."""
from __future__ import annotations

import asyncio
import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from database import database as db_singleton
from middleware import admin_route_guard
from models import AuditAction
from routes import compliance_delivery_audit as cda_routes
from routes.compliance_delivery_audit import serialize_tenant_delivery_row
from server import app
from services.notification_orchestrator import NotificationResult


@pytest.fixture
def client_http():
    with TestClient(app) as c:
        yield c


def test_initiate_tenant_delivery_success_links_message_and_audits():
    from services import tenant_delivery_proof_service as td

    user = {"client_id": "c1", "portal_user_id": "landlord1", "role": "ROLE_CLIENT_ADMIN"}
    prop = {"property_id": "p1", "client_id": "c1", "is_active": True}
    tenant = {
        "portal_user_id": "t1",
        "client_id": "c1",
        "role": "ROLE_TENANT",
        "status": "ACTIVE",
        "auth_email": "tenant@example.com",
    }

    mock_db = MagicMock()

    async def find_one(filter_q, *args, **kwargs):
        fq = filter_q or {}
        if fq.get("property_id") == "p1" and fq.get("client_id") == "c1":
            return prop
        if fq.get("portal_user_id") == "t1":
            return tenant
        if fq.get("message_id") == "mid-1":
            return {
                "message_id": "mid-1",
                "status": "SENT",
                "provider_message_id": "pm-99",
                "postmark_message_id": "pm-99",
            }
        return None

    async def count_documents(q):
        if q.get("tenant_id") == "t1":
            return 0
        return 0

    mock_db.properties.find_one = AsyncMock(side_effect=find_one)
    mock_db.portal_users.find_one = AsyncMock(side_effect=find_one)
    mock_db.tenant_assignments.count_documents = AsyncMock(side_effect=count_documents)
    mock_db.requirements.find = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(return_value=[{"requirement_id": "r1", "tenant_delivery_required": True}])))
    mock_db.requirements.find_one = AsyncMock(
        return_value={"requirement_id": "r1", "client_id": "c1", "property_id": "p1", "tenant_delivery_required": True}
    )
    mock_db.clients.find_one = AsyncMock(return_value={"full_name": "Landlord", "customer_reference": "CR1"})
    ins = AsyncMock()
    mock_db.tenant_delivery_proofs.insert_one = ins
    upd = AsyncMock()
    mock_db.tenant_delivery_proofs.update_one = upd
    mock_db.requirements.update_many = AsyncMock()
    mock_db.message_logs.update_one = AsyncMock()
    mock_db.message_logs.find_one = AsyncMock(side_effect=find_one)

    async def fake_pack(**kwargs):
        return b"%PDF-1.4 fake"

    sent = NotificationResult(
        outcome="sent",
        message_id="mid-1",
        details={"provider_message_id": "pm-99"},
    )

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(td.compliance_pack_service, "generate_compliance_pack", new=fake_pack),
        patch.object(td, "NotificationOrchestrator") as orch_cls,
        patch("services.tenant_delivery_proof_service.create_audit_log", new_callable=AsyncMock) as audit,
        patch.object(td, "sync_compliance_gaps_for_requirement", new_callable=AsyncMock),
    ):
        orch_cls.return_value.send = AsyncMock(return_value=sent)
        out = asyncio.run(
            td.initiate_tenant_compliance_delivery(
                client_id="c1",
                property_id="p1",
                tenant_portal_user_id="t1",
                recipient_email="tenant@example.com",
                initiated_by_user_id="landlord1",
                initiated_by_role="ROLE_CLIENT_ADMIN",
            )
        )

    assert out["outcome"] == "sent"
    assert out["provider_message_id"] == "pm-99"
    assert ins.await_count == 1
    kinds = [c.kwargs.get("action") for c in audit.call_args_list]
    assert AuditAction.TENANT_DELIVERY_INITIATED in kinds
    assert AuditAction.TENANT_DELIVERY_SUCCEEDED in kinds
    um = mock_db.requirements.update_many.await_args
    assert um is not None
    assert um.args[1]["$set"]["tenant_delivery_proof_status"] == "SENT"


def test_initiate_tenant_delivery_failed_audits():
    from services import tenant_delivery_proof_service as td

    prop = {"property_id": "p1", "client_id": "c1"}
    tenant = {
        "portal_user_id": "t1",
        "client_id": "c1",
        "role": "ROLE_TENANT",
        "status": "ACTIVE",
        "auth_email": "tenant@example.com",
    }
    mock_db = MagicMock()

    async def find_one(filter_q, *args, **kwargs):
        if filter_q.get("property_id") == "p1":
            return prop
        if filter_q.get("portal_user_id") == "t1":
            return tenant
        return None

    mock_db.properties.find_one = AsyncMock(side_effect=find_one)
    mock_db.portal_users.find_one = AsyncMock(side_effect=find_one)
    mock_db.tenant_assignments.count_documents = AsyncMock(return_value=0)
    mock_db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    mock_db.clients.find_one = AsyncMock(return_value={})
    mock_db.tenant_delivery_proofs.insert_one = AsyncMock()
    mock_db.tenant_delivery_proofs.update_one = AsyncMock()
    mock_db.message_logs.update_one = AsyncMock()
    mock_db.message_logs.find_one = AsyncMock(return_value=None)

    fail = NotificationResult(outcome="failed", message_id="mid-f", error_message="postmark down")

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(td.compliance_pack_service, "generate_compliance_pack", new=AsyncMock(return_value=b"%PDF")),
        patch.object(td, "NotificationOrchestrator") as orch_cls,
        patch("services.tenant_delivery_proof_service.create_audit_log", new_callable=AsyncMock) as audit,
    ):
        orch_cls.return_value.send = AsyncMock(return_value=fail)
        out = asyncio.run(
            td.initiate_tenant_compliance_delivery(
                client_id="c1",
                property_id="p1",
                tenant_portal_user_id="t1",
                recipient_email="tenant@example.com",
                initiated_by_user_id="landlord1",
                initiated_by_role="ROLE_CLIENT_ADMIN",
            )
        )

    assert out["outcome"] == "failed"
    kinds = [c.kwargs.get("action") for c in audit.call_args_list]
    assert AuditAction.TENANT_DELIVERY_FAILED in kinds


def test_audit_pack_zip_contains_manifest_and_checksums():
    from services import compliance_audit_pack_service as caps

    rid = "r-auth-1"
    req = {
        "requirement_id": rid,
        "client_id": "c1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {
            "version": 1,
            "state": "VERIFIED_CURRENT",
            "effective_expiry_date": "2027-01-01T00:00:00+00:00",
        },
    }
    mock_db = MagicMock()
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "p1", "client_id": "c1"})
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c1"})
    mock_db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[req])))
    mock_db.documents.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))

    def _chain_empty():
        c3 = MagicMock()
        c3.to_list = AsyncMock(return_value=[])
        c2 = MagicMock()
        c2.limit = MagicMock(return_value=c3)
        c1 = MagicMock()
        c1.sort = MagicMock(return_value=c2)
        return c1

    mock_db.audit_logs.find = MagicMock(return_value=_chain_empty())
    mock_db.tenant_delivery_proofs.find = MagicMock(return_value=_chain_empty())
    mock_db.compliance_audit_packs.insert_one = AsyncMock()

    async def fake_upload(fname, data, metadata):
        assert fname.endswith(".zip")
        assert b"PK" in data[:4] or data[:2] == b"PK"  # zip magic
        return "507f1f77bcf86cd799439011"

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(
            caps,
            "filter_requirement_rows_for_client_runtime_surfaces",
            new=AsyncMock(return_value=[req]),
        ),
        patch.object(caps.compliance_pack_service, "generate_compliance_pack", new=AsyncMock(return_value=b"%PDF-audit")),
        patch.object(caps, "_upload_zip_gridfs", new=fake_upload),
        patch("services.compliance_audit_pack_service.create_audit_log", new_callable=AsyncMock) as audit,
    ):
        summary = asyncio.run(
            caps.build_compliance_audit_pack(
                client_id="c1",
                property_id="p1",
                initiated_by_user_id="u1",
                initiated_by_role="ROLE_CLIENT_ADMIN",
            )
        )

    assert summary.get("pack_id", "").startswith("cap_")
    assert len(summary.get("package_sha256", "")) == 64
    assert audit.await_args.kwargs.get("action") == AuditAction.COMPLIANCE_AUDIT_PACK_GENERATED

    # Rebuild zip logic sanity: manifest lists authority ids
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("manifest.json", b'{"authority_requirement_ids":["r-auth-1"]}')
    assert "manifest.json" in zipfile.ZipFile(io.BytesIO(zip_buf.getvalue())).namelist()


def test_http_post_tenant_delivery_and_audit_pack_generate(client_http):
    user = {"client_id": "c-http", "portal_user_id": "pu-http", "role": "ROLE_CLIENT_ADMIN"}

    async def guard(request):
        return user

    mock_db = MagicMock()
    mock_db.portal_users.find_one = AsyncMock(return_value={"auth_email": "t@example.com"})

    with (
        patch.object(cda_routes, "client_route_guard", guard),
        patch.object(cda_routes.database, "get_db", return_value=mock_db),
        patch.object(cda_routes.plan_registry, "enforce_feature", new=AsyncMock(return_value=(True, None, {}))),
        patch.object(
            cda_routes.td_proof,
            "initiate_tenant_compliance_delivery",
            new=AsyncMock(
                return_value={
                    "delivery_id": "td1",
                    "outcome": "sent",
                    "message_log_id": "m1",
                    "provider_message_id": "p1",
                    "notification_outcome": "sent",
                    "audit_log_ids": ["a1", "a2"],
                }
            ),
        ),
    ):
        r = client_http.post(
            "/api/client/compliance/tenant-delivery",
            json={
                "property_id": "p-http",
                "tenant_portal_user_id": "t-http",
                "recipient_email": "t@example.com",
            },
        )
    assert r.status_code == 200, r.text
    assert r.json()["delivery_id"] == "td1"

    with (
        patch.object(cda_routes, "client_route_guard", guard),
        patch.object(cda_routes.plan_registry, "enforce_feature", new=AsyncMock(return_value=(True, None, {}))),
        patch.object(
            cda_routes.audit_pack,
            "build_compliance_audit_pack",
            new=AsyncMock(
                return_value={
                    "pack_id": "cap_z",
                    "package_sha256": "0" * 64,
                    "manifest_sha256": "1" * 64,
                    "gridfs_id": "gid",
                    "byte_size": 10,
                    "filename": "cap_z.zip",
                    "audit_log_id": "aud",
                    "timeline_event_count": 0,
                    "delivery_proof_count": 0,
                    "included_certificate_paths": [],
                }
            ),
        ),
    ):
        r2 = client_http.post(
            "/api/client/compliance/audit-pack/generate",
            json={"property_id": "p-http"},
        )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["pack_id"] == "cap_z"
    assert len(body["package_sha256"]) == 64


def test_serialize_tenant_delivery_list_payload_shape():
    row = {
        "delivery_id": "td1",
        "created_at": "2026-01-01T00:00:00+00:00",
        "delivery_status": "DELIVERED",
        "recipient_email": "a@b.c",
        "provider_message_id": "pm",
        "provider_opened_at": "2026-01-02T00:00:00+00:00",
        "audit_log_ids": ["x"],
    }
    s = serialize_tenant_delivery_row(row)
    assert "ui_status" in s
    assert s["ui_status"]["delivered"] is True
    assert s["ui_status"]["opened"] is True
    assert "provider_evidence_notice" in s


def test_reconcile_postmark_delivered_updates_proof_and_requirements():
    from services import tenant_delivery_reconciliation as tr

    proof = {
        "delivery_id": "tdx",
        "client_id": "c1",
        "property_id": "p1",
        "message_log_id": "ml1",
        "provider_message_id": "POST-1",
        "requirement_ids_covered": ["r1"],
        "delivery_status": "SENT",
    }
    log = {
        "message_id": "ml1",
        "status": "DELIVERED",
        "provider_message_id": "POST-1",
        "metadata": {"tenant_delivery_id": "tdx", "delivery_proof_intent": "TENANT_COMPLIANCE_PACK"},
    }
    mock_db = MagicMock()
    mock_db.tenant_delivery_proofs.update_one = AsyncMock()
    mock_db.requirements.update_many = AsyncMock()
    mock_db.requirements.find_one = AsyncMock(return_value={"requirement_id": "r1", "client_id": "c1", "property_id": "p1"})
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "p1", "client_id": "c1"})

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(tr, "_find_proofs_for_log", new=AsyncMock(return_value=[proof])),
        patch("services.tenant_delivery_reconciliation.create_audit_log", new_callable=AsyncMock),
        patch.object(tr, "sync_compliance_gaps_for_requirement", new_callable=AsyncMock),
    ):
        out = asyncio.run(tr.apply_message_log_to_tenant_delivery_proofs(mock_db, log))
    assert "tdx" in out
    ac = mock_db.tenant_delivery_proofs.update_one.await_args
    assert ac.args[1]["$set"]["delivery_status"] == "DELIVERED"
    assert mock_db.requirements.update_many.await_args.args[1]["$set"]["tenant_delivery_proof_status"] == "DELIVERED"


def test_reconcile_open_sets_provider_opened():
    from services import tenant_delivery_reconciliation as tr

    proof = {
        "delivery_id": "tdo",
        "client_id": "c1",
        "property_id": "p1",
        "message_log_id": "ml1",
        "provider_message_id": "POST-1",
        "requirement_ids_covered": [],
        "delivery_status": "DELIVERED",
        "provider_delivered_at": "2026-01-01T00:00:00+00:00",
    }
    log = {
        "message_id": "ml1",
        "status": "DELIVERED",
        "opened_at": "2026-02-01T12:00:00+00:00",
        "provider_message_id": "POST-1",
        "metadata": {"tenant_delivery_id": "tdo", "delivery_proof_intent": "TENANT_COMPLIANCE_PACK"},
    }
    mock_db = MagicMock()
    mock_db.tenant_delivery_proofs.update_one = AsyncMock()
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "p1", "client_id": "c1"})

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(tr, "_find_proofs_for_log", new=AsyncMock(return_value=[proof])),
        patch("services.tenant_delivery_reconciliation.create_audit_log", new_callable=AsyncMock),
    ):
        asyncio.run(tr.apply_message_log_to_tenant_delivery_proofs(mock_db, log))
    ac = mock_db.tenant_delivery_proofs.update_one.await_args
    assert ac.args[1]["$set"].get("provider_opened_at")


def test_reconcile_bounced_does_not_set_delivered():
    from services import tenant_delivery_reconciliation as tr

    proof = {
        "delivery_id": "tdb",
        "client_id": "c1",
        "property_id": "p1",
        "message_log_id": "ml1",
        "provider_message_id": "POST-1",
        "requirement_ids_covered": ["r1"],
        "delivery_status": "SENT",
    }
    log = {
        "message_id": "ml1",
        "status": "BOUNCED",
        "provider_message_id": "POST-1",
        "metadata": {"tenant_delivery_id": "tdb", "delivery_proof_intent": "TENANT_COMPLIANCE_PACK"},
    }
    mock_db = MagicMock()
    mock_db.tenant_delivery_proofs.update_one = AsyncMock()
    mock_db.requirements.update_many = AsyncMock()
    mock_db.requirements.find_one = AsyncMock(return_value={"requirement_id": "r1", "client_id": "c1", "property_id": "p1"})
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "p1", "client_id": "c1"})

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(tr, "_find_proofs_for_log", new=AsyncMock(return_value=[proof])),
        patch("services.tenant_delivery_reconciliation.create_audit_log", new_callable=AsyncMock),
        patch.object(tr, "sync_compliance_gaps_for_requirement", new_callable=AsyncMock),
    ):
        asyncio.run(tr.apply_message_log_to_tenant_delivery_proofs(mock_db, log))
    ac = mock_db.tenant_delivery_proofs.update_one.await_args
    assert ac.args[1]["$set"]["delivery_status"] == "BOUNCED"
    assert mock_db.requirements.update_many.await_args.args[1]["$set"]["tenant_delivery_proof_status"] == "BOUNCED"


def test_gap_still_open_when_requirement_only_sent():
    from services.compliance_gap_engine import GAP_TENANT_DELIVERY_PROOF_MISSING, infer_compliance_gaps_for_requirement
    from services.requirement_evidence_authority import AUTHORITY_VERSION, EA_VERIFIED_CURRENT

    eff = "2027-06-01T00:00:00+00:00"
    r = {
        "client_id": "c-gap",
        "property_id": "p-gap",
        "requirement_id": "r-gap",
        "requirement_code": "EPC",
        "requirement_type": "EPC",
        "title": "EPC",
        "tenant_delivery_required": True,
        "tenant_delivery_proof_status": "SENT",
        "evidence_authority_synced_at": "2026-01-10T12:00:00+00:00",
        "evidence_authority": {"version": AUTHORITY_VERSION, "state": EA_VERIFIED_CURRENT, "effective_expiry_date": eff},
        "updated_at": "2026-01-10T12:00:00+00:00",
    }
    now = __import__("datetime").datetime(2026, 1, 10, tzinfo=__import__("datetime").timezone.utc)
    from unittest.mock import patch

    with patch("services.compliance_gap_engine.resolve_expiring_soon_days_for_requirement", return_value=60):
        gaps = infer_compliance_gaps_for_requirement(r, property_doc=None, now=now)
    kinds = [g.gap_kind for g in gaps]
    assert GAP_TENANT_DELIVERY_PROOF_MISSING in kinds


def test_gap_closes_when_requirement_tenant_delivery_delivered():
    from services.compliance_gap_engine import GAP_TENANT_DELIVERY_PROOF_MISSING, infer_compliance_gaps_for_requirement
    from services.requirement_evidence_authority import AUTHORITY_VERSION, EA_VERIFIED_CURRENT

    eff = "2027-06-01T00:00:00+00:00"
    r = {
        "client_id": "c-gap",
        "property_id": "p-gap",
        "requirement_id": "r-gap",
        "requirement_code": "EPC",
        "requirement_type": "EPC",
        "title": "EPC",
        "tenant_delivery_required": True,
        "tenant_delivery_proof_status": "DELIVERED",
        "evidence_authority_synced_at": "2026-01-10T12:00:00+00:00",
        "evidence_authority": {"version": AUTHORITY_VERSION, "state": EA_VERIFIED_CURRENT, "effective_expiry_date": eff},
        "updated_at": "2026-01-10T12:00:00+00:00",
    }
    now = __import__("datetime").datetime(2026, 1, 10, tzinfo=__import__("datetime").timezone.utc)
    from unittest.mock import patch

    with patch("services.compliance_gap_engine.resolve_expiring_soon_days_for_requirement", return_value=60):
        gaps = infer_compliance_gaps_for_requirement(r, property_doc=None, now=now)
    kinds = [g.gap_kind for g in gaps]
    assert GAP_TENANT_DELIVERY_PROOF_MISSING not in kinds


def test_http_client_tenant_deliveries_list_payload(client_http):
    user = {"client_id": "c-list", "portal_user_id": "pu-list", "role": "ROLE_CLIENT_ADMIN"}

    async def guard(request):
        return user

    row = {
        "delivery_id": "td-list",
        "created_at": "2026-01-01T00:00:00+00:00",
        "delivery_status": "SENT",
        "recipient_email": "t@x.com",
        "provider_message_id": "pm-1",
    }
    with (
        patch.object(cda_routes, "client_route_guard", guard),
        patch.object(
            cda_routes.td_proof,
            "list_tenant_delivery_proofs_for_scope",
            new=AsyncMock(return_value=[row]),
        ),
    ):
        r = client_http.get("/api/client/compliance/tenant-deliveries")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "provider_evidence_notice" in body
    assert body["items"][0]["delivery_id"] == "td-list"
    assert "ui_status" in body["items"][0]
    assert body["items"][0]["ui_status"]["sent"] is True
    assert body["items"][0]["ui_status"]["delivered"] is False


def test_http_admin_tenant_deliveries_list_and_audit_pack_download(client_http):
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c-adm"})

    async def adm(request: Request):
        return {"portal_user_id": "adm1", "role": "ROLE_ADMIN"}

    row = {
        "delivery_id": "td-adm",
        "client_id": "c-adm",
        "property_id": "p1",
        "delivery_status": "DELIVERED",
        "provider_message_id": "POST-9",
        "sent_at": "2026-01-01T00:00:00+00:00",
    }
    rec = {
        "pack_id": "cap_adm",
        "client_id": "c-adm",
        "property_id": "p1",
        "gridfs_id": "507f1f77bcf86cd799439011",
        "filename": "cap_adm.zip",
    }
    admin_user = {"portal_user_id": "adm1", "role": "ROLE_ADMIN"}
    app.dependency_overrides[admin_route_guard] = adm
    try:
        with (
            patch.object(cda_routes.database, "get_db", return_value=mock_db),
            patch.object(
                cda_routes.td_proof,
                "list_tenant_delivery_proofs_for_scope",
                new=AsyncMock(return_value=[row]),
            ),
        ):
            r = client_http.get("/api/admin/compliance/tenant-deliveries?client_id=c-adm")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "provider_evidence_notice" in body
        assert body["items"][0]["ui_status"]["delivered"] is True

        with (
            patch.object(cda_routes.database, "get_db", return_value=mock_db),
            patch.object(cda_routes, "admin_route_guard", new=AsyncMock(return_value=admin_user)),
            patch.object(cda_routes.audit_pack, "get_audit_pack_record", new=AsyncMock(return_value=rec)),
            patch.object(cda_routes.audit_pack, "read_audit_pack_zip_bytes", new=AsyncMock(return_value=b"PK\x03\x04aa")),
            patch.object(cda_routes, "create_audit_log", new_callable=AsyncMock) as audit,
        ):
            r2 = client_http.get("/api/admin/compliance/audit-packs/cap_adm/download?client_id=c-adm")
        assert r2.status_code == 200
        assert r2.headers.get("X-Pack-Id") == "cap_adm"
        assert audit.await_args.kwargs.get("action") == AuditAction.COMPLIANCE_AUDIT_PACK_DOWNLOADED
    finally:
        app.dependency_overrides.pop(admin_route_guard, None)


def test_http_audit_pack_download_logs_audit(client_http):
    user = {"client_id": "c-dl", "portal_user_id": "pu-dl", "role": "ROLE_CLIENT_ADMIN"}

    async def guard(request):
        return user

    rec = {
        "pack_id": "cap_dl",
        "client_id": "c-dl",
        "property_id": "p1",
        "gridfs_id": "507f1f77bcf86cd799439011",
        "filename": "cap_dl.zip",
    }

    with (
        patch.object(cda_routes, "client_route_guard", guard),
        patch.object(cda_routes.plan_registry, "enforce_feature", new=AsyncMock(return_value=(True, None, {}))),
        patch.object(cda_routes.audit_pack, "get_audit_pack_record", new=AsyncMock(return_value=rec)),
        patch.object(cda_routes.audit_pack, "read_audit_pack_zip_bytes", new=AsyncMock(return_value=b"PK\x03\x04zz")),
        patch.object(cda_routes, "create_audit_log", new_callable=AsyncMock) as audit,
    ):
        r = client_http.get("/api/client/compliance/audit-pack/cap_dl/download")
    assert r.status_code == 200
    assert r.headers.get("X-Pack-Id") == "cap_dl"
    assert audit.await_args.kwargs.get("action") == AuditAction.COMPLIANCE_AUDIT_PACK_DOWNLOADED
