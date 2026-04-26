"""Today requirement business_actions must follow canonical take_action (resolver contract), not gap recommended_*."""
from __future__ import annotations

from services.requirement_action_resolver import resolve_take_action_envelope
from services.today_projection_service import build_business_actions_for_task, cap_and_order_business_actions
from services.unified_tasks_service import _primary_action_fields


def _task_requirement(*, rid: str, pid: str, code: str, take_action: dict | None, **meta_extra):
    meta = {
        "requirement_code": code,
        "action_type": "missing_document",
        "compliance_engine": {
            "fulfillment_mode": "document",
            "requires_document_evidence": True,
            "creates_compliance_job": False,
        },
        **meta_extra,
    }
    if take_action is not None:
        meta["take_action"] = take_action
    return {
        "id": f"requirement:{rid}",
        "source_type": "requirement",
        "source_entity_id": rid,
        "source_id": rid,
        "property_id": pid,
        "primary_action_type": "upload_evidence",
        "metadata": meta,
    }


def test_today_requirement_business_action_matches_metadata_take_action():
    ta = {
        "primary": {"label": "Upload Gas Safety record", "route": "/documents?property_id=p1&requirement_id=r1", "kind": "navigate", "handler": "navigate"},
        "secondary": None,
        "supporting_external_links": [],
        "contract": "requirement_take_action_v1",
        "provenance": {"primary_label": "published_registry", "supporting_links": "engine_default", "source_type": "requirement"},
    }
    task = _task_requirement(rid="r1", pid="p1", code="gas_safety", take_action=ta)
    raw = build_business_actions_for_task(task)
    primaries = [a for a in raw if a.get("id") == "take_action_primary"]
    assert len(primaries) == 1
    assert primaries[0]["label"] == "Upload Gas Safety record"
    assert primaries[0]["navigate"] == "/documents?property_id=p1&requirement_id=r1"
    assert primaries[0].get("action_authority") == "take_action"


def test_today_requirement_respects_cta_label_override_when_take_action_missing_uses_resolver_fallback():
    """When metadata.take_action is absent, Today falls back to resolve_take_action_envelope (same as resolver)."""
    task = _task_requirement(
        rid="r2",
        pid="p2",
        code="gas_safety",
        take_action=None,
        registry_metadata={"cta_label_override": "Provide CP12 certificate"},
    )
    env = resolve_take_action_envelope(
        {
            "requirement_id": "r2",
            "property_id": "p2",
            "requirement_code": "gas_safety",
            "requirement_type": "gas_safety",
            "registry_metadata": {"cta_label_override": "Provide CP12 certificate"},
        },
        property_id="p2",
        property_jurisdiction="England",
    )
    raw = build_business_actions_for_task(task)
    primary = next(a for a in raw if a.get("id") == "take_action_primary")
    assert primary["label"] == env["take_action"]["primary"]["label"]
    assert "Provide CP12" in primary["label"]


def test_today_does_not_emit_upload_certificate_label_for_requirement_document_gap():
    task = _task_requirement(
        rid="r3",
        pid="p3",
        code="eicr",
        take_action={
            "primary": {
                "label": "Upload document",
                "route": "/documents?property_id=p3&requirement_id=r3",
                "kind": "navigate",
                "handler": "navigate",
            },
            "secondary": None,
            "supporting_external_links": [],
        },
    )
    raw = build_business_actions_for_task(task)
    labels = [str(a.get("label") or "") for a in raw]
    assert not any("Upload certificate" == s for s in labels)
    assert "Upload document" in labels


def test_gap_recommended_fields_do_not_override_primary_when_canonical_take_action_present():
    """Priority row may carry misaligned gap recommended_*; unified primary fields follow canonical_take_action."""
    a = {
        "action_type": "missing_document",
        "related_property_id": "p9",
        "related_requirement_id": "r9",
        "requirement_code": "gas_safety",
        "jurisdiction": "England",
        "recommended_url": "/wrong",
        "recommended_action_label": "Wrong label from gap",
        "canonical_take_action": {
            "primary": {
                "label": "Resolver primary",
                "route": "/documents?property_id=p9&requirement_id=r9",
                "kind": "navigate",
                "handler": "navigate",
            },
            "secondary": None,
            "supporting_external_links": [],
        },
    }
    pri_type, label, url, *_ = _primary_action_fields(a, "requirement", compliance_engine=None)
    assert label == "Resolver primary"
    assert url == "/documents?property_id=p9&requirement_id=r9"
    assert pri_type == "upload_evidence"


def test_today_cap_order_prefers_compliance_job_then_take_action_primary():
    ta = {
        "primary": {"label": "Upload", "route": "/documents?property_id=p1&requirement_id=r1", "kind": "navigate", "handler": "navigate"},
        "secondary": None,
        "supporting_external_links": [],
    }
    task = _task_requirement(rid="r1", pid="p1", code="gas_safety", take_action=ta)
    task["metadata"]["compliance_execution_booking"] = {
        "eligible": True,
        "linked_property_requirement_id": "r1",
        "property_id": "p1",
        "requirement_code": "gas_safety",
    }
    task["metadata"]["compliance_engine"]["creates_compliance_job"] = True
    raw = build_business_actions_for_task(task)
    capped = cap_and_order_business_actions(raw, max_actions=2)
    assert len(capped) == 2
    assert capped[0]["id"] == "create_compliance_work_order"
    assert capped[1]["id"] == "take_action_primary"
    assert capped[0].get("primary") is True
