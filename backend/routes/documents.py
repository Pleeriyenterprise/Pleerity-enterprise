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


def _normalize_and_parse_date(date_value) -> datetime:
    """Enterprise-safe date normalization and parsing.
    
    Handles:
    - ISO format: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DDTHH:MM:SSZ
    - UK format: DD/MM/YYYY
    - Unicode dash variants (en-dash, em-dash, figure dash, etc.)
    - Hidden whitespace characters
    - Already parsed datetime objects
    
    Returns:
        datetime object with UTC timezone
        
    Raises:
        ValueError if date cannot be parsed
    """
    import re
    import unicodedata
    
    # Handle datetime objects directly
    if isinstance(date_value, datetime):
        if date_value.tzinfo is None:
            return date_value.replace(tzinfo=timezone.utc)
        return date_value
    
    # Convert to string if needed
    date_str = str(date_value) if date_value else ""
    
    # Debug logging for troubleshooting
    logger.debug(f"Date normalization input: repr={repr(date_str)}, len={len(date_str)}")
    logger.debug(f"Date codepoints: {[f'U+{ord(c):04X}' for c in date_str]}")
    
    # Step 1: Strip whitespace and normalize unicode
    date_str = date_str.strip()
    date_str = unicodedata.normalize('NFKC', date_str)
    
    # Step 2: Replace unicode dash variants with ASCII hyphen
    # Common unicode dashes: en-dash (–), em-dash (—), minus (−), figure dash (‒)
    unicode_dashes = [
        '\u2010',  # Hyphen
        '\u2011',  # Non-breaking hyphen
        '\u2012',  # Figure dash
        '\u2013',  # En dash
        '\u2014',  # Em dash
        '\u2015',  # Horizontal bar
        '\u2212',  # Minus sign
        '\uFE58',  # Small em dash
        '\uFE63',  # Small hyphen-minus
        '\uFF0D',  # Fullwidth hyphen-minus
    ]
    for dash in unicode_dashes:
        date_str = date_str.replace(dash, '-')
    
    # Step 3: Remove any invisible/control characters
    date_str = re.sub(r'[\x00-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202f\u205f-\u206f]', '', date_str)
    
    # Step 4: Handle ISO format with time component
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    # Step 5: Remove timezone suffixes
    date_str = date_str.replace('Z', '')
    date_str = re.sub(r'[+-]\d{2}:?\d{2}$', '', date_str)
    
    # Step 6: Try parsing different formats
    date_str = date_str.strip()
    
    # Try ISO format: YYYY-MM-DD
    iso_match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', date_str)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        return datetime(year, month, day, tzinfo=timezone.utc)
    
    # Try UK format: DD/MM/YYYY
    uk_match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
    if uk_match:
        day, month, year = map(int, uk_match.groups())
        return datetime(year, month, day, tzinfo=timezone.utc)
    
    # Try UK format with dashes: DD-MM-YYYY
    uk_dash_match = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', date_str)
    if uk_dash_match:
        day, month, year = map(int, uk_dash_match.groups())
        return datetime(year, month, day, tzinfo=timezone.utc)
    
    # Try ISO format with slashes: YYYY/MM/DD
    iso_slash_match = re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})$', date_str)
    if iso_slash_match:
        year, month, day = map(int, iso_slash_match.groups())
        return datetime(year, month, day, tzinfo=timezone.utc)
    
    # Last resort: try standard datetime parsing
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d %b %Y', '%d %B %Y']:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    
    # If all else fails, raise with details
    raise ValueError(
        f"Cannot parse date: '{date_str}' (repr={repr(date_str)}, "
        f"codepoints={[f'U+{ord(c):04X}' for c in date_str]})"
    )


# Request models for apply extraction
class EngineerDetails(BaseModel):
    name: Optional[str] = None
    registration_number: Optional[str] = None
    company_name: Optional[str] = None


class ResultSummary(BaseModel):
    overall_result: Optional[str] = None


class ExtractionApplyRequest(BaseModel):
    confirmed_data: Optional[Dict[str, Any]] = None


# Document storage directory (configurable via DATA_DIR or DOCUMENT_STORAGE_PATH)
DATA_DIR = os.getenv("DATA_DIR", "/tmp")
DOCUMENT_STORAGE_PATH = Path(os.environ.get("DOCUMENT_STORAGE_PATH", str(Path(DATA_DIR) / "data" / "documents")))
DOCUMENT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

@router.post("/bulk-upload")
async def bulk_upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    property_id: str = Form(...),
):
    """Bulk upload multiple documents for a property.
    
    Gated: PORTFOLIO and PROFESSIONAL only (zip_upload feature).
    Documents will be auto-matched to requirements based on AI analysis.
    """
    # Feature gating enforcement
    from middleware.feature_gating import require_feature
    gating_check = require_feature("zip_upload")
    await gating_check(lambda r: None)(request)
    
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


@router.post("/zip-upload")
async def upload_zip_archive(
    request: Request,
    file: UploadFile = File(...),
    property_id: str = Form(...),
):
    """Upload a ZIP archive containing multiple documents.
    
    The ZIP file will be extracted and each document will be processed individually.
    Requires Portfolio plan (PLAN_6_15) or higher.
    
    Supported file types inside ZIP:
    - PDF (.pdf)
    - Images (.jpg, .jpeg, .png)
    - Word documents (.doc, .docx)
    """
    import zipfile
    import tempfile
    import shutil
    
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Plan gating: zip_upload requires PLAN_2_PORTFOLIO (plan_registry)
        from services.plan_registry import plan_registry

        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            user["client_id"],
            "zip_upload"
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                    "message": error_msg,
                    "feature": "zip_upload",
                    "upgrade_required": True,
                    **(error_details or {})
                }
            )
        
        # Verify file is a ZIP
        if not file.filename.lower().endswith('.zip'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a ZIP archive (.zip)"
            )
        
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
        
        # Save ZIP to temp location
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, file.filename)
        
        try:
            contents = await file.read()
            
            # Check file size (max 100MB)
            if len(contents) > 100 * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ZIP file too large. Maximum size is 100MB."
                )
            
            with open(zip_path, "wb") as f:
                f.write(contents)
            
            # Extract ZIP
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            
            # Validate ZIP file
            if not zipfile.is_zipfile(zip_path):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid ZIP file"
                )
            
            results = []
            supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx'}
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Check for zip bomb (max 1000 files, max 500MB uncompressed)
                total_size = sum(info.file_size for info in zip_ref.infolist())
                if total_size > 500 * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="ZIP contents too large. Maximum uncompressed size is 500MB."
                    )
                
                if len(zip_ref.namelist()) > 1000:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="ZIP contains too many files. Maximum is 1000 files."
                    )
                
                # Extract all files
                zip_ref.extractall(extract_dir)
            
            # Process each extracted file
            for root, dirs, files_list in os.walk(extract_dir):
                for filename in files_list:
                    # Skip hidden files and macOS metadata
                    if filename.startswith('.') or filename.startswith('__MACOSX'):
                        continue
                    
                    file_path = os.path.join(root, filename)
                    file_ext = os.path.splitext(filename)[1].lower()
                    
                    # Skip unsupported file types
                    if file_ext not in supported_extensions:
                        results.append({
                            "filename": filename,
                            "status": "skipped",
                            "reason": f"Unsupported file type: {file_ext}"
                        })
                        continue
                    
                    try:
                        # Create unique filename
                        unique_filename = f"{uuid.uuid4()}{file_ext}"
                        dest_path = DOCUMENT_STORAGE_PATH / user["client_id"] / unique_filename
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Copy file to document storage
                        shutil.copy2(file_path, dest_path)
                        
                        # Get file size
                        file_size = os.path.getsize(file_path)
                        
                        # Determine MIME type
                        mime_types = {
                            '.pdf': 'application/pdf',
                            '.jpg': 'image/jpeg',
                            '.jpeg': 'image/jpeg',
                            '.png': 'image/png',
                            '.doc': 'application/msword',
                            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                        }
                        mime_type = mime_types.get(file_ext, 'application/octet-stream')
                        
                        # Create document record
                        document = Document(
                            client_id=user["client_id"],
                            property_id=property_id,
                            requirement_id=None,
                            file_name=filename,
                            file_path=str(dest_path),
                            file_size=file_size,
                            mime_type=mime_type,
                            status=DocumentStatus.UPLOADED,
                            uploaded_by=user["portal_user_id"]
                        )
                        
                        doc = document.model_dump()
                        doc["uploaded_at"] = doc["uploaded_at"].isoformat()
                        
                        await db.documents.insert_one(doc)
                        
                        # Try AI analysis for auto-matching
                        matched_requirement = None
                        try:
                            from services.document_analysis import document_analysis_service
                            
                            analysis_result = await document_analysis_service.analyze_document(
                                file_path=str(dest_path),
                                mime_type=mime_type,
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
                                        for req in requirements:
                                            if req["requirement_type"] == req_type:
                                                matched_requirement = req["requirement_id"]
                                                
                                                await db.documents.update_one(
                                                    {"document_id": document.document_id},
                                                    {"$set": {"requirement_id": matched_requirement}}
                                                )
                                                
                                                await regenerate_requirement_due_date(
                                                    matched_requirement, 
                                                    user["client_id"]
                                                )
                                                break
                                        break
                        except Exception as e:
                            logger.warning(f"AI analysis failed for {filename}: {e}")
                        
                        results.append({
                            "filename": filename,
                            "document_id": document.document_id,
                            "status": "uploaded",
                            "matched_requirement": matched_requirement,
                            "ai_analyzed": matched_requirement is not None
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to process {filename}: {e}")
                        results.append({
                            "filename": filename,
                            "status": "failed",
                            "error": str(e)
                        })
            
            # Audit log
            await create_audit_log(
                action=AuditAction.DOCUMENT_UPLOADED,
                actor_id=user["portal_user_id"],
                client_id=user["client_id"],
                resource_type="zip_upload",
                metadata={
                    "property_id": property_id,
                    "zip_filename": file.filename,
                    "files_extracted": len(results),
                    "successful": sum(1 for r in results if r.get("status") == "uploaded"),
                    "auto_matched": sum(1 for r in results if r.get("matched_requirement")),
                    "skipped": sum(1 for r in results if r.get("status") == "skipped")
                }
            )
            
            return {
                "message": f"Processed ZIP archive: {file.filename}",
                "results": results,
                "summary": {
                    "total_extracted": len(results),
                    "successful": sum(1 for r in results if r.get("status") == "uploaded"),
                    "failed": sum(1 for r in results if r.get("status") == "failed"),
                    "skipped": sum(1 for r in results if r.get("status") == "skipped"),
                    "auto_matched": sum(1 for r in results if r.get("matched_requirement"))
                }
            }
            
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ZIP upload error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process ZIP upload: {str(e)}"
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
        from services.provisioning import provisioning_service
        await provisioning_service._update_property_compliance(property_id)
        
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
        from services.provisioning import provisioning_service
        await provisioning_service._update_property_compliance(property_id)
        
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
        
        # Recompute property compliance (skip for client-level docs with no property_id)
        if document.get("property_id"):
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
        
        # Enablement event
        try:
            from services.enablement_service import emit_enablement_event
            from models.enablement import EnablementEventType
            
            # Get property address for context (client-level docs may have property_id None)
            property_id = document.get("property_id")
            property_doc = await db.properties.find_one(
                {"property_id": property_id},
                {"_id": 0, "address": 1}
            ) if property_id else None
            property_address = property_doc.get("address", {}).get("line1", "") if property_doc else ""

            await emit_enablement_event(
                event_type=EnablementEventType.DOCUMENT_VERIFIED,
                client_id=document["client_id"],
                document_id=document_id,
                property_id=property_id,
                context_payload={
                    "document_name": document.get("document_name", document.get("requirement_name", "Document")),
                    "property_address": property_address,
                    "expiry_date": document.get("expiry_date", "N/A")
                }
            )
        except Exception as enable_err:
            logger.warning(f"Failed to emit enablement event: {enable_err}")
        
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
        
        # If this was the only verified doc for the requirement, revert requirement and sync property
        if document.get("requirement_id"):
            await _revert_requirement_if_no_verified_docs(
                db, document["requirement_id"], document.get("property_id")
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


@router.delete("/{document_id}")
async def delete_document(request: Request, document_id: str):
    """Client deletes own document. Requirement reverted to PENDING if no other VERIFIED doc; property compliance synced."""
    user = await client_route_guard(request)
    db = database.get_db()
    try:
        document = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if document["client_id"] != user["client_id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this document")
        requirement_id = document.get("requirement_id")
        property_id = document.get("property_id")
        was_verified = document.get("status") == DocumentStatus.VERIFIED.value
        await db.documents.delete_one({"document_id": document_id})
        if was_verified and requirement_id:
            await _revert_requirement_if_no_verified_docs(db, requirement_id, property_id)
        try:
            file_path = Path(document.get("file_path", ""))
            if file_path.is_file():
                file_path.unlink(missing_ok=True)
        except Exception as file_err:
            logger.warning(f"Could not remove file for document {document_id}: {file_err}")
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="document",
            resource_id=document_id,
            metadata={"action": "document_deleted"}
        )
        return {"message": "Document deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document delete error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete document")


@router.delete("/admin/{document_id}")
async def admin_delete_document(request: Request, document_id: str):
    """Admin deletes a document on behalf of any client. Requirement reverted if no other VERIFIED doc; property compliance synced."""
    user = await admin_route_guard(request)
    db = database.get_db()
    try:
        document = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        requirement_id = document.get("requirement_id")
        property_id = document.get("property_id")
        was_verified = document.get("status") == DocumentStatus.VERIFIED.value
        client_id = document["client_id"]
        await db.documents.delete_one({"document_id": document_id})
        if was_verified and requirement_id:
            await _revert_requirement_if_no_verified_docs(db, requirement_id, property_id)
        try:
            file_path = Path(document.get("file_path", ""))
            if file_path.is_file():
                file_path.unlink(missing_ok=True)
        except Exception as file_err:
            logger.warning(f"Could not remove file for document {document_id}: {file_err}")
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            resource_type="document",
            resource_id=document_id,
            metadata={"action": "admin_document_deleted"}
        )
        return {"message": "Document deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin document delete error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete document")


async def _revert_requirement_if_no_verified_docs(db, requirement_id: str, property_id: Optional[str]) -> None:
    """If no VERIFIED document remains for this requirement, set requirement to PENDING and sync property compliance."""
    remaining = await db.documents.count_documents(
        {"requirement_id": requirement_id, "status": DocumentStatus.VERIFIED.value}
    )
    if remaining > 0:
        return
    await db.requirements.update_one(
        {"requirement_id": requirement_id},
        {"$set": {"status": RequirementStatus.PENDING.value}}
    )
    if property_id:
        from services.provisioning import provisioning_service
        await provisioning_service._update_property_compliance(property_id)


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
    """Analyze a document using AI to extract metadata.
    
    AI Extraction Behavior by Plan:
    - PLAN_1_SOLO (Basic): Extracts document_type, issue_date, expiry_date only
      - No confidence scoring
      - Auto-applies if confidence would have been high (for basic extraction)
    
    - PLAN_2_PORTFOLIO / PLAN_3_PRO (Advanced): Full extraction
      - Includes confidence scoring
      - Returns data for Review & Apply UI
      - Field-level validation
    """
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
        
        # Check client's plan for extraction mode
        from services.plan_registry import plan_registry
        
        client = await db.clients.find_one(
            {"client_id": document["client_id"]},
            {"_id": 0, "billing_plan": 1}
        )
        
        plan_str = client.get("billing_plan", "PLAN_1_SOLO") if client else "PLAN_1_SOLO"
        has_advanced_extraction = plan_registry.get_features_by_string(plan_str).get("ai_extraction_advanced", False)
        
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
            extracted_data = result["extracted_data"]
            
            # For Basic plan (PLAN_1_SOLO): Filter to basic fields only, no confidence
            if not has_advanced_extraction:
                basic_data = {
                    "document_type": extracted_data.get("document_type"),
                    "issue_date": extracted_data.get("issue_date"),
                    "expiry_date": extracted_data.get("expiry_date"),
                    # Don't include confidence scores for basic plan
                }
                # Remove None values
                basic_data = {k: v for k, v in basic_data.items() if v is not None}
                
                return {
                    "message": "Document analyzed (Basic extraction)",
                    "extraction_mode": "basic",
                    "extraction": {
                        "status": "completed",
                        "data": basic_data
                    },
                    "auto_apply_enabled": True,  # Basic plan auto-applies
                    "review_ui_available": False
                }
            else:
                # Advanced extraction: Include all fields and confidence
                return {
                    "message": "Document analyzed successfully",
                    "extraction_mode": "advanced",
                    "extraction": {
                        "status": "completed",
                        "data": extracted_data,
                        "confidence": extracted_data.get("confidence", {}),
                    },
                    "auto_apply_enabled": False,  # Advanced requires review
                    "review_ui_available": True
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
                expiry_dt = _normalize_and_parse_date(expiry_date)
                
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
                    
            except ValueError as date_err:
                logger.warning(f"Failed to parse expiry date '{expiry_date}': {date_err}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid expiry date format: {expiry_date}. Expected formats: YYYY-MM-DD or DD/MM/YYYY."
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
            action=AuditAction.AI_EXTRACTION_APPLIED,
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
                "expiry_date_parsed": update_fields.get("due_date"),
                "certificate_number": cert_number,
                "engineer_name": data.get("engineer_details", {}).get("name") if isinstance(data.get("engineer_details"), dict) else data.get("engineer_name"),
                "user_confirmed": confirmed_data is not None,
                "document_status": "VERIFIED",
                "requirement_status_before": before_state.get("status"),
                "requirement_status_after": after_state.get("status")
            }
        )
        
        logger.info(f"AI extraction applied for document {document_id}: {changes_made}")
        
        # Send email notification to the client
        try:
            from services.email_service import email_service
            
            # Get client details for email
            client = await db.clients.find_one(
                {"client_id": document["client_id"]},
                {"_id": 0, "email": 1, "full_name": 1, "customer_reference": 1}
            )
            
            # Get property address for email
            property_doc = await db.properties.find_one(
                {"property_id": document.get("property_id")},
                {"_id": 0, "nickname": 1, "address_line_1": 1, "postcode": 1}
            )
            
            if client and client.get("email"):
                property_address = property_doc.get("nickname") or property_doc.get("address_line_1", "N/A") if property_doc else "N/A"
                if property_doc and property_doc.get("postcode"):
                    property_address += f", {property_doc.get('postcode')}"
                
                # Format expiry date for email
                expiry_display = "N/A"
                if update_fields.get("due_date"):
                    try:
                        expiry_dt = datetime.fromisoformat(update_fields["due_date"].replace('Z', '+00:00'))
                        expiry_display = expiry_dt.strftime("%d %B %Y")
                    except (ValueError, AttributeError):
                        expiry_display = update_fields.get("due_date", "N/A")
                
                await email_service.send_ai_extraction_email(
                    recipient=client["email"],
                    client_name=client.get("full_name", "there"),
                    client_id=document["client_id"],
                    customer_reference=client.get("customer_reference", ""),
                    property_address=property_address,
                    document_type=data.get("document_type") or document.get("file_name", "Certificate"),
                    certificate_number=cert_number or "N/A",
                    expiry_date=expiry_display,
                    requirement_status=after_state.get("status", "UPDATED"),
                    portal_link=os.getenv("FRONTEND_URL", "https://compliance-vault-pro.pleerity.com") + "/app/dashboard"
                )
                logger.info(f"AI extraction email sent to {client['email']}")
        except Exception as email_err:
            # Don't fail the extraction if email fails
            logger.warning(f"Failed to send AI extraction email: {email_err}")
        
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
