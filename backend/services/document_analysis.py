"""AI Document Analysis Service - Extracts metadata from compliance documents.

IMPORTANT: This service is ASSISTIVE ONLY. Extracted data must be reviewed by users
before being applied. AI CANNOT mark a requirement as compliant - the deterministic
compliance engine remains the final authority.

Requires emergentintegrations for LLM; if not installed, analyze_document returns
success=False with error "AI extraction unavailable".
"""
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
    """Enhanced AI document analysis service with document-type-specific extraction.
    
    IMPORTANT: This service is ASSISTIVE ONLY. Extracted data must be reviewed
    before being applied to requirements. AI cannot mark requirements compliant.
    """
    
    def __init__(self):
        self.api_key = os.getenv("EMERGENT_LLM_KEY", "sk-emergent-f9533226f52E25cF35")
        logger.info("Document Analysis Service initialized (Enhanced)")
    
    def _detect_document_type_hint(self, filename: str) -> str:
        """Detect document type from filename to use appropriate prompt."""
        filename_lower = filename.lower()
        
        if any(kw in filename_lower for kw in ['gas', 'cp12', 'cp17', 'lgsr']):
            return "gas_safety"
        elif any(kw in filename_lower for kw in ['eicr', 'electrical', 'niceic', 'napit']):
            return "eicr"
        elif any(kw in filename_lower for kw in ['epc', 'energy', 'performance']):
            return "epc"
        
        return "default"
    
    def _get_analysis_prompt(self, doc_type_hint: str) -> str:
        """Get the appropriate analysis prompt based on document type hint."""
        type_prompt = DOCUMENT_TYPE_PROMPTS.get(doc_type_hint, DOCUMENT_TYPE_PROMPTS["default"])
        return f"{type_prompt}\n\n{BASE_EXTRACTION_PROMPT}"
    
    async def analyze_document(
        self,
        file_path: str,
        mime_type: str,
        document_id: str,
        client_id: str,
        actor_id: Optional[str] = None,
        doc_type_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a document using AI to extract metadata with enhanced field extraction.
        
        Args:
            file_path: Path to the document file
            mime_type: MIME type of the file
            document_id: ID of the document record
            client_id: ID of the client
            actor_id: ID of the user who triggered the analysis
            doc_type_hint: Optional hint about document type for better extraction
            
        Returns:
            Dictionary with extracted metadata and confidence scores
            
        Note: Extracted data is ASSISTIVE ONLY and must be reviewed by users
              before being applied. AI cannot auto-mark compliance.
        """
        db = database.get_db()
        
        try:
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
            except ImportError:
                logger.warning("emergentintegrations not available; AI document extraction disabled")
                return {
                    "success": False,
                    "error": "AI extraction unavailable",
                    "extracted_data": None,
                    "requires_review": True,
                }
            # Verify file exists
            if not os.path.exists(file_path):
                logger.error(f"Document file not found: {file_path}")
                return {
                    "success": False,
                    "error": "Document file not found",
                    "extracted_data": None,
                    "requires_review": True
                }
            
            # Detect document type from filename if not provided
            if not doc_type_hint:
                doc_type_hint = self._detect_document_type_hint(os.path.basename(file_path))
            
            # Get appropriate prompt for document type
            analysis_prompt = self._get_analysis_prompt(doc_type_hint)
            
            # Initialize chat with Gemini (required for file attachments)
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"doc-analysis-{document_id}",
                system_message=analysis_prompt
            ).with_model("gemini", "gemini-2.5-flash")
            
            # Create file content object
            file_content = FileContentWithMimeType(
                file_path=file_path,
                mime_type=mime_type
            )
            
            # Send message with file attachment
            user_message = UserMessage(
                text="Analyze this compliance document and extract all relevant metadata. Focus on the priority fields: expiry date, issue date, certificate number, and engineer/assessor details. Return only the JSON object.",
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
                
                # Normalize legacy format to enhanced format if needed
                extracted_data = self._normalize_extraction_data(extracted_data)
                
                # Calculate overall confidence based on critical field extraction
                extraction_quality = self._assess_extraction_quality(extracted_data)
                
                # Store extraction result in document record
                await db.documents.update_one(
                    {"document_id": document_id},
                    {"$set": {
                        "ai_extraction": {
                            "extracted_at": datetime.now(timezone.utc).isoformat(),
                            "data": extracted_data,
                            "status": "completed",
                            "doc_type_hint": doc_type_hint,
                            "extraction_quality": extraction_quality,
                            "requires_review": True,  # ALWAYS requires review
                            "review_status": "pending"
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
                        "doc_type_hint": doc_type_hint,
                        "overall_confidence": extracted_data.get("confidence_scores", {}).get("overall"),
                        "extraction_quality": extraction_quality,
                        "has_expiry_date": extracted_data.get("expiry_date") is not None,
                        "has_engineer_details": extracted_data.get("engineer_details", {}).get("name") is not None,
                        "requires_review": True
                    }
                )
                
                logger.info(f"Document analyzed successfully: {document_id} (quality: {extraction_quality})")
                
                return {
                    "success": True,
                    "extracted_data": extracted_data,
                    "extraction_quality": extraction_quality,
                    "requires_review": True,
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
                    "extracted_data": None,
                    "requires_review": True
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
                "extracted_data": None,
                "requires_review": True
            }
    
    def _normalize_extraction_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize extracted data to ensure consistent structure."""
        # Handle legacy format fields
        if "engineer_name" in data and "engineer_details" not in data:
            data["engineer_details"] = {
                "name": data.pop("engineer_name", None),
                "registration_number": data.pop("engineer_registration", None),
                "registration_scheme": None,
                "company_name": data.pop("company_name", None)
            }
        
        if "result" in data and "result_summary" not in data:
            data["result_summary"] = {
                "overall_result": data.pop("result", None),
                "rating": data.pop("rating", None),
                "score": None
            }
        
        if "key_findings" in data and "findings" not in data:
            data["findings"] = {
                "defects": [],
                "warnings": data.pop("key_findings", []),
                "observations": []
            }
        
        # Ensure all required fields exist
        defaults = {
            "document_type": None,
            "document_subtype": None,
            "certificate_number": None,
            "issue_date": None,
            "expiry_date": None,
            "property_address": None,
            "engineer_details": {"name": None, "registration_number": None, "registration_scheme": None, "company_name": None},
            "result_summary": {"overall_result": None, "rating": None, "score": None},
            "findings": {"defects": [], "warnings": [], "observations": []},
            "appliances_or_items": [],
            "additional_info": {"property_type": None, "floor_area_sqm": None, "number_of_items_tested": None},
            "confidence_scores": {"document_type": 0, "certificate_number": 0, "issue_date": 0, "expiry_date": 0, "engineer_details": 0, "overall": 0},
            "extraction_notes": None
        }
        
        for key, default_val in defaults.items():
            if key not in data:
                data[key] = default_val
        
        return data
    
    def _assess_extraction_quality(self, data: Dict[str, Any]) -> str:
        """Assess the quality of extraction based on critical fields."""
        confidence = data.get("confidence_scores", {})
        
        # Critical fields for compliance
        has_expiry = data.get("expiry_date") is not None
        has_issue_date = data.get("issue_date") is not None
        has_cert_number = data.get("certificate_number") is not None
        has_engineer = data.get("engineer_details", {}).get("name") is not None
        has_doc_type = data.get("document_type") is not None
        
        overall_conf = confidence.get("overall", 0)
        
        # Calculate quality score
        field_score = sum([has_expiry * 2, has_issue_date, has_cert_number, has_engineer, has_doc_type]) / 6
        
        if overall_conf >= 0.8 and field_score >= 0.8:
            return "high"
        elif overall_conf >= 0.5 and field_score >= 0.5:
            return "medium"
        else:
            return "low"
    
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
