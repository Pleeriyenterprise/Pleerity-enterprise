"""
Stream D Phase 4 — backend contract tests for requirement CTA parity fixtures.

Freezes `requirement_action_resolver` outputs aligned with
`docs/STREAM_D_CTA_PARITY_ENFORCEMENT.md` and `tests/fixtures/cta_parity_fixtures.py`.
"""

from __future__ import annotations

import pytest

from services.requirement_action_resolver import resolve_take_action_envelope, resolve_take_action_for_priority_action
from tests.fixtures.cta_parity_fixtures import (
    CtaParityCase,
    CtaParityExpectedPrimary,
    CtaParityExpectedSecondary,
    all_cta_parity_cases,
    priority_action_row_from_requirement,
)


def _assert_primary(pri: dict, exp: CtaParityExpectedPrimary) -> None:
    if exp.intent is not None:
        assert pri.get("intent") == exp.intent, f"intent mismatch: {pri!r}"
    if exp.kind is not None:
        assert pri.get("kind") == exp.kind, f"kind mismatch: {pri!r}"
    if exp.handler is not None:
        assert pri.get("handler") == exp.handler, f"handler mismatch: {pri!r}"
    if exp.route_is_none is not None:
        r = pri.get("route")
        if exp.route_is_none:
            assert r in (None, ""), f"expected empty route, got {r!r}"
        else:
            assert r not in (None, ""), f"expected non-empty route, got {r!r}"
    if exp.route_contains is not None:
        assert exp.route_contains in (pri.get("route") or ""), f"route {pri.get('route')!r}"
    if exp.route_equals is not None:
        assert pri.get("route") == exp.route_equals, f"route {pri.get('route')!r}"
    if exp.label_equals is not None:
        assert pri.get("label") == exp.label_equals, f"label {pri.get('label')!r}"
    if exp.label_substring is not None:
        assert exp.label_substring.lower() in (pri.get("label") or "").lower(), f"label {pri.get('label')!r}"
    if exp.evidence_mode is not None:
        assert pri.get("evidence_mode") == exp.evidence_mode
    if exp.metadata_incomplete is not None:
        assert bool(pri.get("metadata_incomplete")) == exp.metadata_incomplete


def _assert_secondary(sec: object, exp: CtaParityExpectedSecondary) -> None:
    if exp.absent:
        assert sec in (None, {}), f"expected no secondary, got {sec!r}"
        return
    assert isinstance(sec, dict), sec
    if exp.route_contains is not None:
        assert exp.route_contains in (sec.get("route") or ""), sec
    if exp.label_substring is not None:
        assert exp.label_substring.lower() in (sec.get("label") or "").lower(), sec


def _assert_case(case: CtaParityCase) -> None:
    env = resolve_take_action_envelope(
        case.requirement,
        property_id=case.property_id,
        property_jurisdiction=case.property_jurisdiction,
    )
    if case.action_type is not None:
        assert env.get("action_type") == case.action_type, case.case_id
    ta = env.get("take_action") or {}
    if case.take_action_suppressed is not None:
        assert ta.get("suppressed") is case.take_action_suppressed, case.case_id
    pri = ta.get("primary")
    if case.primary_none:
        assert pri is None, case.case_id
    elif case.primary is not None:
        assert isinstance(pri, dict), case.case_id
        _assert_primary(pri, case.primary)
    if case.secondary is not None:
        _assert_secondary(ta.get("secondary"), case.secondary)

    if case.skip_priority_projection:
        return

    assert case.priority_compliance_engine is not None, (
        f"{case.case_id}: set priority_compliance_engine (non-empty dict) or skip_priority_projection"
    )

    row = priority_action_row_from_requirement(case.requirement)
    proj = resolve_take_action_for_priority_action(row, compliance_engine=case.priority_compliance_engine)
    if case.priority_primary_action_type is not None:
        assert proj.get("primary_action_type") == case.priority_primary_action_type, case.case_id
    if case.priority_primary_action_url_is_empty:
        assert proj.get("primary_action_url") == "", case.case_id
    elif case.priority_primary_action_url is not None:
        assert proj.get("primary_action_url") == case.priority_primary_action_url, case.case_id
    if case.priority_primary_action_label_equals is not None:
        assert proj.get("primary_action_label") == case.priority_primary_action_label_equals, case.case_id
    if case.priority_primary_action_label_substring is not None:
        assert case.priority_primary_action_label_substring.lower() in (
            proj.get("primary_action_label") or ""
        ).lower(), case.case_id
    if case.priority_secondary_url_contains is not None:
        assert case.priority_secondary_url_contains in (proj.get("secondary_action_url") or ""), case.case_id


@pytest.mark.parametrize("case", all_cta_parity_cases(), ids=lambda c: c.case_id)
def test_cta_parity_envelope_and_priority_projection(case: CtaParityCase) -> None:
    _assert_case(case)


def test_cta_parity_fixture_registry_is_stable_length() -> None:
    """Bump count deliberately when adding cases (doc §2 references P01..)."""
    cases = all_cta_parity_cases()
    assert len(cases) == 10
    ids = [c.case_id for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case_id"
