"""
Ranked retrieval from support_public_content_chunks for public support chat.
KC (kb_article) preferred over site_page; legacy static Q&A remains in support_chatbot_retrieval.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from database import database

from services.support_chatbot_retrieval import _normalize
from services.support_public_content_index_service import SUPPORT_PUBLIC_CONTENT_CHUNKS
from utils.app_urls import get_app_base_url

logger = logging.getLogger(__name__)

# Slightly below static Q&A threshold: KC excerpts are longer than keyword rows.
KC_MATCH_THRESHOLD = 0.24
SITE_MATCH_THRESHOLD = 0.17

# Scan recent chunks first (bounded work per chat turn — no full collection scan).
MAX_KB_CHUNKS_SCAN = 280
MAX_SITE_CHUNKS_SCAN = 160


def _score_chunk(query_norm: str, doc: Dict[str, Any]) -> float:
    if not query_norm:
        return 0.0
    qw = set(query_norm.split())
    if not qw:
        return 0.0
    blob = _normalize(
        f"{doc.get('title') or ''} {' '.join(doc.get('topic_tags') or [])} {doc.get('chunk_text') or ''}"
    )
    if not blob:
        return 0.0
    score = 0.0
    for w in qw:
        if len(w) < 2:
            continue
        if w in blob:
            score += 1.0
    return score / max(len(qw), 1)


def _context_boost_for_chunk(doc: Dict[str, Any], ctx: Optional[Dict[str, Any]]) -> float:
    if not ctx:
        return 1.0
    topic = (ctx.get("intent") or ctx.get("topic") or "").lower()
    tags = [t.lower() for t in (doc.get("topic_tags") or [])]
    if not topic:
        return 1.0
    if topic in tags or any(topic in t for t in tags):
        return 1.2
    if topic in ("compliance_vault_pro", "cvp") and any("cvp" in t or "compliance" in t for t in tags):
        return 1.15
    if topic == "pricing" and "pricing" in tags:
        return 1.15
    return 1.0


async def _load_and_score(
    *,
    source_type: str,
    message: str,
    ctx: Optional[Dict[str, Any]],
    scan_limit: int,
) -> List[Tuple[float, Dict[str, Any]]]:
    db = database.get_db()
    qn = _normalize(message)
    cursor = (
        db[SUPPORT_PUBLIC_CONTENT_CHUNKS]
        .find({"source_type": source_type}, {"_id": 0})
        .sort("indexed_at", -1)
        .limit(scan_limit)
    )
    scored: List[Tuple[float, Dict[str, Any]]] = []
    async for doc in cursor:
        base = _score_chunk(qn, doc)
        if base <= 0:
            continue
        adj = base * _context_boost_for_chunk(doc, ctx)
        scored.append((adj, doc))
    scored.sort(key=lambda x: -x[0])
    return scored


def _body_conversational_preview(body: str, max_chars: int = 420) -> str:
    """Strip heading lines and return a readable excerpt (not a raw chunk dump)."""
    raw = (body or "").replace("\r\n", "\n").strip()
    if not raw:
        return ""
    lines_out: List[str] = []
    for line in raw.split("\n"):
        s = line.strip()
        if s.startswith("#"):
            continue
        if s == "---":
            break
        lines_out.append(line.rstrip())
    text = "\n".join(lines_out).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_sp = cut.rfind(" ")
    if last_sp > max_chars * 0.55:
        cut = cut[:last_sp]
    return cut.rstrip(" ,;:") + "…"


def _build_kb_response_text(top_docs: List[Dict[str, Any]]) -> str:
    """Conversational gist + optional read-more; full text stays behind CTA."""
    d0 = top_docs[0]
    title = (d0.get("title") or "this article").strip()
    body = _body_conversational_preview(d0.get("chunk_text") or "", 420)
    if not body:
        return ""
    lines = [
        f"Here's the gist from **{title}**:\n\n{body}",
        "",
        "For the full walkthrough, open **Read full article** below.",
    ]
    return "\n".join(lines).rstrip() + "\n\n_From Knowledge Centre._"


def _build_site_response_text(top_docs: List[Dict[str, Any]]) -> str:
    d = top_docs[0]
    title = (d.get("title") or "this page").strip()
    body = _body_conversational_preview(d.get("chunk_text") or "", 380)
    url = (d.get("url") or "").strip()
    if not body and not url:
        return ""
    parts: List[str] = []
    if body:
        parts.append(f"From our website (**{title}**):\n\n{body}")
    if url:
        parts.append(f"\n\nRead more: {url}")
    text = "\n".join(parts).strip()
    if text:
        text += "\n\n_From website content._"
    return text


def _sources_from_docs(docs: List[Dict[str, Any]], source_type: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for d in docs:
        if source_type == "kb_article":
            out.append(
                {
                    "source_type": "kb_article",
                    "article_id": d.get("source_id"),
                    "slug": d.get("slug"),
                    "title": d.get("title"),
                }
            )
        else:
            out.append(
                {
                    "source_type": "site_page",
                    "url": d.get("url"),
                    "title": d.get("title"),
                    "source_id": d.get("source_id"),
                }
            )
    return out


async def try_public_support_content_answer(
    message: str,
    conversation_context: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    If indexed KC (or site) chunks match strongly, return a handler dict for support_chatbot.
    Otherwise None. Does not query live website — reads Mongo chunks only.
    """
    ctx = dict(conversation_context) if conversation_context else None
    kb_scored = await _load_and_score(
        source_type="kb_article", message=message, ctx=ctx, scan_limit=MAX_KB_CHUNKS_SCAN
    )
    site_scored = await _load_and_score(
        source_type="site_page", message=message, ctx=ctx, scan_limit=MAX_SITE_CHUNKS_SCAN
    )

    best_kb = kb_scored[0] if kb_scored else None
    best_site = site_scored[0] if site_scored else None

    kb_raw = best_kb[0] if best_kb else 0.0
    site_raw = best_site[0] if best_site else 0.0

    # KC first when above threshold; website only if KC does not qualify (same-topic preference).
    use_kb = bool(best_kb and kb_raw >= KC_MATCH_THRESHOLD)

    if use_kb and best_kb:
        docs = [best_kb[1]]
        if len(kb_scored) > 1 and kb_scored[1][0] >= KC_MATCH_THRESHOLD * 0.85:
            docs.append(kb_scored[1][1])
        response = _build_kb_response_text(docs)
        if not response:
            return None
        base = get_app_base_url(for_email_links=True).rstrip("/")
        slug = docs[0].get("slug")
        actions: List[Dict[str, Any]] = []
        if slug:
            actions.append({"label": "Read full article", "url": f"{base}/support/knowledge-base/{slug}"})
        return {
            "response": response,
            "action": "respond",
            "metadata": {
                "kc_article_matched": True,
                "public_content_retrieval": True,
                "conversational_synthesis": True,
                "sources": _sources_from_docs(docs, "kb_article"),
                "retrieval_path": ["kc_article"],
                "_synthesis_context": [
                    {
                        "title": (d.get("title") or "").strip(),
                        "excerpt": _body_conversational_preview(d.get("chunk_text") or "", 720),
                    }
                    for d in docs[:2]
                ],
            },
            "conversation_context": ctx,
            "actions": actions or None,
        }

    if best_site and site_raw >= SITE_MATCH_THRESHOLD and not use_kb:
        docs = [best_site[1]]
        response = _build_site_response_text(docs)
        if not response:
            return None
        return {
            "response": response,
            "action": "respond",
            "metadata": {
                "site_page_matched": True,
                "public_content_retrieval": True,
                "conversational_synthesis": True,
                "sources": _sources_from_docs(docs, "site_page"),
                "retrieval_path": ["site_page"],
                "_synthesis_context": [
                    {
                        "title": (d.get("title") or "").strip(),
                        "excerpt": _body_conversational_preview(d.get("chunk_text") or "", 720),
                    }
                    for d in docs[:1]
                ],
            },
            "conversation_context": ctx,
            "actions": None,
        }

    return None
