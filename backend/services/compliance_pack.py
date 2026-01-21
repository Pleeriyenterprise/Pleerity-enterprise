"""Compliance Pack Service - Generate downloadable PDF bundles of compliance certificates.

This service creates a professional PDF document containing all valid certificates
for a property, suitable for sharing with agents, tenants, or regulatory bodies.
"""
import os
import io
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict
from database import database
from models import AuditAction
from utils.audit import create_audit_log
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

logger = logging.getLogger(__name__)

# Brand colors
MIDNIGHT_BLUE = HexColor('#0B1D3A')
ELECTRIC_TEAL = HexColor('#00B8A9')
SUCCESS_GREEN = HexColor('#22c55e')
WARNING_AMBER = HexColor('#f59e0b')
DANGER_RED = HexColor('#dc2626')
GRAY_500 = HexColor('#6b7280')
GRAY_200 = HexColor('#e5e7eb')
WHITE = HexColor('#ffffff')


class CompliancePackService:
    """Service to generate compliance pack PDFs."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Set up custom paragraph styles for the PDF."""
        self.styles.add(ParagraphStyle(
            name='PackTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=MIDNIGHT_BLUE,
            spaceAfter=20,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='PackSubtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=GRAY_500,
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=MIDNIGHT_BLUE,
            spaceBefore=20,
            spaceAfter=10
        ))
        
        self.styles.add(ParagraphStyle(
            name='PropertyAddress',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=MIDNIGHT_BLUE,
            fontName='Helvetica-Bold',
            spaceAfter=5
        ))
        
        self.styles.add(ParagraphStyle(
            name='CertificateTitle',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=MIDNIGHT_BLUE,
            fontName='Helvetica-Bold',
            spaceBefore=15,
            spaceAfter=5
        ))
        
        self.styles.add(ParagraphStyle(
            name='CertificateDetail',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=GRAY_500,
            spaceAfter=3
        ))
        
        self.styles.add(ParagraphStyle(
            name='StatusCompliant',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=SUCCESS_GREEN,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='StatusExpiring',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=WARNING_AMBER,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='StatusOverdue',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=DANGER_RED,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=GRAY_500,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='Disclaimer',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=GRAY_500,
            spaceBefore=20,
            spaceAfter=10
        ))
    
    def _get_status_style(self, status: str) -> str:
        """Get the appropriate style name for a status."""
        if status == 'COMPLIANT':
            return 'StatusCompliant'
        elif status == 'EXPIRING_SOON':
            return 'StatusExpiring'
        else:
            return 'StatusOverdue'
    
    def _format_date(self, date_str: Optional[str]) -> str:
        """Format a date string for display."""
        if not date_str:
            return 'Not Set'
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%d %B %Y')
        except (ValueError, AttributeError):
            return str(date_str)[:10] if date_str else 'Not Set'
    
    def _get_requirement_display_name(self, req_type: str) -> str:
        """Get a human-readable name for a requirement type."""
        names = {
            'gas_safety': 'Gas Safety Certificate (CP12)',
            'eicr': 'Electrical Installation Condition Report (EICR)',
            'epc': 'Energy Performance Certificate (EPC)',
            'fire_alarm': 'Fire Alarm Certificate',
            'legionella': 'Legionella Risk Assessment',
            'hmo_license': 'HMO Licence',
            'pat_testing': 'PAT Testing Certificate',
            'fire_risk': 'Fire Risk Assessment',
            'smoke_co_alarm': 'Smoke & CO Alarm Certificate',
            'asbestos': 'Asbestos Survey'
        }
        return names.get(req_type, req_type.replace('_', ' ').title())
    
    async def generate_compliance_pack(
        self,
        property_id: str,
        client_id: str,
        include_expired: bool = False,
        requested_by: str = None,
        requested_by_role: str = None
    ) -> bytes:
        """Generate a compliance pack PDF for a property.
        
        Args:
            property_id: The property to generate pack for
            client_id: The client who owns the property
            include_expired: Whether to include expired certificates
            requested_by: Who requested the pack (for audit)
            requested_by_role: Role of requester
            
        Returns:
            PDF bytes
        """
        db = database.get_db()
        
        # Get property details
        property_doc = await db.properties.find_one(
            {"property_id": property_id, "client_id": client_id},
            {"_id": 0}
        )
        
        if not property_doc:
            raise ValueError("Property not found")
        
        # Get client details
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "full_name": 1, "company_name": 1, "customer_reference": 1}
        )
        
        # Get requirements
        req_filter = {"property_id": property_id, "client_id": client_id}
        if not include_expired:
            req_filter["status"] = {"$ne": "OVERDUE"}
        
        requirements = await db.requirements.find(
            req_filter,
            {"_id": 0}
        ).to_list(100)
        
        # Get related documents
        req_ids = [r.get("requirement_id") for r in requirements]
        documents = await db.documents.find(
            {"requirement_id": {"$in": req_ids}, "status": "VERIFIED"},
            {"_id": 0}
        ).to_list(100)
        
        # Build document map
        doc_map = {}
        for doc in documents:
            req_id = doc.get("requirement_id")
            if req_id not in doc_map:
                doc_map[req_id] = []
            doc_map[req_id].append(doc)
        
        # Generate PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=20*mm,
            bottomMargin=20*mm,
            leftMargin=20*mm,
            rightMargin=20*mm
        )
        
        story = []
        
        # Title
        story.append(Paragraph("COMPLIANCE PACK", self.styles['PackTitle']))
        story.append(Paragraph(
            f"Generated on {datetime.now(timezone.utc).strftime('%d %B %Y at %H:%M UTC')}",
            self.styles['PackSubtitle']
        ))
        
        # Property Info
        address = f"{property_doc.get('address_line_1', '')}"
        if property_doc.get('address_line_2'):
            address += f", {property_doc.get('address_line_2')}"
        address += f"<br/>{property_doc.get('city', '')} {property_doc.get('postcode', '')}"
        
        story.append(Paragraph("Property", self.styles['SectionHeader']))
        story.append(Paragraph(address, self.styles['PropertyAddress']))
        
        if property_doc.get('nickname'):
            story.append(Paragraph(
                f"Ref: {property_doc.get('nickname')}",
                self.styles['CertificateDetail']
            ))
        
        # Compliance Status Summary
        story.append(Spacer(1, 10*mm))
        
        compliant_count = sum(1 for r in requirements if r.get('status') == 'COMPLIANT')
        expiring_count = sum(1 for r in requirements if r.get('status') == 'EXPIRING_SOON')
        overdue_count = sum(1 for r in requirements if r.get('status') == 'OVERDUE')
        
        overall_status = "FULLY COMPLIANT" if overdue_count == 0 and expiring_count == 0 else (
            "ATTENTION NEEDED" if overdue_count == 0 else "ACTION REQUIRED"
        )
        
        status_table_data = [
            ["Overall Status", overall_status],
            ["Valid Certificates", str(compliant_count)],
            ["Expiring Soon", str(expiring_count)],
            ["Overdue", str(overdue_count)]
        ]
        
        status_table = Table(status_table_data, colWidths=[100*mm, 60*mm])
        status_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), MIDNIGHT_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, GRAY_200),
        ]))
        story.append(status_table)
        
        # Certificate Details
        story.append(Paragraph("Certificate Details", self.styles['SectionHeader']))
        
        for req in sorted(requirements, key=lambda x: x.get('requirement_type', '')):
            req_type = req.get('requirement_type', 'unknown')
            status = req.get('status', 'UNKNOWN')
            due_date = req.get('due_date')
            
            story.append(Paragraph(
                self._get_requirement_display_name(req_type),
                self.styles['CertificateTitle']
            ))
            
            # Status
            status_style = self._get_status_style(status)
            status_display = status.replace('_', ' ')
            story.append(Paragraph(f"Status: {status_display}", self.styles[status_style]))
            
            # Expiry date
            story.append(Paragraph(
                f"Valid Until: {self._format_date(due_date)}",
                self.styles['CertificateDetail']
            ))
            
            # Related documents
            req_docs = doc_map.get(req.get('requirement_id'), [])
            if req_docs:
                doc_names = [d.get('file_name', 'Document') for d in req_docs[:3]]
                story.append(Paragraph(
                    f"Documents: {', '.join(doc_names)}",
                    self.styles['CertificateDetail']
                ))
            
            story.append(Spacer(1, 5*mm))
        
        # Disclaimer
        story.append(Spacer(1, 15*mm))
        story.append(Paragraph(
            "<b>Disclaimer:</b> This compliance pack is generated from Compliance Vault Pro and represents "
            "the compliance status as recorded in the system at the time of generation. It does not constitute "
            "legal advice. Property owners should ensure all certificates are independently verified "
            "and remain current. Compliance Vault Pro and Pleerity Enterprise Ltd accept no liability "
            "for any errors or omissions.",
            self.styles['Disclaimer']
        ))
        
        # Footer with landlord info
        if client:
            landlord_info = client.get('company_name') or client.get('full_name', 'Landlord')
            crn = client.get('customer_reference', '')
            story.append(Paragraph(
                f"Landlord: {landlord_info}" + (f" • Ref: {crn}" if crn else ""),
                self.styles['Footer']
            ))
        
        story.append(Paragraph(
            "Powered by Compliance Vault Pro • pleerity.com",
            self.styles['Footer']
        ))
        
        doc.build(story)
        
        # Log generation
        logger.info(f"Compliance pack generated for property {property_id} by {requested_by}")
        
        # Create audit log
        await create_audit_log(
            action=AuditAction.DOCUMENT_VERIFIED,  # Reuse for now
            actor_id=requested_by,
            client_id=client_id,
            resource_type="compliance_pack",
            resource_id=property_id,
            metadata={
                "action": "compliance_pack_generated",
                "property_id": property_id,
                "include_expired": include_expired,
                "certificate_count": len(requirements),
                "requested_by_role": requested_by_role
            }
        )
        
        return buffer.getvalue()
    
    async def get_pack_preview(
        self,
        property_id: str,
        client_id: str
    ) -> Dict:
        """Get a preview of what the compliance pack will contain.
        
        Returns metadata without generating the PDF.
        """
        db = database.get_db()
        
        # Get property
        property_doc = await db.properties.find_one(
            {"property_id": property_id, "client_id": client_id},
            {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1, "nickname": 1}
        )
        
        if not property_doc:
            raise ValueError("Property not found")
        
        # Get requirements
        requirements = await db.requirements.find(
            {"property_id": property_id, "client_id": client_id},
            {"_id": 0, "requirement_type": 1, "status": 1, "due_date": 1}
        ).to_list(100)
        
        return {
            "property_address": f"{property_doc.get('address_line_1', '')}, {property_doc.get('postcode', '')}",
            "property_nickname": property_doc.get('nickname'),
            "total_certificates": len(requirements),
            "compliant": sum(1 for r in requirements if r.get('status') == 'COMPLIANT'),
            "expiring_soon": sum(1 for r in requirements if r.get('status') == 'EXPIRING_SOON'),
            "overdue": sum(1 for r in requirements if r.get('status') == 'OVERDUE'),
            "certificates": [
                {
                    "type": self._get_requirement_display_name(r.get('requirement_type', '')),
                    "status": r.get('status'),
                    "expiry": self._format_date(r.get('due_date'))
                }
                for r in requirements
            ]
        }


compliance_pack_service = CompliancePackService()
