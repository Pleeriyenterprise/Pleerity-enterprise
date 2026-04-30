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
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from utils.expiry_utils import get_computed_status, get_effective_expiry_date
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
        """Resolved branding for client-facing PDFs (Pleerity default or full white-label)."""
        from services.branding_resolver_service import resolve_branding, BrandingContext

        profile = await resolve_branding(client_id, BrandingContext.CLIENT_DOCUMENT_PDF)
        return profile.to_report_dict()
    
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
        from services.requirement_client_runtime_surface import (
            filter_requirement_rows_for_client_runtime_surfaces,
            client_portal_surface_visible_row,
            project_requirement_row_client_runtime,
            compute_client_portal_requirement_stats,
        )

        requirements = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=client_id,
            requirements=requirements,
            client_doc=client,
            properties=properties,
        )
        client_doc = client or {}
        projected = [project_requirement_row_client_runtime(r) for r in requirements]
        portal_reqs = [r for r in projected if client_portal_surface_visible_row(r)]
        counts = compute_client_portal_requirement_stats(portal_reqs)

        # Calculate stats
        total_props = len(properties)
        green = sum(1 for p in properties if p.get("compliance_status") == "GREEN")
        amber = sum(1 for p in properties if p.get("compliance_status") == "AMBER")
        red = sum(1 for p in properties if p.get("compliance_status") == "RED")

        total_reqs = counts["total_requirements"]
        compliant = counts["compliant"]
        overdue = counts["overdue"]
        expiring = counts["expiring_soon"]
        missing_evidence = counts["missing_evidence"]
        
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
        
        # Portfolio CVP headline (persisted property scores — same contract as portal; not the requirement % below)
        try:
            from services.compliance_score import calculate_compliance_score
            from services.scoring_semantics_v1 import (
                SCORING_SEMANTICS_VERSION,
                headline_score_display_for_export,
            )

            cs = await calculate_compliance_score(client_id)
            disp = headline_score_display_for_export(cs.get("score"), cs.get("score_status"))
            scale_note = " (0–100 headline)" if str(disp).isdigit() else ""
            st = cs.get("score_status") or "—"
            auth = cs.get("score_authority") or "—"
            lc_raw = cs.get("last_calculated_at") or cs.get("portfolio_last_calculated_at") or "—"
            cov = cs.get("score_coverage") or {}
            cov_note = ""
            if isinstance(cov, dict) and int(cov.get("properties_missing_score") or 0) > 0:
                cov_note = (
                    f" Averages {int(cov.get('properties_with_score') or 0)} of {int(cov.get('properties_total') or 0)} "
                    f"properties with stored scores; {int(cov.get('properties_missing_score') or 0)} without a stored score."
                )
            cvp_block = f"""
            <b>Portfolio compliance score (CVP headline)</b>{scale_note}: <b>{disp}</b><br/>
            <b>Score status:</b> {st} &nbsp;|&nbsp; <b>Authority:</b> {auth}<br/>
            <b>Last calculated:</b> {lc_raw}<br/>
            <i>Scoring contract: {SCORING_SEMANTICS_VERSION}.</i> This headline uses persisted property scores only.{cov_note}
            """
            elements.append(Paragraph("Portfolio compliance score", styles["heading"]))
            elements.append(Paragraph(cvp_block, styles["body"]))
            elements.append(Spacer(1, 16))
        except Exception as cvp_err:
            logger.warning("Professional compliance summary PDF: CVP headline unavailable: %s", cvp_err)
            elements.append(Paragraph("Portfolio compliance score", styles["heading"]))
            elements.append(
                Paragraph(
                    "<b>Portfolio compliance score (CVP headline):</b> unavailable in this export run.",
                    styles["body"],
                )
            )
            elements.append(Spacer(1, 16))

        # Executive Summary
        elements.append(Paragraph("Executive Summary", styles["heading"]))
        
        score_pct = round((compliant / total_reqs * 100) if total_reqs > 0 else 0)
        summary_text = f"""
        The following <b>{score_pct}%</b> figure is a <b>requirement-status completion rate</b> from portal-visible rows — not the CVP headline score above.
        Out of <b>{total_reqs}</b> total requirements across <b>{total_props}</b> properties:
        <br/><br/>
        • <b>{compliant}</b> requirements are fully compliant<br/>
        • <b>{expiring}</b> are expiring soon and need renewal<br/>
        • <b>{overdue}</b> are overdue and require immediate attention<br/>
        • <b>{missing_evidence}</b> need evidence or confirmation (missing / pending on portal-visible requirements)
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
            ["Missing / pending evidence", str(missing_evidence), f"{round(missing_evidence/total_reqs*100) if total_reqs else 0}%"],
        ]
        
        req_table = Table(req_summary_data, colWidths=[150, 100, 100])
        req_table.setStyle(table_style)
        elements.append(req_table)
        
        # Footer
        elements.append(Spacer(1, 40))
        if branding.get("report_footer_text"):
            elements.append(Paragraph(branding["report_footer_text"], styles["footer"]))
            elements.append(Spacer(1, 10))
        
        for line in branding.get("pdf_attribution_lines") or []:
            elements.append(Paragraph(line, styles["footer"]))
        if branding.get("pdf_footer_contact_line"):
            elements.append(Paragraph(branding["pdf_footer_contact_line"], styles["footer"]))
        
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
        db = database.get_db()
        branding = await self.get_branding(client_id)
        styles = self.create_styles(branding)
        table_style = self.create_table_style(branding)
        
        # Fetch data
        now = datetime.now(timezone.utc)
        end_date = (now + timedelta(days=days)).isoformat()
        
        properties = await db.properties.find({"client_id": client_id}, {"_id": 0}).to_list(1000)

        property_map = {p["property_id"]: p for p in properties}
        property_ids = list(property_map.keys())
        client_row = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1}) or {}

        all_reqs = await db.requirements.find(
            {"property_id": {"$in": property_ids}},
            {"_id": 0},
        ).to_list(10000)
        from services.requirement_client_runtime_surface import (
            filter_requirement_rows_for_client_runtime_surfaces,
        )

        all_reqs = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=client_id,
            requirements=all_reqs,
            client_doc=client_row,
            properties=properties,
        )

        requirements: List[Dict[str, Any]] = []
        end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        for r in all_reqs:
            eff = get_effective_expiry_date(r)
            if eff is None:
                continue
            if eff.tzinfo is None:
                eff = eff.replace(tzinfo=timezone.utc)
            if now <= eff <= end_dt:
                requirements.append(r)

        requirements.sort(key=lambda x: get_effective_expiry_date(x) or now)
        requirements = requirements[:500]
        
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
        elements.append(
            Paragraph(
                "Schedule view only: statuses below are calendar urgency states for upcoming expiries, "
                "not canonical compliance KPI counts.",
                styles["small"],
            )
        )
        elements.append(Spacer(1, 8))
        
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
        exp_data = [["Expiry Date", "Requirement", "Property", "Schedule status"]]
        for req in requirements:
            prop = property_map.get(req.get("property_id"), {})
            eff = get_effective_expiry_date(req)
            due_date = ""
            if eff:
                try:
                    due_date = eff.strftime("%d %b %Y")
                except Exception:
                    due_date = str(eff)[:12]
            cs = get_computed_status(req, property_doc=prop, client_doc=client_row) or (req.get("status") or "")

            exp_data.append([
                due_date,
                req.get("requirement_type", "Unknown"),
                prop.get("address_line_1", "")[:25],
                cs,
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
        for line in branding.get("pdf_attribution_lines") or []:
            elements.append(Paragraph(line, styles["footer"]))
        if branding.get("pdf_footer_contact_line"):
            elements.append(Paragraph(branding["pdf_footer_contact_line"], styles["footer"]))
        
        doc.build(elements)
        buffer.seek(0)
        return buffer

    async def generate_branding_preview_pdf(
        self,
        client_id: str,
        logo_path: Optional[str] = None,
    ) -> io.BytesIO:
        """Generate a one-page sample PDF with current branding for preview.
        logo_path: optional path to uploaded logo file (used when logo is hosted by us).
        """
        branding = await self.get_branding(client_id)
        styles = self.create_styles(branding)
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50,
        )
        elements = []
        now = datetime.now(timezone.utc)

        # Optional logo (prefer local file from resolver / upload)
        eff_logo = logo_path or branding.get("logo_path")
        if eff_logo:
            try:
                from pathlib import Path
                p = Path(eff_logo)
                if p.is_file():
                    img = Image(str(p), width=120, height=60)
                    elements.append(img)
                    elements.append(Spacer(1, 12))
            except Exception:
                pass
        elif branding.get("logo_url"):
            try:
                from urllib.request import urlopen
                img = Image(io.BytesIO(urlopen(branding["logo_url"]).read()), width=120, height=60)
                elements.append(img)
                elements.append(Spacer(1, 12))
            except Exception:
                pass

        elements.append(Paragraph("Branding Preview", styles["title"]))
        elements.append(Paragraph(
            f"{branding['company_name']}<br/>Sample report generated: {now.strftime('%d %B %Y at %H:%M')}",
            styles["subtitle"],
        ))
        elements.append(HRFlowable(
            width="100%",
            thickness=2,
            color=colors.Color(*hex_to_rgb(branding["secondary_color"])),
            spaceAfter=20,
        ))
        elements.append(Paragraph(
            "This is how your reports and compliance packs will look with the current branding settings.",
            styles["body"],
        ))
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("Primary colour", styles["heading"]))
        elements.append(HRFlowable(
            width="100%",
            thickness=24,
            color=colors.Color(*hex_to_rgb(branding["primary_color"])),
            spaceAfter=12,
        ))
        if branding.get("report_header_text"):
            elements.append(Paragraph("Header text:", styles["small"]))
            elements.append(Paragraph(branding["report_header_text"], styles["body"]))
            elements.append(Spacer(1, 12))
        if branding.get("report_footer_text"):
            elements.append(Paragraph("Footer text:", styles["small"]))
            elements.append(Paragraph(branding["report_footer_text"], styles["body"]))
            elements.append(Spacer(1, 20))
        for line in branding.get("pdf_attribution_lines") or []:
            elements.append(Paragraph(line, styles["footer"]))

        doc.build(elements)
        buffer.seek(0)
        return buffer


# Singleton instance
professional_report_generator = ProfessionalReportGenerator()
