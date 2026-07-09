# Executive Adoption Summary — Stage ZA

**Programme:** STAGE ZA — ZOHO ONE BUSINESS VALUE REALISATION & ADOPTION BLUEPRINT  
**Date:** 2026-07-09  
**Status:** **COMPLETE — READY FOR EXECUTIVE ADOPTION APPROVAL**  
**Builds on:** Stage Z audit (`zoho_one_integration_governance_01/`) — architecture conclusions preserved

---

## One-page decision

Pleerity Enterprise should realise its Zoho One investment through **two independent programmes**:

| Programme | What | Who | When | Engineering |
|-----------|------|-----|------|-------------|
| **B — Business Operations** | Books, WorkDrive, Sign, Flow, marketing tools | Finance, legal, marketing, ops | **Start immediately** | **None** |
| **A — Platform Integration** | Analytics feed, optional CRM/Campaigns | Engineering + commercial | After governance | **Yes — minimal scope** |

**Pleerity remains the customer platform and system of record.** Stripe remains payment authority. Zoho replaces **commodity internal operations**, not product IP.

---

## Strategic principles (unchanged from Stage Z)

1. Pleerity is authoritative for all customer-facing operational data.  
2. Engineering invests in compliance, lifecycle, evidence, and conversion — not internal accounting or DMS.  
3. Zoho One subscription value is realised **primarily through Programme B**.  
4. Programme A is **optional and minimal** — Analytics read feed first; CRM/Campaigns only with proven demand.  
5. Programmes A and B are **operationally independent**.

---

## Business value at a glance

| Application | Business value | Programme | Priority |
|-------------|----------------|-----------|----------|
| Zoho Books | **High** | B | **P1 — now** |
| Zoho WorkDrive | **High** | B | **P1 — now** |
| Zoho Sign | **High** | B | **P1 — now** |
| Zoho Analytics | **High** | B + A (feed) | **P2** |
| Zoho Flow | **Medium** | B | **P2** |
| Zoho SalesIQ | **Medium** | B | **P3** |
| Zoho PageSense | **Medium** | B | **P3** |
| Zoho Forms | **Medium** | B | **P3** |
| Zoho CRM | **Medium** (conditional) | A | **P3 — optional** |
| Zoho Campaigns | **Medium** (conditional) | A | **P3 — optional** |
| Zoho Marketing Automation | **Low–Medium** | B (cold only) | **P4 — optional** |

---

## What engineering should NOT build

- Internal general ledger / VAT  
- Internal document management  
- B2B e-sign platform  
- Executive BI suite  
- Marketing A/B testing framework  
- Second customer CRM or support stack  

**Opportunity cost:** Building these diverts capacity from compliance and lifecycle IP.

---

## What engineering should continue building

- Compliance engine, evidence authority, CEG/CIE  
- Account lifecycle, capability enforcement, Stripe convergence  
- Lead conversion governance, product nurture  
- Product-integrated customer support  
- Compliance document vault and immutable reporting  
- Thin governed integration service (**only if Programme A proceeds**)

---

## Programme B — authorise now

**Weeks 1–4 (P1):**

- **Books** — Pleerity Ltd accounting; Stripe payout export procedure  
- **WorkDrive** — internal docs; folder taxonomy and permissions  
- **Sign** — NDAs, vendor, partnership, employment templates  

**Owners:** Finance lead, legal, ops  
**Prerequisites:** Zoho One subscription, internal data classification policy  
**Engineering:** None  
**Expected value:** **High** — finance, legal, and staff productivity

**Leadership action:** Approve Programme B Phase B1 start date.

---

## Programme A — govern first, integrate minimally

**Only if executive approves platform track:**

| Phase | Integration | Value | Condition |
|-------|-------------|-------|-----------|
| A0 | Governance policies + DPIA | Risk reduction | Mandatory |
| A1 | Integration service foundation | Enabler | Mandatory if any integration |
| A2 | Analytics read-only feed | **High** | Recommended first integration |
| A3 | CRM one-way export | Medium | Sales demand in writing |
| A4 | Campaigns audience export | Medium | Kit gap proven |

**Engineering effort:** 6–18 FTE-weeks depending on scope  
**Default minimum:** A0 + A1 + A2 only  

**Leadership action:** Approve Programme A scope separately from Programme B.

---

## Capability verdict summary

| Domain | Winner | Action |
|--------|--------|--------|
| Product CRM & conversion | **Pleerity** | Keep SoR |
| Customer billing | **Stripe / Pleerity** | Keep; export to Books |
| Compliance documents | **Pleerity** | Keep vault |
| Product support | **Pleerity** | Keep |
| Company accounting | **Zoho Books** | Adopt |
| Internal files | **Zoho WorkDrive** | Adopt |
| B2B contracts | **Zoho Sign** | Adopt |
| Executive BI | **Zoho Analytics** | Adopt |
| Marketing site chat/tests | **Zoho SalesIQ / PageSense** | Adopt |

---

## Critical boundaries

| Rule | Enforcement |
|------|-------------|
| No customer compliance docs in WorkDrive | Data classification policy |
| No customer subscriptions in Books | Finance procedure |
| No product leads from Zoho Forms/CRM | Marketing/sales policy |
| No SalesIQ on authenticated portal | Marketing deployment checklist |
| No Zoho Flow writes to Pleerity production | Integration standards |
| Correct public copy | Legal — internal Zoho ≠ customer integration |

---

## Deliverables index

| Document | Stage |
|----------|-------|
| `BUSINESS_VALUE_REALISATION_REVIEW.md` | ZA1 |
| `CAPABILITY_COMPARISON_MATRIX.md` | ZA2 |
| `OPPORTUNITY_COST_ANALYSIS.md` | ZA3 |
| `ZOHO_ONE_ADOPTION_BLUEPRINT.md` | ZA4 |
| `PROGRAMME_A_PLATFORM_IMPLEMENTATION_PLAN.md` | ZA5 |
| `PROGRAMME_B_BUSINESS_OPERATIONS_PLAN.md` | ZA5 |
| `EXECUTIVE_ADOPTION_SUMMARY.md` | Executive |

**Prior audit reference:** `../zoho_one_integration_governance_01/`

---

## Approval

| Decision | Recommendation |
|----------|----------------|
| Approve Stage ZA adoption blueprint | **Yes** |
| Authorise Programme B Phase B1 | **Yes — immediate** |
| Authorise Programme A | **Conditional — scope A0–A2 minimum** |
| Authorise CRM/Campaigns integration | **Only with written commercial demand** |

| Role | Name | Date | Signature |
|------|------|------|-----------|
| CEO / Programme sponsor | | | |
| Finance lead | | | |
| Engineering lead | | | |
| DPO | | | |
| Commercial / marketing lead | | | |

---

## Final statement

Stage ZA converts architectural approval into an **executable adoption strategy**. Programme B realises Zoho One value **immediately without engineering**. Programme A adds **optional, governed platform connectivity** where business value exceeds integration cost.

**No implementation of Programme A is permitted until governance artefacts are published. Programme B may begin upon executive sign-off of this document.**

**Stage ZA status: COMPLETE**
