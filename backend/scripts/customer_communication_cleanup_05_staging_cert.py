#!/usr/bin/env python3
"""Cleanup 05 staging cert. Staging only. yopmail recipients. Never production."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from pymongo import MongoClient

BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND / ".env")

EXPECTED_SHA = "2b2bae4cea8723ab1e76eae0b7b15c268072992a"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
PROD_API = "https://pleerity-api-production.onrender.com/api"
NANCY_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
OUT = BACKEND / "docs/audit/customer_communication_cleanup_results_05.json"

ADMIN_EMAIL = (os.getenv("STAGING_ADMIN_EMAIL") or "prosper@yopmail.com").strip()
ADMIN_PW = (os.getenv("STAGING_ADMIN_PASSWORD") or "").strip()
if not ADMIN_PW:
    pw_file = BACKEND / "docs/audit/.ops_verify_temp_pw.txt"
    if pw_file.is_file():
        ADMIN_PW = pw_file.read_text(encoding="utf-8").strip()


def _req(method: str, path: str, token: str = "", **kwargs):
    headers = kwargs.pop("headers", None) or {}
    if token:
        headers = {**headers, "Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    confirmation = kwargs.pop("confirmation", "")
    if confirmation:
        headers["X-Admin-Confirmation-Token"] = confirmation
    url = path if path.startswith("http") else f"{API}{path}"
    r = getattr(httpx, method.lower())(url, headers=headers, timeout=kwargs.pop("timeout", 120), **kwargs)
    try:
        body = r.json()
    except Exception:
        body = {"raw": (r.text or "")[:1500]}
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _mongo():
    uri = os.getenv("MONGO_URL") or os.getenv("MONGO_URI") or ""
    db_name = (os.getenv("DB_NAME") or "").strip()
    host = (urlparse(uri).hostname or "").lower()
    if "prod" in db_name.lower() or "production" in db_name.lower() or "prod" in host or "production" in host:
        raise RuntimeError("production mongo refused")
    if db_name != "pleerity_staging":
        raise RuntimeError(f"unexpected db {db_name}")
    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    return client, client[db_name]


def main() -> None:
    staging = _req("GET", "/version")
    prod = _req("GET", f"{PROD_API}/version")
    sha = (staging.get("body") or {}).get("commit_sha") or ""
    env = (staging.get("body") or {}).get("environment")
    print(json.dumps({"staging": staging.get("body"), "production": prod.get("body")}, indent=2))
    if env != "staging":
        raise SystemExit("not staging")
    if not sha.startswith("2b2bae4c"):
        raise SystemExit(f"staging sha {sha} != {EXPECTED_SHA}")
    if (prod.get("body") or {}).get("environment") != "production":
        raise SystemExit("production check failed")

    token = _req("POST", "/auth/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    if not token["ok"]:
        raise SystemExit(json.dumps({"login": token}))
    access = token["body"]["access_token"]

    ticket = _req(
        "POST",
        "/support/ticket",
        json={
            "subject": "Cleanup 05 staging acknowledgement check",
            "description": "Staging-only support acknowledgement fixture. Safe yopmail recipient.",
            "category": "other",
            "priority": "low",
            "email": "nancy@yopmail.com",
        },
        timeout=90,
    )
    print("ticket", ticket["status"], {k: ticket["body"].get(k) for k in ("ticket_id", "email_sent", "response_window") if isinstance(ticket.get("body"), dict)})

    _, db = _mongo()
    nancy = db.clients.find_one({"client_id": NANCY_ID}, {"_id": 0, "email": 1, "contact_email": 1}) or {}
    em = (nancy.get("contact_email") or nancy.get("email") or "").lower()
    if "yopmail.com" not in em:
        raise RuntimeError("nancy email not yopmail")

    frags = list(
        db.email_templates.find(
            {"is_active": True},
            {"_id": 0, "alias": 1, "subject": 1},
        ).limit(40)
    )
    greeting_errors = list(
        db.message_logs.find(
            {"error_message": {"$regex": "resolve_greeting"}},
            {"_id": 0, "message_id": 1, "created_at": 1, "template_key": 1},
        ).sort("created_at", -1).limit(5)
    )
    print(json.dumps({"db_templates_sample": len(frags), "recent_greeting_errors": greeting_errors}, default=str, indent=2))

    conf = _req(
        "POST",
        "/admin/governance/confirmation-token",
        access,
        json={
            "action_id": "run_scoped_automation_job",
            "reason": "CUSTOMER-COMMUNICATION-QUALITY-CLEANUP-05 scoped compliance check nancy",
            "resource_key": f"compliance_check_morning:{NANCY_ID}",
        },
    )
    job = None
    if conf["ok"]:
        job = _req(
            "POST",
            "/admin/jobs/run",
            access,
            json={
                "job": "compliance_check_morning",
                "client_id": NANCY_ID,
                "scope_type": "CLIENT",
                "reason": "CUSTOMER-COMMUNICATION-QUALITY-CLEANUP-05 scoped compliance check nancy",
            },
            confirmation=conf["body"]["token"],
            timeout=240,
        )
        print("compliance_job", job["status"], str(job.get("body"))[:500])

    print("utc", datetime.now(timezone.utc).isoformat())


if __name__ == "__main__":
    main()
