"""Phase 2E acceptance helpers — coverage thresholds and validation aggregation."""
from __future__ import annotations

from typing import Any, Dict, List

DEFERRED_P2_IDS = frozenset({"P2-02", "P2-11", "P2-12", "P2-15", "P2-18", "P2-19", "P2-20"})


def evaluate_mutation_coverage(registry: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate P0/P1/P2 registry coverage against Refinement-02 thresholds."""
    by_priority: Dict[str, List[Dict[str, Any]]] = {"P0": [], "P1": [], "P2": []}
    for entry in registry:
        pri = entry.get("priority")
        if pri in by_priority:
            by_priority[pri].append(entry)

    p0 = by_priority["P0"]
    p1 = by_priority["P1"]
    p2 = by_priority["P2"]

    p0_ok = len(p0) >= 5 and all(e.get("emit_implemented") for e in p0)
    p1_ok = len(p1) >= 11 and all(e.get("emit_implemented") for e in p1)
    p2_implemented = [e for e in p2 if e.get("emit_implemented")]
    p2_total_in_scope = len(p2)
    p2_rate = (len(p2_implemented) / p2_total_in_scope) if p2_total_in_scope else 0.0
    p2_ok = p2_rate >= 0.95

    return {
        "p0": {"count": len(p0), "implemented": sum(1 for e in p0 if e.get("emit_implemented")), "passed": p0_ok},
        "p1": {"count": len(p1), "implemented": sum(1 for e in p1 if e.get("emit_implemented")), "passed": p1_ok},
        "p2": {
            "count": p2_total_in_scope,
            "implemented": len(p2_implemented),
            "rate": round(p2_rate, 4),
            "passed": p2_ok,
            "deferred_ids": sorted(DEFERRED_P2_IDS),
        },
        "all_passed": p0_ok and p1_ok and p2_ok,
    }
