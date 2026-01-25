"""
CMS Models for Admin Site Builder
Safe Block System with predefined block types
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# ============================================
# Block Type Definitions (Safe Block System)
# ============================================

class BlockType(str, Enum):
    """Predefined safe block types - NO arbitrary HTML allowed"""
    HERO = "HERO"
    TEXT_BLOCK = "TEXT_BLOCK"
    CTA = "CTA"
    FAQ = "FAQ"
    PRICING_TABLE = "PRICING_TABLE"
    FEATURES_GRID = "FEATURES_GRID"
    TESTIMONIALS = "TESTIMONIALS"
    IMAGE_GALLERY = "IMAGE_GALLERY"
    VIDEO_EMBED = "VIDEO_EMBED"
    CONTACT_FORM = "CONTACT_FORM"
    STATS_BAR = "STATS_BAR"
    LOGO_CLOUD = "LOGO_CLOUD"
    TEAM_SECTION = "TEAM_SECTION"
    SPACER = "SPACER"


# Individual Block Content Schemas
class HeroBlockContent(BaseModel):
    headline: str = Field(..., max_length=200)
    subheadline: Optional[str] = Field(None, max_length=500)
    cta_text: Optional[str] = Field(None, max_length=50)
    cta_link: Optional[str] = None
    secondary_cta_text: Optional[str] = Field(None, max_length=50)
    secondary_cta_link: Optional[str] = None
    background_image_id: Optional[str] = None
    background_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    alignment: Literal["left", "center", "right"] = "center"


class TextBlockContent(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    body: str = Field(..., max_length=5000)
    alignment: Literal["left", "center", "right"] = "left"


class CTABlockContent(BaseModel):
    headline: str = Field(..., max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    button_text: str = Field(..., max_length=50)
    button_link: str
    style: Literal["primary", "secondary", "outline"] = "primary"


class FAQItem(BaseModel):
    question: str = Field(..., max_length=300)
    answer: str = Field(..., max_length=2000)


class FAQBlockContent(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    items: List[FAQItem] = Field(..., min_length=1, max_length=20)


class PricingTier(BaseModel):
    name: str = Field(..., max_length=50)
    price: str = Field(..., max_length=50)  # e.g., "£29/mo"
    description: Optional[str] = Field(None, max_length=200)
    features: List[str] = Field(..., max_length=10)
    cta_text: str = Field(default="Get Started", max_length=50)
    cta_link: str
    is_highlighted: bool = False


class PricingTableContent(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    tiers: List[PricingTier] = Field(..., min_length=1, max_length=5)


class FeatureItem(BaseModel):
    icon: Optional[str] = Field(None, max_length=50)  # Icon name from allowed set
    title: str = Field(..., max_length=100)
    description: str = Field(..., max_length=500)


class FeaturesGridContent(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    features: List[FeatureItem] = Field(..., min_length=1, max_length=12)
    columns: Literal[2, 3, 4] = 3


class TestimonialItem(BaseModel):
    quote: str = Field(..., max_length=1000)
    author_name: str = Field(..., max_length=100)
    author_title: Optional[str] = Field(None, max_length=100)
    author_company: Optional[str] = Field(None, max_length=100)
    author_image_id: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)


class TestimonialsContent(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    testimonials: List[TestimonialItem] = Field(..., min_length=1, max_length=10)
    style: Literal["cards", "carousel", "quote"] = "cards"


class ImageGalleryItem(BaseModel):
    image_id: str
    alt_text: str = Field(..., max_length=200)
    caption: Optional[str] = Field(None, max_length=300)


class ImageGalleryContent(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    images: List[ImageGalleryItem] = Field(..., min_length=1, max_length=20)
    layout: Literal["grid", "masonry", "slider"] = "grid"


class VideoEmbedContent(BaseModel):
    """Only YouTube and Vimeo allowed for safety"""
    title: Optional[str] = Field(None, max_length=200)
    video_url: str  # Validated to be YouTube or Vimeo
    caption: Optional[str] = Field(None, max_length=300)
    autoplay: bool = False


class ContactFormContent(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    form_type: Literal["contact", "quote", "callback"] = "contact"
    success_message: str = Field(default="Thank you! We'll be in touch soon.", max_length=200)


class StatItem(BaseModel):
    value: str = Field(..., max_length=50)  # e.g., "500+", "98%"
    label: str = Field(..., max_length=100)


class StatsBarContent(BaseModel):
    stats: List[StatItem] = Field(..., min_length=1, max_length=6)
    background_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class LogoItem(BaseModel):
    image_id: str
    alt_text: str = Field(..., max_length=100)
    link: Optional[str] = None


class LogoCloudContent(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    logos: List[LogoItem] = Field(..., min_length=1, max_length=20)


class TeamMember(BaseModel):
    name: str = Field(..., max_length=100)
    role: str = Field(..., max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    image_id: Optional[str] = None
    linkedin: Optional[str] = None


class TeamSectionContent(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    members: List[TeamMember] = Field(..., min_length=1, max_length=20)


class SpacerContent(BaseModel):
    height: Literal["sm", "md", "lg", "xl"] = "md"


# ============================================
# Content Block Model
# ============================================

class ContentBlock(BaseModel):
    """Individual content block within a page"""
    block_id: str
    block_type: BlockType
    content: Dict[str, Any]  # Schema-validated based on block_type
    visible: bool = True
    order: int


# ============================================
# SEO Metadata
# ============================================

class SEOMetadata(BaseModel):
    meta_title: Optional[str] = Field(None, max_length=70)
    meta_description: Optional[str] = Field(None, max_length=500)
    og_title: Optional[str] = Field(None, max_length=70)
    og_description: Optional[str] = Field(None, max_length=200)
    og_image_id: Optional[str] = None
    canonical_url: Optional[str] = None
    robots: Literal["index,follow", "noindex,follow", "index,nofollow", "noindex,nofollow"] = "index,follow"


# ============================================
# CMS Page Models
# ============================================

class PageStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class PageType(str, Enum):
    """Types of CMS pages for marketing website."""
    GENERIC = "GENERIC"          # Generic pages (about, contact, etc.)
    HUB = "HUB"                   # /services hub page
    CATEGORY = "CATEGORY"        # /services/{category}
    SERVICE = "SERVICE"          # /services/{category}/{slug}
    LANDING = "LANDING"          # Landing/campaign pages
    LEGAL = "LEGAL"              # Terms, privacy, etc.


class PurchaseMode(str, Enum):
    """How a service can be purchased."""
    STANDALONE = "STANDALONE"     # Can only be purchased standalone
    CVP_ADDON = "CVP_ADDON"       # Can only be added to CVP subscription
    BOTH = "BOTH"                 # Can be purchased either way


# Category configuration for marketing website
CATEGORY_CONFIG = {
    "ai-automation": {
        "slug": "ai-automation",
        "name": "AI & Automation Services",
        "tagline": "Streamline your operations with intelligent automation solutions",
        "description": "Our AI-powered services help SMEs automate repetitive tasks, optimise workflows, and make data-driven decisions.",
        "icon": "cpu",
        "display_order": 1,
        "service_catalogue_category": "ai_automation",
    },
    "market-research": {
        "slug": "market-research",
        "name": "Market Research Services",
        "tagline": "Data-driven insights to inform your business decisions",
        "description": "Comprehensive market analysis to help you understand your competition, identify opportunities, and make informed strategic decisions.",
        "icon": "bar-chart-2",
        "display_order": 2,
        "service_catalogue_category": "market_research",
    },
    "compliance-audits": {
        "slug": "compliance-audits",
        "name": "Compliance & Audit Services",
        "tagline": "Ensure your properties meet regulatory requirements",
        "description": "Professional compliance audits and documentation for landlords and property managers. Note: Our services provide guidance only and do not constitute legal advice.",
        "icon": "shield-check",
        "display_order": 3,
        "service_catalogue_category": "compliance",
    },
    "document-packs": {
        "slug": "document-packs",
        "name": "Landlord Document Packs",
        "tagline": "Professional documentation for property management",
        "description": "Professionally generated document packs tailored to your tenancy requirements. Includes essential notices, agreements, and compliance documentation.",
        "icon": "file-text",
        "display_order": 4,
        "service_catalogue_category": "document_pack",
    },
}


class CMSPageCreate(BaseModel):
    """Create a new CMS page"""
    slug: str = Field(..., pattern=r'^[a-z0-9-]+$', max_length=100)
    title: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    page_type: PageType = PageType.GENERIC
    category_slug: Optional[str] = Field(None, max_length=100)  # Parent category for SERVICE pages
    service_code: Optional[str] = Field(None, max_length=50)    # Linked service from catalogue


class CMSPageUpdate(BaseModel):
    """Update CMS page content (creates draft)"""
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    slug: Optional[str] = Field(None, pattern=r'^[a-z0-9-]+$', max_length=100)
    blocks: Optional[List[ContentBlock]] = None
    seo: Optional[SEOMetadata] = None
    subtitle: Optional[str] = Field(None, max_length=300)
    hero_image: Optional[str] = None
    display_order: Optional[int] = None
    visible_in_nav: Optional[bool] = None


class CMSPageResponse(BaseModel):
    """CMS page response"""
    page_id: str
    slug: str
    title: str
    description: Optional[str] = None
    status: PageStatus
    page_type: PageType = PageType.GENERIC
    category_slug: Optional[str] = None
    service_code: Optional[str] = None
    full_path: Optional[str] = None
    subtitle: Optional[str] = None
    hero_image: Optional[str] = None
    blocks: List[ContentBlock] = []
    seo: Optional[SEOMetadata] = None
    display_order: int = 0
    visible_in_nav: bool = True
    current_version: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    created_by: str
    updated_by: str


# Service Page Content Sections (for SERVICE page type)
class ServicePageSection(str, Enum):
    """Required sections for service pages."""
    OVERVIEW = "OVERVIEW"               # What this service is
    WHO_ITS_FOR = "WHO_ITS_FOR"         # Ideal users, not-for list
    DELIVERABLES = "DELIVERABLES"       # What you receive
    HOW_IT_WORKS = "HOW_IT_WORKS"       # Process steps
    TIMELINE = "TIMELINE"               # Expected turnaround
    CVP_RELATIONSHIP = "CVP_RELATIONSHIP"  # Standalone vs CVP add-on
    WHAT_THIS_IS_NOT = "WHAT_THIS_IS_NOT"  # Clarifications/disclaimers
    CTA = "CTA"                         # Call to action


class ServiceDeliverable(BaseModel):
    """A single deliverable item."""
    name: str = Field(..., max_length=100)
    description: str = Field(..., max_length=300)
    format: str = Field(default="PDF", max_length=50)  # PDF, DOCX, Portal, etc.


class ProcessStep(BaseModel):
    """A process step for How It Works section."""
    step_number: int
    title: str = Field(..., max_length=100)
    description: str = Field(..., max_length=300)


class ServicePageContent(BaseModel):
    """
    Structured content for SERVICE page type.
    Ensures all required sections are present.
    """
    # Overview section
    overview_headline: str = Field(..., max_length=200)
    overview_description: str = Field(..., max_length=1000)
    overview_highlights: List[str] = Field(default_factory=list, max_length=6)
    
    # Who it's for
    ideal_for: List[str] = Field(..., min_length=1, max_length=6)
    not_for: List[str] = Field(default_factory=list, max_length=4)
    
    # Deliverables
    deliverables: List[ServiceDeliverable] = Field(..., min_length=1)
    
    # How it works
    process_steps: List[ProcessStep] = Field(..., min_length=2, max_length=6)
    
    # Timeline
    standard_turnaround: str = Field(..., max_length=100)  # e.g., "48 hours"
    fast_track_available: bool = False
    fast_track_turnaround: Optional[str] = Field(None, max_length=100)
    
    # CVP Relationship
    purchase_mode: PurchaseMode = PurchaseMode.STANDALONE
    requires_cvp_subscription: bool = False
    standalone_description: Optional[str] = Field(None, max_length=300)
    addon_description: Optional[str] = Field(None, max_length=300)
    cvp_benefits: List[str] = Field(default_factory=list, max_length=4)
    
    # Disclaimers
    clarifications: List[str] = Field(default_factory=list, max_length=5)
    legal_disclaimer: Optional[str] = Field(None, max_length=500)
    
    # CTA
    primary_cta_text: str = Field(default="Start Now", max_length=50)
    primary_cta_action: str = Field(default="START_INTAKE")  # START_INTAKE, BUY_NOW, etc.
    secondary_cta_text: Optional[str] = Field(None, max_length=50)
    secondary_cta_action: Optional[str] = None


class CMSRedirect(BaseModel):
    """URL redirect for slug changes."""
    redirect_id: str
    from_path: str
    to_path: str
    redirect_type: int = 301  # 301 permanent, 302 temporary
    created_at: datetime
    created_by: str


# ============================================
# CMS Revision Models
# ============================================

class CMSRevisionResponse(BaseModel):
    """Revision snapshot for rollback"""
    revision_id: str
    page_id: str
    version: int
    title: str
    blocks: List[ContentBlock]
    seo: Optional[SEOMetadata]
    published_at: datetime
    published_by: str
    notes: Optional[str] = None


# ============================================
# CMS Media Models
# ============================================

class MediaType(str, Enum):
    IMAGE = "IMAGE"
    VIDEO_EMBED = "VIDEO_EMBED"


class CMSMediaCreate(BaseModel):
    """Create media entry"""
    file_name: str = Field(..., max_length=255)
    file_type: str  # MIME type
    alt_text: Optional[str] = Field(None, max_length=200)
    tags: List[str] = []


class CMSMediaResponse(BaseModel):
    """Media library entry"""
    media_id: str
    media_type: MediaType
    file_name: str
    file_url: str
    file_size: Optional[int] = None
    alt_text: Optional[str] = None
    tags: List[str] = []
    uploaded_at: datetime
    uploaded_by: str


# ============================================
# Request/Response Models
# ============================================

class BlockCreateRequest(BaseModel):
    """Add a block to a page"""
    block_type: BlockType
    content: Dict[str, Any]
    position: Optional[int] = None  # Insert at position, or append if None


class BlockUpdateRequest(BaseModel):
    """Update block content"""
    content: Optional[Dict[str, Any]] = None
    visible: Optional[bool] = None
    order: Optional[int] = None


class ReorderBlocksRequest(BaseModel):
    """Reorder blocks"""
    block_order: List[str]  # List of block_ids in new order


class PublishPageRequest(BaseModel):
    """Publish page with notes"""
    notes: Optional[str] = Field(None, max_length=500)


class RollbackRequest(BaseModel):
    """Rollback to a specific revision"""
    revision_id: str
    notes: Optional[str] = Field(None, max_length=500)


class VideoEmbedRequest(BaseModel):
    """Safe video embed request - YouTube/Vimeo only"""
    video_url: str
    title: Optional[str] = None


# Block type to content schema mapping
BLOCK_CONTENT_SCHEMAS = {
    BlockType.HERO: HeroBlockContent,
    BlockType.TEXT_BLOCK: TextBlockContent,
    BlockType.CTA: CTABlockContent,
    BlockType.FAQ: FAQBlockContent,
    BlockType.PRICING_TABLE: PricingTableContent,
    BlockType.FEATURES_GRID: FeaturesGridContent,
    BlockType.TESTIMONIALS: TestimonialsContent,
    BlockType.IMAGE_GALLERY: ImageGalleryContent,
    BlockType.VIDEO_EMBED: VideoEmbedContent,
    BlockType.CONTACT_FORM: ContactFormContent,
    BlockType.STATS_BAR: StatsBarContent,
    BlockType.LOGO_CLOUD: LogoCloudContent,
    BlockType.TEAM_SECTION: TeamSectionContent,
    BlockType.SPACER: SpacerContent,
}
