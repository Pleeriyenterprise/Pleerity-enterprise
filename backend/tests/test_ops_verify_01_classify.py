"""OPS-VERIFY-01 classify gates — bundle completeness and classification boundaries."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ops_verify_01_classify import classify_bundle
from scripts.ops_verify_01_manifest import (
    JOURNEY_A,
    JOURNEY_B,
    JOURNEY_C,
    assess_bundle_completeness,
    build_run_manifest_skeleton,
    init_bundle,
    write_json,
)


@pytest.fixture
def bundle_dir(tmp_path: Path) -> Path:
    slug = "test_slug"
    audit = tmp_path / "audit"
    init_bundle(audit, slug=slug)
    return audit / f"ops_verify_01_{slug}"


def test_incomplete_bundle_defaults_implemented_not_verified(bundle_dir: Path) -> None:
    slug = "test_slug"
    payload = classify_bundle(bundle_dir, slug, journeys=[JOURNEY_A])
    row = payload["classifications"][0]
    assert row["classification"] == "IMPLEMENTED_NOT_VERIFIED"
    assert "bundle_incomplete" in " ".join(row["reasons"])


def test_replay_mode_never_verified_operationally(bundle_dir: Path) -> None:
    slug = "test_slug"
    manifest_path = bundle_dir / "ops_verify_01_run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["proof_mode"] = "replay"
    manifest["replay_or_fixture_driver"] = True
    manifest["browser_walkthrough_completed"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    baseline = {
        "cer_rows": [],
        "requirement": {"authority": {"fingerprint": "aaa"}},
        "property_score": {"compliance_score_pending": False},
    }
    post = {
        "cer_count_delta_from_baseline": 1,
        "cer_rows": [{"compliance_evidence_id": "x"}],
        "authority_changed_from_baseline": True,
        "requirement": {"authority": {"fingerprint": "bbb"}},
        "documents": [],
    }
    write_json(bundle_dir / f"ops_verify_01_baseline_{slug}.json", baseline)
    write_json(bundle_dir / f"ops_verify_01_post_submit_{slug}.json", post)
    write_json(bundle_dir / f"ops_verify_01_convergence_{slug}.json", {"async_convergence_partial_signals": {}})

    ui = bundle_dir / "ops_verify_01_ui_notes.md"
    ui.write_text(ui.read_text(encoding="utf-8") + "\n" + ("x" * 250), encoding="utf-8")

    payload = classify_bundle(bundle_dir, slug, journeys=[JOURNEY_A])
    assert payload["classifications"][0]["classification"] == "VERIFIED_REPLAY_ONLY"


def test_operational_ready_still_requires_checkpoints(bundle_dir: Path) -> None:
    slug = "test_slug"
    manifest_path = bundle_dir / "ops_verify_01_run_manifest.json"
    manifest = build_run_manifest_skeleton(slug=slug, client_id="c", property_id="p")
    manifest["proof_mode"] = "operational_browser"
    manifest["browser_walkthrough_completed"] = True
    manifest["replay_or_fixture_driver"] = False
    manifest["checkpoint_results"] = {JOURNEY_A: {cp: True for cp in ("A-1", "A-2", "A-3", "A-4", "A-5", "A-6", "A-7", "A-8", "A-9")}}
    manifest["ui_attestations"] = {
        JOURNEY_A: {"submission_visible": True, "refresh_persisted": True},
    }
    write_json(manifest_path, manifest)

    baseline = {
        "cer_rows": [],
        "requirement": {"authority": {"fingerprint": "aaa"}},
        "property_score": {"compliance_score_pending": False},
    }
    post = {
        "cer_count_delta_from_baseline": 1,
        "cer_rows": [{"compliance_evidence_id": "x"}],
        "authority_changed_from_baseline": True,
        "documents": [],
    }
    conv = {
        "async_convergence_partial_signals": {},
        "score_converged_observable": True,
    }
    write_json(bundle_dir / f"ops_verify_01_baseline_{slug}.json", baseline)
    write_json(bundle_dir / f"ops_verify_01_post_submit_{slug}.json", post)
    write_json(bundle_dir / f"ops_verify_01_convergence_{slug}.json", conv)
    ui = bundle_dir / "ops_verify_01_ui_notes.md"
    ui.write_text(ui.read_text(encoding="utf-8") + "\n" + ("verified " * 40), encoding="utf-8")

    completeness = assess_bundle_completeness(bundle_dir, slug)
    assert completeness["operational_evidence_ready"] is True

    payload = classify_bundle(bundle_dir, slug, journeys=[JOURNEY_A])
    assert payload["classifications"][0]["classification"] == "VERIFIED_OPERATIONALLY"


def test_journey_c_trust_risk_when_cer_created(bundle_dir: Path) -> None:
    slug = "test_slug"
    manifest_path = bundle_dir / "ops_verify_01_run_manifest.json"
    manifest = build_run_manifest_skeleton(slug=slug, client_id="c", property_id="p")
    manifest["browser_walkthrough_completed"] = True
    write_json(manifest_path, manifest)

    post = {"cer_count_delta_from_baseline": 1, "cer_rows": [{"id": 1}]}
    write_json(bundle_dir / f"ops_verify_01_post_submit_{slug}.json", post)

    payload = classify_bundle(bundle_dir, slug, journeys=[JOURNEY_C])
    assert payload["classifications"][0]["classification"] == "TRUST_RISK_PRESENT"
