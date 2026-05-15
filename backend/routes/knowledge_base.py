"""
Knowledge Base / Knowledge & Training Centre

Public endpoints: USER audience articles only.
Admin endpoints: full CRUD, all audiences.
Client Help Centre (/api/client/help): authenticated users, USER articles only.

Features: CRUD, audience (ADMIN|STAFF|USER), categories by scope, version, summary,
draft/publish/archive, search + analytics, PDF export, audit logging.
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from middleware import admin_route_guard, client_route_guard, get_current_user
from database import database
from services import kb_article_feedback_service as kb_article_feedback_svc
import logging
import uuid
import json
import re
import io

logger = logging.getLogger(__name__)

public_router = APIRouter(prefix="/api/kb", tags=["knowledge-base-public"])
admin_router = APIRouter(prefix="/api/admin/kb", tags=["admin-knowledge-base"])
client_help_router = APIRouter(prefix="/api/client/help", tags=["client-help-centre"])

ARTICLES_COLLECTION = "kb_articles"
CATEGORIES_COLLECTION = "kb_categories"
SEARCH_ANALYTICS_COLLECTION = "kb_search_analytics"
FEEDBACK_COLLECTION = "assistant_feedback"


async def sync_public_support_index_for_kb_article(article_id: str) -> None:
    """Keep support_public_content_chunks aligned with strict USER published articles."""
    try:
        from services.support_public_content_index_service import reindex_kb_article_by_id

        await reindex_kb_article_by_id(article_id)
    except Exception as e:
        logger.warning("sync_public_support_index_for_kb_article(%s): %s", article_id, e)


# Help Assistant: fallback when no published docs match (doc-grounded only)
HELP_ASSISTANT_FALLBACK = (
    "I couldn't find a confirmed answer in the current help documentation. "
    "Try different keywords or browse the categories below. This is based on current help documentation only, not legal advice."
)
HELP_ASSISTANT_TOP_N = 5


class ArticleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ArticleAudience(str, Enum):
    ADMIN = "ADMIN"
    STAFF = "STAFF"
    USER = "USER"


# ADMIN Knowledge Centre categories (task)
DEFAULT_CATEGORIES_ADMIN = [
    {"id": "staff-training", "name": "Staff Training", "icon": "📚", "order": 1, "audience": "ADMIN"},
    {"id": "operations-playbooks", "name": "Operations Playbooks", "icon": "📋", "order": 2, "audience": "ADMIN"},
    {"id": "admin-console", "name": "Admin Console", "icon": "⚙️", "order": 3, "audience": "ADMIN"},
    {"id": "provisioning", "name": "Provisioning", "icon": "🔧", "order": 4, "audience": "ADMIN"},
    {"id": "compliance-engine", "name": "Compliance Engine", "icon": "✅", "order": 5, "audience": "ADMIN"},
    {"id": "job-monitoring", "name": "Job Monitoring", "icon": "📊", "order": 6, "audience": "ADMIN"},
    {"id": "feature-flags", "name": "Feature Flags", "icon": "🚩", "order": 7, "audience": "ADMIN"},
    {"id": "support-procedures", "name": "Support Procedures", "icon": "🎧", "order": 8, "audience": "ADMIN"},
    {"id": "release-notes", "name": "Release Notes", "icon": "📦", "order": 9, "audience": "ADMIN"},
]

# USER Help Centre categories (task)
DEFAULT_CATEGORIES_USER = [
    {"id": "getting-started", "name": "Getting Started", "icon": "🚀", "order": 1, "audience": "USER"},
    {"id": "adding-properties", "name": "Adding Properties", "icon": "🏠", "order": 2, "audience": "USER"},
    {"id": "documents-uploads", "name": "Uploading Evidence", "icon": "📄", "order": 3, "audience": "USER"},
    {"id": "compliance-score", "name": "Compliance Score", "icon": "📈", "order": 4, "audience": "USER"},
    {"id": "dashboard-guide", "name": "Dashboard Guide", "icon": "📊", "order": 5, "audience": "USER"},
    {"id": "reminders", "name": "Reminders", "icon": "🔔", "order": 6, "audience": "USER"},
    {"id": "compliance-packs", "name": "Compliance Packs", "icon": "📁", "order": 7, "audience": "USER"},
    {"id": "billing-subscriptions", "name": "Billing", "icon": "💳", "order": 8, "audience": "USER"},
    {"id": "troubleshooting", "name": "Troubleshooting", "icon": "🔧", "order": 9, "audience": "USER"},
]

DEFAULT_CATEGORIES = DEFAULT_CATEGORIES_ADMIN + DEFAULT_CATEGORIES_USER


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ArticleCreate(BaseModel):
    """Request to create a KB article."""
    title: str = Field(..., min_length=5, max_length=200)
    slug: Optional[str] = None
    category_id: str
    excerpt: str = Field(..., min_length=10, max_length=500)
    content: str = Field(..., min_length=50)
    tags: Optional[List[str]] = None
    status: ArticleStatus = ArticleStatus.DRAFT
    audience: ArticleAudience = ArticleAudience.USER
    version: Optional[str] = "1.0"
    summary: Optional[str] = None  # alias/supplement to excerpt for task compatibility
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    product_module: Optional[str] = None
    related_feature_flags: Optional[List[str]] = None
    article_type: Optional[str] = None  # "release_notes" | None
    release_version: Optional[str] = None
    release_date: Optional[str] = None
    changes: Optional[List[str]] = None
    affected_modules: Optional[List[str]] = None


class ArticleUpdate(BaseModel):
    """Request to update a KB article."""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    category_id: Optional[str] = None
    excerpt: Optional[str] = Field(None, min_length=10, max_length=500)
    content: Optional[str] = Field(None, min_length=50)
    tags: Optional[List[str]] = None
    audience: Optional[ArticleAudience] = None
    version: Optional[str] = None
    summary: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    product_module: Optional[str] = None
    related_feature_flags: Optional[List[str]] = None
    article_type: Optional[str] = None
    release_version: Optional[str] = None
    release_date: Optional[str] = None
    changes: Optional[List[str]] = None
    affected_modules: Optional[List[str]] = None


class CategoryCreate(BaseModel):
    """Request to create a category."""
    name: str = Field(..., min_length=2, max_length=100)
    icon: str = "📁"
    description: Optional[str] = None
    order: int = 0
    audience: Optional[str] = None  # ADMIN | USER


class CategoryUpdate(BaseModel):
    """Request to update a category."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    icon: Optional[str] = None
    description: Optional[str] = None
    order: Optional[int] = None
    audience: Optional[str] = None


# Help Assistant (doc-grounded, role-aware)
class HelpAssistantQueryRequest(BaseModel):
    """Request for help-assistant query (documentation only)."""
    query: str = Field(..., min_length=1, max_length=500)
    context: Optional[str] = Field(None, max_length=200)


class HelpAssistantSource(BaseModel):
    """One cited source for help-assistant response."""
    articleId: str
    title: str
    slug: str
    updatedAt: Optional[str] = None


class HelpAssistantQueryResponse(BaseModel):
    """Response from help-assistant: answer from published docs only, or fallback."""
    answer: str
    steps: List[str] = []
    sources: List[HelpAssistantSource] = []
    grounded: bool = False


class HelpAssistantFeedbackRequest(BaseModel):
    """Feedback for a help-assistant answer (Helpful / Not Helpful)."""
    query: str = Field(..., max_length=500)
    answer: str = Field(..., max_length=10000)
    helpful: bool
    source_article_ids: Optional[List[str]] = None
    response_id: Optional[str] = None


class KbArticleFeedbackPublicBody(BaseModel):
    """Article helpful vote from public KB (anonymous session or optional portal JWT)."""
    feedback_type: str = Field(..., description="helpful | not_helpful")
    session_id: Optional[str] = Field(None, max_length=128)

    @field_validator("feedback_type")
    @classmethod
    def _ft(cls, v: str) -> str:
        if v not in ("helpful", "not_helpful"):
            raise ValueError("feedback_type must be helpful or not_helpful")
        return v


class KbArticleFeedbackClientBody(BaseModel):
    """Article helpful vote from authenticated client Help Centre."""
    feedback_type: str = Field(...)

    @field_validator("feedback_type")
    @classmethod
    def _ft(cls, v: str) -> str:
        if v not in ("helpful", "not_helpful"):
            raise ValueError("feedback_type must be helpful or not_helpful")
        return v


class KbArticleFeedbackCommentPublicBody(BaseModel):
    """Optional written note after voting (public KB); must match session or auth dedupe from prior vote."""
    session_id: Optional[str] = Field(None, max_length=128)
    comment: str = Field(..., max_length=kb_article_feedback_svc.MAX_ARTICLE_FEEDBACK_COMMENT_LEN)

    @field_validator("comment")
    @classmethod
    def _comment_nonempty(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("comment must not be empty")
        return s


class KbArticleFeedbackCommentClientBody(BaseModel):
    comment: str = Field(..., max_length=kb_article_feedback_svc.MAX_ARTICLE_FEEDBACK_COMMENT_LEN)

    @field_validator("comment")
    @classmethod
    def _comment_nonempty(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("comment must not be empty")
        return s


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_article_id() -> str:
    """Generate unique article ID."""
    return f"kb-{uuid.uuid4().hex[:12]}"


def generate_slug(title: str) -> str:
    """Generate URL-safe slug from title."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:100]


async def log_kb_action(
    action: str,
    resource_type: str,
    resource_id: str,
    actor_email: str,
    before_state: Optional[Dict] = None,
    after_state: Optional[Dict] = None,
    details: Optional[Dict] = None
):
    """Create audit log entry for KB actions."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    await db["audit_logs"].insert_one({
        "action": action,
        "actor_type": "admin",
        "actor_id": actor_email,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": {
            **(details or {}),
            "before_state": json.dumps(before_state, default=str)[:5000] if before_state else None,
            "after_state": json.dumps(after_state, default=str)[:5000] if after_state else None,
        },
        "created_at": now,
    })


async def ensure_default_categories():
    """Ensure default categories exist (ADMIN + USER sets)."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()

    for cat in DEFAULT_CATEGORIES:
        existing = await db[CATEGORIES_COLLECTION].find_one({"category_id": cat["id"]})
        if not existing:
            await db[CATEGORIES_COLLECTION].insert_one({
                "category_id": cat["id"],
                "name": cat["name"],
                "icon": cat["icon"],
                "order": cat["order"],
                "audience": cat.get("audience", "USER"),
                "description": None,
                "is_active": True,
                "article_count": 0,
                "created_at": now,
            })


async def log_search_analytics(query: str, results_count: int, ip_address: str = None):
    """Log search query for analytics."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    await db[SEARCH_ANALYTICS_COLLECTION].insert_one({
        "query": query.lower().strip(),
        "results_count": results_count,
        "has_results": results_count > 0,
        "ip_address": ip_address,
        "searched_at": now,
    })


def _published_user_article_base_filter() -> Dict[str, Any]:
    """Match published, active, USER-facing help articles (public + client Help Centre)."""
    return {
        "status": ArticleStatus.PUBLISHED.value,
        "is_active": True,
        "$or": [
            {"audience": ArticleAudience.USER.value},
            {"audience": {"$exists": False}},
        ],
    }


async def get_published_user_article_by_id(article_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    q = {"article_id": article_id, **_published_user_article_base_filter()}
    return await db[ARTICLES_COLLECTION].find_one(q, {"_id": 0})


async def category_lookup_map_for_kb() -> Dict[str, Dict[str, Any]]:
    db = database.get_db()
    cursor = db[CATEGORIES_COLLECTION].find(
        {"is_active": True},
        {"_id": 0, "category_id": 1, "name": 1, "icon": 1},
    )
    rows = await cursor.to_list(length=300)
    return {r["category_id"]: r for r in rows if r.get("category_id")}


def serialize_user_facing_kb_article(
    article: Dict[str, Any],
    cat_map: Dict[str, Dict[str, Any]],
    *,
    include_content: bool,
    related_raw: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Strip internal metadata from KB article payloads for public + client Help Centre.
    Do not expose draft status, admin audience labels, or version to end users.
    """
    cid = article.get("category_id")
    cat = cat_map.get(cid) or {}
    out: Dict[str, Any] = {
        "article_id": article.get("article_id"),
        "slug": article.get("slug"),
        "title": article.get("title"),
        "excerpt": article.get("excerpt"),
        "tags": article.get("tags") or [],
        "view_count": article.get("view_count", 0),
        "updated_at": article.get("updated_at"),
        "published_at": article.get("published_at"),
        "category_id": cid,
        "category_name": cat.get("name"),
        "category_icon": cat.get("icon"),
        "order": article.get("order"),
    }
    if include_content:
        out["content"] = article.get("content") or ""
    rel = related_raw or []
    out["related_articles"] = []
    for r in rel:
        out["related_articles"].append(
            {
                "article_id": r.get("article_id"),
                "slug": r.get("slug"),
                "title": r.get("title"),
                "excerpt": r.get("excerpt"),
                "view_count": r.get("view_count", 0),
                "category_id": r.get("category_id"),
            }
        )
    return out


def _allowed_audiences_for_role(role: str) -> List[str]:
    """Return allowed audience values for help-assistant retrieval. USER -> USER only; staff/admin -> USER, STAFF, ADMIN."""
    role = (role or "").strip().upper()
    if role in ("USER", "ROLE_CLIENT", "ROLE_CLIENT_ADMIN", "ROLE_TENANT"):
        return [ArticleAudience.USER.value]
    return [ArticleAudience.USER.value, ArticleAudience.STAFF.value, ArticleAudience.ADMIN.value]


async def search_published_articles_for_assistant(
    query: str,
    allowed_audiences: List[str],
    limit: int = HELP_ASSISTANT_TOP_N,
    context: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search published KB articles by text (title, excerpt, content). Role-aware via allowed_audiences.
    Returns list of dicts with article_id, title, slug, excerpt, content_preview, updated_at.
    Only published, is_active; no drafts or archived.
    """
    db = database.get_db()
    q = (query or "").strip()
    if not q:
        return []
    # Build filter: published, active; audience in allowed set (role-aware); AND text match
    audience_condition = {
        "$or": [
            {"audience": {"$in": allowed_audiences}},
            {"audience": {"$exists": False}},
        ],
    }
    # Text search: at least one of title, excerpt, content matches (regex, case-insensitive)
    search_re = re.escape(q) if len(q) < 50 else re.escape(q[:50])
    text_conditions = [
        {"title": {"$regex": search_re, "$options": "i"}},
        {"excerpt": {"$regex": search_re, "$options": "i"}},
        {"summary": {"$regex": search_re, "$options": "i"}},
        {"content": {"$regex": search_re, "$options": "i"}},
        {"tags": {"$elemMatch": {"$regex": search_re, "$options": "i"}}},
    ]
    if context:
        text_conditions.append({"product_module": {"$regex": re.escape(context[:100]), "$options": "i"}})
    filter_query = {
        "status": ArticleStatus.PUBLISHED.value,
        "is_active": True,
        "$and": [
            audience_condition,
            {"$or": text_conditions},
        ],
    }
    cursor = db[ARTICLES_COLLECTION].find(
        filter_query,
        {"_id": 0, "article_id": 1, "title": 1, "slug": 1, "excerpt": 1, "content": 1, "updated_at": 1},
    ).sort("published_at", -1).limit(limit * 2)
    raw = await cursor.to_list(length=limit * 2)
    # Prefer title/excerpt match order (simple relevance)
    def score(a):
        s = 0
        t, e, c = (a.get("title") or "").lower(), (a.get("excerpt") or "").lower(), (a.get("content") or "").lower()
        ql = q.lower()
        if ql in t:
            s += 3
        if ql in e:
            s += 2
        if ql in c:
            s += 1
        return s
    raw.sort(key=lambda a: -score(a))
    raw = raw[:limit]
    out = []
    for a in raw:
        content = (a.get("content") or "")[:500]
        out.append({
            "article_id": a.get("article_id", ""),
            "title": a.get("title", ""),
            "slug": a.get("slug", ""),
            "excerpt": (a.get("excerpt") or "").strip(),
            "content_preview": content.strip(),
            "updated_at": a.get("updated_at"),
        })
    return out


def _build_help_assistant_response(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build answer, steps, sources, grounded from retrieved articles. No LLM; doc-only."""
    if not articles:
        return {
            "answer": HELP_ASSISTANT_FALLBACK,
            "steps": [],
            "sources": [],
            "grounded": False,
        }
    first = articles[0]
    answer = (first.get("excerpt") or first.get("content_preview") or first.get("title", "")).strip()
    if not answer:
        answer = first.get("title", "See the article below for details.")
    sources = [
        {
            "articleId": a.get("article_id", ""),
            "title": a.get("title", ""),
            "slug": a.get("slug", ""),
            "updatedAt": a.get("updated_at"),
        }
        for a in articles
    ]
    return {
        "answer": answer,
        "steps": [],
        "sources": sources,
        "grounded": True,
    }


def _build_article_pdf(article: dict) -> io.BytesIO:
    """Build a PDF for a KB article (title, version, date, content, page numbers, Pleerity branding)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageTemplate, Frame
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from xml.sax.saxutils import escape
    from utils.branding import COMPANY_NAME

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "KbTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=6,
        textColor=colors.HexColor("#0B1D3A"),
    )
    meta_style = ParagraphStyle(
        "KbMeta",
        parent=styles["Normal"],
        fontSize=9,
        spaceAfter=4,
        textColor=colors.grey,
    )
    body_style = ParagraphStyle(
        "KbBody",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=8,
        textColor=colors.HexColor("#1a1a1a"),
    )

    elements = []
    elements.append(Paragraph(escape(article.get("title", "Untitled")), title_style))
    version = article.get("version") or "1.0"
    updated = article.get("updated_at") or article.get("created_at") or ""
    if updated:
        try:
            from dateutil import parser as date_parser
            dt = date_parser.parse(updated)
            updated = dt.strftime("%d %b %Y")
        except Exception:
            updated = str(updated)[:10]
    elements.append(Paragraph(f"Version {escape(version)} &middot; Last updated: {escape(updated)}", meta_style))
    elements.append(Spacer(1, 12))

    content = article.get("content") or ""
    # Simple markdown-ish to plain: strip headers markers, bold/italic markers, keep newlines
    content_plain = re.sub(r"^#{1,6}\s*", "", content, flags=re.MULTILINE)
    content_plain = re.sub(r"\*+", "", content_plain)
    content_plain = re.sub(r"^-\s*", "", content_plain, flags=re.MULTILINE)
    for block in content_plain.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        block = escape(block).replace("\n", "<br/>")
        elements.append(Paragraph(block, body_style))

    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#0B1D3A"))
        canvas.drawString(inch, inch * 0.5, COMPANY_NAME)
        page_num = canvas.getPageNumber()
        canvas.drawRightString(A4[0] - inch, inch * 0.5, f"Page {page_num}")
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
    output.seek(0)
    return output


# ============================================================================
# PUBLIC ENDPOINTS
# ============================================================================

@public_router.get("/articles")
async def list_public_articles(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, le=100),
    skip: int = Query(0, ge=0),
    request: Request = None,
):
    """List published KB articles visible to end users (USER audience only)."""
    db = database.get_db()

    filter_query = {
        "status": ArticleStatus.PUBLISHED.value,
        "is_active": True,
        "$or": [
            {"audience": ArticleAudience.USER.value},
            {"audience": {"$exists": False}},
        ],
    }

    if category:
        filter_query["category_id"] = category
    if tag:
        filter_query["tags"] = tag
    if search:
        filter_query["$and"] = [
            {"$or": [
                {"title": {"$regex": search, "$options": "i"}},
                {"excerpt": {"$regex": search, "$options": "i"}},
                {"content": {"$regex": search, "$options": "i"}},
                {"tags": {"$regex": search, "$options": "i"}},
            ]}
        ]

    # Sort: when search present, prefer relevance (title match first, then excerpt); else by published_at
    sort_spec = [("order", 1), ("published_at", -1)]
    cursor = db[ARTICLES_COLLECTION].find(
        filter_query,
        {"_id": 0, "content": 0}
    ).sort(sort_spec).skip(skip).limit(limit)

    articles = await cursor.to_list(length=limit)
    total = await db[ARTICLES_COLLECTION].count_documents(filter_query)

    if search:
        ip = request.client.host if request and request.client else None
        await log_search_analytics(search, len(articles), ip)

    cat_map = await category_lookup_map_for_kb()
    safe_articles = [
        serialize_user_facing_kb_article(a, cat_map, include_content=False) for a in articles
    ]
    return {"articles": safe_articles, "total": total}


@public_router.get("/articles/{slug}")
async def get_public_article(
    slug: str,
    request: Request = None,
):
    """Get a single published article by slug (USER audience or no audience). Increments view count."""
    db = database.get_db()

    article = await db[ARTICLES_COLLECTION].find_one(
        {
            "slug": slug,
            "status": ArticleStatus.PUBLISHED.value,
            "is_active": True,
            "$or": [
                {"audience": ArticleAudience.USER.value},
                {"audience": {"$exists": False}},
            ],
        },
        {"_id": 0}
    )
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Increment view count
    await db[ARTICLES_COLLECTION].update_one(
        {"slug": slug},
        {"$inc": {"view_count": 1}}
    )
    
    # Get related articles (same category, limit 3, USER or no audience)
    related_filter = {
        "category_id": article["category_id"],
        "slug": {"$ne": slug},
        "status": ArticleStatus.PUBLISHED.value,
        "is_active": True,
        "$or": [
            {"audience": ArticleAudience.USER.value},
            {"audience": {"$exists": False}},
        ],
    }
    related_cursor = db[ARTICLES_COLLECTION].find(
        related_filter,
        {"_id": 0, "content": 0}
    ).limit(3)
    related = await related_cursor.to_list(length=3)

    article["view_count"] = int(article.get("view_count") or 0) + 1
    cat_map = await category_lookup_map_for_kb()
    return serialize_user_facing_kb_article(
        article,
        cat_map,
        include_content=True,
        related_raw=related,
    )


@public_router.post("/articles/{article_id}/feedback")
async def post_public_kb_article_feedback(
    article_id: str,
    data: KbArticleFeedbackPublicBody,
    request: Request,
):
    """
    Record helpful / not helpful for a published USER-facing article (public KB).
    Anonymous callers must send ``session_id`` (stable browser UUID). Authenticated portal users may omit it (dedupe by user).
    """
    article = await get_published_user_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    user = await get_current_user(request)
    portal_uid = (user or {}).get("portal_user_id")

    snapshot = {
        "slug": article.get("slug"),
        "title": article.get("title"),
        "category_id": article.get("category_id"),
        "audience": article.get("audience") or ArticleAudience.USER.value,
    }
    try:
        result = await kb_article_feedback_svc.submit_article_feedback(
            article_id=article_id,
            feedback_type=data.feedback_type,
            source_surface="public_kb",
            session_id=data.session_id,
            portal_user_id=portal_uid,
            article_snapshot=snapshot,
        )
    except ValueError as exc:
        msg = str(exc)
        if msg == "session_id_required":
            raise HTTPException(
                status_code=400,
                detail="session_id is required for anonymous feedback (send a stable UUID from the browser)",
            ) from exc
        if msg == "invalid_feedback_type":
            raise HTTPException(status_code=400, detail="Invalid feedback_type") from exc
        raise HTTPException(status_code=400, detail="Invalid feedback") from exc
    return result


@public_router.post("/articles/{article_id}/feedback/comment")
async def post_public_kb_article_feedback_comment(
    article_id: str,
    data: KbArticleFeedbackCommentPublicBody,
    request: Request,
):
    """
    Add a one-time written note to the caller's existing helpfulness vote (same article, same dedupe).
    """
    article = await get_published_user_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    user = await get_current_user(request)
    portal_uid = (user or {}).get("portal_user_id")

    try:
        return await kb_article_feedback_svc.append_comment_to_article_feedback(
            article_id=article_id,
            comment=data.comment,
            source_surface="public_kb",
            session_id=data.session_id,
            portal_user_id=portal_uid,
        )
    except ValueError as exc:
        msg = str(exc)
        if msg == "session_id_required":
            raise HTTPException(
                status_code=400,
                detail="session_id is required for anonymous feedback (send a stable UUID from the browser)",
            ) from exc
        if msg == "comment_required":
            raise HTTPException(status_code=400, detail="comment is required") from exc
        if msg == "comment_too_long":
            raise HTTPException(status_code=400, detail="comment is too long") from exc
        if msg == "feedback_not_found":
            raise HTTPException(
                status_code=404,
                detail="No feedback found for this article; submit helpfulness first",
            ) from exc
        raise HTTPException(status_code=400, detail="Invalid comment") from exc


@public_router.get("/categories")
async def list_public_categories():
    """List active USER-scoped categories with article counts (published USER articles only)."""
    db = database.get_db()
    await ensure_default_categories()

    # Categories with audience USER or no audience (backward compat)
    cursor = db[CATEGORIES_COLLECTION].find(
        {"is_active": True, "$or": [{"audience": "USER"}, {"audience": {"$exists": False}}]},
        {"_id": 0}
    ).sort("order", 1)

    categories = await cursor.to_list(length=50)

    article_match = {
        "status": ArticleStatus.PUBLISHED.value,
        "is_active": True,
        "$or": [{"audience": ArticleAudience.USER.value}, {"audience": {"$exists": False}}],
    }
    pipeline = [
        {"$match": article_match},
        {"$group": {"_id": "$category_id", "count": {"$sum": 1}}},
    ]
    counts = {}
    async for doc in db[ARTICLES_COLLECTION].aggregate(pipeline):
        counts[doc["_id"]] = doc["count"]

    for cat in categories:
        cat["article_count"] = counts.get(cat.get("category_id"), 0)

    return {"categories": categories}


@public_router.get("/featured")
async def get_featured_articles():
    """Get featured/popular articles (USER audience only)."""
    db = database.get_db()

    user_filter = {
        "status": ArticleStatus.PUBLISHED.value,
        "is_active": True,
        "$or": [{"audience": ArticleAudience.USER.value}, {"audience": {"$exists": False}}],
    }
    popular_cursor = db[ARTICLES_COLLECTION].find(
        user_filter,
        {"_id": 0, "content": 0}
    ).sort("view_count", -1).limit(5)
    popular = await popular_cursor.to_list(length=5)

    recent_cursor = db[ARTICLES_COLLECTION].find(
        user_filter,
        {"_id": 0, "content": 0}
    ).sort("published_at", -1).limit(5)
    recent = await recent_cursor.to_list(length=5)

    cat_map = await category_lookup_map_for_kb()
    popular_safe = [
        serialize_user_facing_kb_article(a, cat_map, include_content=False) for a in popular
    ]
    recent_safe = [
        serialize_user_facing_kb_article(a, cat_map, include_content=False) for a in recent
    ]
    return {"popular": popular_safe, "recent": recent_safe}


@public_router.get("/tags/popular")
async def get_popular_tags():
    """Get most used tags (USER audience articles only)."""
    db = database.get_db()

    match = {
        "status": ArticleStatus.PUBLISHED.value,
        "is_active": True,
        "$or": [{"audience": ArticleAudience.USER.value}, {"audience": {"$exists": False}}],
    }
    pipeline = [
        {"$match": match},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    tags = []
    async for doc in db[ARTICLES_COLLECTION].aggregate(pipeline):
        tags.append({"tag": doc["_id"], "count": doc["count"]})
    return {"tags": tags}


# ============================================================================
# CLIENT HELP CENTRE (authenticated portal users, USER audience only)
# ============================================================================

@client_help_router.get("/articles")
async def client_help_list_articles(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, le=100),
    skip: int = Query(0, ge=0),
    request: Request = None,
    current_user: dict = Depends(client_route_guard),
):
    """List published USER-scoped articles for Help Centre (authenticated client)."""
    db = database.get_db()

    filter_query = {
        "status": ArticleStatus.PUBLISHED.value,
        "is_active": True,
        "$or": [{"audience": ArticleAudience.USER.value}, {"audience": {"$exists": False}}],
    }
    if category:
        filter_query["category_id"] = category
    if tag:
        filter_query["tags"] = tag
    if search:
        filter_query["$and"] = [
            {"$or": [
                {"title": {"$regex": search, "$options": "i"}},
                {"excerpt": {"$regex": search, "$options": "i"}},
                {"content": {"$regex": search, "$options": "i"}},
                {"tags": {"$regex": search, "$options": "i"}},
            ]}
        ]

    cursor = db[ARTICLES_COLLECTION].find(
        filter_query,
        {"_id": 0, "content": 0}
    ).sort([("order", 1), ("published_at", -1)]).skip(skip).limit(limit)
    articles = await cursor.to_list(length=limit)
    total = await db[ARTICLES_COLLECTION].count_documents(filter_query)
    cat_map = await category_lookup_map_for_kb()
    safe = [serialize_user_facing_kb_article(a, cat_map, include_content=False) for a in articles]
    return {"articles": safe, "total": total}


@client_help_router.get("/articles/{slug}")
async def client_help_get_article(
    slug: str,
    request: Request = None,
    current_user: dict = Depends(client_route_guard),
):
    """Get one published USER article by slug (for Help Centre)."""
    db = database.get_db()

    article = await db[ARTICLES_COLLECTION].find_one(
        {
            "slug": slug,
            "status": ArticleStatus.PUBLISHED.value,
            "is_active": True,
            "$or": [{"audience": ArticleAudience.USER.value}, {"audience": {"$exists": False}}],
        },
        {"_id": 0}
    )
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    await db[ARTICLES_COLLECTION].update_one({"slug": slug}, {"$inc": {"view_count": 1}})

    related_filter = {
        "category_id": article["category_id"],
        "slug": {"$ne": slug},
        "status": ArticleStatus.PUBLISHED.value,
        "is_active": True,
        "$or": [{"audience": ArticleAudience.USER.value}, {"audience": {"$exists": False}}],
    }
    related = await db[ARTICLES_COLLECTION].find(related_filter, {"_id": 0, "content": 0}).limit(3).to_list(length=3)
    article["view_count"] = int(article.get("view_count") or 0) + 1
    cat_map = await category_lookup_map_for_kb()
    return serialize_user_facing_kb_article(
        article,
        cat_map,
        include_content=True,
        related_raw=related,
    )


@client_help_router.get("/categories")
async def client_help_list_categories(
    current_user: dict = Depends(client_route_guard),
):
    """List USER-scoped categories with article counts for Help Centre."""
    db = database.get_db()
    await ensure_default_categories()

    cursor = db[CATEGORIES_COLLECTION].find(
        {"is_active": True, "$or": [{"audience": "USER"}, {"audience": {"$exists": False}}]},
        {"_id": 0}
    ).sort("order", 1)
    categories = await cursor.to_list(length=50)

    article_match = {
        "status": ArticleStatus.PUBLISHED.value,
        "is_active": True,
        "$or": [{"audience": ArticleAudience.USER.value}, {"audience": {"$exists": False}}],
    }
    pipeline = [{"$match": article_match}, {"$group": {"_id": "$category_id", "count": {"$sum": 1}}}]
    counts = {}
    async for doc in db[ARTICLES_COLLECTION].aggregate(pipeline):
        counts[doc["_id"]] = doc["count"]
    for cat in categories:
        cat["article_count"] = counts.get(cat.get("category_id"), 0)
    return {"categories": categories}


@client_help_router.post("/query", response_model=HelpAssistantQueryResponse)
async def client_help_assistant_query(
    data: HelpAssistantQueryRequest,
    current_user: dict = Depends(client_route_guard),
):
    """
    Help Assistant query: answers from published USER-scoped articles only.
    No LLM; no portal data. If no docs match, returns fallback and grounded=false.
    """
    allowed = _allowed_audiences_for_role(current_user.get("role", "USER"))
    articles = await search_published_articles_for_assistant(
        query=data.query,
        allowed_audiences=allowed,
        limit=HELP_ASSISTANT_TOP_N,
        context=data.context,
    )
    result = _build_help_assistant_response(articles)
    return HelpAssistantQueryResponse(**result)


@client_help_router.post("/feedback")
async def client_help_assistant_feedback(
    data: HelpAssistantFeedbackRequest,
    current_user: dict = Depends(client_route_guard),
):
    """Record Helpful / Not Helpful for a help-assistant answer."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    user_id = current_user.get("portal_user_id") or current_user.get("client_id") or "unknown"
    doc = {
        "feedback_id": f"fb-{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "query": data.query[:500],
        "answer": data.answer[:5000],
        "helpful": data.helpful,
        "source_article_ids": data.source_article_ids or [],
        "response_id": data.response_id,
        "scope": "client_help",
        "created_at": now,
    }
    await db[FEEDBACK_COLLECTION].insert_one(doc)
    return {"ok": True, "feedback_id": doc["feedback_id"]}


@client_help_router.post("/articles/{article_id}/feedback")
async def client_help_article_feedback(
    article_id: str,
    data: KbArticleFeedbackClientBody,
    current_user: dict = Depends(client_route_guard),
):
    """Record helpful / not helpful for a Help Centre article (dedupe per portal user)."""
    article = await get_published_user_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    portal_uid = current_user.get("portal_user_id") or current_user.get("client_id")
    snapshot = {
        "slug": article.get("slug"),
        "title": article.get("title"),
        "category_id": article.get("category_id"),
        "audience": article.get("audience") or ArticleAudience.USER.value,
    }
    try:
        return await kb_article_feedback_svc.submit_article_feedback(
            article_id=article_id,
            feedback_type=data.feedback_type,
            source_surface="client_help",
            session_id=None,
            portal_user_id=portal_uid,
            article_snapshot=snapshot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid feedback") from exc


@client_help_router.post("/articles/{article_id}/feedback/comment")
async def client_help_article_feedback_comment(
    article_id: str,
    data: KbArticleFeedbackCommentClientBody,
    current_user: dict = Depends(client_route_guard),
):
    """Attach written note to existing vote (authenticated client)."""
    article = await get_published_user_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    portal_uid = current_user.get("portal_user_id") or current_user.get("client_id")
    try:
        return await kb_article_feedback_svc.append_comment_to_article_feedback(
            article_id=article_id,
            comment=data.comment,
            source_surface="client_help",
            session_id=None,
            portal_user_id=portal_uid,
        )
    except ValueError as exc:
        msg = str(exc)
        if msg == "feedback_not_found":
            raise HTTPException(
                status_code=404,
                detail="No feedback found for this article; submit helpfulness first",
            ) from exc
        if msg == "comment_required":
            raise HTTPException(status_code=400, detail="comment is required") from exc
        if msg == "comment_too_long":
            raise HTTPException(status_code=400, detail="comment is too long") from exc
        raise HTTPException(status_code=400, detail="Invalid comment") from exc


# ============================================================================
# ADMIN ENDPOINTS - ARTICLES
# ============================================================================

@admin_router.get("/articles")
async def admin_list_articles(
    status: Optional[ArticleStatus] = None,
    category: Optional[str] = None,
    audience: Optional[str] = None,
    search: Optional[str] = None,
    include_inactive: bool = False,
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(admin_route_guard)
):
    """List all articles for admin (includes drafts). Returns audience, version, updated_at."""
    db = database.get_db()

    filter_query = {}
    if not include_inactive:
        filter_query["is_active"] = True
    if status:
        filter_query["status"] = status.value
    if category:
        filter_query["category_id"] = category
    if audience:
        filter_query["audience"] = audience
    if search:
        filter_query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"excerpt": {"$regex": search, "$options": "i"}},
            {"summary": {"$regex": search, "$options": "i"}},
            {"content": {"$regex": search, "$options": "i"}},
            {"tags": {"$elemMatch": {"$regex": search, "$options": "i"}}},
        ]

    cursor = db[ARTICLES_COLLECTION].find(
        filter_query,
        {"_id": 0, "content": 0}
    ).sort([("updated_at", -1), ("status", 1)]).skip(skip).limit(limit)

    articles = await cursor.to_list(length=limit)
    total = await db[ARTICLES_COLLECTION].count_documents(filter_query)

    total_published = await db[ARTICLES_COLLECTION].count_documents({"status": "published", "is_active": True})
    total_draft = await db[ARTICLES_COLLECTION].count_documents({"status": "draft", "is_active": True})

    return {
        "articles": articles,
        "total": total,
        "stats": {"published": total_published, "draft": total_draft},
    }


@admin_router.get("/articles/{article_id}")
async def admin_get_article(
    article_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Get full article for editing."""
    db = database.get_db()
    
    article = await db[ARTICLES_COLLECTION].find_one(
        {"article_id": article_id},
        {"_id": 0}
    )
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return article


@admin_router.get("/articles/{article_id}/export-pdf")
async def admin_export_article_pdf(
    article_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Export article as PDF (Download Training Guide). Branded with title, version, date, content, page numbers."""
    db = database.get_db()
    article = await db[ARTICLES_COLLECTION].find_one({"article_id": article_id}, {"_id": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    buf = _build_article_pdf(article)
    filename = f"training-guide-{article.get('slug', article_id)}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@admin_router.post("/articles")
async def admin_create_article(
    request: ArticleCreate,
    current_user: dict = Depends(admin_route_guard)
):
    """Create a new KB article."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    article_id = generate_article_id()
    slug = request.slug or generate_slug(request.title)
    
    # Check slug uniqueness
    existing = await db[ARTICLES_COLLECTION].find_one({"slug": slug})
    if existing:
        # Append ID to make unique
        slug = f"{slug}-{article_id[-6:]}"
    
    doc = {
        "article_id": article_id,
        "title": request.title,
        "slug": slug,
        "category_id": request.category_id,
        "excerpt": request.excerpt,
        "content": request.content,
        "tags": request.tags or [],
        "status": request.status.value,
        "audience": request.audience.value,
        "version": request.version or "1.0",
        "summary": request.summary or request.excerpt[:500] if request.excerpt else None,
        "meta_title": request.meta_title or request.title,
        "meta_description": request.meta_description or request.excerpt,
        "view_count": 0,
        "is_active": True,
        "product_module": request.product_module,
        "related_feature_flags": request.related_feature_flags or [],
        "article_type": request.article_type,
        "release_version": request.release_version,
        "release_date": request.release_date,
        "changes": request.changes or [],
        "affected_modules": request.affected_modules or [],
        "created_at": now,
        "created_by": current_user.get("email"),
        "updated_at": now,
        "updated_by": current_user.get("email"),
        "published_at": now if request.status == ArticleStatus.PUBLISHED else None,
    }
    
    await db[ARTICLES_COLLECTION].insert_one(doc)
    doc.pop("_id", None)
    
    # Audit log
    await log_kb_action(
        action="KB_ARTICLE_CREATED",
        resource_type="kb_article",
        resource_id=article_id,
        actor_email=current_user.get("email"),
        after_state=doc,
    )
    
    logger.info(f"KB article created: {article_id} by {current_user.get('email')}")

    await sync_public_support_index_for_kb_article(article_id)

    return {
        "success": True,
        "article_id": article_id,
        "slug": slug,
        "article": doc,
    }


@admin_router.put("/articles/{article_id}")
async def admin_update_article(
    article_id: str,
    request: ArticleUpdate,
    current_user: dict = Depends(admin_route_guard)
):
    """Update an existing KB article."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    # Get current state
    current = await db[ARTICLES_COLLECTION].find_one({"article_id": article_id})
    if not current:
        raise HTTPException(status_code=404, detail="Article not found")
    
    before_state = {k: v for k, v in current.items() if k != "_id"}
    
    # Build update
    update_data = {"updated_at": now, "updated_by": current_user.get("email")}
    
    if request.title is not None:
        update_data["title"] = request.title
    if request.category_id is not None:
        update_data["category_id"] = request.category_id
    if request.excerpt is not None:
        update_data["excerpt"] = request.excerpt
    if request.content is not None:
        update_data["content"] = request.content
    if request.tags is not None:
        update_data["tags"] = request.tags
    if request.audience is not None:
        update_data["audience"] = request.audience.value
    if request.version is not None:
        update_data["version"] = request.version
    if request.summary is not None:
        update_data["summary"] = request.summary
    if request.meta_title is not None:
        update_data["meta_title"] = request.meta_title
    if request.meta_description is not None:
        update_data["meta_description"] = request.meta_description
    if request.product_module is not None:
        update_data["product_module"] = request.product_module
    if request.related_feature_flags is not None:
        update_data["related_feature_flags"] = request.related_feature_flags
    if request.article_type is not None:
        update_data["article_type"] = request.article_type
    if request.release_version is not None:
        update_data["release_version"] = request.release_version
    if request.release_date is not None:
        update_data["release_date"] = request.release_date
    if request.changes is not None:
        update_data["changes"] = request.changes
    if request.affected_modules is not None:
        update_data["affected_modules"] = request.affected_modules

    await db[ARTICLES_COLLECTION].update_one(
        {"article_id": article_id},
        {"$set": update_data}
    )
    
    updated = await db[ARTICLES_COLLECTION].find_one({"article_id": article_id}, {"_id": 0})
    
    # Audit log
    await log_kb_action(
        action="KB_ARTICLE_UPDATED",
        resource_type="kb_article",
        resource_id=article_id,
        actor_email=current_user.get("email"),
        before_state=before_state,
        after_state=updated,
    )

    await sync_public_support_index_for_kb_article(article_id)

    return {"success": True, "article": updated}


@admin_router.post("/articles/{article_id}/publish")
async def admin_publish_article(
    article_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Publish a draft article."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    current = await db[ARTICLES_COLLECTION].find_one({"article_id": article_id})
    if not current:
        raise HTTPException(status_code=404, detail="Article not found")
    
    before_status = current.get("status")
    
    await db[ARTICLES_COLLECTION].update_one(
        {"article_id": article_id},
        {
            "$set": {
                "status": ArticleStatus.PUBLISHED.value,
                "published_at": now,
                "published_by": current_user.get("email"),
                "updated_at": now,
            }
        }
    )
    
    # Audit log
    await log_kb_action(
        action="KB_ARTICLE_PUBLISHED",
        resource_type="kb_article",
        resource_id=article_id,
        actor_email=current_user.get("email"),
        details={"before_status": before_status},
    )

    await sync_public_support_index_for_kb_article(article_id)

    return {"success": True, "status": "published"}


@admin_router.post("/articles/{article_id}/unpublish")
async def admin_unpublish_article(
    article_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Unpublish an article back to draft."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    await db[ARTICLES_COLLECTION].update_one(
        {"article_id": article_id},
        {
            "$set": {
                "status": ArticleStatus.DRAFT.value,
                "unpublished_at": now,
                "unpublished_by": current_user.get("email"),
                "updated_at": now,
            }
        }
    )
    
    # Audit log
    await log_kb_action(
        action="KB_ARTICLE_UNPUBLISHED",
        resource_type="kb_article",
        resource_id=article_id,
        actor_email=current_user.get("email"),
    )

    await sync_public_support_index_for_kb_article(article_id)

    return {"success": True, "status": "draft"}


@admin_router.post("/articles/{article_id}/archive")
async def admin_archive_article(
    article_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Set article status to archived (visible in admin only, not in public or help centre)."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()

    current = await db[ARTICLES_COLLECTION].find_one({"article_id": article_id})
    if not current:
        raise HTTPException(status_code=404, detail="Article not found")

    await db[ARTICLES_COLLECTION].update_one(
        {"article_id": article_id},
        {"$set": {"status": ArticleStatus.ARCHIVED.value, "updated_at": now, "updated_by": current_user.get("email")}}
    )

    await log_kb_action(
        action="KB_ARTICLE_ARCHIVED",
        resource_type="kb_article",
        resource_id=article_id,
        actor_email=current_user.get("email"),
    )

    await sync_public_support_index_for_kb_article(article_id)

    return {"success": True, "status": "archived"}


@admin_router.delete("/articles/{article_id}")
async def admin_deactivate_article(
    article_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Soft delete (deactivate) an article."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    result = await db[ARTICLES_COLLECTION].update_one(
        {"article_id": article_id},
        {
            "$set": {
                "is_active": False,
                "deactivated_at": now,
                "deactivated_by": current_user.get("email"),
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Audit log
    await log_kb_action(
        action="KB_ARTICLE_DEACTIVATED",
        resource_type="kb_article",
        resource_id=article_id,
        actor_email=current_user.get("email"),
    )

    await sync_public_support_index_for_kb_article(article_id)

    return {"success": True, "message": "Article deactivated"}


# ============================================================================
# ADMIN ENDPOINTS - CATEGORIES
# ============================================================================

@admin_router.get("/categories")
async def admin_list_categories(
    include_inactive: bool = False,
    current_user: dict = Depends(admin_route_guard)
):
    """List all categories for admin."""
    db = database.get_db()
    await ensure_default_categories()
    
    filter_query = {}
    if not include_inactive:
        filter_query["is_active"] = True
    
    cursor = db[CATEGORIES_COLLECTION].find(
        filter_query,
        {"_id": 0}
    ).sort("order", 1)
    
    categories = await cursor.to_list(length=100)
    
    return {"categories": categories}


@admin_router.post("/categories")
async def admin_create_category(
    request: CategoryCreate,
    current_user: dict = Depends(admin_route_guard)
):
    """Create a new category."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    category_id = generate_slug(request.name)
    
    # Check uniqueness
    existing = await db[CATEGORIES_COLLECTION].find_one({"category_id": category_id})
    if existing:
        category_id = f"{category_id}-{uuid.uuid4().hex[:6]}"
    
    doc = {
        "category_id": category_id,
        "name": request.name,
        "icon": request.icon,
        "description": request.description,
        "order": request.order,
        "audience": request.audience or "USER",
        "is_active": True,
        "article_count": 0,
        "created_at": now,
        "created_by": current_user.get("email"),
    }
    
    await db[CATEGORIES_COLLECTION].insert_one(doc)
    doc.pop("_id", None)
    
    return {"success": True, "category": doc}


@admin_router.put("/categories/{category_id}")
async def admin_update_category(
    category_id: str,
    request: CategoryUpdate,
    current_user: dict = Depends(admin_route_guard)
):
    """Update a category."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    update_data = {"updated_at": now}
    if request.name is not None:
        update_data["name"] = request.name
    if request.icon is not None:
        update_data["icon"] = request.icon
    if request.description is not None:
        update_data["description"] = request.description
    if request.order is not None:
        update_data["order"] = request.order
    if request.audience is not None:
        update_data["audience"] = request.audience
    
    result = await db[CATEGORIES_COLLECTION].update_one(
        {"category_id": category_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    
    updated = await db[CATEGORIES_COLLECTION].find_one({"category_id": category_id}, {"_id": 0})
    
    return {"success": True, "category": updated}


@admin_router.delete("/categories/{category_id}")
async def admin_deactivate_category(
    category_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Soft delete a category."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    result = await db[CATEGORIES_COLLECTION].update_one(
        {"category_id": category_id},
        {"$set": {"is_active": False, "deactivated_at": now}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return {"success": True, "message": "Category deactivated"}


# ============================================================================
# ADMIN ENDPOINTS - ANALYTICS
# ============================================================================

@admin_router.get("/analytics")
async def admin_get_analytics(
    days: int = Query(30, le=90),
    current_user: dict = Depends(admin_route_guard)
):
    """Get KB search and view analytics."""
    db = database.get_db()
    
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    # Top viewed articles
    top_viewed_cursor = db[ARTICLES_COLLECTION].find(
        {"status": ArticleStatus.PUBLISHED.value, "is_active": True},
        {"_id": 0, "article_id": 1, "title": 1, "view_count": 1, "category_id": 1}
    ).sort("view_count", -1).limit(10)
    top_viewed = await top_viewed_cursor.to_list(length=10)
    
    # Top searches
    pipeline = [
        {"$match": {"searched_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$query", "count": {"$sum": 1}, "has_results": {"$first": "$has_results"}}},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    top_searches = []
    async for doc in db[SEARCH_ANALYTICS_COLLECTION].aggregate(pipeline):
        top_searches.append({
            "query": doc["_id"],
            "count": doc["count"],
            "has_results": doc.get("has_results", True),
        })
    
    # Searches with no results
    no_results_pipeline = [
        {"$match": {"searched_at": {"$gte": cutoff}, "has_results": False}},
        {"$group": {"_id": "$query", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    no_results = []
    async for doc in db[SEARCH_ANALYTICS_COLLECTION].aggregate(no_results_pipeline):
        no_results.append({"query": doc["_id"], "count": doc["count"]})
    
    # Total stats
    total_articles = await db[ARTICLES_COLLECTION].count_documents({"is_active": True})
    total_published = await db[ARTICLES_COLLECTION].count_documents({"status": "published", "is_active": True})
    total_searches = await db[SEARCH_ANALYTICS_COLLECTION].count_documents({"searched_at": {"$gte": cutoff}})
    
    return {
        "period_days": days,
        "stats": {
            "total_articles": total_articles,
            "total_published": total_published,
            "total_searches": total_searches,
        },
        "top_viewed_articles": top_viewed,
        "top_searches": top_searches,
        "searches_with_no_results": no_results,
    }


@admin_router.get("/feedback-summary")
async def admin_kb_article_feedback_summary(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(25, ge=1, le=200),
    current_user: dict = Depends(admin_route_guard),
):
    """
    Aggregated helpful / not helpful votes for KB articles (public + client Help Centre).
    Intended for admin dashboards; does not expose raw session identifiers.
    """
    _ = current_user
    return await kb_article_feedback_svc.aggregate_feedback_summary(days=days, low_rated_limit=limit)


# ============================================================================
# ADMIN HELP ASSISTANT (doc-grounded, USER + STAFF + ADMIN articles)
# ============================================================================

@admin_router.post("/help-assistant/query", response_model=HelpAssistantQueryResponse)
async def admin_help_assistant_query(
    data: HelpAssistantQueryRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Help Assistant query for admin: answers from published USER, STAFF, and ADMIN articles.
    No LLM; documentation only. If no docs match, returns fallback and grounded=false.
    """
    allowed = _allowed_audiences_for_role(current_user.get("role", "ADMIN"))
    articles = await search_published_articles_for_assistant(
        query=data.query,
        allowed_audiences=allowed,
        limit=HELP_ASSISTANT_TOP_N,
        context=data.context,
    )
    result = _build_help_assistant_response(articles)
    return HelpAssistantQueryResponse(**result)


@admin_router.post("/help-assistant/feedback")
async def admin_help_assistant_feedback(
    data: HelpAssistantFeedbackRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """Record Helpful / Not Helpful for an admin help-assistant answer."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    user_id = current_user.get("portal_user_id") or current_user.get("email") or "unknown"
    doc = {
        "feedback_id": f"fb-{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "query": data.query[:500],
        "answer": data.answer[:5000],
        "helpful": data.helpful,
        "source_article_ids": data.source_article_ids or [],
        "response_id": data.response_id,
        "scope": "admin_help",
        "created_at": now,
    }
    await db[FEEDBACK_COLLECTION].insert_one(doc)
    return {"ok": True, "feedback_id": doc["feedback_id"]}
