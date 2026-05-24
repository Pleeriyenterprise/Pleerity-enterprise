"""
Control-plane circularity detection — static graph analysis (no browser).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set

from .constants import DEFAULT_MAX_NAVIGATION_DEPTH
from .navigation_depth_service import (
    build_adjacency,
    exceeds_max_depth,
    normalize_route,
    walk_paths,
)
from .route_authority_registry import RouteAuthorityRegistry
from .schemas import CircularityCycle, NavigationEdge


class ControlPlaneCircularityService:
    def __init__(
        self,
        registry: Optional[RouteAuthorityRegistry] = None,
        edges: Optional[List[NavigationEdge]] = None,
    ) -> None:
        self.registry = registry or RouteAuthorityRegistry()
        self.edges = edges if edges is not None else self.registry.edges

    def detect_cycles(self) -> List[CircularityCycle]:
        adj = build_adjacency(self.edges)
        cycles: List[CircularityCycle] = []
        seen_signatures: Set[str] = set()

        starts = sorted({normalize_route(e.from_route) for e in self.edges})
        for start in starts:
            paths = walk_paths(start, adj, max_depth=DEFAULT_MAX_NAVIGATION_DEPTH)
            for path in paths:
                if len(path) < 2:
                    continue
                if path[0] != path[-1] and path[-1] not in adj.get(path[-1], []):
                    continue
                # cycle: repeated node
                if len(set(path)) == len(path):
                    continue
                sig = "->".join(path)
                if sig in seen_signatures:
                    continue
                seen_signatures.add(sig)
                entry = self.registry.entry_by_route(path[0])
                resolution_owner = entry.authoritative_resolution_owner if entry else ""
                mutation_present = any(
                    e.mutation_owner and e.mutation_owner != "none"
                    for e in self.edges
                    if normalize_route(e.from_route) in path
                )
                cycles.append(
                    CircularityCycle(
                        entry_surface=path[0],
                        cycle_path=path,
                        authoritative_resolution_owner=resolution_owner,
                        mutation_owner_present=mutation_present,
                        max_navigation_depth=DEFAULT_MAX_NAVIGATION_DEPTH,
                        loop_detected=True,
                        resolution_reachable=mutation_present and bool(resolution_owner),
                        classification_hint="CONTROL_PLANE_CIRCULARITY",
                    )
                )
        return cycles

    def detect_unresolved_escalation_chains(self) -> List[Dict[str, object]]:
        """Aggregate-only hops without mutation owner → escalation chain."""
        chains: List[Dict[str, object]] = []
        aggregate_routes = {"/today", "/command-center", "/reports", "/dashboard"}
        for e in self.edges:
            fr = normalize_route(e.from_route)
            to = normalize_route(e.to_route)
            if fr in aggregate_routes and to in aggregate_routes:
                if e.mutation_owner in ("none", ""):
                    chains.append(
                        {
                            "from": fr,
                            "to": to,
                            "cta_label": e.cta_label,
                            "mutation_owner": e.mutation_owner,
                            "unresolved_escalation": True,
                        }
                    )
        return chains

    def build_artifact(self) -> Dict[str, object]:
        cycles = self.detect_cycles()
        escalations = self.detect_unresolved_escalation_chains()
        depth_violations = []
        adj = build_adjacency(self.edges)
        for start in sorted({normalize_route(e.from_route) for e in self.edges}):
            for path in walk_paths(start, adj):
                if exceeds_max_depth(path):
                    depth_violations.append(
                        {
                            "entry_surface": path[0],
                            "path": path,
                            "depth": len(path),
                            "classification_hint": "RESOLUTION_EXHAUSTION",
                        }
                    )
        return {
            "cycles": [c.to_dict() for c in cycles],
            "unresolved_escalation_chains": escalations,
            "depth_violations": depth_violations,
            "loop_detected": bool(cycles),
            "summary": {
                "cycle_count": len(cycles),
                "escalation_chain_count": len(escalations),
                "depth_violation_count": len(depth_violations),
            },
        }
