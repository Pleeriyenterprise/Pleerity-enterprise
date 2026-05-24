"""
G1 attention authority evaluation framework.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# Precedence rank (lower = higher priority)
ATTENTION_PRECEDENCE = {
    "overdue_remediation": 1,
    "active_risk": 2,
    "open_operational_debt": 3,
    "time_bound_reminder": 4,
    "informational": 5,
}


class AttentionAuthorityService:
    def evaluate_order(self, items: List[Dict[str, object]]) -> Dict[str, object]:
        violations: List[Dict[str, object]] = []
        ordered = sorted(
            items,
            key=lambda x: (
                ATTENTION_PRECEDENCE.get(str(x.get("class", "informational")), 99),
                x.get("urgency_rank", 99),
                x.get("position", 99),
            ),
        )
        for i in range(len(items) - 1):
            a, b = items[i], items[i + 1]
            ra = ATTENTION_PRECEDENCE.get(str(a.get("class", "informational")), 99)
            rb = ATTENTION_PRECEDENCE.get(str(b.get("class", "informational")), 99)
            if ra > rb:
                violations.append(
                    {
                        "type": "ATTENTION_PRIORITY_DRIFT",
                        "lower_item": a.get("id"),
                        "higher_item": b.get("id"),
                        "note": "Displayed order violates precedence",
                    }
                )
        badge_conflicts = self._badge_contradictions(items)
        snooze_checks = self._snooze_checks(items)
        dismiss_checks = self._dismiss_checks(items)
        return {
            "ordered_items": items,
            "expected_order_ids": [x.get("id") for x in ordered],
            "precedence_violations": violations,
            "cross_badge_contradictions": badge_conflicts,
            "snooze_expiry_checks": snooze_checks,
            "dismiss_resurrection_checks": dismiss_checks,
            "classification_hints": self._hints(violations, badge_conflicts, dismiss_checks),
        }

    def _badge_contradictions(self, items: List[Dict[str, object]]) -> List[Dict[str, object]]:
        out = []
        for it in items:
            badges = it.get("badges") or []
            if isinstance(badges, list) and len(set(badges)) > 1:
                if "critical" in badges and "informational" in badges:
                    out.append({"id": it.get("id"), "badges": badges, "type": "OPERATIONAL_ATTENTION_CONTRADICTION"})
        return out

    def _snooze_checks(self, items: List[Dict[str, object]]) -> List[Dict[str, object]]:
        out = []
        for it in items:
            if it.get("snoozed") and not it.get("snooze_expires_at"):
                out.append({"id": it.get("id"), "issue": "snoozed_without_expiry"})
        return out

    def _dismiss_checks(self, items: List[Dict[str, object]]) -> List[Dict[str, object]]:
        out = []
        for it in items:
            if it.get("dismissed_in_ui") != it.get("dismissed_in_api"):
                out.append({"id": it.get("id"), "type": "OPERATIONAL_ATTENTION_CONTRADICTION"})
        return out

    def _hints(self, violations, badge_conflicts, dismiss_checks) -> List[str]:
        hints = []
        if violations:
            hints.append("ATTENTION_PRIORITY_DRIFT")
        if badge_conflicts or dismiss_checks:
            hints.append("OPERATIONAL_ATTENTION_CONTRADICTION")
        return hints
