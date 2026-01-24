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
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

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

# Service code to pack tier mapping
SERVICE_CODE_TO_PACK_TIER = {
    "DOC_PACK_ESSENTIAL": PackTier.ESSENTIAL,
    "DOC_PACK_PLUS": PackTier.PLUS,
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
            
            prompt_info = await bridge.get_prompt_for_service(
                service_code=service_code,
                doc_type=definition.doc_type,
            )
            
            if not prompt_info:
                raise ValueError(f"No active prompt found for {service_code}/{definition.doc_type}")
            
            # Build the prompt with input data
            user_prompt = bridge.build_user_prompt_with_json(
                prompt_info=prompt_info,
                input_data=input_data,
            )
            
            # Execute LLM generation
            from services.prompt_service import prompt_service
            llm = await prompt_service._get_llm_provider()
            
            raw_output, tokens = await llm.generate(
                system_prompt=prompt_info.system_prompt,
                user_prompt=user_prompt,
                temperature=prompt_info.temperature,
                max_tokens=prompt_info.max_tokens,
            )
            
            # Parse output
            parsed_output = prompt_service._parse_llm_output(raw_output)
            
            if not parsed_output:
                raise ValueError("Failed to parse LLM output as JSON")
            
            # Validate output keys
            missing_keys = set(definition.output_keys) - set(parsed_output.keys())
            if missing_keys:
                logger.warning(f"Missing output keys for {item_id}: {missing_keys}")
            
            # Update item with success
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
            
            # Record execution metrics
            await bridge.record_execution_metrics(
                prompt_info=prompt_info,
                execution_time_ms=int((datetime.now(timezone.utc) - now).total_seconds() * 1000),
                success=True,
                prompt_tokens=tokens.get("prompt_tokens", 0),
                completion_tokens=tokens.get("completion_tokens", 0),
            )
            
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
