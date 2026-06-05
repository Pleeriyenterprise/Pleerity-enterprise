#!/usr/bin/env python3
"""
LEGAL-CONTENT-ADMIN-HYDRATION-CLOSEOUT-01
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/legal_content_management_publication_runtime_audit_01"
PROGRAMME = "LEGAL-CONTENT-ADMIN-HYDRATION-CLOSEOUT-01"

SLUG = "6fd5ac4c_d35a58ae"
_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "2.0"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"LEGAL-ADMIN-HYDRATE-{RUN_TAG}"

SLUGS = ["privacy", "terms", "cookies", "accessibility", "careers", "partnerships", "about"]
TAB_LABELS = {
    "privacy": "Privacy Policy",
    "terms": "Terms",
    "cookies": "Cookies",
    "accessibility": "Accessibility",
    "careers": "Careers",
    "partnerships": "Partnerships",
    "about": "About Us",
}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_artifact(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def read_pw(rel: str) -> str:
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


def login_admin() -> Tuple[str, dict]:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    pw = read_pw(f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt")
    for attempt in range(8):
        r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
        if r.status_code != 429:
            r.raise_for_status()
            body = r.json()
            return body.get("access_token") or body["token"], body.get("user") or {}
        time.sleep(25 * (attempt + 1))
    raise RuntimeError("admin login failed")


def part_root_cause(at: str) -> dict:
    probes: List[dict] = []
    admin_list = req("get", "/admin/legal-content", at, timeout=90)
    admin_rows = admin_list.json() if admin_list.status_code == 200 else []
    admin_by = {r.get("slug"): r for r in admin_rows if isinstance(r, dict)}
    for slug in SLUGS:
        admin_row = admin_by.get(slug, {})
        admin_one = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
        aone = admin_one.json() if admin_one.status_code == 200 else {}
        pub = req("get", f"/public/legal-content/{slug}", "", timeout=60)
        pbody = pub.json() if pub.status_code == 200 else {}
        admin_len = len((aone.get("content") or "").strip())
        pub_len = len((pbody.get("content") or "").strip())
        admin_preview = (aone.get("content") or "")[:80]
        pub_preview = (pbody.get("content") or "")[:80]
        probes.append({
            "slug": slug,
            "admin_list_status": admin_list.status_code,
            "admin_get_status": admin_one.status_code,
            "admin_version": aone.get("version"),
            "admin_content_length": admin_len,
            "admin_updated_at": aone.get("updated_at"),
            "public_source": pbody.get("source"),
            "public_fallback_used": pbody.get("fallback_used"),
            "public_version": pbody.get("version"),
            "public_content_length": pub_len,
            "previews_match": admin_preview == pub_preview if admin_len > 0 and pub_len > 0 else None,
            "pass": admin_one.status_code == 200 and admin_len > 100 and pub_len > 100 and admin_preview == pub_preview,
        })
    return {
        "at_utc": utc(),
        "root_cause": "AdminLegalContentPage used raw fetch without apiClient; silent failure on 401 kept Version 0 empty local state",
        "fix": "Use apiClient auth interceptor, per-tab reload, serialized admin rows, seed/refresh controls",
        "probes": probes,
        "pass": admin_list.status_code == 200 and all(p["pass"] for p in probes),
    }


def part_admin_api(at: str) -> dict:
    rows = req("get", "/admin/legal-content", at, timeout=90)
    data = rows.json() if rows.status_code == 200 else []
    probes = []
    for slug in SLUGS:
        row = next((r for r in data if r.get("slug") == slug), {})
        content_length = row.get("content_length")
        if content_length is None:
            content_length = len((row.get("content") or "").strip())
        probes.append({
            "slug": slug,
            "title": row.get("title"),
            "version": row.get("version"),
            "content_length": content_length,
            "updated_at": row.get("updated_at"),
            "is_empty": row.get("is_empty"),
            "pass": (row.get("version") or 0) > 0 and content_length > 100,
        })
    return {"at_utc": utc(), "status": rows.status_code, "probes": probes, "pass": rows.status_code == 200 and all(p["pass"] for p in probes)}


def part_frontend_hydration() -> dict:
    path = ROOT.parent / "frontend/src/pages/AdminLegalContentPage.jsx"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    checks = {
        "uses_api_client": "apiClient" in text,
        "per_tab_reload": "loadSlug(activeTab" in text,
        "refresh_button": "Refresh" in text,
        "seed_button": "seed-canonical" in text,
        "load_error_state": "loadError" in text,
        "publish_copy": "Changes publish to the public site after save" in text,
        "save_publish_label": "Save & Publish" in text,
        "normalize_row": "normalizeRow" in text,
        "empty_warning": "no CMS content loaded" in text.lower() or "no cms content loaded" in text.lower(),
    }
    return {"at_utc": utc(), "checks": checks, "pass": all(checks.values())}


def admin_browser(at: str, admin_user: dict) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"pass": False, "error": "playwright not installed", "tabs": []}
    shot_dir = BUNDLE / "screenshots" / "admin_hydration"
    shot_dir.mkdir(parents=True, exist_ok=True)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    tabs_out: List[dict] = []
    try:
        page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [at, admin_user],
        )
        page.goto(f"{FRONTEND}/admin/settings/legal", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(4000)
        for slug in SLUGS:
            page.get_by_role("tab", name=TAB_LABELS[slug]).click()
            page.wait_for_timeout(2500)
            body = page.locator("body").inner_text()
            textarea = page.locator("textarea").first
            editor_content = textarea.input_value() if textarea.count() else ""
            char_count = len(editor_content.strip())
            version_match = re.search(r"Version\s+(\d+)", body)
            version = int(version_match.group(1)) if version_match else 0
            never = "Last updated: Never" in body
            title_input = page.locator('input[placeholder="Page title"]').first
            title_value = title_input.input_value() if title_input.count() else ""
            if slug in ("privacy", "terms", "careers", "about"):
                page.screenshot(path=str(shot_dir / f"admin_{slug}.png"))
            admin_api = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
            pub_api = req("get", f"/public/legal-content/{slug}", "", timeout=60)
            arow = admin_api.json() if admin_api.status_code == 200 else {}
            prow = pub_api.json() if pub_api.status_code == 200 else {}
            admin_preview = (arow.get("content") or "")[:80]
            public_preview = (prow.get("content") or "")[:80]
            editor_preview = editor_content[:80]
            preview_match = bool(admin_preview) and admin_preview == editor_preview == public_preview
            tabs_out.append({
                "slug": slug,
                "title_populated": bool(title_value.strip()),
                "char_count": char_count,
                "version": version,
                "never_updated": never,
                "admin_preview": admin_preview,
                "editor_preview": editor_preview,
                "public_preview": public_preview,
                "preview_match": preview_match,
                "screenshot": f"screenshots/admin_hydration/admin_{slug}.png" if slug in ("privacy", "terms", "careers", "about") else None,
                "pass": bool(title_value.strip()) and char_count > 100 and version > 0 and not never and preview_match,
            })
        return {"at_utc": utc(), "tabs": tabs_out, "pass": all(t["pass"] for t in tabs_out)}
    except Exception as exc:
        return {"pass": False, "error": str(exc)[:300], "tabs": tabs_out}
    finally:
        browser.close()
        p.stop()


def part_edit_safety(at: str) -> dict:
    slug = "careers"
    before = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    bbody = before.json() if before.status_code == 200 else {}
    prev = bbody.get("content") or ""
    prev_title = bbody.get("title") or "Careers"
    prev_v = bbody.get("version") or 0
    marker_content = f"{prev}\n\n{MARKER}\n"
    put = req("put", f"/admin/legal-content/{slug}", at, json={"slug": slug, "title": prev_title, "content": marker_content}, timeout=90)
    admin_after = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    abody = admin_after.json() if admin_after.status_code == 200 else {}
    pub = req("get", f"/public/legal-content/{slug}", "", timeout=60)
    pbody = pub.json() if pub.status_code == 200 else {}
    restore = req("put", f"/admin/legal-content/{slug}", at, json={"slug": slug, "title": prev_title, "content": prev}, timeout=90)
    admin_final = req("get", f"/admin/legal-content/{slug}", at, timeout=60)
    fbody = admin_final.json() if admin_final.status_code == 200 else {}
    pub_final = req("get", f"/public/legal-content/{slug}", "", timeout=60)
    pfbody = pub_final.json() if pub_final.status_code == 200 else {}
    return {
        "at_utc": utc(),
        "admin_before_length": len(prev),
        "put_status": put.status_code,
        "admin_marker_after_save": MARKER in (abody.get("content") or ""),
        "public_marker_after_save": MARKER in (pbody.get("content") or ""),
        "version_incremented": (abody.get("version") or 0) > prev_v,
        "restore_status": restore.status_code,
        "admin_marker_removed": MARKER not in (fbody.get("content") or ""),
        "public_marker_removed": MARKER not in (pfbody.get("content") or ""),
        "pass": (
            put.status_code == 200
            and MARKER in (abody.get("content") or "")
            and MARKER in (pbody.get("content") or "")
            and restore.status_code == 200
            and MARKER not in (fbody.get("content") or "")
            and MARKER not in (pfbody.get("content") or "")
        ),
    }


def part_regression() -> dict:
    suites = [
        "tests/test_admin_legal_content_hydration.py",
        "tests/test_legal_content_publication.py",
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
    if not results.get("root_cause"):
        flags.append("ADMIN_HYDRATION_DRIFT")
    if not results.get("browser"):
        flags.append("ADMIN_HYDRATION_DRIFT")
    if not results.get("edit_safety"):
        flags.append("PUBLICATION_DRIFT")
    clf = "VERIFIED_OPERATIONALLY" if not blockers else ("PARTIAL" if len(blockers) <= 2 else "FAIL_OPERATIONAL")
    return {
        "programme": PROGRAMME,
        "classification": clf,
        "prior_classification": "VERIFIED_OPERATIONALLY",
        "prior_programme": "LEGAL-CONTENT-PUBLICATION-CLOSEOUT-01",
        "secondary_flags": sorted(set(flags)),
        "blockers": blockers,
        "checklist": results,
        "classified_at_utc": utc(),
        "run_tag": RUN_TAG,
    }


def main() -> int:
    print(PROGRAMME, "starting", RUN_TAG)
    at, admin_user = login_admin()
    results: Dict[str, bool] = {}

    root = part_root_cause(at)
    write_artifact("admin_hydration_root_cause_runtime.json", root)
    results["root_cause"] = root.get("pass") is True

    api = part_admin_api(at)
    write_artifact("admin_api_convergence_runtime.json", api)
    results["admin_api"] = api.get("pass") is True

    fe = part_frontend_hydration()
    write_artifact("admin_frontend_hydration_runtime.json", fe)
    results["frontend"] = fe.get("pass") is True

    browser = admin_browser(at, admin_user)
    write_artifact("admin_browser_hydration_runtime.json", browser)
    results["browser"] = browser.get("pass") is True

    edit = part_edit_safety(at)
    write_artifact("admin_edit_safety_runtime.json", edit)
    results["edit_safety"] = edit.get("pass") is True

    reg = part_regression()
    write_artifact("admin_hydration_regression_runtime.json", reg)
    results["regression"] = reg.get("pass") is True

    clf = classify(results)
    write_artifact("classifications.json", clf)

    report = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{clf['classification']}`",
        f"**Run tag:** `{RUN_TAG}`",
        "",
        "## Summary",
        "Admin Legal Content Management now hydrates from governed CMS via apiClient with serialized admin API rows.",
        "",
        "## Checklist",
    ]
    for k, v in results.items():
        report.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    if clf.get("blockers"):
        report.append("\n**Blockers:** " + ", ".join(clf["blockers"]))
    report.append(f"\n## Harness\n\n`backend/legal_content_admin_hydration_closeout_01_execute.py`\n")
    (BUNDLE / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    watch = [
        "# Legal content publication watchlist",
        "",
        f"- Classification: `{clf['classification']}`",
        f"- Admin hydration closeout: `{RUN_TAG}`",
        "",
    ]
    if clf["classification"] == "VERIFIED_OPERATIONALLY":
        watch.extend([
            "## Verified",
            "- [x] Admin editor hydrates CMS content for all 7 slugs",
            "- [x] Admin API and public API content agree",
            "- [x] Browser editor shows version/last updated/character counts",
            "- [x] Edit safety marker round-trip via admin API",
            "",
            "## Optional",
            "- [ ] Admin UI restore-to-version button",
        ])
    else:
        watch.append(f"- Blockers: {', '.join(clf.get('blockers') or [])}")
    (BUNDLE / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print("CLASSIFICATION", clf["classification"], "blockers", clf.get("blockers"))
    return 0 if clf["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
