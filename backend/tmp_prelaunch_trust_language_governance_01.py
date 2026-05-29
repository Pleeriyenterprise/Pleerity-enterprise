#!/usr/bin/env python3
"""PRELAUNCH-TRUST-LANGUAGE-GOVERNANCE-01 — authority layer + drift prevention verification."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_trust_language_governance_01"
PROGRAMME = "PRELAUNCH-TRUST-LANGUAGE-GOVERNANCE-01"

GOVERNANCE_TARGETS = [
    ROOT / "services/trust_language_governance.py",
    ROOT.parent / "docs/governance/TRUST_LANGUAGE_GOVERNANCE.md",
    ROOT / "services/scoring_explanation_copy.py",
    ROOT.parent / "frontend/src/utils/trustLanguageGovernance.js",
    ROOT.parent / "frontend/src/utils/scoringExplanationCopy.js",
    ROOT / "services/compliance_trending.py",
    ROOT / "services/assistant_retrieval_service.py",
    ROOT / "services/assistant_prompt.py",
    ROOT / "routes/client.py",
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def authority_audit() -> dict:
    missing = [str(p.relative_to(ROOT.parent)) for p in GOVERNANCE_TARGETS if not p.exists()]
    from services.trust_language_governance import COPY_AUTHORITY_REGISTRY, EXPLAINABILITY_TIERS

    return {
        "registry_entries": len(COPY_AUTHORITY_REGISTRY),
        "explainability_tiers": list(EXPLAINABILITY_TIERS.keys()),
        "missing_targets": missing,
        "pass": not missing,
    }


def governance_tests() -> dict:
    import pytest

    exit_code = pytest.main(
        [
            "-q",
            str(ROOT / "tests/test_trust_language_governance.py"),
            str(ROOT / "tests/test_scoring_explanation_copy.py"),
            "--tb=no",
        ]
    )
    return {"pytest_exit_code": exit_code, "pass": exit_code == 0}


def trend_and_assistant_sample() -> dict:
    from services.trust_language_governance import (
        build_score_trend_explanation,
        operational_score_key_reasons,
        validate_customer_copy,
    )

    trend = build_score_trend_explanation(
        compare_days=7,
        score_change=-3,
        change_summaries=["1 new overdue item(s)"],
    )
    reasons = operational_score_key_reasons(
        {"status_score": 75, "document_score": 60, "expiry_score": 100, "overdue_penalty_score": 100}
    )
    violations = validate_customer_copy(trend) + sum(
        (validate_customer_copy(r) for r in reasons), []
    )
    return {
        "trend_sample": trend,
        "reasons_sample": reasons,
        "violations": violations,
        "pass": not violations,
    }


def classify(auth: dict, tests: dict, sample: dict) -> str:
    if auth.get("missing_targets"):
        return "EXPLANATION_FRAGMENTATION_RISK"
    if not tests.get("pass") or not sample.get("pass"):
        return "TRUST_DRIFT_RISK"
    return "TRUST_GOVERNED"


def main() -> int:
    auth = authority_audit()
    tests = governance_tests()
    sample = trend_and_assistant_sample()
    classification = classify(auth, tests, sample)

    result = {
        "programme": PROGRAMME,
        "classification": classification,
        "authority_audit": auth,
        "governance_tests": tests,
        "sample_outputs": sample,
        "captured_at": _utc(),
    }
    _write("authority_audit.json", auth)
    _write("governance_tests.json", tests)
    _write("sample_outputs.json", sample)
    _write("classifications.json", result)
    _write(
        "watchlist.md",
        "# Watchlist\n\n"
        + (
            "- Governance layer active — re-run browser audit after deploy.\n"
            if classification == "TRUST_GOVERNED"
            else "- Review classifications.json blockers.\n"
        ),
    )
    print(json.dumps(result, indent=2))
    return 0 if classification == "TRUST_GOVERNED" else 1


if __name__ == "__main__":
    sys.exit(main())
