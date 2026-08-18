#!/usr/bin/env python3
"""CHECKOUT-SUCCESS-ROUTE-FIX-03 — focused staging runtime proof.

Does not print secrets. Writes docs/audit/checkout_success_03/runtime_03.json
and screenshots under docs/audit/checkout_success_03/.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
CERT = Path(__file__).with_name("stranded_onboarding_runtime_certification_01.py")
OUT_DIR = ROOT / "docs" / "audit" / "checkout_success_03"
OUT = ROOT / "docs" / "audit" / "stranded_onboarding_promotion_results_03.json"
SHOTS = OUT_DIR / "screenshots"
API = "https://pleerity-enterprise.onrender.com/api"
FE = "https://pleerity-enterprise-9jjg.vercel.app"


def _load_so():
    spec = importlib.util.spec_from_file_location("so01", CERT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.SHOTS = SHOTS
    return mod


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _probe_routes(so) -> dict:
    from playwright.sync_api import sync_playwright

    SHOTS.mkdir(parents=True, exist_ok=True)
    out = {}
    with sync_playwright() as p:
        browser = so._launch_browser(p)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        for name, path in (
            ("missing", "/checkout/success"),
            ("session", "/checkout/success?session_id=cs_test_abcdefghijklmnopqrstuv"),
            ("malformed", "/checkout/success?session_id=not-a-session"),
        ):
            page.goto(FE + path, wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(1500)
            body = page.inner_text("body")[:2000]
            html_has_page = page.locator("[data-testid='checkout-success-page']").count() > 0
            hero = page.locator("[data-testid='hero-cta-primary']").count()
            testids = page.locator("[data-testid]").evaluate_all(
                "els => els.map(e => e.getAttribute('data-testid'))"
            )
            shot = f"route_{name}.png"
            page.screenshot(path=str(SHOTS / shot), full_page=True)
            out[name] = {
                "final_url": page.url,
                "has_success_page": html_has_page,
                "hero_cta_count": hero,
                "testids": testids,
                "text_preview": body[:900],
                "screenshot": shot,
                "pass": html_has_page and hero == 0 and "Marketing" not in body,
            }
        browser.close()
    return out


def main() -> int:
    so = _load_so()
    SHOTS.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {
        "programme": "CHECKOUT-SUCCESS-ROUTE-FIX-AND-STRANDED-ONBOARDING-PRODUCTION-PROMOTION-03",
        "started_at": _utc(),
        "api": API,
        "frontend": FE,
        "paths": {},
    }
    ver = httpx.get(f"{API}/version", timeout=60)
    results["api_version"] = {"status": ver.status_code, "body": ver.json()}
    health = httpx.get(f"{API}/health", timeout=60)
    try:
        health_body = health.json()
    except Exception:
        health_body = {"raw": health.text[:400]}
    results["api_health"] = {"status": health.status_code, "body": health_body}

    results["direct_routes"] = _probe_routes(so)

    email_admin, password = so._load_admin()
    token = so._login(email_admin, password)
    step = so._step_up(token, password)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    email = f"so.success.{stamp}@yopmail.com"
    submitted = so._public_post("/intake/submit", so._intake_payload(email, name="SO Success Route"))
    client_id = (submitted.get("body") or {}).get("client_id")
    results["paths"]["register"] = {
        "status": submitted.get("status"),
        "ok": submitted.get("ok"),
        "email": email,
        "client_id": client_id,
        "detail": None if submitted.get("ok") else (submitted.get("body") or {}).get("detail"),
    }
    if not client_id:
        results["verdict"] = "HOLD_FOR_CHECKOUT_SUCCESS_ROUTE_FIX"
        results["finished_at"] = _utc()
        OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        print("register failed", flush=True)
        return 1

    exe = so._execute(
        token,
        step,
        client_id,
        "regenerate_payment",
        send_email=True,
        promo_decision="apply_selected",
        selected_invite_code="STAGINGSO01",
        password=password,
    )
    execution = (exe.get("body") or {}).get("execution") if isinstance(exe.get("body"), dict) else {}
    checkout_url = execution.get("checkout_url")
    session_id = execution.get("session_id")
    results["paths"]["recovery_checkout"] = {
        "status": exe.get("status"),
        "ok": exe.get("ok"),
        "session_id": session_id,
        "applied_invite_code": execution.get("applied_invite_code"),
        "promo_decision": execution.get("promo_decision") or "apply_selected",
        "email_sent": execution.get("email_sent"),
        "detail": None if exe.get("ok") else exe.get("body"),
    }
    if checkout_url:
        results["paths"]["checkout_inspect"] = so._inspect_checkout(checkout_url, "so03_checkout.png")
        pay = so._pay_checkout(checkout_url, email, "so03_paid.png")
        results["paths"]["customer_pay"] = pay
        final_url = pay.get("final_url") or ""
        parsed = urlparse(final_url)
        qs = parse_qs(parsed.query)
        sid_in_url = (qs.get("session_id") or [None])[0]
        text = (pay.get("text_preview") or "").lower()
        results["paths"]["success_landing"] = {
            "final_url": final_url,
            "path": parsed.path,
            "session_id_in_url": sid_in_url,
            "session_id_matches": sid_in_url == session_id,
            "text_has_checkout_complete": "checkout complete" in text or "account setup" in text,
            "text_has_homepage_hero": "hero-cta-primary" in text or "get started today" in text,
            "ok": bool(
                pay.get("ok")
                and "checkout/success" in final_url
                and sid_in_url
                and "get started today" not in text
            ),
        }
        if session_id:
            ss = httpx.get(f"{API}/portal/setup-status", params={"session_id": session_id}, timeout=60)
            try:
                ss_body = ss.json()
            except Exception:
                ss_body = {"raw": ss.text[:400]}
            results["paths"]["setup_status_by_session"] = {
                "status": ss.status_code,
                "client_id": ss_body.get("client_id") if isinstance(ss_body, dict) else None,
                "next_action": ss_body.get("next_action") if isinstance(ss_body, dict) else None,
                "payment_state": ss_body.get("payment_state") if isinstance(ss_body, dict) else None,
                "provisioning_status": ss_body.get("provisioning_status") if isinstance(ss_body, dict) else None,
            }
        results["paths"]["provisioning"] = so._wait_provisioned(token, client_id)
        results["paths"]["messages"] = so._messages(token, email)
        results["paths"]["after_client"] = so._slim_client(so._unwrap_client(so._client_detail(token, client_id)))
        rel = so._execute(
            token,
            step,
            client_id,
            "release_and_restart",
            send_email=False,
            password=password,
        )
        results["paths"]["release_provisioned_blocked"] = {
            "status": rel.get("status"),
            "ok": rel.get("ok"),
            "detail": rel.get("body"),
            "pass": (not rel.get("ok")) and rel.get("status") in (400, 409, 403, 422),
        }

    route_ok = all(v.get("pass") for v in (results.get("direct_routes") or {}).values())
    landing_ok = (results.get("paths") or {}).get("success_landing", {}).get("ok") is True
    results["route_ok"] = route_ok
    results["landing_ok"] = landing_ok
    results["finished_at"] = _utc()
    results["verdict"] = (
        "GO_FOR_STRANDED_ONBOARDING_PRODUCTION_PROMOTION"
        if route_ok and landing_ok
        else "HOLD_FOR_CHECKOUT_SUCCESS_ROUTE_FIX"
    )
    OUT_DIR.joinpath("runtime_03.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(results["verdict"], flush=True)
    print("route_ok", route_ok, "landing_ok", landing_ok, flush=True)
    return 0 if results["verdict"].startswith("GO_") else 1


if __name__ == "__main__":
    sys.exit(main())
