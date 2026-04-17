"""Baseline bundle → draft documents (no planner hooks)."""
from __future__ import annotations

from services.compliance_registry_admin_service import (
    bundle_entries_to_drafts,
    load_baseline_bundle_from_disk,
    validate_registry_draft,
)


def test_load_baseline_bundle_and_build_valid_drafts():
    bundle = load_baseline_bundle_from_disk()
    assert bundle.get("import_bundle_version")
    entries = bundle.get("entries")
    assert isinstance(entries, list) and len(entries) >= 8

    actor = {"portal_user_id": "test", "email": "test@example.com"}
    drafts, summary = bundle_entries_to_drafts(bundle, actor=actor)
    assert summary.get("drafts_built") == len(entries)
    assert not summary.get("duplicate_codes_in_bundle")

    failures = []
    for doc in drafts:
        errs = validate_registry_draft(doc)
        if errs:
            failures.append((doc.get("canonical_code"), doc.get("scope_key"), errs))
    assert not failures, failures

    codes_scopes = {(d.get("canonical_code"), d.get("scope_key")) for d in drafts}
    assert ("OCCUPATION_CONTRACT", "WALES") in codes_scopes
    assert ("LANDLORD_REGISTRATION", "SCOTLAND") in codes_scopes
    assert ("GAS_SAFETY", "DEFAULT") in codes_scopes
