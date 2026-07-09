# Stage Z Supplement — Internal Business Operations Review

**Programme:** STAGE Z — ZOHO ONE INTEGRATION GOVERNANCE & ARCHITECTURE AUDIT  
**Perspective:** Business operations (Pleerity Enterprise Ltd), not customer platform architecture  
**Date:** 2026-07-09  
**Prerequisite:** Stage Z platform audit (`EXECUTIVE_RECOMMENDATION.md`)

---

## Executive summary

The Stage Z platform audit correctly protected Pleerity as the **customer system of record**. This supplement answers a different question:

> **Where should Pleerity Enterprise Ltd adopt Zoho One as its internal business operating system — with no connection to the customer platform?**

**Answer:** Zoho One has **high operational value** for Pleerity Ltd **back-office and GTM support functions**, even where the same Zoho apps must **not** integrate with the CVP platform. Engineering effort should remain concentrated on compliance, lifecycle, evidence authority, and subscription governance — Pleerity's defensible IP.

**Two-layer model (mandatory separation):**

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER A — Pleerity Platform (Product IP)                    │
│  Customer SoR · Compliance · Billing · Support · Documents   │
│  Engineering builds here — competitive advantage             │
└─────────────────────────────────────────────────────────────┘
                              ╳ no authoritative data coupling
┌─────────────────────────────────────────────────────────────┐
│  LAYER B — Pleerity Ltd Business OS (Commodity operations)   │
│  Finance · Internal docs · B2B contracts · Exec BI · GTM     │
│  Zoho One adopts here — do not rebuild in engineering        │
└─────────────────────────────────────────────────────────────┘
```

**Strategic principle:** Do not rebuild commodity business software inside the product unless it creates **genuine competitive advantage** for customers.

---

## Evaluation framework

Each Zoho application is assessed across four dimensions:

| Dimension | Question |
|-----------|----------|
| **Customer-facing platform** | Does this serve CVP customers through Pleerity? |
| **Internal business operations** | Does this run Pleerity Ltd as a company? |
| **Engineering value** | Does building this in Pleerity improve product defensibility? |
| **Operational value** | Does adopting Zoho improve how the business runs day-to-day? |

**Rating scale for operational value:** High / Medium / Low / Negative  
**Adoption stance:** **Adopt (internal)** | **Keep (platform)** | **Hybrid** | **Do not adopt**

---

## Pleerity intellectual property vs commodity functions

### Verified platform IP — retain engineering investment

| Domain | Evidence | Why it is IP |
|--------|----------|--------------|
| Compliance engine & evidence authority | `requirement_evidence_authority.py`, CEG/CIE | Core product differentiation |
| Account lifecycle & capability gating | ILP stack, `account_lifecycle_state_resolver.py` | Revenue + access governance |
| Stripe → lifecycle convergence | `stripe_webhook_service.py`, `client_billing` | Subscription truth chain |
| Lead → client conversion governance | `lead_service.py`, conversion tests | Funnel integrity |
| Customer document vault | `routes/documents.py`, compliance vault | Regulatory evidence chain |
| Product-integrated support | `support_service.py`, AI chatbot, KB | Customer experience tied to product context |
| Property maintenance workflow | `invoice_service.py`, work orders, contractor portal | **Product feature** for landlords — not company accounting |
| Immutable compliance reporting | `reporting_service.py` | Customer deliverable |

### Commodity functions — do not expand engineering

| Function | Current state | Recommendation |
|----------|---------------|----------------|
| Pleerity Ltd general ledger / VAT / AP-AR | **Not in codebase** | **Adopt Zoho Books** |
| Internal company file storage | Local vault is **customer** compliance | **Adopt Zoho WorkDrive** for internal docs |
| Vendor / employment / partner contracts | Click-wrap only for subscriptions | **Adopt Zoho Sign** for B2B |
| Executive P&L / cross-system BI | Admin dashboards are **product ops** | **Adopt Zoho Analytics** |
| Internal Zoho app orchestration | N/A | **Adopt Zoho Flow** (internal only) |
| Marketing site A/B testing | Not implemented | **Adopt PageSense** (marketing site only) |
| Cold-audience email broadcast | Kit integration exists | **Evaluate Campaigns** vs Kit — do not build |

### Common misclassification (avoid)

| Item | Often confused as | Actually is |
|------|-------------------|-------------|
| Maintenance `invoices` collection | Company accounting | **Product workflow** — contractor invoices to clients |
| Stripe subscription invoices | Pleerity Ltd revenue recognition | **Customer billing** — export to Books, don't rebuild |
| `AdminLeadsPage` | Internal sales CRM | **Platform CRM** — product lead SoR |
| `AdminReportingPage` | Executive BI | **Product/compliance reporting** — customer deliverables |
| Newsletter + Kit | Marketing platform | **Correct pattern** — external commodity tool |

---

## Application-by-application assessment

### Customer & Sales

#### Zoho CRM

| Dimension | Assessment |
|-----------|------------|
| Customer-facing platform | **In scope for product** — leads, pipeline, conversion. Pleerity is SoR (`lead_service.py`). **Do not replace.** |
| Internal business operations | Sales call logging, partnership tracking, outbound activity notes for **non-product** relationships |
| Engineering value | **High** for product leads — conversion governance is IP. **None** for internal note-taking |
| Operational value | **Medium** for sales team UI preference on **exported** product leads only |

| Stance | Detail |
|--------|--------|
| **Platform** | **Keep** — authoritative CRM |
| **Internal** | **Hybrid (optional)** — read replica for sales workspace; **not** a second lead database |

**Do not rebuild:** Salesforce-style CRM for internal use.  
**Do not integrate:** Two-way sync or Zoho-native lead creation for product funnel.

---

#### Zoho Campaigns

| Dimension | Assessment |
|-----------|------------|
| Customer-facing platform | Promotional email to prospects/newsletter — touches `newsletter_subscribers` |
| Internal business operations | Marketing team broadcast tool |
| Engineering value | **Low** — Kit already integrated (`kit_integration.py`) |
| Operational value | **Medium** — if marketing team needs Zoho-native campaigns beyond Kit |

| Stance | Detail |
|--------|--------|
| **Platform** | **Keep** lead/newsletter SoR in Pleerity; export audiences only |
| **Internal** | **Adopt (conditional)** — replace or supplement Kit if marketing ops prefers Zoho; **do not build** email campaign builder |

**Do not rebuild:** Email marketing platform, template editor, unsubscribe management at scale.

---

#### Zoho Marketing Automation

| Dimension | Assessment |
|-----------|------------|
| Customer-facing platform | Product-led nurture via `lead_automation_service.py` |
| Internal business operations | Cold-prospect drip campaigns |
| Engineering value | **High** for behavioural triggers tied to lifecycle/compliance events |
| Operational value | **Low–Medium** for pure marketing drips unrelated to product |

| Stance | Detail |
|--------|--------|
| **Platform** | **Keep** — product nurture is IP |
| **Internal** | **Adopt (conditional)** — for **marketing-only** journeys on exported cold lists; never for client/lifecycle comms |

**Do not rebuild:** Generic MA platform.  
**Do not duplicate:** Product nurture sequences already in `job_runner.py`.

---

#### Zoho SalesIQ

| Dimension | Assessment |
|-----------|------------|
| Customer-facing platform | Conflicts `SupportChatWidget.js` on authenticated portal |
| Internal business operations | Marketing website live chat, visitor tracking |
| Engineering value | **Negative** on portal — duplicates product support |
| Operational value | **Medium** on **public marketing site only** |

| Stance | Detail |
|--------|--------|
| **Platform** | **Keep** — product support chat |
| **Internal** | **Adopt (marketing site only)** — sales chat on `pleerityenterprise.co.uk`; no portal embed |

**Do not rebuild:** Live chat for marketing site if SalesIQ adopted.

---

#### Zoho Forms

| Dimension | Assessment |
|-----------|------------|
| Customer-facing platform | Product lead capture via `routes/leads.py` — governed |
| Internal business operations | Event registration, internal surveys, partner intake |
| Engineering value | **High** for product forms (conversion attribution) |
| Operational value | **Medium** for ad-hoc internal forms |

| Stance | Detail |
|--------|--------|
| **Platform** | **Keep** — all revenue-impacting forms |
| **Internal** | **Adopt** — internal/event forms with no platform coupling |

**Do not rebuild:** Form builder for internal ops.  
**Do not use:** Zoho Forms for production lead capture.

---

#### Zoho Analytics

| Dimension | Assessment |
|-----------|------------|
| Customer-facing platform | Supplements `AdminExecutiveOverviewPage` — not customer-facing |
| Internal business operations | Exec dashboards: MRR, funnel, ops KPIs, finance views |
| Engineering value | **Low** — BI is commodity |
| Operational value | **High** — leadership reporting across Stripe exports + ops |

| Stance | Detail |
|--------|--------|
| **Platform** | **Keep** product ops dashboards for engineering/support |
| **Internal** | **Adopt** — executive BI; read-only feeds |

**Do not rebuild:** Executive BI suite, cross-app dashboard builder.

---

#### Zoho PageSense

| Dimension | Assessment |
|-----------|------------|
| Customer-facing platform | Not on authenticated portal |
| Internal business operations | Marketing conversion optimisation |
| Engineering value | **None** |
| Operational value | **Medium** — A/B testing for marketing site |

| Stance | Detail |
|--------|--------|
| **Platform** | **Not applicable** |
| **Internal** | **Adopt** — after cookie consent update; marketing site only |

**Do not rebuild:** A/B testing platform.

---

### Customer Service

#### Zoho Desk

| Dimension | Assessment |
|-----------|------------|
| Customer-facing platform | Mature `support_service.py`, tickets, KB, AI chat — **14+ tests** |
| Internal business operations | IT helpdesk, facilities, internal staff requests |
| Engineering value | **High** — product-context support is IP |
| Operational value | **Medium** for **internal** IT tickets only |

| Stance | Detail |
|--------|--------|
| **Platform** | **Keep** — CVP customer support |
| **Internal** | **Adopt (optional)** — separate Desk org/department for **staff IT** only |

**Do not rebuild:** Customer ticketing.  
**Do not integrate:** CVP customer tickets into Desk.

---

### Documents & Agreements

#### Zoho WorkDrive

| Dimension | Assessment |
|-----------|------------|
| Customer-facing platform | Compliance vault — `routes/documents.py` |
| Internal business operations | Company policies, HR files, board docs, vendor files |
| Engineering value | **High** for compliance evidence chain |
| Operational value | **High** for internal collaboration |

| Stance | Detail |
|--------|--------|
| **Platform** | **Keep** — customer compliance documents |
| **Internal** | **Adopt** — Pleerity Ltd team files; zero customer data |

**Do not rebuild:** Internal DMS, team folders, version control for company docs.

---

#### Zoho Sign

| Dimension | Assessment |
|-----------|------------|
| Customer-facing platform | Subscription click-wrap via `agreement_acceptance_service.py` |
| Internal business operations | Vendor contracts, NDAs, employment, partnership agreements |
| Engineering value | **Medium** for subscription agreements (already solved) |
| Operational value | **High** for B2B legal workflow |

| Stance | Detail |
|--------|--------|
| **Platform** | **Keep** — subscription click-wrap |
| **Internal** | **Adopt** — B2B/HR/vendor signing; manual filing to WorkDrive |

**Do not rebuild:** E-sign platform for internal contracts.

---

### Finance

#### Zoho Books

| Dimension | Assessment |
|-----------|------------|
| Customer-facing platform | Stripe + `client_billing` — subscription SoR |
| Internal business operations | **Pleerity Ltd** accounting: revenue recognition, VAT, expenses, payroll journals |
| Engineering value | **Negative** — accounting in product adds compliance burden |
| Operational value | **High** — finance team standard tool |

| Stance | Detail |
|--------|--------|
| **Platform** | **Keep** — Stripe authoritative; never Books for customer subscriptions |
| **Internal** | **Adopt** — company books; Stripe payout/revenue **export** (manual or scheduled CSV/API) |

**Do not rebuild:** General ledger, VAT returns, expense management, supplier invoicing.  
**Clarification:** Platform `invoices` collection is **maintenance work-order billing between clients and contractors** — a product feature. It is **not** a substitute for Books and should **not** be extended into company accounting.

---

### Integration

#### Zoho Flow

| Dimension | Assessment |
|-----------|------------|
| Customer-facing platform | Must not orchestrate authoritative platform paths |
| Internal business operations | Connect Books ↔ Sign ↔ WorkDrive ↔ CRM (internal) |
| Engineering value | **Negative** as platform orchestrator — unauditable |
| Operational value | **High** for internal Zoho-to-Zoho automation |

| Stance | Detail |
|--------|--------|
| **Platform** | **Do not adopt** as integration layer |
| **Internal** | **Adopt** — finance/legal/marketing internal workflows only |

**Do not rebuild:** iPaaS for internal back-office.  
**Build in Pleerity:** Governed integration service **only** if platform sync is ever approved (Stage Z Phase 3).

---

## Summary decision matrix

| Application | Platform stance | Internal ops stance | Engineering: build? |
|-------------|-----------------|---------------------|---------------------|
| **Zoho CRM** | Keep (SoR) | Hybrid — optional sales UI on export | **No** (internal CRM) |
| **Zoho Campaigns** | Keep SoR; export audiences | Adopt if Kit insufficient | **No** |
| **Zoho Marketing Automation** | Keep product nurture | Adopt for cold marketing only | **No** |
| **Zoho SalesIQ** | Keep portal chat | Adopt — marketing site only | **No** |
| **Zoho Forms** | Keep product forms | Adopt — internal forms | **No** |
| **Zoho Analytics** | Keep product ops dashboards | **Adopt** | **No** |
| **Zoho PageSense** | N/A | **Adopt** (with consent) | **No** |
| **Zoho Desk** | Keep customer support | Adopt — internal IT optional | **No** (customer tickets) |
| **Zoho WorkDrive** | Keep compliance vault | **Adopt** | **No** |
| **Zoho Sign** | Keep click-wrap | **Adopt** | **No** (B2B sign) |
| **Zoho Books** | Keep Stripe | **Adopt** | **No** |
| **Zoho Flow** | Do not adopt | **Adopt** | **No** (internal iPaaS) |

---

## Zoho One bundle adjacencies (out of detailed scope)

Zoho One includes applications not in the Stage Z list. Brief guidance:

| App | Internal ops value | Recommendation |
|-----|-------------------|----------------|
| **Zoho People** (HR) | High — leave, attendance, HR files | **Adopt** — no Pleerity equivalent; do not build HR module |
| **Zoho Projects** | Medium — internal project tracking | **Adopt** — engineering roadmap stays in dev tools; Projects for business/ops initiatives |
| **Zoho Mail / Cliq** | Medium — company comms | **Adopt** if not already on Microsoft/Google — out of engineering scope |

These require **no platform integration**.

---

## Engineering effort allocation guidance

### Continue investing (IP)

- Compliance engine, evidence graph, CEG/CIE
- Account lifecycle, capability enforcement, reactivation authority
- Stripe webhook convergence and billing mirror
- Lead conversion governance and product nurture automation
- Customer support with product context
- Compliance document vault and immutable reporting
- Property maintenance and contractor workflows (product feature)

### Stop / avoid building (commodity)

- Company general ledger or VAT engine
- Internal team document management
- B2B e-sign workflow engine
- Executive cross-app BI platform
- Marketing site A/B testing framework
- Internal form builder for staff surveys
- iPaaS for back-office Zoho apps
- Second customer support stack

### Correct existing pattern (already good)

- **Kit for newsletter** — external commodity; keep one-way sync pattern
- **Stripe for payments** — external SoR; keep mirror in Pleerity for lifecycle only

---

## Internal adoption boundary rules

1. **No customer PII in Zoho** without DPIA and purpose limitation.
2. **Separate Zoho org/spaces** — internal WorkDrive ≠ customer vault.
3. **Stripe → Books** is a **finance export**, not a platform integration.
4. **Product leads never originate in Zoho CRM.**
5. **CVP customer tickets never in Zoho Desk.**
6. **Zoho Flow must not write to Pleerity production APIs** without Stage Z governance programme.
7. **Marketing/legal copy** must distinguish "Pleerity uses Zoho internally" from "customer data is in Zoho".

---

## Recommended internal adoption sequence

| Priority | Application | Effort | Platform coupling |
|----------|-------------|--------|-------------------|
| **P1** | Zoho Books | Finance onboarding | Stripe CSV/export only |
| **P1** | Zoho WorkDrive | Team folder structure | None |
| **P1** | Zoho Sign | Legal template setup | None |
| **P2** | Zoho Analytics | Dashboard build | Read-only exports |
| **P2** | Zoho Flow | Internal automations | None |
| **P3** | PageSense, SalesIQ | Marketing site | Consent policy update |
| **P3** | Campaigns / MA | If Kit/nurture gap proven | Suppression export only |
| **Optional** | Desk (internal IT) | Separate department | None |
| **Optional** | CRM replica | Only if sales demands UI | One-way export (Stage Z Phase 3) |

**P1 items deliver the majority of Zoho One subscription value with zero platform risk.**

---

## Revised executive position

| Layer | Verdict |
|-------|---------|
| **Customer platform** | Minimal Zoho integration; Pleerity remains SoR (unchanged from Stage Z) |
| **Pleerity Ltd business OS** | **Adopt Zoho One aggressively** for finance, internal docs, B2B sign, exec BI, internal workflow |
| **Engineering focus** | Product IP only — do not commoditise the codebase |

**This is not a contradiction.** The platform audit said "do not integrate Zoho into the product." This supplement says "do adopt Zoho for running the company." The boundary is **data and authority separation**.

---

## Approval addition

Before approval, confirm:

- [ ] Finance lead accepts Zoho Books as Pleerity Ltd SoR (not platform)
- [ ] Legal accepts Zoho Sign for B2B (subscription click-wrap unchanged)
- [ ] Marketing accepts Kit vs Campaigns decision documented
- [ ] Engineering confirms no roadmap items for commodity back-office features
- [ ] DPO reviews internal Zoho PII policy (employee + prospect export)

---

**Supplement status: COMPLETE — FOR inclusion with Stage Z audit pack**
