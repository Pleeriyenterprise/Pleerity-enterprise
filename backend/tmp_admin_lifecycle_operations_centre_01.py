"""
ADMIN-LIFECYCLE-OPERATIONS-CENTRE-01 — staging + local validation harness.
develop / staging only. No production.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUT = ROOT / "docs/audit/admin_lifecycle_operations_centre_01"
PROGRAMME = "ADMIN-LIFECYCLE-OPERATIONS-CENTRE-01"

API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api")
FE = os.getenv("STAGING_FE", "https://pleerity-enterprise-9jjg.vercel.app")
ADMIN_EMAIL = os.getenv("STAGING_ADMIN_EMAIL", "prosper@yopmail.com")
ADMIN_PASSWORD = os.getenv("STAGING_ADMIN_PASSWORD", "Pastor@36$")

STAGING_ACCOUNTS = (
    ("lere@yopmail.com", "ACTIVE"),
    ("allison@yopmail.com", "SUSPENDED"),
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True, timeout=30).strip()
    except Exception:
        return "unknown"


def _run_pytest() -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "pytest", "tests/test_admin_lifecycle_operations_centre_01.py", "-q"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-2000:],
        "stderr": proc.stderr[-1000:],
        "pass": proc.returncode == 0,
    }


def _admin_token() -> str:
    r = httpx.post(
        f"{API}/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Origin": FE},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _step_up(headers: dict) -> dict:
    h = dict(headers)
    su = httpx.post(f"{API}/auth/step-up/verify", headers=h, json={"password": ADMIN_PASSWORD}, timeout=90)
    if su.status_code == 200 and su.json().get("step_up_token"):
        h["X-Step-Up-Token"] = su.json()["step_up_token"]
    return h


def _governance_confirm(headers: dict, action_id: str, resource_key: str, reason: str) -> dict:
    h = dict(headers)
    conf = httpx.post(
        f"{API}/admin/governance/confirmation-token",
        headers=h,
        json={"action_id": action_id, "reason": reason, "resource_key": resource_key},
        timeout=60,
    )
    if conf.status_code == 200 and conf.json().get("token"):
        h["X-Admin-Confirmation-Token"] = conf.json()["token"]
    return h


def _mongo_client_id(email: str) -> Optional[str]:
    uri = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
    if not uri:
        return None
    from pymongo import MongoClient

    db = MongoClient(uri, serverSelectionTimeoutMS=10000)[os.getenv("DB_NAME", "pleerity_staging")]
    row = db.clients.find_one({"email": email}, {"_id": 0, "client_id": 1})
    return row.get("client_id") if row else None


def _probe_staging(admin_headers: dict, client_id: str) -> Dict[str, Any]:
    reason = f"{PROGRAMME} staging validation probe — read snapshot only"
    snap = httpx.get(
        f"{API}/admin/clients/{client_id}/lifecycle-operations",
        headers=admin_headers,
        timeout=120,
    )
    out: Dict[str, Any] = {
        "client_id": client_id,
        "snapshot_status": snap.status_code,
    }
    if snap.status_code != 200:
        out["snapshot_error"] = snap.text[:500]
        return out

    body = snap.json()
    lc = body.get("lifecycle") or {}
    actions = body.get("actions") or {}
    out.update(
        {
            "lifecycle_state": lc.get("lifecycle_state"),
            "portal_mode": body.get("lifecycle", {}).get("portal_mode"),
            "runtime_version": lc.get("runtime_version"),
            "has_billing_mirror": bool(body.get("billing", {}).get("stripe_subscription_id")),
            "actions": {
                k: {"available": v.get("available"), "blocked_reason": v.get("blocked_reason")}
                for k, v in actions.items()
                if isinstance(v, dict) and "available" in v
            },
            "no_manual_override_fields": "set_lifecycle_state" not in str(actions),
        }
    )

    refresh = httpx.post(
        f"{API}/admin/clients/{client_id}/lifecycle-operations/refresh-runtime-contract",
        headers=_governance_confirm(admin_headers, "lifecycle_ops_refresh_runtime", client_id, reason),
        json={"reason": reason},
        timeout=120,
    )
    out["refresh_runtime_status"] = refresh.status_code
    if refresh.status_code == 200:
        out["refresh_runtime_result"] = {
            k: refresh.json().get(k)
            for k in ("success", "runtime_version_before", "runtime_version_after", "lifecycle_state")
        }
    else:
        out["refresh_runtime_error"] = refresh.text[:300]

    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    evidence: Dict[str, Any] = {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "commit_sha": _git_sha(),
        "staging_api": API,
        "local_tests": _run_pytest(),
        "staging": {},
        "phases": [],
    }

    try:
        ver = httpx.get(f"{API}/version", timeout=60)
        evidence["staging"]["version_status"] = ver.status_code
        if ver.status_code == 200:
            evidence["staging"]["deployed_sha"] = ver.json().get("commit_sha")
    except Exception as exc:
        evidence["staging"]["version_error"] = str(exc)

    staging_deployed = False
    try:
        admin = _admin_token()
        ah = _step_up({"Authorization": f"Bearer {admin}", "Origin": FE})
        probe_cid = _mongo_client_id(STAGING_ACCOUNTS[0][0]) or "probe-missing"
        probe = httpx.get(
            f"{API}/admin/clients/{probe_cid}/lifecycle-operations",
            headers=ah,
            timeout=60,
        )
        evidence["staging"]["endpoint_probe_status"] = probe.status_code
        staging_deployed = probe.status_code == 200
        if probe.status_code == 404 and "Not Found" in probe.text:
            evidence["staging"]["deployment_note"] = (
                "Lifecycle operations API not deployed on staging yet — local implementation validated only"
            )
    except Exception as exc:
        evidence["staging"]["admin_probe_error"] = str(exc)

    account_results: List[Dict[str, Any]] = []
    if staging_deployed:
        admin = _admin_token()
        ah = _step_up({"Authorization": f"Bearer {admin}", "Origin": FE})
        for email, expected_hint in STAGING_ACCOUNTS:
            cid = _mongo_client_id(email)
            row: Dict[str, Any] = {"email": email, "expected_hint": expected_hint, "client_id": cid}
            if not cid:
                row["skip"] = "client_id not resolved (MONGO_URI missing or account not found)"
            else:
                row.update(_probe_staging(ah, cid))
            account_results.append(row)
        evidence["staging_accounts"] = account_results

    phases = [
        {"id": "local_admin_api_tests", "pass": evidence["local_tests"]["pass"]},
        {
            "id": "staging_endpoint_deployed",
            "pass": staging_deployed,
            "note": "Requires develop deploy with admin_lifecycle_operations router",
        },
    ]
    if staging_deployed and account_results:
        phases.append(
            {
                "id": "inspect_active_customer",
                "pass": any(
                    r.get("lifecycle_state") == "ACTIVE" for r in account_results if r.get("snapshot_status") == 200
                ),
            }
        )
        phases.append(
            {
                "id": "inspect_suspended_customer",
                "pass": any(
                    r.get("lifecycle_state") == "SUSPENDED" for r in account_results if r.get("snapshot_status") == 200
                ),
            }
        )
        phases.append(
            {
                "id": "refresh_runtime_contract",
                "pass": any(r.get("refresh_runtime_status") == 200 for r in account_results),
            }
        )
        phases.append(
            {
                "id": "no_manual_lifecycle_override",
                "pass": all(r.get("no_manual_override_fields", True) for r in account_results),
            }
        )

    evidence["phases"] = phases
    all_pass = all(p["pass"] for p in phases)
    deploy_pending = not staging_deployed
    if all_pass:
        evidence["verdict"] = "ADMIN_LIFECYCLE_OPERATIONS_CENTRE_COMPLETE"
    elif deploy_pending and evidence["local_tests"]["pass"]:
        evidence["verdict"] = "ADMIN_LIFECYCLE_OPERATIONS_CENTRE_COMPLETE_WITH_CONDITIONS"
        evidence["conditions"] = [
            "Push develop and deploy backend (Render) + frontend (Vercel alias) with lifecycle-ops tab",
            "Re-run this harness against staging for full E2E sign-off",
        ]
    else:
        evidence["verdict"] = "ADMIN_LIFECYCLE_OPERATIONS_CENTRE_BLOCKED"

    out_path = OUT / "ADMIN_LIFECYCLE_OPERATIONS_EVIDENCE.json"
    out_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": evidence["verdict"], "phases": phases, "out": str(out_path)}, indent=2))


if __name__ == "__main__":
    main()
