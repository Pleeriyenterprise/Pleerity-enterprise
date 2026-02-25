# CVP Full Service Page + Demo Removal + Risk Check Layout + Lead Email — Task Audit

**Task:** Compliance Vault Pro (CVP) full service page (CTAs, wording), remove/replace placeholder demo, risk-check funnel layout, fix "Activate Monitoring" link in lead email, non-regression. **Do not implement blindly;** this audit identifies what is implemented vs missing, conflicts, and safest options.

**Scope:** Marketing funnel and CVP page only. No changes to provisioning, Stripe webhooks, or new provisioning triggers.

---

## 1. CVP FULL SERVICE PAGE

### 1) “Check Your Compliance Risk” CTA after main pain section

| Requirement | Location | Status |
|-------------|----------|--------|
| Mini block after pain section | Insert after “What it does” (outcomes) | **Done** |
| Heading: “Unsure where you stand?” | `frontend/src/pages/public/CVPLandingPage.js` line 220 | **Done** |
| Body: “Run a quick risk check and get a structured report. Lead-only until you activate monitoring.” | Lines 222–224 | **Done** |
| Button: “Check Your Compliance Risk” → /risk-check | Lines 225–233, `<Link to="/risk-check">` | **Done** |

**File+line reference:** `frontend/src/pages/public/CVPLandingPage.js` 216–235 (section B.5).

---

### 2) After pricing section: CTA “Activate Monitoring” + secondary “See pricing”

| Requirement | Location | Status |
|-------------|----------|--------|
| Button “Activate Monitoring” → /intake/start | Pricing cards use `plan.cta` = “Activate Monitoring”, `<Link to="/intake/start">` at lines 425–430. Additional post-pricing block at lines 439–444: primary “Activate Monitoring” → /intake/start | **Done** |
| Secondary “See pricing” → /pricing | Line 444: `<Link to="/pricing">See pricing</Link>` | **Done** |

**File+line references:**  
- Pricing card buttons: `CVPLandingPage.js` 424–430.  
- After-pricing CTA block: `CVPLandingPage.js` 439–445.

---

### 3) Remove/replace “Demo” wording on CVP with “Risk Check” / “Compliance Risk Report”

| Requirement | Location | Status |
|-------------|----------|--------|
| No “Demo” / “Platform Demo” / sandbox on CVP | Grep over `CVPLandingPage.js`: no matches for Demo, demo, sandbox | **Done** |
| Final CTA uses “View Platform Overview” → /risk-check | Line 489: `<Link to="/risk-check">View Platform Overview</Link>` | **Done** |

No demo wording remains on CVP; no sandbox wording.

---

## 2. REMOVE/REPLACE PLACEHOLDER DEMO PAGE (Option A)

### 1) Demo route and content

| Requirement | Location | Status |
|-------------|----------|--------|
| Demo route must not show placeholder; redirect or replace with Risk Check | `frontend/src/App.js` line 190: `<Route path="/demo" element={<Navigate to="/risk-check" replace />} />` | **Done** |
| Placeholder demo content removed | `DemoPage.js` deleted; no longer in repo or exports | **Done** |

**File+line reference:** `frontend/src/App.js` 190.

---

### 2) All references: /demo, “View Platform Demo”, “Platform Demo”, “Try Demo”

| Search string | Current state | Status |
|---------------|---------------|--------|
| "/demo" (as route) | Only in App.js as redirect target; no component renders /demo | **Done** |
| "View Platform Demo" | Replaced with “View Platform Overview” or “See How It Works”; links go to /risk-check or /compliance-vault-pro#how-it-works | **Done** |
| "Platform Demo" | Not present in CVP/Home/FAQ (DemoPage removed) | **Done** |
| "Try Demo" | Not found in codebase | N/A |

**References updated:** HomePage.js (hero + final CTA → /risk-check), CVPLandingPage.js (hero + final CTA → /risk-check or #how-it-works), FAQPage.js (link → /risk-check). No dead links to the old demo page.

---

## 3. RISK CHECK PAGE LAYOUT (standalone funnel)

### 1) Funnel layout: minimal nav, logo, “Back to Home”, step indicator

| Requirement | Location | Status |
|-------------|----------|--------|
| No full marketing navbar | RiskCheckPage uses `FunnelLayout` (no PublicLayout navbar) | **Done** |
| No footer clutter | FunnelLayout has no footer | **Done** |
| Top-left: Pleerity logo (links home) | `frontend/src/components/public/FunnelLayout.js` lines 13–15: `<Link to="/">` with logo | **Done** |
| Top-right: “Back to Home” | Lines 16–22: `<Link to="/">Back to Home</Link>` | **Done** |
| Centered container with step indicator (e.g. Step 1 of 3) | `frontend/src/pages/public/RiskCheckPage.js` line 157: “Step {step} of 4” | **Done** (4 steps, not 3) |

**File+line references:**  
- Layout: `frontend/src/components/public/FunnelLayout.js` (full file).  
- Step indicator: `frontend/src/pages/public/RiskCheckPage.js` 157.  
- Usage: RiskCheckPage imports FunnelLayout and wraps content (line 3, usage in render).

**Note:** Task says “Step 1 of 3”; implementation uses 4 steps (Questions, Partial reveal, Email gate, Full report). No conflict; “e.g.” allows 4 steps. No change needed.

---

### 2) Funnel remains lead-based

| Requirement | Location | Status |
|-------------|----------|--------|
| Do not create portal users from risk-check | Backend: risk_check routes create/update `risk_leads` only; no portal_users | **Done** |
| Do not trigger provisioning | No provisioning calls from risk_check routes | **Done** |
| Do not grant entitlements | No entitlement assignment from risk-check | **Done** |
| Only capture lead + risk report data | POST /api/risk-check/preview (no persist), POST /api/risk-check/report (creates lead, returns report) | **Done** |

Confirmed from `backend/routes/risk_check.py`, `docs/MARKETING_FUNNEL_CONVERSION_LINKING.md`, and `docs/RISK_CHECK_UI_GAP_ANALYSIS.md`.

---

## 4. FIX BROKEN “ACTIVATE MONITORING” LINK IN LEAD EMAIL (E)

### Problem and requirement

- **Requirement:** Lead email CTA must point to /intake/start on the current marketing domain; not to demo or broken placeholder.  
- **Implementation:** Single env var for public marketing base URL; build CTA as `{base}/intake/start`; safe fallback; unit test for /intake/start in CTA.

### Current implementation

| Requirement | Location | Status |
|-------------|----------|--------|
| Risk-lead email template / builder | `backend/services/risk_lead_email_service.py`: `_activate_url(lead)` builds CTA base URL; all step bodies use `<a href="{url}">Activate Monitoring</a>` with that URL | **Done** |
| Prefer single env var PUBLIC_MARKETING_BASE_URL | Lines 24–25: `base = (os.environ.get("PUBLIC_MARKETING_BASE_URL") or "").strip().rstrip("/")` | **Done** |
| Build CTA URL as `{PUBLIC_MARKETING_BASE_URL}/intake/start` | Line 31: `return f"{base}/intake/start"` | **Done** |
| Safe fallback if env missing | Lines 26–30: try `get_public_app_url(for_email_links=False)`, else FRONTEND_URL / FRONTEND_PUBLIC_URL, else `http://localhost:3000` | **Done** |
| Unit test: email CTA contains “/intake/start” | `backend/tests/test_risk_lead_email_service.py`: `test_activate_url_contains_intake_start`, `test_activate_url_fallback_contains_intake_start`, `test_step1_email_body_contains_intake_start_link` | **Done** |

**File+line references:**  
- URL builder: `backend/services/risk_lead_email_service.py` 22–31 (`_activate_url`).  
- Step 1 body (example): 34–51 (uses `_activate_url(lead)` and `{url}` in link).  
- Tests: `backend/tests/test_risk_lead_email_service.py` 9–41.

**Deployment note:** For production, set `PUBLIC_MARKETING_BASE_URL` to the current marketing domain (e.g. Vercel URL). If unset, fallback uses `get_public_app_url()` or FRONTEND_URL; ensure that resolves to the marketing site, not the backend. No code change required if env is set correctly.

---

## 5. NON-REGRESSION / SAFETY (F)

| Requirement | Status |
|-------------|--------|
| Do NOT change existing provisioning logic | No provisioning code changed by this task | **OK** |
| Do NOT alter Stripe webhook flows | Not touched | **OK** |
| Do NOT add new provisioning triggers | None added | **OK** |
| Keep compliance-safe language (no legal verdicts, no guaranteed compliance claims) | CVP and risk-check copy use “informational indicator”, “not legal advice”, “tracking and organisation” | **OK** |

---

## 6. DELIVERABLES CHECKLIST

### 1) File+line references for each change

All references are in the sections above. Summary:

- **CVP “Check Your Risk” block:** `frontend/src/pages/public/CVPLandingPage.js` 216–235.  
- **CVP pricing + after-pricing CTAs:** `CVPLandingPage.js` 384–445 (pricing section, card buttons, “Activate Monitoring” + “See pricing”).  
- **Demo redirect:** `frontend/src/App.js` 190.  
- **Demo page removed:** `DemoPage.js` deleted; export removed from `frontend/src/pages/public/index.js`.  
- **Risk-check layout:** `frontend/src/components/public/FunnelLayout.js`; step indicator `frontend/src/pages/public/RiskCheckPage.js` 157.  
- **Lead email CTA URL:** `backend/services/risk_lead_email_service.py` 22–31, 34–51 (and other step bodies).  
- **Lead email tests:** `backend/tests/test_risk_lead_email_service.py` 9–41.

### 2) Confirm: homepage hero CTA, CVP CTAs, all demo links → /risk-check

| Check | Status |
|-------|--------|
| Homepage hero primary CTA “Check Your Compliance Risk” → /risk-check | **Done** (HomePage.js ~140–146) |
| Homepage hero secondary “View Platform Overview” → /compliance-vault-pro | **Done** |
| CVP hero primary “Check Your Compliance Risk” → /risk-check | **Done** (CVPLandingPage.js 159–163) |
| CVP “Unsure where you stand?” block → “Check Your Compliance Risk” → /risk-check | **Done** (216–233) |
| CVP pricing “Activate Monitoring” → /intake/start; “See pricing” → /pricing | **Done** (424–430, 439–444) |
| All former demo links now go to /risk-check (or intended target) | **Done** (HomePage, CVP, FAQ updated; /demo redirects) |

### 3) Confirm: /demo redirects to /risk-check (or removed)

**Done.** Route `/demo` renders `<Navigate to="/risk-check" replace />`. Demo page component removed. No placeholder demo reachable.

### 4) Confirm: lead email “Activate Monitoring” link points to /intake/start and works

**Done.**  
- `_activate_url()` returns `{base}/intake/start` with base from `PUBLIC_MARKETING_BASE_URL` or fallback.  
- All nurture step bodies use this URL in the “Activate Monitoring” (or “Activate Continuous Monitoring”) link.  
- Unit tests assert `/intake/start` in URL and in step 1 body.  
- **Operational:** Set `PUBLIC_MARKETING_BASE_URL` to the marketing domain (e.g. Vercel URL) so links resolve correctly in production.

### 5) Screenshots (or notes) for desktop + mobile layout of hero + preview card

**Not produced in this audit.** Task asks for “screenshots (or notes)” for hero + preview card. Implementation is in place; layout notes:

- **Homepage hero:** Two-column grid (copy left, Portfolio Compliance Snapshot mockup right); primary “Check Your Compliance Risk”, secondary “View Platform Overview”; trust bullets below.  
- **Preview card (PortfolioComplianceSnapshotMockup):** “Portfolio Compliance Snapshot (Example)”, 62% bar, “Properties monitored: 4”, “2 properties require attention”, category bars (Gas, EICR, Licensing, Document Coverage), footer microtext, “Generate My Risk Report” button.  
- **Responsive:** Uses Tailwind (e.g. `lg:grid-cols-2`, `flex-col sm:flex-row`). Manual or automated screenshot run (e.g. desktop + mobile viewport) can be added as a follow-up.

---

## 7. CONFLICTS AND RECOMMENDATIONS

**No conflicting instructions identified.** Task requirements align with current implementation:

- CVP has the “Unsure where you stand?” block after the outcomes section, “Activate Monitoring” and “See pricing” after pricing, and no Demo wording.  
- Demo is removed; /demo redirects to /risk-check; former demo links point to /risk-check or the correct CTA.  
- Risk-check uses FunnelLayout (minimal nav, logo, “Back to Home”, step indicator) and remains lead-only.  
- Lead email CTA is built from `PUBLIC_MARKETING_BASE_URL` (or fallback) + `/intake/start` and is covered by tests.

**Safest option:** No code changes required for the items above. Ensure `PUBLIC_MARKETING_BASE_URL` is set in production to the marketing site URL so lead email links work in the wild.

---

## 8. SUMMARY TABLE

| Task section | Status | Notes |
|--------------|--------|--------|
| CVP 1) “Check Your Risk” after pain | **Done** | CVPLandingPage.js 216–235 |
| CVP 2) After pricing: Activate Monitoring + See pricing | **Done** | Cards + block 439–445 |
| CVP 3) No Demo wording on CVP | **Done** | Grep clean |
| C) Demo route → /risk-check; references updated | **Done** | App.js redirect; DemoPage removed |
| D) Risk-check funnel layout | **Done** | FunnelLayout + Step N of 4 |
| D) Risk-check lead-based only | **Done** | No provisioning from risk-check |
| E) Lead email CTA → /intake/start | **Done** | _activate_url + tests; set env in prod |
| F) Non-regression | **OK** | No provisioning/Stripe changes |

This audit is the single reference for compliance with the CVP full service page, demo removal, risk-check layout, and lead email CTA task. No implementation was performed; only verification and documentation.
