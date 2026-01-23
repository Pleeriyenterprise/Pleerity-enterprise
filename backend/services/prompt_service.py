"""
Enterprise Prompt Manager Service

Core business logic for prompt management, testing, and activation.
Implements the Draft -> Tested -> Active lifecycle with full audit trail.

Key Features:
- Version control with immutable history
- Provider-agnostic LLM interface (Gemini default, swappable)
- Schema validation before activation
- Full audit logging

NON-NEGOTIABLES:
- NEVER overwrite active history
- Schema validation REQUIRED before Test Passed and Activation
- prompt_version_used stored permanently on generated documents
- Full audit: who, what, when, evidence
"""
import json
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from abc import ABC, abstractmethod

from models.prompts import (
    PromptStatus, PromptTestStatus, PromptAuditAction,
    PromptTemplateCreate, PromptTemplateUpdate, PromptTemplateResponse,
    PromptTestRequest, PromptTestResult,
    OutputSchema,
)
from database import database

logger = logging.getLogger(__name__)


# ============================================
# LLM Provider Interface (Provider-Agnostic)
# ============================================

class LLMProviderInterface(ABC):
    """
    Abstract interface for LLM providers.
    Allows swapping between Gemini, OpenAI, Anthropic, etc.
    """
    
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Tuple[str, Dict[str, int]]:
        """
        Generate text from the LLM.
        
        Returns: (response_text, {"prompt_tokens": N, "completion_tokens": M})
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for logging."""
        pass


class GeminiProvider(LLMProviderInterface):
    """Gemini LLM provider using emergentintegrations LlmChat."""
    
    def __init__(self):
        self._api_key = None
    
    def _get_api_key(self):
        if self._api_key is None:
            self._api_key = os.environ.get("EMERGENT_LLM_KEY")
            if not self._api_key:
                raise ValueError("EMERGENT_LLM_KEY not found in environment")
        return self._api_key
    
    @property
    def provider_name(self) -> str:
        return "gemini"
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Tuple[str, Dict[str, int]]:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import uuid
        
        api_key = self._get_api_key()
        
        # Create a unique session ID for this test run
        session_id = f"prompt-test-{uuid.uuid4().hex[:8]}"
        
        # Initialize chat with Gemini model
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=system_prompt,
        ).with_model("gemini", "gemini-2.5-flash")
        
        # Create user message
        user_message = UserMessage(text=user_prompt)
        
        # Send message and get response
        response_text = await chat.send_message(user_message)
        
        # Token counts are not directly available, estimate
        tokens = {
            "prompt_tokens": len(system_prompt.split()) + len(user_prompt.split()),
            "completion_tokens": len(response_text.split()) if response_text else 0,
        }
        
        return response_text, tokens


# ============================================
# Schema Validator
# ============================================

class SchemaValidator:
    """Validates LLM output against defined output schema."""
    
    @staticmethod
    def validate(output: Dict[str, Any], schema: OutputSchema) -> Tuple[bool, List[str]]:
        """
        Validate output against schema.
        
        Returns: (is_valid, list_of_errors)
        """
        errors = []
        json_schema = schema.to_json_schema()
        
        # Check root type
        if json_schema["type"] == "object" and not isinstance(output, dict):
            errors.append(f"Expected object at root, got {type(output).__name__}")
            return False, errors
        
        if json_schema["type"] == "array" and not isinstance(output, list):
            errors.append(f"Expected array at root, got {type(output).__name__}")
            return False, errors
        
        # Check required fields
        for required_field in json_schema.get("required", []):
            if required_field not in output:
                errors.append(f"Missing required field: {required_field}")
        
        # Check field types
        properties = json_schema.get("properties", {})
        for field_name, field_schema in properties.items():
            if field_name in output:
                value = output[field_name]
                expected_type = field_schema.get("type")
                
                type_valid = SchemaValidator._check_type(value, expected_type)
                if not type_valid:
                    errors.append(
                        f"Field '{field_name}': expected {expected_type}, "
                        f"got {type(value).__name__}"
                    )
        
        # Check for extra fields if strict validation
        if not json_schema.get("additionalProperties", True):
            extra_fields = set(output.keys()) - set(properties.keys())
            if extra_fields:
                errors.append(f"Unexpected fields: {list(extra_fields)}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """Check if value matches expected JSON Schema type."""
        type_map = {
            "string": str,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        
        if expected_type not in type_map:
            return True  # Unknown type, skip validation
        
        expected = type_map[expected_type]
        return isinstance(value, expected)


# ============================================
# Prompt Service
# ============================================

class PromptService:
    """
    Enterprise Prompt Management Service.
    
    Handles CRUD operations, versioning, testing, and activation
    with full audit trail.
    
    ARCHITECTURAL RULE:
    - service_code MUST exist in service catalogue
    - doc_type MUST be canonical (match service_code or be allowed for that service)
    - Prompt cannot be activated if mismatch exists
    """
    
    COLLECTION = "prompt_templates"
    AUDIT_COLLECTION = "prompt_audit_log"
    TEST_COLLECTION = "prompt_test_results"
    
    # Canonical service code to document type mapping
    SERVICE_DOC_TYPE_MAP = {
        "AI_WF_BLUEPRINT": ["AI_WF_BLUEPRINT", "AI_WORKFLOW_BLUEPRINT"],
        "AI_PROC_MAP": ["AI_PROC_MAP", "AI_PROCESS_MAP"],
        "AI_TOOLS_REC": ["AI_TOOLS_REC", "AI_TOOL_RECOMMENDATIONS"],
        "MR_BASIC": ["MR_BASIC", "MARKET_RESEARCH_BASIC"],
        "MR_ADV": ["MR_ADV", "MARKET_RESEARCH_ADVANCED"],
        "HMO_AUDIT": ["HMO_AUDIT", "HMO_COMPLIANCE_AUDIT"],
        "FULL_AUDIT": ["FULL_AUDIT", "FULL_PROPERTY_AUDIT"],
        "DOC_PACK_ESSENTIAL": ["DOC_PACK_ESSENTIAL"],
        "DOC_PACK_TENANCY": ["DOC_PACK_TENANCY"],
        "DOC_PACK_ULTIMATE": ["DOC_PACK_ULTIMATE"],
    }
    
    def __init__(self, llm_provider: Optional[LLMProviderInterface] = None):
        """
        Initialize with optional LLM provider.
        Defaults to Gemini if not specified.
        """
        self._llm_provider = llm_provider
    
    async def _get_llm_provider(self) -> LLMProviderInterface:
        """Get or create LLM provider (lazy init)."""
        if self._llm_provider is None:
            self._llm_provider = GeminiProvider()
        return self._llm_provider
    
    def _generate_id(self, prefix: str = "PT") -> str:
        """Generate unique ID with timestamp component."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        random_part = hashlib.sha256(
            f"{timestamp}{os.urandom(8).hex()}".encode()
        ).hexdigest()[:8].upper()
        return f"{prefix}-{timestamp}-{random_part}"
    
    async def _validate_service_catalogue_alignment(
        self,
        service_code: str,
        doc_type: str,
    ) -> Tuple[bool, str]:
        """
        Validate that service_code exists in catalogue and doc_type is allowed.
        
        ARCHITECTURAL ENFORCEMENT:
        - service_code MUST exist in service_catalogue_v2 collection
        - doc_type MUST be canonical for that service
        
        Returns: (is_valid, error_message)
        """
        db = database.get_db()
        
        # Check service exists in catalogue (service_catalogue_v2)
        service = await db.service_catalogue_v2.find_one(
            {"service_code": service_code},
            {"service_code": 1, "service_name": 1}
        )
        
        if not service:
            return False, f"Service code '{service_code}' not found in service catalogue. Prompt MUST use a valid catalogue service code."
        
        # Check doc_type is allowed for this service
        allowed_doc_types = self.SERVICE_DOC_TYPE_MAP.get(service_code, [])
        
        # If no specific mapping, allow service_code as doc_type (canonical rule)
        if not allowed_doc_types:
            allowed_doc_types = [service_code]
        
        if doc_type not in allowed_doc_types:
            return False, f"Document type '{doc_type}' not allowed for service '{service_code}'. Allowed types: {allowed_doc_types}"
        
        return True, ""
    
    # ========================================
    # CREATE
    # ========================================
    
    async def create_template(
        self,
        data: PromptTemplateCreate,
        created_by: str,
    ) -> PromptTemplateResponse:
        """
        Create a new prompt template in DRAFT status.
        
        VALIDATES:
        - service_code exists in service catalogue
        - doc_type is canonical for that service
        
        Args:
            data: Template creation data
            created_by: Admin user ID/email
        
        Returns:
            Created template response
            
        Raises:
            ValueError: If service_code or doc_type validation fails
        """
        db = database.get_db()
        
        # ARCHITECTURAL ENFORCEMENT: Validate service catalogue alignment
        is_valid, error_msg = await self._validate_service_catalogue_alignment(
            data.service_code, data.doc_type
        )
        if not is_valid:
            raise ValueError(error_msg)
        
        template_id = self._generate_id("PT")
        now = datetime.now(timezone.utc)
        
        # Build document
        doc = {
            "template_id": template_id,
            "service_code": data.service_code,
            "doc_type": data.doc_type,
            "name": data.name,
            "description": data.description,
            "version": 1,
            "status": PromptStatus.DRAFT.value,
            
            "system_prompt": data.system_prompt,
            "user_prompt_template": data.user_prompt_template,
            "output_schema": data.output_schema.model_dump(),
            
            "temperature": data.temperature,
            "max_tokens": data.max_tokens,
            "tags": data.tags,
            
            # Test tracking
            "last_test_status": None,
            "last_test_at": None,
            "test_count": 0,
            
            # Audit fields
            "created_at": now,
            "created_by": created_by,
            "updated_at": None,
            "updated_by": None,
            "activated_at": None,
            "activated_by": None,
            "deprecated_at": None,
            "deprecated_by": None,
        }
        
        await db[self.COLLECTION].insert_one(doc)
        
        # Log audit
        await self._log_audit(
            template_id=template_id,
            version=1,
            action=PromptAuditAction.CREATED,
            changes_summary=f"Created new prompt template: {data.name}",
            changes_detail={"initial_data": data.model_dump()},
            performed_by=created_by,
        )
        
        logger.info(f"Created prompt template {template_id} by {created_by}")
        
        return self._doc_to_response(doc)
    
    # ========================================
    # READ
    # ========================================
    
    async def get_template(self, template_id: str) -> Optional[PromptTemplateResponse]:
        """Get a template by ID."""
        db = database.get_db()
        
        doc = await db[self.COLLECTION].find_one(
            {"template_id": template_id},
            {"_id": 0}
        )
        
        if not doc:
            return None
        
        return self._doc_to_response(doc)
    
    async def get_active_template(
        self,
        service_code: str,
        doc_type: str,
    ) -> Optional[PromptTemplateResponse]:
        """Get the currently ACTIVE template for a service/doc_type combo."""
        db = database.get_db()
        
        doc = await db[self.COLLECTION].find_one(
            {
                "service_code": service_code,
                "doc_type": doc_type,
                "status": PromptStatus.ACTIVE.value,
            },
            {"_id": 0}
        )
        
        if not doc:
            return None
        
        return self._doc_to_response(doc)
    
    async def list_templates(
        self,
        service_code: Optional[str] = None,
        doc_type: Optional[str] = None,
        status: Optional[List[PromptStatus]] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[PromptTemplateResponse], int]:
        """
        List templates with filters.
        
        Returns: (list_of_templates, total_count)
        """
        db = database.get_db()
        
        # Build query
        query: Dict[str, Any] = {}
        
        if service_code:
            query["service_code"] = service_code
        
        if doc_type:
            query["doc_type"] = doc_type
        
        if status:
            query["status"] = {"$in": [s.value for s in status]}
        
        if tags:
            query["tags"] = {"$all": tags}
        
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
            ]
        
        # Get total count
        total = await db[self.COLLECTION].count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * page_size
        cursor = db[self.COLLECTION].find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(page_size)
        
        docs = await cursor.to_list(length=page_size)
        
        return [self._doc_to_response(doc) for doc in docs], total
    
    async def get_version_history(
        self,
        service_code: str,
        doc_type: str,
    ) -> List[Dict[str, Any]]:
        """Get all versions of a prompt for a service/doc_type."""
        db = database.get_db()
        
        cursor = db[self.COLLECTION].find(
            {
                "service_code": service_code,
                "doc_type": doc_type,
            },
            {"_id": 0}
        ).sort("version", -1)
        
        docs = await cursor.to_list(length=100)
        
        return [
            {
                "template_id": doc["template_id"],
                "version": doc["version"],
                "status": doc["status"],
                "name": doc["name"],
                "created_at": doc["created_at"].isoformat() if isinstance(doc["created_at"], datetime) else doc["created_at"],
                "created_by": doc["created_by"],
                "tested_at": doc.get("last_test_at"),
                "activated_at": doc.get("activated_at").isoformat() if doc.get("activated_at") else None,
                "deprecated_at": doc.get("deprecated_at").isoformat() if doc.get("deprecated_at") else None,
                "test_count": doc.get("test_count", 0),
                "last_test_passed": doc.get("last_test_status") == PromptTestStatus.PASSED.value,
            }
            for doc in docs
        ]
    
    # ========================================
    # UPDATE
    # ========================================
    
    async def update_template(
        self,
        template_id: str,
        data: PromptTemplateUpdate,
        updated_by: str,
    ) -> Optional[PromptTemplateResponse]:
        """
        Update a template.
        
        RULES:
        - DRAFT templates: Updated in place
        - TESTED/ACTIVE templates: Creates NEW VERSION, original stays unchanged
        - DEPRECATED/ARCHIVED: Cannot be updated
        """
        db = database.get_db()
        
        # Get existing template
        existing = await db[self.COLLECTION].find_one(
            {"template_id": template_id},
            {"_id": 0}
        )
        
        if not existing:
            return None
        
        current_status = existing["status"]
        
        # Check if update is allowed
        if current_status in [PromptStatus.DEPRECATED.value, PromptStatus.ARCHIVED.value]:
            raise ValueError(f"Cannot update template in {current_status} status")
        
        # Build update data
        update_data = {}
        changes = {}
        
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                if field == "output_schema":
                    update_data[field] = value
                    if existing.get(field) != value:
                        changes[field] = {"old": existing.get(field), "new": value}
                else:
                    update_data[field] = value
                    if existing.get(field) != value:
                        changes[field] = {"old": existing.get(field), "new": value}
        
        if not update_data:
            return self._doc_to_response(existing)
        
        now = datetime.now(timezone.utc)
        
        # DRAFT: Update in place
        if current_status == PromptStatus.DRAFT.value:
            update_data["updated_at"] = now
            update_data["updated_by"] = updated_by
            # Reset test status when prompt content changes
            if "system_prompt" in update_data or "user_prompt_template" in update_data:
                update_data["last_test_status"] = None
                update_data["last_test_at"] = None
            
            await db[self.COLLECTION].update_one(
                {"template_id": template_id},
                {"$set": update_data}
            )
            
            await self._log_audit(
                template_id=template_id,
                version=existing["version"],
                action=PromptAuditAction.UPDATED,
                changes_summary=f"Updated draft template: {', '.join(changes.keys())}",
                changes_detail=changes,
                performed_by=updated_by,
            )
            
            # Fetch and return updated
            updated = await db[self.COLLECTION].find_one(
                {"template_id": template_id},
                {"_id": 0}
            )
            return self._doc_to_response(updated)
        
        # TESTED/ACTIVE: Create new version
        else:
            new_version = existing["version"] + 1
            new_template_id = self._generate_id("PT")
            
            # Copy existing and apply updates
            new_doc = {**existing}
            new_doc["template_id"] = new_template_id
            new_doc["version"] = new_version
            new_doc["status"] = PromptStatus.DRAFT.value  # New versions start as DRAFT
            new_doc["created_at"] = now
            new_doc["created_by"] = updated_by
            new_doc["updated_at"] = None
            new_doc["updated_by"] = None
            new_doc["activated_at"] = None
            new_doc["activated_by"] = None
            new_doc["deprecated_at"] = None
            new_doc["deprecated_by"] = None
            new_doc["last_test_status"] = None
            new_doc["last_test_at"] = None
            new_doc["test_count"] = 0
            
            # Apply updates
            for field, value in update_data.items():
                new_doc[field] = value
            
            # Remove MongoDB _id if present
            new_doc.pop("_id", None)
            
            await db[self.COLLECTION].insert_one(new_doc)
            
            await self._log_audit(
                template_id=new_template_id,
                version=new_version,
                action=PromptAuditAction.CREATED,
                changes_summary=f"Created new version {new_version} from {template_id} v{existing['version']}",
                changes_detail={
                    "source_template_id": template_id,
                    "source_version": existing["version"],
                    "changes": changes,
                },
                performed_by=updated_by,
            )
            
            logger.info(f"Created new version {new_template_id} v{new_version} from {template_id}")
            
            return self._doc_to_response(new_doc)
    
    # ========================================
    # DELETE / ARCHIVE
    # ========================================
    
    async def archive_template(
        self,
        template_id: str,
        archived_by: str,
    ) -> bool:
        """Archive a template (soft delete)."""
        db = database.get_db()
        
        result = await db[self.COLLECTION].update_one(
            {
                "template_id": template_id,
                "status": {"$ne": PromptStatus.ACTIVE.value},  # Can't archive active
            },
            {
                "$set": {
                    "status": PromptStatus.ARCHIVED.value,
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": archived_by,
                }
            }
        )
        
        if result.modified_count > 0:
            doc = await db[self.COLLECTION].find_one(
                {"template_id": template_id},
                {"version": 1}
            )
            await self._log_audit(
                template_id=template_id,
                version=doc["version"] if doc else 0,
                action=PromptAuditAction.ARCHIVED,
                changes_summary="Template archived",
                performed_by=archived_by,
            )
            return True
        
        return False
    
    # ========================================
    # TESTING (Prompt Playground)
    # ========================================
    
    async def execute_test(
        self,
        request: PromptTestRequest,
        executed_by: str,
    ) -> PromptTestResult:
        """
        Execute a test in the Prompt Playground.
        
        This:
        1. Loads the template
        2. Renders the prompt with {{INPUT_DATA_JSON}}
        3. Calls the LLM
        4. Validates output against schema
        5. Stores result for audit trail
        """
        db = database.get_db()
        start_time = datetime.now(timezone.utc)
        
        # Get template
        template = await db[self.COLLECTION].find_one(
            {"template_id": request.template_id},
            {"_id": 0}
        )
        
        if not template:
            raise ValueError(f"Template not found: {request.template_id}")
        
        test_id = self._generate_id("TEST")
        
        # Render the user prompt with {{INPUT_DATA_JSON}}
        input_json = json.dumps(request.test_input_data, indent=2, default=str)
        rendered_prompt = template["user_prompt_template"].replace(
            "{{INPUT_DATA_JSON}}", 
            input_json
        )
        
        # Use overrides if provided
        temperature = request.temperature_override or template["temperature"]
        max_tokens = request.max_tokens_override or template["max_tokens"]
        
        # Execute LLM call
        try:
            llm = await self._get_llm_provider()
            raw_output, tokens = await llm.generate(
                system_prompt=template["system_prompt"],
                user_prompt=rendered_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            # Parse output
            parsed_output = self._parse_llm_output(raw_output)
            
            # Validate against schema
            schema = OutputSchema(**template["output_schema"])
            if parsed_output:
                is_valid, validation_errors = SchemaValidator.validate(parsed_output, schema)
            else:
                is_valid = False
                validation_errors = ["Failed to parse output as JSON"]
            
            status = PromptTestStatus.PASSED if is_valid else PromptTestStatus.FAILED
            error_message = None
            
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            raw_output = None
            parsed_output = None
            is_valid = False
            validation_errors = [str(e)]
            status = PromptTestStatus.FAILED
            error_message = str(e)
            tokens = {"prompt_tokens": 0, "completion_tokens": 0}
        
        execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        
        # Build result
        result = PromptTestResult(
            test_id=test_id,
            template_id=request.template_id,
            template_version=template["version"],
            status=status,
            input_data=request.test_input_data,
            rendered_user_prompt=rendered_prompt,
            raw_output=raw_output,
            parsed_output=parsed_output,
            schema_validation_passed=is_valid,
            schema_validation_errors=validation_errors,
            execution_time_ms=execution_time,
            prompt_tokens=tokens.get("prompt_tokens", 0),
            completion_tokens=tokens.get("completion_tokens", 0),
            error_message=error_message,
            executed_at=start_time.isoformat(),
            executed_by=executed_by,
        )
        
        # Store test result
        await db[self.TEST_COLLECTION].insert_one(result.model_dump())
        
        # Update template test tracking
        await db[self.COLLECTION].update_one(
            {"template_id": request.template_id},
            {
                "$set": {
                    "last_test_status": status.value,
                    "last_test_at": start_time,
                },
                "$inc": {"test_count": 1},
            }
        )
        
        # Log audit
        await self._log_audit(
            template_id=request.template_id,
            version=template["version"],
            action=PromptAuditAction.TEST_PASSED if is_valid else PromptAuditAction.TEST_FAILED,
            changes_summary=f"Test {'passed' if is_valid else 'failed'}: {test_id}",
            test_id=test_id,
            test_result_snapshot={
                "status": status.value,
                "validation_passed": is_valid,
                "validation_errors": validation_errors,
                "execution_time_ms": execution_time,
            },
            performed_by=executed_by,
        )
        
        logger.info(f"Test {test_id} for {request.template_id}: {status.value}")
        
        return result
    
    async def get_test_results(
        self,
        template_id: str,
        limit: int = 20,
    ) -> List[PromptTestResult]:
        """Get test results for a template."""
        db = database.get_db()
        
        cursor = db[self.TEST_COLLECTION].find(
            {"template_id": template_id},
            {"_id": 0}
        ).sort("executed_at", -1).limit(limit)
        
        docs = await cursor.to_list(length=limit)
        return [PromptTestResult(**doc) for doc in docs]
    
    # ========================================
    # ACTIVATION
    # ========================================
    
    async def activate_template(
        self,
        template_id: str,
        activation_reason: str,
        activated_by: str,
    ) -> Dict[str, Any]:
        """
        Activate a TESTED template.
        
        RULES:
        - Only TESTED templates can be activated
        - Must have passed schema validation
        - Previous ACTIVE version becomes DEPRECATED
        - Activation is logged with evidence
        
        ARCHITECTURAL ENFORCEMENT:
        - service_code MUST exist in service catalogue
        - doc_type MUST be canonical for that service
        - Prompt cannot be activated if mismatch exists
        """
        db = database.get_db()
        now = datetime.now(timezone.utc)
        
        # Get template
        template = await db[self.COLLECTION].find_one(
            {"template_id": template_id},
            {"_id": 0}
        )
        
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        # ARCHITECTURAL ENFORCEMENT: Validate service catalogue alignment before activation
        is_valid, error_msg = await self._validate_service_catalogue_alignment(
            template["service_code"], template["doc_type"]
        )
        if not is_valid:
            raise ValueError(f"ACTIVATION BLOCKED: {error_msg}")
        
        if template["status"] != PromptStatus.TESTED.value:
            raise ValueError(
                f"Only TESTED templates can be activated. Current status: {template['status']}"
            )
        
        if template["last_test_status"] != PromptTestStatus.PASSED.value:
            raise ValueError(
                "Template must have a passing test before activation. "
                "Run a test in the Playground first."
            )
        
        # Find and deprecate current active version
        previous_active = await db[self.COLLECTION].find_one(
            {
                "service_code": template["service_code"],
                "doc_type": template["doc_type"],
                "status": PromptStatus.ACTIVE.value,
            },
            {"template_id": 1, "version": 1}
        )
        
        previous_active_version = None
        
        if previous_active:
            previous_active_version = previous_active["version"]
            
            # Deprecate the current active
            await db[self.COLLECTION].update_one(
                {"template_id": previous_active["template_id"]},
                {
                    "$set": {
                        "status": PromptStatus.DEPRECATED.value,
                        "deprecated_at": now,
                        "deprecated_by": activated_by,
                    }
                }
            )
            
            await self._log_audit(
                template_id=previous_active["template_id"],
                version=previous_active["version"],
                action=PromptAuditAction.DEPRECATED,
                changes_summary=f"Deprecated by new activation of {template_id}",
                performed_by=activated_by,
            )
        
        # Activate the new template
        await db[self.COLLECTION].update_one(
            {"template_id": template_id},
            {
                "$set": {
                    "status": PromptStatus.ACTIVE.value,
                    "activated_at": now,
                    "activated_by": activated_by,
                }
            }
        )
        
        # Log activation with evidence
        await self._log_audit(
            template_id=template_id,
            version=template["version"],
            action=PromptAuditAction.ACTIVATED,
            changes_summary=f"Activated with reason: {activation_reason}",
            activation_reason=activation_reason,
            previous_active_version=previous_active_version,
            performed_by=activated_by,
        )
        
        logger.info(
            f"Activated {template_id} v{template['version']} by {activated_by}. "
            f"Previous active: v{previous_active_version}"
        )
        
        return {
            "success": True,
            "template_id": template_id,
            "new_version": template["version"],
            "status": PromptStatus.ACTIVE.value,
            "previous_active_version": previous_active_version,
            "message": "Template activated successfully",
            "activated_at": now.isoformat(),
            "activated_by": activated_by,
        }
    
    async def mark_as_tested(
        self,
        template_id: str,
        marked_by: str,
    ) -> bool:
        """
        Mark a DRAFT template as TESTED after passing validation.
        
        REQUIREMENT: Template must have a passing test result.
        """
        db = database.get_db()
        
        template = await db[self.COLLECTION].find_one(
            {"template_id": template_id},
            {"_id": 0}
        )
        
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        if template["status"] != PromptStatus.DRAFT.value:
            raise ValueError("Only DRAFT templates can be marked as TESTED")
        
        if template["last_test_status"] != PromptTestStatus.PASSED.value:
            raise ValueError(
                "Template must have a passing test before being marked as TESTED"
            )
        
        await db[self.COLLECTION].update_one(
            {"template_id": template_id},
            {
                "$set": {
                    "status": PromptStatus.TESTED.value,
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": marked_by,
                }
            }
        )
        
        await self._log_audit(
            template_id=template_id,
            version=template["version"],
            action=PromptAuditAction.TESTED,
            changes_summary="Template marked as TESTED",
            performed_by=marked_by,
        )
        
        return True
    
    # ========================================
    # AUDIT LOG
    # ========================================
    
    async def _log_audit(
        self,
        template_id: str,
        version: int,
        action: PromptAuditAction,
        changes_summary: str,
        performed_by: str,
        changes_detail: Optional[Dict[str, Any]] = None,
        test_id: Optional[str] = None,
        test_result_snapshot: Optional[Dict[str, Any]] = None,
        activation_reason: Optional[str] = None,
        previous_active_version: Optional[int] = None,
    ):
        """Log an audit entry."""
        db = database.get_db()
        
        audit_id = self._generate_id("AUD")
        
        entry = {
            "audit_id": audit_id,
            "template_id": template_id,
            "version": version,
            "action": action.value,
            "changes_summary": changes_summary,
            "changes_detail": changes_detail,
            "test_id": test_id,
            "test_result_snapshot": test_result_snapshot,
            "activation_reason": activation_reason,
            "previous_active_version": previous_active_version,
            "performed_by": performed_by,
            "performed_at": datetime.now(timezone.utc),
        }
        
        await db[self.AUDIT_COLLECTION].insert_one(entry)
    
    async def get_audit_log(
        self,
        template_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get audit log entries."""
        db = database.get_db()
        
        query = {}
        if template_id:
            query["template_id"] = template_id
        
        cursor = db[self.AUDIT_COLLECTION].find(
            query,
            {"_id": 0}
        ).sort("performed_at", -1).limit(limit)
        
        docs = await cursor.to_list(length=limit)
        
        # Convert datetime to ISO string
        for doc in docs:
            if isinstance(doc.get("performed_at"), datetime):
                doc["performed_at"] = doc["performed_at"].isoformat()
        
        return docs
    
    # ========================================
    # HELPERS
    # ========================================
    
    def _doc_to_response(self, doc: Dict[str, Any]) -> PromptTemplateResponse:
        """Convert MongoDB document to response model."""
        return PromptTemplateResponse(
            template_id=doc["template_id"],
            service_code=doc["service_code"],
            doc_type=doc["doc_type"],
            name=doc["name"],
            description=doc.get("description"),
            version=doc["version"],
            status=PromptStatus(doc["status"]),
            system_prompt=doc["system_prompt"],
            user_prompt_template=doc["user_prompt_template"],
            output_schema=doc["output_schema"],
            temperature=doc["temperature"],
            max_tokens=doc["max_tokens"],
            tags=doc.get("tags", []),
            last_test_status=PromptTestStatus(doc["last_test_status"]) if doc.get("last_test_status") else None,
            last_test_at=doc["last_test_at"].isoformat() if doc.get("last_test_at") else None,
            test_count=doc.get("test_count", 0),
            created_at=doc["created_at"].isoformat() if isinstance(doc["created_at"], datetime) else doc["created_at"],
            created_by=doc["created_by"],
            updated_at=doc["updated_at"].isoformat() if doc.get("updated_at") else None,
            updated_by=doc.get("updated_by"),
            activated_at=doc["activated_at"].isoformat() if doc.get("activated_at") else None,
            activated_by=doc.get("activated_by"),
            deprecated_at=doc["deprecated_at"].isoformat() if doc.get("deprecated_at") else None,
            deprecated_by=doc.get("deprecated_by"),
        )
    
    def _parse_llm_output(self, raw_output: str) -> Optional[Dict[str, Any]]:
        """Parse LLM output, handling markdown code blocks."""
        if not raw_output:
            return None
        
        text = raw_output.strip()
        
        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None


# Singleton instance
prompt_service = PromptService()
