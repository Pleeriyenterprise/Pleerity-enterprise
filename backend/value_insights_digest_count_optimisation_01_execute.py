#!/usr/bin/env python3
"""
VALUE-INSIGHTS-DIGEST-COUNT-OPTIMISATION-01 — verify cached digest counts + runtime.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/value_insights_digest_count_optimisation_01"
PROGRAMME = "VALUE-INSIGHTS-DIGEST-COUNT-OPTIMISATION-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
NANCY_CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROFILING_BASELINE_MS = 18182.71

_fc_path = ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py"
_spec = importlib.util.spec_from_file_location("_fc", _fc_path)
_fc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_fc)
API = _fc.API

PW_PATH = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v
    if os.environ.get("MONGO_URI") and not os.environ.get("MONGO_URL"):
        os.environ["MONGO_URL"] = os.environ["MONGO_URI"]
    os.environ.setdefault("STRIPE_MODE", "test")


def login() -> str:
    pw = PW_PATH.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": "nancy@yopmail.com", "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json().get("access_token") or r.json()["token"]


def http_timing(path: str, token: str, *, cache_bust: bool = False) -> Dict[str, Any]:
    url = f"{API}{path}"
    if cache_bust:
        url += ("&" if "?" in url else "?") + f"_cb={time.time_ns()}"
    t0 = time.perf_counter()
    r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=180)
    ms = round((time.perf_counter() - t0) * 1000.0, 2)
    body: Dict[str, Any] = {}
    try:
        body = r.json()
    except Exception:
        pass
    tcr = body.get("task_count_resolution") or {}
    return {
        "status": r.status_code,
        "duration_ms": ms,
        "task_count_resolution": tcr,
        "at_risk": body.get("at_risk"),
    }


async def local_authority_and_timing(client_id: str) -> Dict[str, Any]:
    from database import database
    from services.operational_surface_cache import invalidate_client_operational_surfaces
    from services.unified_tasks_service import (
        get_unified_tasks_digest,
        get_unified_tasks_for_client,
        resolve_value_insights_task_counts,
    )
    database.get_db()

    # Authority baseline — full digest rebuild (pre-optimisation behaviour).
    invalidate_client_operational_surfaces(client_id)
    t0 = time.perf_counter()
    baseline_digest = await get_unified_tasks_digest(client_id, activity_limit=3)
    baseline_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    base_summ = baseline_digest.get("summary") or {}

    # Cold resolve — should fallback (cache populated by digest above on same key).
    invalidate_client_operational_surfaces(client_id)
    t1 = time.perf_counter()
    cold_resolve = await resolve_value_insights_task_counts(client_id, activity_limit=3)
    cold_resolve_ms = round((time.perf_counter() - t1) * 1000.0, 2)

    # Warm unified cache then resolve — must populate cache (bypass_cache=False).
    invalidate_client_operational_surfaces(client_id)
    await get_unified_tasks_for_client(
        client_id,
        raw_limit=60,
        surface_profile="full",
        bypass_cache=False,
    )
    t2 = time.perf_counter()
    warm_resolve = await resolve_value_insights_task_counts(client_id, activity_limit=3)
    warm_resolve_ms = round((time.perf_counter() - t2) * 1000.0, 2)

    # Optimised digest stage with cache still warm from previous step.
    t3 = time.perf_counter()
    vi_resolve = await resolve_value_insights_task_counts(client_id, activity_limit=3)
    vi_ms = round((time.perf_counter() - t3) * 1000.0, 2)

    # Today + CC authority references.
    today = await get_unified_tasks_for_client(
        client_id, raw_limit=50, surface_profile="today", bypass_cache=True
    )
    today_summ = today.get("summary") or {}

    from services.command_center_service import get_command_center_primary_bundle

    cc = await get_command_center_primary_bundle(
        client_id, predictive_enabled=False, bypass_cache=True
    )
    cc_summ = cc.get("tasks_digest_summary") or {}

    return {
        "baseline_digest": {
            "urgent_count": int(base_summ.get("urgent_count") or 0),
            "upcoming_count": int(base_summ.get("upcoming_count") or 0),
            "duration_ms": baseline_ms,
        },
        "cold_resolve": {**cold_resolve, "wall_ms": cold_resolve_ms},
        "warm_resolve": {**warm_resolve, "wall_ms": warm_resolve_ms},
        "value_insights_digest_stage": {
            "duration_ms": vi_ms,
            "task_count_resolution": vi_resolve,
            "at_risk": {
                "command_centre_urgent_open": vi_resolve.get("urgent_count"),
                "command_centre_upcoming_open": vi_resolve.get("upcoming_count"),
            },
        },
        "authority": {
            "today_summary": {
                "urgent_count": int(today_summ.get("urgent_count") or 0),
                "upcoming_count": int(today_summ.get("upcoming_count") or 0),
            },
            "command_center_primary": {
                "urgent_count": cc_summ.get("urgent_count"),
                "upcoming_count": cc_summ.get("upcoming_count"),
                "pressure_urgent_count": cc.get("pressure_urgent_count"),
            },
        },
    }


def run_pytest() -> Dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_value_insights_digest_count_optimisation.py",
            "-q",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-2000:],
        "pass": proc.returncode == 0,
    }


async def main() -> None:
    load_dotenv()
    from database import database

    async def _noop_indexes() -> None:
        return None

    database._create_indexes = _noop_indexes  # type: ignore[method-assign]
    await database.connect()

    local = await local_authority_and_timing(NANCY_CLIENT_ID)
    pytest_result = run_pytest()

    base = local["baseline_digest"]
    warm = local["warm_resolve"]
    vi = local["value_insights_digest_stage"]
    tcr = vi.get("task_count_resolution") or {}

    counts_match = (
        int(tcr.get("urgent_count") or -1) == base["urgent_count"]
        and int(tcr.get("upcoming_count") or -1) == base["upcoming_count"]
    )

    write(
        "count_authority_comparison.json",
        {
            "programme": PROGRAMME,
            "run_tag": RUN_TAG,
            "client_id": NANCY_CLIENT_ID,
            "baseline_full_digest": base,
            "optimised_value_insights": vi.get("at_risk"),
            "task_count_resolution": tcr,
            "counts_match_baseline_digest": counts_match,
            "authority_references": local["authority"],
            "notes": [
                "Value insights authority is unified_tasks digest (full profile, raw_limit=60).",
                "Today surface_profile may differ from full profile counts by design.",
                "CC primary upcoming_count is often null until secondary projection runs.",
            ],
        },
    )

    write(
        "before_after_runtime.json",
        {
            "programme": PROGRAMME,
            "run_tag": RUN_TAG,
            "client_id": NANCY_CLIENT_ID,
            "before": {
                "source": "value_insights_and_today_cold_path_profiling_01",
                "vi_unified_tasks_digest_ms": PROFILING_BASELINE_MS,
                "http_value_insights_cold_ms": 57701.8,
            },
            "after_local": {
                "baseline_full_digest_ms": base["duration_ms"],
                "cold_resolve_ms": local["cold_resolve"]["wall_ms"],
                "warm_resolve_ms": warm["wall_ms"],
                "warm_resolve_source": warm.get("source_used"),
                "value_insights_digest_stage_ms": vi["duration_ms"],
                "digest_stage_reduction_ms": round(PROFILING_BASELINE_MS - float(warm.get("wall_ms") or 0), 2),
            },
        },
    )

    write(
        "fallback_behavior.json",
        {
            "programme": PROGRAMME,
            "run_tag": RUN_TAG,
            "cold_cache": local["cold_resolve"],
            "warm_cache": local["warm_resolve"],
            "expected": {
                "cold": "fallback_full_unified_tasks when operational cache empty",
                "warm": "cached_digest when unified tasks cache populated",
            },
        },
    )

    write(
        "regression_runtime.json",
        {
            "programme": PROGRAMME,
            "run_tag": RUN_TAG,
            "pytest": pytest_result,
            "local_counts_match": counts_match,
        },
    )

    http_block: Dict[str, Any] = {"attempted": False, "note": "pre-deploy local verification only"}
    if PW_PATH.exists():
        try:
            token = login()
            http_block = {
                "attempted": True,
                "value_insights_cold": http_timing("/client/value-insights", token, cache_bust=True),
                "value_insights_warm": http_timing("/client/value-insights", token),
            }
        except Exception as exc:
            http_block = {"attempted": True, "error": str(exc)}

    warm_cached = warm.get("source_used") == "cached_digest"
    vi_cached = tcr.get("source_used") == "cached_digest"
    classification = "VERIFIED_OPERATIONALLY"
    if not counts_match:
        classification = "COUNT_AUTHORITY_DRIFT"
    elif not pytest_result["pass"]:
        classification = "PARTIAL"
    elif not warm_cached and not vi_cached:
        classification = "FALLBACK_DRIFT"
    elif not warm_cached or not vi_cached:
        classification = "PARTIAL"

    write(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "run_tag": RUN_TAG,
            "classification": classification,
            "checks": {
                "counts_match_baseline_digest": counts_match,
                "warm_resolve_used_cached_digest": warm_cached,
                "vi_resolve_used_cached_digest": vi_cached,
                "pytest_pass": pytest_result["pass"],
            },
            "http": http_block,
        },
    )

    watchlist = [
        "- [ ] Deploy optimisation to staging and re-measure HTTP value-insights cold/warm",
        "- [ ] Confirm task_count_resolution surfaced in staging API response",
        "- [ ] Validate cached_digest hit rate when dashboard loads CC primary before value-insights",
        "- [ ] Push blocked on protected main — confirm with operator if not yet published",
    ]
    if http_block.get("attempted") and http_block.get("value_insights_warm"):
        tcr_http = (http_block["value_insights_warm"].get("task_count_resolution") or {})
        if not tcr_http:
            watchlist.insert(0, "- [ ] Staging API missing task_count_resolution — deploy pending")

    (OUT / "watchlist.md").write_text(
        f"# {PROGRAMME} watchlist\n\n" + "\n".join(watchlist) + "\n",
        encoding="utf-8",
    )

    report = f"""# {PROGRAMME}

**Run:** `{RUN_TAG}`  
**Fixture:** Nancy (`{NANCY_CLIENT_ID}`)  
**Classification:** `{classification}`

## Summary

Value insights now resolves `urgent_count` / `upcoming_count` via `resolve_value_insights_task_counts`, preferring operational surface cache before falling back to full `get_unified_tasks_digest`.

## Count authority

| Source | urgent | upcoming |
|--------|--------|----------|
| Baseline full digest | {base['urgent_count']} | {base['upcoming_count']} |
| Optimised value insights | {tcr.get('urgent_count')} | {tcr.get('upcoming_count')} |
| Match baseline | {counts_match} | |

Warm resolve: **{warm.get('source_used')}** in **{warm.get('wall_ms')}ms** (was ~{PROFILING_BASELINE_MS}ms digest stage).

## Regression

- pytest: {'PASS' if pytest_result['pass'] else 'FAIL'}
- Local digest stage wall: {vi['duration_ms']}ms

## HTTP

{json.dumps(http_block, indent=2)}

## Artifacts

- `before_after_runtime.json`
- `count_authority_comparison.json`
- `fallback_behavior.json`
- `regression_runtime.json`
- `classifications.json`

**Re-run:** `python value_insights_digest_count_optimisation_01_execute.py`
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(f"Wrote audit artifacts to {OUT}")
    print(f"Classification: {classification}")

    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
