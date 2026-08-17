# Stage ZA2 — Capability Comparison Matrix

**Programme:** STAGE ZA — ZOHO ONE BUSINESS VALUE REALISATION & ADOPTION BLUEPRINT  
**Date:** 2026-07-09  
**Prerequisite:** Stage Z audit (`zoho_one_integration_governance_01/`)

---

## Comparison key

| Verdict | Meaning |
|---------|---------|
| **Pleerity stronger** | Platform capability is mature, governed, and strategically essential |
| **Zoho stronger** | Zoho provides greater operational maturity for this use case |
| **Equivalent** | Both could serve; choice is operational preference not capability gap |
| **Different problems** | Capabilities do not genuinely overlap — comparing unlike domains |

**Important:** Maintenance `invoices`, Stripe billing, and compliance vault are **not** compared to Books/WorkDrive — they solve different problems.

---

## Master comparison table

| Application | Domain compared | Pleerity capability | Zoho capability | Verdict | Recommendation |
|-------------|-----------------|---------------------|-----------------|---------|----------------|
| **Zoho CRM** | Product lead CRM | `lead_service.py`, pipeline, scoring, nurture hooks, conversion governance, `AdminLeadsPage` | Generic CRM, call logging, mobile app, sales dashboards | **Pleerity stronger** (product funnel) | Platform SoR stays Pleerity; Zoho optional for sales UI on export |
| **Zoho CRM** | Partnership / outbound activity notes | Admin enquiry pages exist; no dedicated call CRM | Activity timeline, tasks, mobile | **Zoho stronger** (sales UX) | Optional replica — different problem than product SoR |
| **Zoho Books** | Pleerity Ltd accounting | **Not implemented** | GL, VAT, AP/AR, bank rec, reports | **Zoho stronger** | **Adopt Books** — different problem from Stripe |
| **Zoho Books** | Customer subscriptions | Stripe + `client_billing` + lifecycle | Subscription billing (generic) | **Pleerity stronger** | Stripe remains; export to Books only |
| **Zoho WorkDrive** | Customer compliance documents | Vault + `requirement_evidence_authority` | Generic cloud storage | **Pleerity stronger** (compliance chain) | Platform vault stays |
| **Zoho WorkDrive** | Internal company files | **Not implemented** | Team folders, permissions, versioning | **Zoho stronger** | **Adopt WorkDrive** — different problem |
| **Zoho Sign** | Subscription agreements | Click-wrap + `agreement_acceptance_service` | E-sign platform | **Pleerity stronger** (checkout integration) | Keep click-wrap |
| **Zoho Sign** | B2B / vendor / HR contracts | **Not implemented** | Multi-party sign, templates, audit | **Zoho stronger** | **Adopt Sign** (internal) |
| **Zoho Analytics** | Compliance / customer PDF reports | `reporting_service.py`, immutable artifacts | Generic BI | **Pleerity stronger** (regulated deliverables) | Keep platform reporting |
| **Zoho Analytics** | Executive cross-system BI | Admin ops dashboards (product-focused) | Dashboard builder, blending, scheduling | **Zoho stronger** | **Adopt Analytics** — different problem |
| **Zoho Flow** | Platform integration orchestration | Job runner, webhooks, governed services | iPaaS | **Pleerity stronger** (auditability) | Pleerity integration service if needed |
| **Zoho Flow** | Internal Zoho-to-Zoho automation | **Not implemented** | Connect Books/Sign/WorkDrive | **Zoho stronger** | **Adopt Flow** (internal only) |
| **Zoho Campaigns** | Product lifecycle email | `notification_orchestrator` + Postmark | Email campaigns | **Pleerity stronger** (gated comms) | Keep orchestrator |
| **Zoho Campaigns** | Promotional broadcast | Kit (`kit_integration.py`) + admin newsletter UI | Campaign builder, lists | **Equivalent** | Prove Kit gap; optional Campaigns |
| **Zoho Marketing Automation** | Product behavioural nurture | `lead_automation_service.py`, job triggers | Journey builder | **Pleerity stronger** (lifecycle-tied) | Keep platform nurture |
| **Zoho Marketing Automation** | Cold prospect drips | Not a focus in platform | MA journeys | **Zoho stronger** | Internal marketing only |
| **Zoho SalesIQ** | Authenticated portal support | `support_chatbot.py`, `SupportChatWidget` | Live chat | **Pleerity stronger** | Keep portal chat |
| **Zoho SalesIQ** | Marketing website chat | **Not implemented** | Visitor chat, bots | **Zoho stronger** | Adopt marketing site only |
| **Zoho Forms** | Revenue lead capture | `routes/leads.py`, attribution, dedup | Form builder + webhook | **Pleerity stronger** (governance) | Keep product forms |
| **Zoho Forms** | Internal / event forms | Engineering ticket per form | Self-serve form builder | **Zoho stronger** | Adopt internal forms |
| **Zoho PageSense** | Marketing conversion testing | **Not implemented** | A/B tests, heatmaps | **Zoho stronger** | Adopt after consent review |

---

## Strategic advantage — remain platform-owned

| Capability | Why Pleerity must keep it |
|------------|---------------------------|
| Lead → client conversion | Governed provisioning chain; Zoho cannot enforce ILP rules |
| Compliance evidence authority | Regulatory chain of custody; generic DMS insufficient |
| Subscription lifecycle | Stripe webhooks → capabilities → route enforcement |
| Lifecycle-gated notifications | Suppression rules tied to billing and legal state |
| Product-integrated support | Ticket context includes client, property, compliance state |
| Immutable compliance reporting | Customer deliverable with audit provenance |

---

## Operational maturity — Zoho provides greater value

| Capability | Why Zoho is stronger |
|------------|---------------------|
| UK SME accounting (VAT, GL) | Mature finance product; Pleerity has zero implementation |
| Internal team document management | Enterprise DMS features without build cost |
| B2B e-sign workflow | Legal-grade signing; Pleerity only has click-wrap |
| Executive BI blending | Cross-app dashboards; admin UI is product-ops focused |
| Internal workflow between back-office apps | Flow connects Zoho suite natively |
| Marketing site A/B testing | Purpose-built; not in platform roadmap |
| Marketing site live chat | Isolated from product support stack |

---

## Non-overlapping pairs (do not treat as duplication)

| Pleerity | Zoho | Relationship |
|----------|------|--------------|
| Stripe customer billing | Zoho Books | Revenue **export** for company accounts — not replacement |
| Maintenance work-order invoices | Zoho Books | **Product feature** for landlords — not Pleerity Ltd AP/AR |
| Compliance document vault | WorkDrive | Different data classes — customer vs internal |
| Click-wrap subscription | Zoho Sign | Different contract types |
| Product nurture automation | Zoho MA | Product vs cold marketing audiences |
| Portal support chat | SalesIQ | Authenticated product vs public marketing site |

---

## Stage ZA2 conclusion

Genuine overlap exists only where Stage Z already ruled: **product CRM, product nurture, portal support, and product lead forms** — Pleerity wins on strategic grounds.

Zoho wins on **commodity back-office and marketing-site tooling** where Pleerity has no implementation and no competitive reason to build.
