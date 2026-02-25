# Risk-First Conversion Ladder + Remove Placeholder Demo + Standalone Risk Check Funnel — Task Audit

**Task:** Implementation task "Risk-First Conversion Ladder + Remove Placeholder Demo + Standalone Risk Check Funnel" (HIGH priority). Marketing funnel only; do not change app provisioning flow. Keep current brand identity and compliance-safe wording.

**Purpose:** Map task requirements to current codebase, list what is implemented vs missing, note conflicts, and recommend the safest implementation approach without implementing.

---

## 1. Core strategy (task vs current)

| Requirement | Current state | Status |
|-------------|---------------|--------|
| Risk-first positioning on homepage hero | Homepage hero is product-led: "Compliance Vault Pro – Compliance Vault & Audit Intelligence". Primary CTA = "Start Your Setup" → /intake/start. | **Missing** |
| Primary CTA everywhere = "Check Your Compliance Risk" → /risk-check | Homepage: primary is "Start Your Setup"; "Check Your Compliance Risk" is a third button. Header (PublicHeader.js): already has "Check Your Compliance Risk" → /risk-check. CVP page: primary = "Start Your Setup" → /intake/start. | **Partial** (header only) |
| Secondary CTA = "View Platform Overview" / "See How It Works" → CVP or #how-it-works | Homepage: "View Platform Demo" → /demo. CVP: "View Platform Demo" → /demo. No "View Platform Overview" or anchor to #how-it-works on homepage. | **Missing** (wrong label + wrong target) |
| CVP: after pain section insert "Check Your Compliance Risk" | CVP has no explicit "pain" section; has "What it does" (outcomes). No "Check Your Compliance Risk" section/CTA between content and pricing. | **Missing** |
| CVP: after pricing CTA "Activate Monitoring" → /intake/start | CVP pricing cards use "Start Your Setup" → /intake/start. No "Activate Monitoring" label. | **Missing** (copy only) |
| Placeholder demo must NOT exist; replace with Risk Check (Option A) | `/demo` exists and renders DemoPage (4 image panels, "Demo assets coming soon", CTA to /intake/start). /risk-check exists and is full Risk Check funnel. | **Conflict:** demo exists; task says replace with Risk Check. |
| "View Platform Demo" buttons/links → /risk-check | Homepage hero + final CTA: "View Platform Demo" / "View Demo" → /demo. CVP hero + final CTA: "View Platform Demo" → /demo. FAQPage: link to /demo. | **Missing** (all point to /demo) |
| Risk Check lead-based only; no login/provisioning/entitlements at demo stage | Risk Check: POST /api/risk-check/preview, /report; creates lead in risk_leads; CTA to /intake/start. No client/portal user creation from risk-check. | **Done** |

**Conversion ladder (task):** Homepage → /risk-check → /intake/start → Stripe → Provisioning → Dashboard  
**Current:** Homepage primary sends users to /intake/start; /risk-check exists but is not the primary path. Ladder is partially in place (risk-check → intake → Stripe → provisioning → dashboard); homepage does not feed it as primary.

---

## 2. Homepage (A) — Hero + mockup

| Task requirement | Current | Gap / action |
|------------------|---------|--------------|
| **A.1 Hero copy risk-first** | | |
| Headline: "Are You Fully Compliant as a UK Landlord?" | "Compliance Vault Pro – Compliance Vault & Audit Intelligence" | Replace headline. |
| Subtext: "Structured compliance monitoring and renewal tracking for UK portfolios." | "A structured compliance tracking platform for UK landlords. Monitor certificate expiry dates..." | Replace subtext. |
| Primary CTA: "Check Your Compliance Risk" → /risk-check | First button: "Start Your Setup" → /intake/start | Make "Check Your Compliance Risk" the single primary CTA; link to /risk-check. |
| Secondary CTA: "View Platform Overview" (or "See How It Works") → #how-it-works or /compliance-vault-pro | Second button: "View Platform Demo" → /demo; third: "Check Your Compliance Risk" → /risk-check | One secondary: "View Platform Overview" or "See How It Works". Target: **Option 1** — add `id="how-it-works"` to the existing "Get Set Up in Minutes, Not Hours" section (F) on homepage so link is `/#how-it-works`. **Option 2** — link to `/compliance-vault-pro` (exists). Task says "Implement whichever exists already; do not create broken links." Homepage does not currently have #how-it-works; CVP has `id="how-it-works"`. **Recommendation:** Use `/compliance-vault-pro#how-it-works` for secondary so no new anchor is required on homepage, or add `id="how-it-works"` to homepage section F and use `/#how-it-works`. |
| **A.2 Right-side hero mockup** | | |
| Title: "Portfolio Compliance Snapshot (Example)" | DashboardPreview: "Portfolio Overview" (78%), Expiring Soon / Overdue, Upcoming Expiries list, disabled "Generate Report" | Replace hero right-side content with new mockup. |
| Compliance Score: 62% horizontal bar (not circular) | 78% text only, no bar | New component: horizontal bar for 62%. |
| "Properties monitored: 4" / "2 properties require attention" | Not present | Add to mockup. |
| Category breakdown: Gas Safety 80% (green), Electrical (EICR) 60% (amber), Licensing 40% (red) "Review required", Document Coverage 55% (amber) | Not present | Add bars + rounded % + colour labels. |
| Footer microtext: "Illustrative portfolio example. Live score generated after assessment. Informational indicator only." | "Example preview. Your dashboard reflects your uploaded documents and confirmed dates." | Replace with task wording (compliance-safe). |
| Under card: "Generate My Risk Report" → /risk-check | Disabled "Generate Report" button | Replace with CTA link/button to /risk-check. |
| **A.3 Hero clean** | No heavy disclaimer in hero body | Only small footer under preview card. **OK**; keep disclaimer out of hero body. |

**Implementation note:** DashboardPreview is only used in HomePage.js hero. Either (1) replace DashboardPreview content entirely with the new "Portfolio Compliance Snapshot" mockup and keep one component, or (2) add a new component (e.g. `PortfolioComplianceSnapshotMockup`) and use it in the hero. Option 2 avoids changing other uses of DashboardPreview (there are none currently); Option 1 is simpler. **Recommendation:** New component for the snapshot mockup so hero is clearly task-specific; leave DashboardPreview as-is or remove if unused elsewhere.

---

## 3. Placeholder demo page (task: must NOT exist; replace with Risk Check)

| Task | Current | Recommendation |
|------|---------|----------------|
| Placeholder demo must NOT exist in current form | DemoPage.js at /demo: static page with 4 image panels, fallback "Demo assets coming soon", CTA "Start Your Setup" → /intake/start | **Option A (task):** Replace with Risk Check funnel. |
| How to replace | Two approaches: (1) **Redirect:** `/demo` → redirect to `/risk-check` (same content, one source of truth). (2) **Same component:** `/demo` renders RiskCheckPage. | **Safest:** Redirect `/demo` to `/risk-check` in React Router (`<Route path="/demo" element={<Navigate to="/risk-check" replace />} />`). No duplicate funnel, no broken links; all existing links to /demo land on risk-check. |
| "View Platform Demo" → /risk-check | Task: any "View Platform Demo" buttons/links must go to /risk-check | After redirect, links to /demo already end at /risk-check. Additionally, update all **link text** that says "View Platform Demo" or "View Demo" to point to `/risk-check` (so URL is explicit and analytics clear). Optional: keep href as /demo and rely on redirect. **Recommendation:** Change href to `/risk-check` everywhere so analytics and bookmarks are consistent. |

**Conflict:** Task says "Replace it with the Risk Check funnel (Option A)". That means the *route* /demo should no longer show the placeholder content. It does **not** require deleting DemoPage.js from the repo (could be kept for reference or removed). Redirect satisfies "must NOT exist in its current form."

---

## 4. CVP page (compliance-vault-pro)

| Task | Current | Gap / action |
|------|---------|--------------|
| Two stages: (1) After pain insert "Check Your Compliance Risk"; (2) After pricing "Activate Monitoring" → /intake/start | (1) No "pain" section like homepage; section B is "One platform to track...". (2) Pricing CTAs say "Start Your Setup" → /intake/start | (1) Insert a section after section B ("What it does") with heading/CTA "Check Your Compliance Risk" → /risk-check. (2) Change pricing card button text to "Activate Monitoring"; keep link /intake/start. |
| Primary CTA on CVP | Hero: "Start Your Setup" → /intake/start | Task says primary CTA everywhere = "Check Your Compliance Risk" → /risk-check. So CVP hero primary should also be "Check Your Compliance Risk" → /risk-check (align with task "Primary CTA everywhere"). |
| Secondary CTA on CVP | "View Platform Demo" → /demo | Should go to /risk-check (or keep as secondary to "See How It Works" to CVP #how-it-works). Task: "View Platform Demo" → /risk-check. So CVP secondary → /risk-check. |

**CVP section order today:** Hero → What it does (B) → What You Get (C) → How It Works (D) → How the Score Works (E) → Who It's For (F) → Reminders (G) → Reports (H) → Pricing (I) → FAQ (J) → Final CTA (K).  
**Insert:** After B (What it does), add section "Check Your Compliance Risk" with CTA → /risk-check.  
**Pricing:** In section I, change plan card button text from "Start Your Setup" to "Activate Monitoring"; link stays /intake/start.

---

## 5. Summary: what’s implemented vs missing

**Already implemented (no change needed for this task):**

- Route `/risk-check` and RiskCheckPage (full funnel: steps, preview, report, email gate, CTAs to /intake/start).
- Backend: POST /api/risk-check/preview, /report, /activate; risk_leads; conversion linking to intake and Stripe.
- PublicHeader: "Check Your Compliance Risk" → /risk-check.
- Intake and provisioning unchanged; risk-check is lead-only until activation.
- CVP page exists at /compliance-vault-pro with pricing and #how-it-works.

**Missing or wrong (to implement):**

1. **Homepage hero:** Risk-first headline and subtext; single primary CTA "Check Your Compliance Risk" → /risk-check; single secondary "View Platform Overview" (or "See How It Works") → /compliance-vault-pro#how-it-works or /#how-it-works (add id on homepage).
2. **Homepage hero right side:** Replace current preview with "Portfolio Compliance Snapshot (Example)" mockup: 62% bar, 4 properties / 2 require attention, category bars (Gas 80%, EICR 60%, Licensing 40% red, Document 55%), footer microtext, CTA "Generate My Risk Report" → /risk-check.
3. **Demo page:** /demo must not show placeholder. Redirect /demo → /risk-check (or render RiskCheckPage); update any "View Platform Demo" / "View Demo" links to /risk-check.
4. **CVP page:** Hero primary CTA → "Check Your Compliance Risk" → /risk-check; secondary → /risk-check (or "See How It Works" to #how-it-works). After section B, insert "Check Your Compliance Risk" section with CTA → /risk-check. Pricing card buttons: "Activate Monitoring" → /intake/start.
5. **Homepage:** Final CTA "View Demo" → /risk-check; any other /demo links → /risk-check.

---

## 6. Conflicts and safest options

| Issue | Conflict | Safest option |
|-------|----------|---------------|
| Secondary CTA target | Task: #how-it-works or /compliance-vault-pro. Homepage has no #how-it-works. | Use **/compliance-vault-pro** for "View Platform Overview" so no broken link. Optional: add `id="how-it-works"` to homepage section F and use `/#how-it-works` so users stay on homepage. |
| /demo route | Task: placeholder must not exist; replace with Risk Check. | **Redirect** `/demo` → `/risk-check`. Do not render DemoPage at /demo. Update all links that point to /demo to point to /risk-check so the funnel is explicit. |
| CVP primary CTA | Current: "Start Your Setup" → /intake/start. Task: "Primary CTA everywhere = Check Your Compliance Risk → /risk-check." | Make CVP hero primary = "Check Your Compliance Risk" → /risk-check; keep "Start Your Setup" or "Activate Monitoring" for pricing and after-risk sections. |
| Mockup component | Task specifies new hero mockup; current DashboardPreview is different. | Add **new component** (e.g. `PortfolioComplianceSnapshotMockup`) for the task mockup; use it only in the homepage hero. Keeps existing DashboardPreview unchanged for possible reuse; no risk of breaking other pages. |

---

## 7. Recommended implementation order (no code written here)

1. **Redirect /demo → /risk-check** (App.js): Replace `<Route path="/demo" element={<DemoPage />} />` with `<Route path="/demo" element={<Navigate to="/risk-check" replace />} />`. Then replace all links to `/demo` with `/risk-check` in HomePage, CVPLandingPage, FAQPage so the funnel is explicit.
2. **Homepage hero copy and CTAs:** Update headline and subtext to task wording; single primary "Check Your Compliance Risk" → /risk-check; single secondary "View Platform Overview" → /compliance-vault-pro (or /#how-it-works if you add the id).
3. **Homepage hero mockup:** New component for "Portfolio Compliance Snapshot (Example)" with 62% bar, 4/2 properties, category bars, footer microtext, "Generate My Risk Report" → /risk-check. Use it in the hero; remove or keep DashboardPreview elsewhere.
4. **CVP page:** (a) Hero: primary "Check Your Compliance Risk" → /risk-check, secondary to /risk-check or "See How It Works" → #how-it-works. (b) After section B, insert "Check Your Compliance Risk" section with CTA → /risk-check. (c) Pricing section: button text "Activate Monitoring", link /intake/start.
5. **Homepage final CTA:** "View Demo" → /risk-check (or "View Platform Overview" → /compliance-vault-pro for consistency).

**Do not:**

- Change intake, Stripe, provisioning, or dashboard flows.
- Add login or provisioning from /risk-check.
- Change brand colours/typography/spacing beyond what the task specifies.
- Leave the placeholder demo page reachable at /demo.

This audit is the single reference for what is done vs missing and the recommended, conflict-free way to implement the task.
