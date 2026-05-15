"""Registry-backed CVP plan features for public support grounding."""
from services.support_assistant_plan_features import (
    build_cvp_plan_features_for_support,
    format_plan_features_for_prompt,
)


def test_plan_features_available_from_registry():
    snap = build_cvp_plan_features_for_support()
    assert snap.get("available") is True
    plans = snap.get("plans") or []
    assert len(plans) >= 3
    solo = next((p for p in plans if p.get("code") == "PLAN_1_SOLO"), None)
    assert solo is not None
    assert solo.get("max_properties") == 2
    cats = solo.get("enabled_features_by_category") or {}
    assert "core" in cats
    assert any("Compliance" in name for name in cats["core"])


def test_format_includes_grounding_rule():
    text = format_plan_features_for_prompt(build_cvp_plan_features_for_support())
    assert "registry-backed" in text.lower()
    assert "do not guess" in text.lower() or "only assert" in text.lower()
    assert "Solo" in text or "PLAN_1" in text


def test_tenant_portal_label_deduped():
    snap = build_cvp_plan_features_for_support()
    pro = next(p for p in snap["plans"] if p["code"] == "PLAN_3_PRO")
    portal = pro.get("enabled_features_by_category", {}).get("portal", [])
    tenant_labels = [x for x in portal if "tenant" in x.lower()]
    assert len(tenant_labels) == 1
