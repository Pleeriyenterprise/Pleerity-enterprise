"""
Explanation Engine — Explainability layer for Pleerity.
Generates contextual explanations for risk signals, compliance alerts, contractor scores,
and related insights. Each explanation includes explanation_text, why_it_matters, and recommended_action_text.
"""
from typing import Any, Dict, Optional

from presentation.label_service import recommended_action_client_text, risk_type_client_label

# --- Output shape ---
def _out(explanation_text: str, why_it_matters: str, recommended_action_text: str) -> Dict[str, Any]:
    return {
        "explanation_text": explanation_text,
        "why_it_matters": why_it_matters,
        "recommended_action_text": recommended_action_text,
    }


# ---------- Risk signals ----------
def explain_risk_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate explanation for a risk signal.
    Uses risk_type, reasons, recommended_action, and optional metadata (e.g. asset age).
    """
    risk_type = (signal.get("risk_type") or "").strip()
    reasons = signal.get("reasons") or []
    recommended = (signal.get("recommended_action") or "").strip()
    rec_client = (signal.get("recommended_action_client") or "").strip()
    if rec_client:
        recommended_action_text = rec_client
    elif recommended:
        recommended_action_text = recommended if recommended.endswith(".") else f"{recommended}."
    else:
        recommended_action_text = recommended_action_client_text(risk_type, "")
    level = (signal.get("risk_level") or "medium").lower()

    # Build why_it_matters from type-specific context + reasons
    why_parts = []
    if risk_type == "Boiler Failure Risk":
        why_parts.append(
            "Boilers older than 12 years fail significantly more often. "
            "Recurring heating issues or work orders increase the chance of emergency failure."
        )
        if reasons:
            why_parts.append(" " + " ".join(reasons[:2]))
    elif risk_type == "Damp / Moisture Risk":
        why_parts.append(
            "Recurring damp or moisture issues can indicate underlying problems and affect tenant health and property condition."
        )
        if reasons:
            why_parts.append(" " + " ".join(reasons[:2]))
    elif risk_type == "Electrical Risk":
        why_parts.append(
            "Electrical issues and overdue EICR increase fire and safety risk. Timely inspection helps avoid liability."
        )
        if reasons:
            why_parts.append(" " + " ".join(reasons[:2]))
    elif risk_type in ("Recurring Repairs Risk", "Recurring Repairs"):
        why_parts.append(
            "Repeated issues on the same asset or category suggest root causes that patch repairs may not fix."
        )
        if reasons:
            why_parts.append(" " + " ".join(reasons[:1]))
    elif risk_type in ("SLA Breach Risk", "SLA Breach"):
        why_parts.append(
            "Missed response or completion deadlines can affect tenant satisfaction and regulatory expectations."
        )
        if reasons:
            why_parts.append(" " + " ".join(reasons[:2]))
    elif risk_type in ("Compliance Churn Risk", "Compliance Churn"):
        why_parts.append(
            "Frequent compliance status changes can indicate missing evidence or expiring certificates that need attention."
        )
        if reasons:
            why_parts.append(" " + " ".join(reasons[:1]))
    elif risk_type == "Certificate Expiry Soon":
        why_parts.append(
            "Certificates expiring soon may lead to non-compliance if not renewed and evidence uploaded in time."
        )
        if reasons:
            why_parts.append(" " + " ".join(reasons[:1]))
    elif risk_type in ("Maintenance Frequency Risk", "Maintenance Frequency"):
        why_parts.append(
            "High maintenance frequency can indicate ageing assets or underlying defects that warrant inspection."
        )
        if reasons:
            why_parts.append(" " + " ".join(reasons[:1]))
    else:
        if reasons:
            why_parts.append(" ".join(reasons[:3]))
        else:
            why_parts.append("This signal was raised based on property data and may require follow-up to reduce risk.")

    why_it_matters = "".join(why_parts).strip() or "This signal highlights an area that may need attention to reduce risk."
    client_rt = (signal.get("risk_type_label_client") or "").strip() or risk_type_client_label(risk_type)
    desc = (signal.get("description") or "").strip()
    lead = desc if desc else client_rt
    explanation_text = f"{lead}. {why_it_matters}".strip() if lead else why_it_matters

    out = _out(explanation_text, why_it_matters, recommended_action_text)
    try:
        from services.operational_value_compression_service import classify_risk_consequence

        out["operational_consequence"] = classify_risk_consequence(signal)
    except Exception:
        pass
    return out


# ---------- Compliance alerts (per requirement) ----------
def explain_compliance_alert(requirement: Dict[str, Any], catalog_entry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generate explanation for a compliance requirement (e.g. expiring certificate, overdue, missing).
    Includes legal/regulatory context where applicable.
    """
    code = (requirement.get("requirement_code") or requirement.get("requirement_type") or "").strip().lower()
    status = (requirement.get("status") or "").strip().upper()
    title = (catalog_entry or {}).get("title") or (requirement.get("category") or code or "Requirement")
    if isinstance(title, str):
        title = title.strip()

    # Legal context and risk by requirement type (UK-oriented; generic where needed)
    legal_context = ""
    risk_of_non_compliance = "Non-compliance can lead to fines, invalid insurance, or legal liability."
    if code in ("gas_safety", "gas safety", "cp12"):
        legal_context = "UK law requires annual gas safety inspections by a Gas Safe registered engineer. A valid certificate must be provided to tenants."
        risk_of_non_compliance = "If the certificate expires while a tenant occupies the property, you may face fines or legal liability."
    elif "eicr" in code:
        legal_context = "Electrical Installation Condition Reports are required for rental properties at least every 5 years (England)."
        risk_of_non_compliance = "Missing or overdue EICR can affect tenant safety and leave you exposed to enforcement action."
    elif code in ("epc",):
        legal_context = "An Energy Performance Certificate is required for rental properties; minimum E rating applies."
        risk_of_non_compliance = "Letting without a valid EPC can result in penalties."
    elif code in ("hmo_license", "hmo licence"):
        legal_context = "An HMO licence is mandatory for properties that meet the licensing criteria in your area."
        risk_of_non_compliance = "Operating an unlicensed HMO can lead to significant fines and rent repayment orders."
    elif code in ("fire_risk_assessment", "fire_alarm", "fire alarm"):
        legal_context = "Fire safety requirements (e.g. risk assessment, alarm inspection) are required for many rental and HMO properties."
        risk_of_non_compliance = "Failure to comply can result in enforcement and liability in the event of fire."
    else:
        legal_context = "This requirement is part of your compliance framework. Keeping evidence up to date helps maintain your score and reduces risk."

    if status in ("OVERDUE", "EXPIRED"):
        why_it_matters = f"{legal_context} {risk_of_non_compliance} This item is overdue or expired."
    elif status == "EXPIRING_SOON":
        why_it_matters = f"{legal_context} {risk_of_non_compliance} This item is expiring soon; renew and upload evidence before the due date."
    elif status in ("PENDING", "MISSING"):
        why_it_matters = f"{legal_context} Evidence or documentation is missing. {risk_of_non_compliance}"
    else:
        why_it_matters = f"{legal_context} {risk_of_non_compliance}"

    explanation_text = f"{title}: {why_it_matters}"

    if status in ("OVERDUE", "EXPIRED"):
        recommended_action_text = "Upload the certificate or evidence and update the due date, or mark as not applicable if appropriate."
    elif status == "EXPIRING_SOON":
        if "gas" in code:
            recommended_action_text = "Schedule a Gas Safe inspection and upload the new certificate when complete."
        elif "eicr" in code:
            recommended_action_text = "Arrange an EICR inspection and upload the report when complete."
        else:
            recommended_action_text = "Schedule the required inspection or renewal and upload evidence when complete."
    elif status in ("PENDING", "MISSING"):
        recommended_action_text = "Upload the required document or evidence for this requirement."
    else:
        recommended_action_text = "Review this requirement and upload or confirm evidence as needed."

    return _out(explanation_text, why_it_matters, recommended_action_text)


# ---------- Contractor score ----------
def explain_contractor_score(contractor: Dict[str, Any]) -> Dict[str, Any]:
    """
    Explain how contractor performance/reliability score is calculated and what it means.
    """
    performance_score = contractor.get("performance_score")
    reliability = contractor.get("reliability_score")
    if performance_score is None and reliability is None:
        return _out(
            "This contractor does not have a score yet.",
            "Scores are calculated from completed jobs, response times, SLA success, and invoice approval. Assign and complete jobs to see a score.",
            "Assign jobs and complete them to build a reliability and performance score.",
        )

    score = performance_score if performance_score is not None else (round((reliability or 0) * 100) if reliability is not None else None)
    if score is None:
        score = 0
    else:
        score = round(score)

    why_it_matters = (
        "This contractor's score is based on: reliability (completed jobs vs assigned), "
        "SLA success rate, response time, and invoice approval rate. "
        "Higher-scoring contractors tend to complete jobs faster and with fewer disputes."
    )
    if score >= 85:
        usage = "Well suited for urgent and high-priority work."
    elif score >= 70:
        usage = "Consider contractors with scores above 85% for the most urgent work."
    elif score >= 50:
        usage = "Consider for non-urgent work; monitor performance."
    else:
        usage = "Consider reassigning critical work to higher-scoring contractors where possible."

    recommended_action_text = usage
    explanation_text = f"Contractor reliability/performance score: {score}%. {why_it_matters} {usage}"

    return _out(explanation_text, why_it_matters, recommended_action_text)


# ---------- Compliance score (portfolio) — can delegate to existing trend ----------
def explain_compliance_score(client_id: str, score_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Explanation for overall compliance score. Prefer using compliance_trending.get_score_change_explanation
    for trend; this provides a static summary when no trend is requested.
    """
    if not score_data:
        return _out(
            "Your compliance score reflects how many requirements are met across your portfolio.",
            "Scores are based on evidence status: compliant, expiring soon, overdue, or missing. Higher scores mean better standing and lower risk.",
            "Keep certificates and evidence up to date; address overdue and expiring items to improve your score.",
        )
    score = score_data.get("score")
    breakdown = score_data.get("breakdown") or score_data.get("stats") or {}
    why_it_matters = (
        "Your score is driven by the number of compliant requirements versus overdue, expiring, or missing evidence. "
        "Addressing overdue and expiring items will improve your score and reduce risk."
    )
    recommended_action_text = "Review overdue and expiring-soon items; upload evidence and renew certificates before due dates."
    explanation_text = f"Portfolio compliance score: {score}. {why_it_matters}"
    return _out(explanation_text, why_it_matters, recommended_action_text)
