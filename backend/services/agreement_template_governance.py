"""
Agreement template governance — block publishing invalid commercial disclosures.

Required commercial placeholders (enabled blocks aggregate text):
- {{onboarding_fee_line}} — onboarding fee disclosure
- {{pilot_offer_line}} — pilot offer disclosure (may render empty for non-pilot)
- {{monthly_fee}} + recurring billing language — subscription disclosure
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

_RECURRING_PATTERNS = (
    re.compile(r"\{\{\s*monthly_fee\s*\}\}", re.I),
    re.compile(r"recurring\s+subscription", re.I),
    re.compile(r"billed\s+on\s+a\s+monthly", re.I),
)


class AgreementTemplateGovernanceError(ValueError):
    def __init__(self, issues: List[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


def _block_text_blob(block: Dict[str, Any]) -> str:
    parts: List[str] = [str(block.get("content") or "")]
    for node in block.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        if str(node.get("type") or "").lower() == "bullet_list":
            parts.extend(str(i) for i in (node.get("items") or []))
        else:
            parts.append(str(node.get("text") or ""))
    return " ".join(parts)


def validate_agreement_template_for_publish(
    content_blocks: List[Dict[str, Any]],
    *,
    require_pilot_disclosures: bool = True,
) -> Tuple[bool, List[str]]:
    """
    Validate template content before publish/activation.

    Returns (valid, issues).
    """
    issues: List[str] = []
    enabled = [b for b in (content_blocks or []) if isinstance(b, dict) and b.get("enabled", True)]
    blob = " ".join(_block_text_blob(b) for b in enabled)

    if "{{onboarding_fee_line}}" not in blob and "onboarding_fee_line" not in blob:
        issues.append("Missing required placeholder: {{onboarding_fee_line}} (onboarding fee disclosure)")

    if require_pilot_disclosures and "{{pilot_offer_line}}" not in blob:
        issues.append("Missing required placeholder: {{pilot_offer_line}} (pilot offer disclosure)")

    has_recurring = any(p.search(blob) for p in _RECURRING_PATTERNS)
    if not has_recurring:
        issues.append(
            "Missing recurring billing disclosure (require {{monthly_fee}} and recurring subscription language)"
        )

    plan_block = next((b for b in enabled if str(b.get("key") or "") == "plan_fees"), None)
    if not plan_block:
        issues.append("Missing required block key: plan_fees (plan and fees section)")

    return (len(issues) == 0, issues)


def assert_agreement_template_publishable(
    content_blocks: List[Dict[str, Any]],
    *,
    require_pilot_disclosures: bool = True,
) -> None:
    valid, issues = validate_agreement_template_for_publish(
        content_blocks, require_pilot_disclosures=require_pilot_disclosures
    )
    if not valid:
        raise AgreementTemplateGovernanceError(issues)
