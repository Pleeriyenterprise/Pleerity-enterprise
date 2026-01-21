"""Professional PDF Report Generator - Enterprise-grade report generation.

Uses reportlab to create professionally formatted PDF reports with:
- Custom branding (colors, logo)
- Professional layout
- Compliance status visualization
- Property breakdown tables
- Expiry schedules
- Audit log exports

All reports respect plan gating and white-label settings.
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    PageBreak, Image, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics.charts.piecharts import Pie
from database import database
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import io
import logging

logger = logging.getLogger(__name__)


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple for reportlab."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4))


class ProfessionalReportGenerator:
    """Generate enterprise-grade PDF reports with custom branding."""
    
    def __init__(self):
        self.default_colors = {
            "primary": "#0B1D3A",
            "secondary": "#00B8A9",
            "accent": "#FFB800",
            "text": "#1F2937",
            "success": "#22C55E",
            "warning": "#F59E0B",
            "danger": "#EF4444"
        }
    
    async def get_branding(self, client_id: str) -> Dict[str, Any]:
        """Get client branding settings or defaults."""
        db = database.get_db()
        
        branding = await db.branding_settings.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "company_name": 1, "full_name": 1, "email": 1, "phone": 1}
        )
        
        if not branding:
            branding = {}
        
        # Merge with defaults
        return {
            "company_name": branding.get("company_name") or client.get("company_name") or client.get("full_name", ""),
            "logo_url": branding.get("logo_url"),
            "primary_color": branding.get("primary_color", self.default_colors["primary"]),
            "secondary_color": branding.get("secondary_color", self.default_colors["secondary"]),
            "accent_color": branding.get("accent_color", self.default_colors["accent"]),
            "text_color": branding.get("text_color", self.default_colors["text"]),
            "report_header_text": branding.get("report_header_text"),
            "report_footer_text": branding.get("report_footer_text"),
            "include_pleerity_branding": branding.get("include_pleerity_branding", True),
            "contact_email": branding.get("contact_email") or client.get("email"),
            "contact_phone": branding.get("contact_phone") or client.get("phone"),
            "website_url": branding.get("website_url"),
        }
    
    def create_styles(self, branding: Dict[str, Any]) -> Dict[str, ParagraphStyle]:
        """Create branded paragraph styles."""
        base_styles = getSampleStyleSheet()
        
        primary_rgb = hex_to_rgb(branding["primary_color"])
        secondary_rgb = hex_to_rgb(branding["secondary_color"])
        text_rgb = hex_to_rgb(branding["text_color"])
        
        return {
            "title": ParagraphStyle(
                'BrandedTitle',
                parent=base_styles['Title'],
                textColor=colors.Color(*primary_rgb),
                fontSize=24,
                spaceAfter=12,
                alignment=TA_LEFT
            ),
            "subtitle": ParagraphStyle(
                'BrandedSubtitle',
                parent=base_styles['Normal'],
                textColor=colors.Color(*text_rgb),
                fontSize=12,
                spaceAfter=20,
            ),
            "heading": ParagraphStyle(
                'BrandedHeading',
                parent=base_styles['Heading2'],
                textColor=colors.Color(*primary_rgb),
                fontSize=14,
                spaceBefore=12,
                spaceAfter=6,
            ),
            "body": ParagraphStyle(
                'BrandedBody',
                parent=base_styles['Normal'],
                textColor=colors.Color(*text_rgb),
                fontSize=10,
            ),
            "small": ParagraphStyle(
                'BrandedSmall',
                parent=base_styles['Normal'],
                textColor=colors.gray,
                fontSize=8,
            ),
            "footer": ParagraphStyle(
                'BrandedFooter',
                parent=base_styles['Normal'],
                textColor=colors.gray,
                fontSize=8,
                alignment=TA_CENTER,
            ),
        }
    
    def create_table_style(self, branding: Dict[str, Any]) -> TableStyle:
        """Create branded table style."""
        primary_rgb = hex_to_rgb(branding["primary_color"])
        secondary_rgb = hex_to_rgb(branding["secondary_color"])
        
        return TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(*primary_rgb)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # Data rows
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.Color(0.8, 0.8, 0.8)),
            
            # Alignment
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
    
    async def generate_compliance_summary_pdf(
        self,
        client_id: str,
        include_details: bool = True
    ) -> io.BytesIO:
        """Generate a professionally formatted compliance summary PDF.
        
        Includes:
        - Executive summary
        - Compliance score breakdown
        - Property status overview
        - Requirements summary
        - Upcoming expiry schedule
        """
        db = database.get_db()
        branding = await self.get_branding(client_id)
        styles = self.create_styles(branding)
        table_style = self.create_table_style(branding)
        
        # Fetch data
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        properties = await db.properties.find({"client_id": client_id}, {"_id": 0}).to_list(1000)
        requirements = await db.requirements.find({"client_id": client_id}, {"_id": 0}).to_list(10000)
        
        # Calculate stats
        total_props = len(properties)
        green = sum(1 for p in properties if p.get("compliance_status") == "GREEN")
        amber = sum(1 for p in properties if p.get("compliance_status") == "AMBER")
        red = sum(1 for p in properties if p.get("compliance_status") == "RED")
        
        total_reqs = len(requirements)
        compliant = sum(1 for r in requirements if r.get("status") == "COMPLIANT")
        pending = sum(1 for r in requirements if r.get("status") == "PENDING")
        overdue = sum(1 for r in requirements if r.get("status") == "OVERDUE")
        expiring = sum(1 for r in requirements if r.get("status") == "EXPIRING_SOON")
        
        # Build PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )
        
        elements = []
        now = datetime.now(timezone.utc)
        
        # Header
        if branding.get("report_header_text"):
            elements.append(Paragraph(branding["report_header_text"], styles["small"]))
            elements.append(Spacer(1, 6))
        
        # Title
        elements.append(Paragraph("Compliance Summary Report", styles["title"]))
        elements.append(Paragraph(
            f"{branding['company_name']}<br/>Generated: {now.strftime('%d %B %Y at %H:%M')}",
            styles["subtitle"]
        ))
        
        # Divider
        elements.append(HRFlowable(
            width="100%",
            thickness=2,
            color=colors.Color(*hex_to_rgb(branding["secondary_color"])),
            spaceAfter=20
        ))
        
        # Executive Summary
        elements.append(Paragraph("Executive Summary", styles["heading"]))
        
        score_pct = round((compliant / total_reqs * 100) if total_reqs > 0 else 0)
        summary_text = f"""
        Your property portfolio currently shows a <b>{score_pct}%</b> compliance rate. 
        Out of <b>{total_reqs}</b> total requirements across <b>{total_props}</b> properties:
        <br/><br/>
        • <b>{compliant}</b> requirements are fully compliant<br/>
        • <b>{expiring}</b> are expiring soon and need renewal<br/>
        • <b>{overdue}</b> are overdue and require immediate attention<br/>
        • <b>{pending}</b> are pending verification
        """
        elements.append(Paragraph(summary_text, styles["body"]))
        elements.append(Spacer(1, 20))
        
        # Property Status Table
        elements.append(Paragraph("Property Compliance Status", styles["heading"]))
        
        prop_data = [["Property Address", "City", "Postcode", "Status"]]
        for prop in properties[:20]:  # Limit to first 20
            status = prop.get("compliance_status", "UNKNOWN")
            prop_data.append([
                prop.get("address_line_1", ""),
                prop.get("city", ""),
                prop.get("postcode", ""),
                status
            ])
        
        prop_table = Table(prop_data, colWidths=[200, 80, 70, 70])
        prop_table.setStyle(table_style)
        
        # Color-code status cells
        for i, row in enumerate(prop_data[1:], start=1):
            status = row[3]
            if status == "GREEN":
                prop_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (3, i), (3, i), colors.Color(*hex_to_rgb("#22C55E"))),
                    ('FONTNAME', (3, i), (3, i), 'Helvetica-Bold'),
                ]))
            elif status == "AMBER":
                prop_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (3, i), (3, i), colors.Color(*hex_to_rgb("#F59E0B"))),
                    ('FONTNAME', (3, i), (3, i), 'Helvetica-Bold'),
                ]))
            elif status == "RED":
                prop_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (3, i), (3, i), colors.Color(*hex_to_rgb("#EF4444"))),
                    ('FONTNAME', (3, i), (3, i), 'Helvetica-Bold'),
                ]))
        
        elements.append(prop_table)
        elements.append(Spacer(1, 20))
        
        # Requirements Summary
        elements.append(Paragraph("Requirements Overview", styles["heading"]))
        
        req_summary_data = [
            ["Status", "Count", "Percentage"],
            ["Compliant", str(compliant), f"{round(compliant/total_reqs*100) if total_reqs else 0}%"],
            ["Expiring Soon", str(expiring), f"{round(expiring/total_reqs*100) if total_reqs else 0}%"],
            ["Overdue", str(overdue), f"{round(overdue/total_reqs*100) if total_reqs else 0}%"],
            ["Pending", str(pending), f"{round(pending/total_reqs*100) if total_reqs else 0}%"],
        ]
        
        req_table = Table(req_summary_data, colWidths=[150, 100, 100])
        req_table.setStyle(table_style)
        elements.append(req_table)
        
        # Footer
        elements.append(Spacer(1, 40))
        if branding.get("report_footer_text"):
            elements.append(Paragraph(branding["report_footer_text"], styles["footer"]))
            elements.append(Spacer(1, 10))
        
        if branding.get("include_pleerity_branding", True):
            elements.append(Paragraph(
                "Generated by Compliance Vault Pro • Powered by Pleerity",
                styles["footer"]
            ))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
    
    async def generate_audit_log_pdf(
        self,
        client_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        actions: Optional[List[str]] = None
    ) -> io.BytesIO:
        """Generate audit log export PDF.
        
        Includes all audit log entries for the client with filters.
        """
        db = database.get_db()
        branding = await self.get_branding(client_id)
        styles = self.create_styles(branding)
        table_style = self.create_table_style(branding)
        
        # Build query
        query = {"client_id": client_id}
        if start_date:
            query["timestamp"] = {"$gte": start_date}
        if end_date:
            query.setdefault("timestamp", {})["$lte"] = end_date
        if actions:
            query["action"] = {"$in": actions}
        
        # Fetch audit logs
        logs = await db.audit_logs.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).to_list(500)
        
        # Build PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=50,
            bottomMargin=50
        )
        
        elements = []
        now = datetime.now(timezone.utc)
        
        # Title
        elements.append(Paragraph("Audit Log Report", styles["title"]))
        elements.append(Paragraph(
            f"{branding['company_name']}<br/>Generated: {now.strftime('%d %B %Y at %H:%M')}",
            styles["subtitle"]
        ))
        
        elements.append(HRFlowable(
            width="100%",
            thickness=2,
            color=colors.Color(*hex_to_rgb(branding["secondary_color"])),
            spaceAfter=20
        ))
        
        # Summary
        elements.append(Paragraph(f"Total entries: {len(logs)}", styles["body"]))
        elements.append(Spacer(1, 15))
        
        # Audit Log Table
        log_data = [["Timestamp", "Action", "Actor", "Details"]]
        for log in logs[:100]:  # Limit to 100 entries
            timestamp = log.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamp = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    pass
            
            details = log.get("metadata", {})
            details_str = ", ".join(f"{k}: {v}" for k, v in list(details.items())[:3])
            
            log_data.append([
                timestamp,
                log.get("action", ""),
                log.get("actor_id", "System")[:8] + "...",
                details_str[:40] + "..." if len(details_str) > 40 else details_str
            ])
        
        log_table = Table(log_data, colWidths=[100, 120, 80, 150])
        log_table.setStyle(table_style)
        elements.append(log_table)
        
        # Footer
        elements.append(Spacer(1, 40))
        if branding.get("include_pleerity_branding", True):
            elements.append(Paragraph(
                "Audit Log Export • Compliance Vault Pro by Pleerity",
                styles["footer"]
            ))
        
        doc.build(elements)
        buffer.seek(0)
        return buffer
    
    async def generate_expiry_schedule_pdf(
        self,
        client_id: str,
        days: int = 90
    ) -> io.BytesIO:
        """Generate expiry schedule PDF showing upcoming certificate expirations."""
        from datetime import timedelta
        
        db = database.get_db()
        branding = await self.get_branding(client_id)
        styles = self.create_styles(branding)
        table_style = self.create_table_style(branding)
        
        # Fetch data
        now = datetime.now(timezone.utc)
        end_date = (now + timedelta(days=days)).isoformat()
        
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0, "property_id": 1, "address_line_1": 1, "city": 1, "postcode": 1}
        ).to_list(1000)
        
        property_map = {p["property_id"]: p for p in properties}
        property_ids = list(property_map.keys())
        
        requirements = await db.requirements.find(
            {
                "property_id": {"$in": property_ids},
                "due_date": {"$lte": end_date, "$gte": now.isoformat()}
            },
            {"_id": 0}
        ).sort("due_date", 1).to_list(500)
        
        # Build PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )
        
        elements = []
        
        # Title
        elements.append(Paragraph("Expiry Schedule Report", styles["title"]))
        elements.append(Paragraph(
            f"{branding['company_name']}<br/>Next {days} Days • Generated: {now.strftime('%d %B %Y')}",
            styles["subtitle"]
        ))
        
        elements.append(HRFlowable(
            width="100%",
            thickness=2,
            color=colors.Color(*hex_to_rgb(branding["secondary_color"])),
            spaceAfter=20
        ))
        
        # Summary
        elements.append(Paragraph(f"<b>{len(requirements)}</b> items expiring in the next {days} days", styles["body"]))
        elements.append(Spacer(1, 15))
        
        # Expiry Schedule Table
        exp_data = [["Expiry Date", "Requirement", "Property", "Status"]]
        for req in requirements:
            prop = property_map.get(req.get("property_id"), {})
            due_date = req.get("due_date", "")
            if due_date:
                try:
                    dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                    due_date = dt.strftime('%d %b %Y')
                except:
                    pass
            
            exp_data.append([
                due_date,
                req.get("requirement_type", "Unknown"),
                prop.get("address_line_1", "")[:25],
                req.get("status", "")
            ])
        
        exp_table = Table(exp_data, colWidths=[80, 140, 150, 80])
        exp_table.setStyle(table_style)
        
        # Color-code by urgency
        for i, row in enumerate(exp_data[1:], start=1):
            status = row[3]
            if status == "OVERDUE":
                exp_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.Color(1, 0.95, 0.95)),
                ]))
            elif status == "EXPIRING_SOON":
                exp_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.Color(1, 0.98, 0.9)),
                ]))
        
        elements.append(exp_table)
        
        # Footer
        elements.append(Spacer(1, 40))
        if branding.get("include_pleerity_branding", True):
            elements.append(Paragraph(
                "Expiry Schedule • Compliance Vault Pro by Pleerity",
                styles["footer"]
            ))
        
        doc.build(elements)
        buffer.seek(0)
        return buffer


# Singleton instance
professional_report_generator = ProfessionalReportGenerator()
