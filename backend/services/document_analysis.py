"""AI Document Analysis Service - Extracts metadata from compliance documents."""
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
from database import database
from models import AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# System prompt for document analysis
DOCUMENT_ANALYSIS_PROMPT = """You are an expert document analyzer specializing in UK property compliance certificates.

Your task is to extract specific metadata from compliance documents such as:
- Gas Safety Certificates (CP12)
- Electrical Installation Condition Reports (EICR)
- Energy Performance Certificates (EPC)
- Fire Safety Certificates
- Legionella Risk Assessments
- HMO Licenses
- PAT Testing Reports

For each document, extract and return a JSON object with the following structure:
{
    "document_type": "string - type of document (e.g., 'Gas Safety Certificate', 'EICR', 'EPC')",
    "certificate_number": "string or null - certificate/report number if present",
    "issue_date": "string or null - date issued in YYYY-MM-DD format",
    "expiry_date": "string or null - expiry date in YYYY-MM-DD format",
    "next_inspection_date": "string or null - next inspection due date in YYYY-MM-DD format",
    "property_address": "string or null - property address mentioned",
    "engineer_name": "string or null - name of engineer/assessor",
    "engineer_registration": "string or null - Gas Safe/NICEIC/other registration number",
    "company_name": "string or null - company that issued the certificate",
    "rating": "string or null - for EPC, the energy rating (A-G)",
    "result": "string or null - PASS/FAIL/SATISFACTORY/UNSATISFACTORY if applicable",
    "key_findings": ["array of strings - any important findings or notes"],
    "confidence_scores": {
        "document_type": 0.0 to 1.0,
        "certificate_number": 0.0 to 1.0,
        "issue_date": 0.0 to 1.0,
        "expiry_date": 0.0 to 1.0,
        "overall": 0.0 to 1.0
    }
}

Rules:
1. Only extract information that is clearly visible in the document
2. If a field cannot be determined, set it to null
3. Confidence scores should reflect how certain you are about each extraction
4. Dates must be converted to YYYY-MM-DD format
5. Be conservative - if unsure, indicate lower confidence
6. Do not make up information - only extract what's visible

Return ONLY the JSON object, no additional text."""


class DocumentAnalysisService:
    def __init__(self):
        self.api_key = os.getenv("EMERGENT_LLM_KEY", "sk-emergent-f9533226f52E25cF35")
        logger.info("Document Analysis Service initialized")
    
    async def analyze_document(
        self,
        file_path: str,
        mime_type: str,
        document_id: str,
        client_id: str,
        actor_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a document using AI to extract metadata.
        
        Args:
            file_path: Path to the document file
            mime_type: MIME type of the file
            document_id: ID of the document record
            client_id: ID of the client
            actor_id: ID of the user who triggered the analysis
            
        Returns:
            Dictionary with extracted metadata and confidence scores
        """
        db = database.get_db()
        
        try:
            # Verify file exists
            if not os.path.exists(file_path):
                logger.error(f"Document file not found: {file_path}")
                return {
                    "success": False,
                    "error": "Document file not found",
                    "extracted_data": None
                }
            
            # Initialize chat with Gemini (required for file attachments)
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"doc-analysis-{document_id}",
                system_message=DOCUMENT_ANALYSIS_PROMPT
            ).with_model("gemini", "gemini-2.5-flash")
            
            # Create file content object
            file_content = FileContentWithMimeType(
                file_path=file_path,
                mime_type=mime_type
            )
            
            # Send message with file attachment
            user_message = UserMessage(
                text="Please analyze this compliance document and extract all relevant metadata. Return only the JSON object.",
                file_contents=[file_content]
            )
            
            response = await chat.send_message(user_message)
            
            # Parse the JSON response
            try:
                # Clean up response - remove markdown code blocks if present
                response_text = response.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                extracted_data = json.loads(response_text)
                
                # Store extraction result in document record
                await db.documents.update_one(
                    {"document_id": document_id},
                    {"$set": {
                        "ai_extraction": {
                            "extracted_at": datetime.now(timezone.utc).isoformat(),
                            "data": extracted_data,
                            "status": "completed"
                        }
                    }}
                )
                
                # Audit log
                await create_audit_log(
                    action=AuditAction.DOCUMENT_AI_ANALYZED,
                    actor_id=actor_id,
                    client_id=client_id,
                    resource_type="document",
                    resource_id=document_id,
                    metadata={
                        "document_type": extracted_data.get("document_type"),
                        "overall_confidence": extracted_data.get("confidence_scores", {}).get("overall"),
                        "has_expiry_date": extracted_data.get("expiry_date") is not None
                    }
                )
                
                logger.info(f"Document analyzed successfully: {document_id}")
                
                return {
                    "success": True,
                    "extracted_data": extracted_data,
                    "error": None
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Response was: {response[:500]}")
                
                # Store failed extraction
                await db.documents.update_one(
                    {"document_id": document_id},
                    {"$set": {
                        "ai_extraction": {
                            "extracted_at": datetime.now(timezone.utc).isoformat(),
                            "status": "failed",
                            "error": "Failed to parse AI response",
                            "raw_response": response[:1000]
                        }
                    }}
                )
                
                return {
                    "success": False,
                    "error": "Failed to parse AI response",
                    "extracted_data": None
                }
        
        except Exception as e:
            logger.error(f"Document analysis error: {e}")
            
            # Store error in document record
            await db.documents.update_one(
                {"document_id": document_id},
                {"$set": {
                    "ai_extraction": {
                        "extracted_at": datetime.now(timezone.utc).isoformat(),
                        "status": "failed",
                        "error": str(e)
                    }
                }}
            )
            
            return {
                "success": False,
                "error": str(e),
                "extracted_data": None
            }
    
    async def get_extraction_summary(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get the AI extraction summary for a document."""
        db = database.get_db()
        
        document = await db.documents.find_one(
            {"document_id": document_id},
            {"_id": 0, "ai_extraction": 1}
        )
        
        if document and document.get("ai_extraction"):
            return document["ai_extraction"]
        
        return None


# Singleton instance
document_analysis_service = DocumentAnalysisService()
