#!/usr/bin/env python3
"""
LEGAL-CONTENT-PUBLICATION-CONVERGENCE-01
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/legal_content_management_publication_runtime_audit_01"
PROGRAMME = "LEGAL-CONTENT-PUBLICATION-CONVERGENCE-01"

SLUG = "6fd5ac4c_d35a58ae"
CLIENT_EMAIL = "nancy@yopmail.com"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "2.0"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"LEGAL-PUBLISH-CONVERGE-{RUN_TAG}"

PAGES = {
    "privacy": "/legal/privacy",
    "terms": "/legal/terms",
    "cookies": "/legal/cookies",
    "accessibility": "/accessibility",
    "careers": "/careers",
    "partnerships": "/partnerships",
    "about": "/about",
}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_artifact(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def read_pw(rel: str, env_key: str = "") -> str:
    if env_key and os.environ.get(env_key):
        return os.environ[env_key].strip()
    p = ROOT / rel
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def h(token: str = "") -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {"Content-Type": "application/json"}


def req(method: str, path: str, token: str = "", **kwargs) -> httpx.Response:
    time.sleep(PACE)
    url = path if path.startswith("http") else f"{API}{path}"
    headers = kwargs.pop("headers", None) or (h(token) if token else h())
    for attempt in range(4):
        try:
            resp = getattr(httpx, method)(url, headers=headers, timeout=kwargs.pop("timeout", 120), **kwargs)
            if resp.status_code == 429 and attempt < 3:
                time.sleep(20 * (attempt + 1))
                continue
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout):
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("request failed")


def _login_post(path: str, payload: dict) -> httpx.Response:
    last: Optional[httpx.Response] = None
    for attempt in range(8):
        r = httpx.post(f"{API}{path}", json=payload, timeout=120)
        last = r
        if r.status_code != 429:
            return r
        time.sleep(25 * (attempt + 1))
    return last if last else httpx.Response(429)


def login_admin() -> Tuple[str, dict]:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt", "OPS_VERIFY_ADMIN_PASSWORD")
    r = _login_post("/auth/admin/login", {"email": email, "password": pw})
    r.raise_for_status()
    body = r.json()
    return body.get("access_token") or body["token"], body.get("user") or {}


def login_client() -> str:
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt", "OPS_VERIFY_PASSWORD")
    r = _login_post("/auth/login", {"email": CLIENT_EMAIL, "password": pw})
    r.raise_for_status()
    return r.json()["access_token"]


def login_contractor() -> str:
    pw = read_pw(f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt", "OPS_CONTRACTOR_PASSWORD")
    r = _login_post("/auth/contractor-login", {"email": CONTRACTOR_EMAIL, "password": pw})
    r.raise_for_status()
    return r.json()["access_token"]


def fetch_public_text_playwright(path: str) -> Tuple[int, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        r = httpx.get(f"{FRONTEND}{path}", timeout=120, follow_redirects=True)
        return r.status_code, re.sub(r"<[^>]+>", " ", r.text)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(4000)
        return 200, page.locator("body").inner_text()
    except Exception:
        return 0, ""
    finally:
        browser.close()
        p.stop()


def part_architecture(at: str) -> dict:
    pub = req("get", "/public/legal-content/privacy", "", timeout=60)
    has_api = pub.status_code == 200
    body = pub.json() if has_api else {}
    return {
        "at_utc": utc(),
        "pattern": "public_read_api_with_canonical_fallback",
        "public_api_path": "/api/public/legal-content/{slug}",
        "public_api_status": pub.status_code,
        "sample_source": body.get("source"),
        "sample_has_html": bool(body.get("content_html")),
        "admin_path": "/api/admin/legal-content/{slug}",
        "frontend": "PublicLegalContentPage.jsx fetches public API; server canonical fallback when CMS empty",
        "pass": has_api and body.get("content"),
    }


def part_seed(at: str) -> dict:
    seed = req("post", "/admin/legal-content/seed-canonical", at, timeout=120)
    results = []
    if seed.status_code == 200:
        results = (seed.json() or {}).get("results") or []
    inv = req("get", "/admin/legal-content", at, timeout=90)
    rows = inv.json() if inv.status_code == 200 else []
    by_slug = {r.get("slug"): r for r in rows if isinstance(r, dict)}
    probes = []
    for slug in PAGES:
        row = by_slug.get(slug, {})
        probes.append({
            "slug": slug,
            "version": row.get("version", 0),
            "content_length": len(row.get("content") or ""),
            "provenance": row.get("provenance"),
            "pass": (row.get("version") or 0) > 0 and len((row.get("content") or "").strip()) > 100,
        })
    return {
        "at_utc": utc(),
        "seed_status": seed.status_code,
        "seed_results": results,
        "probes": probes,
        "pass": seed.status_code == 200 and all(p["pass"] for p in probes),
    }


def part_sanitisation(at: str) -> dict:
    slug = "partnerships"
    probe = (
        f"# Safe\n\n**bold** _italic_\n\n- item\n\n"
        f"[link](https://example.com)\n\n"
        f"<script>alert('x')</script>\n\n{MARKER}-SANIT"
    )
    before = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    bbody = before.json() if before.status_code == 200 else {}
    put = req("put", f"/admin/legal-content/{slug}", at, json={"slug": slug, "title": bbody.get("title") or "Partnerships", "content": probe}, timeout=90)
    stored = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    sbody = stored.json() if stored.status_code == 200 else {}
    pub = req("get", f"/public/legal-content/{slug}", "", timeout=60)
    pbody = pub.json() if pub.status_code == 200 else {}
    _, rendered = fetch_public_text_playwright(PAGES[slug])
    restore = req("put", f"/admin/legal-content/{slug}", at, json={"slug": slug, "title": bbody.get("title") or "Partnerships", "content": bbody.get("content") or ""}, timeout=90)
    sc = sbody.get("content") or ""
    html = pbody.get("content_html") or ""
    return {
        "at_utc": utc(),
        "put_status": put.status_code,
        "stored_script_stripped": "<script>" not in sc.lower(),
        "public_html_no_script": "<script>" not in html.lower(),
        "marker_on_public_api": f"{MARKER}-SANIT" in (pbody.get("content") or ""),
        "marker_on_public_page": f"{MARKER}-SANIT" in rendered,
        "restore_ok": restore.status_code == 200,
        "pass": put.status_code == 200 and "<script>" not in sc.lower() and "<script>" not in html.lower() and restore.status_code == 200,
    }


def public_screenshots() -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed", "pages": []}
    shot_dir = BUNDLE / "screenshots" / "convergence"
    shot_dir.mkdir(parents=True, exist_ok=True)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    pages = []
    try:
        for slug, path in PAGES.items():
            page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(4000)
            shot = f"convergence_{slug}.png"
            page.screenshot(path=str(shot_dir / shot))
            body = page.locator("body").inner_text()
            pages.append({
                "slug": slug,
                "path": path,
                "screenshot": f"screenshots/convergence/{shot}",
                "pass": len(body) > 200,
                "raw_markdown_leak": "##" in body[:500] and "Privacy" not in body[:200],
            })
        return {"at_utc": utc(), "pages": pages, "pass": all(x["pass"] for x in pages)}
    except Exception as exc:
        return {"pass": False, "error": str(exc)[:200], "pages": pages}
    finally:
        browser.close()
        p.stop()


def part_rendering() -> dict:
    probes = []
    for slug, path in PAGES.items():
        pub = req("get", f"/public/legal-content/{slug}", "", timeout=60)
        body = pub.json() if pub.status_code == 200 else {}
        _, text = fetch_public_text_playwright(path)
        probes.append({
            "slug": slug,
            "api_status": pub.status_code,
            "source": body.get("source"),
            "version": body.get("version"),
            "public_text_length": len(text),
            "pass": pub.status_code == 200 and len(text) > 150,
        })
    shots = public_screenshots()
    return {"at_utc": utc(), "probes": probes, "browser_shots": shots, "pass": all(p["pass"] for p in probes) and shots.get("pass", False)}


def part_edit_publication(at: str) -> dict:
    slug = "careers"
    before = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    bbody = before.json() if before.status_code == 200 else {}
    prev = bbody.get("content") or ""
    prev_v = bbody.get("version") or 0
    marker_content = f"{prev}\n\n<!-- {MARKER} -->\n\nConvergence audit marker."
    put = req("put", f"/admin/legal-content/{slug}", at, json={"slug": slug, "title": bbody.get("title") or "Careers", "content": marker_content}, timeout=90)
    after = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    abody = after.json() if after.status_code == 200 else {}
    pub = req("get", f"/public/legal-content/{slug}", "", timeout=60)
    pbody = pub.json() if pub.status_code == 200 else {}
    time.sleep(2)
    _, pub_text = fetch_public_text_playwright(PAGES[slug])
    marker_on_api = MARKER in (pbody.get("content") or "")
    marker_on_page = MARKER in pub_text
    restore = req("put", f"/admin/legal-content/{slug}", at, json={"slug": slug, "title": bbody.get("title") or "Careers", "content": prev}, timeout=90)
    time.sleep(2)
    _, pub_text_after = fetch_public_text_playwright(PAGES[slug])
    logs = req("get", "/admin/audit-logs", at, params={"action": "ADMIN_ACTION", "limit": 30}, timeout=90)
    rows = (logs.json() or {}).get("logs") or []
    legal_rows = [r for r in rows if (r.get("metadata") or {}).get("action_type") in ("LEGAL_CONTENT_UPDATED", "LEGAL_CONTENT_RESTORED")]
    return {
        "at_utc": utc(),
        "put_status": put.status_code,
        "version_incremented": (abody.get("version") or 0) > prev_v,
        "marker_on_public_api": marker_on_api,
        "marker_on_public_page": marker_on_page,
        "restored": restore.status_code == 200,
        "marker_removed_publicly": MARKER not in pub_text_after,
        "audit_rows": len(legal_rows),
        "pass": put.status_code == 200 and marker_on_api and marker_on_page and restore.status_code == 200 and MARKER not in pub_text_after,
    }


def part_reset(at: str) -> dict:
    probes = []
    backup_slug = "cookies"
    before = req("get", f"/admin/legal-content/{backup_slug}", at, timeout=60)
    bbody = before.json() if before.status_code == 200 else {}
    backup = {"title": bbody.get("title"), "content": bbody.get("content")}
    for slug in PAGES:
        reset = req("post", f"/admin/legal-content/{slug}/reset-default", at, timeout=90)
        pub = req("get", f"/public/legal-content/{slug}", "", timeout=60)
        pbody = pub.json() if pub.status_code == 200 else {}
        probes.append({
            "slug": slug,
            "reset_status": reset.status_code,
            "public_nonempty": len((pbody.get("content") or "").strip()) > 50,
            "pass": reset.status_code == 200 and len((pbody.get("content") or "").strip()) > 50,
        })
    restore = req("put", f"/admin/legal-content/{backup_slug}", at, json={"slug": backup_slug, "title": backup.get("title") or "Cookie Policy", "content": backup.get("content") or ""}, timeout=90)
    return {
        "at_utc": utc(),
        "probes": probes,
        "about_reset_ok": next((p for p in probes if p["slug"] == "about"), {}).get("reset_status") == 200,
        "restored_backup": restore.status_code == 200,
        "pass": all(p["pass"] for p in probes),
    }


def part_admin_ui_copy() -> dict:
    path = ROOT.parent / "frontend/src/pages/AdminLegalContentPage.jsx"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return {
        "at_utc": utc(),
        "instant_misleading_removed": "Changes apply instantly" not in text,
        "publish_copy_present": "publish" in text.lower() and "versioned" in text.lower(),
        "save_publish_label": "Save & Publish" in text,
        "auth_token_fixed": "auth_token" in text,
        "pass": "Changes apply instantly" not in text and "Save & Publish" in text and "auth_token" in text,
    }


def part_version_restore(at: str) -> dict:
    slug = "careers"
    before = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    bbody = before.json() if before.status_code == 200 else {}
    versions = req("get", f"/admin/legal-content/{slug}/versions", at, timeout=60)
    vrows = versions.json() if versions.status_code == 200 else []
    target = vrows[-1] if vrows else None
    restore_status = None
    if target and target.get("version"):
        r = req("post", f"/admin/legal-content/{slug}/restore/{target['version']}", at, timeout=90)
        restore_status = r.status_code
    final = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    fbody = final.json() if final.status_code == 200 else {}
    return {
        "at_utc": utc(),
        "versions_count": len(vrows),
        "has_previous_content": any("previous_content" in v for v in vrows[:5]),
        "restore_endpoint_status": restore_status,
        "final_version": fbody.get("version"),
        "pass": versions.status_code == 200 and len(vrows) >= 1 and restore_status == 200,
    }


def part_permissions(at: str, ct: str, contractor_t: str) -> dict:
    probes = []
    backup = req("get", "/admin/legal-content/partnerships", at, timeout=60)
    bbody = backup.json() if backup.status_code == 200 else {}
    pub = req("get", "/public/legal-content/privacy", "", timeout=60)
    pub_body = pub.json() if pub.status_code == 200 else {}
    leak = any(k in json.dumps(pub_body).lower() for k in ("audit", "previous_content", "updated_by_user_id", "bearer"))
    admin_status = req(
        "put",
        "/admin/legal-content/partnerships",
        at,
        json={"slug": "partnerships", "title": bbody.get("title") or "Partnerships", "content": (bbody.get("content") or "") + "\nperm-probe"},
        timeout=60,
    ).status_code
    probes.append({"name": "admin_put", "status": admin_status, "pass": admin_status == 200})
    for name, tok, expect in [
        ("landlord_put", ct, (401, 403)),
        ("contractor_put", contractor_t, (401, 403)),
        ("unauth_put", "", (401, 403)),
    ]:
        status = req(
            "put",
            "/admin/legal-content/partnerships",
            tok,
            json={"slug": "partnerships", "title": "x", "content": "y"},
            timeout=60,
        ).status_code
        passed = status in expect
        probes.append({"name": name, "status": status, "pass": passed})
    probes.append({"name": "public_read", "status": pub.status_code, "pass": pub.status_code == 200})
    req(
        "put",
        "/admin/legal-content/partnerships",
        at,
        json={"slug": "partnerships", "title": bbody.get("title") or "Partnerships", "content": bbody.get("content") or ""},
        timeout=90,
    )
    return {
        "at_utc": utc(),
        "probes": probes,
        "no_metadata_leak": not leak,
        "pass": all(p["pass"] for p in probes) and not leak,
    }


def part_alignment() -> dict:
    checks = []
    for slug, terms in [
        ("privacy", ["gdpr", "stripe", "data", "retention"]),
        ("cookies", ["cookie", "analytics"]),
        ("terms", ["subscription", "recurring", "stripe", "cancel"]),
        ("accessibility", ["wcag", "contact"]),
    ]:
        pub = req("get", f"/public/legal-content/{slug}", "", timeout=60)
        text = ((pub.json() or {}).get("content") or "").lower()
        hits = [t for t in terms if t in text]
        checks.append({"slug": slug, "hits": hits, "pass": len(hits) >= 2})
    return {"at_utc": utc(), "checks": checks, "pass": all(c["pass"] for c in checks)}


def part_concurrency(at: str) -> dict:
    slug = "partnerships"
    base = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    bbody = base.json() if base.status_code == 200 else {}

    def save_once(n: int) -> int:
        return req("put", f"/admin/legal-content/{slug}", at, json={"slug": slug, "title": bbody.get("title") or "Partnerships", "content": f"{bbody.get('content','')}\n{n}"}, timeout=90).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = [f.result() for f in as_completed([pool.submit(save_once, 1), pool.submit(save_once, 2)])]
    pub = req("get", f"/public/legal-content/{slug}", "", timeout=60)
    restore = req("put", f"/admin/legal-content/{slug}", at, json={"slug": slug, "title": bbody.get("title") or "Partnerships", "content": bbody.get("content") or ""}, timeout=90)
    return {
        "at_utc": utc(),
        "concurrent_codes": codes,
        "public_version": (pub.json() or {}).get("version"),
        "restored": restore.status_code == 200,
        "pass": all(c == 200 for c in codes) and restore.status_code == 200,
    }


def part_regression() -> dict:
    suites = [
        "tests/test_legal_content_publication.py",
        "tests/test_cms_site_builder.py",
        "tests/test_admin_action_governance_policy.py",
    ]
    out = {"suites": [], "pass": True, "at_utc": utc()}
    for suite in suites:
        proc = subprocess.run([sys.executable, "-m", "pytest", suite, "-q", "--tb=no"], cwd=str(ROOT), capture_output=True, text=True)
        row = {"suite": suite, "ok": proc.returncode == 0, "exit_code": proc.returncode}
        out["suites"].append(row)
        out["pass"] = out["pass"] and row["ok"]
    return out


def classify(results: Dict[str, bool]) -> dict:
    blockers = [k for k, v in results.items() if not v]
    flags = []
    if not results.get("architecture"):
        flags.append("PUBLICATION_DRIFT")
    if not results.get("seed"):
        flags.append("CONTENT_ALIGNMENT_DRIFT")
    if not results.get("sanitisation"):
        flags.append("SANITISATION_DRIFT")
    if not results.get("edit_publication"):
        flags.append("PUBLICATION_DRIFT")
    if not results.get("permissions"):
        flags.append("PERMISSION_DRIFT")
    clf = "VERIFIED_OPERATIONALLY"
    if blockers:
        clf = "PARTIAL" if len(blockers) <= 3 else "FAIL_OPERATIONAL"
    if "PUBLICATION_DRIFT" in flags and blockers:
        clf = "PARTIAL" if len(blockers) <= 4 else clf
    return {
        "programme": PROGRAMME,
        "classification": clf,
        "secondary_flags": sorted(set(flags)),
        "blockers": blockers,
        "checklist": results,
        "classified_at_utc": utc(),
        "run_tag": RUN_TAG,
    }


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    at, _ = login_admin()
    ct = login_client()
    contractor_t = login_contractor()
    results: Dict[str, bool] = {}

    arch = part_architecture(at)
    write_artifact("publication_architecture_runtime.json", arch)
    results["architecture"] = arch.get("pass", False)

    seed = part_seed(at)
    write_artifact("cms_seed_runtime.json", seed)
    results["seed"] = seed.get("pass", False)

    san = part_sanitisation(at)
    write_artifact("sanitisation_runtime.json", san)
    results["sanitisation"] = san.get("pass", False)

    render = part_rendering()
    write_artifact("public_rendering_runtime.json", render)
    results["rendering"] = render.get("pass", False)

    edit = part_edit_publication(at)
    write_artifact("edit_publication_runtime.json", edit)
    results["edit_publication"] = edit.get("pass", False)

    reset = part_reset(at)
    write_artifact("reset_default_convergence_runtime.json", reset)
    results["reset"] = reset.get("pass", False)

    ui = part_admin_ui_copy()
    write_artifact("admin_ui_copy_runtime.json", ui)
    results["admin_ui"] = ui.get("pass", False)

    ver = part_version_restore(at)
    write_artifact("version_restore_runtime.json", ver)
    results["version_restore"] = ver.get("pass", False)

    perm = part_permissions(at, ct, contractor_t)
    write_artifact("legal_publication_permissions_runtime.json", perm)
    results["permissions"] = perm.get("pass", False)

    align = part_alignment()
    write_artifact("content_alignment_recheck_runtime.json", align)
    results["alignment"] = align.get("pass", False)

    conc = part_concurrency(at)
    write_artifact("publication_cache_concurrency_runtime.json", conc)
    results["concurrency"] = conc.get("pass", False)

    reg = part_regression()
    write_artifact("legal_publication_regression_runtime.json", reg)
    results["regression"] = reg.get("pass", False)

    clf = classify(results)
    write_artifact("classifications.json", clf)

    report = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{clf['classification']}`",
        f"**Run tag:** `{RUN_TAG}`",
        "",
        "## Summary",
        "Governed legal_content CMS is wired to public pages via `/api/public/legal-content/{slug}` with canonical server fallback.",
        "Public React pages fetch CMS content; admin save publishes immediately.",
        "",
        "## Checklist",
    ]
    for k, v in results.items():
        report.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        report.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    (BUNDLE / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    watch = [
        "# Legal content publication watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
        f"- Convergence run: `{RUN_TAG}`",
        "",
    ]
    if clf["classification"] == "VERIFIED_OPERATIONALLY":
        watch.extend([
            "- [x] Public pages consume governed CMS content",
            "- [x] Canonical seed, sanitisation, edit→publish, reset-all-slugs verified",
        ])
    else:
        watch.extend([
            "- [ ] Deploy backend + frontend convergence to staging/production",
            "- [ ] Re-run convergence harness after deploy",
        ])
    watch.extend([
        "",
        "## Optional follow-ups",
        "- [ ] Admin UI: restore-to-version button (API exists)",
        "- [ ] CDN cache headers tuning if propagation delay observed",
    ])
    (BUNDLE / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
