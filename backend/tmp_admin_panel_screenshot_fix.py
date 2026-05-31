import httpx
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/phase2b_requirement_satisfaction_closeout_01/screenshots"
API = "https://pleerity-enterprise.onrender.com/api"
FE = "https://pleerityenterprise.co.uk"
CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
apw = (ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt").read_text().strip()
at = httpx.post(
    f"{API}/auth/admin/login",
    json={"email": "aigbochievictory@gmail.com", "password": apw},
    timeout=120,
).json()["access_token"]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(f"{FE}/login/admin", timeout=120000)
    page.evaluate("(t) => localStorage.setItem('auth_token', t)", at)
    page.evaluate("() => localStorage.setItem('user', JSON.stringify({role: 'ADMIN'}))")
    page.goto(f"{FE}/admin/clients/{CID}/control-panel", wait_until="networkidle", timeout=120000)
    page.wait_for_timeout(4000)
    page.screenshot(path=str(OUT / "admin_client_panel.png"), full_page=True)
    body = page.inner_text("body").lower()
    print("url", page.url)
    print("checks", {
        "missing_required": "missing required" in body,
        "unresolved": "unresolved" in body,
        "satisfied_by_declaration": "satisfied by declaration" in body,
    })
    browser.close()
