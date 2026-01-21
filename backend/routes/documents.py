from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form, Depends, status, Body
from pydantic import BaseModel
from database import database
from middleware import client_route_guard, admin_route_guard
from models import Document, DocumentStatus, RequirementStatus, AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import os
import uuid
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


# Request models for apply extraction
class EngineerDetails(BaseModel):
    name: Optional[str] = None
    registration_number: Optional[str] = None
    company_name: Optional[str] = None


class ResultSummary(BaseModel):
    overall_result: Optional[str] = None


class ExtractionApplyRequest(BaseModel):
    confirmed_data: Optional[Dict[str, Any]] = None


# Document storage directory
DOCUMENT_STORAGE_PATH = Path("/app/data/documents")
DOCUMENT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

@router.post("/bulk-upload")
async def bulk_upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    property_id: str = Form(...),
):
    """Bulk upload multiple documents for a property.
    
    Documents will be auto-matched to requirements based on AI analysis.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Verify property belongs to client
        property_doc = await db.properties.find_one(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not property_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        # Get all requirements for this property
        requirements = await db.requirements.find(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        
        results = []
        
        for file in files:
            try:
                # Create unique filename
                file_extension = Path(file.filename).suffix
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                file_path = DOCUMENT_STORAGE_PATH / user["client_id"] / unique_filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Save file
                contents = await file.read()
                with open(file_path, "wb") as f:
                    f.write(contents)
                
                # Create document record (without requirement assignment initially)
                document = Document(
                    client_id=user["client_id"],
                    property_id=property_id,
                    requirement_id=None,  # Will be assigned after AI analysis
                    file_name=file.filename,
                    file_path=str(file_path),
                    file_size=len(contents),
                    mime_type=file.content_type or "application/octet-stream",
                    status=DocumentStatus.UPLOADED,
                    uploaded_by=user["portal_user_id"]
                )
                
                doc = document.model_dump()
                doc["uploaded_at"] = doc["uploaded_at"].isoformat()
                
                await db.documents.insert_one(doc)
                
                # Try AI analysis to auto-match requirement
                matched_requirement = None
                try:
                    from services.document_analysis import document_analysis_service
                    
                    analysis_result = await document_analysis_service.analyze_document(
                        file_path=str(file_path),
                        mime_type=file.content_type or "application/pdf",
                        document_id=document.document_id,
                        client_id=user["client_id"],
                        actor_id=user["portal_user_id"]
                    )
                    
                    if analysis_result["success"]:
                        doc_type = analysis_result["extracted_data"].get("document_type", "").lower()
                        
                        # Match to requirement based on document type
                        type_mapping = {
                            "gas safety": "gas_safety",
                            "gas safe": "gas_safety",
                            "cp12": "gas_safety",
                            "eicr": "eicr",
                            "electrical": "eicr",
                            "epc": "epc",
                            "energy performance": "epc",
                            "fire": "fire_alarm",
                            "legionella": "legionella",
                            "hmo": "hmo_license",
                            "pat": "pat_testing"
                        }
                        
                        for key, req_type in type_mapping.items():
                            if key in doc_type:
                                # Find matching requirement
                                for req in requirements:
                                    if req["requirement_type"] == req_type:
                                        matched_requirement = req["requirement_id"]
                                        
                                        # Update document with requirement
                                        await db.documents.update_one(
                                            {"document_id": document.document_id},
                                            {"$set": {"requirement_id": matched_requirement}}
                                        )
                                        
                                        # Update requirement due date
                                        await regenerate_requirement_due_date(
                                            matched_requirement, 
                                            user["client_id"]
                                        )
                                        break
                                break
                except Exception as e:
                    logger.warning(f"AI analysis failed for {file.filename}: {e}")
                
                results.append({
                    "filename": file.filename,
                    "document_id": document.document_id,
                    "status": "uploaded",
                    "matched_requirement": matched_requirement,
                    "ai_analyzed": matched_requirement is not None
                })
                
            except Exception as e:
                logger.error(f"Failed to upload {file.filename}: {e}")
                results.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": str(e)
                })
        
        # Audit log
        await create_audit_log(
            action=AuditAction.DOCUMENT_UPLOADED,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="documents_bulk",
            metadata={
                "property_id": property_id,
                "files_count": len(files),
                "successful": sum(1 for r in results if r["status"] == "uploaded"),
                "auto_matched": sum(1 for r in results if r.get("matched_requirement"))
            }
        )
        
        return {
            "message": f"Processed {len(files)} files",
            "results": results,
            "summary": {
                "total": len(files),
                "successful": sum(1 for r in results if r["status"] == "uploaded"),
                "failed": sum(1 for r in results if r["status"] == "failed"),
                "auto_matched": sum(1 for r in results if r.get("matched_requirement"))
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process bulk upload"
        )


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    property_id: str = Form(...),
    requirement_id: str = Form(...)
):
    """Upload a compliance document (client or admin)."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Verify property and requirement belong to client
        property_doc = await db.properties.find_one(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not property_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        requirement = await db.requirements.find_one(
            {"requirement_id": requirement_id, "client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requirement not found"
            )
        
        # Create unique filename
        file_extension = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = DOCUMENT_STORAGE_PATH / user["client_id"] / unique_filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Create document record
        document = Document(
            client_id=user["client_id"],
            property_id=property_id,
            requirement_id=requirement_id,
            file_name=file.filename,
            file_path=str(file_path),
            file_size=len(contents),
            mime_type=file.content_type or "application/octet-stream",
            status=DocumentStatus.UPLOADED,
            uploaded_by=user["portal_user_id"]
        )
        
        doc = document.model_dump()
        doc["uploaded_at"] = doc["uploaded_at"].isoformat()
        
        await db.documents.insert_one(doc)
        
        # Update requirement status and regenerate due date
        await regenerate_requirement_due_date(requirement_id, user["client_id"])
        
        # Audit log
        await create_audit_log(
            action=AuditAction.DOCUMENT_UPLOADED,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="document",
            resource_id=document.document_id,
            metadata={
                "filename": file.filename,
                "requirement_id": requirement_id,
                "property_id": property_id
            }
        )
        
        logger.info(f"Document uploaded: {document.document_id}")
        
        return {
            "message": "Document uploaded successfully",
            "document_id": document.document_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )

@router.post("/admin/upload")
async def admin_upload_document(
    request: Request,
    file: UploadFile = File(...),
    client_id: str = Form(...),
    property_id: str = Form(...),
    requirement_id: str = Form(...)
):
    """Admin uploads document on behalf of client."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Verify property and requirement belong to client
        property_doc = await db.properties.find_one(
            {"property_id": property_id, "client_id": client_id},
            {"_id": 0}
        )
        
        if not property_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        requirement = await db.requirements.find_one(
            {"requirement_id": requirement_id, "client_id": client_id},
            {"_id": 0}
        )
        
        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requirement not found"
            )
        
        # Create unique filename
        file_extension = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = DOCUMENT_STORAGE_PATH / client_id / unique_filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Create document record
        document = Document(
            client_id=client_id,
            property_id=property_id,
            requirement_id=requirement_id,
            file_name=file.filename,
            file_path=str(file_path),
            file_size=len(contents),
            mime_type=file.content_type or "application/octet-stream",
            status=DocumentStatus.UPLOADED,
            uploaded_by=user["portal_user_id"],
            manual_review_flag=False
        )
        
        doc = document.model_dump()
        doc["uploaded_at"] = doc["uploaded_at"].isoformat()
        
        await db.documents.insert_one(doc)
        
        # Update requirement status and regenerate due date
        await regenerate_requirement_due_date(requirement_id, client_id)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            resource_type="document",
            resource_id=document.document_id,
            metadata={
                "action": "admin_document_upload",
                "filename": file.filename,
                "requirement_id": requirement_id,
                "property_id": property_id
            }
        )
        
        logger.info(f"Admin uploaded document for client {client_id}: {document.document_id}")
        
        return {
            "message": "Document uploaded successfully by admin",
            "document_id": document.document_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin document upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )

@router.post("/verify/{document_id}")
async def verify_document(request: Request, document_id: str):
    """Admin verifies a document."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        document = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        old_status = document["status"]
        
        # Update document status
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"status": DocumentStatus.VERIFIED.value}}
        )
        
        # Update requirement status to COMPLIANT
        await db.requirements.update_one(
            {"requirement_id": document["requirement_id"]},
            {"$set": {"status": RequirementStatus.COMPLIANT.value}}
        )
        
        # Recompute property compliance
        from services.provisioning import provisioning_service
        await provisioning_service._update_property_compliance(document["property_id"])
        
        # Audit log
        await create_audit_log(
            action=AuditAction.DOCUMENT_VERIFIED,
            actor_id=user["portal_user_id"],
            client_id=document["client_id"],
            resource_type="document",
            resource_id=document_id,
            before_state={"status": old_status},
            after_state={"status": DocumentStatus.VERIFIED.value}
        )
        
        return {"message": "Document verified"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify document"
        )

@router.post("/reject/{document_id}")
async def reject_document(request: Request, document_id: str, reason: str = Form(...)):
    """Admin rejects a document."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        document = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        old_status = document["status"]
        
        # Update document status
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"status": DocumentStatus.REJECTED.value}}
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.DOCUMENT_REJECTED,
            actor_id=user["portal_user_id"],
            client_id=document["client_id"],
            resource_type="document",
            resource_id=document_id,
            before_state={"status": old_status},
            after_state={"status": DocumentStatus.REJECTED.value},
            metadata={"reason": reason}
        )
        
        return {"message": "Document rejected"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document rejection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject document"
        )

async def regenerate_requirement_due_date(requirement_id: str, client_id: str):
    """Regenerate requirement due date after document upload."""
    db = database.get_db()
    
    requirement = await db.requirements.find_one(
        {"requirement_id": requirement_id},
        {"_id": 0}
    )
    
    if requirement:
        # Calculate new due date based on frequency
        new_due_date = datetime.now(timezone.utc) + timedelta(days=requirement["frequency_days"])
        
        await db.requirements.update_one(
            {"requirement_id": requirement_id},
            {
                "$set": {
                    "status": RequirementStatus.COMPLIANT.value,
                    "due_date": new_due_date.isoformat()
                }
            }
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.REQUIREMENTS_EVALUATED,
            client_id=client_id,
            resource_type="requirement",
            resource_id=requirement_id,
            metadata={
                "action": "regenerate_due_date",
                "new_due_date": new_due_date.isoformat()
            }
        )


@router.post("/analyze/{document_id}")
async def analyze_document_ai(request: Request, document_id: str):
    """Analyze a document using AI to extract metadata (admin or client who owns it)."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Get document
        document = await db.documents.find_one(
            {"document_id": document_id},
            {"_id": 0}
        )
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Verify ownership (client can only analyze their own documents)
        if user.get("role") != "ROLE_ADMIN" and document["client_id"] != user["client_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to analyze this document"
            )
        
        # Check if already analyzed
        if document.get("ai_extraction", {}).get("status") == "completed":
            return {
                "message": "Document already analyzed",
                "extraction": document["ai_extraction"]
            }
        
        # Perform AI analysis
        from services.document_analysis import document_analysis_service
        
        result = await document_analysis_service.analyze_document(
            file_path=document["file_path"],
            mime_type=document.get("mime_type", "application/pdf"),
            document_id=document_id,
            client_id=document["client_id"],
            actor_id=user["portal_user_id"]
        )
        
        if result["success"]:
            return {
                "message": "Document analyzed successfully",
                "extraction": {
                    "status": "completed",
                    "data": result["extracted_data"]
                }
            }
        else:
            return {
                "message": "Document analysis failed",
                "error": result["error"],
                "extraction": None
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document AI analysis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze document"
        )


@router.get("/{document_id}/extraction")
async def get_document_extraction(request: Request, document_id: str):
    """Get AI extraction results for a document."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        document = await db.documents.find_one(
            {"document_id": document_id},
            {"_id": 0}
        )
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Verify ownership
        if user.get("role") != "ROLE_ADMIN" and document["client_id"] != user["client_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this document"
            )
        
        extraction = document.get("ai_extraction")
        
        if not extraction:
            return {
                "has_extraction": False,
                "extraction": None
            }
        
        return {
            "has_extraction": True,
            "extraction": extraction
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get extraction error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get extraction"
        )


@router.get("")
async def list_documents(request: Request, property_id: str = None, requirement_id: str = None):
    """List documents for the client."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        query = {"client_id": user["client_id"]}
        if property_id:
            query["property_id"] = property_id
        if requirement_id:
            query["requirement_id"] = requirement_id
        
        documents = await db.documents.find(
            query,
            {"_id": 0, "file_path": 0}  # Don't expose file path
        ).sort("uploaded_at", -1).to_list(100)
        
        return {
            "documents": documents,
            "total": len(documents)
        }
    
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents"
        )



@router.post("/{document_id}/apply-extraction")
async def apply_ai_extraction(
    request: Request, 
    document_id: str,
    body: ExtractionApplyRequest = Body(default=None)
):
    """Apply reviewed AI-extracted data to the associated requirement.
    
    This endpoint allows users to:
    1. Review AI-extracted data
    2. Modify any incorrect values
    3. Apply the data to update the requirement's due date
    
    IMPORTANT: This does NOT auto-mark the requirement as compliant.
    The deterministic compliance engine evaluates status based on dates only.
    
    Args:
        document_id: The document whose extraction to apply
        body: Request body containing optional confirmed_data (if user corrected AI extraction)
    
    Returns:
        Success message with changes applied, or descriptive error.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    # Extract confirmed_data from body
    confirmed_data = body.confirmed_data if body else None
    
    try:
        # Get document
        document = await db.documents.find_one(
            {"document_id": document_id},
            {"_id": 0}
        )
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        # Verify ownership
        if user.get("role") != "ROLE_ADMIN" and document["client_id"] != user["client_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this document. You can only apply extraction to your own documents."
            )
        
        # Get AI extraction
        extraction = document.get("ai_extraction", {})
        extraction_status = extraction.get("status")
        
        if extraction_status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document has not been analyzed yet. Current extraction status: {extraction_status or 'none'}"
            )
        
        # Use confirmed_data if provided, otherwise use AI extraction
        data = confirmed_data if confirmed_data else extraction.get("data", {})
        
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No extraction data available to apply. Please analyze the document first."
            )
        
        # Validate we have a requirement to update
        requirement_id = document.get("requirement_id")
        if not requirement_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document is not linked to a requirement. Please link the document to a requirement before applying extraction."
            )
        
        # Get requirement
        requirement = await db.requirements.find_one(
            {"requirement_id": requirement_id},
            {"_id": 0}
        )
        
        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Associated requirement not found: {requirement_id}"
            )
        
        # Capture before state for audit
        before_state = {
            "due_date": requirement.get("due_date"),
            "status": requirement.get("status")
        }
        
        # Prepare update data
        update_fields = {}
        changes_made = []
        
        # Apply expiry date if provided (this affects due_date)
        expiry_date = data.get("expiry_date")
        if expiry_date:
            try:
                # Parse the date - handle various formats
                if isinstance(expiry_date, str):
                    # Remove timezone info for simpler parsing
                    clean_date = expiry_date.replace('Z', '+00:00').split('T')[0] if 'T' in expiry_date else expiry_date
                    try:
                        expiry_dt = datetime.fromisoformat(expiry_date.replace('Z', '+00:00'))
                    except ValueError:
                        # Try parsing just the date part
                        expiry_dt = datetime.strptime(clean_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                else:
                    expiry_dt = expiry_date
                
                update_fields["due_date"] = expiry_dt.isoformat()
                changes_made.append(f"Due date set to {expiry_dt.strftime('%Y-%m-%d')}")
                
                # Also update status based on date if needed
                now = datetime.now(timezone.utc)
                if expiry_dt < now:
                    update_fields["status"] = "OVERDUE"
                    changes_made.append("Status set to OVERDUE (past due date)")
                elif expiry_dt < now + timedelta(days=30):
                    update_fields["status"] = "EXPIRING_SOON"
                    changes_made.append("Status set to EXPIRING_SOON (expires within 30 days)")
                else:
                    update_fields["status"] = "COMPLIANT"
                    changes_made.append("Status set to COMPLIANT (valid certificate)")
                    
            except Exception as date_err:
                logger.warning(f"Failed to parse expiry date '{expiry_date}': {date_err}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid expiry date format: {expiry_date}. Expected ISO format (YYYY-MM-DD)."
                )
        else:
            logger.info(f"No expiry_date in extraction data for document {document_id}")
        
        # Store extracted data in document for reference
        document_update = {
            "ai_extraction.review_status": "approved",
            "ai_extraction.reviewed_at": datetime.now(timezone.utc).isoformat(),
            "ai_extraction.reviewed_by": user["portal_user_id"],
            "ai_extraction.applied_data": data,
            "ai_extracted_data": data,  # Legacy field for compatibility
            "status": DocumentStatus.VERIFIED.value  # Mark document as verified after applying
        }
        
        # Add certificate number if available
        cert_number = data.get("certificate_number")
        if cert_number:
            document_update["certificate_number"] = cert_number
            changes_made.append(f"Certificate number: {cert_number}")
        
        # Add confidence score if available
        confidence = data.get("confidence_scores", {}).get("overall") if isinstance(data.get("confidence_scores"), dict) else data.get("confidence")
        if confidence:
            document_update["confidence_score"] = confidence
        
        # Update document
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": document_update}
        )
        
        # Update requirement if we have changes
        after_state = before_state.copy()
        if update_fields:
            update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db.requirements.update_one(
                {"requirement_id": requirement_id},
                {"$set": update_fields}
            )
            after_state["due_date"] = update_fields.get("due_date", after_state["due_date"])
            after_state["status"] = update_fields.get("status", after_state["status"])
        
        # Create specific audit action for extraction applied
        await create_audit_log(
            action=AuditAction.DOCUMENT_AI_ANALYZED,
            actor_id=user["portal_user_id"],
            client_id=document["client_id"],
            resource_type="document",
            resource_id=document_id,
            before_state=before_state,
            after_state=after_state,
            metadata={
                "action": "extraction_applied",
                "requirement_id": requirement_id,
                "changes_made": changes_made,
                "expiry_date_set": expiry_date,
                "certificate_number": cert_number,
                "engineer_name": data.get("engineer_details", {}).get("name") if isinstance(data.get("engineer_details"), dict) else data.get("engineer_name"),
                "user_confirmed": confirmed_data is not None,
                "document_status": "VERIFIED"
            }
        )
        
        logger.info(f"AI extraction applied for document {document_id}: {changes_made}")
        
        return {
            "message": "Extraction applied successfully",
            "document_id": document_id,
            "requirement_id": requirement_id,
            "changes_applied": changes_made,
            "requirement_status": after_state.get("status"),
            "due_date": after_state.get("due_date"),
            "note": "Requirement status has been updated based on the certificate expiry date."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Apply extraction error for document {document_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply extraction: {str(e)}"
        )


@router.post("/{document_id}/reject-extraction")
async def reject_ai_extraction(request: Request, document_id: str, reason: str = None):
    """Mark AI extraction as rejected (user will enter data manually)."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        document = await db.documents.find_one(
            {"document_id": document_id},
            {"_id": 0}
        )
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Verify ownership
        if user.get("role") != "ROLE_ADMIN" and document["client_id"] != user["client_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )
        
        # Update extraction status
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {
                "ai_extraction.review_status": "rejected",
                "ai_extraction.reviewed_at": datetime.now(timezone.utc).isoformat(),
                "ai_extraction.reviewed_by": user["portal_user_id"],
                "ai_extraction.rejection_reason": reason
            }}
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.DOCUMENT_AI_ANALYZED,
            actor_id=user["portal_user_id"],
            client_id=document["client_id"],
            resource_type="document",
            resource_id=document_id,
            metadata={
                "action": "extraction_rejected",
                "reason": reason
            }
        )
        
        return {"message": "Extraction marked as rejected"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reject extraction error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject extraction"
        )


@router.get("/{document_id}/details")
async def get_document_details(request: Request, document_id: str):
    """Get full document details including AI extraction and requirement info."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        document = await db.documents.find_one(
            {"document_id": document_id},
            {"_id": 0, "file_path": 0}
        )
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Verify ownership
        if user.get("role") != "ROLE_ADMIN" and document["client_id"] != user["client_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )
        
        # Get associated requirement
        requirement = None
        if document.get("requirement_id"):
            requirement = await db.requirements.find_one(
                {"requirement_id": document["requirement_id"]},
                {"_id": 0}
            )
        
        # Get property info
        property_doc = None
        if document.get("property_id"):
            property_doc = await db.properties.find_one(
                {"property_id": document["property_id"]},
                {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1}
            )
        
        return {
            "document": document,
            "requirement": requirement,
            "property": property_doc
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document details error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document details"
        )
