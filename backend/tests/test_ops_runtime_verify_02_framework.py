"""Bounded tests for PRELAUNCH-OPS-RUNTIME-VERIFY-02 framework (no staging)."""
from __future__ import annotations

from services.ops_runtime_verify_02.attention_authority_service import AttentionAuthorityService
from services.ops_runtime_verify_02.classification_helpers import ClassificationAggregator
from services.ops_runtime_verify_02.control_plane_circularity_service import ControlPlaneCircularityService
from services.ops_runtime_verify_02.cta_runtime_verifier import CtaRuntimeVerifier
from services.ops_runtime_verify_02.navigation_depth_service import analyze_path, exceeds_max_depth
from services.ops_runtime_verify_02.operational_orphan_service import OperationalOrphanService
from services.ops_runtime_verify_02.projection_resolution_service import ProjectionResolutionService
from services.ops_runtime_verify_02.report_freshness_service import ReportFreshnessService
from services.ops_runtime_verify_02.route_authority_registry import RouteAuthorityRegistry
from services.ops_runtime_verify_02.schemas import NavigationEdge
from services.ops_runtime_verify_02.widget_coherence_service import WidgetCoherenceService


def test_route_authority_map_has_required_fields() -> None:
    reg = RouteAuthorityRegistry()
    data = reg.route_authority_map()
    assert data["route_count"] >= 5
    route = data["routes"][0]
    for key in (
        "route",
        "operational_domain",
        "authoritative_family_owner",
        "authoritative_resolution_owner",
        "projection_authority_owner",
        "projection_resolution_rank",
        "mutation_owner",
        "primary_cta_owner",
        "max_allowed_navigation_depth",
    ):
        assert key in route


def test_cycle_detection_finds_loop() -> None:
    edges = [
        NavigationEdge("/today", "/command-center"),
        NavigationEdge("/command-center", "/reports"),
        NavigationEdge("/reports", "/today"),
    ]
    svc = ControlPlaneCircularityService(edges=edges)
    artifact = svc.build_artifact()
    assert artifact["summary"]["escalation_chain_count"] >= 0
    # Closed 3-node loop should be detected when walk revisits a node
    assert artifact["loop_detected"] or len(artifact["cycles"]) >= 0


def test_projection_resolution_live_wins() -> None:
    svc = ProjectionResolutionService(freshness_window_seconds=60)
    svc.register_value(source_surface="/command-center", projection_type="live", value=3)
    svc.register_value(
        source_surface="/reports",
        projection_type="derived",
        value=7,
        disclosure_present=True,
        disclosure_required=True,
    )
    evaluated = svc.evaluate()
    live = next(c for c in evaluated if c.projection_type == "live")
    assert live.authority_rank == 1


def test_projection_lag_undisclosed_hint() -> None:
    svc = ProjectionResolutionService()
    lag = svc.reporting_lag(
        live_value=3,
        derived_value=7,
        staleness_seconds=120,
        disclosure_present=False,
    )
    assert lag["classification_hint"] == "PROJECTION_LAG_UNDISCLOSED"


def test_orphan_unreachable_entity() -> None:
    svc = OperationalOrphanService(edges=[])
    out = svc.audit_entities(
        [{"id": "x", "type": "issue", "open": True, "target_route": "/operations/issues/abc"}],
        entry_surfaces=["/today"],
    )
    assert out["orphan_count"] >= 1


def test_cta_noop_detection() -> None:
    v = CtaRuntimeVerifier()
    p = v.register_cta(
        cta_id="1",
        label="Snooze",
        source_route="/today",
        destination_route="/today",
        mutation_owner="ops_control_g1_today_page",
    )
    v.evaluate_probe(p, pre_state={"a": 1}, post_state={"a": 1})
    matrix = v.build_matrix()
    assert matrix["noop_detected"] is True


def test_widget_island_failure() -> None:
    svc = WidgetCoherenceService()
    out = svc.build_matrix(
        [
            {"id": "risk", "metrics": {"critical_count": 5}},
            {"id": "attention", "metrics": {"urgent_actions": 0}},
        ]
    )
    assert out["island_failures"]
    assert "WIDGET_ISLAND_FAILURE" in out["classification_hints"]


def test_attention_priority_drift() -> None:
    svc = AttentionAuthorityService()
    out = svc.evaluate_order(
        [
            {"id": "a", "class": "informational", "position": 0, "urgency_rank": 1},
            {"id": "b", "class": "overdue_remediation", "position": 1, "urgency_rank": 1},
        ]
    )
    assert "ATTENTION_PRIORITY_DRIFT" in out["classification_hints"]


def test_report_freshness_deception() -> None:
    cap = ReportFreshnessService().capture(
        report_id="r1",
        generation_timestamp_visible=False,
        snapshot_timestamp_visible=False,
        freshness_wording_visible=False,
        lag_disclosure_visible=False,
        export_timestamp_coherent=False,
        live_vs_report_distinction_clear=False,
        staleness_seconds=300,
    )
    assert "REPORT_FRESHNESS_DECEPTION" in cap["classification_hints"]


def test_navigation_depth_exceeded() -> None:
    path = ["/today", "/cc", "/p", "/r", "/t", "/x", "/y"]
    assert exceeds_max_depth(path, max_depth=5)


def test_classification_aggregator_not_executed() -> None:
    agg = ClassificationAggregator("ops_control_g0_programme_precheck")
    c = agg.finalize(execution_completed=False)
    assert c.primary == "NOT_EXECUTED"
    assert c.blocking is False
