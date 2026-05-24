"""
Route authority map generation from frontend route discovery + programme registry.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .constants import DEFAULT_MAX_NAVIGATION_DEPTH, Verify02Family
from .schemas import NavigationEdge, RouteAuthorityEntry

# Programme in-scope routes → family ownership (charter-aligned)
_ROUTE_OWNERSHIP: Dict[str, Tuple[str, str, str, int, str]] = {
    # route_prefix: (domain, family, projection_authority, rank, resolution_owner)
    "/today": ("attention", Verify02Family.G1.value, "attention_list", 2, Verify02Family.G1.value),
    "/tasks": ("attention", Verify02Family.G1.value, "attention_list", 2, Verify02Family.G1.value),
    "/command-center": ("live_projection", Verify02Family.G2.value, "live", 1, Verify02Family.G2.value),
    "/work-queue": ("live_projection", Verify02Family.G2.value, "live", 1, Verify02Family.G2.value),
    "/properties": ("property_hub", Verify02Family.G3.value, "live", 3, Verify02Family.G3.value),
    "/properties/:propertyId": ("property_hub", Verify02Family.G3.value, "live", 3, Verify02Family.G3.value),
    "/requirements": ("requirement", Verify02Family.G4.value, "row", 3, Verify02Family.G4.value),
    "/documents": ("document", Verify02Family.G5.value, "surface_visibility", 3, Verify02Family.G5.value),
    "/documents/bulk-upload": ("document", Verify02Family.G5.value, "surface_visibility", 3, Verify02Family.G5.value),
    "/calendar": ("calendar", Verify02Family.G6.value, "temporal_visibility", 3, Verify02Family.G6.value),
    "/reports": ("reporting", Verify02Family.G7.value, "derived", 4, Verify02Family.G7.value),
    "/reports/audit-pack": ("reporting", Verify02Family.G7.value, "exported", 5, Verify02Family.G7.value),
}

# VERIFY-01 mutation owners for operational detail routes (read-only in VERIFY-02)
_MUTATION_OWNER_BY_PREFIX: Dict[str, str] = {
    "/operations/issues": "ops_runtime_01_issues",
    "/operations/work-orders": "ops_runtime_02_work_orders",
    "/operations/jobs": "ops_runtime_02_work_orders",
    "/operations/risk-signals": "ops_runtime_04_risk_signals",
    "/operations/rent": "ops_runtime_06_rent_ops",
}

# Static navigation edges for cycle analysis (CTA / drilldown semantics)
_DEFAULT_NAVIGATION_EDGES: List[NavigationEdge] = [
    NavigationEdge("/today", "/command-center", "View command centre"),
    NavigationEdge("/today", "/properties/:propertyId", "Open property"),
    NavigationEdge("/today", "/requirements", "Open requirement"),
    NavigationEdge("/today", "/reports", "View report"),
    NavigationEdge("/command-center", "/properties/:propertyId", "Property drilldown"),
    NavigationEdge("/command-center", "/operations/issues/:issueId", "Issue drilldown", mutation_owner="ops_runtime_01_issues"),
    NavigationEdge("/command-center", "/requirements", "Requirements"),
    NavigationEdge("/command-center", "/reports", "Reports"),
    NavigationEdge("/properties/:propertyId", "/requirements", "Requirements tab"),
    NavigationEdge("/properties/:propertyId", "/documents", "Documents tab"),
    NavigationEdge("/properties/:propertyId", "/calendar", "Calendar"),
    NavigationEdge("/properties/:propertyId", "/today", "Back to today"),
    NavigationEdge("/requirements", "/documents", "Linked document"),
    NavigationEdge("/documents", "/requirements", "Linked requirement"),
    NavigationEdge("/reports", "/command-center", "Back to command centre"),
    NavigationEdge("/reports", "/properties/:propertyId", "Property drilldown"),
    NavigationEdge("/calendar", "/properties/:propertyId", "Property event"),
    NavigationEdge("/calendar", "/operations/jobs/:jobId", "Job detail", mutation_owner="ops_runtime_02_work_orders"),
]

_CYCLE_EXEMPTIONS: Dict[str, List[str]] = {
    "/tasks": ["/today"],
    "/app/tasks": ["/today"],
    "/app/today": ["/today"],
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def discover_routes_from_app_js(app_js_path: Optional[Path] = None) -> List[str]:
    path = app_js_path or (_repo_root() / "frontend" / "src" / "App.js")
    if not path.is_file():
        return sorted(_ROUTE_OWNERSHIP.keys())
    text = path.read_text(encoding="utf-8", errors="replace")
    found = set(re.findall(r'path="(/[^"]+)"', text))
    # Programme scope filter
    prefixes = (
        "/today",
        "/tasks",
        "/command-center",
        "/work-queue",
        "/properties",
        "/requirements",
        "/documents",
        "/calendar",
        "/reports",
        "/operations/",
        "/app/",
    )
    scoped = [r for r in found if r.startswith(prefixes)]
    for r in _ROUTE_OWNERSHIP:
        scoped.append(r)
    return sorted(set(scoped))


def _match_ownership(route: str) -> Tuple[str, str, str, int, str]:
    if route in _ROUTE_OWNERSHIP:
        return _ROUTE_OWNERSHIP[route]
    for prefix, meta in sorted(_ROUTE_OWNERSHIP.items(), key=lambda x: -len(x[0])):
        if route.startswith(prefix.rstrip("/")) or (
            ":propertyId" in prefix and route.startswith("/properties/")
        ):
            return meta
    if route.startswith("/operations/"):
        return ("operations", Verify02Family.G2.value, "live", 1, Verify02Family.G2.value)
    return ("unknown", Verify02Family.G0.value, "none", 0, Verify02Family.G0.value)


def _mutation_owner_for_route(route: str) -> str:
    for prefix, owner in _MUTATION_OWNER_BY_PREFIX.items():
        if route.startswith(prefix):
            return owner
    return "none"


def build_route_authority_entries(routes: Optional[List[str]] = None) -> List[RouteAuthorityEntry]:
    routes = routes or discover_routes_from_app_js()
    entries: List[RouteAuthorityEntry] = []
    for route in routes:
        domain, family, proj_auth, rank, resolution = _match_ownership(route)
        if rank == 0:
            continue
        app_aliases = [f"/app{route}"] if route.startswith("/") and not route.startswith("/app") else []
        entries.append(
            RouteAuthorityEntry(
                route=route,
                operational_domain=domain,
                authoritative_family_owner=family,
                inherited_dependency_owners=list(_MUTATION_OWNER_BY_PREFIX.values())[:4],
                authoritative_resolution_owner=resolution,
                projection_authority_owner=proj_auth,
                projection_resolution_rank=rank,
                mutation_owner=_mutation_owner_for_route(route),
                primary_cta_owner=family,
                cycle_detection_exemptions=_CYCLE_EXEMPTIONS.get(route, []),
                max_allowed_navigation_depth=DEFAULT_MAX_NAVIGATION_DEPTH,
                app_alias_routes=app_aliases,
            )
        )
    return entries


def build_route_authority_map(routes: Optional[List[str]] = None) -> Dict[str, object]:
    entries = build_route_authority_entries(routes)
    return {
        "programme": "PRELAUNCH-OPS-RUNTIME-VERIFY-02",
        "routes": [e.to_dict() for e in entries],
        "route_count": len(entries),
    }


def default_navigation_edges() -> List[NavigationEdge]:
    return list(_DEFAULT_NAVIGATION_EDGES)


class RouteAuthorityRegistry:
    def __init__(self, app_js_path: Optional[Path] = None) -> None:
        self.app_js_path = app_js_path
        self.routes = discover_routes_from_app_js(app_js_path)
        self.entries = build_route_authority_entries(self.routes)
        self.edges = default_navigation_edges()

    def route_authority_map(self) -> Dict[str, object]:
        return build_route_authority_map(self.routes)

    def entry_by_route(self, route: str) -> Optional[RouteAuthorityEntry]:
        for e in self.entries:
            if e.route == route:
                return e
        return None
