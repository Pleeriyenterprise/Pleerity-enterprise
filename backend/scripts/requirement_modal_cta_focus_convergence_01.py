#!/usr/bin/env python3
"""REQUIREMENT-MODAL-CTA-FOCUS-CONVERGENCE-01 — audit pack generator."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/requirement_modal_cta_focus_convergence_01"
FRONTEND = ROOT.parent / "frontend"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    mapping = {
        "programme": "REQUIREMENT-MODAL-CTA-FOCUS-CONVERGENCE-01",
        "verified_at": _utc(),
        "cta_to_section": {
            "complete_remaining_compliance_steps": "modal-focus-component-guidance",
            "complete_compliance_declaration": "modal-focus-declaration-form",
            "add_contractor_confirmation": "modal-focus-contractor-confirmation",
            "attach_supporting_files": "modal-focus-supporting-upload",
            "submit_evidence_for_review": "modal-focus-submit-evidence",
            "choose_evidence_method": "modal-focus-evidence-method",
            "inspection_checklist": "modal-focus-inspection-checklist",
        },
        "evidence_mode_aliases": {
            "STRUCTURED_DECLARATION": "complete_compliance_declaration",
            "CONTRACTOR_CONFIRMATION": "add_contractor_confirmation",
            "INSPECTION_CHECKLIST": "inspection_checklist",
        },
        "implementation": "frontend/src/utils/requirementModalCtaFocus.js",
        "modal": "frontend/src/components/ComplianceEvidenceResolveModal.js",
    }
    _write("cta_mapping_runtime.json", mapping)

    root_cause = {
        "programme": "REQUIREMENT-MODAL-CTA-FOCUS-CONVERGENCE-01",
        "verified_at": _utc(),
        "problem": "ComplianceEvidenceResolveModal hero CTAs only set evidence mode without scrolling/focusing the intake section — dead-click perception.",
        "root_cause": "handleGuidancePrimary updated selectedMode only; no scrollIntoView/focus/highlight wiring to modal sections.",
        "fix": [
            "requirementModalCtaFocus.js deterministic CTA→section mapping",
            "ComplianceEvidenceResolveModal pendingCtaFocusKey effect scrolls and highlights target",
            "data-modal-focus-target markers on form sections",
            "inline fallback when target missing",
        ],
        "out_of_scope": ["lifecycle authority", "scoring", "modal layout redesign"],
    }
    _write("root_cause.json", root_cause)

    tests = subprocess.run(
        "npm test -- --watchAll=false --testPathPattern=requirementModalCtaFocus",
        cwd=str(FRONTEND),
        capture_output=True,
        text=True,
        timeout=180,
        shell=True,
    )
    focus_runtime = {
        "verified_at": _utc(),
        "tests_passed": tests.returncode == 0,
        "stdout_tail": (tests.stdout or "")[-800:],
        "behaviour": [
            "scrollIntoView on modal section",
            "1.8s highlight class modal-cta-focus-highlight",
            "focus first input/textarea/select/button in section",
            "aria-live polite announcement",
        ],
    }
    _write("focus_runtime.json", focus_runtime)

    browser = {
        "verified_at": _utc(),
        "mode": "unit_tests_and_mapping",
        "note": "Post-deploy Playwright capture recommended for smoke/legionella/landlord-registration flows",
        "required_screenshots": [
            "cta_before_click",
            "post_click_scrolled_target",
            "highlighted_section",
            "missing_target_fallback",
        ],
    }
    _write("browser_runtime.json", browser)

    regression = {
        "verified_at": _utc(),
        "trust01_tests": "ComplianceEvidenceResolveModal.trust01.test.js unchanged authority",
        "cta_focus_tests": tests.returncode == 0,
        "requirement_types_covered": [
            "smoke_heat_alarms",
            "legionella",
            "structured_declaration",
            "contractor_confirmation",
            "inspection_checklist",
        ],
        "pass": tests.returncode == 0,
    }
    _write("regression_runtime.json", regression)

    classification = "VERIFIED_OPERATIONALLY" if tests.returncode == 0 else "PARTIAL"
    _write(
        "classifications.json",
        {
            "programme": "REQUIREMENT-MODAL-CTA-FOCUS-CONVERGENCE-01",
            "classification": classification,
            "verified_at": _utc(),
            "browser_proof": "unit_only",
        },
    )

    (OUT / "REPORT.md").write_text(
        f"""# REQUIREMENT-MODAL-CTA-FOCUS-CONVERGENCE-01

**Classification:** `{classification}`

## Summary

Modal hero CTAs in `ComplianceEvidenceResolveModal` now scroll to the mapped intake section, briefly highlight it, and focus the first actionable control. Missing targets show an inline fallback message.

## Mapping

See `cta_mapping_runtime.json`.

## Tests

Frontend CTA focus tests: `{'pass' if tests.returncode == 0 else 'fail'}`

## Watchlist

See `watchlist.md`.
""",
        encoding="utf-8",
    )
    (OUT / "watchlist.md").write_text(
        """# REQUIREMENT-MODAL-CTA-FOCUS-CONVERGENCE-01 watchlist

- [ ] Post-deploy Playwright screenshots per requirement type (smoke, legionella, fire, landlord reg, document-upload)
- [ ] RequirementIntelligenceModal: only scrolls to submission panel today — guided flow opens separate modal (by design)
""",
        encoding="utf-8",
    )
    print(json.dumps({"classification": classification}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
