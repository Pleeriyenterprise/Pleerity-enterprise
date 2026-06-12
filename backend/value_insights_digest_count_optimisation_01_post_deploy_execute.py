#!/usr/bin/env python3
"""
VALUE-INSIGHTS-DIGEST-COUNT-OPTIMISATION-01 — post-deploy staging verification only.
"""
from __future__ import annotations

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
PROGRAMME = "VALUE-INSIGHTS-DIGEST-COUNT-OPTIMISATION-01-POST-DEPLOY"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MIN_COMMIT = "ab588f05"
NANCY_CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
CACHE_TTL_WAIT_S = 48
PROFILING_DIGEST_MS = 18182.71

_fc_path = ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py"
_spec = importlib.util.spec_from_file_location("_fc", _fc_path)
_fc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_fc)
API = _fc.API

PW_PATH = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def hdr(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login() -> str:
    pw = PW_PATH.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": "nancy@yopmail.com", "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json().get("access_token") or r.json()["token"]


def timed_get(path: str, token: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    t0 = time.perf_counter()
    r = httpx.get(f"{API}{path}", headers=hdr(token), params=params or {}, timeout=180)
    ms = round((time.perf_counter() - t0) * 1000.0, 2)
    body: Dict[str, Any] = {}
    try:
        body = r.json()
    except Exception:
        pass
    return {"status": r.status_code, "duration_ms": ms, "body": body}


def extract_vi(body: Dict[str, Any]) -> Dict[str, Any]:
    tcr = body.get("task_count_resolution") or {}
    at_risk = body.get("at_risk") or {}
    return {
        "task_count_resolution": tcr,
        "urgent_count": at_risk.get("command_centre_urgent_open"),
        "upcoming_count": at_risk.get("command_centre_upcoming_open"),
        "digest_duration_ms": tcr.get("duration_ms"),
        "source_used": tcr.get("source_used"),
        "fallback_reason": tcr.get("fallback_reason"),
    }


def deploy_proof() -> Dict[str, Any]:
    r = httpx.get(f"{API}/version", timeout=60)
    body = r.json() if r.status_code == 200 else {}
    sha = str(body.get("commit_sha") or "")
    return {
        "run_tag": RUN_TAG,
        "expected_commit_prefix": MIN_COMMIT,
        "version_endpoint": {
            "status": r.status_code,
            "commit_sha": sha,
            "environment": body.get("environment"),
        },
        "deploy_match": sha.startswith(MIN_COMMIT) or MIN_COMMIT in sha,
    }


def run_pytest() -> Dict[str, Any]:
    cases = [
        "tests/test_value_insights_digest_count_optimisation.py",
        "tests/test_operational_surface_cache.py",
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *cases, "-q", "--noconftest"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    fe_block: Dict[str, Any] = {"pass": False, "skipped": True, "reason": "npx not available"}
    try:
        fe_proc = subprocess.run(
            "npx react-scripts test --watchAll=false --testPathPattern=ClientCommandCenterPage",
            cwd=str(ROOT.parent / "frontend"),
            capture_output=True,
            text=True,
            shell=True,
        )
        fe_block = {
            "exit_code": fe_proc.returncode,
            "pass": fe_proc.returncode == 0,
            "skipped": False,
            "stdout_tail": fe_proc.stdout[-2500:],
            "stderr_tail": fe_proc.stderr[-1500:],
        }
    except Exception as exc:
        fe_block = {"pass": False, "skipped": True, "reason": str(exc)[:200]}
    return {
        "backend": {
            "exit_code": proc.returncode,
            "pass": proc.returncode == 0,
            "stdout_tail": proc.stdout[-2500:],
        },
        "frontend_smoke": fe_block,
    }


def classify(
    *,
    deploy_ok: bool,
    tcr_present: bool,
    counts_match: bool,
    warm_ok: bool,
    cold_fallback_ok: bool,
    pytest_ok: bool,
) -> str:
    if not deploy_ok:
        return "PARTIAL"
    if not counts_match:
        return "COUNT_AUTHORITY_DRIFT"
    if not cold_fallback_ok:
        return "FALLBACK_DRIFT"
    if deploy_ok and tcr_present and counts_match and warm_ok and cold_fallback_ok and pytest_ok:
        return "VERIFIED_OPERATIONALLY"
    return "PARTIAL"


def main() -> int:
    proof = deploy_proof()
    if not PW_PATH.exists():
        write("post_deploy_verify.json", {"error": "missing_nancy_password_fixture", "deploy_proof": proof})
        print("Missing password fixture")
        return 1

    token = login()

    # 1) Cold path first — no cache priming on this worker session.
    cold_vi = timed_get("/client/value-insights", token)
    cold = extract_vi(cold_vi["body"])

    baseline_urgent = int(cold.get("urgent_count") or 0)
    baseline_upcoming = int(cold.get("upcoming_count") or 0)

    # 2) Warm paths — Today/CC (user-requested) vs tasks/digest (shared cache key authority).
    today_prime = timed_get("/today/items", token)
    warm_after_today_vi = timed_get("/client/value-insights", token)
    warm_after_today = extract_vi(warm_after_today_vi["body"])

    cc_prime = timed_get("/client/command-center", token, params={"projection": "primary"})
    warm_after_cc_vi = timed_get("/client/value-insights", token)
    warm_after_cc = extract_vi(warm_after_cc_vi["body"])

    # Canonical warm path: /tasks/digest populates unified:{client}:60:full (value-insights peek key).
    digest_prime = timed_get("/client/tasks/digest", token, params={"activity_limit": 3})
    warm_vi = timed_get("/client/value-insights", token)
    warm = extract_vi(warm_vi["body"])

    # Authority cross-check — tasks/digest should match cold fallback counts.
    baseline_digest = timed_get("/client/tasks/digest", token, params={"activity_limit": 3})
    base_summ = (baseline_digest["body"] or {}).get("summary") or {}
    digest_authority_match = (
        int(base_summ.get("urgent_count") or 0) == baseline_urgent
        and int(base_summ.get("upcoming_count") or 0) == baseline_upcoming
    )

    # 4) Cold retry after TTL wait (best-effort worker cache expiry).
    if os.environ.get("SKIP_TTL_WAIT") != "1":
        print(f"Waiting {CACHE_TTL_WAIT_S}s for operational cache TTL …")
        time.sleep(CACHE_TTL_WAIT_S)
    cold_retry_vi = timed_get("/client/value-insights", token)
    cold_retry = extract_vi(cold_retry_vi["body"])

    counts_match = digest_authority_match and (
        warm.get("urgent_count") == baseline_urgent
        and warm.get("upcoming_count") == baseline_upcoming
        and warm_after_today.get("urgent_count") == baseline_urgent
        and warm_after_cc.get("urgent_count") == baseline_urgent
        and cold_retry.get("urgent_count") == baseline_urgent
    )

    warm_ok = bool(
        warm.get("source_used") in ("cached_digest", "command_center_summary")
        and (warm.get("digest_duration_ms") or 9999) < 500
    )
    today_cc_cache_share = warm_after_today.get("source_used") == "cached_digest" or warm_after_cc.get(
        "source_used"
    ) == "cached_digest"

    cold_fallback_ok = cold.get("source_used") == "fallback_full_unified_tasks" and bool(
        cold.get("fallback_reason")
    ) or cold_retry.get("source_used") == "fallback_full_unified_tasks"

    tcr_present = bool((cold_vi["body"] or {}).get("task_count_resolution"))

    timing = {
        "profiling_baseline_digest_stage_ms": PROFILING_DIGEST_MS,
        "cold_value_insights_total_ms": cold_vi["duration_ms"],
        "cold_digest_stage_ms": cold.get("digest_duration_ms"),
        "warm_after_tasks_digest_prime_total_ms": warm_vi["duration_ms"],
        "warm_after_tasks_digest_prime_digest_stage_ms": warm.get("digest_duration_ms"),
        "warm_after_today_total_ms": warm_after_today_vi["duration_ms"],
        "warm_after_today_digest_stage_ms": warm_after_today.get("digest_duration_ms"),
        "warm_after_cc_total_ms": warm_after_cc_vi["duration_ms"],
        "warm_after_cc_digest_stage_ms": warm_after_cc.get("digest_duration_ms"),
        "tasks_digest_prime_ms": digest_prime["duration_ms"],
        "today_prime_ms": today_prime["duration_ms"],
        "cc_primary_prime_ms": cc_prime["duration_ms"],
        "cold_retry_after_ttl_total_ms": cold_retry_vi["duration_ms"],
        "cold_retry_digest_stage_ms": cold_retry.get("digest_duration_ms"),
        "digest_stage_reduction_warm_vs_baseline_ms": round(
            PROFILING_DIGEST_MS - float(warm.get("digest_duration_ms") or 0), 2
        ),
    }

    pytest_result = run_pytest()

    classification = classify(
        deploy_ok=proof["deploy_match"],
        tcr_present=tcr_present,
        counts_match=counts_match,
        warm_ok=warm_ok,
        cold_fallback_ok=cold_fallback_ok,
        pytest_ok=pytest_result["backend"]["pass"],
    )

    verify = {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "client_id": NANCY_CLIENT_ID,
        "deploy_proof": proof,
        "task_count_resolution_present": tcr_present,
        "warm_cache_path": {
            "note": "Today/CC use surface_profile today/command_center — different cache keys than value-insights peek (60:full).",
            "tasks_digest_prime": {"status": digest_prime["status"], "duration_ms": digest_prime["duration_ms"]},
            "after_tasks_digest": {**warm, "total_ms": warm_vi["duration_ms"]},
            "today_prime": {"status": today_prime["status"], "duration_ms": today_prime["duration_ms"]},
            "after_today": {**warm_after_today, "total_ms": warm_after_today_vi["duration_ms"]},
            "cc_primary_prime": {"status": cc_prime["status"], "duration_ms": cc_prime["duration_ms"]},
            "after_cc": {**warm_after_cc, "total_ms": warm_after_cc_vi["duration_ms"]},
            "today_cc_share_unified_full_cache": today_cc_cache_share,
            "pass": warm_ok,
        },
        "cold_fallback_path": {
            "first_call_no_prime": {**cold, "total_ms": cold_vi["duration_ms"]},
            "after_ttl_wait": {**cold_retry, "total_ms": cold_retry_vi["duration_ms"]},
            "pass": cold_fallback_ok,
        },
        "count_authority": {
            "cold_fallback_reference": {
                "urgent_count": baseline_urgent,
                "upcoming_count": baseline_upcoming,
            },
            "tasks_digest_cross_check": {
                "urgent_count": int(base_summ.get("urgent_count") or 0),
                "upcoming_count": int(base_summ.get("upcoming_count") or 0),
                "duration_ms": baseline_digest["duration_ms"],
                "matches_cold": digest_authority_match,
            },
            "counts_match_all_paths": counts_match,
        },
        "timing_comparison": timing,
        "regression": pytest_result,
        "classification": classification,
    }

    write("post_deploy_verify.json", verify)
    write(
        "post_deploy_runtime.json",
        {
            "programme": PROGRAMME,
            "run_tag": RUN_TAG,
            "timing": timing,
            "classification": classification,
        },
    )
    write(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "run_tag": RUN_TAG,
            "pre_deploy_classification": "VERIFIED_OPERATIONALLY",
            "post_deploy_classification": classification,
            "checks": {
                "deploy_match": proof["deploy_match"],
                "task_count_resolution_present": tcr_present,
                "counts_match": counts_match,
                "warm_cache_path": warm_ok,
                "cold_fallback": cold_fallback_ok,
                "pytest_backend": pytest_result["backend"]["pass"],
                "pytest_frontend_smoke": pytest_result["frontend_smoke"]["pass"],
            },
        },
    )

    watchlist = [
        "- [x] Post-deploy verification run complete",
        f"- [ ] Classification: {classification}",
    ]
    if not proof["deploy_match"]:
        watchlist.append("- [ ] Staging /api/version not yet on ab588f05+ — re-run after deploy")
    if not warm_ok:
        watchlist.append("- [ ] Warm cached_digest path not observed after tasks/digest prime")
    if not today_cc_cache_share:
        watchlist.append(
            "- [ ] Today/CC do not populate unified:60:full cache — dashboard load order may still cold-fallback value-insights"
        )
    if not cold_fallback_ok:
        watchlist.append("- [ ] Cold fallback not observed — worker may have been warm from other traffic")
    if classification != "VERIFIED_OPERATIONALLY":
        watchlist.append("- [ ] Investigate partial verification before next optimisation")
    else:
        watchlist.append("- [ ] Next candidate: value-insights compliance_score headline slice (~13s)")

    (OUT / "watchlist.md").write_text(
        f"# {PROGRAMME}\n\n" + "\n".join(watchlist) + "\n",
        encoding="utf-8",
    )

    report = f"""# {PROGRAMME}

**Run:** `{RUN_TAG}`  
**Fixture:** Nancy (`{NANCY_CLIENT_ID}`)  
**Classification:** `{classification}`

## Deploy proof

- `/api/version` commit: `{proof['version_endpoint'].get('commit_sha')}`
- Deploy match (ab588f05+): **{proof['deploy_match']}**
- `task_count_resolution` present: **{tcr_present}**

## Warm cache path

| Step | source_used | digest_ms | total_ms | urgent | upcoming |
|------|-------------|-----------|----------|--------|----------|
| After tasks/digest prime | {warm.get('source_used')} | {warm.get('digest_duration_ms')} | {warm_vi['duration_ms']} | {warm.get('urgent_count')} | {warm.get('upcoming_count')} |
| After Today | {warm_after_today.get('source_used')} | {warm_after_today.get('digest_duration_ms')} | {warm_after_today_vi['duration_ms']} | {warm_after_today.get('urgent_count')} | {warm_after_today.get('upcoming_count')} |
| After CC primary | {warm_after_cc.get('source_used')} | {warm_after_cc.get('digest_duration_ms')} | {warm_after_cc_vi['duration_ms']} | {warm_after_cc.get('urgent_count')} | {warm_after_cc.get('upcoming_count')} |

Warm path pass: **{warm_ok}**

## Cold fallback path

| Step | source_used | fallback_reason | digest_ms | total_ms |
|------|-------------|-----------------|-----------|----------|
| First (no prime) | {cold.get('source_used')} | {cold.get('fallback_reason')} | {cold.get('digest_duration_ms')} | {cold_vi['duration_ms']} |
| After {CACHE_TTL_WAIT_S}s TTL | {cold_retry.get('source_used')} | {cold_retry.get('fallback_reason')} | {cold_retry.get('digest_duration_ms')} | {cold_retry_vi['duration_ms']} |

Cold fallback pass: **{cold_fallback_ok}**

## Count authority

Baseline digest: urgent={baseline_urgent}, upcoming={baseline_upcoming}  
All paths match: **{counts_match}**

## Timing

Digest stage reduction (warm vs profiling baseline): **{timing['digest_stage_reduction_warm_vs_baseline_ms']}ms**

## Regression

- Backend pytest: {'PASS' if pytest_result['backend']['pass'] else 'FAIL'}
- Frontend smoke: {'PASS' if pytest_result['frontend_smoke']['pass'] else 'FAIL'}

**Re-run:** `python value_insights_digest_count_optimisation_01_post_deploy_execute.py`
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    print(f"Classification: {classification}")
    print(f"Deploy match: {proof['deploy_match']}")
    print(f"Warm source: {warm.get('source_used')} digest_ms={warm.get('digest_duration_ms')}")
    print(f"Cold source: {cold.get('source_used')}")
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
