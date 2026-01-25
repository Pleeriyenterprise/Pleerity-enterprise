"""
Service Catalogue V2 - Enterprise-grade, fully dynamic, admin-managed service catalogue.

This is the AUTHORITATIVE source of truth for:
- What services exist and are orderable
- Website service listings and Learn More pages
- Get Started routing to correct intake/workflow
- Document eligibility and generation rules
- Add-on availability and pricing

If a service is not defined here, it MUST NOT be executable anywhere.

HARD RULE: CVP BOUNDARY
- CVP (Compliance Vault Pro) remains isolated
- CVP documents = reports/summaries/audits only
- Legal/operational documents flow through Orders only
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime, timezone
from database import database
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS - Authoritative Categories
# ============================================================================

class ServiceCategory(str, Enum):
    """
    Explicit service categories as defined.
    These map to website sections and workflow routing.
    """
    AI_AUTOMATION = "ai_automation"           # Workflow blueprints, process mapping, AI tools
    MARKET_RESEARCH = "market_research"       # Basic and advanced market research
    COMPLIANCE = "compliance"                 # Audits, checklists, tracking
    DOCUMENT_PACK = "document_pack"           # Essential, Tenancy, Ultimate packs
    SUBSCRIPTION = "subscription"             # CVP subscription tiers
    CLEARFORM = "clearform"                   # ClearForm document generation product


class PricingModel(str, Enum):
    """How the service is priced."""
    ONE_TIME = "one_time"                     # Single purchase
    SUBSCRIPTION_MONTHLY = "subscription_monthly"  # Monthly recurring
    INCLUDED = "included"                     # Included in subscription


class ProductType(str, Enum):
    """Product type for Stripe integration."""
    ONE_TIME = "one_time"
    RECURRING = "recurring"


class DeliveryType(str, Enum):
    """How deliverables are provided."""
    DIGITAL = "digital"                       # Digital only (DOCX + PDF)
    DIGITAL_PRINTED = "digital+printed"       # Digital with printed option
    PORTAL = "portal"                         # Portal access only (CVP)


class GenerationMode(str, Enum):
    """How documents are generated."""
    TEMPLATE_MERGE = "TEMPLATE_MERGE"         # Static template merge only
    GPT_ENHANCED = "GPT_ENHANCED"             # Template + GPT sections
    GPT_FULL = "GPT_FULL"                     # Full GPT generation


class PackTier(str, Enum):
    """Document pack hierarchy - Essential → Plus → Pro."""
    ESSENTIAL = "ESSENTIAL"
    PLUS = "PLUS"
    PRO = "PRO"


# ============================================================================
# PRICING VARIANT SCHEMA
# ============================================================================

class PricingVariant(BaseModel):
    """
    Pricing variant for a service (standard, fast_track, printed).
    Each variant has its own Stripe price ID.
    """
    variant_code: str                         # e.g., "standard", "fast_track", "printed"
    variant_name: str                         # e.g., "Standard", "Fast Track (+£20)"
    price_amount: int                         # In pence
    stripe_price_id: str                      # Stripe Price ID
    target_due_hours: int = 72                # SLA target
    is_addon: bool = False                    # True for fast_track, printed
    addon_type: Optional[str] = None          # "delivery_speed" or "delivery_format"


# ============================================================================
# DOCUMENT DEFINITION SCHEMA
# ============================================================================

class DocumentTemplate(BaseModel):
    """
    Document template definition within a service or pack.
    """
    template_code: str                        # e.g., "doc_rent_arrears_letter_template"
    template_name: str                        # e.g., "Rent Arrears Letter"
    format: str = "docx"                      # docx, pdf, or both
    generation_order: int = 0                 # Order within pack
    gpt_sections: List[str] = []              # GPT placeholders to populate
    is_optional: bool = False                 # Can user deselect?


# ============================================================================
# INTAKE FIELD SCHEMA
# ============================================================================

class IntakeFieldType(str, Enum):
    """Types of intake fields."""
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    CURRENCY = "currency"
    DATE = "date"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    CHECKBOX = "checkbox"
    FILE = "file"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"


class IntakeFieldSchema(BaseModel):
    """Schema for a single intake field - follows CRM Field Dictionary."""
    field_id: str                             # API name from CRM dictionary
    label: str                                # Human-readable label
    field_type: IntakeFieldType
    required: bool = True
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    options: Optional[List[str]] = None       # For select/multi_select
    validation_regex: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    default_value: Optional[Any] = None
    order: int = 0
    conditional_on: Optional[str] = None      # Field ID that controls visibility
    conditional_value: Optional[Any] = None   # Value that triggers visibility


# ============================================================================
# SERVICE CATALOGUE ENTRY
# ============================================================================

class ServiceCatalogueEntryV2(BaseModel):
    """
    Complete service definition - Authoritative record.
    
    This is the single source of truth for all service behaviour.
    """
    # === Identity (immutable after creation) ===
    service_code: str = Field(..., description="Unique immutable service code")
    
    # === Display ===
    service_name: str
    description: str                          # Short description for catalogue
    long_description: Optional[str] = None    # Full description for Learn More page
    icon: Optional[str] = None                # Icon identifier for UI
    
    # === Classification ===
    category: ServiceCategory
    tags: List[str] = []
    
    # === Website Display ===
    website_preview: Optional[str] = None     # Preview text for website cards
    learn_more_slug: Optional[str] = None     # URL slug for Learn More page
    
    # === Pricing (Multi-variant) ===
    pricing_model: PricingModel
    base_price: int = 0                       # Base price in pence
    price_currency: str = "gbp"
    vat_rate: float = 0.20                    # 20% UK VAT
    
    # Pricing variants (standard, fast_track, printed)
    pricing_variants: List[PricingVariant] = []
    
    # === Add-ons ===
    fast_track_available: bool = False        # +£20, 24hr delivery
    fast_track_price: int = 2000              # £20 in pence
    fast_track_hours: int = 24
    
    printed_copy_available: bool = False      # +£25, postal delivery
    printed_copy_price: int = 2500            # £25 in pence
    
    # === Delivery ===
    delivery_type: DeliveryType = DeliveryType.DIGITAL
    standard_turnaround_hours: int = 72       # Default SLA
    delivery_format: str = "digital"          # digital, zip_bundle, portal
    
    # === Workflow Routing ===
    workflow_name: str                        # Workflow to execute
    product_type: ProductType = ProductType.ONE_TIME
    
    # === Documents ===
    documents_generated: List[DocumentTemplate] = []
    
    # === Document Pack Hierarchy (for DOCUMENT_PACK category only) ===
    pack_tier: Optional[PackTier] = None      # ESSENTIAL, PLUS, PRO
    includes_lower_tiers: bool = False        # PRO includes PLUS + ESSENTIAL
    parent_pack_code: Optional[str] = None    # For tier inheritance
    
    # === Intake Fields (CRM Field Dictionary) ===
    intake_fields: List[IntakeFieldSchema] = []
    
    # === Generation ===
    generation_mode: GenerationMode = GenerationMode.TEMPLATE_MERGE
    master_prompt_id: Optional[str] = None    # Reference to authoritative prompt
    gpt_sections: List[str] = []              # GPT placeholders this service uses
    
    # === Review ===
    review_required: bool = True              # Human review gate
    
    # === CVP Integration ===
    requires_cvp_subscription: bool = False
    is_cvp_feature: bool = False              # True = CVP-only feature
    allowed_plans: List[str] = []             # Empty = all plans
    
    # === Status ===
    active: bool = True
    display_order: int = 0                    # UI ordering
    
    # === Audit ===
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage."""
        data = self.model_dump()
        # Convert enums to values
        data["category"] = self.category.value
        data["pricing_model"] = self.pricing_model.value
        data["delivery_type"] = self.delivery_type.value
        data["generation_mode"] = self.generation_mode.value
        data["product_type"] = self.product_type.value
        if self.pack_tier:
            data["pack_tier"] = self.pack_tier.value
        # Convert nested models
        data["pricing_variants"] = [v.model_dump() for v in self.pricing_variants]
        data["documents_generated"] = [d.model_dump() for d in self.documents_generated]
        data["intake_fields"] = [f.model_dump() for f in self.intake_fields]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceCatalogueEntryV2":
        """Create from MongoDB document."""
        # Handle enum conversion
        if "category" in data and isinstance(data["category"], str):
            data["category"] = ServiceCategory(data["category"])
        if "pricing_model" in data and isinstance(data["pricing_model"], str):
            data["pricing_model"] = PricingModel(data["pricing_model"])
        if "delivery_type" in data and isinstance(data["delivery_type"], str):
            data["delivery_type"] = DeliveryType(data["delivery_type"])
        if "generation_mode" in data and isinstance(data["generation_mode"], str):
            data["generation_mode"] = GenerationMode(data["generation_mode"])
        if "product_type" in data and isinstance(data["product_type"], str):
            data["product_type"] = ProductType(data["product_type"])
        if "pack_tier" in data and data["pack_tier"] and isinstance(data["pack_tier"], str):
            data["pack_tier"] = PackTier(data["pack_tier"])
        
        # Handle nested models
        if "pricing_variants" in data:
            data["pricing_variants"] = [
                PricingVariant(**v) if isinstance(v, dict) else v 
                for v in data["pricing_variants"]
            ]
        if "documents_generated" in data:
            data["documents_generated"] = [
                DocumentTemplate(**d) if isinstance(d, dict) else d 
                for d in data["documents_generated"]
            ]
        if "intake_fields" in data:
            data["intake_fields"] = [
                IntakeFieldSchema(**f) if isinstance(f, dict) else f 
                for f in data["intake_fields"]
            ]
        
        return cls(**data)
    
    def calculate_total_price(
        self,
        fast_track: bool = False,
        printed_copy: bool = False,
    ) -> Dict[str, Any]:
        """
        Calculate total price with add-ons.
        Returns breakdown for transparency.
        """
        base = self.base_price
        addons = []
        
        if fast_track and self.fast_track_available:
            addons.append({
                "name": "Fast Track Delivery",
                "code": "fast_track",
                "price": self.fast_track_price,
            })
        
        if printed_copy and self.printed_copy_available:
            addons.append({
                "name": "Printed Copy",
                "code": "printed_copy",
                "price": self.printed_copy_price,
            })
        
        subtotal = base + sum(a["price"] for a in addons)
        vat = int(subtotal * self.vat_rate)
        total = subtotal + vat
        
        return {
            "base_price": base,
            "addons": addons,
            "subtotal": subtotal,
            "vat_rate": self.vat_rate,
            "vat_amount": vat,
            "total": total,
            "currency": self.price_currency,
        }


# ============================================================================
# SERVICE CATALOGUE SERVICE V2
# ============================================================================

class ServiceCatalogueServiceV2:
    """
    Service for managing the Service Catalogue V2.
    All service lookups MUST go through this service.
    
    This is the single source of truth - if not here, not executable.
    """
    
    COLLECTION = "service_catalogue_v2"
    
    async def get_service(self, service_code: str) -> Optional[ServiceCatalogueEntryV2]:
        """Get a service by code."""
        db = database.get_db()
        doc = await db[self.COLLECTION].find_one(
            {"service_code": service_code},
            {"_id": 0}
        )
        if not doc:
            return None
        return ServiceCatalogueEntryV2.from_dict(doc)
    
    async def get_active_service(self, service_code: str) -> Optional[ServiceCatalogueEntryV2]:
        """Get a service only if it's active."""
        db = database.get_db()
        doc = await db[self.COLLECTION].find_one(
            {"service_code": service_code, "active": True},
            {"_id": 0}
        )
        if not doc:
            return None
        return ServiceCatalogueEntryV2.from_dict(doc)
    
    async def list_services(
        self,
        category: Optional[ServiceCategory] = None,
        active_only: bool = True,
        is_cvp_feature: Optional[bool] = None,
    ) -> List[ServiceCatalogueEntryV2]:
        """List services with optional filtering."""
        db = database.get_db()
        
        query = {}
        if active_only:
            query["active"] = True
        if category:
            query["category"] = category.value
        if is_cvp_feature is not None:
            query["is_cvp_feature"] = is_cvp_feature
        
        cursor = db[self.COLLECTION].find(query, {"_id": 0}).sort("display_order", 1)
        docs = await cursor.to_list(length=None)
        
        return [ServiceCatalogueEntryV2.from_dict(d) for d in docs]
    
    async def list_by_category(
        self,
        category: ServiceCategory,
        active_only: bool = True,
    ) -> List[ServiceCatalogueEntryV2]:
        """List services in a specific category."""
        return await self.list_services(category=category, active_only=active_only)
    
    async def list_document_packs(
        self,
        active_only: bool = True,
    ) -> List[ServiceCatalogueEntryV2]:
        """List document packs in tier order."""
        services = await self.list_services(
            category=ServiceCategory.DOCUMENT_PACK,
            active_only=active_only
        )
        # Sort by pack tier order
        tier_order = {"ESSENTIAL": 1, "PLUS": 2, "PRO": 3}
        return sorted(
            services,
            key=lambda s: tier_order.get(s.pack_tier.value if s.pack_tier else "", 99)
        )
    
    async def get_pack_documents(
        self,
        service_code: str,
    ) -> List[DocumentTemplate]:
        """
        Get all documents for a pack, including inherited from lower tiers.
        Implements pack hierarchy: PRO includes PLUS includes ESSENTIAL.
        """
        service = await self.get_service(service_code)
        if not service or service.category != ServiceCategory.DOCUMENT_PACK:
            return []
        
        documents = list(service.documents_generated)
        
        # If this pack includes lower tiers, fetch them
        if service.includes_lower_tiers and service.parent_pack_code:
            parent = await self.get_service(service.parent_pack_code)
            if parent:
                parent_docs = await self.get_pack_documents(parent.service_code)
                # Prepend parent docs (lower tier docs come first)
                documents = parent_docs + documents
        
        return documents
    
    async def create_service(
        self,
        entry: ServiceCatalogueEntryV2,
        created_by: str,
    ) -> ServiceCatalogueEntryV2:
        """Create a new service in the catalogue."""
        db = database.get_db()
        
        # Check for duplicate service_code
        existing = await db[self.COLLECTION].find_one({"service_code": entry.service_code})
        if existing:
            raise ValueError(f"Service code already exists: {entry.service_code}")
        
        # Set audit fields
        entry.created_at = datetime.now(timezone.utc)
        entry.updated_at = datetime.now(timezone.utc)
        entry.created_by = created_by
        entry.updated_by = created_by
        
        await db[self.COLLECTION].insert_one(entry.to_dict())
        logger.info(f"Service created: {entry.service_code} by {created_by}")
        
        return entry
    
    async def update_service(
        self,
        service_code: str,
        updates: Dict[str, Any],
        updated_by: str,
    ) -> Optional[ServiceCatalogueEntryV2]:
        """Update a service. service_code cannot be changed."""
        db = database.get_db()
        
        # Prevent service_code modification
        if "service_code" in updates:
            del updates["service_code"]
        
        updates["updated_at"] = datetime.now(timezone.utc)
        updates["updated_by"] = updated_by
        
        result = await db[self.COLLECTION].update_one(
            {"service_code": service_code},
            {"$set": updates}
        )
        
        if result.modified_count == 0:
            return None
        
        logger.info(f"Service updated: {service_code} by {updated_by}")
        return await self.get_service(service_code)
    
    async def deactivate_service(self, service_code: str, updated_by: str) -> bool:
        """Deactivate a service (soft delete)."""
        db = database.get_db()
        
        result = await db[self.COLLECTION].update_one(
            {"service_code": service_code},
            {
                "$set": {
                    "active": False,
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": updated_by,
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Service deactivated: {service_code} by {updated_by}")
            return True
        return False
    
    async def activate_service(self, service_code: str, updated_by: str) -> bool:
        """Activate a service."""
        db = database.get_db()
        
        result = await db[self.COLLECTION].update_one(
            {"service_code": service_code},
            {
                "$set": {
                    "active": True,
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": updated_by,
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Service activated: {service_code} by {updated_by}")
            return True
        return False
    
    async def validate_service_for_order(
        self,
        service_code: str,
        user_plan: Optional[str] = None,
        has_cvp_subscription: bool = False,
    ) -> tuple[bool, str]:
        """
        Validate if a service can be ordered.
        Returns (is_valid, error_message).
        """
        service = await self.get_active_service(service_code)
        
        if not service:
            return False, f"Service not found or inactive: {service_code}"
        
        if service.requires_cvp_subscription and not has_cvp_subscription:
            return False, f"Service {service_code} requires an active CVP subscription"
        
        if service.allowed_plans and user_plan not in service.allowed_plans:
            return False, f"Service {service_code} is not available for plan {user_plan}"
        
        return True, ""
    
    async def get_stripe_price_id(
        self,
        service_code: str,
        variant: str = "standard",
    ) -> Optional[str]:
        """Get Stripe price ID for a service variant."""
        service = await self.get_service(service_code)
        if not service:
            return None
        
        for v in service.pricing_variants:
            if v.variant_code == variant:
                return v.stripe_price_id
        
        return None
    
    async def calculate_order_price(
        self,
        service_code: str,
        fast_track: bool = False,
        printed_copy: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Calculate total order price with add-ons."""
        service = await self.get_service(service_code)
        if not service:
            return None
        
        return service.calculate_total_price(
            fast_track=fast_track,
            printed_copy=printed_copy,
        )
    
    async def get_workflow_name(self, service_code: str) -> Optional[str]:
        """Get workflow name for a service."""
        service = await self.get_service(service_code)
        return service.workflow_name if service else None
    
    async def get_intake_fields(self, service_code: str) -> List[IntakeFieldSchema]:
        """Get intake fields for a service."""
        service = await self.get_service(service_code)
        if not service:
            return []
        return sorted(service.intake_fields, key=lambda f: f.order)
    
    async def count_services(
        self,
        category: Optional[ServiceCategory] = None,
        active_only: bool = True,
    ) -> int:
        """Count services."""
        db = database.get_db()
        query = {}
        if active_only:
            query["active"] = True
        if category:
            query["category"] = category.value
        return await db[self.COLLECTION].count_documents(query)
    
    async def ensure_indexes(self):
        """Create database indexes."""
        db = database.get_db()
        await db[self.COLLECTION].create_index("service_code", unique=True)
        await db[self.COLLECTION].create_index("category")
        await db[self.COLLECTION].create_index("active")
        await db[self.COLLECTION].create_index("display_order")
        logger.info("Service catalogue V2 indexes created")


# Singleton instance
service_catalogue_v2 = ServiceCatalogueServiceV2()
