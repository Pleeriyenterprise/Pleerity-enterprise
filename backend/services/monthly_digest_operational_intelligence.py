"""
Monthly Operations Intelligence Digest — presentation layer for client-facing PDF.

Transforms assembly payloads into executive briefing content. Never exposes raw
backend objects, workflow metadata, or registry dumps.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from services.monthly_digest_naming import DIGEST_REPORT_TITLE
from services.scoring_explanation_copy import email_score_delta_line

APPENDIX_MAX_ROWS = 12

# Tokens that must never appear in client-facing digest text.
_FORBIDDEN_LEAK_TOKENS = frozenset(
    {
        "workflow_class",
        "take_action",
        "property_id",
        "requirement_id",
        "handler",
        "provenance",
        "guidance_target",
        "allowed_evidence_modes",
        "canonical_take_action",
        "semantic_state",
        "evidence_authority",
        "evidence_completeness",
    }
)

_INTERNAL_JSON_PATTERN = re.compile(
    r"\{[^{}]*(\"workflow_class\"|\"take_action\"|\"property_id\"|\"route\"|\"handler\"|\"contract\"|\"provenance\")"
)


def _safe_text(value: Any, *, max_len: int = 240) -> str:
    """Coerce to client-safe plain text; reject dict/list serialisation."""
    if value is None:
        return ""
    if isinstance(value, dict) or isinstance(value, list):
        return ""
    s = str(value).strip()
    if not s or s.startswith("{") or s.startswith("["):
        return ""
    if _INTERNAL_JSON_PATTERN.search(s):
        return ""
    return s[:max_len]


def humanize_risk_driver(driver: Any) -> str:
    """Convert a score driver dict (or legacy string) to a briefing line."""
    if isinstance(driver, str):
        t = _safe_text(driver)
        if t and not _INTERNAL_JSON_PATTERN.search(t):
            return t
        return ""
    if not isinstance(driver, dict):
        return ""
    prop = _safe_text(driver.get("property_name") or driver.get("name"), max_len=60)
    req = _safe_text(driver.get("requirement_name"), max_len=80)
    status = _safe_text(driver.get("status"), max_len=32).replace("_", " ").title()
    if prop and req and status:
        return f"{prop} — {req} ({status})"
    if req and status:
        return f"{req} ({status})"
    if prop:
        return f"{prop} — elevated compliance attention"
    return ""


def interpret_evidence_posture(state_raw: str, evidence_raw: str) -> Tuple[str, str]:
    """
    Calm client-facing evidence posture — does not equate missing with non-compliance.
    Returns (short_label, operational_note).
    """
    st = (state_raw or "").strip().lower()
    ev = (evidence_raw or "").strip().lower().replace("_", " ")

    if st in ("compliant", "valid") and ev in ("verified", "verified current", "yes"):
        return "Verified on file", "Accepted evidence recorded for this obligation."
    if ev in ("pending review", "pending", "uploaded", "submitted"):
        return "Pending review", "Evidence submitted; acceptance pending review — not a compliance determination."
    if st in ("pending", "missing") and ev in ("missing", "no", "—", ""):
        return "No accepted evidence", "No accepted evidence on file yet; upload and review may be required."
    if "unverified" in ev or st == "needs confirmation":
        return "Uploaded, unverified", "Document on file awaiting verification or date confirmation."
    if st in ("overdue", "expired"):
        return "Overdue / expired", "Renewal or replacement evidence may be required — review obligation dates."
    if st in ("expiring soon", "expiring_soon"):
        return "Renewal approaching", "Plan renewal before the recorded due date."
    if st == "not required":
        return "Not in scope", "Obligation marked not required for this property."
    return _safe_text(state_raw, max_len=24) or "Under review", "Status reflects recorded obligation and evidence states."


def _count_evidence_postures(model: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for rr in model.get("requirement_rows_pdf") or []:
        if not isinstance(rr, dict):
            continue
        label, _ = interpret_evidence_posture(str(rr.get("state") or ""), str(rr.get("evidence_state") or ""))
        counts[label] += 1
    return dict(counts)


def build_portfolio_stability(model: Dict[str, Any]) -> Dict[str, str]:
    """
    Lightweight portfolio trajectory framing — operational, not promotional.
    Labels: Stable | Improving | Deteriorating | Volatile | Evidence onboarding phase
    """
    deltas = model.get("deltas") or {}
    sd = deltas.get("score_delta")
    overdue = int(model.get("overdue") or 0)
    missing = int(model.get("missing_evidence_count") or 0)
    uploads = int(model.get("documents_uploaded_period") or 0)
    total = int(model.get("total_requirements") or 0)
    valid = int(model.get("valid_count") or model.get("compliant") or 0)
    resolved_n = len(deltas.get("resolved_improved_labels") or [])
    new_risk_n = len(deltas.get("newly_overdue_labels") or [])
    unknown_props = int(model.get("unknown_or_stale_property_count") or 0)

    trajectory = "Stable"
    notes: List[str] = []

    if not deltas.get("has_prior_snapshot"):
        trajectory = "Evidence onboarding phase"
        notes.append("First stored monthly snapshot — trajectory comparison begins next period.")
        if missing > 0 and uploads > 0:
            notes.append("Upload activity is in progress; several obligations await acceptance or review.")
        elif missing > 0:
            notes.append("Evidence gaps remain — this reflects record state, not an automatic non-compliance finding.")
        return {"trajectory": trajectory, "interpretation": " ".join(notes[:2])}

    try:
        d = int(sd) if sd is not None else 0
    except (TypeError, ValueError):
        d = 0

    if resolved_n > 0 and new_risk_n > 0:
        trajectory = "Volatile"
        notes.append("Mixed movement: some obligations strengthened while new exposure appeared.")
    elif d >= 4 and new_risk_n == 0:
        trajectory = "Improving"
        notes.append("Score movement and resolved items indicate strengthening portfolio posture.")
    elif d <= -4 or new_risk_n >= 2:
        trajectory = "Deteriorating"
        notes.append("Score decline or newly overdue items warrant operational review.")
    elif missing > 0 and uploads >= 3 and valid < max(1, total // 2):
        trajectory = "Evidence onboarding phase"
        notes.append("Verification backlog remains while upload activity continues.")
    else:
        trajectory = "Stable"
        notes.append("No material adverse movement against the prior monthly snapshot.")

    if overdue > 0:
        notes.append(f"{overdue} overdue obligation(s) concentrate operational risk.")
    elif missing > 0:
        notes.append(f"{missing} obligation(s) lack accepted evidence — review may be outstanding.")
    if unknown_props > 0:
        notes.append(f"{unknown_props} propert{'y' if unknown_props == 1 else 'ies'} with incomplete score coverage.")

    return {"trajectory": trajectory, "interpretation": " ".join(notes[:3])}


def humanize_recommendation(rec: Any) -> str:
    """Extract human action text from a recommendation dict or string."""
    if isinstance(rec, str):
        return _safe_text(rec)
    if not isinstance(rec, dict):
        return ""
    action = _safe_text(rec.get("action") or rec.get("label") or rec.get("title"))
    if not action:
        return ""
    impact = _safe_text(rec.get("impact"), max_len=40)
    if impact and impact not in action:
        return f"{action} ({impact})"
    return action


def _priority_bucket(priority: Any) -> str:
    p = str(priority or "medium").lower()
    if p in ("critical", "high", "urgent"):
        return "immediate"
    if p in ("low", "informational", "monitor"):
        return "monitoring"
    return "upcoming"


def curate_priority_actions(
    model: Dict[str, Any],
    *,
    max_per_bucket: int = 6,
) -> Dict[str, List[Dict[str, str]]]:
    """
    Deduplicated, grouped priority actions for the next 30 days.
    Returns buckets: immediate, upcoming, monitoring.
    """
    buckets: Dict[str, List[Dict[str, str]]] = {
        "immediate": [],
        "upcoming": [],
        "monitoring": [],
    }
    seen: set = set()

    def _add(bucket: str, *, property_name: str, issue: str, action: str, urgency: str, impact: str) -> None:
        key = (bucket, property_name.lower()[:40], issue.lower()[:60])
        if key in seen:
            return
        seen.add(key)
        if len(buckets[bucket]) >= max_per_bucket:
            return
        buckets[bucket].append(
            {
                "property": property_name or "Portfolio",
                "issue": issue,
                "action": action,
                "urgency": urgency,
                "impact": impact,
            }
        )

    score_block = model.get("score_block") if isinstance(model.get("score_block"), dict) else {}
    for rec in (score_block.get("recommendations") or model.get("top_next_actions") or [])[:12]:
        text = humanize_recommendation(rec)
        if not text:
            continue
        pri = rec.get("priority") if isinstance(rec, dict) else "medium"
        bucket = _priority_bucket(pri)
        display = ""
        if isinstance(rec, dict):
            display = _safe_text(rec.get("display_label"), max_len=60)
        _add(
            bucket,
            property_name=display or "Portfolio",
            issue=text.split("—")[0].strip()[:80] if "—" in text else "Compliance action",
            action=text,
            urgency=bucket.replace("monitoring", "Monitor").title(),
            impact=_safe_text(rec.get("impact") if isinstance(rec, dict) else "", max_len=32) or "Operational",
        )

    for item in model.get("urgent_items") or []:
        if not isinstance(item, dict):
            continue
        line = _safe_text(item.get("line") or item.get("title"))
        if not line:
            continue
        prop = ""
        if "(" in line and line.endswith(")"):
            prop = line[line.rfind("(") + 1 : -1].strip()
            line = line[: line.rfind("(")].strip()
        bucket = "immediate" if "overdue" in line.lower() or "urgent" in line.lower() else "upcoming"
        _add(
            bucket,
            property_name=prop,
            issue=line[:80],
            action="Review in portal and complete the required step.",
            urgency="Immediate" if bucket == "immediate" else "Upcoming",
            impact="Reduces portfolio exposure",
        )

    # Grouped patterns from requirement rows (high-risk only, deduped by type)
    type_groups: Dict[str, List[str]] = defaultdict(list)
    for rr in model.get("requirement_rows_pdf") or []:
        if not isinstance(rr, dict):
            continue
        st = str(rr.get("state") or "").lower()
        if st not in ("overdue", "expired", "missing", "expiring soon", "pending"):
            continue
        name = _safe_text(rr.get("requirement_name"), max_len=48)
        prop = _safe_text(rr.get("property_name"), max_len=48)
        if name and prop:
            type_groups[name].append(prop)

    for req_name, props in sorted(type_groups.items(), key=lambda x: -len(x[1])):
        if len(props) < 2:
            continue
        unique_props = list(dict.fromkeys(props))[:8]
        n = len(unique_props)
        bucket = "immediate" if any(
            str(rr.get("state", "")).lower() in ("overdue", "expired")
            for rr in model.get("requirement_rows_pdf") or []
            if isinstance(rr, dict) and _safe_text(rr.get("requirement_name")) == req_name
        ) else "upcoming"
        _add(
            bucket,
            property_name=f"{n} properties",
            issue=f"{req_name} attention required",
            action=f"Prioritise {req_name.lower()} evidence across {n} properties.",
            urgency="Immediate" if bucket == "immediate" else "Upcoming",
            impact="Concentrated portfolio exposure",
        )

    if not any(buckets.values()):
        buckets["monitoring"].append(
            {
                "property": "Portfolio",
                "issue": "No urgent compliance actions identified",
                "action": "Continue monitoring expiries and maintain verified evidence.",
                "urgency": "Monitor",
                "impact": "Sustains current posture",
            }
        )
    return buckets


def build_risk_highlights(model: Dict[str, Any], *, max_items: int = 6) -> List[str]:
    """Highest-value operational risk patterns — not per-requirement enumeration."""
    highlights: List[str] = []
    seen: set = set()

    score_block = model.get("score_block") if isinstance(model.get("score_block"), dict) else {}
    for driver in (score_block.get("drivers") or [])[:20]:
        line = humanize_risk_driver(driver)
        if line and line not in seen:
            seen.add(line)
            highlights.append(line)
        if len(highlights) >= max_items:
            return highlights

    overdue = int(model.get("overdue") or 0)
    missing = int(model.get("missing_evidence_count") or 0)
    expiring = int(model.get("expiring_soon") or 0)
    critical_props = int(model.get("critical_property_count") or 0)

    if overdue > 0:
        highlights.append(f"{overdue} obligation(s) are overdue or expired across the portfolio.")
    if missing > 0:
        highlights.append(
            f"{missing} obligation(s) have no accepted evidence on file (review may be outstanding)."
        )
    if expiring > 0:
        highlights.append(f"{expiring} renewal(s) approaching within the compliance window.")
    if critical_props > 0:
        highlights.append(f"{critical_props} propert{'y' if critical_props == 1 else 'ies'} at critical risk level.")

    type_missing: Dict[str, int] = defaultdict(int)
    for rr in model.get("requirement_rows_pdf") or []:
        if not isinstance(rr, dict):
            continue
        ev = str(rr.get("evidence_state") or "").lower()
        st = str(rr.get("state") or "").lower()
        if "missing" in ev or st in ("missing", "pending"):
            type_missing[_safe_text(rr.get("requirement_name"), max_len=40) or "Requirement"] += 1
    for name, count in sorted(type_missing.items(), key=lambda x: -x[1])[:3]:
        if count >= 2:
            line = f"{count} properties missing verified {name.lower()} evidence"
            if line not in seen:
                highlights.append(line)

    return highlights[:max_items]


def build_executive_interpretation(model: Dict[str, Any]) -> str:
    """One-paragraph operational synthesis — calm portfolio governance memo tone."""
    stability = build_portfolio_stability(model)
    parts: List[str] = [stability["interpretation"]]

    deltas = model.get("deltas") or {}
    uploads = int(model.get("documents_uploaded_period") or 0)
    resolved = deltas.get("resolved_improved_labels") or []
    newly_overdue = deltas.get("newly_overdue_labels") or []

    if uploads > 0 and resolved:
        parts.append(
            f"{uploads} document upload(s) this period; {len(resolved)} obligation area(s) show strengthened status."
        )
    elif uploads > 0:
        parts.append(f"{uploads} document upload(s) recorded this period.")
    if newly_overdue:
        parts.append(f"{len(newly_overdue)} obligation(s) newly entered an overdue state.")

    postures = _count_evidence_postures(model)
    pending = postures.get("Pending review", 0) + postures.get("Uploaded, unverified", 0)
    if pending > 0:
        parts.append(f"{pending} obligation(s) await evidence review or verification.")

    if len(parts) == 1 and stability["trajectory"] == "Stable":
        return parts[0]
    return " ".join(parts[:4])


def build_what_changed_lines(model: Dict[str, Any]) -> List[str]:
    """Month-on-month change narrative — core digest section."""
    deltas = model.get("deltas") or {}
    lines: List[str] = []
    stability = build_portfolio_stability(model)

    if not deltas.get("has_prior_snapshot"):
        lines.append(
            "Baseline established: this report records portfolio state at month end. "
            "Subsequent digests will compare score movement, exposure, verification progress, and property-level change."
        )
        lines.append(f"Portfolio trajectory: {stability['trajectory']}.")
        uploads = int(model.get("documents_uploaded_period") or 0)
        if uploads:
            lines.append(f"Evidence uploads completed this period: {uploads} document(s).")
        postures = _count_evidence_postures(model)
        if postures.get("Pending review", 0):
            lines.append(
                f"Verification in progress: {postures['Pending review']} obligation(s) await evidence review."
            )
        return lines

    lines.append(f"Portfolio trajectory: {stability['trajectory']}. {stability['interpretation']}")

    sd = deltas.get("score_delta")
    if sd is not None:
        lines.append(email_score_delta_line(sd))

    resolved = deltas.get("resolved_improved_labels") or []
    newly_overdue = deltas.get("newly_overdue_labels") or []
    if resolved:
        lines.append(f"Resolved or strengthened ({len(resolved)}): " + "; ".join(_safe_text(x) for x in resolved[:4] if _safe_text(x)))
    if newly_overdue:
        lines.append(f"New operational risk ({len(newly_overdue)}): " + "; ".join(_safe_text(x) for x in newly_overdue[:4] if _safe_text(x)))

    movement = build_property_movement_rows(model)
    improved = [m["property"] for m in movement if m.get("direction") == "Improved"]
    deteriorated = [m["property"] for m in movement if m.get("direction") == "Deteriorated"]
    if improved:
        lines.append(f"Properties with strengthened posture: {', '.join(improved[:5])}.")
    if deteriorated:
        lines.append(f"Properties requiring attention: {', '.join(deteriorated[:5])}.")

    for label in (deltas.get("newly_expiring_labels") or [])[:3]:
        t = _safe_text(label)
        if t:
            lines.append(f"Renewal window opened: {t}")

    doc_delta = deltas.get("documents_uploaded_delta_vs_prev_period")
    uploads = int(model.get("documents_uploaded_period") or 0)
    if doc_delta is not None:
        try:
            d = int(doc_delta)
            lines.append(f"Evidence uploads vs prior month: {d:+d} ({uploads} this period).")
        except (TypeError, ValueError):
            pass
    elif model.get("include_recent_documents", True):
        lines.append(f"Evidence uploads this period: {uploads}.")

    nmd = deltas.get("newly_missing_evidence_delta")
    if nmd is not None and nmd != 0:
        try:
            n = int(nmd)
            direction = "increased" if n > 0 else "reduced"
            lines.append(f"Unresolved evidence exposure {direction} by {abs(n)} item(s) vs last report.")
        except (TypeError, ValueError):
            pass

    postures = _count_evidence_postures(model)
    pending = postures.get("Pending review", 0)
    unverified = postures.get("Uploaded, unverified", 0)
    if pending or unverified:
        bits = []
        if pending:
            bits.append(f"{pending} pending review")
        if unverified:
            bits.append(f"{unverified} uploaded awaiting verification")
        lines.append("Verification progress: " + ", ".join(bits) + ".")

    if len(lines) <= 2 and sd is None:
        lines.append("No material score or exposure movement against the prior monthly snapshot.")
    return lines


def build_property_movement_rows(model: Dict[str, Any]) -> List[Dict[str, str]]:
    """Portfolio movement table — direction inferred from delta labels."""
    deltas = model.get("deltas") or {}
    resolved_text = " ".join(deltas.get("resolved_improved_labels") or []).lower()
    overdue_text = " ".join(deltas.get("newly_overdue_labels") or []).lower()
    rows: List[Dict[str, str]] = []

    for pr in model.get("property_rows_pdf") or []:
        if not isinstance(pr, dict):
            continue
        name = _safe_text(pr.get("name"), max_len=50) or "Property"
        score = pr.get("score")
        score_disp = str(score) if score is not None else "—"
        risk = _safe_text(pr.get("risk_level"), max_len=20) or "—"
        direction = "Stable"
        key_change = "No material change flagged"
        nl = name.lower()
        if nl and nl in resolved_text:
            direction = "Improved"
            key_change = "Obligations resolved or strengthened"
        elif nl and nl in overdue_text:
            direction = "Deteriorated"
            key_change = "New overdue or missing evidence"
        elif int(pr.get("overdue_count") or 0) > 0:
            direction = "Attention"
            key_change = f"{int(pr.get('overdue_count') or 0)} overdue item(s)"
        elif int(pr.get("missing_evidence_count") or 0) > 0:
            direction = "Attention"
            key_change = f"{int(pr.get('missing_evidence_count') or 0)} without accepted evidence"
        elif int(pr.get("expiring_soon_count") or 0) > 0:
            direction = "Monitor"
            key_change = f"{int(pr.get('expiring_soon_count') or 0)} renewal(s) approaching"

        prev_score = "—"
        if deltas.get("has_prior_snapshot") and score is not None and deltas.get("score_delta") is not None:
            try:
                prev_score = str(int(score) - int(deltas["score_delta"]))
            except (TypeError, ValueError):
                pass

        rows.append(
            {
                "property": name,
                "previous_score": prev_score,
                "current_score": score_disp,
                "direction": direction,
                "key_change": key_change,
            }
        )
    return rows


def build_evidence_activity_summary(model: Dict[str, Any]) -> Dict[str, Any]:
    """Evidence lifecycle summary for the reporting period."""
    deltas = model.get("deltas") or {}
    uploads = int(model.get("documents_uploaded_period") or 0)
    missing = int(model.get("missing_evidence_count") or 0)
    valid = int(model.get("valid_count") or model.get("compliant") or 0)
    total = int(model.get("total_requirements") or 0)
    doc_delta = deltas.get("documents_uploaded_delta_vs_prev_period")

    trend = "steady"
    if doc_delta is not None:
        try:
            d = int(doc_delta)
            trend = "increasing" if d > 0 else "decreasing" if d < 0 else "steady"
        except (TypeError, ValueError):
            pass

    postures = _count_evidence_postures(model)
    pending = postures.get("Pending review", 0)
    unverified = postures.get("Uploaded, unverified", 0)

    lines = [
        f"Documents uploaded this period: {uploads}.",
        f"Obligations with accepted evidence: {valid} of {total}." if total else f"Accepted evidence on {valid} obligation(s).",
    ]
    if missing:
        lines.append(
            f"Obligations without accepted evidence: {missing} (record state — not an automatic non-compliance finding)."
        )
    else:
        lines.append("No obligations flagged without accepted evidence in scope.")
    if pending:
        lines.append(f"Pending evidence review: {pending} obligation(s).")
    if unverified:
        lines.append(f"Uploaded, awaiting verification: {unverified} obligation(s).")
    if doc_delta is not None:
        try:
            lines.append(f"Upload activity vs prior month: {int(doc_delta):+d} ({trend}).")
        except (TypeError, ValueError):
            pass
    return {"trend": trend, "lines": lines}


def build_condensed_appendix_rows(
    model: Dict[str, Any],
    *,
    max_rows: int = APPENDIX_MAX_ROWS,
) -> List[Dict[str, str]]:
    """High-risk obligations only — compact appendix, not full registry dump."""
    rows: List[Dict[str, str]] = []
    for rr in model.get("requirement_rows_pdf") or []:
        if not isinstance(rr, dict):
            continue
        st = str(rr.get("state") or "").lower()
        ev_label, _ = interpret_evidence_posture(str(rr.get("state") or ""), str(rr.get("evidence_state") or ""))
        urgent = st in ("overdue", "expired", "missing", "pending") or "missing" in ev_label.lower()
        if not urgent and st != "expiring soon":
            continue
        rows.append(
            {
                "property": _safe_text(rr.get("property_name"), max_len=40) or "—",
                "obligation": _safe_text(rr.get("requirement_name"), max_len=48) or "—",
                "status": _safe_text(rr.get("state"), max_len=24) or "—",
                "evidence": ev_label[:24],
            }
        )
    rows.sort(key=lambda r: (0 if "overdue" in r["status"].lower() else 1, r["property"]))
    return rows[:max_rows]


def build_trend_indicators(model: Dict[str, Any]) -> Dict[str, str]:
    """Compact trend labels for executive snapshot."""
    deltas = model.get("deltas") or {}
    sd = deltas.get("score_delta")
    score_trend = "Baseline"
    if sd is not None:
        try:
            d = int(sd)
            score_trend = "Improving" if d > 0 else "Declining" if d < 0 else "Stable"
        except (TypeError, ValueError):
            score_trend = "—"

    risk = str(model.get("risk_level") or "—")
    uploads = int(model.get("documents_uploaded_period") or 0)
    doc_delta = deltas.get("documents_uploaded_delta_vs_prev_period")
    upload_trend = "—"
    if doc_delta is not None:
        try:
            upload_trend = "Up" if int(doc_delta) > 0 else "Down" if int(doc_delta) < 0 else "Flat"
        except (TypeError, ValueError):
            pass
    elif uploads:
        upload_trend = "Active"

    resolved_n = len(deltas.get("resolved_improved_labels") or [])
    worsening_n = len(deltas.get("newly_overdue_labels") or [])
    return {
        "score_trend": score_trend,
        "risk_level": risk,
        "upload_activity": upload_trend,
        "resolved_items": str(resolved_n) if deltas.get("has_prior_snapshot") else "—",
        "new_risk_items": str(worsening_n) if deltas.get("has_prior_snapshot") else "—",
    }


def build_digest_intelligence(model: Dict[str, Any]) -> Dict[str, Any]:
    """Full presentation model for Monthly Operations Intelligence Digest PDF."""
    stability = build_portfolio_stability(model)
    return {
        "report_class": DIGEST_REPORT_TITLE,
        "portfolio_stability": stability,
        "executive_interpretation": build_executive_interpretation(model),
        "what_changed": build_what_changed_lines(model),
        "priority_actions": curate_priority_actions(model),
        "risk_highlights": build_risk_highlights(model),
        "property_movement": build_property_movement_rows(model),
        "evidence_activity": build_evidence_activity_summary(model),
        "condensed_appendix": build_condensed_appendix_rows(model),
        "trend_indicators": build_trend_indicators(model),
        "evidence_posture_counts": _count_evidence_postures(model),
    }


def assert_client_safe_text(text: str) -> bool:
    """True when text contains no forbidden internal leakage patterns."""
    if not text:
        return True
    low = text.lower()
    if _INTERNAL_JSON_PATTERN.search(text):
        return False
    for tok in _FORBIDDEN_LEAK_TOKENS:
        if tok in low:
            return False
    return True


def collect_all_client_text(intelligence: Dict[str, Any]) -> str:
    """Flatten intelligence model for leakage tests."""
    chunks: List[str] = [intelligence.get("executive_interpretation") or ""]
    chunks.extend(intelligence.get("what_changed") or [])
    chunks.extend(intelligence.get("risk_highlights") or [])
    chunks.extend((intelligence.get("evidence_activity") or {}).get("lines") or [])
    for bucket in (intelligence.get("priority_actions") or {}).values():
        for item in bucket:
            if isinstance(item, dict):
                chunks.extend(str(v) for v in item.values())
    for row in intelligence.get("property_movement") or []:
        if isinstance(row, dict):
            chunks.extend(str(v) for v in row.values())
    for row in intelligence.get("condensed_appendix") or []:
        if isinstance(row, dict):
            chunks.extend(str(v) for v in row.values())
    return "\n".join(chunks)
