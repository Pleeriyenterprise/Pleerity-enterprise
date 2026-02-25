# Risk-First Homepage & CVP Page — Task Compliance Audit

**Purpose:** Check the codebase against the stated task requirements. Identify what is implemented, what is missing, and any conflicts. Propose the safest option where instructions conflict. **Audit only — no implementation.**

---

## CORE STRATEGY (task)

| Requirement | Current state | Status |
|-------------|---------------|--------|
| Risk-first positioning on homepage hero | Hero headline: "Are You Fully Compliant as a UK Landlord?"; subtext matches; primary CTA "Check Your Compliance Risk" → /risk-check | **Done** |
| Primary CTA everywhere (homepage + CVP) = "Check Your Compliance Risk" → /risk-check | Homepage hero primary ✓. CVP hero primary = "Check Your Risk" → /risk-check (shortened label). Header nav "Check Your Compliance Risk" → /risk-check ✓ | **Done** (CVP label slightly shortened) |
| Secondary CTA on homepage = "View Platform Overview" (or "See How It Works") → CVP section or /compliance-vault-pro | Homepage hero secondary is **"Start Monitoring"** → **/intake/start**. Task requires **"View Platform Overview"** → #how-it-works or /compliance-vault-pro | **Gap** |
| CVP page: (1) After pain section insert "Check Your Compliance Risk"; (2) After pricing "Activate Monitoring" → /intake/start | CVP has mid-page block "See your compliance risk in 60 seconds" with "Check Your Risk" → /risk-check (after "What it does"). Pricing cards and post-pricing block have "Activate Monitoring" → /intake/start ✓ | **Done** |
| Placeholder demo page must NOT exist; replace with Risk Check funnel (Option A) | App.js: `/demo` → `<Navigate to="/risk-check" replace />` | **Done** |
| Any "View Platform Demo" buttons/links → /risk-check | FAQPage: "Schedule a Demo" → /risk-check ✓. No "View Platform Demo" wording found; demo route goes to risk-check | **Done** |
| Risk Check is lead-only until they activate monitoring; no login/provisioning/entitlements at demo stage | Risk check creates lead only; intake/Stripe/provisioning are separate flow | **Done** (per prior implementation) |

---

## CONVERSION LADDER (task)

**Required ladder (only):** Homepage → /risk-check → /intake/start → Stripe → Provisioning → Dashboard.

**Conflicts with ladder (bypass risk-check):**

- **Homepage hero secondary:** "Start Monitoring" → /intake/start. Sends users straight to intake and skips risk-check.
- **Homepage section "THE PROBLEM" (C):** "Start Your Setup" → /intake/start.
- **Homepage section "HOW IT WORKS" (F):** "Start Tracking Today" → /intake/start.
- **Homepage "Dashboard preview" section:** "Generate Report" → /intake/start.
- **Homepage "PRICING FRAMING" (H):** "Start Your Setup" → /intake/start.
- **Homepage final CTA (J):** Primary = "Start Your Setup" → /intake/start, secondary = "View Platform Overview" → /risk-check. Task says primary everywhere = "Check Your Compliance Risk" → /risk-check; so this block inverts the intended primary/secondary and sends primary to intake.

**Safest option:** Align all homepage CTAs with the single ladder: primary = risk-check (or "Check Your Compliance Risk"), secondary = "View Platform Overview" → /compliance-vault-pro or #how-it-works. Remove or change any CTA that goes directly to /intake/start so the only path to intake is via risk-check (or explicit "Activate Monitoring" from CVP/email).

---

## A) HOMEPAGE — Detailed

### A.1 Hero copy (risk-first)

| Task | Current | Status |
|------|---------|--------|
| Headline: "Are You Fully Compliant as a UK Landlord?" | Matches | **Done** |
| Subtext: "Structured compliance monitoring and renewal tracking for UK portfolios." | Matches | **Done** |
| Primary CTA: "Check Your Compliance Risk" → /risk-check | Matches | **Done** |
| Secondary CTA: "View Platform Overview" → Option 1: #how-it-works, Option 2: /compliance-vault-pro | Secondary is "Start Monitoring" → /intake/start | **Gap** |

**Implement:** Change hero secondary to "View Platform Overview". Link to **/compliance-vault-pro** (Option 2) unless you add `id="how-it-works"` to the "Get Set Up in Minutes" section (F) and use `#how-it-works` (Option 1). Option 2 avoids depending on an anchor that does not currently exist.

### A.2 Right-side hero preview mockup (Portfolio Compliance Snapshot)

| Task | Current (PortfolioComplianceSnapshotMockup.js) | Status |
|------|-----------------------------------------------|--------|
| Title: "Portfolio Compliance Snapshot (Example)" | "Compliance Score (Example Preview)" | **Gap** — align title |
| Compliance Score: 62% as **horizontal bar** (not circular) | 62% text + "Moderate–High" badge; no bar | **Gap** — add horizontal bar |
| "Properties monitored: 4" | Not present | **Gap** |
| "2 properties require attention" | Not present (has 3 sample alerts as list) | **Gap** |
| Category breakdown **with bars + rounded %**: Gas Safety 80% (green), Electrical (EICR) 60% (amber), Licensing 40% (red) "Review required", Document Coverage 55% (amber) | Simple list of alerts (e.g. "Gas Safety: due soon"); no category bars | **Gap** — replace with category bars |
| Footer microtext: "Illustrative portfolio example. Live score generated after assessment. Informational indicator only." | "Example preview. Your score is generated from your inputs. This is not legal advice." | **Gap** — use task wording |
| Under card: "Generate My Risk Report" → /risk-check | Button "Generate My Risk Report" → /risk-check ✓ | **Done** |

**Implement:** Update `PortfolioComplianceSnapshotMockup.js`: title, 62% as horizontal bar, "Properties monitored: 4", "2 properties require attention", category breakdown (Gas Safety, EICR, Licensing, Document Coverage) with bars and colours, task footer microtext. Keep CTA under the card as-is.

### A.3 Hero cleanliness

| Task | Current | Status |
|------|---------|--------|
| No heavy disclaimer in hero body; only small footer under preview card | Hero has trust bullets (Expiry reminders, etc.); no long disclaimer in hero. Footer under mockup is "Built for UK landlords • Expiry tracking..." (homepage) and inside mockup "Example preview. Your score..." | **Done** if task footer lives under preview card only; move any disclaimer text into mockup footer per task |

---

## CVP PAGE — Two stages

| Task | Current | Status |
|------|---------|--------|
| Stage 1: After pain section insert "Check Your Compliance Risk" | Section "B.5) See your compliance risk in 60 seconds" after "What it does"; "Check Your Risk" → /risk-check | **Done** |
| Stage 2: After pricing section CTA "Activate Monitoring" → /intake/start | Pricing cards: cta "Activate Monitoring" → /intake/start; post-pricing block "Activate Monitoring" → /intake/start | **Done** |

CVP hero: primary "Check Your Risk" → /risk-check, secondary "Start Monitoring" → /intake/start. Task does not require changing CVP hero secondary; only homepage secondary is specified. Optional: use full label "Check Your Compliance Risk" on CVP hero primary for consistency.

---

## CONFLICTS AND SAFEST OPTIONS

| Topic | Conflict | Safest option |
|-------|----------|---------------|
| Homepage secondary CTA | Task: "View Platform Overview" → CVP/anchor. Current: "Start Monitoring" → /intake/start. | Use **"View Platform Overview"** and link to **/compliance-vault-pro** (no anchor dependency). Ensures secondary does not bypass risk-check. |
| Homepage final CTA (J) | Current primary = "Start Your Setup" → /intake/start. Task: primary = "Check Your Compliance Risk" → /risk-check. | Make **primary** = "Check Your Compliance Risk" → /risk-check, **secondary** = "View Platform Overview" → /compliance-vault-pro (or "Start Your Setup" → /intake/start if you want to keep one direct path; task implies single ladder so prefer risk-check as primary). |
| Other homepage CTAs to /intake/start | "THE PROBLEM", "HOW IT WORKS", "Dashboard preview", "PRICING FRAMING" all have CTAs to /intake/start. | Either (a) change to /risk-check or /compliance-vault-pro so the only path to intake is via risk-check/CVP, or (b) leave one "Start Your Setup" as secondary and make all primary CTAs "Check Your Compliance Risk" → /risk-check. Safest for a single ladder: **primary = risk-check everywhere**, secondary = View Platform Overview or Start Your Setup as desired. |
| Mockup: horizontal bar vs circular | Task explicitly asks for horizontal bar for 62%. | Use a **horizontal bar** (e.g. div with width 62%, green/amber as per task). Do not use a circular gauge. |

---

## SUMMARY: IMPLEMENTED VS GAPS

**Implemented**

- Risk-first hero headline and subtext on homepage.
- Homepage hero primary CTA "Check Your Compliance Risk" → /risk-check.
- /demo redirects to /risk-check.
- Header "Check Your Compliance Risk" → /risk-check.
- CVP page: mid-page "Check Your Risk" block; pricing and post-pricing "Activate Monitoring" → /intake/start.
- Portfolio mockup: 62% and a CTA "Generate My Risk Report" → /risk-check.
- Risk check is lead-only; no login/provisioning at demo stage.

**Gaps**

1. **Homepage hero secondary:** Replace "Start Monitoring" → /intake/start with **"View Platform Overview"** → /compliance-vault-pro (or #how-it-works if you add the id).
2. **Portfolio mockup content:** Title "Portfolio Compliance Snapshot (Example)"; 62% as horizontal bar; "Properties monitored: 4"; "2 properties require attention"; category breakdown with bars (Gas Safety 80% green, EICR 60% amber, Licensing 40% red "Review required", Document Coverage 55% amber); footer microtext per task; keep "Generate My Risk Report" under card.
3. **Conversion ladder:** Align remaining homepage CTAs so primary = "Check Your Compliance Risk" → /risk-check and secondary = "View Platform Overview" (or equivalent). At minimum: fix hero secondary and final CTA (J) so primary is risk-check and secondary is View Platform Overview; then decide whether to change THE PROBLEM, HOW IT WORKS, Dashboard preview, and PRICING FRAMING to risk-check or CVP.

---

## FILE REFERENCES

- **Homepage:** `frontend/src/pages/public/HomePage.js` — hero (lines ~122–170), sections C/J, CTAs.
- **CVP page:** `frontend/src/pages/public/CVPLandingPage.js` — hero, B.5 block, pricing, final CTA.
- **Mockup:** `frontend/src/components/public/PortfolioComplianceSnapshotMockup.js` — title, score, bars, footer, CTA.
- **Routes:** `frontend/src/App.js` — /demo → /risk-check, /compliance-vault-pro, /risk-check.
- **Header:** `frontend/src/components/public/PublicHeader.js` — "Check Your Compliance Risk" → /risk-check.

---

## RECOMMENDED IMPLEMENTATION ORDER (when you implement)

1. Homepage hero: secondary CTA to "View Platform Overview" → /compliance-vault-pro.
2. Homepage final CTA (J): primary = "Check Your Compliance Risk" → /risk-check, secondary = "View Platform Overview" → /compliance-vault-pro.
3. PortfolioComplianceSnapshotMockup: full task spec (title, bar, properties count, category bars, footer).
4. Optional: add `id="how-it-works"` to Homepage section F and use #how-it-works for secondary if you prefer anchor over CVP link.
5. Optional: change other homepage CTAs that currently go to /intake/start to /risk-check or /compliance-vault-pro so the conversion ladder is the only path.
