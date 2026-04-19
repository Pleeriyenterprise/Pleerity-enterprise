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


def merge_placeholders(template: str, ctx: Dict[str, Any]) -> str:
    out = str(template or "")
    for k, v in sorted(ctx.keys(), key=len, reverse=True):
        val = "" if v is None else str(v)
        out = out.replace("{{" + k + "}}", val)
    out = re.sub(r"\{\{[^}]+\}\}", "", out)
    return out


def build_agreement_pdf_bytes(
    *,
    title: str,
    subtitle: str,
    content_blocks: List[Dict[str, Any]],
    render_ctx: Dict[str, Any],
    brand_primary: str = "#0B1D3A",
    footer_text: str = "",
) -> bytes:
    buf = io.BytesIO()
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
    h1 = ParagraphStyle(
        name="AgH1",
        parent=styles["Heading1"],
        textColor=heading_color,
        spaceAfter=8,
        fontSize=16,
    )
    h2 = ParagraphStyle(name="AgH2", parent=styles["Heading2"], spaceAfter=6, fontSize=12)
    body = ParagraphStyle(name="AgBody", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=8)

    story: list[Any] = []
    story.append(Paragraph(merge_placeholders(title, render_ctx), h1))
    if subtitle:
        story.append(Paragraph(merge_placeholders(subtitle, render_ctx), h2))
    story.append(Spacer(1, 4 * mm))

    blocks = sorted(
        [b for b in content_blocks if isinstance(b, dict) and b.get("enabled", True)],
        key=lambda b: int(b.get("order") or 0),
    )
    for b in blocks:
        label = str(b.get("label") or b.get("key") or "Section")
        raw = str(b.get("content") or "")
        merged = merge_placeholders(raw, render_ctx)
        story.append(Paragraph(f"<b>{label}</b>", h2))
        for para in merged.split("\n\n"):
            if para.strip():
                story.append(Paragraph(para.strip().replace("\n", "<br/>"), body))
        story.append(Spacer(1, 3 * mm))

    if footer_text:
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(f"<i>{footer_text}</i>", body))

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 12 * mm, footer_text[:200] if footer_text else "")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    pdf = buf.getvalue()
    buf.close()
    return pdf
