"""
Retrieval for Compliance Vault Assistant: portal facts (minimal PII) + knowledge base snippets.
Used by /api/assistant/chat only. No web scraping; KB from curated markdown under backend/docs/assistant_kb/.
"""
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from database import database
from utils import ai_config

logger = logging.getLogger(__name__)

# KB directory from ASSISTANT_KB_PATH (default backend/docs/assistant_kb)
KB_DIR = ai_config.get_assistant_kb_path()

# Top N snippets returned by ranking (MVP)
KB_TOP_N = 3


class Snippet(TypedDict):
    """KB snippet with source_id, title, content, and relevance score."""
    source_id: str
    title: str
    content: str
    score: float


# In-memory cache: list of (source_id, title, content) loaded from .md files
_KB_CACHE: Optional[List[tuple]] = None
_KB_CACHE_DIR: Optional[Path] = None


def _load_kb_into_cache() -> List[tuple]:
    """Load all .md files from KB_DIR into cache. Returns list of (source_id, title, content)."""
    global _KB_CACHE, _KB_CACHE_DIR
    if _KB_CACHE is not None and _KB_CACHE_DIR == KB_DIR:
        return _KB_CACHE
    _KB_CACHE_DIR = KB_DIR
    _KB_CACHE = []
    if not KB_DIR.is_dir():
        logger.debug("KB dir not found: %s", KB_DIR)
        return _KB_CACHE
    for path in sorted(KB_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            title = path.stem.replace("_", " ").replace("-", " ").title()
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            source_id = f"assistant_kb/{path.name}"
            _KB_CACHE.append((source_id, title, text[:8000]))
        except Exception as e:
            logger.warning("Failed to read KB file %s: %s", path, e)
    return _KB_CACHE


def _keyword_overlap_score(query: str, text: str) -> float:
    """Case-insensitive keyword overlap: number of query words that appear in text."""
    words = set(re.findall(r"[a-z0-9]+", query.lower()))
    if not words:
        return 0.0
    text_lower = text.lower()
    matches = sum(1 for w in words if w in text_lower)
    return float(matches) / len(words) if words else 0.0


def load_kb_snippets(query: str) -> List[Snippet]:
    """
    Load all .md from backend/docs/assistant_kb/ from cache; rank by keyword overlap with query;
    return top KB_TOP_N snippets with source_id, title, content (trimmed), score.
    """
    raw = _load_kb_into_cache()
    if not raw:
        return []
    scored: List[tuple] = []
    for source_id, title, content in raw:
        score = _keyword_overlap_score(query, f"{title} {content}")
        scored.append((score, source_id, title, content))
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = scored[:KB_TOP_N]
    return [
        Snippet(source_id=sid, title=t, content=c.strip(), score=sc)
        for sc, sid, t, c in top
    ]


def _snippet_dict(source_id: str, title: str, content: str, score: float = 0.0) -> Dict[str, Any]:
    return {
        "source_type": "kb",
        "source_id": source_id,
        "title": title,
        "content": content,
        "score": score,
    }


async def get_portal_facts(
    client_id: str,
    user_role: str,
    property_id: Optional[str] = None,
    include_address_line: bool = False,
    portal_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Minimal portal data for assistant context. PII minimization: nickname + postcode only
    unless include_address_line is True (e.g. user explicitly asked for address).
    When portal_user_id is provided, user/account_state are scoped to that portal user.
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
            "onboarding_status": 1,
            "provisioning_status": 1,
            "activation_email_status": 1,
            "activation_email_sent_at": 1,
            "email": 1,
            "full_name": 1,
        },
    )
    if not client:
        return {"error": "Client not found"}

    # Portal user for user + account_state (optional portal_user_id to scope to current user)
    pu_query: Dict[str, Any] = {"client_id": client_id}
    if portal_user_id:
        pu_query["portal_user_id"] = portal_user_id
    portal_user = await db.portal_users.find_one(
        pu_query,
        {"_id": 0, "portal_user_id": 1, "auth_email": 1, "role": 1, "password_status": 1},
    )

    prop_projection = {
        "_id": 0,
        "property_id": 1,
        "nickname": 1,
        "postcode": 1,
        "compliance_score": 1,
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

    # user: name, email, role, CRN (minimal for assistant context)
    name = client.get("full_name") or client.get("name") or ((portal_user or {}).get("auth_email") or "").split("@")[0] or ""
    email = (portal_user or {}).get("auth_email") or client.get("email") or ""
    role = (portal_user or {}).get("role") or "ROLE_CLIENT"
    user_blob = {"name": name, "email": email, "role": role, "crn": client.get("customer_reference") or ""}

    # account_state: payment_state, provisioning_status, portal_user_exists, activation_email_status, password_set
    sub = (client.get("subscription_status") or "").strip().upper()
    payment_state = "paid" if sub in ("ACTIVE", "TRIALING") else "unpaid" if sub in ("PAST_DUE", "CANCELED", "UNPAID") else "pending"
    onb = (client.get("onboarding_status") or "").strip()
    prov = (client.get("provisioning_status") or "").strip() or ("COMPLETED" if onb == "PROVISIONED" else "IN_PROGRESS" if onb == "PROVISIONING" else "FAILED" if onb == "FAILED" else "NOT_STARTED")
    act = (client.get("activation_email_status") or "").strip().upper()
    activation_email_status = act if act in ("SENT", "FAILED", "NOT_SENT") else "NOT_SENT"
    password_set = bool(portal_user and ((portal_user.get("password_status") or "").upper() == "SET"))
    account_state = {
        "payment_state": payment_state,
        "provisioning_status": prov,
        "portal_user_exists": bool(portal_user),
        "activation_email_status": activation_email_status,
        "password_set": password_set,
    }

    # portfolio_summary: counts and high-level view (scores if available)
    property_count = len(properties)
    req_count = len(requirements)
    doc_count = len(documents)
    today = datetime.now(timezone.utc).date().isoformat()
    def _is_overdue(r: Dict[str, Any]) -> bool:
        due = r.get("due_date")
        if not due:
            return False
        if hasattr(due, "date"):
            due_str = due.date().isoformat() if hasattr(due, "date") else str(due)[:10]
        else:
            due_str = str(due)[:10]
        return due_str < today

    overdue = sum(1 for r in requirements if _is_overdue(r))
    expiring_soon_count = sum(
        1 for r in requirements
        if (r.get("status") or "").strip().upper() == "EXPIRING_SOON"
    )
    compliant_count = sum(
        1 for r in requirements
        if (r.get("status") or "").strip().upper() == "COMPLIANT"
    )
    scores = [p.get("compliance_score") for p in properties if p.get("compliance_score") is not None]
    score_portfolio = round(sum(scores) / len(scores), 1) if scores else None
    scores_by_property = {
        p.get("property_id"): p.get("compliance_score")
        for p in properties
        if p.get("property_id") and p.get("compliance_score") is not None
    }
    portfolio_summary = {
        "property_count": property_count,
        "requirement_count": req_count,
        "document_count": doc_count,
        "overdue_requirements_count": overdue,
        "expiring_soon_count": expiring_soon_count,
        "compliant_count": compliant_count,
        "score_portfolio": score_portfolio,
        "scores_by_property": scores_by_property,
    }

    # notification_prefs for assistant context (task: email_enabled, sms_enabled, reminder_timing_days, recipients)
    notif_doc = await db.notification_preferences.find_one(
        {"client_id": client_id},
        {"_id": 0, "expiry_reminders": 1, "sms_enabled": 1, "reminder_days_before": 1},
    )
    notification_prefs: Dict[str, Any] = {
        "email_enabled": bool(notif_doc.get("expiry_reminders", True) if notif_doc else True),
        "sms_enabled": bool(notif_doc.get("sms_enabled", False) if notif_doc else False),
        "reminder_timing_days": notif_doc.get("reminder_days_before", 30) if notif_doc else 30,
        "recipients": [],
    }

    return {
        "client_summary": summary,
        "user": user_blob,
        "account_state": account_state,
        "portfolio_summary": portfolio_summary,
        "notification_prefs": notification_prefs,
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
    Return top KB_TOP_N KB snippets ranked by keyword overlap with query.
    Uses in-memory cache of backend/docs/assistant_kb/*.md. Each item includes
    source_id, title, content, score for citations.
    """
    snippets_list = load_kb_snippets(query)
    return [_snippet_dict(s["source_id"], s["title"], s["content"], s["score"]) for s in snippets_list]
