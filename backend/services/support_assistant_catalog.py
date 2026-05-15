"""
Approved, server-built knowledge for the public support assistant.
All pricing comes from live registries / catalog constants — no invented figures.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

SERVICE_LABELS: Dict[str, str] = {
    "AI_WF_BLUEPRINT": "Workflow Automation Blueprint",
    "AI_PROC_MAP": "Business Process Mapping",
    "AI_TOOL_REPORT": "AI Tool Recommendation Report",
    "MR_BASIC": "Market Research — Basic Report",
    "MR_ADV": "Market Research — Advanced Report",
    "HMO_AUDIT": "HMO Compliance Audit",
    "FULL_AUDIT": "Full Compliance Audit",
    "MOVE_CHECKLIST": "Move-In/Out Checklist",
}


def build_approved_knowledge_dict() -> Dict[str, Any]:
    """
    Single structured object embedded in prompts and parity-checked against retrieval KB.
    """
    from utils.app_urls import get_app_base_url

    base = get_app_base_url(for_email_links=True).rstrip("/")

    # CVP — plan_registry
    cvp_plans: List[str] = []
    try:
        from services.plan_registry import PLAN_DEFINITIONS, PlanCode

        for code in (PlanCode.PLAN_1_SOLO, PlanCode.PLAN_2_PORTFOLIO, PlanCode.PLAN_3_PRO):
            plan = PLAN_DEFINITIONS.get(code, {}) or {}
            name = plan.get("name", code.value)
            monthly = plan.get("monthly_price")
            onboarding = plan.get("onboarding_fee")
            if monthly is not None and onboarding is not None:
                cvp_plans.append(f"{name}: £{float(monthly):.0f}/month + £{float(onboarding):.0f} onboarding")
    except Exception as e:
        logger.warning("support_assistant_catalog: CVP plans unavailable: %s", e)

    # Document packs — pack_registry
    document_packs: Dict[str, Any] = {}
    try:
        from services.pack_registry import PACK_REGISTRY, PACK_ADDONS

        for key, pack in PACK_REGISTRY.items():
            document_packs[key] = {
                "name": pack.get("name"),
                "price_gbp": round(int(pack.get("price_pence", 0)) / 100),
                "document_count": pack.get("document_count"),
            }
        addons = {}
        for code, ad in PACK_ADDONS.items():
            addons[code] = {
                "name": ad.get("name"),
                "price_gbp": round(int(ad.get("price_pence", 0)) / 100),
            }
    except Exception as e:
        logger.warning("support_assistant_catalog: pack registry unavailable: %s", e)
        addons = {}

    # Other services — SERVICE_BASE_PRICES (intake_draft_service)
    other_services: List[Dict[str, Any]] = []
    try:
        from services.intake_draft_service import SERVICE_BASE_PRICES

        for code, pence in sorted(SERVICE_BASE_PRICES.items()):
            if code.startswith("DOC_PACK"):
                continue
            other_services.append({
                "code": code,
                "name": SERVICE_LABELS.get(code, code),
                "price_gbp": round(int(pence) / 100),
            })
    except Exception as e:
        logger.warning("support_assistant_catalog: service prices unavailable: %s", e)

    support_email = __import__("os").environ.get("SUPPORT_EMAIL", "info@pleerityenterprise.co.uk")
    support_whatsapp = __import__("os").environ.get("SUPPORT_WHATSAPP_NUMBER", "+447440645017")

    return {
        "company": {
            "legal_name": "Pleerity Enterprise Ltd",
            "focus": "Property compliance and business services for landlords and property managers",
            "support_email": support_email,
            "support_whatsapp": support_whatsapp,
        },
        "frontend_links": {
            "client_signin": f"{base}/login/client",
            "pricing": f"{base}/pricing",
            "compliance_vault_landing": f"{base}/compliance-vault-pro",
            "services": f"{base}/services",
            "dashboard": f"{base}/dashboard",
            "risk_check": f"{base}/risk-check",
        },
        "compliance_vault_pro": {
            "summary": (
                "Compliance Vault Pro helps UK landlords and agents track property compliance in one place: "
                "add properties, upload certificates and evidence, see requirement statuses and renewal dates, "
                "get reminders before things expire, monitor portfolio compliance from a dashboard, "
                "and pull reports or audit packs when preparing for inspections or lender questions."
            ),
            "workflow_examples": [
                "Upload a gas safety or EICR certificate and see it tied to the property record",
                "Check which requirements are due soon on the renewals calendar",
                "Review compliance score drivers before an inspection — score is a risk indicator, not legal advice",
                "Download a report or audit pack for your records",
            ],
            "grounding_topics": {
                "compliance_score": (
                    "Score reflects requirement status and evidence on file in CVP — a risk indicator, "
                    "not legal advice. Drivers show what is missing, due soon, or expired."
                ),
                "evidence_upload": (
                    "Upload PDFs or images per property; requirements update when evidence is linked. "
                    "After upload, staff or AI review may apply depending on plan."
                ),
                "requirement_status": (
                    "Each requirement shows statuses such as compliant, due soon, overdue, or missing — "
                    "based on records in the platform, not a council decision."
                ),
                "plan_comparison": (
                    "Compare plans using PLAN_FEATURE_FACTS only — property limits and listed features per tier. "
                    "Do not assume Professional features on Solo or Portfolio unless listed."
                ),
                "tenant_portal": (
                    "Tenant portal (Professional plan) gives tenants read-only visibility — not on Solo/Portfolio. "
                    "Confirm in plan_feature_facts before stating availability."
                ),
            },
            "plans_text": " | ".join(cvp_plans) if cvp_plans else None,
        },
        "document_packs": {"tiers": document_packs, "addons": addons},
        "other_services": other_services,
        "policies": {
            "password_reset": "Use 'Forgot password?' on the client sign-in page with your email, or ask your organisation admin to resend a setup link from the CVP admin portal. Reset/setup links typically expire after 1 hour.",
            "billing_payments": "Card payments via Stripe (PCI). Subscription management and receipts are available in the client portal under Billing when logged in.",
            "invoices_receipts": "Order confirmations and subscription receipts are available in the portal Billing section after sign-in. For checkout purchases, use the order reference from your confirmation email.",
            "order_status": "Signed-in users: Dashboard → My Orders. Otherwise provide order reference plus the email used at purchase for verification.",
            "human_support": "Live agents Mon–Fri 9am–6pm GMT; chat widget handoff, email ticket, or WhatsApp with your conversation reference.",
            "resend_activation": "Account activation and admin setup emails can only be resent by a user with admin access to your organisation in the CVP admin portal, or by our support team after verification — the public chat cannot trigger sends.",
            "no_legal_advice": "We do not interpret law or predict enforcement; use a qualified solicitor or council licensing for legal questions.",
        },
    }


def format_cvp_product_context_for_prompt(snapshot: Dict[str, Any]) -> str:
    """Practical CVP product context for explanations (not pricing)."""
    cvp = snapshot.get("compliance_vault_pro") or {}
    lines = []
    if cvp.get("summary"):
        lines.append(f"CVP overview: {cvp['summary']}")
    for ex in cvp.get("workflow_examples") or []:
        lines.append(f"Example: {ex}")
    for key, text in (cvp.get("grounding_topics") or {}).items():
        lines.append(f"{key}: {text}")
    return "\n".join(lines)[:6000]


def format_pricing_paragraph_for_prompt(snapshot: Dict[str, Any]) -> str:
    """Compact text block for LLM system prompt."""
    cvp = snapshot.get("compliance_vault_pro") or {}
    parts = []
    product_ctx = format_cvp_product_context_for_prompt(snapshot)
    if product_ctx:
        parts.append(product_ctx)
    if cvp.get("plans_text"):
        parts.append(f"CVP plans (pricing): {cvp['plans_text']}")
    dp = snapshot.get("document_packs") or {}
    tiers = dp.get("tiers") or {}
    if tiers:
        line = ", ".join(
            f"{v.get('name') or k}: £{v.get('price_gbp', 0)} ({v.get('document_count', '?')} documents)"
            for k, v in tiers.items()
        )
        parts.append(f"Document packs: {line}")
    addons = dp.get("addons") or {}
    if addons:
        al = ", ".join(f"{v.get('name')} +£{v.get('price_gbp', 0)}" for v in addons.values())
        parts.append(f"Pack add-ons: {al}")
    for row in snapshot.get("other_services") or []:
        parts.append(f"{row.get('name')}: £{row.get('price_gbp')}")
    return "\n".join(parts) if parts else "(pricing unavailable — direct user to Pricing page)"
