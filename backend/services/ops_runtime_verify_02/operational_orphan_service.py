"""
Operational orphan detection — reachability without truthful resolution path.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set

from .navigation_depth_service import build_adjacency, normalize_route
from .route_authority_registry import RouteAuthorityRegistry
from .schemas import NavigationEdge, OrphanEntity


class OperationalOrphanService:
    def __init__(
        self,
        registry: Optional[RouteAuthorityRegistry] = None,
        edges: Optional[List[NavigationEdge]] = None,
    ) -> None:
        self.registry = registry or RouteAuthorityRegistry()
        self.edges = edges if edges is not None else self.registry.edges

    def audit_entities(
        self,
        entities: List[Dict[str, object]],
        *,
        entry_surfaces: Optional[List[str]] = None,
    ) -> Dict[str, object]:
        entry_surfaces = entry_surfaces or ["/today", "/command-center", "/properties"]
        adj = build_adjacency(self.edges)
        orphans: List[OrphanEntity] = []
        dead_refs: List[Dict[str, object]] = []

        for ent in entities:
            eid = str(ent.get("id", ""))
            etype = str(ent.get("type", "unknown"))
            open_ = bool(ent.get("open", True))
            target = str(ent.get("target_route", ""))
            reachable: List[str] = []
            loop_only = False

            for start in entry_surfaces:
                start_n = normalize_route(start)
                if self._can_reach(start_n, target, adj):
                    reachable.append(start_n)

            if open_ and not reachable:
                orphans.append(
                    OrphanEntity(
                        entity_type=etype,
                        entity_id=eid,
                        open=open_,
                        reachable_paths=[],
                        loop_only=False,
                        orphan=True,
                    )
                )
            elif open_ and reachable and self._only_via_cycle(reachable[0], target, adj):
                loop_only = True
                orphans.append(
                    OrphanEntity(
                        entity_type=etype,
                        entity_id=eid,
                        open=open_,
                        reachable_paths=reachable,
                        loop_only=True,
                        orphan=True,
                    )
                )

            if ent.get("dead_reference"):
                dead_refs.append({"entity_id": eid, "type": etype, "note": ent.get("note", "")})

        return {
            "entities_checked": entities,
            "navigation_paths": [o.to_dict() for o in orphans if o.reachable_paths],
            "orphans": [o.to_dict() for o in orphans if o.orphan],
            "dead_references": dead_refs,
            "orphan_count": sum(1 for o in orphans if o.orphan),
        }

    def _can_reach(self, start: str, target: str, adj: Dict[str, List[str]], depth: int = 0) -> bool:
        if depth > 8:
            return False
        if not target:
            return False
        if start == normalize_route(target):
            return True
        for nxt in adj.get(start, []):
            if self._can_reach(nxt, target, adj, depth + 1):
                return True
        return False

    def _only_via_cycle(self, start: str, target: str, adj: Dict[str, List[str]]) -> bool:
        # Simplified: reachable but every path revisits an aggregate hub
        visited: Set[str] = set()
        aggregate = {"/today", "/command-center", "/reports", "/dashboard"}

        def walk(node: str, depth: int) -> bool:
            if depth > 6:
                return False
            if normalize_route(target) == node:
                return True
            visited.add(node)
            for nxt in adj.get(node, []):
                if nxt in visited and nxt in aggregate:
                    continue
                if walk(nxt, depth + 1):
                    return node in aggregate
            return False

        return walk(start, 0)
