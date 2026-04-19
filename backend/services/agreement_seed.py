"""Bootstrap default CVP service agreement template and document settings (idempotent)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from database import database
from models.agreements import (
    COL_AGREEMENT_TEMPLATES,
    COL_AGREEMENT_TEMPLATE_VERSIONS,
    COL_SYSTEM_DOCUMENT_SETTINGS,
    DEFAULT_TEMPLATE_CODE,
)
from services.agreement_catalog_service import SETTINGS_DOC_ID

logger = logging.getLogger(__name__)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


DEFAULT_BLOCKS: list[dict[str, Any]] = [
    {
        "key": "parties",
        "label": "Parties",
        "type": "rich_text",
        "required": True,
        "order": 1,
        "enabled": True,
        "content": (
            "This Service Agreement is made between {{provider_company_name}} (\"Provider\") "
            "and {{client_full_name}} (\"Client\"), company name if applicable: {{client_company_name}}, "
            "email {{client_email}}."
        ),
    },
    {
        "key": "service_plan",
        "label": "Plan and fees",
        "type": "rich_text",
        "required": True,
        "order": 2,
        "enabled": True,
        "content": (
            "Client selects <strong>{{plan_name}}</strong> billed <strong>{{billing_interval}}</strong> at "
            "<strong>{{monthly_fee}}</strong> ({{currency}}). Setup fee (if applicable): {{onboarding_fee_line}}."
        ),
    },
    {
        "key": "property_context",
        "label": "Client details",
        "type": "rich_text",
        "required": True,
        "order": 3,
        "enabled": True,
        "content": "Primary property / correspondence address: {{client_address}}.",
    },
    {
        "key": "electronic_acceptance",
        "label": "Electronic acceptance",
        "type": "rich_text",
        "required": True,
        "order": 4,
        "enabled": True,
        "content": (
            "Accepted electronically by {{accepted_signatory_name}}. "
            "Acceptance recorded at {{acceptance_timestamp}} for agreement version {{agreement_version}}."
        ),
    },
]


async def ensure_default_agreement_assets() -> None:
    db = database.get_db()
    existing = await db[COL_AGREEMENT_TEMPLATES].find_one({"code": DEFAULT_TEMPLATE_CODE}, {"_id": 0, "template_id": 1})
    if existing and existing.get("template_id"):
        await db[COL_SYSTEM_DOCUMENT_SETTINGS].update_one(
            {"settings_id": SETTINGS_DOC_ID},
            {
                "$setOnInsert": {
                    "settings_id": SETTINGS_DOC_ID,
                    "provider_company_name": "Pleerity Enterprise Ltd",
                    "provider_tagline": "AI-Driven Solutions & Compliance.",
                    "provider_address": "8 Valley Court, Hamilton ML3 8HW",
                    "provider_email": "info@pleerityenterprise.co.uk",
                    "provider_phone": "02033376060",
                    "provider_signature_image_url": "",
                    "provider_logo_image_url": "",
                    "brand_primary_color": "#0B1D3A",
                    "brand_secondary_color": "#00B8A9",
                    "default_footer_text": "Pleerity Enterprise Ltd – AI-Driven Solutions & Compliance.",
                    "created_at": _utc(),
                }
            },
            upsert=True,
        )
        return

    template_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    now = _utc()

    version_doc: Dict[str, Any] = {
        "version_id": version_id,
        "template_id": template_id,
        "version_number": 1,
        "status": "published",
        "title": "Property Compliance Management Agreement",
        "subtitle": "(Compliance Vault Pro Service)",
        "content_blocks": DEFAULT_BLOCKS,
        "placeholders": [],
        "effective_from": now,
        "published_at": now,
        "published_by": {"user_id": "system", "name": "System seed"},
        "change_notes": "Initial seeded published version",
        "created_at": now,
    }

    template_doc: Dict[str, Any] = {
        "template_id": template_id,
        "code": DEFAULT_TEMPLATE_CODE,
        "name": "Property Compliance Management Agreement",
        "description": "Default recurring agreement for Compliance Vault Pro clients",
        "category": "service_agreement",
        "status": "active",
        "current_published_version_id": version_id,
        "created_at": now,
        "updated_at": now,
        "created_by": {"user_id": "system", "name": "System seed"},
    }

    await db[COL_AGREEMENT_TEMPLATE_VERSIONS].insert_one(version_doc)
    await db[COL_AGREEMENT_TEMPLATES].insert_one(template_doc)

    await db[COL_SYSTEM_DOCUMENT_SETTINGS].update_one(
        {"settings_id": SETTINGS_DOC_ID},
        {
            "$setOnInsert": {
                "settings_id": SETTINGS_DOC_ID,
                "provider_company_name": "Pleerity Enterprise Ltd",
                "provider_tagline": "AI-Driven Solutions & Compliance.",
                "provider_address": "8 Valley Court, Hamilton ML3 8HW",
                "provider_email": "info@pleerityenterprise.co.uk",
                "provider_phone": "02033376060",
                "provider_signature_image_url": "",
                "provider_logo_image_url": "",
                "brand_primary_color": "#0B1D3A",
                "brand_secondary_color": "#00B8A9",
                "default_footer_text": "Pleerity Enterprise Ltd – AI-Driven Solutions & Compliance.",
                "created_at": now,
            }
        },
        upsert=True,
    )
    logger.info("Seeded default agreement template %s version %s", DEFAULT_TEMPLATE_CODE, version_id)
