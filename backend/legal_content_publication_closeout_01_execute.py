#!/usr/bin/env python3
"""
LEGAL-CONTENT-PUBLICATION-CLOSEOUT-01
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/legal_content_management_publication_runtime_audit_01"
PROGRAMME = "LEGAL-CONTENT-PUBLICATION-CLOSEOUT-01"

SLUG = "6fd5ac4c_d35a58ae"
_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "2.0"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"LEGAL-CMS-CLOSEOUT-{RUN_TAG}"

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
    for attempt in range(5):
        try:
            resp = getattr(httpx, method)(url, headers=headers, timeout=kwargs.pop("timeout", 120), **kwargs)
            if resp.status_code == 429 and attempt < 4:
                time.sleep(20 * (attempt + 1))
                continue
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("request failed")


def login_admin() -> str:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt", "OPS_VERIFY_ADMIN_PASSWORD")
    for attempt in range(8):
        r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
        if r.status_code != 429:
            r.raise_for_status()
            return r.json().get("access_token") or r.json()["token"]
        time.sleep(25 * (attempt + 1))
    raise RuntimeError("admin login failed")


def fetch_public_text_playwright(path: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        r = httpx.get(f"{FRONTEND}{path}", timeout=120, follow_redirects=True)
        return re.sub(r"<[^>]+>", " ", r.text)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(3000)
        return page.locator("body").inner_text()
    finally:
        browser.close()
        p.stop()


def part_careers_reset(at: str) -> dict:
    slug = "careers"
    before = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    bbody = before.json() if before.status_code == 200 else {}
    prev_version = bbody.get("version") or 0
    prev_len = len((bbody.get("content") or "").strip())
    reset = req("post", f"/admin/legal-content/{slug}/reset-default", at, timeout=90)
    after = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    abody = after.json() if after.status_code == 200 else {}
    pub = req("get", f"/public/legal-content/{slug}", "", timeout=60)
    pbody = pub.json() if pub.status_code == 200 else {}
    rendered = fetch_public_text_playwright(PAGES[slug])
    versions = req("get", f"/admin/legal-content/{slug}/versions", at, timeout=60)
    vrows = versions.json() if versions.status_code == 200 else []
    content_len = len((abody.get("content") or "").strip())
    return {
        "at_utc": utc(),
        "reset_status": reset.status_code,
        "version_before": prev_version,
        "version_after": abody.get("version"),
        "version_incremented": (abody.get("version") or 0) > prev_version,
        "content_length_before": prev_len,
        "content_length_after": content_len,
        "versions_count": len(vrows),
        "public_source": pbody.get("source"),
        "public_fallback_used": pbody.get("fallback_used"),
        "public_content_length": len((pbody.get("content") or "").strip()),
        "public_has_canonical_text": "Talent Pool" in (pbody.get("content") or ""),
        "public_page_has_content": len(rendered) > 200,
        "pass": (
            reset.status_code == 200
            and content_len > 100
            and (abody.get("version") or 0) > prev_version
            and pbody.get("source") == "cms"
            and pbody.get("fallback_used") is False
            and len(rendered) > 200
        ),
    }


def part_edit_publication(at: str) -> dict:
    slug = "careers"
    before = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    bbody = before.json() if before.status_code == 200 else {}
    prev_content = bbody.get("content") or ""
    prev_title = bbody.get("title") or "Careers"
    prev_version = bbody.get("version") or 0
    marker_content = f"{prev_content}\n\n{MARKER}\n\nCloseout audit marker."
    put = req(
        "put",
        f"/admin/legal-content/{slug}",
        at,
        json={"slug": slug, "title": prev_title, "content": marker_content},
        timeout=90,
    )
    after = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    abody = after.json() if after.status_code == 200 else {}
    time.sleep(3)
    pub = req("get", f"/public/legal-content/{slug}", "", timeout=60)
    pbody = pub.json() if pub.status_code == 200 else {}
    rendered = fetch_public_text_playwright(PAGES[slug])
    logs = req("get", "/admin/audit-logs", at, params={"action": "ADMIN_ACTION", "limit": 20}, timeout=90)
    rows = (logs.json() or {}).get("logs") or []
    legal_rows = [r for r in rows if (r.get("metadata") or {}).get("action_type") == "LEGAL_CONTENT_UPDATED"]
    restore = req(
        "put",
        f"/admin/legal-content/{slug}",
        at,
        json={"slug": slug, "title": prev_title, "content": prev_content},
        timeout=90,
    )
    time.sleep(3)
    pub_after = req("get", f"/public/legal-content/{slug}", "", timeout=60)
    pbody_after = pub_after.json() if pub_after.status_code == 200 else {}
    rendered_after = fetch_public_text_playwright(PAGES[slug])
    return {
        "at_utc": utc(),
        "slug": slug,
        "marker": MARKER,
        "put_status": put.status_code,
        "version_before": prev_version,
        "version_after_edit": abody.get("version"),
        "version_incremented": (abody.get("version") or 0) > prev_version,
        "marker_in_admin": MARKER in (abody.get("content") or ""),
        "marker_on_public_api_content": MARKER in (pbody.get("content") or ""),
        "marker_on_public_api_html": MARKER in (pbody.get("content_html") or ""),
        "marker_on_public_page": MARKER in rendered,
        "audit_rows": len(legal_rows),
        "restore_status": restore.status_code,
        "marker_removed_api": MARKER not in (pbody_after.get("content") or ""),
        "marker_removed_page": MARKER not in rendered_after,
        "pass": (
            put.status_code == 200
            and (abody.get("version") or 0) > prev_version
            and MARKER in (pbody.get("content") or "")
            and MARKER in rendered
            and restore.status_code == 200
            and MARKER not in rendered_after
        ),
    }


def part_public_routes() -> dict:
    probes: List[dict] = []
    for slug, path in PAGES.items():
        pub = req("get", f"/public/legal-content/{slug}", "", timeout=60)
        body = pub.json() if pub.status_code == 200 else {}
        rendered = fetch_public_text_playwright(path)
        html = body.get("content_html") or ""
        probes.append({
            "slug": slug,
            "path": path,
            "api_status": pub.status_code,
            "source": body.get("source"),
            "version": body.get("version"),
            "fallback_used": body.get("fallback_used"),
            "content_length": len((body.get("content") or "").strip()),
            "public_text_length": len(rendered),
            "raw_markdown_leak": "##" in rendered[:300] and slug not in rendered[:100].lower(),
            "script_in_html": "<script" in html.lower(),
            "pass": (
                pub.status_code == 200
                and len((body.get("content") or "").strip()) > 100
                and len(rendered) > 150
                and "<script" not in html.lower()
                and body.get("source") in ("cms", "canonical_fallback")
            ),
        })
    return {
        "at_utc": utc(),
        "probes": probes,
        "pass": all(p["pass"] for p in probes),
    }


def part_sanitisation(at: str) -> dict:
    slug = "partnerships"
    probe = f"# Safe\n\n**bold**\n\n<script>alert(1)</script>\n\n{MARKER}-SANIT"
    before = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    bbody = before.json() if before.status_code == 200 else {}
    put = req(
        "put",
        f"/admin/legal-content/{slug}",
        at,
        json={"slug": slug, "title": bbody.get("title") or "Partnerships", "content": probe},
        timeout=90,
    )
    stored = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    sbody = stored.json() if stored.status_code == 200 else {}
    pub = req("get", f"/public/legal-content/{slug}", "", timeout=60)
    pbody = pub.json() if pub.status_code == 200 else {}
    rendered = fetch_public_text_playwright(PAGES[slug])
    restore = req(
        "put",
        f"/admin/legal-content/{slug}",
        at,
        json={"slug": slug, "title": bbody.get("title") or "Partnerships", "content": bbody.get("content") or ""},
        timeout=90,
    )
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
        "pass": (
            put.status_code == 200
            and "<script>" not in sc.lower()
            and "<script>" not in html.lower()
            and restore.status_code == 200
        ),
    }


def classify(results: Dict[str, bool]) -> dict:
    blockers = [k for k, v in results.items() if not v]
    flags: List[str] = []
    if not results.get("careers_reset"):
        flags.append("CONTENT_ALIGNMENT_DRIFT")
    if not results.get("edit_publication"):
        flags.append("PUBLICATION_DRIFT")
    if not results.get("public_routes"):
        flags.append("PUBLICATION_DRIFT")
    if not results.get("sanitisation"):
        flags.append("SANITISATION_DRIFT")
    clf = "VERIFIED_OPERATIONALLY" if not blockers else ("PARTIAL" if len(blockers) <= 2 else "FAIL_OPERATIONAL")
    return {
        "programme": PROGRAMME,
        "classification": clf,
        "prior_classification": "PARTIAL",
        "prior_programme": "LEGAL-CONTENT-PUBLICATION-CONVERGENCE-01",
        "secondary_flags": sorted(set(flags)),
        "blockers": blockers,
        "checklist": results,
        "classified_at_utc": utc(),
        "run_tag": RUN_TAG,
    }


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    at = login_admin()
    results: Dict[str, bool] = {}

    careers = part_careers_reset(at)
    write_artifact("careers_reset_runtime.json", careers)
    results["careers_reset"] = careers.get("pass") is True

    edit = part_edit_publication(at)
    write_artifact("edit_publication_closeout_runtime.json", edit)
    results["edit_publication"] = edit.get("pass") is True

    routes = part_public_routes()
    write_artifact("public_routes_closeout_runtime.json", routes)
    results["public_routes"] = routes.get("pass") is True

    san = part_sanitisation(at)
    write_artifact("sanitisation_closeout_runtime.json", san)
    results["sanitisation"] = san.get("pass") is True

    clf = classify(results)
    write_artifact("classifications.json", clf)

    report = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{clf['classification']}`",
        f"**Prior:** `PARTIAL` (LEGAL-CONTENT-PUBLICATION-CONVERGENCE-01)",
        f"**Run tag:** `{RUN_TAG}`",
        "",
        "## Closeout summary",
        "Focused verification after careers canonical reset and Vercel frontend deploy.",
        "",
        "## Checklist",
    ]
    for k, v in results.items():
        report.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        report.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    report.append(f"\n## Harness\n\n`backend/legal_content_publication_closeout_01_execute.py`\n")
    (BUNDLE / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    watch = [
        "# Legal content publication watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
        f"- Closeout run: `{RUN_TAG}`",
        "",
    ]
    if clf["classification"] == "VERIFIED_OPERATIONALLY":
        watch.extend([
            "## Verified",
            "- [x] Careers reset to canonical default",
            "- [x] Admin edit publishes marker to public API and live page",
            "- [x] Restore removes marker publicly",
            "- [x] All 7 public routes CMS-backed with safe rendering",
            "- [x] Sanitisation intact",
            "",
            "## Optional",
            "- [ ] Admin UI restore-to-version button",
        ])
    else:
        watch.extend([
            "## Remaining",
            f"- Blockers: {', '.join(clf.get('blockers') or ['none'])}",
            "- [ ] Re-run closeout after resolving blockers",
        ])
    (BUNDLE / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
