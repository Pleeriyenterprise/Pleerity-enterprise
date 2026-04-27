import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from database import database as db_singleton
from services.compliance_pack import compliance_pack_service


def test_compliance_pack_uses_authoritative_status_labels():
    mock_db = MagicMock()
    property_doc = {
        "property_id": "p1",
        "client_id": "c1",
        "address_line_1": "Laurel Gardens",
        "city": "London",
        "postcode": "E1 1AA",
    }
    reqs = [
        {
            "requirement_id": "r1",
            "requirement_type": "gas_safety",
            "status": "OVERDUE",
            "mandatory": True,
        }
    ]

    async def find_one(q, *_a, **_k):
        if q.get("property_id") == "p1":
            return property_doc
        if q.get("client_id") == "c1":
            return {"client_id": "c1", "company_name": "Premier PM"}
        return None

    mock_db.properties.find_one = AsyncMock(side_effect=find_one)
    mock_db.clients.find_one = AsyncMock(side_effect=find_one)
    mock_db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=reqs)))
    mock_db.documents.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))

    captured = {"table_data": None}

    class FakeTable:
        def __init__(self, data, *args, **kwargs):
            captured["table_data"] = data

        def setStyle(self, *_a, **_k):
            return None

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch(
            "services.requirement_client_runtime_surface.filter_requirement_rows_for_client_runtime_surfaces",
            new=AsyncMock(return_value=reqs),
        ),
        patch("services.compliance_pack.Table", new=FakeTable),
        patch("services.compliance_pack.create_audit_log", new=AsyncMock(return_value="aud1")),
        patch("reportlab.platypus.doctemplate.BaseDocTemplate.build", return_value=None),
    ):
        asyncio.run(
            compliance_pack_service.generate_compliance_pack(
                property_id="p1",
                client_id="c1",
                include_expired=False,
                requested_by="u1",
                requested_by_role="ROLE_CLIENT_ADMIN",
            )
        )

    assert captured["table_data"] is not None
    status_row = next((row for row in captured["table_data"] if row[0] == "Overall Status"), None)
    assert status_row is not None
    assert status_row[1] in {"COMPLIANT", "PARTIALLY COMPLIANT", "ACTION REQUIRED", "HIGH RISK"}

