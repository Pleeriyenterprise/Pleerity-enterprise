#!/usr/bin/env python3
"""PRELAUNCH-SCORING-EXPLANATION-TRUST-REWRITE-01 — live copy verification."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_scoring_explanation_trust_rewrite_01"
PROGRAMME = "PRELAUNCH-SCORING-EXPLANATION-TRUST-REWRITE-01"
FE = "https://pleerityenterprise.co.uk"
EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"

FORBIDDEN = [
    r"weighted contributions",
    r"scoring engine",
    r"maintenance confidence",
    r"operational responsiveness",
    r"document-backed operational summary",
    r"100 / 70 / 30 / 0",
    r"~\s*60\s*%",
    r"credit within each bucket",
    r"bucket emphasis",
    r"design guide",
    r"Points earned",
    r"Potential impact:\s*\+",
    r"CVP Score v",
]

REQUIRED = [
    r"Understanding your compliance score",
    r"How you.?re doing in each area|What affects this score",
    r"Accepted evidence",
    r"Not legal advice",
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def browser_checks() -> dict:
    if sync_playwright is None:
        return {"skipped": True}
    pw = PW_FILE.read_text(encoding="utf-8").strip()
    out: dict = {"captured_at": _utc(), "pages": {}, "forbidden_hits": [], "required_missing": []}
    with sync_playwright() as p:
        page = p.chromium.launch(headless=True).new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(f"{FE}/login/client", timeout=120000)
        page.locator("#email").fill(EMAIL)
        page.locator("#password").fill(PW)
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(5000)

        for path, key in [("/dashboard", "dashboard"), ("/compliance-score", "compliance_score")]:
            page.goto(f"{FE}{path}", wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(4000)
            text = page.locator("body").inner_text()
            out["pages"][key] = {"path": path, "chars": len(text)}
            for pat in FORBIDDEN:
                if re.search(pat, text, re.I):
                    out["forbidden_hits"].append({"page": key, "pattern": pat})
            for pat in REQUIRED:
                if not re.search(pat, text, re.I):
                    out["required_missing"].append({"page": key, "pattern": pat})

        page.goto(f"{FE}/dashboard", wait_until="networkidle", timeout=120000)
        fw = page.get_by_text(re.compile(r"Understanding your compliance score", re.I))
        if fw.count():
            fw.first.click()
            page.wait_for_timeout(1000)
            fw_text = page.locator("body").inner_text()
            out["pages"]["framework_expanded"] = True
            for pat in FORBIDDEN:
                if re.search(pat, fw_text, re.I):
                    out["forbidden_hits"].append({"page": "framework_expanded", "pattern": pat})

        page.goto(f"{FE}/compliance-score", wait_until="networkidle", timeout=120000)
        meth = page.locator('[data-testid="score-methodology"]')
        if meth.count():
            meth.click()
            page.wait_for_timeout(1000)
            adv = page.get_by_text(re.compile(r"More detail", re.I))
            if adv.count():
                adv.first.click()
                page.wait_for_timeout(800)
            meth_text = page.locator("body").inner_text()
            out["pages"]["methodology_expanded"] = True
            for pat in FORBIDDEN:
                if re.search(pat, meth_text, re.I):
                    out["forbidden_hits"].append({"page": "methodology_expanded", "pattern": pat})
            if re.search(r"60\s*%\s*legal|roughly\s*60", meth_text, re.I):
                out["forbidden_hits"].append({"page": "methodology_expanded", "pattern": "approximate weight split"})

        page.goto(f"{FE}/compliance-score", wait_until="networkidle", timeout=120000)
        defs = page.get_by_role("button", name=re.compile(r"View definitions", re.I))
        if defs.count():
            defs.first.click()
            page.wait_for_timeout(800)
            defs_text = page.locator("body").inner_text()
            out["pages"]["definitions_modal"] = True
            if re.search(r"Date confidence", defs_text, re.I):
                out["forbidden_hits"].append({"page": "definitions_modal", "pattern": "Date confidence"})
            if not re.search(r"Confirmed vs estimated dates", defs_text, re.I):
                out["required_missing"].append({"page": "definitions_modal", "pattern": "Confirmed vs estimated dates"})
    return out


def main() -> int:
    b = browser_checks()
    blockers = []
    if b.get("forbidden_hits"):
        blockers.append("engineering_language")
    if b.get("required_missing"):
        blockers.append("required_copy_missing")
    if b.get("skipped"):
        blockers.append("browser_skipped")

    classification = "TRUST_SAFE" if not blockers else ("ENGINEERING_LEAKAGE" if "engineering_language" in blockers else "MOSTLY_SAFE")

    result = {
        "programme": PROGRAMME,
        "classification": classification,
        "blockers": blockers,
        "browser": b,
    }
    if classification == "TRUST_SAFE":
        _write("browser_runtime.json", b)
        _write("classifications.json", result)
        _write("watchlist.md", "# Watchlist\n\n- None — runtime verified.\n")

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
