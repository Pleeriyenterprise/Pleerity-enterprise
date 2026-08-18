#!/usr/bin/env python3
"""Focused stranded-onboarding regression 03 — API-only release/restart and identity guards."""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT = Path(__file__).with_name("stranded_onboarding_runtime_certification_01.py")
OUT = ROOT / "docs" / "audit" / "checkout_success_03" / "focused_regression_03.json"


def _load_so():
    spec = importlib.util.spec_from_file_location("so01", CERT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    so = _load_so()
    email_admin, password = so._load_admin()
    token = so._login(email_admin, password)
    step = so._step_up(token, password)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    email = f"so.regrel.{stamp}@yopmail.com"
    first = so._public_post("/intake/submit", so._intake_payload(email, name="SO RegRel"))
    cid = (first.get("body") or {}).get("client_id")
    in_pending_before = so._client_in_pending(token, cid) if cid else False
    rel = so._execute(
        token, step, cid, "release_and_restart", send_email=False, password=password
    ) if cid else {"ok": False}
    after_rel = so._slim_client(so._unwrap_client(so._client_detail(token, cid))) if cid else {}
    in_pending_after = so._client_in_pending(token, cid) if cid else None
    check = so._public_post("/intake/check-email", {"email": email}) if False else None
    avail = so._get(f"/intake/check-email?email={email}", token) if False else None
    # public check-email
    import httpx
    from urllib.parse import quote
    cr = httpx.get(
        f"{so.API}/intake/check-email",
        params={"email": email},
        headers={"Origin": so.ORIGIN},
        timeout=60,
    )
    second = so._public_post("/intake/submit", so._intake_payload(email, name="SO RegRel 2"))
    new_id = (second.get("body") or {}).get("client_id")
    third = so._public_post("/intake/submit", so._intake_payload(email, name="SO RegRel 3"))
    identities = so._identities_for_email(token, email) if email else []
    active = [
        x
        for x in identities
        if str(x.get("onboarding_identity_status") or "").upper() != "RELEASED_FOR_RESTART"
        and not str(x.get("email") or "").endswith("@released.invalid")
    ]
    out = {
        "email": email,
        "first": {"status": first.get("status"), "client_id": cid},
        "in_pending_before": in_pending_before,
        "release": {
            "status": rel.get("status"),
            "ok": rel.get("ok"),
            "identity": after_rel.get("onboarding_identity_status"),
            "released_canonical_email": after_rel.get("released_canonical_email"),
        },
        "in_pending_after_release": in_pending_after,
        "check_email": {"status": cr.status_code, "body": cr.json() if cr.headers.get("content-type", "").startswith("application/json") else cr.text[:300]},
        "second": {
            "status": second.get("status"),
            "client_id": new_id,
            "restarted_from_client_id": (second.get("body") or {}).get("restarted_from_client_id"),
        },
        "third_duplicate": {
            "status": third.get("status"),
            "ok": third.get("ok"),
            "detail": (third.get("body") or {}).get("detail") if not third.get("ok") else None,
        },
        "identities": identities,
        "active_count": len(active),
        "pass": bool(
            first.get("ok")
            and rel.get("ok")
            and after_rel.get("onboarding_identity_status") == "RELEASED_FOR_RESTART"
            and in_pending_before
            and not in_pending_after
            and second.get("ok")
            and (second.get("body") or {}).get("restarted_from_client_id") == cid
            and not third.get("ok")
            and len(active) == 1
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"pass": out["pass"], "active_count": out["active_count"], "release_status": rel.get("status")}))


if __name__ == "__main__":
    main()
