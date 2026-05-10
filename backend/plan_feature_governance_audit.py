"""
L-010e — audited string literals for ``plan_registry.enforce_feature`` and ``require_feature``.

**Governance:** Runtime gates must use feature keys that exist in ``FEATURE_MATRIX`` / ``FEATURE_METADATA``
(see ``services/plan_registry.py``). CI asserts this frozenset ⊆ ``all_feature_matrix_keys()``.

**Maintenance:** When adding ``enforce_feature(..., \"new_key\")`` or ``require_feature(\"new_key\")``,
add ``new_key`` to ``FEATURE_MATRIX`` (all plans) + ``FEATURE_METADATA`` + this frozenset, then run
``tests/test_l010_plan_feature_governance_contract.py``.

**Dynamic keys:** ``notification_orchestrator`` passes ``plan_feature`` from DB template rows — those
values come from ``plan_required_feature_key`` on ``notification_templates`` / seed definitions;
CI covers non-null seed keys separately.
"""

from __future__ import annotations

from typing import FrozenSet

# Audited 2026-05-08: string literal second argument to ``plan_registry.enforce_feature`` in production
# modules (excluding ``services/plan_registry.py`` definition, tests, and duplicate service wrappers).
PRODUCTION_ENFORCE_FEATURE_KEY_LITERALS: FrozenSet[str] = frozenset(
    {
        "ai_extraction_advanced",
        "audit_log_export",
        "compliance_calendar",
        "reports_csv",
        "reports_pdf",
        "scheduled_reports",
        "sms_reminders",
        "tenant_portal",
        "webhooks",
        "white_label_reports",
        "zip_upload",
    }
)

# ``middleware.feature_gating.require_feature("...")`` and bulk-upload route (same mechanism).
PRODUCTION_REQUIRE_FEATURE_KEY_LITERALS: FrozenSet[str] = frozenset(
    {
        "zip_upload",
    }
)
