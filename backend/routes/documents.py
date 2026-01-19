from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form, Depends, status
from database import database
from middleware import client_route_guard, admin_route_guard
from models import Document, DocumentStatus, RequirementStatus, AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timedelta, timezone
import os
import uuid
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

# Document storage directory
DOCUMENT_STORAGE_PATH = Path("/app/data/documents")
DOCUMENT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

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
