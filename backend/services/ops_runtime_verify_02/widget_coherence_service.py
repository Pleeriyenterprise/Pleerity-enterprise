"""
G2 widget-island / cross-widget coherence framework.
"""
from __future__ import annotations

from typing import Dict, List, Tuple


class WidgetCoherenceService:
    def build_matrix(self, widgets: List[Dict[str, object]]) -> Dict[str, object]:
        pairs: List[Dict[str, object]] = []
        islands: List[Dict[str, object]] = []
        for i, a in enumerate(widgets):
            for b in widgets[i + 1 :]:
                coherent, note = self._pair_coherent(a, b)
                pairs.append(
                    {
                        "a": a.get("id"),
                        "b": b.get("id"),
                        "coherent": coherent,
                        "note": note,
                    }
                )
                if not coherent:
                    islands.append(
                        {
                            "widgets": [a.get("id"), b.get("id")],
                            "classification_hint": "WIDGET_ISLAND_FAILURE",
                        }
                    )
        return {
            "widgets": widgets,
            "cross_widget_pairs": pairs,
            "island_failures": islands,
            "classification_hints": ["WIDGET_ISLAND_FAILURE", "COGNITIVE_TRUST_RISK"] if islands else [],
        }

    def _pair_coherent(self, a: Dict[str, object], b: Dict[str, object]) -> Tuple[bool, str]:
        ma = a.get("metrics") or {}
        mb = b.get("metrics") or {}
        # critical vs zero urgent
        crit_a = int(ma.get("critical_count", 0) or 0)
        urgent_b = int(mb.get("urgent_actions", 0) or 0)
        if crit_a > 0 and urgent_b == 0 and b.get("id") == "attention":
            return False, "critical_count>0 but urgent_actions=0"
        open_a = int(ma.get("open_issues", 0) or 0)
        health = str(mb.get("health", "")).lower()
        if open_a > 0 and health == "healthy" and b.get("id") == "property_health":
            return False, "open issues but property health healthy"
        return True, ""
