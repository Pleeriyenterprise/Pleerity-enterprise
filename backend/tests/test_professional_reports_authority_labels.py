from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_expiry_schedule_pdf_labels_calendar_scope(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)

    from services.professional_reports import ProfessionalReportGenerator
    from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE

    now = datetime.now(timezone.utc)
    branding_profile = MagicMock()
    branding_profile.to_report_dict.return_value = {
        "company_name": "Pleerity",
        "primary_color": "#0B1D3A",
        "secondary_color": "#00B8A9",
        "text_color": "#1F2937",
        "report_header_text": "",
        "report_footer_text": "",
        "pdf_attribution_lines": [],
        "pdf_footer_contact_line": "",
    }
    db = MagicMock()
    db.clients.find_one = AsyncMock(
        side_effect=[
            {"client_id": "c1", "full_name": "Client"},
            {"client_id": "c1", "default_jurisdiction": "England"},
        ]
    )
    db.properties.find = MagicMock(
        side_effect=[
            MagicMock(
                to_list=AsyncMock(
                    return_value=[
                        {"property_id": "p1", "client_id": "c1", "address_line_1": "1 Test Road", "jurisdiction": "England"}
                    ]
                )
            ),
            MagicMock(to_list=AsyncMock(return_value=[{"property_id": "p1", "client_id": "c1", "address_line_1": "1 Test Road"}])),
        ]
    )
    db.requirements.find = MagicMock(
        return_value=MagicMock(
            to_list=AsyncMock(
                return_value=[
                    {
                        "requirement_id": "r1",
                        "property_id": "p1",
                        "requirement_type": "EPC",
                        "status": "PENDING",
                        "due_date": (now + timedelta(days=10)).isoformat(),
                        "client_surface_visible": True,
                        "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
                    }
                ]
            )
        )
    )

    gen = ProfessionalReportGenerator()
    with patch("services.professional_reports.database.get_db", return_value=db), patch(
        "services.branding_resolver_service.resolve_branding",
        new_callable=AsyncMock,
        return_value=branding_profile,
    ):
        pdf = await gen.generate_expiry_schedule_pdf("c1", days=30)

    raw = pdf.getvalue()
    assert b"Expiry Schedule Report" in raw
    assert b"Schedule view only" in raw
    assert b"Schedule status" in raw
