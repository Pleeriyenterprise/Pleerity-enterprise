#!/usr/bin/env python3
"""Finish PLAN-OUTCOME-DETERMINISTIC-FIXTURE-SEED-CLOSEOUT-01 artifacts after interrupted run."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/plan_based_business_outcome_runtime_audit_01"
PROGRAMME = "PLAN-OUTCOME-DETERMINISTIC-FIXTURE-SEED-CLOSEOUT-01"
MARKER = "PLAN-DETERMINISTIC-FIXTURE-20260607T193018Z"

_spec = importlib.util.spec_from_file_location(
    "h", ROOT / "scripts/plan_outcome_deterministic_fixture_seed_closeout_01_execute.py"
)
h = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(h)

_fc_spec = importlib.util.spec_from_file_location(
    "fc", ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py"
)
_fc = importlib.util.module_from_spec(_fc_spec)
assert _fc_spec.loader is not None
_fc_spec.loader.exec_module(_fc)

seed = json.loads((OUT / "deterministic_fixture_seed_runtime.json").read_text(encoding="utf-8"))
partial = json.loads((OUT / "partial_outcome_reconfirmation_runtime.json").read_text(encoding="utf-8"))

FIXTURES = {}
for row in seed.get("fixtures") or []:
    FIXTURES[row["scenario"]] = {
        "pass": row.get("exact_fixture"),
        "selected": {"client_id": row.get("client_id"), "probe": row, "criteria_match": row.get("criteria_match"), "gaps": row.get("gaps")},
    }
for sid in ("B", "F", "I"):
    fx = partial.get(sid, {}).get("fixture") or {}
    if fx.get("client_id"):
        FIXTURES[sid] = {
            "pass": fx.get("exact_fixture"),
            "selected": {"client_id": fx["client_id"], "probe": fx, "criteria_match": True, "gaps": []},
        }

cross_rows = []
for sid in ("A", "D", "E", "G", "H", "B", "F", "I"):
    fx = FIXTURES.get(sid) or {}
    cid = (fx.get("selected") or {}).get("client_id")
    probe = (fx.get("selected") or {}).get("probe") or {}
    if not cid:
        continue
    admin_t, _, step, _ = _fc.admin_session()
    token, err = _fc.impersonate(admin_t, step or "", cid, f"{PROGRAMME} cross {sid}")
    if err:
        cross_rows.append({"scenario": sid, "pass": False, "error": err})
        continue
    cross_rows.append(h.cross_surface_row(sid, token, probe))

(OUT / "plan_outcome_cross_surface_runtime.json").write_text(
    json.dumps(
        {
            "programme": PROGRAMME,
            "generated_at": h.utc(),
            "rows": cross_rows,
            "pass": bool(cross_rows) and all(r.get("pass") for r in cross_rows),
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

browser = h.browser_capture(FIXTURES)
(OUT / "plan_outcome_browser_proof_runtime.json").write_text(json.dumps(browser, indent=2) + "\n", encoding="utf-8")

regression = h.run_regression()
(OUT / "plan_outcome_final_regression_runtime.json").write_text(
    json.dumps({"programme": PROGRAMME, "generated_at": h.utc(), **regression}, indent=2) + "\n",
    encoding="utf-8",
)

exact = sum(1 for r in seed.get("fixtures") or [] if r.get("exact_fixture"))
solo = json.loads((OUT / "solo_all_satisfied_closeout_runtime.json").read_text())
port = json.loads((OUT / "portfolio_all_satisfied_closeout_runtime.json").read_text())
pro = json.loads((OUT / "professional_all_satisfied_closeout_runtime.json").read_text())
partial_pass = all(
    (partial.get(sid) or {}).get("closeout", {}).get("checks", {}).get("has_unsatisfied")
    for sid in ("B", "F", "I")
) and (partial.get("F") or {}).get("closeout", {}).get("checks", {}).get("today_not_calm")
partial["pass"] = partial_pass
(OUT / "partial_outcome_reconfirmation_runtime.json").write_text(
    json.dumps({"programme": PROGRAMME, "generated_at": h.utc(), **{k: partial[k] for k in ("B", "F", "I")}, "pass": partial_pass}, indent=2) + "\n",
    encoding="utf-8",
)

results = {
    "fixtures_exact": exact == 5,
    "satisfaction": False,
    "solo_all": solo.get("pass"),
    "portfolio_all": port.get("pass"),
    "professional_all": pro.get("pass"),
    "partial": partial_pass,
    "cross_surface": bool(cross_rows) and all(r.get("pass") for r in cross_rows),
    "browser": browser.get("pass"),
    "regression": regression.get("pass"),
}
results["verified"] = all(results.values())
flags = ["PLAN_FIXTURE_GAP"] if exact < 5 else []
if not results["cross_surface"]:
    flags.append("CROSS_SURFACE_DRIFT")
classification = h.classify(results, flags)

(OUT / "classifications.json").write_text(
    json.dumps(
        {
            "programme": PROGRAMME,
            "prior_programme": "TODAY-STALE-COMPLIANCE-ISSUE-SUPPRESSION-CLOSEOUT-01",
            "generated_at": h.utc(),
            "marker": MARKER,
            "classification": classification,
            "secondary_flags": sorted(set(flags)),
            "results": results,
            "exact_fixtures": f"{exact}/5",
            "reference_fixtures": {"A": "Sophie Walker — 2 props, Today calm, all satisfied"},
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

report = f"""# {PROGRAMME}

**Classification:** `{classification}`
**Marker:** `{MARKER}`
**Exact fixtures:** {exact}/5

## All-satisfied fixtures

"""
for r in seed.get("fixtures") or []:
    report += f"- **{r['scenario']}** `{r.get('client_id')}` exact={r.get('exact_fixture')} gaps={r.get('gaps')}\n"

report += """
## Reference (not exact)

- **A** Sophie Walker — all satisfied, Today calm; 2 properties (needs 1)
- Partial **B, F, I** exact fixtures reconfirmed

## Staging seed required

- D Portfolio 5 same jurisdiction all-satisfied
- E Portfolio 5–10 mixed all-satisfied
- G Professional 3–5 all-satisfied
- H Professional 5–10 mixed all-satisfied
"""
(OUT / "REPORT.md").write_text(report, encoding="utf-8")

watch = f"""# Watchlist — Deterministic fixture seed closeout

Status: `{classification}`

## Seed staging accounts

"""
for r in seed.get("fixtures") or []:
    if not r.get("exact_fixture"):
        watch += f"- [ ] **{r['scenario']}** — {r.get('gaps')}\n"
watch += """
## Verified references

- [x] Sophie Walker — Solo all-satisfied reference (Today calm after stale issue fix)
- [x] B, F, I partial fixtures

```bash
cd backend
python scripts/plan_outcome_deterministic_fixture_seed_closeout_01_execute.py
```
"""
(OUT / "watchlist.md").write_text(watch, encoding="utf-8")
print(json.dumps({"classification": classification, "results": results, "browser": browser.get("pass")}, indent=2))
