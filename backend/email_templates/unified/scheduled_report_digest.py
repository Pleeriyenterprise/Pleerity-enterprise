"""
Structured scheduled compliance report email body (daily / weekly / requirements).

Replaces raw CSV / ``=== SUMMARY ===`` dumps in customer inboxes. Full tabular exports
belong in the portal or CSV attachments — not the email body.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from email_templates.unified.blocks import (
    bullet_list_html,
    intro_paragraph_html,
    info_panel_html,
    key_value_table_html,
    section_title_html,
)
from presentation.label_service import compliance_requirement_status_label, requirement_label


def _freq_title(frequency: str) -> str:
    f = (frequency or "weekly").strip().lower()
    if f == "daily":
        return "Your daily compliance summary"
    if f == "monthly":
        return "Your monthly compliance overview"
    return "Your weekly compliance overview"


def _human_due(s: Any) -> str:
    if not s or s == "N/A":
        return "—"
    raw = str(s).strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        y, m, d = raw[:10].split("-")
        months = (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
        try:
            mi = int(m)
            di = int(d)
            yi = int(y)
            if 1 <= mi <= 12:
                return f"{di} {months[mi - 1]} {yi}"
        except ValueError:
            pass
    return raw


def _row_label(row: Dict[str, Any]) -> str:
    code = (row.get("requirement_code") or row.get("requirement_type") or "").strip()
    base = requirement_label(code) if code else str(row.get("description") or "Requirement").strip()
    addr = str(row.get("property_address") or "").strip()
    if addr:
        return f"{base} — {addr}"
    return base


def _aggregate_requirement_rows(rows: List[Dict[str, Any]]) -> Tuple[Dict[str, int], List[Dict[str, Any]], List[Dict[str, Any]]]:
    counts: Dict[str, int] = {}
    overdue: List[Dict[str, Any]] = []
    expiring: List[Dict[str, Any]] = []
    for r in rows:
        st = str(r.get("status") or "").upper()
        counts[st] = counts.get(st, 0) + 1
        if st == "OVERDUE":
            overdue.append(r)
        elif st == "EXPIRING_SOON":
            expiring.append(r)
    overdue.sort(key=lambda x: str(x.get("due_date") or ""))
    expiring.sort(key=lambda x: str(x.get("due_date") or ""))
    return counts, overdue[:5], expiring[:4]


def build_scheduled_report_digest_html(model: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (inner_body_html, header_title_for_layout).

    Caller wraps with ``build_customer_email_layout`` / ``_customer_email_html``.
    """
    frequency = str(model.get("frequency") or "weekly")
    header_title = _freq_title(frequency)
    report_type = str(model.get("report_type") or "Compliance report")
    period_label = str(model.get("generated_date") or "").strip() or "today"

    portal = str(model.get("portal_link") or "#").strip()
    summary = model.get("report_summary")
    properties = model.get("properties_snapshot") or []
    rows: List[Dict[str, Any]] = list(model.get("report_rows") or [])

    parts: List[str] = []

    parts.append(
        intro_paragraph_html(
            f"This is your scheduled {report_type.lower()} for the period ending {period_label}. "
            "It highlights what needs attention next — not a full data export."
        )
    )

    if summary and isinstance(summary, dict):
        parts.append(section_title_html("Portfolio snapshot"))
        cb = summary.get("compliance_breakdown") or {}
        rb = summary.get("requirements_breakdown") or {}
        kv: List[Tuple[str, str]] = [
            ("Properties on file", str(summary.get("total_properties", 0))),
            ("Properties — on track (green)", str(cb.get("green", 0))),
            ("Properties — needs attention (amber)", str(cb.get("amber", 0))),
            ("Properties — urgent (red)", str(cb.get("red", 0))),
            ("Requirements — compliant", str(rb.get("compliant", 0))),
            ("Requirements — overdue", str(rb.get("overdue", 0))),
            ("Requirements — due soon", str(rb.get("expiring_soon", 0))),
            ("Requirements — pending / missing evidence", str(rb.get("pending", 0))),
            ("Overall compliance rate", f"{summary.get('compliance_rate', 0)}%"),
        ]
        parts.append(key_value_table_html(kv))
        red_props = [p for p in properties if str(p.get("compliance_status", "")).upper() == "RED"]
        amb_props = [p for p in properties if str(p.get("compliance_status", "")).upper() == "AMBER"]
        priority_lines = []
        for p in red_props[:4]:
            addr = str(p.get("address") or "Property").strip()
            od = p.get("overdue")
            priority_lines.append(f"{addr} — compliance status is red; overdue requirements: {od}.")
        for p in amb_props[:3]:
            if len(priority_lines) >= 5:
                break
            addr = str(p.get("address") or "Property").strip()
            priority_lines.append(f"{addr} — needs attention soon (amber).")
        if priority_lines:
            parts.append(section_title_html("Top priorities"))
            parts.append(bullet_list_html(priority_lines))
        else:
            parts.append(
                info_panel_html(
                    "All clear for now",
                    "<p style=\"margin:0;\">No properties are currently flagged red or amber in this summary. "
                    "Keep evidence up to date so reminders stay quiet.</p>",
                )
            )

    elif rows:
        parts.append(section_title_html("Requirements overview"))
        counts, overdue_top, expiring_top = _aggregate_requirement_rows(rows)
        kv = [
            ("Requirements in this report", str(len(rows))),
            ("Overdue", str(counts.get("OVERDUE", 0))),
            ("Due soon", str(counts.get("EXPIRING_SOON", 0))),
            ("Pending", str(counts.get("PENDING", 0))),
            ("Compliant", str(counts.get("COMPLIANT", 0))),
        ]
        parts.append(key_value_table_html(kv))
        action_lines = []
        for r in overdue_top:
            lbl = _row_label(r)
            due = _human_due(r.get("due_date"))
            st = compliance_requirement_status_label(str(r.get("status") or ""))
            action_lines.append(f"{lbl} — {st}, due {due}.")
        for r in expiring_top:
            if len(action_lines) >= 6:
                break
            lbl = _row_label(r)
            due = _human_due(r.get("due_date"))
            st = compliance_requirement_status_label(str(r.get("status") or ""))
            action_lines.append(f"{lbl} — {st}, due {due}.")
        if action_lines:
            parts.append(section_title_html("Suggested next actions"))
            parts.append(bullet_list_html(action_lines))
        parts.append(
            intro_paragraph_html(
                "Open your portal to review every requirement, upload evidence, and download a full export if you need one."
            )
        )

    else:
        parts.append(
            info_panel_html(
                "Summary unavailable",
                "<p style=\"margin:0;\">We could not attach a structured summary to this message. "
                "Open your portal for the latest compliance view and full reports.</p>",
            )
        )

    parts.append(
        intro_paragraph_html(
            "For spreadsheet or PDF exports, use Reports in your portal — email stays short on purpose."
        )
    )

    inner = "".join(parts)
    return inner, header_title


def build_scheduled_report_digest_text(model: Dict[str, Any]) -> str:
    frequency = str(model.get("frequency") or "weekly")
    title = _freq_title(frequency)
    report_type = str(model.get("report_type") or "Compliance report")
    period_label = str(model.get("generated_date") or "").strip() or "today"
    portal = str(model.get("portal_link") or "#").strip()
    lines = [
        title.upper(),
        "",
        f"Report: {report_type}",
        f"Period: {period_label}",
        "",
        f"This email summarises what needs attention. It is not a full export.",
        "",
    ]
    summary = model.get("report_summary")
    if summary and isinstance(summary, dict):
        cb = summary.get("compliance_breakdown") or {}
        rb = summary.get("requirements_breakdown") or {}
        lines.extend(
            [
                "PORTFOLIO SNAPSHOT",
                f"- Properties: {summary.get('total_properties', 0)}",
                f"- Green / Amber / Red: {cb.get('green', 0)} / {cb.get('amber', 0)} / {cb.get('red', 0)}",
                f"- Requirements compliant: {rb.get('compliant', 0)}",
                f"- Overdue: {rb.get('overdue', 0)}",
                f"- Due soon: {rb.get('expiring_soon', 0)}",
                f"- Pending: {rb.get('pending', 0)}",
                f"- Compliance rate: {summary.get('compliance_rate', 0)}%",
                "",
            ]
        )
    rows = list(model.get("report_rows") or [])
    if rows:
        counts, overdue_top, expiring_top = _aggregate_requirement_rows(rows)
        lines.extend(
            [
                "REQUIREMENTS",
                f"- Total rows: {len(rows)}",
                f"- Overdue: {counts.get('OVERDUE', 0)}",
                f"- Due soon: {counts.get('EXPIRING_SOON', 0)}",
                "",
                "TOP ACTIONS:",
            ]
        )
        for r in overdue_top + expiring_top:
            lines.append(f"* {_row_label(r)} — due {_human_due(r.get('due_date'))}")
        lines.append("")
    lines.extend(
        [
            f"Open portal: {portal}",
            "",
            "Why you received this: scheduled compliance reports are enabled for your account.",
            "",
        ]
    )
    return "\n".join(lines)
