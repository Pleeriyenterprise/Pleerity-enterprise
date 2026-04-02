from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import tenant_request_compliance_service as svc


class _Coll:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    async def find_one(self, query, projection=None):
        for r in self.rows:
            ok = True
            for k, v in query.items():
                if isinstance(v, dict) and "$nin" in v:
                    if r.get(k) in set(v["$nin"]):
                        ok = False
                        break
                elif k == "$or":
                    ok_or = False
                    for q in v:
                        if all(r.get(k2) == v2 for k2, v2 in q.items()):
                            ok_or = True
                            break
                    if not ok_or:
                        ok = False
                        break
                elif r.get(k) != v:
                    ok = False
                    break
            if ok:
                return dict(r)
        return None

    async def update_one(self, query, update):
        for i, r in enumerate(self.rows):
            if all(r.get(k) == v for k, v in query.items()):
                nr = dict(r)
                nr.update((update or {}).get("$set") or {})
                self.rows[i] = nr
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)

    async def count_documents(self, query):
        c = 0
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                c += 1
        return c


class _Db:
    def __init__(self):
        self.tenant_requests = _Coll(
            [
                {
                    "request_id": "tr1",
                    "client_id": "c1",
                    "property_id": "p1",
                    "requirement_id": "req1",
                    "requirement_code": "gas_safety",
                    "status": "PENDING",
                    "tenant_name": "Tenant A",
                }
            ]
        )
        self.work_orders = _Coll([])
        self.documents = _Coll([])
        self.requirements = _Coll([])


@pytest.mark.asyncio
async def test_start_compliance_job_from_tenant_request_success(monkeypatch):
    db = _Db()
    monkeypatch.setattr(svc.database, "get_db", lambda: db)
    monkeypatch.setattr(svc, "create_audit_log", AsyncMock(return_value=None))
    monkeypatch.setattr(
        svc,
        "create_compliance_execution_work_order",
        AsyncMock(return_value={"work_order_id": "wo1", "client_id": "c1"}),
    )

    out = await svc.start_compliance_job_from_tenant_request(
        client_id="c1",
        tenant_request_id="tr1",
        actor_portal_user_id="pu1",
        actor_role="ROLE_CLIENT_ADMIN",
        allow_duplicate=False,
    )
    assert out["work_order"]["work_order_id"] == "wo1"
    tr = await db.tenant_requests.find_one({"request_id": "tr1", "client_id": "c1"})
    assert tr["linked_work_order_id"] == "wo1"
    assert tr["status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_start_compliance_job_duplicate_prevented(monkeypatch):
    db = _Db()
    db.work_orders.rows.append(
        {
            "work_order_id": "wo-existing",
            "client_id": "c1",
            "work_order_kind": "COMPLIANCE",
            "status": "ASSIGNED",
            "tenant_request_id": "tr1",
            "linked_property_requirement_id": "req1",
            "property_id": "p1",
        }
    )
    monkeypatch.setattr(svc.database, "get_db", lambda: db)
    monkeypatch.setattr(svc, "create_audit_log", AsyncMock(return_value=None))
    monkeypatch.setattr(
        svc,
        "create_compliance_execution_work_order",
        AsyncMock(return_value={"work_order_id": "wo-new", "client_id": "c1"}),
    )

    with pytest.raises(ValueError, match="active compliance job already exists"):
        await svc.start_compliance_job_from_tenant_request(
            client_id="c1",
            tenant_request_id="tr1",
            actor_portal_user_id="pu1",
            allow_duplicate=False,
        )

