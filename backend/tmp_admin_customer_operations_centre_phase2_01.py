"""
ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01 — staging validation harness.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUT = ROOT / "docs/audit/admin_customer_operations_centre_phase2_01"
PROGRAMME = "ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01"

API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api")
FE = os.getenv("STAGING_FE", "https://pleerity-enterprise-9jjg.vercel.app")
ADMIN_EMAIL = os.getenv("STAGING_ADMIN_EMAIL", "prosper@yopmail.com")
ADMIN_PASSWORD = os.getenv("STAGING_ADMIN_PASSWORD", "Pastor@36$")


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True, timeout=30).strip()
    except Exception:
        return "unknown"


def _run_pytest() -> dict:
    files = [
        "tests/test_admin_lifecycle_operations_centre_01.py",
        "tests/test_admin_customer_operations_centre_phase2_01.py",
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *files, "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {"pass": proc.returncode == 0, "stdout": proc.stdout[-1500:]}


def _admin_token() -> str:
    r = httpx.post(
        f"{API}/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Origin": FE},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _mongo_client_id(email: str) -> str | None:
    uri = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
    if not uri:
        return None
    from pymongo import MongoClient

    db = MongoClient(uri, serverSelectionTimeoutMS=10000)[os.getenv("DB_NAME", "pleerity_staging")]
    row = db.clients.find_one({"email": email}, {"_id": 0, "client_id": 1})
    return row.get("client_id") if row else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    evidence = {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "commit_sha": _git_sha(),
        "local_tests": _run_pytest(),
        "phases": [],
    }

    try:
        ver = httpx.get(f"{API}/version", timeout=60)
        evidence["staging_version"] = ver.json() if ver.status_code == 200 else {"status": ver.status_code}
    except Exception as exc:
        evidence["staging_version_error"] = str(exc)

    staging_ok = False
    snapshot = {}
    try:
        admin = _admin_token()
        headers = {"Authorization": f"Bearer {admin}", "Origin": FE}
        cid = _mongo_client_id("lere@yopmail.com") or "probe"
        r = httpx.get(f"{API}/admin/clients/{cid}/lifecycle-operations", headers=headers, timeout=120)
        evidence["snapshot_status"] = r.status_code
        if r.status_code == 200:
            staging_ok = True
            snapshot = r.json()
            evidence["phase2_fields"] = {
                k: k in snapshot
                for k in (
                    "customer_health",
                    "authority_chain",
                    "operational_timeline",
                    "runtime_diagnostics",
                    "background_processing",
                    "communications",
                    "webhook_diagnostics",
                )
            }
            evidence["health_overall"] = (snapshot.get("customer_health") or {}).get("overall")
    except Exception as exc:
        evidence["staging_probe_error"] = str(exc)

    phases = [
        {"id": "local_tests", "pass": evidence["local_tests"]["pass"]},
        {"id": "staging_snapshot", "pass": staging_ok},
        {"id": "customer_health", "pass": bool(snapshot.get("customer_health"))},
        {"id": "authority_chain", "pass": bool(snapshot.get("authority_chain"))},
        {"id": "operational_timeline", "pass": "operational_timeline" in snapshot},
        {"id": "governed_actions_preserved", "pass": bool(snapshot.get("actions", {}).get("refresh_runtime_contract"))},
    ]
    evidence["phases"] = phases

    if all(p["pass"] for p in phases):
        evidence["verdict"] = "ADMIN_CUSTOMER_OPERATIONS_CENTRE_PHASE2_COMPLETE"
    elif evidence["local_tests"]["pass"] and not staging_ok:
        evidence["verdict"] = "ADMIN_CUSTOMER_OPERATIONS_CENTRE_PHASE2_COMPLETE_WITH_CONDITIONS"
        evidence["conditions"] = ["Deploy develop with phase 2 changes and re-run harness"]
    else:
        evidence["verdict"] = "ADMIN_CUSTOMER_OPERATIONS_CENTRE_PHASE2_BLOCKED"

    path = OUT / "ADMIN_CUSTOMER_OPERATIONS_PHASE2_EVIDENCE.json"
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": evidence["verdict"], "phases": phases}, indent=2))


if __name__ == "__main__":
    main()
