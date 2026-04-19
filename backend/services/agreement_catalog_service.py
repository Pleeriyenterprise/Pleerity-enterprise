"""Read-only access to agreement templates and published versions."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from database import database
from models.agreements import (
    COL_AGREEMENT_TEMPLATES,
    COL_AGREEMENT_TEMPLATE_VERSIONS,
    COL_SYSTEM_DOCUMENT_SETTINGS,
    DEFAULT_TEMPLATE_CODE,
)

def _col(db, name: str):
    return db[name]

logger = logging.getLogger(__name__)

SETTINGS_DOC_ID = "doc_settings_default"


async def get_system_document_settings() -> Dict[str, Any]:
    db = database.get_db()
    doc = await _col(db, COL_SYSTEM_DOCUMENT_SETTINGS).find_one({"settings_id": SETTINGS_DOC_ID}, {"_id": 0})
    if not doc:
        return {}
    return doc


async def get_template_by_code(code: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    return await _col(db, COL_AGREEMENT_TEMPLATES).find_one({"code": code.strip()}, {"_id": 0})


async def get_published_version_for_template(template_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    t = await _col(db, COL_AGREEMENT_TEMPLATES).find_one({"template_id": template_id}, {"_id": 0})
    if not t:
        return None
    vid = (t.get("current_published_version_id") or "").strip()
    if not vid:
        return None
    ver = await _col(db, COL_AGREEMENT_TEMPLATE_VERSIONS).find_one({"version_id": vid, "template_id": template_id}, {"_id": 0})
    if not ver or ver.get("status") != "published":
        return None
    return ver


async def get_version_by_id(version_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    return await _col(db, COL_AGREEMENT_TEMPLATE_VERSIONS).find_one({"version_id": version_id}, {"_id": 0})


async def resolve_published_by_template_code(
    template_code: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Returns (template_doc, version_doc) for current published chain.
    """
    tpl = await get_template_by_code(template_code)
    if not tpl:
        return None, None
    tid = tpl.get("template_id")
    if not tid:
        return None, None
    ver = await get_published_version_for_template(str(tid))
    if not ver:
        return tpl, None
    return tpl, ver


async def get_current_published_bundle(
    template_code: str = DEFAULT_TEMPLATE_CODE,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    return await resolve_published_by_template_code(template_code)


def acceptance_text_default(template_name: str) -> str:
    return (
        f"I have read and agree to the {template_name} and understand it forms part of my subscription."
    )
