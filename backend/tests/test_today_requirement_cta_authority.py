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


def test_today_emits_direct_evidence_take_action_primary_with_evidence_mode():
    ta = {
        "primary": {
            "label": "Submit compliance declaration",
            "route": None,
            "kind": "direct_evidence_action",
            "handler": "direct_evidence",
            "intent": "direct_evidence_action",
            "property_id": "p1",
            "requirement_id": "r1",
            "evidence_mode": "STRUCTURED_DECLARATION",
        },
        "secondary": None,
        "supporting_external_links": [],
        "contract": "requirement_take_action_v1",
        "provenance": {},
    }
    task = _task_requirement(rid="r1", pid="p1", code="declaration_only", take_action=ta)
    raw = build_business_actions_for_task(task)
    prim = next(a for a in raw if a.get("id") == "take_action_primary")
    assert prim.get("kind") == "direct_evidence_action"
    assert prim.get("evidence_mode") == "STRUCTURED_DECLARATION"
    assert prim.get("navigate") == ""


def test_today_emits_guided_take_action_primary_without_navigate_url():
    ta = {
        "primary": {
            "label": "Resolve requirement",
            "route": None,
            "kind": "guided_evidence_resolution",
            "handler": "guided_evidence",
            "intent": "guided_evidence_resolution",
            "property_id": "p1",
            "requirement_id": "r1",
        },
        "secondary": {
            "label": "Upload document",
            "route": "/documents?property_id=p1&requirement_id=r1",
            "kind": "navigate",
            "handler": "navigate",
        },
        "supporting_external_links": [],
        "contract": "requirement_take_action_v1",
        "provenance": {},
    }
    task = _task_requirement(rid="r1", pid="p1", code="smoke_heat_alarms", take_action=ta)
    raw = build_business_actions_for_task(task)
    prim = next(a for a in raw if a.get("id") == "take_action_primary")
    assert prim.get("kind") == "guided_evidence_resolution"
    assert prim.get("navigate") == ""
    assert prim.get("requirement_id") == "r1"


def test_unified_primary_fields_canonical_empty_route_does_not_fallback_to_gap_url():
    """Stream D B2: empty canonical primary route — use resolver URL (here guided → ''), not gap recommended_url."""
    a = {
        "action_type": "missing_document",
        "related_property_id": "p1",
        "related_requirement_id": "r1",
        "requirement_code": "smoke_heat_alarms",
        "jurisdiction": "England",
        "registry_metadata": {},
        "recommended_url": "/wrong-gap",
        "recommended_action_label": "Wrong gap label",
        "canonical_take_action": {
            "primary": {
                "label": "Resolve requirement",
                "route": "",
                "kind": "guided_evidence_resolution",
                "handler": "guided_evidence",
                "intent": "guided_evidence_resolution",
                "property_id": "p1",
                "requirement_id": "r1",
            },
            "secondary": None,
            "supporting_external_links": [],
            "contract": "requirement_take_action_v1",
        },
    }
    eng = {"compliance_requirement_class": "DOCUMENT", "fulfillment_mode": "document"}
    pri_type, label, url, *_ = _primary_action_fields(a, "requirement", compliance_engine=eng)
    assert pri_type == "guided_evidence_resolution"
    assert url == ""
    assert label == "Resolve requirement"


def test_unified_primary_fields_canonical_empty_label_does_not_fallback_to_gap_label():
    """Stream D B2: empty canonical primary label — use resolver-derived label, not gap recommended_action_label."""
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
                "label": "",
                "route": "/documents?property_id=p9&requirement_id=r9",
                "kind": "navigate",
                "handler": "navigate",
            },
            "secondary": None,
            "supporting_external_links": [],
        },
    }
    pri_type, label, url, *_ = _primary_action_fields(a, "requirement", compliance_engine=None)
    assert "/wrong" not in url
    assert url == "/documents?property_id=p9&requirement_id=r9"
    assert label != "Wrong label from gap"


def test_unified_primary_fields_for_guided_resolution():
    a = {
        "action_type": "missing_document",
        "related_property_id": "p1",
        "related_requirement_id": "r1",
        "requirement_code": "smoke_heat_alarms",
        "jurisdiction": "England",
        "registry_metadata": {},
    }
    eng = {"compliance_requirement_class": "DOCUMENT", "fulfillment_mode": "document"}
    pri_type, label, url, *_ = _primary_action_fields(a, "requirement", compliance_engine=eng)
    assert pri_type == "guided_evidence_resolution"
    assert url == ""
    assert "Resolve" in label or "evidence" in label.lower()


def test_orphan_reclassified_task_not_rendered_as_requirement_take_action():
    task = {
        "id": "requirement:orphan-r1",
        "source_type": "priority_action",
        "source_entity_id": "orphan-r1",
        "source_id": "orphan-r1",
        "property_id": "p1",
        "primary_action_type": "view_details",
        "primary_action_label": "View details",
        "primary_action_url": "/requirements?property_id=p1",
        "metadata": {
            "action_type": "missing_document",
            "requirement_code": "gas_safety",
            "canonical_guard": {"reclassified": True},
        },
    }
    actions = build_business_actions_for_task(task)
    ids = {a.get("id") for a in actions}
    assert "take_action_primary" not in ids
    assert "open_primary" in ids
