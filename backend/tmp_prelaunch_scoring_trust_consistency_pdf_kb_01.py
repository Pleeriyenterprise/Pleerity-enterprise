#!/usr/bin/env python3
"""PRELAUNCH-SCORING-TRUST-CONSISTENCY-PDF-KB-01 — secondary-surface copy verification."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_scoring_trust_consistency_pdf_kb_01"
PROGRAMME = "PRELAUNCH-SCORING-TRUST-CONSISTENCY-PDF-KB-01"
FE = "https://pleerityenterprise.co.uk"
EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"

FORBIDDEN = [
    r"scoring engine",
    r"weighted contributions",
    r"bucket emphasis",
    r"credit in bucket",
    r"credit earned within each bucket",
    r"CVP Score v",
    r"model weighting",
    r"scoring formula",
    r"point allocation",
    r"35\s*%\s*requirement status",
    r"100\s*/\s*70\s*/\s*30",
    r"moved by\s*[+-]?\d+\s*point",
    r"Score\s*[+-]\d+",
    r"Delta\s*[+-]?\d+",
]

STATIC_TARGETS = [
    ROOT / "services/pdf_report_builder.py",
    ROOT / "services/scoring_explanation_copy.py",
    ROOT / "services/property_timeline_service.py",
    ROOT / "services/email_service.py",
    ROOT / "services/monthly_digest_pdf_service.py",
    ROOT / "docs/assistant_kb/how_scoring_works.md",
    ROOT / "docs/assistant_kb/score_changes.md",
    ROOT / "scripts/seed_kb_articles.py",
    ROOT.parent / "frontend/src/utils/confidenceUxCopy.js",
    ROOT.parent / "frontend/src/utils/scoringExplanationCopy.js",
]

REQUIRED_SNIPPETS = {
    "how_scoring_works.md": [r"accepted", r"not a legal opinion", r"Do \*\*not\*\* quote internal weights"],
    "score_changes.md": [r"overdue", r"accepted", r"Do not quote point changes"],
    "scoring_explanation_copy.py": [r"KB_COMPLIANCE_SCORE_EXPLAINED", r"score_change_narrative"],
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def static_scan() -> dict:
    hits: list = []
    missing: list = []
    for path in STATIC_TARGETS:
        if not path.exists():
            hits.append({"file": str(path.relative_to(ROOT.parent)), "issue": "missing"})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(ROOT.parent))
        # Skip internal denylist / guard-rail constants — not customer-visible copy.
        if path.name == "scoringExplanationCopy.js":
            text = text.split("SCORING_EXPLANATION_FORBIDDEN_TERMS", 1)[0]
        for line in text.splitlines():
            if re.search(r"do\s+\*\*not\*\*|do not quote|must not appear", line, re.I):
                continue
            for pat in FORBIDDEN:
                if re.search(pat, line, re.I):
                    hits.append({"file": rel, "pattern": pat, "line": line.strip()[:120]})
        for snippet_pat in REQUIRED_SNIPPETS.get(path.name, []):
            if not re.search(snippet_pat, text, re.I):
                missing.append({"file": rel, "pattern": snippet_pat})
    return {"scanned": len(STATIC_TARGETS), "forbidden_hits": hits, "required_missing": missing}


def pdf_local_check() -> dict:
    try:
        import reportlab.rl_config as rl_config

        rl_config.pageCompression = 0
        from services.pdf_report_builder import build_score_explanation_report
    except Exception as exc:
        return {"skipped": True, "error": str(exc)}

    payload = {
        "score": 72,
        "score_status": "ok",
        "grade": "B",
        "score_authority": "persisted",
        "last_calculated_at": "2026-03-15T10:30:00+00:00",
        "stats": {"compliant": 2, "expiring_soon": 1, "overdue": 0},
        "properties_count": 1,
        "data_completeness_percent": 100,
        "score_model_version": "2",
        "drivers": [],
        "property_breakdown": [],
        "bucket_breakdown": {
            "legal_core": {"percent": 80},
            "documentation_completeness": {"percent": 70},
            "operational_responsiveness": {"percent": 90},
            "recency_maintenance_confidence": {"percent": 85},
        },
    }
    pdf = build_score_explanation_report("c1", payload, {"company_name": "Co", "customer_reference": "CRN"}, {})
    low = pdf.lower()
    byte_hits = []
    for needle in (b"cvp score", b"credit in bucket", b"credit earned", b"bucket emphasis", b"point(s)"):
        if needle in low:
            byte_hits.append(needle.decode())
    ok_markers = any(x in pdf for x in (b"Core legal requirements", b"How you", b"Accepted evidence"))
    return {
        "pdf_bytes": len(pdf),
        "forbidden_hits": byte_hits,
        "has_trust_markers": ok_markers,
        "pass": not byte_hits and ok_markers,
    }


def copy_module_check() -> dict:
    from services.scoring_explanation_copy import email_score_delta_line, score_change_narrative

    issues = []
    for fn, val in (("score_change_narrative(+5)", score_change_narrative(5)), ("score_change_narrative(-3)", score_change_narrative(-3)), ("email_score_delta_line(4)", email_score_delta_line(4))):
        if re.search(r"point|\+\d+|\-\d+", val, re.I):
            issues.append({"fn": fn, "text": val})
    return {"issues": issues, "pass": not issues}


def browser_checks() -> dict:
    if sync_playwright is None or not PW_FILE.exists():
        return {"skipped": True, "reason": "playwright or credentials missing"}
    try:
        pw = PW_FILE.read_text(encoding="utf-8").strip()
        out: dict = {"captured_at": _utc(), "pages": {}, "forbidden_hits": [], "required_missing": []}
        with sync_playwright() as p:
            page = p.chromium.launch(headless=True).new_context(viewport={"width": 1440, "height": 900}).new_page()
            page.goto(f"{FE}/login/client", timeout=120000)
            page.locator("#email").fill(EMAIL)
            page.locator("#password").fill(pw)
            page.locator('button[type="submit"]').click()
            try:
                page.wait_for_url(re.compile(r"/dashboard|/command-centre|/today|/compliance-score"), timeout=45000)
            except Exception:
                pass
            page.wait_for_timeout(3000)

            for path, key in [("/dashboard", "dashboard"), ("/compliance-score", "compliance_score"), ("/requirements", "requirements")]:
                page.goto(f"{FE}{path}", wait_until="networkidle", timeout=120000)
                page.wait_for_timeout(4000)
                text = page.locator("body").inner_text()
                out["pages"][key] = {"path": path, "chars": len(text)}
                for pat in FORBIDDEN:
                    if re.search(pat, text, re.I):
                        out["forbidden_hits"].append({"page": key, "pattern": pat})
                if key == "requirements" and re.search(r"scoring engine", text, re.I):
                    out["forbidden_hits"].append({"page": key, "pattern": "scoring engine (requirements confidence line)"})
        return out
    except Exception as exc:
        return {"skipped": True, "reason": str(exc)}


def classify(static: dict, pdf: dict, copy: dict, browser: dict) -> str:
    if static.get("forbidden_hits") or pdf.get("forbidden_hits") or copy.get("issues"):
        return "ENGINEERING_LANGUAGE_LEAK"
    if static.get("required_missing"):
        return "TRUST_DRIFT_RISK"
    if not pdf.get("pass"):
        return "FALSE_PRECISION_RISK"
    # Staging may lag deploy — treat browser-only hits as drift, not code leak.
    if browser.get("forbidden_hits"):
        return "TRUST_DRIFT_RISK"
    if browser.get("skipped"):
        return "TRUST_DRIFT_RISK"
    return "TRUST_SAFE"


def main() -> int:
    static = static_scan()
    pdf = pdf_local_check()
    copy = copy_module_check()
    browser = browser_checks()
    classification = classify(static, pdf, copy, browser)
    blockers = []
    if static.get("forbidden_hits"):
        blockers.append("static_forbidden")
    if static.get("required_missing"):
        blockers.append("static_required_missing")
    if pdf.get("forbidden_hits") or not pdf.get("pass", True):
        blockers.append("pdf_export")
    if copy.get("issues"):
        blockers.append("directional_copy")
    if browser.get("forbidden_hits"):
        blockers.append("browser_forbidden")

    result = {
        "programme": PROGRAMME,
        "classification": classification,
        "blockers": blockers,
        "static_scan": static,
        "pdf_local": pdf,
        "copy_module": copy,
        "browser": browser,
        "captured_at": _utc(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    _write("static_scan.json", static)
    _write("pdf_local.json", pdf)
    _write("copy_module.json", copy)
    _write("browser_runtime.json", browser)
    _write("classifications.json", result)
    _write(
        "watchlist.md",
        "# Watchlist\n\n"
        + ("- None — secondary surfaces verified.\n" if classification == "TRUST_SAFE" else "- Review blockers in classifications.json\n"),
    )
    print(json.dumps(result, indent=2))
    return 0 if classification == "TRUST_SAFE" else 1


if __name__ == "__main__":
    sys.exit(main())
