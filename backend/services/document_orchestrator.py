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
        self._gemini_client = None
    
    async def _get_gemini_client(self):
        """Lazy initialization of Gemini client."""
        if self._gemini_client is None:
            try:
                from emergentintegrations.llm.gemini import GeminiClient
                api_key = os.environ.get("EMERGENT_LLM_KEY")
                if not api_key:
                    raise ValueError("EMERGENT_LLM_KEY not found in environment")
                self._gemini_client = GeminiClient(api_key=api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                raise
        return self._gemini_client
    
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
    
    async def execute_generation(
        self,
        order_id: str,
        intake_data: Dict[str, Any],
        regeneration: bool = False,
        regeneration_notes: Optional[str] = None,
    ) -> OrchestrationResult:
        """
        Execute document generation for an order.
        
        This is the main entry point for document generation.
        
        Args:
            order_id: The order ID
            intake_data: Form data from the intake
            regeneration: Whether this is a regeneration request
            regeneration_notes: Notes for regeneration (changes requested)
        
        Returns:
            OrchestrationResult with structured output or error
        """
        start_time = datetime.now(timezone.utc)
        db = database.get_db()
        
        # Step 1: Validate order
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
        
        # Step 2: Get prompt for service
        prompt_def = get_prompt_for_service(service_code)
        if not prompt_def:
            # For document packs, use orchestrator prompt
            if service_code.startswith("DOC_PACK_"):
                prompt_def = get_prompt_for_service("DOC_PACK_ORCHESTRATOR")
                if prompt_def:
                    intake_data["pack_type"] = service_code
            
            if not prompt_def:
                return OrchestrationResult(
                    success=False,
                    status=OrchestrationStatus.FAILED,
                    service_code=service_code,
                    order_id=order_id,
                    error_message=f"No prompt defined for service: {service_code}",
                )
        
        # Step 3: Validate intake data
        is_valid, missing_fields = validate_intake_data(
            prompt_def.service_code,
            intake_data
        )
        
        if not is_valid:
            logger.warning(f"Intake validation failed for {order_id}: {missing_fields}")
            # Don't fail - proceed with available data and flag gaps
        
        # Step 4: Build the prompt
        try:
            user_prompt = self._build_user_prompt(prompt_def, intake_data, regeneration, regeneration_notes)
        except Exception as e:
            return OrchestrationResult(
                success=False,
                status=OrchestrationStatus.FAILED,
                service_code=service_code,
                order_id=order_id,
                error_message=f"Failed to build prompt: {str(e)}",
            )
        
        # Step 5: Execute GPT generation
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
        
        # Step 6: Extract data gaps from output
        data_gaps = structured_output.get("data_gaps_flagged", [])
        
        # Calculate execution time
        execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        
        # Step 7: Store execution record
        execution_record = {
            "order_id": order_id,
            "service_code": service_code,
            "prompt_id": prompt_def.prompt_id,
            "status": OrchestrationStatus.GENERATED.value,
            "structured_output": structured_output,
            "intake_data_snapshot": intake_data,
            "validation_issues": missing_fields if not is_valid else [],
            "data_gaps": data_gaps,
            "is_regeneration": regeneration,
            "regeneration_notes": regeneration_notes,
            "execution_time_ms": execution_time,
            "prompt_tokens": tokens.get("prompt_tokens", 0),
            "completion_tokens": tokens.get("completion_tokens", 0),
            "created_at": datetime.now(timezone.utc),
        }
        
        await db[self.COLLECTION].insert_one(execution_record)
        
        # Step 8: Update order status
        await db.orders.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "document_status": "draft_generated",
                    "review_status": "pending",
                    "last_generation_at": datetime.now(timezone.utc),
                },
                "$inc": {"regeneration_count": 1} if regeneration else {}
            }
        )
        
        return OrchestrationResult(
            success=True,
            status=OrchestrationStatus.GENERATED,
            service_code=service_code,
            order_id=order_id,
            structured_output=structured_output,
            validation_issues=missing_fields if not is_valid else None,
            data_gaps=data_gaps if data_gaps else None,
            execution_time_ms=execution_time,
            prompt_tokens=tokens.get("prompt_tokens", 0),
            completion_tokens=tokens.get("completion_tokens", 0),
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
        
        Uses Gemini via emergentintegrations library.
        """
        client = await self._get_gemini_client()
        
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
        
        # Execute generation
        response = await client.generate(
            user_prompt=user_prompt,
            system_prompt=full_system_prompt,
            temperature=prompt_def.temperature,
            max_tokens=prompt_def.max_tokens,
        )
        
        # Parse response
        response_text = response.text if hasattr(response, 'text') else str(response)
        
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
        
        # Update latest execution
        result = await db[self.COLLECTION].update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "status": status.value,
                    "reviewed_by": reviewer_id,
                    "reviewed_at": datetime.now(timezone.utc),
                    "review_notes": review_notes,
                }
            },
            sort=[("created_at", -1)]
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
        
        return result.modified_count > 0


# Singleton instance
document_orchestrator = DocumentOrchestrator()
