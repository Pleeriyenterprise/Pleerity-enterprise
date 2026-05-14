"""
Knowledge Base article-level feedback (helpful / not helpful).

Separate from ``assistant_feedback`` (help-assistant Q&A). Designed for
analytics: per-article aggregates, time windows, dedupe by voter.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from pymongo.errors import DuplicateKeyError

from database import database

logger = logging.getLogger(__name__)

KB_ARTICLE_FEEDBACK_COLLECTION = "kb_article_feedback"

_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,128}$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def ensure_kb_article_feedback_indexes() -> None:
    db = database.get_db()
    coll = db[KB_ARTICLE_FEEDBACK_COLLECTION]
    await coll.create_index([("article_id", 1), ("dedupe_key", 1)], unique=True)
    await coll.create_index([("created_at", -1)])
    await coll.create_index([("article_id", 1), ("created_at", -1)])
    await coll.create_index([("source_surface", 1), ("created_at", -1)])


def _validate_session_id(session_id: str) -> Optional[str]:
    if not session_id or not _SESSION_ID_RE.match(session_id.strip()):
        return None
    return session_id.strip()


def _build_dedupe_key(*, portal_user_id: Optional[str], session_id: Optional[str]) -> Tuple[str, str]:
    """
    One vote per article per authenticated portal user, else one per anonymous session.
    Returns (dedupe_key, voter_kind).
    """
    if portal_user_id:
        return f"user:{portal_user_id}", "authenticated"
    sid = _validate_session_id(session_id or "")
    if not sid:
        raise ValueError("session_id_required")
    return f"session:{sid}", "anonymous"


async def _totals_for_article(db, article_id: str) -> Dict[str, Any]:
    coll = db[KB_ARTICLE_FEEDBACK_COLLECTION]
    pipeline = [
        {"$match": {"article_id": article_id}},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "helpful": {"$sum": {"$cond": [{"$eq": ["$feedback_type", "helpful"]}, 1, 0]}},
                "not_helpful": {"$sum": {"$cond": [{"$eq": ["$feedback_type", "not_helpful"]}, 1, 0]}},
            }
        },
    ]
    rows = await coll.aggregate(pipeline).to_list(length=1)
    if not rows:
        return {"total": 0, "helpful": 0, "not_helpful": 0, "helpful_pct": None}
    r = rows[0]
    total = int(r.get("total") or 0)
    helpful = int(r.get("helpful") or 0)
    not_helpful = int(r.get("not_helpful") or 0)
    pct = round(100.0 * helpful / total, 2) if total > 0 else None
    return {"total": total, "helpful": helpful, "not_helpful": not_helpful, "helpful_pct": pct}


async def submit_article_feedback(
    *,
    article_id: str,
    feedback_type: str,
    source_surface: str,
    session_id: Optional[str],
    portal_user_id: Optional[str],
    article_snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Insert one feedback row if not duplicate. Never overwrites an existing vote.

    ``article_snapshot`` must include slug, title, category_id, audience (for analytics slice).
    """
    if feedback_type not in ("helpful", "not_helpful"):
        raise ValueError("invalid_feedback_type")

    await ensure_kb_article_feedback_indexes()
    db = database.get_db()
    coll = db[KB_ARTICLE_FEEDBACK_COLLECTION]

    dedupe_key, voter_kind = _build_dedupe_key(portal_user_id=portal_user_id, session_id=session_id)

    existing = await coll.find_one({"article_id": article_id, "dedupe_key": dedupe_key}, {"_id": 1})
    if existing:
        totals = await _totals_for_article(db, article_id)
        return {
            "ok": True,
            "duplicate": True,
            "article_id": article_id,
            "totals": totals,
        }

    doc = {
        "feedback_id": f"kbf-{uuid.uuid4().hex[:12]}",
        "article_id": article_id,
        "article_slug": article_snapshot.get("slug") or "",
        "article_title_snapshot": (article_snapshot.get("title") or "")[:300],
        "article_audience_snapshot": article_snapshot.get("audience") or "USER",
        "article_category_id": article_snapshot.get("category_id"),
        "feedback_type": feedback_type,
        "user_id": portal_user_id,
        "session_fingerprint": None if portal_user_id else _validate_session_id(session_id or ""),
        "dedupe_key": dedupe_key,
        "voter_kind": voter_kind,
        "source_surface": source_surface,
        "created_at": _now_iso(),
    }

    try:
        await coll.insert_one(doc)
    except DuplicateKeyError:
        logger.info("kb_article_feedback duplicate race article_id=%s dedupe=%s", article_id, dedupe_key)
        totals = await _totals_for_article(db, article_id)
        return {"ok": True, "duplicate": True, "article_id": article_id, "totals": totals}

    totals = await _totals_for_article(db, article_id)
    return {"ok": True, "duplicate": False, "article_id": article_id, "totals": totals}


async def aggregate_feedback_summary(*, days: int = 30, low_rated_limit: int = 25) -> Dict[str, Any]:
    """
    Global totals plus per-article rows for admin (analytics-ready).
    """
    await ensure_kb_article_feedback_indexes()
    db = database.get_db()
    coll = db[KB_ARTICLE_FEEDBACK_COLLECTION]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    match = {"created_at": {"$gte": cutoff}}

    global_pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": None,
                "votes": {"$sum": 1},
                "helpful": {"$sum": {"$cond": [{"$eq": ["$feedback_type", "helpful"]}, 1, 0]}},
                "not_helpful": {"$sum": {"$cond": [{"$eq": ["$feedback_type", "not_helpful"]}, 1, 0]}},
            }
        },
    ]
    g = await coll.aggregate(global_pipeline).to_list(length=1)
    totals = {"votes": 0, "helpful": 0, "not_helpful": 0, "helpful_pct": None}
    if g:
        votes = int(g[0].get("votes") or 0)
        helpful = int(g[0].get("helpful") or 0)
        not_helpful = int(g[0].get("not_helpful") or 0)
        pct = round(100.0 * helpful / votes, 2) if votes > 0 else None
        totals = {"votes": votes, "helpful": helpful, "not_helpful": not_helpful, "helpful_pct": pct}

    by_article_pipeline: List[Dict[str, Any]] = [
        {"$match": match},
        {
            "$group": {
                "_id": "$article_id",
                "votes": {"$sum": 1},
                "helpful": {"$sum": {"$cond": [{"$eq": ["$feedback_type", "helpful"]}, 1, 0]}},
                "not_helpful": {"$sum": {"$cond": [{"$eq": ["$feedback_type", "not_helpful"]}, 1, 0]}},
                "slug": {"$last": "$article_slug"},
                "title": {"$last": "$article_title_snapshot"},
            }
        },
        {"$match": {"votes": {"$gte": 1}}},
        {"$sort": {"not_helpful": -1, "votes": -1}},
        {"$limit": low_rated_limit},
    ]
    articles: List[Dict[str, Any]] = []
    async for row in coll.aggregate(by_article_pipeline):
        votes = int(row.get("votes") or 0)
        helpful = int(row.get("helpful") or 0)
        not_helpful = int(row.get("not_helpful") or 0)
        pct = round(100.0 * helpful / votes, 2) if votes > 0 else None
        articles.append(
            {
                "article_id": row["_id"],
                "slug": row.get("slug"),
                "title": row.get("title"),
                "votes": votes,
                "helpful": helpful,
                "not_helpful": not_helpful,
                "helpful_pct": pct,
            }
        )

    lowest_helpful_pct = sorted(
        [a for a in articles if a.get("votes", 0) >= 3 and a.get("helpful_pct") is not None],
        key=lambda x: x.get("helpful_pct", 100),
    )[:10]

    return {
        "period_days": days,
        "totals": totals,
        "articles": articles,
        "lowest_helpful_pct_articles": lowest_helpful_pct,
    }
