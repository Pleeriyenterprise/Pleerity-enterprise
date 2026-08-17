# Programme A — Customer Platform Integration Plan

**Programme:** STAGE ZA — ZOHO ONE BUSINESS VALUE REALISATION & ADOPTION BLUEPRINT  
**Track:** Engineering-led platform integrations  
**Date:** 2026-07-09  
**Authority:** Stage Z architecture — Pleerity remains SoR

---

## Programme definition

Programme A contains **only** Zoho applications that require engineering work, Pleerity API coupling, or governed data export from the customer platform.

**Operational independence:** Programme A must not block Programme B. Programme B can proceed while Programme A is in governance or build phases.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| Zoho Analytics (read-only feed) | Books, WorkDrive, Sign (internal) |
| Zoho CRM (one-way export, optional) | Flow (internal Zoho-only) |
| Zoho Campaigns (audience export, conditional) | SalesIQ, PageSense, Forms (marketing) |
| Zoho Sign (platform B2B webhook, conditional) | Desk, MA platform nurture |
| Pleerity Integration Service (foundation) | Any Zoho write to authoritative collections |

---

## Prerequisites

| # | Prerequisite | Owner | Status |
|---|--------------|-------|--------|
| A-P1 | Stage Z audit approved in principle | Architecture owner | Assumed complete |
| A-P2 | P0 governance policies published | Compliance + engineering | Required before build |
| A-P3 | DPIA signed for platform data export | DPO | Required before production OAuth |
| A-P4 | Legal/marketing copy corrected (no false Zoho claims) | Legal/marketing | Required |
| A-P5 | Written business case per integration | Commercial stakeholder | Required for CRM, Campaigns |
| A-P6 | Sandbox Zoho org isolated from production | Engineering | Required |
| A-P7 | `ZOHO_INTEGRATION_ENABLED=false` default | Engineering | Required |

---

## Phased implementation

### Phase A0 — Governance (Weeks 1–4)

| Activity | Owner | Effort |
|----------|-------|--------|
| Publish MDM, SoR, sync, conflict, security policies | Compliance | 1–2 weeks |
| DPIA for Pleerity → Zoho PII export | DPO | 1–2 weeks |
| Business case: CRM, Campaigns, Analytics | Commercial | 1 week |
| Sandbox org provisioning | Engineering | 2 days |

**Exit:** Gates G1–G4 from Stage Z (`GOVERNANCE_GAP_ANALYSIS.md`)

**Business value:** Risk reduction — enables safe integration

---

### Phase A1 — Integration foundation (Weeks 5–8)

| Activity | Owner | Effort |
|----------|-------|--------|
| Design `services/integrations/` adapter pattern | Engineering lead | 1 week |
| OAuth client (sandbox), token refresh | Engineering | 3–5 days |
| Integration audit event schema | Engineering | 2–3 days |
| Dead-letter + replay spec | Engineering | 2–3 days |
| Feature flags, monitoring spec | Engineering + Ops | 2–3 days |

**Engineering effort:** ~1 FTE × 4 weeks

**Integrations live:** None (infrastructure only)

**Business value:** Enables governed future integrations without rework

---

### Phase A2 — Analytics read-only feed (Weeks 9–10)

| Activity | Owner | Effort |
|----------|-------|--------|
| Nightly export job (aggregated leads, MRR, conversion) | Engineering | 1 week |
| Analytics workspace connection | Finance/ops + marketing | 3–5 days |
| PII minimisation review | DPO | 2 days |

**Engineering effort:** ~0.25 FTE × 2 weeks

**Integration model:** Read only — no Zoho write to Pleerity

**Dependencies:** A1 complete, DPIA approved

**Risks:** PII in export; mitigate with aggregation

**Business value:** **High** — automated executive visibility

**Priority:** **First platform integration** (lowest risk)

---

### Phase A3 — CRM one-way export (Weeks 11–14, optional)

| Activity | Owner | Effort |
|----------|-------|--------|
| Field mapping registry (lead → Zoho Lead) | Engineering + sales | 1 week |
| Event triggers: create, update, convert | Engineering | 1–2 weeks |
| Sandbox pilot (100 leads) | Sales + QA | 1 week |
| Production pilot (new leads only) | Ops | 1 week |

**Engineering effort:** ~1 FTE × 4 weeks

**Dependencies:** A-P5 sales demand sign-off, A1 complete

**Skip condition:** Sales confirms `AdminLeadsPage` is sufficient

**Risks:** Two-way sync pressure; duplicate leads — mitigated by policy

**Business value:** **Medium** — sales enablement only

**Priority:** **Optional P3**

---

### Phase A4 — Campaigns audience export (Weeks 15–18, conditional)

| Activity | Owner | Effort |
|----------|-------|--------|
| Suppression export (lifecycle, unsubscribes) | Engineering | 1 week |
| Audience sync job | Engineering | 1 week |
| Unsubscribe webhook ingress | Engineering | 3–5 days |
| Marketing UAT | Marketing | 1 week |

**Engineering effort:** ~0.5 FTE × 4 weeks

**Dependencies:** Kit gap documented, DPIA, A1 complete

**Skip condition:** Kit meets broadcast needs

**Risks:** Duplicate promotional sends — suppression export mandatory

**Business value:** **Medium**

**Priority:** **Conditional P3**

---

### Phase A5 — Sign platform webhook (Weeks 19–22, optional)

| Activity | Owner | Effort |
|----------|-------|--------|
| Webhook ingress validator | Engineering | 1 week |
| Audit record on B2B completion | Engineering | 3–5 days |
| Legal UAT | Legal | 1 week |

**Engineering effort:** ~0.5 FTE × 2–4 weeks

**Dependencies:** Legal defines B2B vs click-wrap boundary

**Note:** Internal Sign use is Programme B — no engineering. This phase is **only** if platform-linked B2B signing is required.

**Business value:** **Medium** — B2B contract audit trail in Pleerity

**Priority:** **Optional P4**

---

## Programme A — owners

| Role | Responsibility |
|------|----------------|
| **Programme sponsor** | Architecture owner |
| **Delivery lead** | Engineering lead |
| **Commercial owner** | Head of sales / marketing |
| **Compliance** | DPO |
| **Operations** | Platform ops — monitoring sync health |

---

## Dependencies on Programme B

| Dependency | Direction |
|------------|-----------|
| Analytics dashboards | Programme B can build dashboards **before** A2 feed using manual CSV |
| Books revenue data | Programme B Stripe → Books export feeds Analytics independently |
| Programme A does **not** depend on Programme B completion |

---

## Programme A — expected business value

| Phase | Value | Measurability |
|-------|-------|---------------|
| A0 Governance | Risk reduction, audit compliance | Policy publication |
| A1 Foundation | Future integration velocity | Service deployed (disabled) |
| A2 Analytics feed | Executive time saved on ad-hoc reports | Dashboard refresh SLA < 24h |
| A3 CRM export | Sales activity logging in preferred UI | Sales adoption %; sync lag < 15m |
| A4 Campaigns | Marketing broadcast efficiency | Campaign send without duplicate suppressions |
| A5 Sign webhook | B2B contract traceability in platform audit | Webhook success rate |

---

## Programme A — total effort estimate

| Scenario | Engineering | Calendar |
|----------|-------------|----------|
| **Minimum** (A0 + A1 + A2 Analytics only) | ~6 FTE-weeks | ~10 weeks |
| **Full optional** (A0–A5) | ~18 FTE-weeks | ~22 weeks |
| **Skip all optional** (A0 + A1 only, no live integrations) | ~5 FTE-weeks | ~8 weeks |

---

## Programme A — kill switches

| Condition | Action |
|-----------|--------|
| No sales demand for CRM | Skip A3 permanently |
| Kit sufficient | Skip A4 |
| No B2B platform signing need | Skip A5 |
| Governance not complete | **Halt entire programme** |
| Sync conflict detected | Pause integration; Pleerity wins |

---

## Programme A conclusion

Programme A is **optional beyond Analytics read feed**. Default path: complete governance + A1 foundation + A2 Analytics only. CRM and Campaigns require explicit commercial justification.

**Programme A must remain operationally independent from Programme B.**
