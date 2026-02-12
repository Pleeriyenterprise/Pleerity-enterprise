"""
Plan registry gating tests (Step 1 + Step 2).
Tests resolve_plan_code, subscription_allows_feature_access, feature matrix,
plan-features response shape, and check_feature_access (Solo vs Portfolio vs Pro).
Single source of truth: plan_registry.py (2/10/25, Solo/Portfolio/Pro).
"""
import pytest
import sys
from pathlib import Path

# Ensure backend root is on path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from services.plan_registry import (
    plan_registry,
    PlanCode,
    subscription_allows_feature_access,
    SUBSCRIPTION_STATUSES_ALLOWING_FEATURE_ACCESS,
)


class TestResolvePlanCode:
    """Public resolve_plan_code and plan_registry feature matrix."""

    def test_resolve_canonical_plan_codes(self):
        """Canonical codes resolve to correct PlanCode."""
        assert plan_registry.resolve_plan_code("PLAN_1_SOLO") == PlanCode.PLAN_1_SOLO
        assert plan_registry.resolve_plan_code("PLAN_2_PORTFOLIO") == PlanCode.PLAN_2_PORTFOLIO
        assert plan_registry.resolve_plan_code("PLAN_3_PRO") == PlanCode.PLAN_3_PRO

    def test_resolve_legacy_plan_codes(self):
        """Legacy codes map to canonical plans."""
        assert plan_registry.resolve_plan_code("PLAN_1") == PlanCode.PLAN_1_SOLO
        assert plan_registry.resolve_plan_code("PLAN_2_5") == PlanCode.PLAN_2_PORTFOLIO
        assert plan_registry.resolve_plan_code("PLAN_6_15") == PlanCode.PLAN_3_PRO

    def test_resolve_unknown_defaults_to_solo(self):
        """Unknown code defaults to PLAN_1_SOLO."""
        assert plan_registry.resolve_plan_code("UNKNOWN") == PlanCode.PLAN_1_SOLO


class TestSubscriptionAllowsFeatureAccess:
    """Subscription allow-list: ACTIVE and TRIALING allow feature access."""

    def test_active_allows_access(self):
        """ACTIVE is in allow-list."""
        assert subscription_allows_feature_access("ACTIVE") is True

    def test_trialing_allows_access(self):
        """TRIALING is in allow-list."""
        assert subscription_allows_feature_access("TRIALING") is True

    def test_pending_denies_access(self):
        """PENDING is not in allow-list."""
        assert subscription_allows_feature_access("PENDING") is False

    def test_canceled_denies_access(self):
        """CANCELED is not in allow-list."""
        assert subscription_allows_feature_access("CANCELED") is False

    def test_none_denies_access(self):
        """None/empty denies access."""
        assert subscription_allows_feature_access(None) is False
        assert subscription_allows_feature_access("") is False

    def test_case_insensitive(self):
        """Allow-list check is case-insensitive (normalized to upper)."""
        assert subscription_allows_feature_access("active") is True
        assert subscription_allows_feature_access("trialing") is True


class TestPlanRegistryFeatureMatrix:
    """Feature availability and max_properties from plan_registry (2/10/25)."""

    def test_solo_max_properties_is_2(self):
        """PLAN_1_SOLO has max_properties 2."""
        assert plan_registry.get_property_limit(PlanCode.PLAN_1_SOLO) == 2

    def test_portfolio_max_properties_is_10(self):
        """PLAN_2_PORTFOLIO has max_properties 10."""
        assert plan_registry.get_property_limit(PlanCode.PLAN_2_PORTFOLIO) == 10

    def test_pro_max_properties_is_25(self):
        """PLAN_3_PRO has max_properties 25."""
        assert plan_registry.get_property_limit(PlanCode.PLAN_3_PRO) == 25

    def test_solo_zip_upload_disabled(self):
        """PLAN_1_SOLO does not have zip_upload."""
        features = plan_registry.get_features(PlanCode.PLAN_1_SOLO)
        assert features.get("zip_upload") is False

    def test_solo_reports_pdf_disabled(self):
        """PLAN_1_SOLO does not have reports_pdf."""
        features = plan_registry.get_features(PlanCode.PLAN_1_SOLO)
        assert features.get("reports_pdf") is False

    def test_portfolio_zip_upload_enabled(self):
        """PLAN_2_PORTFOLIO has zip_upload."""
        features = plan_registry.get_features(PlanCode.PLAN_2_PORTFOLIO)
        assert features.get("zip_upload") is True

    def test_portfolio_reports_pdf_enabled(self):
        """PLAN_2_PORTFOLIO has reports_pdf."""
        features = plan_registry.get_features(PlanCode.PLAN_2_PORTFOLIO)
        assert features.get("reports_pdf") is True

    def test_pro_webhooks_enabled(self):
        """PLAN_3_PRO has webhooks."""
        features = plan_registry.get_features(PlanCode.PLAN_3_PRO)
        assert features.get("webhooks") is True


class TestPlanFeaturesResponseShape:
    """GET /api/client/plan-features response shape and caps (2/10/25)."""

    def _build_plan_features_response(self, plan_code, subscription_status, is_active):
        """Same structure as client.get_plan_features route."""
        plan_def = plan_registry.get_plan(plan_code)
        features = plan_registry.get_features(plan_code)
        features["max_properties"] = plan_registry.get_property_limit(plan_code)
        return {
            "plan": plan_code.value,
            "plan_name": plan_def["name"],
            "subscription_status": subscription_status,
            "features": features,
            "is_active": is_active,
        }

    def test_plan_features_response_has_required_keys(self):
        """Response has plan, plan_name, subscription_status, features, is_active."""
        data = self._build_plan_features_response(
            PlanCode.PLAN_1_SOLO, "ACTIVE", True
        )
        assert "plan" in data
        assert "plan_name" in data
        assert "subscription_status" in data
        assert "features" in data
        assert "is_active" in data
        assert "max_properties" in data["features"]

    def test_plan_features_solo_cap_2(self):
        """Solo plan-features has max_properties 2."""
        data = self._build_plan_features_response(
            PlanCode.PLAN_1_SOLO, "ACTIVE", True
        )
        assert data["features"]["max_properties"] == 2
        assert data["plan"] == "PLAN_1_SOLO"

    def test_plan_features_portfolio_cap_10(self):
        """Portfolio plan-features has max_properties 10."""
        data = self._build_plan_features_response(
            PlanCode.PLAN_2_PORTFOLIO, "ACTIVE", True
        )
        assert data["features"]["max_properties"] == 10
        assert data["plan"] == "PLAN_2_PORTFOLIO"

    def test_plan_features_pro_cap_25(self):
        """Pro plan-features has max_properties 25."""
        data = self._build_plan_features_response(
            PlanCode.PLAN_3_PRO, "ACTIVE", True
        )
        assert data["features"]["max_properties"] == 25
        assert data["plan"] == "PLAN_3_PRO"


class TestCheckFeatureAccessSoloPortfolioPro:
    """check_feature_access (sync) for affected endpoints: Solo vs Portfolio vs Pro."""

    def test_zip_upload_solo_denied_portfolio_allowed(self):
        """zip_upload: Solo denied, Portfolio allowed."""
        allowed_solo, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_1_SOLO, "zip_upload"
        )
        allowed_portfolio, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_2_PORTFOLIO, "zip_upload"
        )
        assert allowed_solo is False
        assert allowed_portfolio is True

    def test_reports_pdf_solo_denied_portfolio_allowed(self):
        """reports_pdf: Solo denied, Portfolio allowed."""
        allowed_solo, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_1_SOLO, "reports_pdf"
        )
        allowed_portfolio, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_2_PORTFOLIO, "reports_pdf"
        )
        assert allowed_solo is False
        assert allowed_portfolio is True

    def test_webhooks_solo_portfolio_denied_pro_allowed(self):
        """webhooks: Solo and Portfolio denied, Pro allowed."""
        allowed_solo, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_1_SOLO, "webhooks"
        )
        allowed_portfolio, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_2_PORTFOLIO, "webhooks"
        )
        allowed_pro, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_3_PRO, "webhooks"
        )
        assert allowed_solo is False
        assert allowed_portfolio is False
        assert allowed_pro is True

    def test_white_label_reports_solo_portfolio_denied_pro_allowed(self):
        """white_label_reports: Solo and Portfolio denied, Pro allowed."""
        allowed_solo, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_1_SOLO, "white_label_reports"
        )
        allowed_portfolio, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_2_PORTFOLIO, "white_label_reports"
        )
        allowed_pro, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_3_PRO, "white_label_reports"
        )
        assert allowed_solo is False
        assert allowed_portfolio is False
        assert allowed_pro is True

    def test_audit_log_export_pro_only(self):
        """audit_log_export: Pro only."""
        allowed_solo, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_1_SOLO, "audit_log_export"
        )
        allowed_portfolio, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_2_PORTFOLIO, "audit_log_export"
        )
        allowed_pro, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_3_PRO, "audit_log_export"
        )
        assert allowed_solo is False
        assert allowed_portfolio is False
        assert allowed_pro is True

    def test_scheduled_reports_portfolio_and_pro(self):
        """scheduled_reports: Portfolio and Pro allowed."""
        allowed_solo, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_1_SOLO, "scheduled_reports"
        )
        allowed_portfolio, _, _ = plan_registry.check_feature_access(
            PlanCode.PLAN_2_PORTFOLIO, "scheduled_reports"
        )
        assert allowed_solo is False
        assert allowed_portfolio is True
