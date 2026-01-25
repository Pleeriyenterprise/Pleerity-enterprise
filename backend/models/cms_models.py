"""
CMS Models - Data models for the Content Management System

Defines the schema for CMS pages, blocks, media, and redirects.
All content is CMS-driven with safe block types only.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import re


# ============================================================================
# ENUMS
# ============================================================================

class PageStatus(str, Enum):
    """Page publication status."""
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class PageType(str, Enum):
    """Types of CMS pages."""
    HUB = "HUB"                    # /services hub page
    CATEGORY = "CATEGORY"          # /services/{category}
    SERVICE = "SERVICE"            # /services/{category}/{slug}
    LANDING = "LANDING"            # Generic landing pages
    LEGAL = "LEGAL"                # Terms, privacy, etc.


class BlockType(str, Enum):
    """
    Safe CMS block types.
    
    IMPORTANT: Only these block types are allowed.
    No raw HTML, scripts, or unsafe embeds permitted.
    """
    # Text blocks
    TEXT = "TEXT"                  # Rich text paragraph
    HEADING = "HEADING"            # H1-H6 heading
    SUBHEADING = "SUBHEADING"      # Smaller heading
    QUOTE = "QUOTE"                # Blockquote
    
    # Media blocks
    IMAGE = "IMAGE"                # Single image
    IMAGE_GALLERY = "IMAGE_GALLERY"  # Multiple images
    VIDEO_EMBED = "VIDEO_EMBED"    # YouTube/Vimeo embed (sanitized)
    
    # Interactive blocks
    CTA_BUTTON = "CTA_BUTTON"      # Call-to-action button
    CTA_CARD = "CTA_CARD"          # CTA with description
    
    # List blocks
    FEATURE_LIST = "FEATURE_LIST"  # Bulleted features with icons
    CHECKLIST = "CHECKLIST"        # Checkmark list
    NUMBERED_LIST = "NUMBERED_LIST"  # Ordered list
    
    # Structured blocks
    COMPARISON_TABLE = "COMPARISON_TABLE"  # Feature comparison
    PRICING_CARD = "PRICING_CARD"  # Price display
    STATS_ROW = "STATS_ROW"        # Statistics display
    
    # Layout blocks
    DIVIDER = "DIVIDER"            # Horizontal divider
    SPACER = "SPACER"              # Vertical space
    ACCORDION = "ACCORDION"        # Expandable FAQ
    TABS = "TABS"                  # Tabbed content
    
    # Service-specific blocks
    SERVICE_OVERVIEW = "SERVICE_OVERVIEW"      # Standard service intro
    WHO_ITS_FOR = "WHO_ITS_FOR"               # Target audience
    DELIVERABLES = "DELIVERABLES"             # What you receive
    HOW_IT_WORKS = "HOW_IT_WORKS"             # Process steps
    TIMELINE = "TIMELINE"                      # Turnaround info
    CVP_RELATIONSHIP = "CVP_RELATIONSHIP"      # CVP add-on vs standalone
    WHAT_THIS_IS_NOT = "WHAT_THIS_IS_NOT"     # Clarifications/disclaimers


class CTAAction(str, Enum):
    """CTA button action types."""
    START_INTAKE = "START_INTAKE"      # Route to intake form
    BUY_NOW = "BUY_NOW"                # Direct purchase
    ADD_TO_CVP = "ADD_TO_CVP"          # Add as CVP addon
    BOOK_CONSULTATION = "BOOK_CONSULTATION"  # Calendar booking
    CONTACT = "CONTACT"                # Contact form
    EXTERNAL_LINK = "EXTERNAL_LINK"    # External URL
    INTERNAL_LINK = "INTERNAL_LINK"    # Internal route


class MediaType(str, Enum):
    """Allowed media file types."""
    IMAGE_JPG = "image/jpeg"
    IMAGE_PNG = "image/png"
    IMAGE_WEBP = "image/webp"
    PDF = "application/pdf"
    VIDEO_MP4 = "video/mp4"


# ============================================================================
# BLOCK SCHEMAS
# ============================================================================

class BlockBase(BaseModel):
    """Base block schema."""
    block_id: str
    block_type: BlockType
    order: int = 0
    visible: bool = True


class TextBlock(BlockBase):
    """Rich text block."""
    block_type: BlockType = BlockType.TEXT
    content: str
    alignment: str = "left"  # left, center, right


class HeadingBlock(BlockBase):
    """Heading block."""
    block_type: BlockType = BlockType.HEADING
    content: str
    level: int = 2  # 1-6
    alignment: str = "left"


class ImageBlock(BlockBase):
    """Image block."""
    block_type: BlockType = BlockType.IMAGE
    src: str  # URL or GridFS ID
    alt: str
    caption: Optional[str] = None
    width: Optional[str] = None  # e.g., "100%", "500px"
    alignment: str = "center"


class VideoEmbedBlock(BlockBase):
    """Safe video embed (YouTube/Vimeo only)."""
    block_type: BlockType = BlockType.VIDEO_EMBED
    provider: str  # youtube, vimeo
    video_id: str  # Sanitized video ID only
    title: Optional[str] = None
    aspect_ratio: str = "16:9"


class CTAButtonBlock(BlockBase):
    """Call-to-action button."""
    block_type: BlockType = BlockType.CTA_BUTTON
    label: str
    action: CTAAction
    service_code: Optional[str] = None  # For intake/purchase CTAs
    url: Optional[str] = None  # For link CTAs
    variant: str = "primary"  # primary, secondary, outline
    full_width: bool = False


class FeatureListBlock(BlockBase):
    """Feature list with icons."""
    block_type: BlockType = BlockType.FEATURE_LIST
    title: Optional[str] = None
    features: List[Dict[str, str]]  # [{icon, text}]


class ComparisonTableBlock(BlockBase):
    """Feature comparison table."""
    block_type: BlockType = BlockType.COMPARISON_TABLE
    title: Optional[str] = None
    headers: List[str]
    rows: List[Dict[str, Any]]  # [{feature, values: []}]


class AccordionBlock(BlockBase):
    """FAQ/Accordion block."""
    block_type: BlockType = BlockType.ACCORDION
    title: Optional[str] = None
    items: List[Dict[str, str]]  # [{question, answer}]


class ServiceOverviewBlock(BlockBase):
    """Service overview section."""
    block_type: BlockType = BlockType.SERVICE_OVERVIEW
    headline: str
    description: str
    highlights: List[str] = []


class WhoItsForBlock(BlockBase):
    """Target audience section."""
    block_type: BlockType = BlockType.WHO_ITS_FOR
    title: str = "Who It's For"
    ideal_for: List[str]
    not_for: List[str] = []


class DeliverablesBlock(BlockBase):
    """What you receive section."""
    block_type: BlockType = BlockType.DELIVERABLES
    title: str = "What You Receive"
    items: List[Dict[str, str]]  # [{name, description, format}]


class HowItWorksBlock(BlockBase):
    """Process steps section."""
    block_type: BlockType = BlockType.HOW_IT_WORKS
    title: str = "How It Works"
    steps: List[Dict[str, str]]  # [{step_number, title, description}]


class TimelineBlock(BlockBase):
    """Turnaround timeline section."""
    block_type: BlockType = BlockType.TIMELINE
    title: str = "Timeline"
    standard_turnaround: str
    fast_track_available: bool = False
    fast_track_turnaround: Optional[str] = None


class CVPRelationshipBlock(BlockBase):
    """CVP add-on vs standalone section."""
    block_type: BlockType = BlockType.CVP_RELATIONSHIP
    title: str = "CVP Subscription"
    purchase_mode: str  # STANDALONE, CVP_ADDON, BOTH
    standalone_description: Optional[str] = None
    addon_description: Optional[str] = None
    cvp_benefits: List[str] = []


class WhatThisIsNotBlock(BlockBase):
    """Clarifications/disclaimers section."""
    block_type: BlockType = BlockType.WHAT_THIS_IS_NOT
    title: str = "Important Notes"
    clarifications: List[str]
    disclaimer: Optional[str] = None


# ============================================================================
# PAGE MODELS
# ============================================================================

class SEOMetadata(BaseModel):
    """SEO metadata for pages."""
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    canonical_url: Optional[str] = None
    no_index: bool = False  # For preview environments


class CMSPage(BaseModel):
    """CMS Page model."""
    page_id: str
    page_type: PageType
    status: PageStatus = PageStatus.DRAFT
    
    # URL structure
    slug: str
    category_slug: Optional[str] = None  # For service pages
    full_path: str  # Computed: /services/{category_slug}/{slug}
    
    # Service linkage (for SERVICE pages)
    service_code: Optional[str] = None
    
    # Content
    title: str
    subtitle: Optional[str] = None
    hero_image: Optional[str] = None
    blocks: List[Dict[str, Any]] = []
    
    # SEO
    seo: SEOMetadata = SEOMetadata()
    
    # Display
    display_order: int = 0
    visible_in_nav: bool = True
    
    # Audit
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"
    updated_by: str = "system"
    published_at: Optional[datetime] = None
    published_by: Optional[str] = None


class CMSRedirect(BaseModel):
    """URL redirect mapping for slug changes."""
    redirect_id: str
    from_path: str
    to_path: str
    redirect_type: int = 301  # 301 permanent, 302 temporary
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"


class CMSMedia(BaseModel):
    """CMS media asset."""
    media_id: str
    filename: str
    original_filename: str
    media_type: MediaType
    size_bytes: int
    sha256_hash: str
    
    # Storage
    storage_type: str  # "gridfs" or "external"
    gridfs_id: Optional[str] = None
    external_url: Optional[str] = None
    
    # Metadata
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    tags: List[str] = []
    
    # Status
    is_published: bool = False
    
    # Audit
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    uploaded_by: str = "system"


# ============================================================================
# CATEGORY CONFIGURATION
# ============================================================================

CATEGORY_CONFIG = {
    "ai-automation": {
        "slug": "ai-automation",
        "name": "AI & Automation Services",
        "description": "Streamline your operations with intelligent automation solutions",
        "icon": "cpu",
        "display_order": 1,
        "service_catalogue_category": "ai_automation",
    },
    "market-research": {
        "slug": "market-research",
        "name": "Market Research Services",
        "description": "Data-driven insights to inform your business decisions",
        "icon": "bar-chart-2",
        "display_order": 2,
        "service_catalogue_category": "market_research",
    },
    "compliance-audits": {
        "slug": "compliance-audits",
        "name": "Compliance & Audit Services",
        "description": "Ensure your properties meet regulatory requirements",
        "icon": "shield-check",
        "display_order": 3,
        "service_catalogue_category": "compliance",
    },
    "document-packs": {
        "slug": "document-packs",
        "name": "Landlord Document Packs",
        "description": "Professional documentation for property management",
        "icon": "file-text",
        "display_order": 4,
        "service_catalogue_category": "document_pack",
    },
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_slug(text: str) -> str:
    """Generate URL-safe slug from text."""
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug


def sanitize_video_id(provider: str, url_or_id: str) -> Optional[str]:
    """
    Extract and validate video ID from URL or direct ID.
    Returns None if invalid.
    """
    if provider == "youtube":
        # Match various YouTube URL formats
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$'
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
    elif provider == "vimeo":
        patterns = [
            r'vimeo\.com\/(\d+)',
            r'^(\d+)$'
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
    return None


def validate_block(block: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate a CMS block.
    Returns (is_valid, error_message).
    """
    block_type = block.get("block_type")
    
    if not block_type:
        return False, "Block type is required"
    
    try:
        BlockType(block_type)
    except ValueError:
        return False, f"Invalid block type: {block_type}"
    
    # Type-specific validation
    if block_type == BlockType.VIDEO_EMBED.value:
        provider = block.get("provider")
        video_id = block.get("video_id")
        if provider not in ["youtube", "vimeo"]:
            return False, "Video provider must be youtube or vimeo"
        if not sanitize_video_id(provider, video_id):
            return False, "Invalid video ID"
    
    if block_type == BlockType.CTA_BUTTON.value:
        action = block.get("action")
        try:
            CTAAction(action)
        except ValueError:
            return False, f"Invalid CTA action: {action}"
    
    return True, ""
