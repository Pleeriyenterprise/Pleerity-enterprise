# Stage ZA4 — Zoho One Adoption Blueprint

**Programme:** STAGE ZA — ZOHO ONE BUSINESS VALUE REALISATION & ADOPTION BLUEPRINT  
**Date:** 2026-07-09  
**Prerequisite:** Stage Z architecture approved in principle

---

## Master blueprint table

| Application | Business purpose | Primary users | Internal / Platform | Integration required | Implementation approach | Dependencies | Risks | Operational value | Priority |
|-------------|------------------|---------------|---------------------|----------------------|-------------------------|--------------|-------|-------------------|----------|
| **Zoho Books** | Pleerity Ltd accounting, VAT, AP/AR, bank reconciliation | Finance, founder, accountant | **Internal** | **No** | Standalone org setup; Stripe payout CSV/API export; chart of accounts | Bank feed, accountant access | Confusion with customer Stripe billing | **High** | **P1** |
| **Zoho WorkDrive** | Internal policies, HR files, vendor docs, board materials | All staff, legal, HR, finance | **Internal** | **No** | Folder taxonomy; permissions by role; link from Sign completed docs | Sign (optional), staff onboarding | Customer data uploaded by mistake | **High** | **P1** |
| **Zoho Sign** | NDAs, vendor contracts, partnership agreements, employment | Legal, commercial, HR | **Internal** | **No** (internal use) | Template library; routing rules; completed PDF → WorkDrive via Flow | WorkDrive, legal templates | Using for subscription checkout | **High** | **P1** |
| **Zoho Flow** | Automate internal handoffs (Sign→WorkDrive, Books reminders) | Finance, legal, ops | **Internal** | **No** | Zoho-native flows only; no Pleerity API writes | Books, WorkDrive, Sign adopted | Platform orchestration creep | **Medium** | **P2** |
| **Zoho Analytics** | Executive BI: MRR, funnel, ops KPIs, finance views | CEO, finance, commercial | **Both** | **Yes** (read-only feed) | Programme B: dashboards; Programme A: nightly Pleerity export | Stripe export, optional lead export | PII in dashboards; stale data | **High** | **P2** |
| **Zoho CRM** | Sales activity UI on product leads (optional) | Sales, commercial | **Platform** (replica) | **Yes** (one-way outbound) | Pleerity → Zoho upsert; external key `pleerity_lead_id` | Integration service, sales demand sign-off | Two-way sync; duplicate leads | **Medium** | **P3** (optional) |
| **Zoho Campaigns** | Promotional email broadcast | Marketing | **Hybrid** | **Yes** (audience export) | Suppression export from Pleerity; unsubscribe webhook back | Kit evaluation, DPIA | Duplicate sends to clients | **Medium** | **P3** (conditional) |
| **Zoho Marketing Automation** | Cold prospect drip campaigns | Marketing | **Internal** (audience) | **No** (platform) | Standalone lists; no product nurture | Campaigns or standalone | Client lifecycle emails in MA | **Low–Medium** | **P4** (optional) |
| **Zoho SalesIQ** | Marketing website live chat & visitor engagement | Marketing, pre-sales | **Internal** (marketing site) | **No** | Embed on public pages only; not on portal | Cookie consent update | Portal embed conflict | **Medium** | **P3** |
| **Zoho Forms** | Event registration, internal surveys, partner intake | Marketing, HR, ops | **Internal** | **No** | Self-serve forms; manual or Flow routing | WorkDrive for uploads | Product lead capture via Zoho | **Medium** | **P3** |
| **Zoho PageSense** | Landing page A/B testing and conversion optimisation | Marketing | **Internal** (marketing site) | **No** | Marketing site snippet; consent banner update | Cookie policy | GDPR/consent non-compliance | **Medium** | **P3** |

---

## Implementation approach definitions

| Approach | Description |
|----------|-------------|
| **Standalone adoption** | Configure Zoho app; no Pleerity code or API coupling |
| **Manual bridge** | CSV export/import between systems (e.g. Stripe → Books) |
| **Read-only feed** | Scheduled Pleerity export to Analytics — no write path |
| **One-way sync** | Pleerity Integration Service pushes to Zoho after platform write |
| **Event-driven ingress** | Zoho webhook → validated adapter → Pleerity (Campaigns unsubscribe, Sign completion if platform-linked later) |
| **Marketing embed** | JavaScript snippet on public marketing pages only |

---

## Per-application detail

### Zoho Books

| Field | Detail |
|-------|--------|
| Business purpose | Run Pleerity Enterprise Ltd finances |
| Primary users | Finance manager, external accountant |
| Integration required | **No** |
| Approach | Standalone + Stripe payout export (weekly/monthly) |
| Dependencies | UK VAT settings, bank connection, accountant invite |
| Risks | Staff confuse customer Stripe with company books |
| Value | **High** — eliminates manual bookkeeping |
| Priority | **P1 — immediate** |

### Zoho WorkDrive

| Field | Detail |
|-------|--------|
| Business purpose | Single internal document repository |
| Primary users | All employees |
| Integration required | **No** |
| Approach | Standalone; folder structure: Legal, HR, Finance, Commercial, Board |
| Dependencies | Staff Zoho accounts |
| Risks | Customer compliance docs must never be stored here |
| Value | **High** |
| Priority | **P1 — immediate** |

### Zoho Sign

| Field | Detail |
|-------|--------|
| Business purpose | Execute non-subscription legal agreements |
| Primary users | Legal, commercial, HR |
| Integration required | **No** for internal; **Yes** only if platform B2B signing approved later |
| Approach | Template library; Flow files to WorkDrive |
| Dependencies | Legal template approval |
| Risks | Replacing subscription click-wrap |
| Value | **High** |
| Priority | **P1 — immediate** |

### Zoho Analytics

| Field | Detail |
|-------|--------|
| Business purpose | Leadership dashboards across finance and growth |
| Primary users | CEO, finance, head of commercial |
| Integration required | **Yes** — read-only Pleerity + Stripe exports |
| Approach | Programme B dashboards first with manual CSV; Programme A automates feed |
| Dependencies | Books data, Stripe export, governance/DPIA for platform feed |
| Risks | PII exposure in shared dashboards |
| Value | **High** |
| Priority | **P2** |

### Zoho Flow

| Field | Detail |
|-------|--------|
| Business purpose | Internal automation between Zoho apps |
| Primary users | Ops, finance |
| Integration required | **No** |
| Approach | Sign complete → WorkDrive folder; Books payment reminder |
| Dependencies | P1 apps live |
| Risks | Used for platform sync (prohibited) |
| Value | **Medium** |
| Priority | **P2** |

### Zoho CRM

| Field | Detail |
|-------|--------|
| Business purpose | Sales team workspace for product leads |
| Primary users | Sales |
| Integration required | **Yes** |
| Approach | One-way Pleerity → Zoho; skip if admin CRM sufficient |
| Dependencies | Programme A governance, integration service, written sales demand |
| Risks | Duplicate CRM SoR |
| Value | **Medium** (conditional) |
| Priority | **P3 — optional** |

### Zoho Campaigns

| Field | Detail |
|-------|--------|
| Business purpose | Marketing broadcast email |
| Primary users | Marketing |
| Integration required | **Yes** — audience + suppression |
| Approach | Export subscribers/prospects; webhook unsubscribes |
| Dependencies | Kit gap documented, DPIA |
| Risks | Emails to suppressed lifecycle clients |
| Value | **Medium** (conditional) |
| Priority | **P3 — optional** |

### Zoho Marketing Automation

| Field | Detail |
|-------|--------|
| Business purpose | Cold prospect nurturing |
| Primary users | Marketing |
| Integration required | **No** |
| Approach | Standalone cold lists only |
| Dependencies | Marketing strategy for cold audience |
| Risks | Overlap with Pleerity nurture |
| Value | **Low–Medium** |
| Priority | **P4 — optional** |

### Zoho SalesIQ

| Field | Detail |
|-------|--------|
| Business purpose | Pre-sales chat on marketing website |
| Primary users | Marketing, sales |
| Integration required | **No** |
| Approach | Marketing site embed only |
| Dependencies | Cookie consent |
| Risks | Portal deployment |
| Value | **Medium** |
| Priority | **P3** |

### Zoho Forms

| Field | Detail |
|-------|--------|
| Business purpose | Internal and event forms |
| Primary users | Marketing, HR, events |
| Integration required | **No** |
| Approach | Standalone forms; no product lead paths |
| Dependencies | None |
| Risks | Revenue forms bypass Pleerity |
| Value | **Medium** |
| Priority | **P3** |

### Zoho PageSense

| Field | Detail |
|-------|--------|
| Business purpose | Conversion rate optimisation |
| Primary users | Marketing |
| Integration required | **No** |
| Approach | Marketing site snippet post-consent |
| Dependencies | Cookie policy update |
| Risks | Consent non-compliance |
| Value | **Medium** |
| Priority | **P3** |

---

## Adoption sequencing (combined view)

```
Week 1–4   Programme B P1: Books + WorkDrive + Sign (parallel)
Week 5–6   Programme B P2: Flow automations
Week 5–8   Programme B: Analytics dashboards (manual data initially)
Week 9–12  Programme B P3: SalesIQ, PageSense, Forms (marketing)
Week 1–8   Programme A Phase 0: Governance (parallel, if platform track approved)
Week 9+    Programme A: Analytics feed → optional CRM → optional Campaigns
```

---

## Stage ZA4 conclusion

**11 applications assessed.** **3 are immediate internal wins** (Books, WorkDrive, Sign). **4 are marketing-site or internal standalone** (SalesIQ, PageSense, Forms, MA). **Up to 3 require platform integration** (Analytics feed, CRM, Campaigns) under Programme A with governance.
