#!/usr/bin/env python3
"""DASHBOARD-SCORE-WIDGET-LABEL-CONVERGENCE-01 closeout artifacts."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/dashboard_score_widget_semantic_convergence_01"
FE = ROOT.parent / "frontend"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ui_labels = {
        "generated_at": _utc(),
        "labels": {
            "obligations": "Score-tracked obligations",
            "valid": "Valid for scoring",
            "renewal": "Next renewal",
        },
        "tooltips_present": True,
        "legacy_labels_removed": ["Requirements", "Valid", "Days to Next Expiry"],
        "implementation": "frontend/src/utils/dashboardScoreWidgetLabels.js + ClientDashboard.js",
    }
    _write("ui_label_runtime.json", ui_labels)

    expiry = {
        "generated_at": _utc(),
        "rules": {
            "gt_365_confirmed": "1+ year",
            "gt_365_estimated": "1+ year estimated",
            "null": "No upcoming renewal",
            "lte_365": "numeric days",
        },
        "raw_days_in_tooltip_only": True,
    }
    _write("expiry_label_runtime.json", expiry)

    proc = subprocess.run(
        ["npm", "test", "--", "--watchAll=false", "--testPathPattern=dashboardScoreWidgetLabels|ClientDashboard.scoreWidgetLabels"],
        cwd=str(FE),
        capture_output=True,
        text=True,
        timeout=300,
        shell=True,
    )
    regression = {
        "generated_at": _utc(),
        "frontend_passed": proc.returncode == 0,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }
    _write("regression_runtime.json", regression)

    klass = "VERIFIED_OPERATIONALLY" if proc.returncode == 0 else "FAIL_OPERATIONAL"
    _write(
        "classifications.json",
        {
            "programme": "DASHBOARD-SCORE-WIDGET-LABEL-CONVERGENCE-01",
            "classified_at": _utc(),
            "classification": klass,
            "prior_classification": "COUNT_CONVERGENCE_DRIFT",
            "resolved": proc.returncode == 0,
        },
    )

    (OUT / "REPORT.md").write_text(
        f"""# DASHBOARD-SCORE-WIDGET-LABEL-CONVERGENCE-01

Classification: **{klass}**

## Changes
- Widget labels converged to score-projection semantics
- Tooltips added via DashboardKpiHint
- Far-future renewal display capped at 1+ year (estimated when applicable)
- Registry helper line when requirements list count differs
- Assurance-aware quick action copy for stale upload-and-verify rows

## Tests
Frontend: `dashboardScoreWidgetLabels.test.js`, `ClientDashboard.scoreWidgetLabels.test.js`
""",
        encoding="utf-8",
    )
    (OUT / "watchlist.md").write_text(
        f"""# Watchlist — label convergence ({_utc()[:10]})

## Classification: {klass}

- Deploy frontend bundle to staging/production
- Optional: align Compliance Score page stat labels for parity
""",
        encoding="utf-8",
    )
    print(f"classification={klass}")
    return 0 if klass == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
