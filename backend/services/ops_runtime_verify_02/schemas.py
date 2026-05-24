"""
Typed structures for VERIFY-02 artifacts (JSON-serializable).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def to_json_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_json_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [to_json_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_json_dict(v) for k, v in obj.items()}
    return obj


@dataclass
class RouteAuthorityEntry:
    route: str
    operational_domain: str
    authoritative_family_owner: str
    inherited_dependency_owners: List[str] = field(default_factory=list)
    authoritative_resolution_owner: str = ""
    projection_authority_owner: str = ""
    projection_resolution_rank: int = 0
    mutation_owner: str = "none"
    primary_cta_owner: str = ""
    cycle_detection_exemptions: List[str] = field(default_factory=list)
    max_allowed_navigation_depth: int = 5
    app_alias_routes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return to_json_dict(self)


@dataclass
class NavigationEdge:
    from_route: str
    to_route: str
    cta_label: str = ""
    mutation_owner: str = "none"
    is_exempt: bool = False


@dataclass
class CircularityCycle:
    entry_surface: str
    cycle_path: List[str]
    authoritative_resolution_owner: str
    mutation_owner_present: bool
    max_navigation_depth: int
    loop_detected: bool
    resolution_reachable: bool
    classification_hint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return to_json_dict(self)


@dataclass
class ProjectionContradiction:
    source_surface: str
    projection_type: str
    authority_rank: int
    value: Optional[float] = None
    freshness_window_seconds: int = 60
    disclosure_required: bool = False
    disclosure_present: bool = False
    reconciliation_owner: str = ""
    contradiction_detected: bool = False
    resolution: str = "unresolved"  # acceptable_lag | authoritative_winner | unresolved

    def to_dict(self) -> Dict[str, Any]:
        return to_json_dict(self)


@dataclass
class CtaProbeResult:
    cta_id: str
    label: str
    source_route: str
    destination_route: str
    reachable: bool = False
    mutation_owner_present: bool = False
    noop_detected: bool = False
    duplicate_cta: bool = False
    contradictory_cta: bool = False
    dead_end: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return to_json_dict(self)


@dataclass
class OrphanEntity:
    entity_type: str
    entity_id: str
    open: bool
    reachable_paths: List[str] = field(default_factory=list)
    loop_only: bool = False
    orphan: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return to_json_dict(self)
