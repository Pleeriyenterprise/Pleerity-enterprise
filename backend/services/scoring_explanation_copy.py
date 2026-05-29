"""
Customer-facing compliance score explanation copy (PDF, KB, assistant).
Operational and human-readable — no internal weighting or model architecture.
Aligned with frontend/src/utils/scoringExplanationCopy.js
"""
from typing import Any

SCORE_AREA_LABELS = {
    "legal_core": "Core legal requirements",
    "documentation_completeness": "Accepted evidence",
    "operational_responsiveness": "Maintenance & actions",
    "recency_maintenance_confidence": "Up-to-date records",
}

SCORE_AREA_DESCRIPTIONS = {
    "legal_core": (
        "Key certificates and legal obligations for your property and area. "
        "Accepted, in-date evidence helps; missing, overdue, or expiring items lower this."
    ),
    "documentation_completeness": (
        "How many required items have evidence that has been accepted — "
        "uploads alone may not count until review is complete."
    ),
    "operational_responsiveness": (
        "Open maintenance issues and overdue actions can lower your score until they are resolved."
    ),
    "recency_maintenance_confidence": (
        "Items due soon and open follow-ups can lower your score until renewals or reviews are complete."
    ),
}

SCORE_COMPONENTS_SECTION_TITLE = "How you're doing in each area"

SCORE_COMPONENTS_SECTION_INTRO = (
    "These percentages show how well you are meeting each part of your compliance picture right now — "
    "based on your current records, not a fixed formula you can reverse-engineer from counts alone."
)

SCORE_COMPONENTS_FALLBACK = (
    "Area-by-area scores appear here once each property has been fully assessed. "
    "The headline score and recommended actions still reflect your current records."
)

SCORE_HEADLINE_DISCLAIMER = "Guidance based on your records in the portal. Not legal advice."

SCORE_FRAMEWORK_DISCLAIMER = (
    "This score is guidance based on your records in the portal. "
    "It is not legal advice and does not certify compliance."
)

SCORE_METHODOLOGY_INTRO = (
    "Your score is based on your current requirements, documents, dates, and maintenance status. "
    "It updates when those records change."
)

SCORE_METHODOLOGY_PORTFOLIO = (
    "If you have more than one property, your overall score is the average of each property's score."
)

SCORE_ADVANCED_DETAILS_BODY = [
    "Your score improves when required documents are uploaded and accepted, dates are confirmed, "
    "overdue items are cleared, and renewals are kept current.",
    "Your score can fall when evidence is missing or not yet accepted, items become overdue or due soon, "
    "or maintenance issues and linked actions stay open.",
    "Accepted evidence means a document has passed review or external verification — "
    "an upload on its own may not be enough until it is accepted.",
    SCORE_METHODOLOGY_PORTFOLIO,
]

SCORE_SCOPE_INCLUDED = (
    "Applicable requirements for each property (for example gas safety, EICR, EPC, and licence where configured)."
)

SCORE_SCOPE_EXCLUDED = (
    "Local council rules unless configured, optional uploads you chose not to track, "
    "and evidence not yet uploaded or accepted."
)

SCORE_DEFINITIONS_VALID = (
    "The requirement is current and within date; documents are accepted where required."
)

SCORE_DEFINITIONS_EXPIRING = (
    "The due or expiry date is approaching (typically within the next 30–60 days, depending on the requirement)."
)

SCORE_DEFINITIONS_OVERDUE = "The due or expiry date has passed — action is needed."

SCORE_DEFINITIONS_UPDATES = (
    "The score refreshes when documents, dates, applicability, or status change. "
    "The headline may update shortly after you make changes."
)

SCORE_PDF_METHODOLOGY_SUMMARY = (
    "Your score reflects required documents, accepted evidence, overdue or expiring items, "
    "and open maintenance work based on your records at the time this report was generated. "
    "It is operational guidance — not legal advice or a compliance certificate."
)

SCORE_CHANGE_DIRECTIONAL_UP = "Your compliance score improved based on your latest records."

SCORE_CHANGE_DIRECTIONAL_DOWN = "Your compliance score decreased based on your latest records."

SCORE_CHANGE_DIRECTIONAL_GENERIC = "Your compliance score was refreshed based on your latest records."

SCORE_EMAIL_DELTA_IMPROVED = "Your compliance score improved since your last report."

SCORE_EMAIL_DELTA_DECREASED = "Your compliance score decreased since your last report."

SCORE_EMAIL_DELTA_GENERIC = "Your compliance score was updated since your last report."

KB_COMPLIANCE_SCORE_EXPLAINED = """## Understanding your compliance score

Your **compliance score** (0–100) is guidance based on what the portal knows about your properties today. It is **not legal advice** and does not certify compliance.

### What affects your score

- **Required documents and accepted evidence** — uploads help, but evidence usually needs to be **accepted** after review before it fully counts.
- **Overdue or expiring items** — past-due or soon-due requirements can lower your score until they are resolved.
- **Maintenance and open actions** — unresolved maintenance issues or linked actions can reduce your score.
- **Property records** — each property is assessed from its own requirements; if you have several properties, your overall score is the **average** of their scores.

### What improves your score

Upload and get documents **accepted**, confirm dates, clear overdue items, and keep renewals current. Use **Quick Actions** on the Dashboard, **Score drivers** on the Compliance score page, and the **Requirements** list to see what to fix first.

### Why your score may not change immediately after an upload

Review, date confirmation, or background refresh may still be in progress. Check the requirement and document status, then refresh after a few minutes.

### Where to learn more

Open **Compliance score** in the portal for your current score, area breakdown, and definitions. Use **Documents** and **Requirements** to complete the work that moves the score."""


ASSISTANT_HOW_SCORING_WORKS = """# How compliance scoring works (customer guidance)

Compliance Vault Pro shows a **compliance score** (0–100) for each property and for your portfolio. The score reflects what the portal is tracking based on requirements and evidence—it is **not a legal opinion**.

## What the score reflects

- Required documents and **accepted** evidence (uploads alone may not count until accepted)
- Overdue or expiring requirements
- Open maintenance issues and linked actions where applicable
- Current dates and requirement status on file

## Portfolio vs property

Each **property** has its own score. If you have more than one property, the **portfolio** score is the average of those property scores.

## How to explain a score to a user

Use plain language tied to their records, for example:

- "Some requirements still need accepted evidence."
- "One or more items are overdue or due soon."
- "Open maintenance work may be affecting this property."
- "Your score will refresh after the next update once records change."

Do **not** quote internal weights, formulas, model versions, or point allocations.

## Important

The score updates when requirements, documents, or dates change. It may not change instantly after every upload. It does not guarantee legal compliance."""


def score_change_narrative(delta: Any) -> str:
    """Directional customer copy for score deltas — no pseudo-precision."""
    if delta is None:
        return SCORE_CHANGE_DIRECTIONAL_GENERIC
    try:
        d = int(delta)
    except (TypeError, ValueError):
        return SCORE_CHANGE_DIRECTIONAL_GENERIC
    if d == 0:
        return SCORE_CHANGE_DIRECTIONAL_GENERIC
    if d > 0:
        return SCORE_CHANGE_DIRECTIONAL_UP
    return SCORE_CHANGE_DIRECTIONAL_DOWN


def email_score_delta_line(delta: Any) -> str:
    """Digest email — directional score movement without point arithmetic."""
    if delta is None:
        return SCORE_EMAIL_DELTA_GENERIC
    try:
        d = int(delta)
    except (TypeError, ValueError):
        return SCORE_EMAIL_DELTA_GENERIC
    if d > 0:
        return SCORE_EMAIL_DELTA_IMPROVED
    if d < 0:
        return SCORE_EMAIL_DELTA_DECREASED
    return SCORE_EMAIL_DELTA_GENERIC


