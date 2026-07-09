# Stage ZA1 — Business Value Realisation Review

**Programme:** STAGE ZA — ZOHO ONE BUSINESS VALUE REALISATION & ADOPTION BLUEPRINT  
**Date:** 2026-07-09  
**Prerequisite:** Stage Z audit approved in principle (`zoho_one_integration_governance_01/`)  
**Method:** Commercial and operational assessment — not engineering

---

## Purpose

Convert approved Stage Z architectural positions into **qualitative business value** assessments. No financial projections are provided; impact is rated **High / Medium / Low** with reasoned justification.

## Impact scale

| Rating | Meaning |
|--------|---------|
| **High** | Material time savings, removes recurring manual work, or unlocks capability Pleerity does not have |
| **Medium** | Noticeable improvement for specific teams; partial manual process reduction |
| **Low** | Marginal benefit, niche use, or conditional on other adoption |
| **Negative** | Would harm operations if misapplied (e.g. wrong layer) |

---

## Summary matrix

| Application | Overall business value | Primary beneficiary | Programme |
|-------------|------------------------|---------------------|-----------|
| Zoho Books | **High** | Finance, leadership | B |
| Zoho WorkDrive | **High** | All staff, legal, ops | B |
| Zoho Sign | **High** | Legal, commercial, HR | B |
| Zoho Analytics | **High** | Leadership, finance, ops | A (read feed) + B (dashboards) |
| Zoho Flow | **Medium** | Finance, legal, marketing ops | B |
| Zoho CRM | **Medium** (conditional) | Sales, commercial | A (optional) |
| Zoho Campaigns | **Medium** (conditional) | Marketing | A (optional) |
| Zoho Marketing Automation | **Low–Medium** (internal only) | Marketing | B (cold lists only) |
| Zoho SalesIQ | **Medium** | Marketing, pre-sales | B (marketing site) |
| Zoho Forms | **Medium** | Marketing, ops, HR | B (internal forms) |
| Zoho PageSense | **Medium** | Marketing | B |

---

## Application assessments

### Zoho Books

| Factor | Assessment |
|--------|------------|
| Time saved | **High** — eliminates spreadsheet-based bookkeeping, manual VAT prep, and ad-hoc revenue reconciliation |
| Manual processes eliminated | **High** — journal entries, supplier invoices, expense categorisation, bank reconciliation |
| Operational efficiency | **High** — single finance SoR for Pleerity Ltd |
| Staff productivity | **High** — finance team (or founder-led finance) operates in purpose-built tooling |
| Marketing / sales / CX | Low — no direct customer impact |
| Financial management | **High** — core purpose; Stripe revenue exported for recognition, not re-keyed |
| Legal administration | Low |
| Executive visibility | **Medium** — P&L, cash flow via Books reports; enhanced when combined with Analytics |
| ROI qualitative | **High** — Zoho One subscription cost justified by Books alone for a UK SME |

**Notes:** Platform maintenance `invoices` and Stripe customer billing are **out of scope** for Books. Books serves **Pleerity Enterprise Ltd** only.

---

### Zoho WorkDrive

| Factor | Assessment |
|--------|------------|
| Time saved | **High** — ends email attachment chains, lost policy versions, and informal file shares |
| Manual processes eliminated | **High** — central filing, folder permissions, version history |
| Operational efficiency | **High** — HR, legal, finance, and leadership share one internal DMS |
| Staff productivity | **High** — instant access to templates, contracts archive, board materials |
| Customer experience | None directly — must not store customer compliance evidence |
| Financial management | **Medium** — invoice scans, supplier docs |
| Legal administration | **High** — contract repository alongside Sign |
| Executive visibility | Low |
| ROI qualitative | **High** — commodity capability; building internal DMS in Pleerity would be pure cost |

---

### Zoho Sign

| Factor | Assessment |
|--------|------------|
| Time saved | **High** — removes print-sign-scan cycles for NDAs, vendor agreements, partnerships |
| Manual processes eliminated | **High** — routing, reminders, completion tracking |
| Operational efficiency | **High** — legal and commercial workflows standardised |
| Staff productivity | **High** — legal, HR, commercial teams |
| Customer experience | **Low** on platform — subscription click-wrap remains Pleerity |
| Sales enablement | **Medium** — faster partner and vendor onboarding |
| Legal administration | **High** — audit trail, signer identity, completed PDF archive |
| Executive visibility | Low |
| ROI qualitative | **High** for B2B operations; no engineering effort required for internal use |

---

### Zoho Analytics

| Factor | Assessment |
|--------|------------|
| Time saved | **High** — leadership stops requesting ad-hoc exports from engineering/ops |
| Manual processes eliminated | **High** — recurring report builds, spreadsheet merges (Stripe + leads + ops) |
| Operational efficiency | **Medium** — complements product admin dashboards, does not replace them |
| Staff productivity | **High** — self-serve dashboards for CEO, finance, commercial |
| Marketing effectiveness | **Medium** — funnel and campaign performance views when feeds exist |
| Sales enablement | **Medium** — pipeline and conversion visibility |
| Executive visibility | **High** — primary value driver |
| Financial management | **Medium** — MRR, churn, revenue views when Stripe data exported |
| ROI qualitative | **High** — executive BI is commodity; building in Pleerity is low strategic return |

**Platform note:** Read-only Pleerity data feed is Programme A; dashboard build and daily use is Programme B.

---

### Zoho Flow

| Factor | Assessment |
|--------|------------|
| Time saved | **Medium** — automates handoffs between Zoho apps (Sign → WorkDrive, Books reminders) |
| Manual processes eliminated | **Medium** — internal notifications, file filing, approval nudges |
| Operational efficiency | **Medium** — connects Books, Sign, WorkDrive without custom scripts |
| Staff productivity | **Medium** — ops, finance, legal |
| ROI qualitative | **Medium** — value increases as more Zoho apps are adopted; must not orchestrate platform paths |

---

### Zoho CRM

| Factor | Assessment |
|--------|------------|
| Time saved | **Medium** — only if sales team avoids Pleerity admin UI for daily activity logging |
| Manual processes eliminated | **Low–Medium** — call notes, task reminders in familiar CRM UI |
| Sales enablement | **Medium** — pipeline views, mobile app, call logging |
| Customer experience | **None** if one-way replica — customers never touch Zoho |
| ROI qualitative | **Medium**, conditional — **skip entirely** if sales uses `AdminLeadsPage` effectively |

**Condition:** Business value realised only with written sales demand and one-way Pleerity → Zoho sync.

---

### Zoho Campaigns

| Factor | Assessment |
|--------|------------|
| Time saved | **Medium** — template design, list management, send scheduling |
| Marketing effectiveness | **Medium** — broadcast newsletters, announcements, event invites |
| Manual processes eliminated | **Medium** — reduces manual Kit workarounds if Kit is insufficient |
| Customer experience | **Low** — promotional only; operational email stays Pleerity |
| ROI qualitative | **Medium**, conditional — prove Kit gap before adoption |

---

### Zoho Marketing Automation

| Factor | Assessment |
|--------|------------|
| Time saved | **Low–Medium** — for **cold prospect** drips only |
| Marketing effectiveness | **Medium** — multi-step campaigns on non-product audiences |
| Manual processes eliminated | **Low** for product nurture — Pleerity already automates |
| Customer experience | **Negative** if applied to clients — lifecycle comms must stay Pleerity |
| ROI qualitative | **Low–Medium** — internal marketing-only use; **do not integrate with platform nurture** |

---

### Zoho SalesIQ

| Factor | Assessment |
|--------|------------|
| Time saved | **Medium** — live qualification on marketing site without engineering chat build |
| Sales enablement | **Medium** — visitor chat, basic lead capture to marketing (not platform SoR) |
| Customer experience | **Negative** on authenticated portal — conflicts product support chat |
| Marketing effectiveness | **Medium** — real-time engagement on public pages |
| ROI qualitative | **Medium** — marketing website only; zero platform integration |

---

### Zoho Forms

| Factor | Assessment |
|--------|------------|
| Time saved | **Medium** — rapid internal surveys, event registration, partner intake |
| Manual processes eliminated | **Medium** — no engineering ticket for one-off forms |
| Staff productivity | **Medium** — marketing, HR, events |
| Customer experience | **High** if used for product leads — **prohibited**; Pleerity forms only for revenue paths |
| ROI qualitative | **Medium** — internal ops; platform lead capture stays Pleerity |

---

### Zoho PageSense

| Factor | Assessment |
|--------|------------|
| Time saved | **Medium** — A/B tests without engineering experiments |
| Marketing effectiveness | **Medium** — conversion optimisation on marketing site |
| Manual processes eliminated | **Low** — reduces guesswork on landing page changes |
| Customer experience | None on portal |
| ROI qualitative | **Medium** — after cookie consent alignment; marketing site only |

---

## Value realisation by business function

| Function | Highest-value Zoho apps | Expected impact |
|----------|-------------------------|-----------------|
| **Finance** | Books, Analytics, Flow | **High** |
| **Legal** | Sign, WorkDrive, Flow | **High** |
| **Leadership** | Analytics, Books | **High** |
| **Marketing** | PageSense, SalesIQ, Campaigns (conditional), Forms (internal) | **Medium** |
| **Sales** | CRM (conditional), Analytics | **Medium** |
| **Engineering** | None directly — freed capacity by not building commodity tools | **High** (opportunity cost) |
| **Customer operations** | None — Pleerity platform | N/A |

---

## Stage ZA1 conclusion

**Immediate high-value realisation (Programme B):** Books, WorkDrive, Sign — no platform work required.

**Conditional platform value (Programme A):** Analytics read feed, optional CRM export, optional Campaigns — only after governance and proven gap.

**Marketing site tools (Programme B):** SalesIQ, PageSense, internal Forms — adopt without engineering.

**Do not pursue for platform ROI:** Marketing Automation on product nurture, SalesIQ on portal, Forms for product leads.
