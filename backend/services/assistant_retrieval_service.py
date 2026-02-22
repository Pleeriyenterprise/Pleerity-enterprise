"""
Retrieval for Compliance Vault Assistant: portal facts (minimal PII) + knowledge base snippets.
Used by /api/assistant/chat only. No web scraping; KB from curated markdown under backend/docs/assistant_kb/.
"""
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from database import database
from utils import ai_config

logger = logging.getLogger(__name__)

# KB directory from ASSISTANT_KB_PATH (default backend/docs/assistant_kb)
KB_DIR = ai_config.get_assistant_kb_path()

# Snippet shape for KB
def _snippet(source_id: str, title: str, content: str) -> Dict[str, Any]:
    return {
        "source_type": "kb",
        "source_id": source_id,
        "title": title,
        "content": content,
    }


async def get_portal_facts(
    client_id: str,
    user_role: str,
    property_id: Optional[str] = None,
    include_address_line: bool = False,
) -> Dict[str, Any]:
    """
    Minimal portal data for assistant context. PII minimization: nickname + postcode only
    unless include_address_line is True (e.g. user explicitly asked for address).
    """
    db = database.get_db()

    client = await db.clients.find_one(
        {"client_id": client_id},
        {
            "_id": 0,
            "client_id": 1,
            "customer_reference": 1,
            "billing_plan": 1,
            "subscription_status": 1,
            "client_type": 1,
        },
    )
    if not client:
        return {"error": "Client not found"}

    prop_projection = {
        "_id": 0,
        "property_id": 1,
        "nickname": 1,
        "postcode": 1,
    }
    if include_address_line:
        prop_projection["address_line_1"] = 1

    query = {"client_id": client_id}
    if property_id:
        query["property_id"] = property_id

    properties_cursor = db.properties.find(query, prop_projection).limit(100)
    properties = await properties_cursor.to_list(length=100)

    req_query = {"client_id": client_id}
    if property_id:
        req_query["property_id"] = property_id
    requirements = await db.requirements.find(
        req_query,
        {"_id": 0, "requirement_id": 1, "property_id": 1, "requirement_type": 1, "status": 1, "due_date": 1},
    ).to_list(1000)

    doc_query = {"client_id": client_id}
    if property_id:
        doc_query["property_id"] = property_id
    documents = await db.documents.find(
        doc_query,
        {
            "_id": 0,
            "document_id": 1,
            "property_id": 1,
            "file_name": 1,
            "status": 1,
            "uploaded_at": 1,
            "ai_extracted_data": 1,
        },
    ).sort("uploaded_at", -1).limit(100).to_list(length=100)

    # Build minimal requirement status per property
    req_by_prop: Dict[str, List[Dict[str, Any]]] = {}
    for r in requirements:
        pid = r.get("property_id") or "client"
        if pid not in req_by_prop:
            req_by_prop[pid] = []
        due = r.get("due_date")
        due_str = due.isoformat() if hasattr(due, "isoformat") else str(due) if due else None
        req_by_prop[pid].append({
            "requirement_type": r.get("requirement_type"),
            "status": r.get("status"),
            "due_date": due_str,
        })

    # Documents: type from file name or ai_extracted_data; extracted expiry if present
    doc_list = []
    for d in documents:
        extracted = d.get("ai_extracted_data") or {}
        expiry = extracted.get("expiry_date") or extracted.get("due_date")
        doc_list.append({
            "document_id": d.get("document_id"),
            "property_id": d.get("property_id"),
            "file_name": d.get("file_name"),
            "uploaded_at": d.get("uploaded_at").isoformat() if hasattr(d.get("uploaded_at"), "isoformat") else str(d.get("uploaded_at")),
            "status": d.get("status"),
            "extracted_expiry": expiry,
        })

    summary = {
        "client_id": client_id,
        "customer_reference": client.get("customer_reference"),
        "plan": client.get("billing_plan"),
        "subscription_status": client.get("subscription_status"),
        "client_type": client.get("client_type"),
    }

    return {
        "client_summary": summary,
        "properties": [
            {
                "property_id": p.get("property_id"),
                "nickname": p.get("nickname"),
                "postcode": p.get("postcode"),
                **({"address_line_1": p.get("address_line_1")} if include_address_line else {}),
            }
            for p in properties
        ],
        "requirements_by_property": req_by_prop,
        "documents": doc_list,
        "property_id_filter": property_id,
    }


def get_kb_snippets(query: str) -> List[Dict[str, Any]]:
    """
    Return KB snippets from backend/docs/assistant_kb/*.md.
    For MVP we return all snippets; query can be used later for simple keyword filtering.
    """
    snippets: List[Dict[str, Any]] = []
    if not KB_DIR.is_dir():
        logger.debug("KB dir not found: %s", KB_DIR)
        return snippets

    for path in sorted(KB_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            # Title: first # line or filename
            title = path.stem.replace("_", " ").replace("-", " ").title()
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            source_id = f"assistant_kb/{path.name}"
            snippets.append(_snippet(source_id=source_id, title=title, content=text[:8000]))
        except Exception as e:
            logger.warning("Failed to read KB file %s: %s", path, e)

    return snippets
