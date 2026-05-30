"""Canonical workflow timer field names — server-side only, set on authoritative transitions."""
from __future__ import annotations

from typing import FrozenSet

# Work order timers
WO_QUOTE_REQUESTED_AT = "quote_requested_at"
WO_AWAITING_QUOTE_SINCE = "awaiting_quote_since"
WO_AWAITING_LANDLORD_QUOTE_RESPONSE_SINCE = "awaiting_landlord_quote_response_since"
WO_AWAITING_CONTRACTOR_QUOTE_REVISION_SINCE = "awaiting_contractor_quote_revision_since"
WO_VISIT_PROPOSED_SINCE = "visit_proposed_since"
WO_AWAITING_VISIT_CONFIRMATION_SINCE = "awaiting_visit_confirmation_since"
WO_AWAITING_VISIT_RESCHEDULE_SINCE = "awaiting_visit_reschedule_since"
WO_WORK_AUTHORISED_SINCE = "work_authorised_since"
WO_COMPLETION_PROOF_PENDING_SINCE = "completion_proof_pending_since"
WO_INVOICE_PENDING_SINCE = "invoice_pending_since"

WORK_ORDER_TIMER_FIELDS: FrozenSet[str] = frozenset(
    {
        WO_QUOTE_REQUESTED_AT,
        WO_AWAITING_QUOTE_SINCE,
        WO_AWAITING_LANDLORD_QUOTE_RESPONSE_SINCE,
        WO_AWAITING_CONTRACTOR_QUOTE_REVISION_SINCE,
        WO_VISIT_PROPOSED_SINCE,
        WO_AWAITING_VISIT_CONFIRMATION_SINCE,
        WO_AWAITING_VISIT_RESCHEDULE_SINCE,
        WO_WORK_AUTHORISED_SINCE,
        WO_COMPLETION_PROOF_PENDING_SINCE,
        WO_INVOICE_PENDING_SINCE,
    }
)

# Contractor onboarding
CTR_PORTAL_INVITE_SENT_AT = "portal_invite_sent_at"
CTR_ACTIVATION_PENDING_SINCE = "activation_pending_since"

# Tenant onboarding
TENANT_PORTAL_INVITE_SENT_AT = "tenant_portal_invite_sent_at"
TENANT_ACTIVATION_PENDING_SINCE = "tenant_activation_pending_since"

# Evidence
DOC_EVIDENCE_UPLOADED_SINCE = "evidence_uploaded_since"
DOC_AWAITING_EVIDENCE_REVIEW_SINCE = "awaiting_evidence_review_since"
DOC_AWAITING_LANDLORD_EVIDENCE_ACTION_SINCE = "awaiting_landlord_evidence_action_since"

# Requirements (property_requirements or embedded)
REQ_OVERDUE_SINCE = "overdue_since"
REQ_UNRESOLVED_SINCE = "unresolved_since"
