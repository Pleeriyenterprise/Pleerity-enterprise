"""ClearForm Document Service

Handles document generation using AI (Gemini via Emergent LLM Key).
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import json

from database import database
from clearform.models.documents import (
    ClearFormDocument,
    ClearFormDocumentType,
    ClearFormDocumentStatus,
    DocumentGenerationRequest,
    DocumentVaultItem,
    DocumentVaultResponse,
    DOCUMENT_TYPE_CONFIG,
)
from clearform.models.credits import CreditTransactionType, DOCUMENT_CREDIT_COSTS
from clearform.services.credit_service import credit_service

logger = logging.getLogger(__name__)


class DocumentService:
    """Document generation and vault management service."""
    
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        if self.db is None:
            self.db = database.get_db()
        return self.db
    
    async def create_document(
        self,
        user_id: str,
        request: DocumentGenerationRequest,
    ) -> ClearFormDocument:
        """Create a new document generation request.
        
        1. Check user has sufficient credits
        2. Deduct credits
        3. Create document record
        4. Trigger generation (async)
        """
        db = self._get_db()
        
        # Get credit cost
        doc_type = request.document_type.value
        credit_cost = DOCUMENT_CREDIT_COSTS.get(doc_type, 1)
        
        # Check balance
        has_credits = await credit_service.check_balance(user_id, credit_cost)
        if not has_credits:
            raise ValueError(f"Insufficient credits. Need {credit_cost} credits for {doc_type}")
        
        # Generate title from intent if not provided
        title = self._generate_title(request)
        
        # Create document record
        document = ClearFormDocument(
            user_id=user_id,
            document_type=request.document_type,
            title=title,
            intent_data=request.model_dump(exclude_none=True),
            status=ClearFormDocumentStatus.PENDING,
            credits_used=credit_cost,
        )
        
        # Deduct credits
        transaction, success = await credit_service.deduct_credits(
            user_id=user_id,
            amount=credit_cost,
            transaction_type=CreditTransactionType.DOCUMENT_GENERATION,
            description=f"Document generation: {title}",
            reference_id=document.document_id,
            reference_type="document",
        )
        
        if not success:
            raise ValueError("Failed to deduct credits")
        
        document.credit_transaction_id = transaction.transaction_id
        
        # Save document
        await db.clearform_documents.insert_one(document.model_dump())
        
        logger.info(f"Created document {document.document_id} for user {user_id}")
        
        # Trigger async generation
        await self._generate_document_content(document)
        
        return document
    
    def _generate_title(self, request: DocumentGenerationRequest) -> str:
        """Generate a title from the request."""
        if request.document_type == ClearFormDocumentType.CV_RESUME:
            if request.full_name and request.job_title_target:
                return f"{request.full_name} - {request.job_title_target} CV"
            elif request.full_name:
                return f"{request.full_name}'s CV"
            return "Professional CV"
        
        elif request.document_type == ClearFormDocumentType.COMPLAINT_LETTER:
            if request.company_name:
                return f"Complaint to {request.company_name}"
            return "Complaint Letter"
        
        elif request.document_type == ClearFormDocumentType.FORMAL_LETTER:
            if request.subject:
                return request.subject
            elif request.recipient_organization:
                return f"Letter to {request.recipient_organization}"
            return "Formal Letter"
        
        return f"{request.document_type.value.replace('_', ' ').title()}"
    
    async def _generate_document_content(self, document: ClearFormDocument) -> None:
        """Generate document content using AI.
        
        This is called after document creation and credit deduction.
        """
        db = self._get_db()
        start_time = datetime.now(timezone.utc)
        
        try:
            # Update status to generating
            await db.clearform_documents.update_one(
                {"document_id": document.document_id},
                {"$set": {"status": ClearFormDocumentStatus.GENERATING.value, "updated_at": start_time}}
            )
            
            # Build prompt based on document type
            prompt = self._build_generation_prompt(document)
            
            # Call LLM using emergentintegrations
            import os
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            chat = LlmChat(
                api_key=os.environ.get("EMERGENT_LLM_KEY"),
                session_id=f"clearform-{document.document_id}",
                system_message=self._get_system_prompt(document.document_type),
            ).with_model("gemini", "gemini-2.0-flash")
            
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
            
            # Parse response
            content = response.strip()
            
            # Calculate generation time
            end_time = datetime.now(timezone.utc)
            generation_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Update document with content
            await db.clearform_documents.update_one(
                {"document_id": document.document_id},
                {
                    "$set": {
                        "status": ClearFormDocumentStatus.COMPLETED.value,
                        "content_markdown": content,
                        "content_plain": self._markdown_to_plain(content),
                        "ai_model_used": "gemini-2.0-flash",
                        "generation_time_ms": generation_time_ms,
                        "completed_at": end_time,
                        "updated_at": end_time,
                    }
                }
            )
            
            logger.info(f"Generated document {document.document_id} in {generation_time_ms}ms")
            
        except Exception as e:
            logger.error(f"Document generation failed for {document.document_id}: {e}")
            
            # Update status to failed
            await db.clearform_documents.update_one(
                {"document_id": document.document_id},
                {
                    "$set": {
                        "status": ClearFormDocumentStatus.FAILED.value,
                        "error_message": str(e),
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$inc": {"retry_count": 1}
                }
            )
            
            # Refund credits on failure
            await credit_service.add_credits(
                user_id=document.user_id,
                amount=document.credits_used,
                transaction_type=CreditTransactionType.REFUND,
                description=f"Refund for failed generation: {document.title}",
                reference_id=document.document_id,
                reference_type="document_refund",
            )
    
    def _get_system_prompt(self, document_type: ClearFormDocumentType) -> str:
        """Get system prompt for document type."""
        if document_type == ClearFormDocumentType.FORMAL_LETTER:
            return """You are a professional letter writing assistant. Generate formal, well-structured letters that are:
- Professional and appropriately formal
- Clear and concise
- Properly formatted with date, addresses, salutation, body, and closing
- Grammatically correct
- Suitable for business or official correspondence

Output the letter in markdown format with proper structure."""

        elif document_type == ClearFormDocumentType.COMPLAINT_LETTER:
            return """You are a professional complaint letter writing assistant. Generate effective complaint letters that are:
- Professional but firm
- Clear about the issue and desired resolution
- Include relevant reference numbers and dates
- Properly formatted with all necessary sections
- Persuasive but respectful

Output the letter in markdown format with proper structure."""

        elif document_type == ClearFormDocumentType.CV_RESUME:
            return """You are a professional CV/Resume writing assistant. Generate modern, ATS-friendly CVs that are:
- Well-structured with clear sections
- Achievement-focused using action verbs
- Tailored to the target role
- Professional and clean formatting
- Optimized for both human readers and ATS systems

Output the CV in markdown format with proper sections (Summary, Experience, Education, Skills)."""

        return "You are a professional document writing assistant. Generate clear, well-formatted documents."
    
    def _build_generation_prompt(self, document: ClearFormDocument) -> str:
        """Build the user prompt for document generation."""
        intent_data = document.intent_data
        doc_type = document.document_type
        
        if doc_type == ClearFormDocumentType.FORMAL_LETTER:
            parts = [f"Write a formal letter with the following requirements:\n\nIntent: {intent_data.get('intent', 'Professional correspondence')}"]
            if intent_data.get("recipient_name"):
                parts.append(f"Recipient: {intent_data['recipient_name']}")
            if intent_data.get("recipient_title"):
                parts.append(f"Title: {intent_data['recipient_title']}")
            if intent_data.get("recipient_organization"):
                parts.append(f"Organization: {intent_data['recipient_organization']}")
            if intent_data.get("sender_name"):
                parts.append(f"Sender: {intent_data['sender_name']}")
            if intent_data.get("subject"):
                parts.append(f"Subject: {intent_data['subject']}")
            if intent_data.get("tone"):
                parts.append(f"Tone: {intent_data['tone']}")
            return "\n".join(parts)
        
        elif doc_type == ClearFormDocumentType.COMPLAINT_LETTER:
            parts = [f"Write a professional complaint letter with the following details:\n\nIntent: {intent_data.get('intent', 'File a complaint')}"]
            if intent_data.get("company_name"):
                parts.append(f"Company: {intent_data['company_name']}")
            if intent_data.get("issue_date"):
                parts.append(f"Issue Date: {intent_data['issue_date']}")
            if intent_data.get("issue_description"):
                parts.append(f"Issue: {intent_data['issue_description']}")
            if intent_data.get("desired_resolution"):
                parts.append(f"Desired Resolution: {intent_data['desired_resolution']}")
            if intent_data.get("order_reference"):
                parts.append(f"Reference Number: {intent_data['order_reference']}")
            return "\n".join(parts)
        
        elif doc_type == ClearFormDocumentType.CV_RESUME:
            parts = [f"Create a professional CV/Resume with the following information:\n\nCareer Goal: {intent_data.get('intent', 'Professional career advancement')}"]
            if intent_data.get("full_name"):
                parts.append(f"Name: {intent_data['full_name']}")
            if intent_data.get("job_title_target"):
                parts.append(f"Target Role: {intent_data['job_title_target']}")
            if intent_data.get("years_experience"):
                parts.append(f"Years of Experience: {intent_data['years_experience']}")
            if intent_data.get("skills"):
                parts.append(f"Key Skills: {', '.join(intent_data['skills'])}")
            if intent_data.get("work_history"):
                parts.append(f"Work History:\n{json.dumps(intent_data['work_history'], indent=2)}")
            if intent_data.get("education"):
                parts.append(f"Education:\n{json.dumps(intent_data['education'], indent=2)}")
            return "\n".join(parts)
        
        return f"Generate a {doc_type.value.replace('_', ' ')}: {intent_data.get('intent', '')}"
    
    def _markdown_to_plain(self, markdown: str) -> str:
        """Convert markdown to plain text (basic)."""
        import re
        # Remove markdown formatting
        plain = re.sub(r'\*\*(.+?)\*\*', r'\1', markdown)  # Bold
        plain = re.sub(r'\*(.+?)\*', r'\1', plain)  # Italic
        plain = re.sub(r'#{1,6}\s*', '', plain)  # Headers
        plain = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', plain)  # Links
        return plain.strip()
    
    async def get_document(self, user_id: str, document_id: str) -> Optional[ClearFormDocument]:
        """Get a document by ID (must belong to user)."""
        db = self._get_db()
        doc = await db.clearform_documents.find_one(
            {"document_id": document_id, "user_id": user_id},
            {"_id": 0}
        )
        if doc:
            return ClearFormDocument(**doc)
        return None
    
    async def get_vault(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        document_type: Optional[ClearFormDocumentType] = None,
        status: Optional[ClearFormDocumentStatus] = None,
        search: Optional[str] = None,
    ) -> DocumentVaultResponse:
        """Get user's document vault with pagination and filters."""
        db = self._get_db()
        
        query = {"user_id": user_id}
        
        # Exclude archived by default
        if status:
            query["status"] = status.value
        else:
            query["status"] = {"$ne": ClearFormDocumentStatus.ARCHIVED.value}
        
        if document_type:
            query["document_type"] = document_type.value
        
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"tags": {"$in": [search.lower()]}},
            ]
        
        # Get total count
        total = await db.clearform_documents.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * page_size
        cursor = db.clearform_documents.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(page_size)
        
        items = []
        async for doc in cursor:
            items.append(DocumentVaultItem(
                document_id=doc["document_id"],
                document_type=doc["document_type"],
                title=doc["title"],
                status=doc["status"],
                created_at=doc["created_at"],
                completed_at=doc.get("completed_at"),
                tags=doc.get("tags", []),
                has_pdf=doc.get("pdf_file_id") is not None,
                has_docx=doc.get("docx_file_id") is not None,
            ))
        
        return DocumentVaultResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(skip + len(items)) < total,
        )
    
    async def archive_document(self, user_id: str, document_id: str) -> bool:
        """Archive a document (soft delete)."""
        db = self._get_db()
        result = await db.clearform_documents.update_one(
            {"document_id": document_id, "user_id": user_id},
            {
                "$set": {
                    "status": ClearFormDocumentStatus.ARCHIVED.value,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        return result.modified_count > 0
    
    async def update_tags(self, user_id: str, document_id: str, tags: List[str]) -> bool:
        """Update document tags."""
        db = self._get_db()
        result = await db.clearform_documents.update_one(
            {"document_id": document_id, "user_id": user_id},
            {
                "$set": {
                    "tags": [t.lower().strip() for t in tags],
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        return result.modified_count > 0
    
    async def get_document_types(self) -> List[Dict[str, Any]]:
        """Get available document types with their configurations."""
        return [
            {
                "type": doc_type.value,
                **config,
            }
            for doc_type, config in DOCUMENT_TYPE_CONFIG.items()
        ]


# Global service instance
document_service = DocumentService()
