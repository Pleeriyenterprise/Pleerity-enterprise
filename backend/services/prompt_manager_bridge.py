"""
Prompt Manager Integration for Document Orchestrator

This module provides the bridge between the Enterprise Prompt Manager
and the Document Orchestrator service.

Features:
- Fetches ACTIVE prompts from Prompt Manager
- Falls back to legacy gpt_prompt_registry if no managed prompt exists
- Tracks prompt_version_used for audit compliance
- Records prompt execution metrics for analytics

NON-NEGOTIABLES:
- prompt_version_used MUST be stored permanently on generated documents
- ACTIVE prompts take precedence over hardcoded registry prompts
- All executions logged for performance analytics
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from database import database
from services.gpt_prompt_registry import get_prompt_for_service, PromptDefinition

logger = logging.getLogger(__name__)

# ============================================================================
# SERVICE CODE ALIAS MAP
# ============================================================================
# Maps legacy/variant service codes to the canonical service_code used in Prompt Manager.
# This prevents silent lookup failures when orders use different naming conventions.
# 
# Pattern: "ORDER_SERVICE_CODE" -> "PROMPT_MANAGER_SERVICE_CODE"
#
SERVICE_CODE_ALIASES = {
    # AI Services
    "AI_WORKFLOW": "AI_WF_BLUEPRINT",
    "AI_TOOL_REPORT": "AI_TOOL_RECOMMENDATION",
    
    # Document Pack variants
    "DOC_PACK_ESSENTIAL": "DOC_PACK_ESSENTIAL",
    "DOC_PACK_PLUS": "DOC_PACK_PLUS", 
    "DOC_PACK_PRO": "DOC_PACK_PRO",
    
    # Compliance services
    "FULL_COMPLIANCE_AUDIT": "FULL_COMPLIANCE_AUDIT",
    "HMO_COMPLIANCE_AUDIT": "HMO_COMPLIANCE_AUDIT",
    "MOVE_IN_OUT_CHECKLIST": "MOVE_IN_OUT_CHECKLIST",
    
    # Market Research
    "MR_BASIC": "MR_BASIC",
    "MR_ADV": "MR_ADV",
}


@dataclass
class ManagedPromptInfo:
    """Information about the prompt used for generation."""
    template_id: str
    version: int
    service_code: str
    doc_type: str
    name: str
    source: str  # "prompt_manager" or "legacy_registry"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "version": self.version,
            "service_code": self.service_code,
            "doc_type": self.doc_type,
            "name": self.name,
            "source": self.source,
        }


class PromptManagerBridge:
    """
    Bridge between Prompt Manager and Document Orchestrator.
    
    Provides prompt selection with fallback to legacy registry
    and tracks prompt usage for analytics.
    """
    
    PROMPTS_COLLECTION = "prompt_templates"
    EXECUTION_METRICS_COLLECTION = "prompt_execution_metrics"
    
    async def get_prompt_for_service(
        self,
        service_code: str,
        doc_type: Optional[str] = None,
    ) -> Tuple[Optional[PromptDefinition], Optional[ManagedPromptInfo]]:
        """
        Get the prompt for a service, preferring Prompt Manager ACTIVE prompts.
        
        Priority:
        1. ACTIVE prompt from Prompt Manager matching service_code + doc_type
        2. ACTIVE prompt from Prompt Manager matching service_code (any doc_type)
        3. Legacy prompt from gpt_prompt_registry
        
        Returns:
            Tuple of (PromptDefinition, ManagedPromptInfo)
            - PromptDefinition: The prompt to use
            - ManagedPromptInfo: Tracking info (None if using legacy registry)
        """
        db = database.get_db()
        
        # Resolve service code aliases to prevent silent lookup failures
        canonical_service_code = SERVICE_CODE_ALIASES.get(service_code, service_code)
        
        if canonical_service_code != service_code:
            logger.info(f"Resolved service code alias: {service_code} -> {canonical_service_code}")
        
        # Try to find ACTIVE prompt in Prompt Manager
        query = {
            "service_code": canonical_service_code,
            "status": "ACTIVE",
        }
        
        if doc_type:
            query["doc_type"] = doc_type
        
        managed_prompt = await db[self.PROMPTS_COLLECTION].find_one(
            query,
            {"_id": 0}
        )
        
        # If no exact match with doc_type, try without doc_type filter
        if not managed_prompt and doc_type:
            managed_prompt = await db[self.PROMPTS_COLLECTION].find_one(
                {"service_code": canonical_service_code, "status": "ACTIVE"},
                {"_id": 0}
            )
        
        if managed_prompt:
            # Convert managed prompt to PromptDefinition format
            prompt_def = self._managed_to_prompt_definition(managed_prompt)
            
            prompt_info = ManagedPromptInfo(
                template_id=managed_prompt["template_id"],
                version=managed_prompt["version"],
                service_code=managed_prompt["service_code"],
                doc_type=managed_prompt["doc_type"],
                name=managed_prompt["name"],
                source="prompt_manager",
            )
            
            logger.info(
                f"Using Prompt Manager prompt for {service_code} ({canonical_service_code}): "
                f"{prompt_info.template_id} v{prompt_info.version}"
            )
            
            return prompt_def, prompt_info
        
        # Fall back to legacy registry
        legacy_prompt = get_prompt_for_service(service_code)
        
        if legacy_prompt:
            prompt_info = ManagedPromptInfo(
                template_id=f"LEGACY_{legacy_prompt.prompt_id}",
                version=0,  # Legacy prompts don't have versions
                service_code=service_code,
                doc_type=doc_type or "GENERAL_DOCUMENT",
                name=legacy_prompt.name,
                source="legacy_registry",
            )
            
            logger.info(
                f"Using legacy registry prompt for {service_code}: "
                f"{legacy_prompt.prompt_id}"
            )
            
            return legacy_prompt, prompt_info
        
        return None, None
    
    def _managed_to_prompt_definition(
        self,
        managed_prompt: Dict[str, Any],
    ) -> PromptDefinition:
        """
        Convert a managed prompt from Prompt Manager to PromptDefinition format.
        
        The key transformation is converting the {{INPUT_DATA_JSON}} pattern
        to the format expected by the orchestrator.
        """
        # The user_prompt_template uses {{INPUT_DATA_JSON}} pattern
        # We need to make it compatible with the orchestrator's format substitution
        user_template = managed_prompt["user_prompt_template"]
        
        # The orchestrator will call _build_user_prompt_with_json which handles this
        
        return PromptDefinition(
            prompt_id=managed_prompt["template_id"],
            prompt_type="MASTER",  # Managed prompts are always MASTER type
            service_code=managed_prompt["service_code"],
            name=managed_prompt["name"],
            description=managed_prompt.get("description", ""),
            system_prompt=managed_prompt["system_prompt"],
            user_prompt_template=user_template,
            output_schema=self._build_output_schema_dict(managed_prompt["output_schema"]),
            temperature=managed_prompt.get("temperature", 0.3),
            max_tokens=managed_prompt.get("max_tokens", 4000),
            required_fields=[],  # Managed prompts use schema validation instead
            gpt_sections=[],
        )
    
    def _build_output_schema_dict(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Build output schema dict from managed prompt schema format."""
        fields = schema.get("fields", [])
        
        output = {}
        for field in fields:
            field_name = field.get("field_name")
            field_type = field.get("field_type", "string")
            description = field.get("description", "")
            
            if field_type == "array":
                output[field_name] = f"[{field.get('array_item_type', 'string')}] - {description}"
            elif field_type == "object":
                output[field_name] = f"{{object}} - {description}"
            else:
                output[field_name] = f"({field_type}) - {description}"
        
        return output
    
    def build_user_prompt_with_json(
        self,
        template: str,
        intake_data: Dict[str, Any],
        regeneration: bool = False,
        regeneration_notes: Optional[str] = None,
    ) -> str:
        """
        Build user prompt using the {{INPUT_DATA_JSON}} injection pattern.
        
        This is the ONLY approved method for injecting data into managed prompts.
        """
        # Convert intake data to JSON string
        input_json = json.dumps(intake_data, indent=2, default=str)
        
        # Replace the single injection point
        user_prompt = template.replace("{{INPUT_DATA_JSON}}", input_json)
        
        # Add regeneration context if applicable
        if regeneration and regeneration_notes:
            user_prompt += f"\n\nREGENERATION REQUEST:\nPrevious version feedback: {regeneration_notes}\nPlease address the above feedback in this generation.\n"
        
        return user_prompt
    
    async def record_execution_metrics(
        self,
        prompt_info: ManagedPromptInfo,
        order_id: str,
        execution_time_ms: int,
        prompt_tokens: int,
        completion_tokens: int,
        success: bool,
        error_message: Optional[str] = None,
    ):
        """
        Record execution metrics for prompt performance analytics.
        
        This data feeds into the Prompt Performance Analytics dashboard.
        """
        db = database.get_db()
        
        metric = {
            "template_id": prompt_info.template_id,
            "version": prompt_info.version,
            "service_code": prompt_info.service_code,
            "doc_type": prompt_info.doc_type,
            "source": prompt_info.source,
            "order_id": order_id,
            "execution_time_ms": execution_time_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "success": success,
            "error_message": error_message,
            "executed_at": datetime.now(timezone.utc),
        }
        
        await db[self.EXECUTION_METRICS_COLLECTION].insert_one(metric)
        
        logger.debug(
            f"Recorded execution metrics for {prompt_info.template_id}: "
            f"{execution_time_ms}ms, {prompt_tokens + completion_tokens} tokens"
        )
    
    async def get_prompt_analytics(
        self,
        template_id: Optional[str] = None,
        service_code: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get prompt performance analytics.
        
        Returns metrics like:
        - Total executions
        - Success rate
        - Average execution time
        - Total tokens used
        - Cost estimate
        """
        db = database.get_db()
        
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        match_stage = {"executed_at": {"$gte": cutoff}}
        
        if template_id:
            match_stage["template_id"] = template_id
        if service_code:
            match_stage["service_code"] = service_code
        
        pipeline = [
            {"$match": match_stage},
            {
                "$group": {
                    "_id": {
                        "template_id": "$template_id",
                        "version": "$version",
                        "service_code": "$service_code",
                    },
                    "total_executions": {"$sum": 1},
                    "successful_executions": {
                        "$sum": {"$cond": ["$success", 1, 0]}
                    },
                    "failed_executions": {
                        "$sum": {"$cond": ["$success", 0, 1]}
                    },
                    "total_execution_time_ms": {"$sum": "$execution_time_ms"},
                    "avg_execution_time_ms": {"$avg": "$execution_time_ms"},
                    "total_prompt_tokens": {"$sum": "$prompt_tokens"},
                    "total_completion_tokens": {"$sum": "$completion_tokens"},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "min_execution_time_ms": {"$min": "$execution_time_ms"},
                    "max_execution_time_ms": {"$max": "$execution_time_ms"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "template_id": "$_id.template_id",
                    "version": "$_id.version",
                    "service_code": "$_id.service_code",
                    "total_executions": 1,
                    "successful_executions": 1,
                    "failed_executions": 1,
                    "success_rate": {
                        "$multiply": [
                            {"$divide": ["$successful_executions", "$total_executions"]},
                            100
                        ]
                    },
                    "avg_execution_time_ms": {"$round": ["$avg_execution_time_ms", 0]},
                    "min_execution_time_ms": 1,
                    "max_execution_time_ms": 1,
                    "total_prompt_tokens": 1,
                    "total_completion_tokens": 1,
                    "total_tokens": 1,
                }
            },
            {"$sort": {"total_executions": -1}},
        ]
        
        cursor = db[self.EXECUTION_METRICS_COLLECTION].aggregate(pipeline)
        results = await cursor.to_list(length=100)
        
        # Calculate totals
        total_executions = sum(r["total_executions"] for r in results)
        total_successful = sum(r["successful_executions"] for r in results)
        total_tokens = sum(r["total_tokens"] for r in results)
        
        return {
            "period_days": days,
            "total_executions": total_executions,
            "total_successful": total_successful,
            "total_failed": total_executions - total_successful,
            "overall_success_rate": round(
                (total_successful / total_executions * 100) if total_executions > 0 else 0,
                2
            ),
            "total_tokens_used": total_tokens,
            "by_prompt": results,
        }


# Singleton instance
prompt_manager_bridge = PromptManagerBridge()
