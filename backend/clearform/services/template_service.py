"""ClearForm Template Service

Handles deterministic and hybrid document generation using templates.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import re
import os

from database import database
from clearform.models.documents import (
    ClearFormDocument,
    ClearFormDocumentType,
    ClearFormDocumentStatus,
)
from clearform.models.rule_packs import (
    DocumentTemplate,
    TemplateSection,
    RulePack,
    ValidationRule,
    ValidationSeverity,
    GenerationMode,
    get_template,
    get_rule_pack,
    get_templates_for_type,
    get_rule_packs_for_type,
    DOCUMENT_TEMPLATES,
    RULE_PACKS,
)
from clearform.models.workspaces import SmartProfile
from clearform.models.credits import CreditTransactionType
from clearform.services.credit_service import credit_service

logger = logging.getLogger(__name__)


class TemplateService:
    """Template-based document generation service."""
    
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        if self.db is None:
            self.db = database.get_db()
        return self.db
    
    # =========================================================================
    # TEMPLATE & RULE PACK QUERIES
    # =========================================================================
    
    async def get_available_templates(
        self,
        document_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get available templates, optionally filtered by document type."""
        templates = []
        
        for template in DOCUMENT_TEMPLATES.values():
            if not template.is_active:
                continue
            if document_type and template.document_type != document_type:
                continue
            
            templates.append({
                "template_id": template.template_id,
                "name": template.name,
                "description": template.description,
                "document_type": template.document_type,
                "generation_mode": template.generation_mode.value,
                "category": template.category.value,
                "tags": template.tags,
                "credit_cost": template.credit_cost,
                "use_count": template.use_count,
                "has_rule_pack": template.rule_pack_id is not None,
            })
        
        return templates
    
    async def get_template_details(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get full template details including sections and placeholders."""
        template = get_template(template_id)
        if not template:
            return None
        
        # Get associated rule pack
        rule_pack = None
        if template.rule_pack_id:
            rule_pack = get_rule_pack(template.rule_pack_id)
        
        return {
            "template": template.model_dump(),
            "rule_pack": rule_pack.model_dump() if rule_pack else None,
        }
    
    async def get_rule_packs(
        self,
        document_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get available rule packs."""
        packs = []
        
        for pack in RULE_PACKS.values():
            if not pack.is_active:
                continue
            if document_type and document_type not in pack.document_types:
                continue
            
            packs.append({
                "pack_id": pack.pack_id,
                "name": pack.name,
                "description": pack.description,
                "category": pack.category.value,
                "document_types": pack.document_types,
                "compliance_standard": pack.compliance_standard,
                "section_count": len(pack.required_sections),
                "rule_count": len(pack.validation_rules),
                "is_premium": pack.is_premium,
            })
        
        return packs
    
    # =========================================================================
    # PROFILE PRE-FILL
    # =========================================================================
    
    async def get_user_profiles(self, user_id: str) -> List[SmartProfile]:
        """Get user's smart profiles for auto-fill."""
        db = self._get_db()
        profiles = await db.clearform_smart_profiles.find(
            {"user_id": user_id},
            {"_id": 0}
        ).to_list(length=50)
        
        return [SmartProfile(**p) for p in profiles]
    
    async def get_default_profile(self, user_id: str) -> Optional[SmartProfile]:
        """Get user's default smart profile."""
        db = self._get_db()
        profile = await db.clearform_smart_profiles.find_one(
            {"user_id": user_id, "is_default": True},
            {"_id": 0}
        )
        return SmartProfile(**profile) if profile else None
    
    def apply_profile_to_template(
        self,
        template: DocumentTemplate,
        profile: SmartProfile,
    ) -> Dict[str, str]:
        """Map profile fields to template placeholders.
        
        Returns a dict of placeholder_key -> value for auto-fill.
        """
        prefilled = {}
        
        for section in template.sections:
            for placeholder in section.placeholders:
                if placeholder.profile_field:
                    value = getattr(profile, placeholder.profile_field, None)
                    if value:
                        prefilled[placeholder.key] = value
        
        return prefilled
    
    # =========================================================================
    # TEMPLATE-BASED GENERATION
    # =========================================================================
    
    async def generate_from_template(
        self,
        user_id: str,
        template_id: str,
        data: Dict[str, Any],
        profile_id: Optional[str] = None,
    ) -> ClearFormDocument:
        """Generate a document using a template.
        
        Args:
            user_id: User ID
            template_id: Template to use
            data: Placeholder values
            profile_id: Optional profile for auto-fill
        
        Returns:
            Generated document
        """
        db = self._get_db()
        
        # Get template
        template = get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        # Check credits
        credit_cost = template.credit_cost
        has_credits = await credit_service.check_balance(user_id, credit_cost)
        if not has_credits:
            raise ValueError(f"Insufficient credits. Need {credit_cost} credits.")
        
        # Apply profile pre-fill if provided
        if profile_id:
            profile = await self._get_profile(user_id, profile_id)
            if profile:
                prefilled = self.apply_profile_to_template(template, profile)
                # Merge with provided data (provided data takes precedence)
                data = {**prefilled, **data}
        
        # Generate title
        title = self._generate_title_from_data(template, data)
        
        # Create document record
        doc_type = ClearFormDocumentType(template.document_type)
        document = ClearFormDocument(
            user_id=user_id,
            document_type=doc_type,
            title=title,
            intent_data={
                "template_id": template_id,
                "template_name": template.name,
                "generation_mode": template.generation_mode.value,
                **data,
            },
            status=ClearFormDocumentStatus.PENDING,
            credits_used=credit_cost,
        )
        
        # Deduct credits
        transaction, success = await credit_service.deduct_credits(
            user_id=user_id,
            amount=credit_cost,
            transaction_type=CreditTransactionType.DOCUMENT_GENERATION,
            description=f"Template document: {title}",
            reference_id=document.document_id,
            reference_type="document",
        )
        
        if not success:
            raise ValueError("Failed to deduct credits")
        
        document.credit_transaction_id = transaction.transaction_id
        
        # Save document
        await db.clearform_documents.insert_one(document.model_dump())
        
        logger.info(f"Created template document {document.document_id} for user {user_id}")
        
        # Generate content
        await self._generate_template_content(document, template, data)
        
        return document
    
    async def _get_profile(self, user_id: str, profile_id: str) -> Optional[SmartProfile]:
        """Get a specific profile."""
        db = self._get_db()
        profile = await db.clearform_smart_profiles.find_one(
            {"user_id": user_id, "profile_id": profile_id},
            {"_id": 0}
        )
        return SmartProfile(**profile) if profile else None
    
    def _generate_title_from_data(
        self,
        template: DocumentTemplate,
        data: Dict[str, Any],
    ) -> str:
        """Generate document title from template and data."""
        if data.get("subject"):
            return data["subject"]
        
        if template.document_type == "complaint_letter":
            company = data.get("company_name", "Company")
            return f"Complaint to {company}"
        
        if template.document_type == "formal_letter":
            recipient = data.get("recipient_name") or data.get("recipient_organization")
            if recipient:
                return f"Letter to {recipient}"
        
        return f"{template.name} Document"
    
    async def _generate_template_content(
        self,
        document: ClearFormDocument,
        template: DocumentTemplate,
        data: Dict[str, Any],
    ) -> None:
        """Generate document content from template."""
        db = self._get_db()
        start_time = datetime.now(timezone.utc)
        
        try:
            # Update status
            await db.clearform_documents.update_one(
                {"document_id": document.document_id},
                {"$set": {"status": ClearFormDocumentStatus.GENERATING.value}}
            )
            
            content_parts = []
            
            for section in sorted(template.sections, key=lambda s: s.order):
                section_content = await self._render_section(section, data, template.generation_mode)
                if section_content:
                    content_parts.append(section_content)
            
            # Combine all sections
            full_content = "\n\n".join(content_parts)
            
            # Validate against rule pack
            validation_results = None
            if template.rule_pack_id:
                rule_pack = get_rule_pack(template.rule_pack_id)
                if rule_pack:
                    validation_results = self._validate_document(full_content, data, rule_pack)
            
            # Calculate time
            end_time = datetime.now(timezone.utc)
            generation_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Update document
            await db.clearform_documents.update_one(
                {"document_id": document.document_id},
                {
                    "$set": {
                        "status": ClearFormDocumentStatus.COMPLETED.value,
                        "content_markdown": full_content,
                        "content_plain": self._markdown_to_plain(full_content),
                        "ai_model_used": "template" if template.generation_mode == GenerationMode.TEMPLATE_ONLY else "gemini-2.0-flash",
                        "generation_time_ms": generation_time_ms,
                        "completed_at": end_time,
                        "updated_at": end_time,
                        "validation_results": validation_results,
                    }
                }
            )
            
            logger.info(f"Generated template document {document.document_id} in {generation_time_ms}ms")
            
        except Exception as e:
            logger.error(f"Template generation failed for {document.document_id}: {e}")
            
            await db.clearform_documents.update_one(
                {"document_id": document.document_id},
                {
                    "$set": {
                        "status": ClearFormDocumentStatus.FAILED.value,
                        "error_message": str(e),
                        "updated_at": datetime.now(timezone.utc),
                    }
                }
            )
            
            # Refund credits
            await credit_service.add_credits(
                user_id=document.user_id,
                amount=document.credits_used,
                transaction_type=CreditTransactionType.REFUND,
                description=f"Refund for failed generation: {document.title}",
                reference_id=document.document_id,
                reference_type="document_refund",
            )
    
    async def _render_section(
        self,
        section: TemplateSection,
        data: Dict[str, Any],
        generation_mode: GenerationMode,
    ) -> str:
        """Render a single template section."""
        content = section.content
        
        # Replace placeholders
        for placeholder in section.placeholders:
            key = placeholder.key
            value = data.get(key, placeholder.default_value or "")
            
            # Handle special formatting
            if placeholder.field_type == "date" and not value:
                value = datetime.now().strftime("%d %B %Y")
            
            content = content.replace(f"{{{{{key}}}}}", str(value) if value else "")
        
        # Clean up empty lines and unresolved placeholders
        content = re.sub(r'\{\{[^}]+\}\}', '', content)  # Remove unresolved
        content = re.sub(r'\n{3,}', '\n\n', content)     # Multiple blank lines -> 2
        
        # AI enhancement for hybrid mode
        if section.is_ai_enhanced and generation_mode in [GenerationMode.HYBRID, GenerationMode.AI_FULL]:
            content = await self._enhance_with_ai(section, content, data)
        
        return content.strip()
    
    async def _enhance_with_ai(
        self,
        section: TemplateSection,
        current_content: str,
        data: Dict[str, Any],
    ) -> str:
        """Enhance section content with AI."""
        if not section.ai_prompt:
            return current_content
        
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            # Build prompt with data substitution
            prompt = section.ai_prompt
            for key, value in data.items():
                prompt = prompt.replace(f"{{{{{key}}}}}", str(value) if value else "[not provided]")
            
            chat = LlmChat(
                api_key=os.environ.get("EMERGENT_LLM_KEY"),
                session_id=f"template-{section.section_id}",
                system_message="You are a professional document writer. Generate clear, professional content. Output only the requested content, no explanations or formatting instructions.",
            ).with_model("gemini", "gemini-2.0-flash")
            
            response = await chat.send_message(UserMessage(text=prompt))
            return response.strip()
            
        except Exception as e:
            logger.error(f"AI enhancement failed: {e}")
            return current_content
    
    def _validate_document(
        self,
        content: str,
        data: Dict[str, Any],
        rule_pack: RulePack,
    ) -> List[Dict[str, Any]]:
        """Validate document against rule pack."""
        results = []
        
        for rule in rule_pack.validation_rules:
            result = self._evaluate_rule(rule, content, data)
            if result:
                results.append(result)
        
        return results
    
    def _evaluate_rule(
        self,
        rule: ValidationRule,
        content: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Evaluate a single validation rule."""
        passed = True
        
        # Parse condition
        condition = rule.condition
        
        if condition == "required":
            field_value = data.get(rule.field, "")
            passed = bool(field_value and str(field_value).strip())
        
        elif condition.startswith("min_length:"):
            min_len = int(condition.split(":")[1])
            if rule.section:
                # Check section content length
                passed = len(content) >= min_len
            elif rule.field:
                field_value = data.get(rule.field, "")
                passed = len(str(field_value)) >= min_len
        
        elif condition.startswith("max_length:"):
            max_len = int(condition.split(":")[1])
            if rule.field:
                field_value = data.get(rule.field, "")
                passed = len(str(field_value)) <= max_len
        
        elif condition.startswith("pattern:"):
            pattern = condition.split(":", 1)[1]
            if rule.section:
                passed = bool(re.search(pattern, content, re.IGNORECASE))
            elif rule.field:
                field_value = data.get(rule.field, "")
                passed = bool(re.search(pattern, str(field_value), re.IGNORECASE))
        
        elif condition == "has_numbers":
            passed = bool(re.search(r'\d+', content))
        
        elif condition == "has_deadline":
            passed = bool(re.search(r'\d+\s*(days?|weeks?|business days?)', content, re.IGNORECASE))
        
        elif condition == "no_profanity":
            # Simple check - could be enhanced
            profanity = ["damn", "hell", "crap"]  # Minimal list
            passed = not any(word in content.lower() for word in profanity)
        
        # Only return failed rules
        if not passed:
            return {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "severity": rule.severity.value,
                "message": rule.error_message,
                "suggestion": rule.suggestion,
            }
        
        return None
    
    def _markdown_to_plain(self, markdown: str) -> str:
        """Convert markdown to plain text."""
        plain = re.sub(r'\*\*(.+?)\*\*', r'\1', markdown)
        plain = re.sub(r'\*(.+?)\*', r'\1', plain)
        plain = re.sub(r'#{1,6}\s*', '', plain)
        plain = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', plain)
        return plain.strip()


# Global service instance
template_service = TemplateService()
