"""
Document Generation Service - Mock generator for Phase 1.
Implements a pluggable document generation interface for order deliverables.

Phase 1: Deterministic MOCK generator with DRAFT watermark
Future: Real LLM-powered generation via interface swap

Key Features:
- Generates DOCX + PDF for each order
- Follows consistent schema per service type
- Produces versioned documents (v1, v2, v3...)
- All documents marked with DRAFT/MOCK watermark
"""
import io
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, BinaryIO
from enum import Enum

from services.storage_adapter import storage_adapter, FileMetadata, upload_order_document
from database import database

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Types of generated documents."""
    SECTION_21_NOTICE = "SECTION_21_NOTICE"
    SECTION_8_NOTICE = "SECTION_8_NOTICE"
    TENANCY_AGREEMENT = "TENANCY_AGREEMENT"
    INVENTORY_REPORT = "INVENTORY_REPORT"
    COMPLIANCE_AUDIT = "COMPLIANCE_AUDIT"
    MARKET_RESEARCH = "MARKET_RESEARCH"
    GENERAL_DOCUMENT = "GENERAL_DOCUMENT"


class DocumentVersion:
    """Represents a single version of a generated document."""
    def __init__(
        self,
        version: int,
        document_type: DocumentType,
        file_id_docx: Optional[str] = None,
        file_id_pdf: Optional[str] = None,
        generated_at: Optional[datetime] = None,
        generated_by: str = "system",
        is_regeneration: bool = False,
        regeneration_notes: Optional[str] = None,
        is_approved: bool = False,
        approved_at: Optional[datetime] = None,
        approved_by: Optional[str] = None,
        content_hash: Optional[str] = None,
    ):
        self.version = version
        self.document_type = document_type
        self.file_id_docx = file_id_docx
        self.file_id_pdf = file_id_pdf
        self.generated_at = generated_at or datetime.now(timezone.utc)
        self.generated_by = generated_by
        self.is_regeneration = is_regeneration
        self.regeneration_notes = regeneration_notes
        self.is_approved = is_approved
        self.approved_at = approved_at
        self.approved_by = approved_by
        self.content_hash = content_hash
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "document_type": self.document_type.value if isinstance(self.document_type, DocumentType) else self.document_type,
            "file_id_docx": self.file_id_docx,
            "file_id_pdf": self.file_id_pdf,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "generated_by": self.generated_by,
            "is_regeneration": self.is_regeneration,
            "regeneration_notes": self.regeneration_notes,
            "is_approved": self.is_approved,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by": self.approved_by,
            "content_hash": self.content_hash,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentVersion":
        return cls(
            version=data.get("version", 1),
            document_type=DocumentType(data.get("document_type", "GENERAL_DOCUMENT")),
            file_id_docx=data.get("file_id_docx"),
            file_id_pdf=data.get("file_id_pdf"),
            generated_at=datetime.fromisoformat(data["generated_at"]) if data.get("generated_at") else None,
            generated_by=data.get("generated_by", "system"),
            is_regeneration=data.get("is_regeneration", False),
            regeneration_notes=data.get("regeneration_notes"),
            is_approved=data.get("is_approved", False),
            approved_at=datetime.fromisoformat(data["approved_at"]) if data.get("approved_at") else None,
            approved_by=data.get("approved_by"),
            content_hash=data.get("content_hash"),
        )


class DocumentGenerator(ABC):
    """Abstract base class for document generation."""
    
    @abstractmethod
    async def generate_documents(
        self,
        order_id: str,
        regeneration_notes: Optional[str] = None,
    ) -> DocumentVersion:
        """
        Generate documents for an order.
        Returns the created DocumentVersion with file references.
        """
        pass
    
    @abstractmethod
    def get_document_type_for_service(self, service_code: str) -> DocumentType:
        """Map service code to document type."""
        pass


class MockDocumentGenerator(DocumentGenerator):
    """
    Mock document generator for Phase 1.
    Generates deterministic DOCX + PDF with DRAFT watermark.
    """
    
    # Service code to document type mapping
    SERVICE_TO_DOC_TYPE = {
        "DOC_PACK_TENANCY": DocumentType.SECTION_21_NOTICE,
        "DOC_PACK_INVENTORY": DocumentType.INVENTORY_REPORT,
        "AUDIT_HMO": DocumentType.COMPLIANCE_AUDIT,
        "AUDIT_FULL": DocumentType.COMPLIANCE_AUDIT,
        "MARKET_RESEARCH": DocumentType.MARKET_RESEARCH,
        "AI_WORKFLOW": DocumentType.GENERAL_DOCUMENT,
    }
    
    def get_document_type_for_service(self, service_code: str) -> DocumentType:
        return self.SERVICE_TO_DOC_TYPE.get(service_code, DocumentType.GENERAL_DOCUMENT)
    
    async def generate_documents(
        self,
        order_id: str,
        regeneration_notes: Optional[str] = None,
    ) -> DocumentVersion:
        """
        Generate mock DOCX + PDF for an order.
        Stores in GridFS and returns DocumentVersion.
        """
        db = database.get_db()
        
        # Fetch order details
        order = await db.orders.find_one({"order_id": order_id})
        if not order:
            raise ValueError(f"Order not found: {order_id}")
        
        # Determine version number
        existing_versions = order.get("document_versions", [])
        new_version = len(existing_versions) + 1
        
        # Get document type
        doc_type = self.get_document_type_for_service(order.get("service_code", ""))
        
        # Generate DOCX content
        docx_content = self._generate_mock_docx(order, new_version, doc_type, regeneration_notes)
        
        # Generate PDF content
        pdf_content = self._generate_mock_pdf(order, new_version, doc_type, regeneration_notes)
        
        # Upload DOCX to storage
        docx_filename = f"{order_id}_v{new_version}.docx"
        docx_meta = await upload_order_document(
            order_id=order_id,
            file_data=io.BytesIO(docx_content),
            filename=docx_filename,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            document_type=doc_type.value,
            version=new_version,
            uploaded_by="system",
        )
        
        # Upload PDF to storage
        pdf_filename = f"{order_id}_v{new_version}.pdf"
        pdf_meta = await upload_order_document(
            order_id=order_id,
            file_data=io.BytesIO(pdf_content),
            filename=pdf_filename,
            content_type="application/pdf",
            document_type=doc_type.value,
            version=new_version,
            uploaded_by="system",
        )
        
        # Create version record
        doc_version = DocumentVersion(
            version=new_version,
            document_type=doc_type,
            file_id_docx=docx_meta.file_id,
            file_id_pdf=pdf_meta.file_id,
            generated_at=datetime.now(timezone.utc),
            generated_by="system",
            is_regeneration=new_version > 1,
            regeneration_notes=regeneration_notes,
            content_hash=docx_meta.sha256_hash,
        )
        
        # Update order with new version
        await db.orders.update_one(
            {"order_id": order_id},
            {
                "$push": {"document_versions": doc_version.to_dict()},
                "$set": {
                    "current_document_version": new_version,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
        logger.info(f"Generated mock documents for order {order_id} v{new_version}")
        return doc_version
    
    def _generate_mock_docx(
        self,
        order: Dict[str, Any],
        version: int,
        doc_type: DocumentType,
        regeneration_notes: Optional[str] = None,
    ) -> bytes:
        """Generate mock DOCX content as bytes."""
        # In a real implementation, we'd use python-docx
        # For mock, we generate a simple XML structure that represents a DOCX
        
        customer = order.get("customer", {})
        params = order.get("parameters", {})
        
        # Build document content based on type
        content_sections = self._build_document_sections(order, doc_type, version, regeneration_notes)
        
        # Create a simple mock DOCX (actually just XML for now)
        # In production, this would be a proper DOCX file
        mock_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- MOCK DOCUMENT - NOT FOR PRODUCTION USE -->
<!-- DRAFT/MOCK WATERMARK -->
<document>
    <header>
        <title>{doc_type.value}</title>
        <order_id>{order.get('order_id')}</order_id>
        <version>v{version}</version>
        <generated_at>{datetime.now(timezone.utc).isoformat()}</generated_at>
        <watermark>DRAFT - MOCK DOCUMENT - NON-PRODUCTION</watermark>
    </header>
    <customer>
        <name>{customer.get('full_name', 'N/A')}</name>
        <email>{customer.get('email', 'N/A')}</email>
    </customer>
    <service>
        <code>{order.get('service_code', 'N/A')}</code>
        <name>{order.get('service_name', 'N/A')}</name>
    </service>
    <content>
        {content_sections}
    </content>
    <footer>
        <disclaimer>This is a MOCK document generated for testing purposes only. Do not use in production.</disclaimer>
        <regeneration_notes>{regeneration_notes or 'N/A'}</regeneration_notes>
    </footer>
</document>
"""
        return mock_content.encode('utf-8')
    
    def _generate_mock_pdf(
        self,
        order: Dict[str, Any],
        version: int,
        doc_type: DocumentType,
        regeneration_notes: Optional[str] = None,
    ) -> bytes:
        """Generate mock PDF content as bytes."""
        # For a real implementation, we'd use reportlab
        # For mock, we generate a simple text-based representation
        
        customer = order.get("customer", {})
        params = order.get("parameters", {})
        
        content_sections = self._build_document_sections(order, doc_type, version, regeneration_notes)
        
        mock_content = f"""
================================================================================
                        *** DRAFT - MOCK DOCUMENT ***
================================================================================

Document Type: {doc_type.value}
Order Reference: {order.get('order_id')}
Version: v{version}
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

--------------------------------------------------------------------------------
                               CUSTOMER DETAILS
--------------------------------------------------------------------------------
Name: {customer.get('full_name', 'N/A')}
Email: {customer.get('email', 'N/A')}
Phone: {customer.get('phone', 'N/A')}

--------------------------------------------------------------------------------
                               SERVICE DETAILS
--------------------------------------------------------------------------------
Service Code: {order.get('service_code', 'N/A')}
Service Name: {order.get('service_name', 'N/A')}
Category: {order.get('service_category', 'N/A')}

--------------------------------------------------------------------------------
                              DOCUMENT CONTENT
--------------------------------------------------------------------------------
{content_sections}

--------------------------------------------------------------------------------
                                LEGAL NOTICE
--------------------------------------------------------------------------------
This is a MOCK document generated for testing purposes only.
Do not use this document for any legal, official, or production purposes.

Watermark: DRAFT/MOCK - NON-PRODUCTION

{f'Regeneration Notes: {regeneration_notes}' if regeneration_notes else ''}

================================================================================
                        *** END OF MOCK DOCUMENT ***
================================================================================
"""
        return mock_content.encode('utf-8')
    
    def _build_document_sections(
        self,
        order: Dict[str, Any],
        doc_type: DocumentType,
        version: int,
        regeneration_notes: Optional[str] = None,
    ) -> str:
        """Build document sections based on document type."""
        params = order.get("parameters", {})
        
        if doc_type == DocumentType.SECTION_21_NOTICE:
            return self._build_section_21(params, version)
        elif doc_type == DocumentType.SECTION_8_NOTICE:
            return self._build_section_8(params, version)
        elif doc_type == DocumentType.TENANCY_AGREEMENT:
            return self._build_tenancy_agreement(params, version)
        elif doc_type == DocumentType.INVENTORY_REPORT:
            return self._build_inventory_report(params, version)
        elif doc_type == DocumentType.COMPLIANCE_AUDIT:
            return self._build_compliance_audit(params, version)
        elif doc_type == DocumentType.MARKET_RESEARCH:
            return self._build_market_research(params, version)
        else:
            return self._build_general_document(params, version)
    
    def _build_section_21(self, params: Dict, version: int) -> str:
        return f"""
SECTION 21 NOTICE (Housing Act 1988)
-------------------------------------
Property Address: {params.get('property_address', '[Property Address Not Provided]')}
Tenant Name(s): {params.get('tenant_names', '[Tenant Names Not Provided]')}
Tenancy Start Date: {params.get('tenancy_start_date', '[Date Not Provided]')}
Notice Expiry Date: {params.get('notice_expiry_date', '[To Be Calculated]')}

IMPORTANT NOTICE TO TENANT(S):

This is a notice to inform you that your landlord requires possession of the
dwelling-house at the above address at the end of your tenancy.

[MOCK CONTENT - This section would contain the full legal notice text]

Landlord/Agent Details:
Name: {params.get('landlord_name', '[Landlord Name]')}
Address: {params.get('landlord_address', '[Landlord Address]')}
Signature: [DRAFT - UNSIGNED]
Date: [DRAFT - UNDATED]

Document Version: v{version}
"""
    
    def _build_section_8(self, params: Dict, version: int) -> str:
        return f"""
SECTION 8 NOTICE (Housing Act 1988)
-------------------------------------
Property Address: {params.get('property_address', '[Property Address Not Provided]')}
Tenant Name(s): {params.get('tenant_names', '[Tenant Names Not Provided]')}
Grounds for Possession: {params.get('grounds', '[Grounds Not Specified]')}

NOTICE SEEKING POSSESSION OF A PROPERTY LET ON AN ASSURED TENANCY

[MOCK CONTENT - This section would contain the full legal notice text]

Document Version: v{version}
"""
    
    def _build_tenancy_agreement(self, params: Dict, version: int) -> str:
        return f"""
ASSURED SHORTHOLD TENANCY AGREEMENT
------------------------------------
Property: {params.get('property_address', '[Property Address]')}
Landlord: {params.get('landlord_name', '[Landlord Name]')}
Tenant(s): {params.get('tenant_names', '[Tenant Names]')}
Term: {params.get('term_months', '12')} months
Start Date: {params.get('start_date', '[Start Date]')}
Rent: £{params.get('monthly_rent', '[Amount]')} per month
Deposit: £{params.get('deposit_amount', '[Amount]')}

[MOCK CONTENT - Full tenancy agreement terms would appear here]

Document Version: v{version}
"""
    
    def _build_inventory_report(self, params: Dict, version: int) -> str:
        return f"""
PROPERTY INVENTORY & CONDITION REPORT
--------------------------------------
Property: {params.get('property_address', '[Property Address]')}
Inspection Date: {params.get('inspection_date', '[Date]')}
Inspector: {params.get('inspector_name', '[Inspector Name]')}

ROOM-BY-ROOM INVENTORY:

1. ENTRANCE HALL
   - Flooring: [MOCK DATA]
   - Walls: [MOCK DATA]
   - Condition: [MOCK DATA]

2. LIVING ROOM
   - Flooring: [MOCK DATA]
   - Furniture: [MOCK DATA]
   - Condition: [MOCK DATA]

[Additional rooms would be listed here]

Document Version: v{version}
"""
    
    def _build_compliance_audit(self, params: Dict, version: int) -> str:
        return f"""
PROPERTY COMPLIANCE AUDIT REPORT
---------------------------------
Property: {params.get('property_address', '[Property Address]')}
Audit Date: {params.get('audit_date', datetime.now(timezone.utc).strftime('%Y-%m-%d'))}
Property Type: {params.get('property_type', 'Residential')}

COMPLIANCE STATUS SUMMARY:
---------------------------
Gas Safety: {params.get('gas_status', '[Status]')}
Electrical (EICR): {params.get('eicr_status', '[Status]')}
EPC Rating: {params.get('epc_rating', '[Rating]')}
Smoke/CO Alarms: {params.get('alarms_status', '[Status]')}
HMO Licence: {params.get('hmo_status', 'N/A')}

FINDINGS:
---------
[MOCK CONTENT - Detailed findings would appear here]

RECOMMENDATIONS:
----------------
[MOCK CONTENT - Recommendations would appear here]

Document Version: v{version}
"""
    
    def _build_market_research(self, params: Dict, version: int) -> str:
        return f"""
MARKET RESEARCH REPORT
-----------------------
Area: {params.get('area', '[Area]')}
Property Type: {params.get('property_type', 'All Types')}
Report Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}

MARKET OVERVIEW:
----------------
[MOCK DATA - Market overview would appear here]

COMPARABLE PROPERTIES:
----------------------
[MOCK DATA - Comparable properties would be listed here]

RENTAL ESTIMATES:
-----------------
Low: £{params.get('rent_estimate_low', '800')} pcm
Mid: £{params.get('rent_estimate_mid', '950')} pcm
High: £{params.get('rent_estimate_high', '1100')} pcm

RECOMMENDATIONS:
----------------
[MOCK CONTENT - Investment recommendations would appear here]

Document Version: v{version}
"""
    
    def _build_general_document(self, params: Dict, version: int) -> str:
        return f"""
GENERAL DOCUMENT
-----------------
This is a general purpose document generated by the system.

Parameters Provided:
{chr(10).join(f'  - {k}: {v}' for k, v in params.items()) if params else '  None'}

Document Version: v{version}

[MOCK CONTENT - Document body would appear here based on service type]
"""


# Singleton instance - Mock generator for Phase 1
document_generator = MockDocumentGenerator()


# Main interface function
async def generate_documents(
    order_id: str,
    regeneration_notes: Optional[str] = None,
) -> DocumentVersion:
    """
    Generate documents for an order.
    This is the main entry point - swap document_generator instance to change implementation.
    """
    return await document_generator.generate_documents(order_id, regeneration_notes)


async def get_document_versions(order_id: str) -> List[DocumentVersion]:
    """Get all document versions for an order."""
    db = database.get_db()
    order = await db.orders.find_one({"order_id": order_id}, {"document_versions": 1})
    
    if not order or "document_versions" not in order:
        return []
    
    return [DocumentVersion.from_dict(v) for v in order["document_versions"]]


async def get_current_document_version(order_id: str) -> Optional[DocumentVersion]:
    """Get the current (latest) document version for an order."""
    versions = await get_document_versions(order_id)
    return versions[-1] if versions else None


async def get_approved_document_version(order_id: str) -> Optional[DocumentVersion]:
    """Get the approved document version for an order."""
    versions = await get_document_versions(order_id)
    for v in reversed(versions):
        if v.is_approved:
            return v
    return None


async def approve_document_version(
    order_id: str,
    version: int,
    approved_by: str,
) -> DocumentVersion:
    """
    Approve a specific document version.
    Once approved, this version is locked and becomes the final deliverable.
    """
    db = database.get_db()
    
    # Update the specific version
    result = await db.orders.update_one(
        {
            "order_id": order_id,
            "document_versions.version": version,
        },
        {
            "$set": {
                "document_versions.$.is_approved": True,
                "document_versions.$.approved_at": datetime.now(timezone.utc).isoformat(),
                "document_versions.$.approved_by": approved_by,
                "approved_document_version": version,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    if result.modified_count == 0:
        raise ValueError(f"Document version {version} not found for order {order_id}")
    
    # Return the updated version
    versions = await get_document_versions(order_id)
    for v in versions:
        if v.version == version:
            return v
    
    raise ValueError("Failed to retrieve approved version")
