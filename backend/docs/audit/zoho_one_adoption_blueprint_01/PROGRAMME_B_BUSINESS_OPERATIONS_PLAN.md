# Programme B — Internal Business Operations Plan

**Programme:** STAGE ZA — ZOHO ONE BUSINESS VALUE REALISATION & ADOPTION BLUEPRINT  
**Track:** Business-led Zoho adoption — no platform engineering  
**Date:** 2026-07-09

---

## Programme definition

Programme B realises **immediate Zoho One value** for Pleerity Enterprise Ltd internal operations. No Pleerity code changes, no staging/production deployment, no platform API coupling.

**Operational independence:** Programme B starts immediately upon business approval. It does not wait for Programme A governance or engineering.

---

## Scope

| Application | Purpose |
|-------------|---------|
| **Zoho Books** | Company accounting |
| **Zoho WorkDrive** | Internal document management |
| **Zoho Sign** | B2B, vendor, HR contracts |
| **Zoho Flow** | Internal Zoho automations |
| **Zoho Analytics** | Executive dashboards (manual data until Programme A2) |
| **Zoho SalesIQ** | Marketing website chat |
| **Zoho PageSense** | Marketing A/B testing |
| **Zoho Forms** | Internal/event forms |
| **Zoho Marketing Automation** | Cold prospect drips (optional) |
| **Zoho People** | HR (bundle — optional) |

**Explicitly excluded:** Customer compliance vault, Stripe customer billing, product support tickets, product lead capture.

---

## Prerequisites

| # | Prerequisite | Owner | Effort |
|---|--------------|-------|--------|
| B-P1 | Stage ZA blueprint approved | Leadership | 1 meeting |
| B-P2 | Zoho One subscription active | Finance | Existing |
| B-P3 | Internal data classification policy | DPO | 2–3 days |
| B-P4 | Staff Zoho accounts provisioned | IT/ops | 1 day |
| B-P5 | Cookie policy update (SalesIQ, PageSense) | Legal/marketing | 1 week |
| B-P6 | Stripe → Books export procedure documented | Finance | 2–3 days |

**No engineering prerequisites.**

---

## Phased implementation

### Phase B1 — Finance & legal foundation (Weeks 1–4)

**Objective:** Establish company SoR for money and contracts.

#### Zoho Books

| Item | Detail |
|------|--------|
| Owner | Finance lead / founder |
| Effort | 2–3 weeks (incl. accountant onboarding) |
| Activities | UK company setup, VAT, chart of accounts, bank feed, Stripe payout import procedure |
| Dependencies | B-P2, B-P6 |
| Risks | Mixing customer Stripe with company books — **mitigate with documented export procedure** |
| Business value | **High** |

#### Zoho WorkDrive

| Item | Detail |
|------|--------|
| Owner | Ops / HR lead |
| Effort | 1 week |
| Activities | Folder taxonomy (Legal, HR, Finance, Commercial, Board), permissions, staff training |
| Dependencies | B-P4 |
| Risks | Customer data in WorkDrive — **mitigate with data classification policy** |
| Business value | **High** |

#### Zoho Sign

| Item | Detail |
|------|--------|
| Owner | Legal / commercial lead |
| Effort | 1–2 weeks |
| Activities | NDA, vendor, employment, partnership templates; signer routing; archive to WorkDrive |
| Dependencies | WorkDrive folders |
| Risks | Subscription agreements via Sign — **prohibited**; click-wrap stays Pleerity |
| Business value | **High** |

**Phase B1 exit criteria:**

- [ ] Books: bank connected, first reconciliation complete
- [ ] WorkDrive: all staff have access, folder structure live
- [ ] Sign: 3+ templates approved and used
- [ ] Stripe → Books monthly export runbook executed once

**Combined effort:** ~0.5 FTE (business ops) × 4 weeks — can run in parallel

---

### Phase B2 — Automation & visibility (Weeks 5–8)

#### Zoho Flow

| Item | Detail |
|------|--------|
| Owner | Ops |
| Effort | 3–5 days |
| Activities | Sign completed → WorkDrive; Books invoice reminder; optional Forms → email |
| Dependencies | B1 complete |
| Risks | Flow calling Pleerity APIs — **prohibited** |
| Business value | **Medium** |

#### Zoho Analytics

| Item | Detail |
|------|--------|
| Owner | CEO / finance |
| Effort | 1–2 weeks |
| Activities | Dashboards: cash (Books), MRR (Stripe CSV), lead funnel (manual export until Programme A2) |
| Dependencies | Books live; Stripe export |
| Risks | Stale manual data — acceptable until A2 automates |
| Business value | **High** |

**Phase B2 exit criteria:**

- [ ] 2+ Flow automations running
- [ ] Executive dashboard reviewed monthly by leadership

**Combined effort:** ~0.25 FTE × 4 weeks

---

### Phase B3 — Marketing website tools (Weeks 9–12)

#### Zoho SalesIQ

| Item | Detail |
|------|--------|
| Owner | Marketing |
| Effort | 3–5 days |
| Activities | Embed on public marketing pages; chat routing rules; **not on authenticated portal** |
| Dependencies | B-P5 cookie consent |
| Risks | Portal embed — **prohibited** |
| Business value | **Medium** |

#### Zoho PageSense

| Item | Detail |
|------|--------|
| Owner | Marketing |
| Effort | 3–5 days |
| Activities | Snippet on marketing site; first A/B test on key landing page |
| Dependencies | B-P5 |
| Risks | Consent |
| Business value | **Medium** |

#### Zoho Forms

| Item | Detail |
|------|--------|
| Owner | Marketing / HR |
| Effort | 2–3 days |
| Activities | Event registration, internal feedback forms |
| Dependencies | None |
| Risks | Product lead forms — **prohibited** |
| Business value | **Medium** |

**Phase B3 exit criteria:**

- [ ] SalesIQ live on marketing site
- [ ] PageSense first experiment complete
- [ ] 2+ internal Forms in use

**Combined effort:** ~0.25 FTE (marketing) × 4 weeks

---

### Phase B4 — Optional marketing expansion (Weeks 13–16)

#### Zoho Campaigns (standalone trial)

| Item | Detail |
|------|--------|
| Owner | Marketing |
| Effort | 1–2 weeks |
| Activities | Trial broadcast using manually exported list; compare to Kit |
| Dependencies | Documented Kit gap |
| Note | Full integration is Programme A4; B4 is standalone trial only |
| Business value | **Medium** (if Kit insufficient) |

#### Zoho Marketing Automation

| Item | Detail |
|------|--------|
| Owner | Marketing |
| Effort | 1 week |
| Activities | Cold prospect list only; no product client journeys |
| Dependencies | Marketing strategy |
| Business value | **Low–Medium** |

#### Zoho People (bundle)

| Item | Detail |
|------|--------|
| Owner | HR / founder |
| Effort | 1–2 weeks |
| Activities | Employee records, leave if needed |
| Dependencies | HR process definition |
| Business value | **Medium** (grows with headcount) |

**Phase B4:** Entirely optional — skip if not needed.

---

## Programme B — owners

| Role | Responsibility |
|------|----------------|
| **Programme sponsor** | CEO / COO |
| **Delivery lead** | Finance lead (B1), Marketing lead (B3) |
| **Legal** | Sign templates, data classification |
| **DPO** | Internal PII policy for Zoho |
| **IT** | Staff account provisioning |

**No engineering owner required.**

---

## Dependencies on Programme A

| Item | Relationship |
|------|--------------|
| Analytics automated Pleerity feed | Programme A2 enhances B2 dashboards — **not blocking** |
| CRM in Zoho | Programme A3 — B does not need it |
| Campaigns integration | Programme A4 — B4 can trial manually first |

**Programme B has zero hard dependencies on Programme A.**

---

## Programme B — expected business value

| Phase | Applications | Value | Indicative impact |
|-------|--------------|-------|-------------------|
| B1 | Books, WorkDrive, Sign | **High** | Finance/legal manual work **High** reduction |
| B2 | Flow, Analytics | **High** | Executive visibility **High**; admin tasks **Medium** reduction |
| B3 | SalesIQ, PageSense, Forms | **Medium** | Marketing efficiency **Medium** |
| B4 | Campaigns, MA, People | **Low–Medium** | Conditional on team size and Kit gap |

---

## Programme B — effort estimate

| Phase | Business effort | Calendar | Engineering |
|-------|-----------------|----------|-------------|
| B1 | 0.5 FTE × 4 weeks | Weeks 1–4 | **None** |
| B2 | 0.25 FTE × 4 weeks | Weeks 5–8 | **None** |
| B3 | 0.25 FTE × 4 weeks | Weeks 9–12 | **None** |
| B4 | 0.25 FTE × 4 weeks | Optional | **None** |

**Total:** ~12–16 weeks business-led adoption; **zero engineering FTE**.

---

## Programme B — success metrics

| Metric | Target |
|--------|--------|
| Books bank reconciliation | Monthly, on time |
| Internal docs in WorkDrive | >90% new internal docs filed there |
| B2B contracts via Sign | 100% non-subscription agreements |
| Executive dashboard use | Monthly leadership review |
| Customer data in WorkDrive | **0 incidents** |
| Product leads via Zoho Forms | **0** |
| Portal SalesIQ embed | **0** |

---

## Programme B — risks and mitigations

| Risk | Mitigation |
|------|------------|
| Customer PII in Zoho | Data classification policy; staff training |
| Subscription contracts via Sign | Policy: click-wrap only in Pleerity |
| False "integrated" marketing claims | Legal copy distinguishes internal Zoho use |
| Programme B blocked waiting for engineering | **Explicit independence** — start B1 immediately |

---

## Programme B conclusion

Programme B delivers **the majority of Zoho One subscription value** with **no platform risk and no engineering cost**. Leadership should **authorise B1 immediately** upon Stage ZA approval.

Programme B and Programme A run in parallel with **no operational coupling**.
