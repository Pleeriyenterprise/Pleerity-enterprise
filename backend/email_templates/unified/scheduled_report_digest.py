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
    obligation = str(row.get("obligation") or "").strip()
    if obligation:
        base = obligation
    else:
        code = (row.get("requirement_code") or row.get("requirement_type") or "").strip()
        base = requirement_label(code) if code else str(row.get("description") or "Requirement").strip()
    addr = str(row.get("property_address") or "").strip()
    if addr:
        return f"{base} — {addr}"
    return base


def _row_due_date(row: Dict[str, Any]) -> Any:
    return row.get("due_date") or row.get("renewal_date")


def _row_status_bucket(row: Dict[str, Any]) -> str:
    """Legacy enum bucket for scheduled digest aggregation."""
    st = str(row.get("status") or "").upper()
    if st in ("OVERDUE", "EXPIRED", "EXPIRING_SOON", "PENDING", "COMPLIANT", "MISSING"):
        if st == "EXPIRED":
            return "OVERDUE"
        if st == "MISSING":
            return "PENDING"
        return st
    triage = str(row.get("triage_category") or "").lower()
    urgency = str(row.get("urgency") or "").lower()
    if "immediate" in triage or urgency == "urgent":
        return "OVERDUE"
    if "renewal" in triage or "upcoming" in triage:
        return "EXPIRING_SOON"
    if "fully compliant" in triage or "monitoring" in triage:
        return "COMPLIANT"
    return "PENDING"


def _aggregate_requirement_rows(rows: List[Dict[str, Any]]) -> Tuple[Dict[str, int], List[Dict[str, Any]], List[Dict[str, Any]]]:
    counts: Dict[str, int] = {}
    overdue: List[Dict[str, Any]] = []
    expiring: List[Dict[str, Any]] = []
    for r in rows:
        st = _row_status_bucket(r)
        counts[st] = counts.get(st, 0) + 1
        if st == "OVERDUE":
            overdue.append(r)
        elif st == "EXPIRING_SOON":
            expiring.append(r)
    overdue.sort(key=lambda x: str(_row_due_date(x) or ""))
    expiring.sort(key=lambda x: str(_row_due_date(x) or ""))
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
    parts.append(
        info_panel_html(
            "How to read this",
            "<p style=\"margin:0;\">Green, amber, and red here are <strong>dashboard operational indicators</strong> from tracked "
            "requirements and evidence recorded in Compliance Vault Pro — not a legal determination. "
            "Figures can change when data updates or scoring recalculates. Your portal is authoritative for current obligation state.</p>",
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
            ("Requirements met (recorded rate)", f"{summary.get('compliance_rate', 0)}%"),
        ]
        ch = summary.get("compliance_score_headline") or {}
        if isinstance(ch, dict) and (ch.get("compliance_score_display") or ch.get("score_status")):
            kv.append(("Portfolio CVP score (headline)", str(ch.get("compliance_score_display") or "N/A")))
            kv.append(("CVP score status", str(ch.get("score_status") or "—")))
            kv.append(("CVP last calculated", str(ch.get("last_calculated_at") or "—")))
        parts.append(key_value_table_html(kv))
        red_props = [p for p in properties if str(p.get("compliance_status", "")).upper() == "RED"]
        amb_props = [p for p in properties if str(p.get("compliance_status", "")).upper() == "AMBER"]
        priority_lines = []
        for p in red_props[:4]:
            addr = str(p.get("address") or "Property").strip()
            od = p.get("overdue")
            priority_lines.append(f"{addr} — dashboard indicator red; overdue tracked requirements: {od}.")
        for p in amb_props[:3]:
            if len(priority_lines) >= 5:
                break
            addr = str(p.get("address") or "Property").strip()
            priority_lines.append(f"{addr} — dashboard indicator amber; review upcoming items in the portal.")
        if priority_lines:
            parts.append(section_title_html("Top priorities"))
            parts.append(bullet_list_html(priority_lines))
        else:
            parts.append(
                info_panel_html(
                    "All clear in this scheduled summary",
                    "<p style=\"margin:0;\">No properties are flagged red or amber in this run’s snapshot. "
                    "Keep evidence up to date in the portal so operational indicators stay current.</p>",
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
            due = _human_due(_row_due_date(r))
            st = str(r.get("operational_status") or "").strip() or compliance_requirement_status_label(
                str(r.get("status") or "")
            )
            action_lines.append(f"{lbl} — {st}, due {due}.")
        for r in expiring_top:
            if len(action_lines) >= 6:
                break
            lbl = _row_label(r)
            due = _human_due(_row_due_date(r))
            st = str(r.get("operational_status") or "").strip() or compliance_requirement_status_label(
                str(r.get("status") or "")
            )
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
        "HOW TO READ THIS:",
        "- Green / amber / red are dashboard operational indicators from tracked requirements — not a legal determination.",
        "- The portal is authoritative for current obligation state and when scores last recalculated.",
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
                f"- Requirements met (recorded rate): {summary.get('compliance_rate', 0)}%",
            ]
        )
        ch = summary.get("compliance_score_headline") or {}
        if isinstance(ch, dict) and (ch.get("compliance_score_display") or ch.get("score_status")):
            lines.append(f"- Portfolio CVP headline: {ch.get('compliance_score_display') or 'N/A'}")
            lines.append(f"- CVP score status: {ch.get('score_status') or '—'}")
            lines.append(f"- CVP last calculated: {ch.get('last_calculated_at') or '—'}")
        lines.append("")
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
            lines.append(f"* {_row_label(r)} — due {_human_due(_row_due_date(r))}")
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
