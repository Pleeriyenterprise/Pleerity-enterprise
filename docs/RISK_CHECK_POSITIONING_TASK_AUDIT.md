# Risk Check Positioning on Homepage + CVP Page (Conversion-First) — Task Audit

**Task:** Implement Risk Check positioning on Homepage + CVP page with visible Compliance Score Preview mockup. Conversion-first; lead-based until activation; keep brand identity. **Do not implement blindly.** This audit identifies what is implemented vs missing, conflicts with prior tasks, and the safest approach.

**Context (task):** Marketing site already rebuilt. Risk Check = primary conversion funnel. Routes /risk-check and /intake/start exist. No provisioning/login from risk-check.

---

## 1. GOALS CHECKLIST (task “must meet all”)

| Goal | Current state | Status |
|------|---------------|--------|
| 1) Prominent primary CTA to /risk-check on Homepage hero | HomePage.js 136–146: primary “Check Your Compliance Risk” → /risk-check | **Done** |
| 2) “Compliance Score Preview” mockup on Homepage | PortfolioComplianceSnapshotMockup in hero right column (171–174); content differs from task spec (see A.2 below) | **Partial** |
| 3) Risk Check CTAs on CVP: above-fold and mid-page | CVP hero: “Check Your Compliance Risk” → /risk-check; secondary “See How It Works” → #how-it-works. Mid-page block (216–235): “Unsure where you stand?” + “Check Your Compliance Risk” → /risk-check. No “Start Monitoring” or “View Pricing” in hero/mid per this task’s exact wording | **Partial** |
| 4) All “Demo” links point to /risk-check (or remove placeholder) | /demo redirects to /risk-check (App.js 190); no Demo wording on CVP/Home/FAQ | **Done** |
| 5) Compliance-safe language | “Informational indicator”, “not legal advice” used; mockup footer “Informational indicator only” | **Done** |
| 6) Responsive and clean on mobile | Tailwind responsive classes (e.g. flex-col sm:flex-row, grid lg:grid-cols-2); no change needed | **Done** |

---

## 2. A) HOMEPAGE CHANGES

**File:** `frontend/src/pages/public/HomePage.js`

### A.1) Hero CTAs

| Requirement | Current (file:line) | Gap / conflict |
|-------------|---------------------|----------------|
| Primary: “Check Your Compliance Risk” → /risk-check | 136–146: `<Link to="/risk-check">Check Your Compliance Risk</Link>` | **Done** |
| Secondary: “Start Monitoring” → /intake/start | 152–158: secondary is “View Platform Overview” → `/compliance-vault-pro` | **Missing.** Task explicitly asks secondary = “Start Monitoring” → /intake/start. A previous task specified secondary = “View Platform Overview” → CVP. **Conflict.** Recommendation: follow this (conversion-first) task and set homepage hero secondary to “Start Monitoring” → /intake/start so both funnels are above the fold. |
| Keep existing CTA styling | Button + Link usage unchanged | **OK** |

**Recommendation:** Change HomePage.js hero secondary button to text “Start Monitoring” and link to `/intake/start`. Primary stays “Check Your Compliance Risk” → /risk-check.

---

### A.2) “Compliance Score Preview” section (under hero or hero right column)

Current implementation: **PortfolioComplianceSnapshotMockup** in hero right column (`HomePage.js` 171–174), `frontend/src/components/public/PortfolioComplianceSnapshotMockup.js`.

| Task requirement | Current implementation | Status |
|------------------|------------------------|--------|
| Static mock card (no API calls) | No API calls | **Done** |
| Title: “Compliance Score (Example Preview)” | “Portfolio Compliance Snapshot (Example)” | **Different** — task asks “Compliance Score (Example Preview)”. |
| Score badge: “62%” | 62% shown with horizontal bar | **Done** |
| Risk label: “Moderate–High” | Not present (has “2 properties require attention” + category bars) | **Missing** |
| 3 sample alerts: “Gas Safety: due soon”, “EICR: not confirmed”, “Document vault: incomplete” | Category breakdown bars (Gas Safety 80%, EICR 60%, Licensing 40%, Document Coverage 55%) | **Different** — task asks for 3 text alerts, not bar breakdown. |
| Footer note: “Example preview. Your score is generated from your inputs. This is not legal advice.” | “Illustrative portfolio example. Live score generated after assessment. Informational indicator only.” | **Different** — task wording is explicit. |
| CTA under card: “Generate My Risk Report” → /risk-check | Present (PortfolioComplianceSnapshotMockup.js 69–74) | **Done** |

**Conflict:** Existing mockup was built for an earlier “Portfolio Compliance Snapshot” spec (bars, properties count). This task specifies a simpler card: title “Compliance Score (Example Preview)”, 62%, “Moderate–High”, three bullet alerts, and the exact footer. **Safest option:** Update `PortfolioComplianceSnapshotMockup.js` to match this task (title, add risk label “Moderate–High”, replace category bars with the 3 alerts, replace footer with task text). Keep “Generate My Risk Report” → /risk-check. Optionally keep the horizontal 62% bar for consistency with existing design.

---

### A.3) Optional trust strip

| Task | Current | Status |
|------|---------|--------|
| 1-line near preview: “Built for UK landlords • Expiry tracking • Reminder automation • Audit trail” | Trust bullets below hero (different text): Expiry reminders, Evidence vault, Portfolio view, PDF reports, Not legal advice | **Optional** — task says “recommended”. Can add this line under or near the preview card; no conflict. |

---

## 3. B) COMPLIANCE VAULT PRO PAGE CHANGES

**File:** `frontend/src/pages/public/CVPLandingPage.js`

### B.1) Above the fold

| Requirement | Current (file:line) | Status |
|-------------|---------------------|--------|
| Primary: “Check Your Risk” → /risk-check | 159–163: “Check Your Compliance Risk” → /risk-check | **Done** (task allows “Check Your Risk”; current is longer, acceptable) |
| Secondary: “Start Monitoring” → /intake/start | 164–171: “See How It Works” → /compliance-vault-pro#how-it-works | **Missing.** Task asks secondary = “Start Monitoring” → /intake/start. |

**Recommendation:** Add or replace secondary button so above-fold has: primary “Check Your Compliance Risk” (or “Check Your Risk”) → /risk-check, secondary “Start Monitoring” → /intake/start. “See How It Works” can remain as a third link or move elsewhere (e.g. mid-page or nav).

---

### B.2) Mid-page CTA block (after “How it works” or “What you get”)

| Requirement | Current (file:line) | Status |
|-------------|---------------------|--------|
| Headline: “See your compliance risk in 60 seconds” | 220: “Unsure where you stand?” | **Different** — task asks this exact headline. |
| Body: “Answer a few questions and get a structured risk report. Lead-only until you activate monitoring.” | 222–224: “Run a quick risk check and get a structured report. Lead-only until you activate monitoring.” | **Close** — minor wording difference. |
| Button “Check Your Risk” → /risk-check | 225–233: “Check Your Compliance Risk” → /risk-check | **Done** |
| Button “View Pricing” → /pricing | Not in this block | **Missing.** Task asks “View Pricing” → /pricing in the same block. |

**Recommendation:** In the existing block (216–235): (1) Change heading to “See your compliance risk in 60 seconds”. (2) Set body to “Answer a few questions and get a structured risk report. Lead-only until you activate monitoring.” (3) Add secondary button “View Pricing” → /pricing next to “Check Your Risk” (or “Check Your Compliance Risk”).

---

### B.3) Replace “Demo” on CVP

| Requirement | Current | Status |
|-------------|---------|--------|
| No “Demo”; use “Risk Check” / “Compliance Risk Report”; no sandbox | Grep: no “Demo” or “sandbox” in CVPLandingPage.js | **Done** |

---

## 4. C) NAV + LINKS CLEANUP

| Search | Current | Status |
|--------|---------|--------|
| "/demo" | Only in App.js as redirect path (190); no links to /demo in Home/CVP/FAQ | **Done** |
| "View Demo" | Replaced; no remaining instances | **Done** |
| "Platform Demo" | Removed with DemoPage | **Done** |
| "Try Demo" | Not found | **Done** |

No further cleanup required.

---

## 5. D) ROUTING

| Requirement | Current (file:line) | Status |
|-------------|----------------------|--------|
| Route /risk-check → RiskCheckPage | App.js 224: `<Route path="/risk-check" element={<RiskCheckPage />} />` | **Done** |

---

## 6. E) ACCESSIBILITY + SEO

| Requirement | Current | Status |
|-------------|---------|--------|
| Buttons as <Link> or <a> with aria-label if needed | CTAs use `<Link>` / Button asChild; no aria-label on hero CTAs | **OK** — add aria-label only if needed for screen readers (e.g. “Check your compliance risk”). |
| Score preview clearly “Example preview” | Footer says “Illustrative portfolio example” / “Informational indicator only”; card title “Portfolio Compliance Snapshot (Example)” | **Partial** — task wants “Compliance Score (Example Preview)” and footer “Example preview. Your score is generated from your inputs. This is not legal advice.” Align with A.2. |
| H2 near preview for SEO: “UK landlord compliance tracking—risk report in 60 seconds” | No H2 with this phrase in hero; next section H2 is “See Your Entire Portfolio in One View” | **Missing.** Task asks for this H2 near the preview. Add above the preview card (or above hero right column) so the preview section has this heading. |

---

## 7. CONFLICTS AND SAFEST OPTIONS

### Conflict 1: Homepage hero secondary CTA

- **Previous task:** Secondary = “View Platform Overview” (or “See How It Works”) → /compliance-vault-pro.
- **This task:** Secondary = “Start Monitoring” → /intake/start.
- **Recommendation:** Treat this task as the conversion-first spec and set homepage hero secondary to “Start Monitoring” → /intake/start. Keep primary “Check Your Compliance Risk” → /risk-check. Optionally add “View Platform Overview” elsewhere (e.g. below hero or in a trust strip) if you want both paths visible.

### Conflict 2: Preview card content

- **Existing:** “Portfolio Compliance Snapshot (Example)” with 62% bar, properties count, category bars, different footer.
- **This task:** “Compliance Score (Example Preview)”, 62%, “Moderate–High”, 3 alerts (Gas Safety: due soon; EICR: not confirmed; Document vault: incomplete), specific footer, same CTA.
- **Recommendation:** Update the existing mockup component to match this task (one source of truth). No need for a second component; change title, add risk label, replace bars with the 3 alerts, update footer. Keeps one card, one CTA, compliance-safe.

### No conflict

- Demo removal, routing, CVP “Demo” wording, compliance language, and responsive layout are already correct. CVP mid-page block exists; only headline, body, and “View Pricing” need to align with this task.

---

## 8. SUMMARY: IMPLEMENTED VS MISSING

**Implemented (no change needed):**

- Homepage primary CTA “Check Your Compliance Risk” → /risk-check (HomePage.js 136–146).
- Preview mockup present in hero right column with 62% and “Generate My Risk Report” → /risk-check (PortfolioComplianceSnapshotMockup.js).
- CVP above-fold primary “Check Your Compliance Risk” → /risk-check (CVPLandingPage.js 159–163).
- CVP mid-page block with “Check Your Compliance Risk” → /risk-check (216–235).
- All demo links/route point to /risk-check; no Demo wording on CVP.
- Compliance-safe language; responsive layout.
- Route /risk-check exists (App.js 224).

**Missing or to change:**

1. **Homepage hero secondary CTA:** Change to “Start Monitoring” → /intake/start (HomePage.js 152–158).
2. **Homepage preview card (mockup):** Align with task: title “Compliance Score (Example Preview)”; add risk label “Moderate–High”; replace category bars with 3 alerts (Gas Safety: due soon; EICR: not confirmed; Document vault: incomplete); footer “Example preview. Your score is generated from your inputs. This is not legal advice.” (PortfolioComplianceSnapshotMockup.js.)
3. **Homepage SEO H2:** Add H2 “UK landlord compliance tracking—risk report in 60 seconds” near the preview (HomePage.js, above or adjacent to mockup).
4. **CVP above-fold secondary:** Add “Start Monitoring” → /intake/start (CVPLandingPage.js 164–171; add button or replace “See How It Works” per product preference).
5. **CVP mid-page block:** Headline “See your compliance risk in 60 seconds”; body “Answer a few questions and get a structured risk report. Lead-only until you activate monitoring.”; add “View Pricing” → /pricing (CVPLandingPage.js 216–235).
6. **Optional:** Trust strip “Built for UK landlords • Expiry tracking • Reminder automation • Audit trail” near preview (HomePage.js).

---

## 9. DELIVERABLES (task)

| Deliverable | Status |
|-------------|--------|
| 1) PR-ready diff with file:line references | This audit provides file:line refs; implementation will produce the diff. |
| 2) Screenshots or notes for desktop + mobile | Not produced in this audit. After implementing the missing items, add brief layout notes or screenshots for hero + preview on desktop and mobile. |
| 3) Confirm all demo links go to /risk-check | **Confirmed:** /demo redirects to /risk-check; no remaining demo links to old placeholder. |

---

## 10. RECOMMENDED IMPLEMENTATION ORDER (no code written here)

1. Update **PortfolioComplianceSnapshotMockup.js** to task spec (title, 62%, Moderate–High, 3 alerts, footer).
2. Add **H2** “UK landlord compliance tracking—risk report in 60 seconds” near the preview on **HomePage.js** (e.g. above the mockup in the hero right column).
3. Change **HomePage.js** hero secondary to “Start Monitoring” → /intake/start.
4. (Optional) Add trust strip under or near preview on HomePage.
5. On **CVPLandingPage.js**: add secondary “Start Monitoring” → /intake/start above the fold; update mid-page block headline/body and add “View Pricing” → /pricing.

This audit is the single reference for what is implemented vs missing and how to resolve conflicts without duplicating or breaking existing behaviour.
