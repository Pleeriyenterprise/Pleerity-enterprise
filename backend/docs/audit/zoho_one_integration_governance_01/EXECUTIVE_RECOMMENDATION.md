# Executive Recommendation — Zoho One Integration

**Programme:** STAGE Z — ZOHO ONE INTEGRATION GOVERNANCE & ARCHITECTURE AUDIT  
**Date:** 2026-07-09  
**Verdict:** **PROCEED TO GOVERNANCE ONLY — NO IMPLEMENTATION UNTIL APPROVED**

---

## Summary

Pleerity is a **mature, production-governed platform** with first-party CRM, support, billing, compliance, documents, notifications, and reporting. **No Zoho integration exists in code.** Legal and marketing materials incorrectly reference Zoho as integrated — this must be corrected independently of any integration programme.

The **proposed architecture** (Pleerity as system of record → integration layer → selected Zoho apps) is **technically sound**. A simpler and safer default is to **integrate nothing** until a proven business gap exists; where integration is justified, **one-way outbound sync** and **read-only connectors** minimise risk.

**Stripe remains the payment processor.** No compelling reason to adopt Zoho Books for customer billing was identified.

**Supplement (business operations):** A separate review evaluates Zoho One as **Pleerity Ltd's internal business operating system**. See `INTERNAL_BUSINESS_OPERATIONS_REVIEW.md`. Platform and company layers must remain **authority-separated** — adopt Zoho aggressively for back-office (Books, WorkDrive, Sign, Analytics, Flow); do not integrate those into the customer platform.

---

## Strategic position

| Principle | Recommendation |
|-----------|----------------|
| Pleerity as authoritative platform | **Preserve** |
| Single system of record per entity | **Enforce** |
| Avoid duplicate functionality | **Reject** Desk, MA, SalesIQ, Forms as platform integrations |
| Genuine Zoho operational value | **Limited** — CRM sales UI, optional Campaigns, Analytics BI, B2B Sign |
| Minimise vendor lock-in | **One-way sync**; no Zoho Flow as orchestration brain |
| Scalability & maintainability | **Pleerity-owned integration service** |

---

## Application decisions (executive view)

| Application | Decision | Rationale |
|-------------|----------|-----------|
| **Zoho CRM** | **Optional** — one-way Pleerity → Zoho | Mature Pleerity CRM is SoR; Zoho for sales visibility only |
| **Zoho Campaigns** | **Optional** — after Kit gap proof | Broadcast marketing; suppression sync required |
| **Zoho Marketing Automation** | **Do not integrate** | Duplicates `lead_automation_service` |
| **Zoho SalesIQ** | **Do not integrate** | Duplicates support chat |
| **Zoho Forms** | **Do not integrate** | Sufficient public lead APIs |
| **Zoho Analytics** | **Integrate (read only)** | Low-risk executive BI |
| **Zoho PageSense** | **Defer** | Cookie/consent complexity |
| **Zoho Desk** | **Do not integrate** | Mature Pleerity support module |
| **Zoho WorkDrive** | **Do not integrate** (customer docs) | Compliance vault is platform-owned |
| **Zoho Sign** | **Optional** — B2B contracts | Event-driven; subscription stays click-wrap |
| **Zoho Books** | **Do not integrate** (customer billing) | Stripe authoritative |
| **Zoho Flow** | **Do not integrate** (primary) | Logic must remain auditable in Pleerity |

---

## CRM architecture (executive)

**Adopt the proposed CRM architecture:**

```
Website → Pleerity CRM (authoritative) → Integration layer → Zoho CRM (replica)
```

- **One-way sync** in all initial phases
- **No Zoho-originated leads**
- **No retirement** of Pleerity CRM functionality
- **Skip Zoho CRM entirely** if sales team uses Pleerity admin CRM

---

## Marketing architecture (executive)

**Do not adopt Zoho as the marketing ecosystem.**

Pleerity owns lead capture, nurture, lifecycle email, and newsletter (Kit). Zoho Campaigns may serve as an **optional broadcast adjunct** with suppression export. Zoho Marketing Automation, SalesIQ, and Forms should **not** be integrated.

---

## Critical risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| False Zoho claims in production copy | **High** (trust/compliance) | Correct legal/marketing copy immediately |
| Two-way CRM sync conflicts | **Critical** | Prohibit in policy; one-way only |
| Duplicate support (Desk) | **High** | Do not integrate |
| Billing split (Books vs Stripe) | **Critical** | Stripe only for customers |
| PII export without DPIA | **High** | Complete DPIA before OAuth |
| Zoho Flow as hidden logic | **Medium** | Pleerity-owned integration service |

---

## Governance before implementation

Seven P0 governance artefacts are **missing** and block implementation:

1. Master Data Policy  
2. System of Record Policy (Zoho extension)  
3. Synchronisation Policy  
4. Conflict Resolution Policy  
5. Security Requirements  
6. Secret Management runbook  
7. DPIA sign-off  

See `GOVERNANCE_GAP_ANALYSIS.md` for full detail and approval gates G1–G6.

---

## Recommended path forward

### Immediate (no code)

1. **Approve this audit pack** for architecture and governance direction.
2. **Correct legal/marketing copy** that claims Zoho is integrated.
3. **Confirm business demand** for Zoho CRM and/or Campaigns in writing.
4. **Publish P0 policies** and complete DPIA.

### If business demand confirmed

5. Build **Pleerity Integration Service** (Phase 1 foundation).
6. Pilot **Zoho Analytics** read-only (lowest risk).
7. Pilot **one-way CRM export** only if sales requires Zoho UI.
8. Evaluate Campaigns only if Kit proves insufficient.

### Default recommendation — platform (lowest risk)

**Do not integrate Zoho into the customer platform** in the near term unless a proven gap exists (Analytics read-only, optional CRM export). Pleerity's product capabilities are production-ready and authority-governed.

### Default recommendation — internal business operations

**Adopt Zoho One for Pleerity Ltd back-office without platform coupling:**

| Priority | Adopt internally | Do not build in engineering |
|----------|------------------|----------------------------|
| **P1** | Books, WorkDrive, Sign | GL, internal DMS, B2B e-sign |
| **P2** | Analytics, Flow | Executive BI, internal iPaaS |
| **P3** | PageSense, SalesIQ (marketing site), Campaigns if Kit gap | A/B testing, marketing chat, email platform |

Full per-application analysis: `INTERNAL_BUSINESS_OPERATIONS_REVIEW.md`.

---

## Audit deliverables

| Document | Stage |
|----------|-------|
| `CURRENT_PLATFORM_CAPABILITY_ASSESSMENT.md` | Z1 |
| `ZOHO_FEASIBILITY_ASSESSMENT.md` | Z2 |
| `SYSTEM_OF_RECORD_MATRIX.md` | Z3 |
| `DUPLICATION_AND_CONFLICT_ANALYSIS.md` | Z4 |
| `INTEGRATION_STRATEGY.md` | Z5 |
| `MARKETING_ARCHITECTURE_REVIEW.md` | Z6 |
| `CRM_ARCHITECTURE_RECOMMENDATION.md` | Z7 |
| `GOVERNANCE_GAP_ANALYSIS.md` | Z8 |
| `PHASED_INTEGRATION_ROADMAP.md` | Roadmap |
| `EXECUTIVE_RECOMMENDATION.md` | Executive summary |
| `INTERNAL_BUSINESS_OPERATIONS_REVIEW.md` | Business ops supplement |

---

## Formal approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture owner | | | |
| Engineering lead | | | |
| DPO / Compliance | | | |
| Commercial stakeholder | | | |

**Implementation must not begin until this audit is reviewed, formally approved, and P0 governance artefacts are published.**

---

## Audit conclusion

The Zoho One programme has **two distinct tracks**:

1. **Customer platform** — architecturally viable but minimally required. Pleerity remains authoritative. Most in-scope apps duplicate production capability and should not integrate.
2. **Pleerity Ltd business operations** — **strong adoption case**. Books, WorkDrive, Sign, Analytics, and Flow deliver commodity back-office value without engineering cost or platform risk.

Engineering should focus on compliance, lifecycle, evidence, and subscription IP — not on rebuilding accounting, internal DMS, or executive BI.

**Audit status: COMPLETE (including business ops supplement) — AWAITING FORMAL APPROVAL**
