"""Generate branded PDF for an issued agreement from frozen version + render context."""

from __future__ import annotations

import io
import logging
import re
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

logger = logging.getLogger(__name__)


def merge_placeholders(template: str, ctx: Dict[str, Any] | None) -> str:
    out = str(template or "")
    safe_ctx = ctx if isinstance(ctx, dict) else {}
    for k, v in sorted([(str(k), v) for k, v in safe_ctx.items()], key=lambda kv: len(kv[0]), reverse=True):
        out = out.replace("{{" + k + "}}", "" if v is None else str(v))
    return re.sub(r"\{\{[^}]+\}\}", "", out)


def build_agreement_pdf_from_document(
    *,
    document_structure: Dict[str, Any],
    brand_primary: str = "#0B1D3A",
    footer_text: str = "",
) -> bytes:
    """Build PDF from canonical structured agreement document."""
    buf = io.BytesIO()
    title = str(document_structure.get("title") or "Service Agreement")
    subtitle = str(document_structure.get("subtitle") or "")
    sections = list(document_structure.get("sections") or [])
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title[:120],
    )
    styles = getSampleStyleSheet()
    bp = (brand_primary or "#0B1D3A").strip()
    if not bp.startswith("#"):
        bp = "#" + bp
    try:
        heading_color = colors.HexColor(bp)
    except Exception:
        heading_color = colors.HexColor("#0B1D3A")
    h1 = ParagraphStyle(name="AgH1", parent=styles["Heading1"], textColor=heading_color, spaceAfter=8, fontSize=16)
    h2 = ParagraphStyle(name="AgH2", parent=styles["Heading2"], spaceAfter=6, fontSize=12)
    h3 = ParagraphStyle(name="AgH3", parent=styles["Heading3"], spaceAfter=4, fontSize=10)
    body = ParagraphStyle(name="AgBody", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=8)

    story: list[Any] = [Paragraph(title, h1)]
    if subtitle:
        story.append(Paragraph(subtitle, h2))
    story.append(Spacer(1, 4 * mm))
    for s in sections:
        heading = str(s.get("heading") or "Section")
        story.append(Paragraph(f"<b>{heading}</b>", h2))
        for node in s.get("nodes") or []:
            t = str(node.get("type") or "").lower()
            if t == "subheading":
                story.append(Paragraph(str(node.get("text") or ""), h3))
            elif t == "bullet_list":
                for item in node.get("items") or []:
                    story.append(Paragraph(f"• {str(item)}", body))
            else:
                story.append(Paragraph(str(node.get("text") or ""), body))
        story.append(Spacer(1, 2 * mm))

    if footer_text.strip():
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(f"<i>{footer_text}</i>", body))

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 12 * mm, (footer_text or "")[:200])
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    pdf = buf.getvalue()
    buf.close()
    return pdf


def build_agreement_pdf_bytes(
    *,
    title: str,
    subtitle: str,
    content_blocks: List[Dict[str, Any]],
    render_ctx: Dict[str, Any],
    brand_primary: str = "#0B1D3A",
    footer_text: str = "",
) -> bytes:
    merged_title = merge_placeholders(title, render_ctx)
    merged_subtitle = merge_placeholders(subtitle, render_ctx)
    sections = []
    for b in sorted([b for b in content_blocks if isinstance(b, dict) and b.get("enabled", True)], key=lambda b: int(b.get("order") or 0)):
        sections.append(
            {
                "key": b.get("key") or "",
                "heading": b.get("label") or b.get("key") or "Section",
                "nodes": [{"type": "paragraph", "text": merge_placeholders(str(b.get("content") or ""), render_ctx)}],
            }
        )
    return build_agreement_pdf_from_document(
        document_structure={"title": merged_title, "subtitle": merged_subtitle, "sections": sections},
        brand_primary=brand_primary,
        footer_text=merge_placeholders(footer_text, render_ctx),
    )
