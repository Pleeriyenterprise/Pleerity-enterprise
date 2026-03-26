"""
Evaluation-style tests: intent routing, tool extractors, catalogue grounding.
Run: pytest tests/test_support_assistant_evaluation.py -q
"""
import pytest

from services.support_assistant_intent import SupportAssistantIntent, classify_support_intent
from services.support_assistant_tools import extract_verification_tokens
from services.support_assistant_catalog import build_approved_knowledge_dict, format_pricing_paragraph_for_prompt


@pytest.mark.parametrize(
    "message,expected",
    [
        ("What is Pleerity?", SupportAssistantIntent.COMPANY_ABOUT),
        ("How much does CVP cost?", SupportAssistantIntent.CVP_PRICING),
        ("I need document packs for my tenancy", SupportAssistantIntent.DOCUMENT_PACKS),
        ("Forgot password", SupportAssistantIntent.PASSWORD_LOGIN),
        ("Where is my invoice", SupportAssistantIntent.RECEIPTS_INVOICES),
        ("Cancel subscription and refund", SupportAssistantIntent.ACCOUNT_BILLING),
        ("Activation email never arrived", SupportAssistantIntent.ONBOARDING_SETUP),
        ("What is a CRN", SupportAssistantIntent.COMPLIANCE_CRN),
        ("The dashboard gives a 500 error", SupportAssistantIntent.TECHNICAL),
        ("I want to speak to a human", SupportAssistantIntent.HUMAN_HANDOFF),
        ("hello", SupportAssistantIntent.GENERAL_CHAT),
    ],
)
def test_intent_classification_snapshot(message, expected):
    intent, conf = classify_support_intent(message, {})
    assert intent == expected
    assert conf >= 0.35


def test_extract_crn_email_order():
    m = "My CRN is PLE-CVP-2026-00099 and email foo@bar.com order PLE-20260301-0002"
    t = extract_verification_tokens(m)
    assert t["crn"] == "PLE-CVP-2026-00099"
    assert t["email"] == "foo@bar.com"
    assert t["order_ref"] == "PLE-20260301-0002"


def test_approved_catalog_has_pricing_keys():
    d = build_approved_knowledge_dict()
    assert d.get("company", {}).get("legal_name")
    assert d.get("frontend_links", {}).get("pricing")
    para = format_pricing_paragraph_for_prompt(d)
    assert para and len(para) > 10
