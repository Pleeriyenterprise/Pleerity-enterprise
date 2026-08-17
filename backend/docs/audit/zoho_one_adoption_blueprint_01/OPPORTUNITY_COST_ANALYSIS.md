# Stage ZA3 — Opportunity Cost Analysis

**Programme:** STAGE ZA — ZOHO ONE BUSINESS VALUE REALISATION & ADOPTION BLUEPRINT  
**Date:** 2026-07-09

---

## Framework

For each capability domain:

| Decision | Meaning |
|----------|---------|
| **Engineering continues** | Strategic IP — competitive advantage justifies investment |
| **Zoho handles** | Commodity operations — building adds little strategic value |
| **Hybrid** | Pleerity owns product path; Zoho owns adjacent ops path |
| **Defer** | No action until business case proven |

---

## Opportunity cost matrix

| Capability domain | Current state | Strategic value of building | Recommendation | Rationale |
|-------------------|---------------|----------------------------|----------------|-----------|
| **Compliance engine & CEG/CIE** | Production, high maturity | **Very high** | **Engineering continues** | Core product differentiation |
| **Account lifecycle & ILP stack** | Production | **Very high** | **Engineering continues** | Revenue and access governance |
| **Stripe → lifecycle convergence** | Production | **Very high** | **Engineering continues** | Cannot outsource to Zoho |
| **Lead capture & conversion** | Production | **Very high** | **Engineering continues** | Funnel integrity is IP |
| **Product nurture automation** | `lead_automation_service` | **High** | **Engineering continues** | Behaviour tied to product events |
| **Customer support (CVP)** | `support_service`, AI chat | **High** | **Engineering continues** | Product-context support |
| **Compliance document vault** | Vault + evidence authority | **Very high** | **Engineering continues** | Regulatory chain |
| **Immutable compliance reporting** | `reporting_service` | **High** | **Engineering continues** | Customer deliverable |
| **Property maintenance workflow** | Work orders, contractor portal | **High** | **Engineering continues** | Product feature for landlords |
| **Subscription click-wrap** | `agreement_acceptance_service` | **Medium–High** | **Engineering continues** | Integrated checkout |
| **Newsletter (Kit)** | `kit_integration` — external | **Low** (already outsourced) | **Zoho handles** (if Kit replaced) | Commodity email list |
| **Pleerity Ltd general ledger** | Not built | **None** | **Zoho handles** | Books — pure commodity |
| **VAT / tax reporting (company)** | Not built | **None** | **Zoho handles** | Finance regulatory tooling |
| **Bank reconciliation (company)** | Not built | **None** | **Zoho handles** | Books native feature |
| **Internal team documents** | Not built | **None** | **Zoho handles** | WorkDrive |
| **B2B / vendor / HR contracts** | Not built | **None** | **Zoho handles** | Sign |
| **Executive P&L dashboards** | Partial admin ops views | **Low** | **Zoho handles** | Analytics |
| **Cross-app executive BI** | Not built | **Low** | **Zoho handles** | Analytics + exports |
| **Internal approval workflows** | Not built | **Low** | **Zoho handles** | Flow + Sign |
| **HR administration** | Not built | **None** | **Zoho handles** | Zoho People (bundle) |
| **Internal collaboration (files)** | Not built | **None** | **Zoho handles** | WorkDrive |
| **Internal Zoho app automation** | Not built | **Negative** (in platform) | **Zoho handles** | Flow (internal) |
| **Marketing site A/B testing** | Not built | **Low** | **Zoho handles** | PageSense |
| **Marketing site live chat** | Not built | **Low** | **Zoho handles** | SalesIQ |
| **Internal / event forms** | Per-form engineering | **Low** | **Zoho handles** | Forms (internal) |
| **Sales CRM UI (product leads)** | `AdminLeadsPage` mature | **Medium** | **Hybrid** | Keep SoR; optional Zoho UI export |
| **Promotional email campaigns** | Kit integrated | **Low** | **Defer** | Campaigns only if Kit gap proven |
| **Cold prospect MA journeys** | Not built | **Low** | **Zoho handles** | MA — marketing-only, no platform tie |
| **Platform ↔ Zoho sync layer** | Not built | **Medium** (if Programme A proceeds) | **Engineering continues** (minimal) | Thin governed adapters only |

---

## Engineering effort — stop building

These capabilities would consume engineering capacity with **negligible competitive return**:

1. **Internal accounting module** — VAT, GL, AP/AR, bank reconciliation  
2. **Internal document management system** — team folders, HR files  
3. **B2B e-sign engine** — multi-party legal workflows  
4. **Executive BI platform** — dashboard builder, data blending  
5. **Internal iPaaS** — Zoho-to-Zoho and finance automations  
6. **Marketing A/B testing framework** — experiments on public site  
7. **Generic form builder** — internal surveys and events  
8. **Second customer support stack** — Desk for CVP tickets  
9. **Generic marketing automation platform** — product nurture replacement  
10. **Salesforce-class CRM** — as alternative to existing Pleerity CRM SoR  

**Estimated opportunity cost if pursued:** Multiple engineer-months per year diverted from compliance, lifecycle, and evidence IP.

---

## Engineering effort — continue investing

| Priority | Domain | Why |
|----------|--------|-----|
| **P0** | Compliance engine & evidence authority | Defensible moat |
| **P0** | Account lifecycle & capability enforcement | Revenue protection |
| **P0** | Stripe webhook convergence | Billing truth |
| **P1** | Lead conversion governance | Commercial funnel integrity |
| **P1** | Product nurture automation | Conversion and retention |
| **P1** | Customer support with product context | Retention and trust |
| **P2** | Property maintenance / contractor ops | Product expansion |
| **P2** | Compliance reporting artifacts | Customer obligation |
| **P3** | Governed integration service | **Only if Programme A approved** — thin layer, not feature rebuild |

---

## Hybrid domains — split ownership

| Domain | Pleerity owns | Zoho owns |
|--------|---------------|-----------|
| **Revenue** | Stripe customer billing, lifecycle | Books company recognition |
| **Documents** | Customer compliance vault | Internal company files |
| **Contracts** | Subscription click-wrap | B2B/vendor/HR signing |
| **Reporting** | Customer compliance PDFs | Executive BI dashboards |
| **CRM** | Lead SoR, conversion | Optional sales activity UI |
| **Email** | Lifecycle/operational (orchestrator) | Promotional broadcast (optional) |
| **Chat** | Portal product support | Marketing site pre-sales |
| **Forms** | Revenue-impacting capture | Internal/event forms |

---

## Decision tree (for new capability requests)

```
Is this customer-facing and tied to compliance, billing, or lifecycle?
├── YES → Engineering builds (or extends existing IP)
└── NO → Is it Pleerity Ltd internal operations?
    ├── YES → Zoho handles (Programme B)
    └── NO → Is it executive/marketing tooling on public site?
        ├── YES → Zoho handles (Programme B)
        └── NO → Does it require Pleerity data authority?
            ├── YES → Thin integration only (Programme A)
            └── NO → Do not build; re-evaluate need
```

---

## Stage ZA3 conclusion

**Zoho should replace commodity operational processes** that Pleerity has never built and has no strategic reason to build.

**Pleerity should continue investing** in compliance, lifecycle, evidence, conversion, and product-integrated customer operations.

**The highest opportunity cost mistake** would be diverting engineering to internal finance, DMS, or BI while under-investing in compliance and lifecycle IP.
