"""
Document Pack Orchestrator

Implements pack inheritance, canonical ordering, and per-document generation
for the Document Pack services (ESSENTIAL, PLUS, PRO).

Key Features:
- Pack inheritance (PRO inherits PLUS inherits ESSENTIAL)
- Canonical ordering enforced server-side
- Per-document versioning with regeneration support
- Entitlement + Selection filtering
- Integration with Prompt Manager for generation

NON-NEGOTIABLES:
- Canonical order must be enforced
- Each document is a separate versioned item
- prompt_version_used and input_snapshot_hash stored for audit
- Never overwrite prior versions
"""
import hashlib
import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

from bson import ObjectId
from database import database

logger = logging.getLogger(__name__)


# ============================================
# Pack Tier Definitions
# ============================================

class PackTier(str, Enum):
    """Document Pack tiers with inheritance."""
    ESSENTIAL = "ESSENTIAL"
    PLUS = "PLUS"  # Inherits ESSENTIAL
    PRO = "PRO"    # Inherits ESSENTIAL + PLUS


# ============================================
# Document Registry - Authoritative Mapping
# ============================================

@dataclass
class DocumentDefinition:
    """Definition of a document type in the registry."""
    doc_key: str                    # Internal identifier (e.g., doc_rent_arrears_letter_template)
    doc_type: str                   # Prompt Manager doc_type (e.g., RENT_ARREARS_LETTER)
    pack_tier: PackTier             # Tier this doc belongs to
    output_keys: List[str]          # Expected JSON output keys from prompt
    display_name: str               # Human-readable name
    canonical_index: int = 0        # Position in canonical order (set by orchestrator)
    

# Authoritative Document Registry
# Maps doc_key -> DocumentDefinition
DOCUMENT_REGISTRY: Dict[str, DocumentDefinition] = {
    # ========================================
    # ESSENTIAL TIER (5 documents)
    # ========================================
    "doc_rent_arrears_letter_template": DocumentDefinition(
        doc_key="doc_rent_arrears_letter_template",
        doc_type="RENT_ARREARS_LETTER",
        pack_tier=PackTier.ESSENTIAL,
        output_keys=["GPT_RENT_ARREARS_LETTER"],
        display_name="Rent Arrears Letter",
    ),
    "doc_deposit_refund_letter_template": DocumentDefinition(
        doc_key="doc_deposit_refund_letter_template",
        doc_type="DEPOSIT_REFUND_EXPLANATION_LETTER",
        pack_tier=PackTier.ESSENTIAL,
        output_keys=["GPT_DEPOSIT_REFUND_LETTER"],
        display_name="Deposit Refund / Explanation Letter",
    ),
    "doc_tenant_reference_letter_template": DocumentDefinition(
        doc_key="doc_tenant_reference_letter_template",
        doc_type="TENANT_REFERENCE_LETTER",
        pack_tier=PackTier.ESSENTIAL,
        output_keys=["GPT_TENANT_REFERENCE_LETTER"],
        display_name="Tenant Reference Letter",
    ),
    "doc_rent_receipt_template": DocumentDefinition(
        doc_key="doc_rent_receipt_template",
        doc_type="RENT_RECEIPT",
        pack_tier=PackTier.ESSENTIAL,
        output_keys=["GPT_RENT_RECEIPT"],
        display_name="Rent Receipt",
    ),
    "doc_gdpr_notice_template": DocumentDefinition(
        doc_key="doc_gdpr_notice_template",
        doc_type="GDPR_NOTICE",
        pack_tier=PackTier.ESSENTIAL,
        output_keys=["GPT_GDPR_NOTICE"],
        display_name="GDPR / Data Processing Notice",
    ),
    
    # ========================================
    # PLUS TIER (5 documents - Tenancy Legal & Notices)
    # ========================================
    "doc_tenancy_agreement_ast_template": DocumentDefinition(
        doc_key="doc_tenancy_agreement_ast_template",
        doc_type="TENANCY_AGREEMENT_AST",
        pack_tier=PackTier.PLUS,
        output_keys=["agreement_metadata", "GPT_LEGAL_TERMS_BODY"],
        display_name="Assured Shorthold Tenancy (AST) Agreement",
    ),
    "doc_guarantor_agreement_template": DocumentDefinition(
        doc_key="doc_guarantor_agreement_template",
        doc_type="GUARANTOR_AGREEMENT",
        pack_tier=PackTier.PLUS,
        output_keys=["guarantor_details", "GPT_GUARANTOR_TERMS_BODY"],
        display_name="Guarantor Agreement",
    ),
    "doc_tenancy_renewal_template": DocumentDefinition(
        doc_key="doc_tenancy_renewal_template",
        doc_type="TENANCY_RENEWAL",
        pack_tier=PackTier.PLUS,
        output_keys=["agreement_metadata", "GPT_RENEWAL_TERMS_BODY"],
        display_name="Tenancy Renewal / Extension Document",
    ),
    "doc_rent_increase_notice_template": DocumentDefinition(
        doc_key="doc_rent_increase_notice_template",
        doc_type="RENT_INCREASE_NOTICE",
        pack_tier=PackTier.PLUS,
        output_keys=["GPT_RENT_INCREASE_LEGAL_BODY"],
        display_name="Rent Increase Notice",
    ),
    "doc_notice_to_quit_template": DocumentDefinition(
        doc_key="doc_notice_to_quit_template",
        doc_type="NOTICE_TO_QUIT",
        pack_tier=PackTier.PLUS,
        output_keys=["GPT_NOTICE_TO_QUIT_BODY"],
        display_name="Notice to Quit",
    ),
    
    # ========================================
    # PRO TIER (4 documents - Ultimate Pack)
    # ========================================
    "doc_inventory_condition_report": DocumentDefinition(
        doc_key="doc_inventory_condition_report",
        doc_type="INVENTORY_CONDITION_REPORT",
        pack_tier=PackTier.PRO,
        output_keys=["property_overview", "inventory_condition_table", "condition_summary"],
        display_name="Inventory & Condition Report",
    ),
    "doc_deposit_information_pack": DocumentDefinition(
        doc_key="doc_deposit_information_pack",
        doc_type="DEPOSIT_INFORMATION_PACK",
        pack_tier=PackTier.PRO,
        output_keys=["GPT_DEPOSIT_INFORMATION_BODY"],
        display_name="Deposit Information Pack",
    ),
    "doc_property_access_notice": DocumentDefinition(
        doc_key="doc_property_access_notice",
        doc_type="PROPERTY_ACCESS_NOTICE",
        pack_tier=PackTier.PRO,
        output_keys=["GPT_ACCESS_NOTICE_BODY"],
        display_name="Property Access Notice",
    ),
    "doc_additional_landlord_notice": DocumentDefinition(
        doc_key="doc_additional_landlord_notice",
        doc_type="ADDITIONAL_LANDLORD_NOTICE",
        pack_tier=PackTier.PRO,
        output_keys=["landlord_details", "notice_title", "notice_context", "notice_body", "action_required"],
        display_name="Additional Landlord Notice",
    ),
}


# ============================================
# Canonical Order - Server-Side Enforced
# ============================================

# Canonical order lists per pack tier
CANONICAL_ORDER = {
    PackTier.ESSENTIAL: [
        "doc_rent_arrears_letter_template",
        "doc_deposit_refund_letter_template",
        "doc_tenant_reference_letter_template",
        "doc_rent_receipt_template",
        "doc_gdpr_notice_template",
    ],
    PackTier.PLUS: [
        # Essential (inherited)
        "doc_rent_arrears_letter_template",
        "doc_deposit_refund_letter_template",
        "doc_tenant_reference_letter_template",
        "doc_rent_receipt_template",
        "doc_gdpr_notice_template",
        # Plus (Tenancy)
        "doc_tenancy_agreement_ast_template",
        "doc_guarantor_agreement_template",
        "doc_tenancy_renewal_template",
        "doc_rent_increase_notice_template",
        "doc_notice_to_quit_template",
    ],
    PackTier.PRO: [
        # Essential (inherited)
        "doc_rent_arrears_letter_template",
        "doc_deposit_refund_letter_template",
        "doc_tenant_reference_letter_template",
        "doc_rent_receipt_template",
        "doc_gdpr_notice_template",
        # Plus (inherited)
        "doc_tenancy_agreement_ast_template",
        "doc_guarantor_agreement_template",
        "doc_tenancy_renewal_template",
        "doc_rent_increase_notice_template",
        "doc_notice_to_quit_template",
        # Pro
        "doc_inventory_condition_report",
        "doc_deposit_information_pack",
        "doc_property_access_notice",
        "doc_additional_landlord_notice",
    ],
}

# Service code to pack tier mapping (DOC_PACK_TENANCY is alias for PLUS for intake/seed compatibility)
SERVICE_CODE_TO_PACK_TIER = {
    "DOC_PACK_ESSENTIAL": PackTier.ESSENTIAL,
    "DOC_PACK_PLUS": PackTier.PLUS,
    "DOC_PACK_TENANCY": PackTier.PLUS,
    "DOC_PACK_PRO": PackTier.PRO,
}


# ============================================
# Document Item Model
# ============================================

@dataclass
class DocumentItem:
    """
    Represents a single document within a pack order.
    Each document has its own versioning and audit trail.
    """
    item_id: str                            # Unique ID for this item
    order_id: str                           # Parent order ID
    doc_key: str                            # Registry key
    doc_type: str                           # Prompt Manager doc_type
    canonical_index: int                    # Position in canonical order
    display_name: str                       # Human-readable name
    
    # Version tracking
    version: int = 1                        # Current version number
    status: str = "PENDING"                 # PENDING, GENERATING, COMPLETED, FAILED, APPROVED, REJECTED
    
    # Generation metadata
    prompt_version_used: Optional[Dict[str, Any]] = None  # From Prompt Manager
    input_snapshot_hash: Optional[str] = None             # Hash of input data
    
    # Output
    generated_output: Optional[Dict[str, Any]] = None     # Raw LLM output
    files: List[Dict[str, Any]] = field(default_factory=list)  # Generated files (DOCX, PDF)
    
    # Regeneration tracking
    regenerated_from_version: Optional[int] = None
    regen_reason: Optional[str] = None
    regen_notes: Optional[str] = None
    
    # Timestamps
    created_at: Optional[str] = None
    generated_at: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    
    # Error handling
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)


# ============================================
# Document Pack Orchestrator Service
# ============================================

class DocumentPackOrchestrator:
    """
    Orchestrates document pack generation with inheritance,
    canonical ordering, and per-document versioning.
    """
    
    COLLECTION = "document_pack_items"
    
    def __init__(self):
        self._prompt_bridge = None
    
    async def _get_prompt_bridge(self):
        """Lazy load prompt manager bridge."""
        if self._prompt_bridge is None:
            from services.prompt_manager_bridge import prompt_manager_bridge
            self._prompt_bridge = prompt_manager_bridge
        return self._prompt_bridge
    
    # ========================================
    # Pack Tier & Entitlement Logic
    # ========================================
    
    def get_pack_tier(self, service_code: str) -> PackTier:
        """Get pack tier from service code."""
        tier = SERVICE_CODE_TO_PACK_TIER.get(service_code)
        if not tier:
            raise ValueError(f"Unknown service code: {service_code}")
        return tier
    
    def get_allowed_docs(self, pack_tier: PackTier) -> List[str]:
        """
        Get allowed document keys for a pack tier.
        Implements inheritance: PRO > PLUS > ESSENTIAL
        """
        return CANONICAL_ORDER.get(pack_tier, [])
    
    def get_canonical_order(self, pack_tier: PackTier) -> List[str]:
        """Get canonical order list for a pack tier."""
        return CANONICAL_ORDER.get(pack_tier, [])
    
    def get_canonical_index(self, doc_key: str, pack_tier: PackTier) -> int:
        """Get canonical index for a document in a pack tier."""
        order = self.get_canonical_order(pack_tier)
        try:
            return order.index(doc_key)
        except ValueError:
            return -1  # Not in this tier
    
    def _get_selected_docs_for_plan(self, order: Dict[str, Any], service_code: str) -> List[str]:
        """
        Resolve selected doc_keys from order for use in document plan.
        Uses document_pack_info.selected_docs if set (after webhook), else selected_documents,
        else all allowed docs for the pack tier.
        """
        pack_info = order.get("document_pack_info") or {}
        if pack_info.get("selected_docs"):
            return list(pack_info["selected_docs"])
        if order.get("selected_documents"):
            return list(order["selected_documents"])
        return self.get_allowed_docs(self.get_pack_tier(service_code))
    
    # ============================================
    # Document Plan (deterministic, no LLM)
    # ============================================
    
    async def build_document_plan(self, order_id: str) -> Dict[str, Any]:
        """
        Build deterministic document plan for an order. No LLM; no side effects.
        
        Returns:
            {
                "pack_code": str,
                "document_plan": [{"doc_key", "doc_type", "prompt_service_code", "prompt_doc_type", "template_id"}, ...],
                "delivery_mode": ["DOCX", "PDF"],
                "bundle_format": "ZIP"
            }
        Raises:
            ValueError: If order not found or service_code is not a document pack.
        """
        db = database.get_db()
        order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
        if not order:
            raise ValueError(f"Order not found: {order_id}")
        
        service_code = order.get("service_code")
        if not service_code or service_code not in SERVICE_CODE_TO_PACK_TIER:
            raise ValueError(f"Order {order_id} is not a document pack order (service_code={service_code})")
        
        selected_docs = self._get_selected_docs_for_plan(order, service_code)
        docs_ordered = self.filter_and_order_docs(service_code, selected_docs)
        
        document_plan = []
        for doc_key, canonical_index, definition in docs_ordered:
            prompt_service_code = self._get_service_code_for_doc_type(definition.doc_type)
            template_id = None
            try:
                meta = await db.document_templates.find_one(
                    {"service_code": prompt_service_code, "doc_type": definition.doc_type},
                    {"_id": 0, "template_id": 1},
                )
                if meta:
                    template_id = meta.get("template_id")
            except Exception:
                pass
            
            document_plan.append({
                "doc_key": doc_key,
                "doc_type": definition.doc_type,
                "canonical_index": canonical_index,
                "prompt_service_code": prompt_service_code,
                "prompt_doc_type": definition.doc_type,
                "template_id": template_id,
            })
        
        return {
            "pack_code": service_code,
            "document_plan": document_plan,
            "delivery_mode": ["DOCX", "PDF"],
            "bundle_format": "ZIP",
        }
    
    # ========================================
    # Filtering & Ordering
    # ========================================
    
    def filter_and_order_docs(
        self,
        service_code: str,
        selected_docs: List[str],
    ) -> List[Tuple[str, int, DocumentDefinition]]:
        """
        Apply entitlement and selection filters, then sort by canonical order.
        
        Args:
            service_code: The pack service code (DOC_PACK_ESSENTIAL, etc.)
            selected_docs: List of doc_keys selected by client
            
        Returns:
            List of (doc_key, canonical_index, DocumentDefinition) sorted by canonical order
        """
        pack_tier = self.get_pack_tier(service_code)
        allowed_docs = set(self.get_allowed_docs(pack_tier))
        
        # Filter 1: Entitlement - only docs allowed by pack tier
        # Filter 2: Selection - only docs selected by client
        docs_to_generate = [
            doc_key for doc_key in selected_docs
            if doc_key in allowed_docs and doc_key in DOCUMENT_REGISTRY
        ]
        
        # Sort by canonical order
        canonical_order = self.get_canonical_order(pack_tier)
        
        result = []
        for doc_key in docs_to_generate:
            idx = self.get_canonical_index(doc_key, pack_tier)
            if idx >= 0:
                definition = DOCUMENT_REGISTRY[doc_key]
                result.append((doc_key, idx, definition))
        
        # Sort by canonical index
        result.sort(key=lambda x: x[1])
        
        return result
    
    # ========================================
    # Input Hashing
    # ========================================
    
    def compute_input_hash(self, input_data: Dict[str, Any]) -> str:
        """Compute hash of input data for audit trail."""
        serialized = json.dumps(input_data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
    
    # ========================================
    # Document Item Management
    # ========================================
    
    def _generate_item_id(self) -> str:
        """Generate unique document item ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        random_part = hashlib.sha256(
            f"{timestamp}{__import__('os').urandom(8).hex()}".encode()
        ).hexdigest()[:8].upper()
        return f"DI-{timestamp}-{random_part}"
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID for generation_runs."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        random_part = hashlib.sha256(
            f"{timestamp}{__import__('os').urandom(8).hex()}".encode()
        ).hexdigest()[:8].upper()
        return f"GR-{timestamp}-{random_part}"
    
    async def create_document_items(
        self,
        order_id: str,
        service_code: str,
        selected_docs: List[str],
        input_data: Dict[str, Any],
    ) -> List[DocumentItem]:
        """
        Create document items for an order based on selection and entitlement.
        
        Args:
            order_id: The parent order ID
            service_code: Pack service code
            selected_docs: List of doc_keys selected by client
            input_data: Intake data for generation
            
        Returns:
            List of created DocumentItem objects
        """
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        input_hash = self.compute_input_hash(input_data)
        
        # Get filtered and ordered docs
        docs_to_create = self.filter_and_order_docs(service_code, selected_docs)
        
        items = []
        for doc_key, canonical_index, definition in docs_to_create:
            item = DocumentItem(
                item_id=self._generate_item_id(),
                order_id=order_id,
                doc_key=doc_key,
                doc_type=definition.doc_type,
                canonical_index=canonical_index,
                display_name=definition.display_name,
                version=1,
                status="PENDING",
                input_snapshot_hash=input_hash,
                created_at=now,
            )
            items.append(item)
        
        # Store in database
        if items:
            await db[self.COLLECTION].insert_many([item.to_dict() for item in items])
            logger.info(f"Created {len(items)} document items for order {order_id}")
        
        return items
    
    async def get_document_items(self, order_id: str) -> List[Dict[str, Any]]:
        """Get all document items for an order, sorted by canonical order."""
        db = database.get_db()
        
        cursor = db[self.COLLECTION].find(
            {"order_id": order_id},
            {"_id": 0}
        ).sort("canonical_index", 1)
        
        return await cursor.to_list(length=100)
    
    async def get_document_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get a single document item by ID."""
        db = database.get_db()
        return await db[self.COLLECTION].find_one(
            {"item_id": item_id},
            {"_id": 0}
        )
    
    # ========================================
    # Document Generation
    # ========================================
    
    async def generate_document(
        self,
        item_id: str,
        input_data: Dict[str, Any],
        generated_by: str,
    ) -> Dict[str, Any]:
        """
        Generate a single document using the Prompt Manager.
        
        Args:
            item_id: Document item ID
            input_data: Input data for generation
            generated_by: User who triggered generation
            
        Returns:
            Updated document item
        """
        db = database.get_db()
        now = datetime.now(timezone.utc)
        
        # Get item
        item = await self.get_document_item(item_id)
        if not item:
            raise ValueError(f"Document item not found: {item_id}")
        
        # Get document definition
        definition = DOCUMENT_REGISTRY.get(item["doc_key"])
        if not definition:
            raise ValueError(f"Unknown doc_key: {item['doc_key']}")
        
        # Update status to GENERATING
        await db[self.COLLECTION].update_one(
            {"item_id": item_id},
            {"$set": {"status": "GENERATING"}}
        )
        
        try:
            # Get prompt from Prompt Manager
            bridge = await self._get_prompt_bridge()
            
            # Determine service_code for prompt lookup
            # For document packs, we need to map doc_type to service_code
            service_code = self._get_service_code_for_doc_type(definition.doc_type)
            
            # get_prompt_for_service returns (PromptDefinition, ManagedPromptInfo)
            prompt_def, prompt_info = await bridge.get_prompt_for_service(
                service_code=service_code,
                doc_type=definition.doc_type,
            )
            
            if not prompt_def or not prompt_info:
                raise ValueError(f"No active prompt found for {service_code}/{definition.doc_type}")
            
            # Build the prompt with input data
            user_prompt = bridge.build_user_prompt_with_json(
                template=prompt_def.user_prompt_template,
                intake_data=input_data,
            )
            
            # Execute LLM generation
            from services.prompt_service import prompt_service
            llm = await prompt_service._get_llm_provider()
            
            raw_output, tokens = await llm.generate(
                system_prompt=prompt_def.system_prompt,
                user_prompt=user_prompt,
                temperature=prompt_def.temperature,
                max_tokens=prompt_def.max_tokens,
            )
            
            # Parse output
            parsed_output = prompt_service._parse_llm_output(raw_output)
            
            if not parsed_output:
                raise ValueError("Failed to parse LLM output as JSON")
            
            # Validate output keys
            missing_keys = set(definition.output_keys) - set(parsed_output.keys())
            if missing_keys:
                logger.warning(f"Missing output keys for {item_id}: {missing_keys}")
            
            # Update item with success (JSON output)
            update_data = {
                "status": "COMPLETED",
                "generated_output": parsed_output,
                "prompt_version_used": prompt_info.to_dict(),
                "input_snapshot_hash": self.compute_input_hash(input_data),
                "generated_at": now.isoformat(),
                "error_message": None,
            }
            
            await db[self.COLLECTION].update_one(
                {"item_id": item_id},
                {"$set": update_data}
            )
            
            # Render DOCX + PDF and store file references on item
            try:
                from services.template_renderer import template_renderer
                from services.template_renderer import RenderStatus as TRenderStatus
                order_doc = await db.orders.find_one({"order_id": item["order_id"]}, {"_id": 0, "service_code": 1})
                pack_service_code = (order_doc or {}).get("service_code", self._get_service_code_for_doc_type(definition.doc_type))
                render_result = await template_renderer.render_pack_item(
                    order_id=item["order_id"],
                    item_id=item_id,
                    service_code=pack_service_code,
                    doc_type=definition.doc_type,
                    structured_output=parsed_output,
                    intake_snapshot=input_data,
                    item_version=1,
                    status=TRenderStatus.DRAFT,
                )
                if not render_result.success:
                    logger.warning("Pack item render failed for %s: %s", item_id, render_result.error_message)
            except Exception as render_err:
                logger.exception("Pack item render error for %s: %s", item_id, render_err)
            
            # Record execution metrics
            await bridge.record_execution_metrics(
                prompt_info=prompt_info,
                order_id=item.get("order_id", "unknown"),
                execution_time_ms=int((datetime.now(timezone.utc) - now).total_seconds() * 1000),
                prompt_tokens=tokens.get("prompt_tokens", 0),
                completion_tokens=tokens.get("completion_tokens", 0),
                success=True,
            )
            
            # Dual-write to generation_runs for reporting (provider, model, token usage, input hash)
            now_utc = datetime.now(timezone.utc)
            input_hash = self.compute_input_hash(input_data)
            try:
                run_id = self._generate_run_id()
                llm = await prompt_service._get_llm_provider()
                model_used = getattr(llm, "_model", None) or "gemini-2.5-flash"
                await db.generation_runs.insert_one({
                    "run_id": run_id,
                    "order_id": item["order_id"],
                    "template_id": prompt_info.template_id if prompt_info else None,
                    "prompt_version": prompt_info.version if prompt_info else None,
                    "doc_type": definition.doc_type,
                    "status": "COMPLETED",
                    "provider": getattr(llm, "provider_name", "gemini"),
                    "model": model_used,
                    "prompt_tokens": tokens.get("prompt_tokens", 0),
                    "completion_tokens": tokens.get("completion_tokens", 0),
                    "intake_snapshot_hash": input_hash,
                    "started_at": now,
                    "completed_at": now_utc,
                    "created_at": now_utc,
                    "updated_at": now_utc,
                })
            except Exception as e:
                logger.warning("generation_runs dual-write failed (non-fatal): %s", e)
            
            logger.info(f"Generated document {item_id} ({definition.doc_type})")
            
            return await self.get_document_item(item_id)
            
        except Exception as e:
            logger.error(f"Document generation failed for {item_id}: {e}")
            
            await db[self.COLLECTION].update_one(
                {"item_id": item_id},
                {"$set": {
                    "status": "FAILED",
                    "error_message": str(e),
                }}
            )
            
            # Dual-write FAILED run to generation_runs
            try:
                run_id = self._generate_run_id()
                await db.generation_runs.insert_one({
                    "run_id": run_id,
                    "order_id": item["order_id"],
                    "template_id": None,
                    "doc_type": item.get("doc_type", ""),
                    "status": "FAILED",
                    "provider": None,
                    "model": None,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "intake_snapshot_hash": None,
                    "started_at": now,
                    "completed_at": datetime.now(timezone.utc),
                    "error_message": (str(e))[:1000],
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                })
            except Exception as ex:
                logger.warning("generation_runs FAILED dual-write failed: %s", ex)
            
            raise
    
    def _get_service_code_for_doc_type(self, doc_type: str) -> str:
        """Map doc_type to the service_code used in Prompt Manager."""
        # For document packs, the prompts are registered under DOC_PACK_* service codes
        DOC_TYPE_TO_SERVICE = {
            # Essential
            "RENT_ARREARS_LETTER": "DOC_PACK_ESSENTIAL",
            "DEPOSIT_REFUND_EXPLANATION_LETTER": "DOC_PACK_ESSENTIAL",
            "TENANT_REFERENCE_LETTER": "DOC_PACK_ESSENTIAL",
            "RENT_RECEIPT": "DOC_PACK_ESSENTIAL",
            "GDPR_NOTICE": "DOC_PACK_ESSENTIAL",
            # Plus
            "TENANCY_AGREEMENT_AST": "DOC_PACK_PLUS",
            "TENANCY_RENEWAL": "DOC_PACK_PLUS",
            "NOTICE_TO_QUIT": "DOC_PACK_PLUS",
            "GUARANTOR_AGREEMENT": "DOC_PACK_PLUS",
            "RENT_INCREASE_NOTICE": "DOC_PACK_PLUS",
            # Pro
            "INVENTORY_CONDITION_REPORT": "DOC_PACK_PRO",
            "DEPOSIT_INFORMATION_PACK": "DOC_PACK_PRO",
            "PROPERTY_ACCESS_NOTICE": "DOC_PACK_PRO",
            "ADDITIONAL_LANDLORD_NOTICE": "DOC_PACK_PRO",
        }
        return DOC_TYPE_TO_SERVICE.get(doc_type, "DOC_PACK_ESSENTIAL")
    
    async def generate_all_documents(
        self,
        order_id: str,
        input_data: Dict[str, Any],
        generated_by: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate all pending documents for an order in canonical order.
        
        Args:
            order_id: The order ID
            input_data: Input data for generation
            generated_by: User who triggered generation
            
        Returns:
            List of generated document items
        """
        items = await self.get_document_items(order_id)
        results = []
        
        for item in items:
            if item["status"] == "PENDING":
                try:
                    result = await self.generate_document(
                        item_id=item["item_id"],
                        input_data=input_data,
                        generated_by=generated_by,
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to generate {item['item_id']}: {e}")
                    results.append(await self.get_document_item(item["item_id"]))
        
        return results
    
    # ========================================
    # Regeneration
    # ========================================
    
    async def regenerate_document(
        self,
        item_id: str,
        input_data: Dict[str, Any],
        regen_reason: str,
        regen_notes: Optional[str],
        regenerated_by: str,
    ) -> Dict[str, Any]:
        """
        Regenerate a single document, creating a new version.
        
        Args:
            item_id: Document item ID
            input_data: Input data for regeneration
            regen_reason: Required reason for regeneration
            regen_notes: Optional notes
            regenerated_by: User who triggered regeneration
            
        Returns:
            Updated document item with new version
        """
        db = database.get_db()
        
        # Get current item
        item = await self.get_document_item(item_id)
        if not item:
            raise ValueError(f"Document item not found: {item_id}")
        
        if not regen_reason:
            raise ValueError("Regeneration reason is required")
        
        # Store current version in history
        current_version = item["version"]
        
        # Create version history entry
        history_entry = {
            "version": current_version,
            "generated_output": item.get("generated_output"),
            "prompt_version_used": item.get("prompt_version_used"),
            "input_snapshot_hash": item.get("input_snapshot_hash"),
            "generated_at": item.get("generated_at"),
            "status": item.get("status"),
        }
        
        # Update item for regeneration
        await db[self.COLLECTION].update_one(
            {"item_id": item_id},
            {
                "$set": {
                    "version": current_version + 1,
                    "status": "PENDING",
                    "regenerated_from_version": current_version,
                    "regen_reason": regen_reason,
                    "regen_notes": regen_notes,
                    "generated_output": None,
                    "generated_at": None,
                    "error_message": None,
                },
                "$push": {
                    "version_history": history_entry
                }
            }
        )
        
        logger.info(f"Prepared regeneration for {item_id} from v{current_version} to v{current_version + 1}")
        
        # Now generate the new version
        return await self.generate_document(
            item_id=item_id,
            input_data=input_data,
            generated_by=regenerated_by,
        )
    
    # ========================================
    # Review & Approval
    # ========================================
    
    async def approve_document(
        self,
        item_id: str,
        approved_by: str,
    ) -> Dict[str, Any]:
        """Approve a completed document."""
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        result = await db[self.COLLECTION].update_one(
            {
                "item_id": item_id,
                "status": "COMPLETED",
            },
            {
                "$set": {
                    "status": "APPROVED",
                    "approved_at": now,
                    "approved_by": approved_by,
                }
            }
        )
        
        if result.modified_count == 0:
            raise ValueError(f"Cannot approve document {item_id} - not in COMPLETED status")
        
        logger.info(f"Approved document {item_id} by {approved_by}")
        return await self.get_document_item(item_id)
    
    async def reject_document(
        self,
        item_id: str,
        rejection_reason: str,
        rejected_by: str,
    ) -> Dict[str, Any]:
        """Reject a document, requiring regeneration."""
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        result = await db[self.COLLECTION].update_one(
            {
                "item_id": item_id,
                "status": {"$in": ["COMPLETED", "APPROVED"]},
            },
            {
                "$set": {
                    "status": "REJECTED",
                    "rejection_reason": rejection_reason,
                    "rejected_at": now,
                    "rejected_by": rejected_by,
                }
            }
        )
        
        if result.modified_count == 0:
            raise ValueError(f"Cannot reject document {item_id}")
        
        logger.info(f"Rejected document {item_id} by {rejected_by}: {rejection_reason}")
        return await self.get_document_item(item_id)
    
    # ========================================
    # ZIP Bundle (pack_bundles)
    # ========================================
    
    async def build_and_store_bundle(self, order_id: str) -> Dict[str, Any]:
        """
        Build a ZIP bundle from approved document_pack_items (DOCX + PDF per doc),
        store in GridFS, and insert a pack_bundles record.
        
        Only includes items with status APPROVED and with docx_gridfs_id and pdf_gridfs_id.
        Order is canonical (canonical_index ascending).
        
        Returns:
            The pack_bundles document (bundle_id, order_id, pack_code, bundle_version, zip_file_id, zip_filename, filenames, created_at).
        Raises:
            ValueError: If order not found, not a pack order, or no approved items with files.
        """
        db = database.get_db()
        order = await db.orders.find_one({"order_id": order_id}, {"_id": 0, "order_ref": 1, "service_code": 1})
        if not order:
            raise ValueError(f"Order not found: {order_id}")
        service_code = order.get("service_code")
        if not service_code or service_code not in SERVICE_CODE_TO_PACK_TIER:
            raise ValueError(f"Order {order_id} is not a document pack order")
        
        order_ref = order.get("order_ref", order_id)
        
        items = await self.get_document_items(order_id)
        approved_with_files = [
            it for it in items
            if it.get("status") == "APPROVED"
            and it.get("docx_gridfs_id") and it.get("pdf_gridfs_id")
        ]
        if not approved_with_files:
            raise ValueError(f"No approved document items with rendered files for order {order_id}")
        
        approved_with_files.sort(key=lambda x: x.get("canonical_index", 0))
        
        from motor.motor_asyncio import AsyncIOMotorGridFSBucket
        fs = AsyncIOMotorGridFSBucket(db, bucket_name="order_files")
        
        zip_buffer = io.BytesIO()
        filenames_in_zip: List[str] = []
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for it in approved_with_files:
                docx_id = it.get("docx_gridfs_id")
                pdf_id = it.get("pdf_gridfs_id")
                fn_docx = it.get("filename_docx") or f"{it.get('doc_type', 'doc')}.docx"
                fn_pdf = it.get("filename_pdf") or f"{it.get('doc_type', 'doc')}.pdf"
                try:
                    out_docx = io.BytesIO()
                    await fs.download_to_stream(ObjectId(docx_id), out_docx)
                    out_docx.seek(0)
                    zf.writestr(fn_docx, out_docx.getvalue())
                    filenames_in_zip.append(fn_docx)
                except Exception as e:
                    logger.warning("Failed to add DOCX to bundle for item %s: %s", it.get("item_id"), e)
                try:
                    out_pdf = io.BytesIO()
                    await fs.download_to_stream(ObjectId(pdf_id), out_pdf)
                    out_pdf.seek(0)
                    zf.writestr(fn_pdf, out_pdf.getvalue())
                    filenames_in_zip.append(fn_pdf)
                except Exception as e:
                    logger.warning("Failed to add PDF to bundle for item %s: %s", it.get("item_id"), e)
        
        if not filenames_in_zip:
            raise ValueError(f"Could not add any files to bundle for order {order_id}")
        
        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()
        zip_filename = f"{order_ref}_{service_code}_bundle.zip"
        
        zip_grid_id = await fs.upload_from_stream(
            zip_filename,
            io.BytesIO(zip_bytes),
            metadata={"order_id": order_id, "pack_code": service_code, "type": "pack_bundle"},
        )
        
        latest = await db.pack_bundles.find_one(
            {"order_id": order_id},
            {"bundle_version": 1},
            sort=[("bundle_version", -1)],
        )
        bundle_version = (latest["bundle_version"] + 1) if latest else 1
        
        bundle_id = f"BDL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{hashlib.sha256(f'{order_id}{bundle_version}'.encode()).hexdigest()[:8].upper()}"
        
        bundle_doc = {
            "bundle_id": bundle_id,
            "order_id": order_id,
            "pack_code": service_code,
            "bundle_version": bundle_version,
            "zip_file_id": str(zip_grid_id),
            "zip_filename": zip_filename,
            "filenames": filenames_in_zip,
            "created_at": datetime.now(timezone.utc),
        }
        await db.pack_bundles.insert_one(bundle_doc)
        bundle_doc["created_at"] = bundle_doc["created_at"].isoformat()
        logger.info("Built and stored bundle %s for order %s (v%d, %d files)", bundle_id, order_id, bundle_version, len(filenames_in_zip))
        return {k: v for k, v in bundle_doc.items() if k != "_id"}
    
    # ========================================
    # Utility Methods
    # ========================================
    
    def get_registry(self) -> Dict[str, Dict[str, Any]]:
        """Get the full document registry as dictionaries."""
        return {
            key: {
                "doc_key": defn.doc_key,
                "doc_type": defn.doc_type,
                "pack_tier": defn.pack_tier.value,
                "output_keys": defn.output_keys,
                "display_name": defn.display_name,
            }
            for key, defn in DOCUMENT_REGISTRY.items()
        }
    
    def get_pack_info(self, service_code: str) -> Dict[str, Any]:
        """Get information about a pack tier including allowed docs."""
        pack_tier = self.get_pack_tier(service_code)
        allowed_docs = self.get_allowed_docs(pack_tier)
        
        docs_info = []
        for idx, doc_key in enumerate(allowed_docs):
            defn = DOCUMENT_REGISTRY.get(doc_key)
            if defn:
                docs_info.append({
                    "doc_key": doc_key,
                    "doc_type": defn.doc_type,
                    "display_name": defn.display_name,
                    "canonical_index": idx,
                    "pack_tier": defn.pack_tier.value,
                })
        
        return {
            "service_code": service_code,
            "pack_tier": pack_tier.value,
            "total_documents": len(allowed_docs),
            "documents": docs_info,
        }


# Singleton instance
document_pack_orchestrator = DocumentPackOrchestrator()
