"""
OPS-VERIFY-01 manifest constants, bundle layout, and completeness gates (read-only).

Does not connect to MongoDB. Does not mutate authority/workflow systems.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

UNIT_ID = "OPS-VERIFY-01"
UNIT_NAME = "Client Evidence Journey Operational Closure Verification"

READ_ONLY_OBSERVATIONAL = True
IMPLEMENTATION_SCOPE = "operational_verification_capture_and_classify_only"

DEFAULT_CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
DEFAULT_PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
DEFAULT_SLUG = "6fd5ac4c_d35a58ae"

JOURNEY_A = "A_guided_structured_evidence_submit"
JOURNEY_B = "B_primary_document_upload"
JOURNEY_C = "C_supporting_upload_only"
JOURNEY_D = "D_verification_review_optional"

JOURNEYS: Tuple[str, ...] = (JOURNEY_A, JOURNEY_B, JOURNEY_C, JOURNEY_D)
JOURNEYS_MANDATORY: Tuple[str, ...] = (JOURNEY_A, JOURNEY_B, JOURNEY_C)

CLASSIFICATIONS: Tuple[str, ...] = (
    "VERIFIED_OPERATIONALLY",
    "VERIFIED_REPLAY_ONLY",
    "IMPLEMENTED_NOT_VERIFIED",
    "USER_VISIBLE_GAP",
    "ASYNC_CONVERGENCE_PARTIAL",
    "SYSTEM_OUTCOME_UNPROVEN",
    "TRUST_RISK_PRESENT",
)

CHECKPOINTS: Dict[str, Tuple[str, ...]] = {
    JOURNEY_A: (
        "A-1",
        "A-2",
        "A-3",
        "A-4",
        "A-5",
        "A-6",
        "A-7",
        "A-8",
        "A-9",
    ),
    JOURNEY_B: ("B-1", "B-2", "B-3", "B-4", "B-5", "B-6", "B-7"),
    JOURNEY_C: ("C-1", "C-2", "C-3", "C-4"),
    JOURNEY_D: ("D-1", "D-2", "D-3", "D-4"),
}

PROOF_MODES_ALLOWED = ("operational_browser", "replay", "fixture", "unproven")


def bundle_dir(audit_root: Path, slug: str) -> Path:
    return audit_root / f"ops_verify_01_{slug.strip()}"


def bundle_paths(bundle: Path, slug: str) -> Dict[str, Path]:
    return {
        "manifest": bundle / "ops_verify_01_run_manifest.json",
        "baseline": bundle / f"ops_verify_01_baseline_{slug}.json",
        "post_submit": bundle / f"ops_verify_01_post_submit_{slug}.json",
        "convergence": bundle / f"ops_verify_01_convergence_{slug}.json",
        "classifications": bundle / "ops_verify_01_classifications.json",
        "ui_notes": bundle / "ops_verify_01_ui_notes.md",
    }


def build_run_manifest_skeleton(
    *,
    slug: str,
    client_id: str,
    property_id: str,
    requirement_ids: Optional[List[str]] = None,
    journeys_executed: Optional[List[str]] = None,
    verifier: str = "",
) -> Dict[str, Any]:
    run_id = f"ops_verify_01_{slug}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    return {
        "unit_id": UNIT_ID,
        "unit_name": UNIT_NAME,
        "run_id": run_id,
        "slug": slug,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "client_id": client_id,
        "property_id": property_id,
        "requirement_ids": requirement_ids or [],
        "journeys_executed": journeys_executed or [],
        "verifier": verifier,
        "proof_mode": "unproven",
        "replay_or_fixture_driver": False,
        "browser_walkthrough_completed": False,
        "staging_url": "",
        "async_sla_minutes": 15,
        "ui_attestations": {},
        "checkpoint_results": {},
        "notes": "Infrastructure replay proof ≠ operational closure proof.",
        "implementation_scope": IMPLEMENTATION_SCOPE,
        "read_only": READ_ONLY_OBSERVATIONAL,
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def read_json_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def ui_notes_minimal_content() -> str:
    return """# OPS-VERIFY-01 UI notes

Record real staging browser walkthrough evidence only. Replay/fixture drivers do not satisfy operational verification.

## Preconditions
- [ ] Real client login on staging (not TestClient / not harness-only)
- [ ] Requirement id(s) recorded in run manifest
- [ ] Baseline capture completed before user action

## Journey A — Guided structured evidence submit
- Surfaces visited:
- Submit outcome (Submission recorded vs upload-only):
- Requirement details → Your submission visible (Y/N):
- View submission / refresh persistence (Y/N):
- Screenshot refs (paths/filenames):

## Journey B — Primary document upload
- Surfaces visited:
- Document visible in vault (Y/N):
- Requirement linkage coherent (Y/N):
- Screenshot refs:

## Journey C — Supporting-upload-only
- Upload succeeded (Y/N):
- Requirement did NOT present as fully recorded/compliant (Y/N):
- Truthful supporting-only copy shown (Y/N):
- Screenshot refs:

## Journey D — Verification / review (optional)
- Action taken:
- User-visible labels match DB (Y/N):
- Screenshot refs:

## Async convergence observation
- T+0 timestamp:
- T+SLA timestamp:
- Score headline updated (Y/N):
- Tasks/today refreshed (Y/N):
"""


def init_bundle(
    audit_root: Path,
    *,
    slug: str,
    client_id: str = DEFAULT_CLIENT_ID,
    property_id: str = DEFAULT_PROPERTY_ID,
    verifier: str = "",
    overwrite: bool = False,
) -> Path:
    bundle = bundle_dir(audit_root, slug)
    paths = bundle_paths(bundle, slug)
    bundle.mkdir(parents=True, exist_ok=True)
    if not paths["manifest"].is_file() or overwrite:
        write_json(
            paths["manifest"],
            build_run_manifest_skeleton(
                slug=slug,
                client_id=client_id,
                property_id=property_id,
                verifier=verifier,
            ),
        )
    if not paths["ui_notes"].is_file() or overwrite:
        paths["ui_notes"].write_text(ui_notes_minimal_content(), encoding="utf-8")
    return bundle


def assess_bundle_completeness(
    bundle: Path,
    slug: str,
    *,
    journeys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    paths = bundle_paths(bundle, slug)
    journeys = journeys or list(JOURNEYS_MANDATORY)
    present = {k: p.is_file() for k, p in paths.items()}
    manifest = read_json_if_exists(paths["manifest"]) or {}
    ui_notes_ok = present.get("ui_notes") and paths["ui_notes"].stat().st_size > 200
    browser_ok = bool(manifest.get("browser_walkthrough_completed"))
    replay_flag = bool(manifest.get("replay_or_fixture_driver"))
    proof_mode = str(manifest.get("proof_mode") or "unproven")

    needs_post = any(j in journeys for j in (JOURNEY_A, JOURNEY_B, JOURNEY_D))
    needs_convergence = any(j in journeys for j in (JOURNEY_A, JOURNEY_B))

    missing: List[str] = []
    if not present.get("manifest"):
        missing.append("manifest")
    if not present.get("baseline"):
        missing.append("baseline")
    if needs_post and not present.get("post_submit"):
        missing.append("post_submit")
    if needs_convergence and not present.get("convergence"):
        missing.append("convergence")
    if not ui_notes_ok:
        missing.append("ui_notes_substantive")

    operational_evidence_ready = (
        not missing
        and browser_ok
        and not replay_flag
        and proof_mode == "operational_browser"
    )

    return {
        "bundle_dir": str(bundle),
        "files_present": present,
        "missing_for_operational": missing,
        "browser_walkthrough_completed": browser_ok,
        "replay_or_fixture_driver": replay_flag,
        "proof_mode": proof_mode,
        "ui_notes_substantive": ui_notes_ok,
        "operational_evidence_ready": operational_evidence_ready,
    }
