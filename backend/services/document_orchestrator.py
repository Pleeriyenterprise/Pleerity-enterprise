"""
Document Orchestrator Service - Core orchestration for GPT-powered document generation.

This service implements the complete document generation pipeline:

CORRECT FLOW (Audit-safe, Dispute-resolution ready):
Payment Verified
→ Service Identified (service_code)
→ Prompt Selected (from registry)
→ Intake Validation
→ Intake Snapshot (IMMUTABLE COPY - locked before GPT)
→ GPT Execution
→ Structured JSON Output
→ Document Rendering (DOCX + PDF)
→ Versioning + Hashing
→ Human Review
   ├─ Approve → Auto-Deliver → COMPLETE
   ├─ Regenerate (with reason) → New Version → Review
   └─ Request Info → Client Input → Resume Review

IMMUTABILITY RULES:
- Intake data is snapshotted BEFORE GPT execution
- Each version is immutable (no overwrites)
- Previous versions marked SUPERSEDED, never deleted
- All versions retained for audit trail
- SHA256 hashes stored for tamper detection
"""
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib
import logging
import os

from services.gpt_prompt_registry import (
    get_prompt_for_service,
    validate_intake_data,
    PromptDefinition,
    AUTHORITATIVE_FRAMEWORK,
)
from services.prompt_manager_bridge import prompt_manager_bridge, ManagedPromptInfo
from services.service_catalogue_v2 import service_catalogue_v2
from database import database

logger = logging.getLogger(__name__)


class OrchestrationStatus(str, Enum):
    """Status of orchestration execution."""
    PENDING = "PENDING"
    INTAKE_LOCKED = "INTAKE_LOCKED"      # Intake snapshot created
    GENERATING = "GENERATING"             # GPT execution in progress
    GENERATED = "GENERATED"               # JSON output ready
    RENDERING = "RENDERING"               # Document rendering in progress
    RENDERED = "RENDERED"                 # DOCX + PDF ready
    REVIEW_PENDING = "REVIEW_PENDING"     # Awaiting human review
    APPROVED = "APPROVED"                 # Human approved
    REJECTED = "REJECTED"                 # Human requested changes
    INFO_REQUESTED = "INFO_REQUESTED"     # Awaiting client input
    DELIVERING = "DELIVERING"             # Auto-delivery in progress
    COMPLETE = "COMPLETE"                 # Delivered successfully
    FAILED = "FAILED"


@dataclass
class OrchestrationResult:
    """Result of an orchestration execution."""
    success: bool
    status: OrchestrationStatus
    service_code: str
    order_id: str
    version: int = 0
    structured_output: Optional[Dict[str, Any]] = None
    rendered_documents: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    validation_issues: List[str] = field(default_factory=list)
    data_gaps: List[str] = field(default_factory=list)
    execution_time_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    # NEW: Prompt version tracking for audit compliance
    prompt_version_used: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status.value,
            "service_code": self.service_code,
            "order_id": self.order_id,
            "version": self.version,
            "structured_output": self.structured_output,
            "rendered_documents": self.rendered_documents,
            "error_message": self.error_message,
            "validation_issues": self.validation_issues or [],
            "data_gaps": self.data_gaps or [],
            "execution_time_ms": self.execution_time_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "prompt_version_used": self.prompt_version_used,
        }


def create_intake_snapshot(intake_data: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """
    Create immutable snapshot of intake data with hash.
    This MUST be called BEFORE GPT execution.
    """
    # Deep copy to ensure immutability
    snapshot = json.loads(json.dumps(intake_data, default=str))
    snapshot["_snapshot_created_at"] = datetime.now(timezone.utc).isoformat()
    
    # Compute hash for integrity verification
    snapshot_hash = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, default=str).encode()
    ).hexdigest()
    
    return snapshot, snapshot_hash


class DocumentOrchestrator:
    """
    Document Orchestrator - Controls the GPT-powered document generation pipeline.
    
    This is the central orchestration service that:
    - Enforces payment gating
    - Selects and executes prompts
    - Produces structured JSON
    - Manages the review workflow
    """
    
    COLLECTION = "orchestration_executions"
    
    def __init__(self):
        self._llm_client = None
        self._api_key = None
    
    def _get_api_key(self):
        """Get the Emergent LLM API key."""
        if self._api_key is None:
            self._api_key = os.environ.get("EMERGENT_LLM_KEY")
            if not self._api_key:
                raise ValueError("EMERGENT_LLM_KEY not found in environment")
        return self._api_key
    
    def _create_llm_client(self, system_prompt: str, session_id: str = None):
        """Create a new LLM client instance with the given system prompt."""
        from emergentintegrations.llm.chat import LlmChat
        import uuid
        
        api_key = self._get_api_key()
        if session_id is None:
            session_id = f"doc_gen_{uuid.uuid4().hex[:8]}"
        
        return LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=system_prompt
        )
    
    async def validate_order_for_generation(
        self,
        order_id: str,
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Validate that an order is eligible for document generation.
        
        Checks:
        1. Order exists
        2. Payment is verified
        3. Service code is valid
        4. Order is not already completed
        
        Returns: (is_valid, error_message, order_data)
        """
        db = database.get_db()
        
        order = await db.orders.find_one(
            {"order_id": order_id},
            {"_id": 0}
        )
        
        if not order:
            return False, f"Order not found: {order_id}", None
        
        # Check payment status
        payment_status = order.get("stripe_payment_status", "")
        if payment_status != "paid":
            return False, f"Payment not verified. Status: {payment_status}", None
        
        # Check order status - don't regenerate completed orders
        order_status = order.get("order_status", "")
        if order_status in ["completed", "cancelled", "archived"]:
            return False, f"Order is {order_status}, cannot generate documents", None
        
        # Validate service exists
        service_code = order.get("service_code")
        if not service_code:
            return False, "Order has no service_code", None
        
        service = await service_catalogue_v2.get_active_service(service_code)
        if not service:
            return False, f"Service not found or inactive: {service_code}", None
        
        return True, "", order
    
    async def execute_full_pipeline(
        self,
        order_id: str,
        intake_data: Dict[str, Any],
        regeneration: bool = False,
        regeneration_notes: Optional[str] = None,
    ) -> OrchestrationResult:
        """
        Execute the FULL document generation pipeline.
        
        This is the correct, audit-safe flow:
        1. Payment Verified
        2. Service Identified
        3. Prompt Selected
        4. Intake Validation
        5. Intake Snapshot (IMMUTABLE - locked before GPT)
        6. GPT Execution
        7. Structured JSON Output
        8. Document Rendering (DOCX + PDF)
        9. Versioning + Hashing
        10. Ready for Human Review
        
        Args:
            order_id: The order ID
            intake_data: Form data from the intake
            regeneration: Whether this is a regeneration request
            regeneration_notes: Notes for regeneration (MANDATORY for regeneration)
        
        Returns:
            OrchestrationResult with rendered documents ready for review
        """
        from services.template_renderer import template_renderer
        
        start_time = datetime.now(timezone.utc)
        db = database.get_db()
        
        # ================================================================
        # STEP 1: Validate order (Payment Verified)
        # ================================================================
        is_valid, error_msg, order = await self.validate_order_for_generation(order_id)
        if not is_valid:
            return OrchestrationResult(
                success=False,
                status=OrchestrationStatus.FAILED,
                service_code="",
                order_id=order_id,
                error_message=error_msg,
            )
        
        service_code = order.get("service_code")
        
        # ================================================================
        # STEP 2: Get prompt for service (Prompt Selected)
        # CANONICAL RULE: doc_type == service_code for service-specific documents
        # Prioritize Prompt Manager ACTIVE prompts
        # ================================================================
        from services.document_generator import SERVICE_TO_DOC_TYPE, DocumentType
        
        # CANONICAL: Document type equals service code
        # This ensures Payment → Order → Prompt → Document stay aligned
        doc_type = service_code  # Canonical rule
        
        # Try Prompt Manager first, fall back to legacy registry
        prompt_def, prompt_info = await prompt_manager_bridge.get_prompt_for_service(
            service_code=service_code,
            doc_type=doc_type,
        )
        
        # Flag whether we're using managed prompt (for different prompt building)
        using_managed_prompt = prompt_info and prompt_info.source == "prompt_manager"
        
        if not prompt_def:
            # For document packs, use orchestrator prompt
            if service_code.startswith("DOC_PACK_"):
                prompt_def, prompt_info = await prompt_manager_bridge.get_prompt_for_service(
                    service_code="DOC_PACK_ORCHESTRATOR",
                    doc_type=doc_type,
                )
                if prompt_def:
                    intake_data["pack_type"] = service_code
                    using_managed_prompt = prompt_info and prompt_info.source == "prompt_manager"
            
            if not prompt_def:
                return OrchestrationResult(
                    success=False,
                    status=OrchestrationStatus.FAILED,
                    service_code=service_code,
                    order_id=order_id,
                    error_message=f"No prompt defined for service: {service_code}",
                )
        
        # Store prompt version info for audit (includes service_code, doc_type)
        prompt_version_used = prompt_info.to_dict() if prompt_info else None
        
        logger.info(
            f"Selected prompt for {order_id}: {prompt_info.template_id if prompt_info else 'unknown'} "
            f"(source: {prompt_info.source if prompt_info else 'none'})"
        )
        
        # ================================================================
        # STEP 3: Validate intake data
        # ================================================================
        is_valid, missing_fields = validate_intake_data(
            prompt_def.service_code,
            intake_data
        )
        
        if not is_valid:
            logger.warning(f"Intake validation failed for {order_id}: {missing_fields}")
            # Don't fail - proceed with available data and flag gaps
        
        # ================================================================
        # STEP 4: CREATE INTAKE SNAPSHOT (IMMUTABLE - BEFORE GPT)
        # This is critical for audit trail and dispute resolution
        # ================================================================
        intake_snapshot, intake_hash = create_intake_snapshot(intake_data)
        
        logger.info(f"Intake snapshot created for {order_id}: hash={intake_hash[:16]}...")
        
        # Update order status
        await db.orders.update_one(
            {"order_id": order_id},
            {"$set": {"orchestration_status": OrchestrationStatus.INTAKE_LOCKED.value}}
        )
        
        # ================================================================
        # STEP 5: Build the prompt
        # NEW: Use {{INPUT_DATA_JSON}} pattern for managed prompts
        # ================================================================
        try:
            if using_managed_prompt:
                # Use the single injection pattern for managed prompts
                user_prompt = prompt_manager_bridge.build_user_prompt_with_json(
                    template=prompt_def.user_prompt_template,
                    intake_data=intake_snapshot,
                    regeneration=regeneration,
                    regeneration_notes=regeneration_notes,
                )
            else:
                # Legacy prompts use format string substitution
                user_prompt = self._build_user_prompt(prompt_def, intake_snapshot, regeneration, regeneration_notes)
        except Exception as e:
            return OrchestrationResult(
                success=False,
                status=OrchestrationStatus.FAILED,
                service_code=service_code,
                order_id=order_id,
                error_message=f"Failed to build prompt: {str(e)}",
            )
        
        # ================================================================
        # STEP 6: Execute GPT generation
        # ================================================================
        await db.orders.update_one(
            {"order_id": order_id},
            {"$set": {"orchestration_status": OrchestrationStatus.GENERATING.value}}
        )
        
        try:
            structured_output, tokens = await self._execute_gpt(
                prompt_def,
                user_prompt,
            )
        except Exception as e:
            logger.error(f"GPT execution failed for {order_id}: {e}")
            return OrchestrationResult(
                success=False,
                status=OrchestrationStatus.FAILED,
                service_code=service_code,
                order_id=order_id,
                error_message=f"GPT execution failed: {str(e)}",
            )
        
        # ================================================================
        # STEP 7: Render documents (DOCX + PDF)
        # ================================================================
        await db.orders.update_one(
            {"order_id": order_id},
            {"$set": {"orchestration_status": OrchestrationStatus.RENDERING.value}}
        )
        
        try:
            render_result = await template_renderer.render_from_orchestration(
                order_id=order_id,
                structured_output=structured_output,
                intake_snapshot=intake_snapshot,
                is_regeneration=regeneration,
                regeneration_notes=regeneration_notes,
            )
            
            if not render_result.success:
                return OrchestrationResult(
                    success=False,
                    status=OrchestrationStatus.FAILED,
                    service_code=service_code,
                    order_id=order_id,
                    error_message=f"Rendering failed: {render_result.error_message}",
                )
        except Exception as e:
            logger.error(f"Rendering failed for {order_id}: {e}")
            return OrchestrationResult(
                success=False,
                status=OrchestrationStatus.FAILED,
                service_code=service_code,
                order_id=order_id,
                error_message=f"Rendering failed: {str(e)}",
            )
        
        # ================================================================
        # STEP 8: Store execution record with full audit trail
        # NEW: Include prompt_version_used for compliance
        # ================================================================
        data_gaps = structured_output.get("data_gaps_flagged", [])
        execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        
        execution_record = {
            "order_id": order_id,
            "service_code": service_code,
            "prompt_id": prompt_def.prompt_id,
            "version": render_result.version,
            "status": OrchestrationStatus.REVIEW_PENDING.value,
            # CRITICAL: Prompt version tracking for audit compliance
            "prompt_version_used": prompt_version_used,
            # Immutable snapshots
            "intake_snapshot": intake_snapshot,
            "intake_snapshot_hash": intake_hash,
            "structured_output": structured_output,
            "json_output_hash": render_result.json_output_hash,
            # Rendered documents
            "rendered_documents": {
                "docx": {
                    "filename": render_result.docx.filename,
                    "sha256_hash": render_result.docx.sha256_hash,
                    "size_bytes": render_result.docx.size_bytes,
                },
                "pdf": {
                    "filename": render_result.pdf.filename,
                    "sha256_hash": render_result.pdf.sha256_hash,
                    "size_bytes": render_result.pdf.size_bytes,
                },
            },
            # Validation & gaps
            "validation_issues": missing_fields if not is_valid else [],
            "data_gaps": data_gaps,
            # Regeneration context
            "is_regeneration": regeneration,
            "regeneration_notes": regeneration_notes,
            # Metrics
            "execution_time_ms": execution_time,
            "render_time_ms": render_result.render_time_ms,
            "prompt_tokens": tokens.get("prompt_tokens", 0),
            "completion_tokens": tokens.get("completion_tokens", 0),
            # Audit
            "created_at": datetime.now(timezone.utc),
        }
        
        await db[self.COLLECTION].insert_one(execution_record)
        
        # Record execution metrics for Prompt Performance Analytics
        if prompt_info:
            await prompt_manager_bridge.record_execution_metrics(
                prompt_info=prompt_info,
                order_id=order_id,
                execution_time_ms=execution_time,
                prompt_tokens=tokens.get("prompt_tokens", 0),
                completion_tokens=tokens.get("completion_tokens", 0),
                success=True,
            )
        
        
        # ================================================================
        # STEP 9: Update order status - Ready for Human Review
        # NEW: Store prompt_version_used permanently on order
        # ================================================================
        order_update = {
            "$set": {
                "document_status": "rendered",
                "review_status": "pending",
                "orchestration_status": OrchestrationStatus.REVIEW_PENDING.value,
                "current_version": render_result.version,
                "last_generation_at": datetime.now(timezone.utc),
                # CRITICAL: Store prompt_version_used permanently for audit
                "prompt_version_used": prompt_version_used,
            },
        }
        
        if regeneration:
            order_update["$inc"] = {"regeneration_count": 1}
        
        await db.orders.update_one({"order_id": order_id}, order_update)
        
        logger.info(
            f"Pipeline complete for {order_id} v{render_result.version}: "
            f"DOCX={render_result.docx.sha256_hash[:8]}, PDF={render_result.pdf.sha256_hash[:8]}, "
            f"Prompt={prompt_info.template_id if prompt_info else 'legacy'}"
        )
        
        return OrchestrationResult(
            success=True,
            status=OrchestrationStatus.REVIEW_PENDING,
            service_code=service_code,
            order_id=order_id,
            version=render_result.version,
            structured_output=structured_output,
            rendered_documents={
                "docx": {
                    "filename": render_result.docx.filename,
                    "sha256_hash": render_result.docx.sha256_hash,
                    "size_bytes": render_result.docx.size_bytes,
                },
                "pdf": {
                    "filename": render_result.pdf.filename,
                    "sha256_hash": render_result.pdf.sha256_hash,
                    "size_bytes": render_result.pdf.size_bytes,
                },
            },
            validation_issues=missing_fields if not is_valid else [],
            data_gaps=data_gaps if data_gaps else [],
            execution_time_ms=execution_time,
            prompt_tokens=tokens.get("prompt_tokens", 0),
            completion_tokens=tokens.get("completion_tokens", 0),
            prompt_version_used=prompt_version_used,
        )
    
    # Keep legacy method for backwards compatibility
    async def execute_generation(
        self,
        order_id: str,
        intake_data: Dict[str, Any],
        regeneration: bool = False,
        regeneration_notes: Optional[str] = None,
    ) -> OrchestrationResult:
        """
        Execute document generation - delegates to full pipeline.
        
        DEPRECATED: Use execute_full_pipeline directly.
        """
        return await self.execute_full_pipeline(
            order_id=order_id,
            intake_data=intake_data,
            regeneration=regeneration,
            regeneration_notes=regeneration_notes,
        )
    
    def _build_user_prompt(
        self,
        prompt_def: PromptDefinition,
        intake_data: Dict[str, Any],
        regeneration: bool = False,
        regeneration_notes: Optional[str] = None,
    ) -> str:
        """Build the user prompt by substituting intake data into template."""
        
        # Create a copy with empty string defaults for missing fields
        data = {k: v if v is not None else "" for k, v in intake_data.items()}
        
        # Add regeneration context if applicable
        if regeneration and regeneration_notes:
            data["regeneration_context"] = f"\n\nREGENERATION REQUEST:\nPrevious version feedback: {regeneration_notes}\nPlease address the above feedback in this generation.\n"
        else:
            data["regeneration_context"] = ""
        
        # Substitute template variables
        try:
            user_prompt = prompt_def.user_prompt_template.format(**data)
        except KeyError as e:
            # If a field is missing, use empty string
            logger.warning(f"Missing field in prompt template: {e}")
            # Do a safer substitution
            user_prompt = prompt_def.user_prompt_template
            for key, value in data.items():
                user_prompt = user_prompt.replace(f"{{{key}}}", str(value) if value else "Not provided")
        
        if regeneration and regeneration_notes:
            user_prompt += data["regeneration_context"]
        
        return user_prompt
    
    async def _execute_gpt(
        self,
        prompt_def: PromptDefinition,
        user_prompt: str,
    ) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """
        Execute GPT generation and return structured output.
        
        Uses LlmChat from emergentintegrations library.
        """
        client = await self._get_llm_client()
        
        # Build the full prompt with JSON output instruction
        output_schema_str = json.dumps(prompt_def.output_schema, indent=2)
        
        full_system_prompt = f"""{prompt_def.system_prompt}

OUTPUT FORMAT:
You MUST return your response as valid JSON matching this exact schema:

```json
{output_schema_str}
```

Return ONLY the JSON object, no additional text or markdown formatting.
"""
        
        # Execute generation using LlmChat send_message
        # Combine system prompt with user prompt for LlmChat
        full_prompt = f"{full_system_prompt}\n\n---\n\nUser Request:\n{user_prompt}"
        
        response = await client.send_message(full_prompt)
        
        # Parse response - LlmChat returns the message content directly
        response_text = response if isinstance(response, str) else str(response)
        
        # Clean up response - remove markdown code blocks if present
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        try:
            structured_output = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT response as JSON: {e}")
            logger.error(f"Response text: {response_text[:500]}...")
            # Return a wrapper with the raw text
            structured_output = {
                "raw_response": response_text,
                "parse_error": str(e),
                "data_gaps_flagged": ["Response could not be parsed as JSON"]
            }
        
        # Extract token counts if available
        tokens = {
            "prompt_tokens": getattr(response, 'prompt_tokens', 0) or 0,
            "completion_tokens": getattr(response, 'completion_tokens', 0) or 0,
        }
        
        return structured_output, tokens
    
    async def get_execution_history(
        self,
        order_id: str,
    ) -> List[Dict[str, Any]]:
        """Get execution history for an order."""
        db = database.get_db()
        
        cursor = db[self.COLLECTION].find(
            {"order_id": order_id},
            {"_id": 0}
        ).sort("created_at", -1)
        
        return await cursor.to_list(length=100)
    
    async def get_latest_execution(
        self,
        order_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the latest execution for an order."""
        db = database.get_db()
        
        return await db[self.COLLECTION].find_one(
            {"order_id": order_id},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
    
    async def mark_reviewed(
        self,
        order_id: str,
        approved: bool,
        reviewer_id: str,
        review_notes: Optional[str] = None,
    ) -> bool:
        """Mark an execution as reviewed (approved or rejected)."""
        db = database.get_db()
        
        status = OrchestrationStatus.APPROVED if approved else OrchestrationStatus.REJECTED
        
        # Find and update latest execution using find_one_and_update with sort
        result = await db[self.COLLECTION].find_one_and_update(
            {"order_id": order_id},
            {
                "$set": {
                    "status": status.value,
                    "reviewed_by": reviewer_id,
                    "reviewed_at": datetime.now(timezone.utc),
                    "review_notes": review_notes,
                }
            },
            sort=[("created_at", -1)],
            return_document=False  # Return original document (before update)
        )
        
        # Update order status
        if approved:
            await db.orders.update_one(
                {"order_id": order_id},
                {
                    "$set": {
                        "document_status": "final_ready",
                        "review_status": "approved",
                    }
                }
            )
        else:
            await db.orders.update_one(
                {"order_id": order_id},
                {
                    "$set": {
                        "review_status": "changes_requested",
                    }
                }
            )
        
        # find_one_and_update returns the document if found, None otherwise
        return result is not None


# Singleton instance
document_orchestrator = DocumentOrchestrator()
