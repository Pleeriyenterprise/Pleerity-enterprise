"""AI Document Analysis Service - Extracts metadata from compliance documents.

IMPORTANT: This service is ASSISTIVE ONLY. Extracted data must be reviewed by users
before being applied. AI CANNOT mark a requirement as compliant - the deterministic
compliance engine remains the final authority.
"""
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
from database import database
from models import AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Document type specific extraction prompts for enhanced accuracy
DOCUMENT_TYPE_PROMPTS = {
    "gas_safety": """You are analyzing a UK Gas Safety Certificate (CP12/CP17 Landlord Gas Safety Record).

PRIORITY FIELDS TO EXTRACT (in order of importance):
1. **Expiry Date / Next Check Due**: Usually labeled "Landlord Check Due" or "Next Inspection Date" - CRITICAL
2. **Issue Date / Date of Check**: When the inspection was performed
3. **Certificate/Record Number**: Unique identifier for this certificate
4. **Gas Safe Registered Engineer**:
   - Name of engineer
   - Gas Safe registration number (7-digit number)
5. **Property Address**: Address of the inspected property
6. **Appliances Checked**: List of gas appliances inspected
7. **Result**: Overall result (PASS/FAIL or SATISFACTORY)
8. **Defects Found**: Any issues or warnings noted
9. **Company/Employer Details**: Company that issued the certificate

Gas Safety certificates are valid for 12 months. The expiry date is typically exactly 1 year from issue.""",

    "eicr": """You are analyzing a UK Electrical Installation Condition Report (EICR).

PRIORITY FIELDS TO EXTRACT (in order of importance):
1. **Next Inspection Date**: When the next EICR is due - CRITICAL
2. **Date of Inspection**: When this inspection was completed
3. **Report Reference Number**: Unique report identifier
4. **Classification**: Overall condition (C1 - Danger, C2 - Urgent, C3 - Improvement recommended, FI - Further Investigation)
5. **Electrician/Inspector Details**:
   - Name of inspector
   - Registration number (NICEIC, NAPIT, ELECSA, etc.)
   - Scheme provider
6. **Property Address**: Address of the inspected installation
7. **Installation Details**: 
   - Number of circuits tested
   - Type of installation
8. **Observations/Defects**: Any issues found, categorized by code
9. **Company Details**: Electrical contractor information

EICR validity varies: typically 5 years for rental properties, 3 years for older installations.""",

    "epc": """You are analyzing a UK Energy Performance Certificate (EPC).

PRIORITY FIELDS TO EXTRACT (in order of importance):
1. **Valid Until / Expiry Date**: EPCs are valid for 10 years - CRITICAL
2. **Date of Assessment / Issue Date**: When the EPC was created
3. **Certificate Reference Number / RRN**: The EPC's unique reference (format: XXXX-XXXX-XXXX-XXXX-XXXX)
4. **Energy Rating**: Current rating (A-G) and score (1-100)
5. **Potential Rating**: Potential rating if improvements made
6. **Assessor Details**:
   - Name of assessor
   - Assessor ID / Accreditation number
   - Accreditation scheme
7. **Property Address**: Full address of the property
8. **Property Type**: Dwelling type (house, flat, etc.)
9. **Floor Area**: Total floor area in square meters
10. **Main Heating**: Primary heating system type
11. **Recommendations**: Suggested improvements listed

EPCs are valid for 10 years from the assessment date.""",

    "default": """You are an expert document analyzer specializing in UK property compliance certificates.

Analyze this document and extract key compliance information."""
}

# Base extraction structure for all document types
BASE_EXTRACTION_PROMPT = """
Return a JSON object with this EXACT structure:
{
    "document_type": "string - exact type (e.g., 'Gas Safety Certificate', 'EICR', 'EPC')",
    "document_subtype": "string or null - specific variant (e.g., 'CP12', 'Landlord Certificate', 'Domestic EPC')",
    "certificate_number": "string or null - certificate/report/RRN number",
    "issue_date": "string or null - date in YYYY-MM-DD format",
    "expiry_date": "string or null - expiry/next inspection date in YYYY-MM-DD format",
    "property_address": "string or null - full property address",
    "engineer_details": {
        "name": "string or null",
        "registration_number": "string or null - Gas Safe ID, NICEIC number, Assessor ID, etc.",
        "registration_scheme": "string or null - e.g., 'Gas Safe', 'NICEIC', 'NAPIT', 'Elmhurst'",
        "company_name": "string or null"
    },
    "result_summary": {
        "overall_result": "string or null - PASS/FAIL/SATISFACTORY/UNSATISFACTORY/Rating grade",
        "rating": "string or null - for EPC: A-G, for EICR: classification code",
        "score": "number or null - numeric score if applicable"
    },
    "findings": {
        "defects": ["array of strings - any defects or issues noted"],
        "warnings": ["array of strings - warnings or recommendations"],
        "observations": ["array of strings - general observations"]
    },
    "appliances_or_items": ["array of strings - appliances checked (gas) or circuits tested (electrical)"],
    "additional_info": {
        "property_type": "string or null",
        "floor_area_sqm": "number or null",
        "number_of_items_tested": "number or null"
    },
    "confidence_scores": {
        "document_type": 0.0 to 1.0,
        "certificate_number": 0.0 to 1.0,
        "issue_date": 0.0 to 1.0,
        "expiry_date": 0.0 to 1.0,
        "engineer_details": 0.0 to 1.0,
        "overall": 0.0 to 1.0
    },
    "extraction_notes": "string or null - any notes about extraction difficulties or uncertainties"
}

CRITICAL RULES:
1. ONLY extract information that is CLEARLY VISIBLE in the document
2. If a field cannot be determined with reasonable confidence, set it to null
3. Dates MUST be in YYYY-MM-DD format (convert from any format you see)
4. Be CONSERVATIVE - if unsure, use lower confidence scores
5. DO NOT make up or infer information that isn't explicitly stated
6. For Gas Safety: expiry is typically issue_date + 12 months
7. For EICR: check for "Next Inspection" field, NOT issue date
8. For EPC: Valid for 10 years from assessment date

Return ONLY the JSON object, no additional text or explanation."""


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
