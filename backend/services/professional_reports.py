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
from presentation.jurisdiction_reporting import portfolio_jurisdiction_summary_sentence
from services.report_branding_layout import append_report_cover_block
from services.report_layout_governance import (
    GovernancePdfContext,
    append_governance_matrix_for_properties,
    append_unresolved_obligations_section,
    make_page_callbacks,
)
from services.reporting_semantics_v1 import (
    EXPORT_DETERMINISM_POINT_IN_TIME,
    EXPORT_GRADE_DEFINITIONS,
    GRADE_CLIENT_PRESENTATION,
)
import io
import logging

logger = logging.getLogger(__name__)


def _professional_compliance_summary_escape_xml(text: str) -> str:
    """XML-safe text for ReportLab Paragraph markup (compliance summary PDF only)."""
    from xml.sax.saxutils import escape

    return escape(text or "", {'"': "&quot;", "'": "&apos;"})


def _professional_compliance_summary_score_batch_time_display(raw: Any) -> str:
    """Persisted headline score batch time for display — not PDF generation time."""
    if raw is None or raw == "":
        return "—"
    if isinstance(raw, datetime):
        dt = raw if raw.tzinfo is not None else raw.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%d %B %Y at %H:%M UTC")
    s = str(raw).strip()
    if not s:
        return "—"
    s_iso = s.replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s_iso)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).strftime("%d %B %Y at %H:%M UTC")
    except Exception:
        if len(s) >= 19 and "T" in s[:19]:
            return s[:19].replace("T", " ")
        return s[:48] if len(s) > 48 else s


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
        include_details: bool = True,
        artifact_lineage: Optional[Dict[str, Any]] = None,
    ) -> io.BytesIO:
        """Generate a professionally formatted compliance summary PDF.

        Snapshot framing: export time vs persisted CVP headline (`calculate_compliance_score`),
        including `score_status_message` and last score batch time when returned.

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
        from services.requirement_client_runtime_surface import compute_client_portal_requirement_stats
        from services.reporting_semantics_v1 import load_score_projection_portal_rows

        client_doc = client or {}
        portal_reqs = await load_score_projection_portal_rows(
            db,
            client_id=client_id,
            client_doc=client_doc,
            properties=properties,
            requirements=requirements,
        )
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
            bottomMargin=62,
        )
        
        elements = []
        now = datetime.now(timezone.utc)
        from services.reporting_semantics_v1 import EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT, GRADE_REGULATORY

        lineage = artifact_lineage or {}
        export_grade = lineage.get("export_grade") or GRADE_REGULATORY
        determinism = lineage.get("determinism") or (
            EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT if lineage.get("artifact_id") else EXPORT_DETERMINISM_POINT_IN_TIME
        )
        grade_def = EXPORT_GRADE_DEFINITIONS.get(export_grade) or {}
        gov_ctx = GovernancePdfContext(
            export_grade=export_grade,
            export_grade_label=lineage.get("export_grade_label") or grade_def.get("label") or export_grade,
            generated_at=now,
            determinism=determinism,
            jurisdiction_summary=(lineage.get("jurisdiction_scope") or portfolio_jurisdiction_summary_sentence(client_doc, properties))[:90],
            company_name=branding.get("company_name") or "",
            artifact_id=str(lineage.get("artifact_id") or ""),
            semantics_version=str(lineage.get("semantics_version") or "v1"),
            immutable_status=str(lineage.get("immutable_status") or ("frozen" if lineage.get("artifact_id") else "")),
            report_scope=str(lineage.get("report_scope") or "portfolio"),
            source_snapshot_hash=str(lineage.get("source_snapshot_hash") or ""),
        )
        on_first, on_later = make_page_callbacks(gov_ctx)
        
        client_row = client or {}
        crn = client_row.get("customer_reference") or client_id
        append_report_cover_block(
            elements,
            report_title="Compliance Summary Report",
            branding=branding,
            gov_ctx=gov_ctx,
            styles=styles,
            account_line=(
                f"<b>Account:</b> {_professional_compliance_summary_escape_xml(branding.get('company_name') or '')}"
                f" &nbsp;|&nbsp; <b>CRN:</b> {_professional_compliance_summary_escape_xml(crn)}"
            ),
            scope_line="<b>Scope:</b> portfolio",
        )

        snap_ts = now.strftime("%d %B %Y at %H:%M UTC")
        elements.append(
            Paragraph(
                f"<b>Snapshot generated at</b> {_professional_compliance_summary_escape_xml(snap_ts)}",
                styles["body"],
            )
        )
        elements.append(
            Paragraph(
                "Point-in-time export. The CVP headline below reflects persisted scores from the last completed calculation "
                "shown under <b>Last score calculation</b>; it may differ after later recalculation.",
                styles["small"],
            )
        )
        elements.append(Spacer(1, 10))
        
        # Portfolio CVP headline (persisted property scores; not the requirement completion % below)
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
            lc_candidate = cs.get("last_calculated_at") or cs.get("portfolio_last_calculated_at")
            lc_display = _professional_compliance_summary_score_batch_time_display(lc_candidate)
            ssm = (cs.get("score_status_message") or "").strip()
            headline_note_html = ""
            if ssm:
                headline_note_html = (
                    f"<br/><b>Headline note:</b> {_professional_compliance_summary_escape_xml(ssm)}"
                )
            cov = cs.get("score_coverage") or {}
            cov_note = ""
            if isinstance(cov, dict) and int(cov.get("properties_missing_score") or 0) > 0:
                cov_note = (
                    f" Averages {int(cov.get('properties_with_score') or 0)} of {int(cov.get('properties_total') or 0)} "
                    f"properties with stored scores; {int(cov.get('properties_missing_score') or 0)} without a stored score."
                )
            cvp_block = f"""
            <b>Portfolio compliance score (CVP headline)</b>{scale_note}: <b>{_professional_compliance_summary_escape_xml(str(disp))}</b><br/>
            <b>Score status:</b> {_professional_compliance_summary_escape_xml(str(st))} &nbsp;|&nbsp; <b>Authority:</b> {_professional_compliance_summary_escape_xml(str(auth))}<br/>
            <b>Last score calculation (persisted batch):</b> {_professional_compliance_summary_escape_xml(lc_display)}{headline_note_html}<br/>
            <i>Scoring contract: {SCORING_SEMANTICS_VERSION}.</i> Headline uses persisted property scores only.{cov_note}
            """
            elements.append(Paragraph("Portfolio compliance score", styles["heading"]))
            elements.append(Paragraph(cvp_block, styles["body"]))
            elements.append(
                Paragraph(
                    "Last score calculation time is when the persisted headline was last computed in the system, "
                    "not when this PDF was generated.",
                    styles["small"],
                )
            )
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
        The following <b>{score_pct}%</b> figure is a <b>requirement-status completion rate</b> from requirements included in this report's scope — not the CVP headline score above.
        Out of <b>{total_reqs}</b> total requirements across <b>{total_props}</b> properties:
        <br/><br/>
        • <b>{compliant}</b> requirements are fully compliant<br/>
        • <b>{expiring}</b> are expiring soon and need renewal<br/>
        • <b>{overdue}</b> are overdue and require immediate attention<br/>
        • <b>{missing_evidence}</b> need evidence or confirmation (missing / pending within that same scope, at export time)
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
        
        prop_table = Table(prop_data, colWidths=[200, 80, 70, 70], repeatRows=1)
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
        doc.build(elements, onFirstPage=on_first, onLaterPages=on_later)
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
