# Phased Integration Roadmap

**Programme:** STAGE Z — ZOHO ONE INTEGRATION GOVERNANCE & ARCHITECTURE AUDIT  
**Date:** 2026-07-09  
**Prerequisite:** Formal approval of this audit pack and P0 governance policies

---

## Roadmap principles

1. **Pleerity remains system of record** for all customer-facing entities.
2. **No integration without governance** — P0 policies and DPIA first.
3. **Lowest risk first** — read-only and one-way outbound before any ingress.
4. **Prove value before expand** — each phase has exit criteria; skip phase if no business demand.
5. **No production Zoho OAuth** until sandbox pilot passes.

---

## Phase 0 — Governance & alignment (Weeks 1–4)

**Objective:** Establish controls and correct misalignment before any technical work.

| Activity | Owner | Deliverable |
|----------|-------|-------------|
| Approve audit pack | Architecture owner | Signed audit approval |
| Publish P0 policies | Compliance + engineering | MDM, SoR, sync, conflict, security policies |
| Complete DPIA | DPO | DPIA sign-off |
| Correct legal/marketing copy | Legal/marketing | Remove false Zoho integration claims |
| Confirm business demand | Sales/marketing | Written requirement for CRM and/or Campaigns |
| Zoho org setup (sandbox only) | Engineering | Isolated sandbox org, no production data |

**Exit criteria:**

- [ ] G1–G4 approval gates passed (see `GOVERNANCE_GAP_ANALYSIS.md`)
- [ ] No false Zoho claims in production-facing copy
- [ ] Business case documented for each proposed integration

**Integrations enabled:** None

---

## Phase 1 — Integration foundation (Weeks 5–8)

**Objective:** Build governed integration layer without connecting production Zoho.

| Activity | Detail |
|----------|--------|
| Design integration service | `services/integrations/` — adapter pattern, mapping registry |
| Define audit event schema | Extend `audit_logs` for sync events |
| Implement OAuth client (sandbox) | Token refresh, scope minimisation |
| Dead-letter + replay design | Admin-only replay API spec |
| Contract tests | Sandbox fixtures for CRM, Sign webhooks |
| Feature flags | `ZOHO_INTEGRATION_ENABLED=false` default |

**Exit criteria:**

- [ ] Integration service skeleton with Kit-level test coverage
- [ ] Sandbox OAuth flow verified
- [ ] Monitoring dashboards spec approved
- [ ] Security review passed

**Integrations enabled:** None (infrastructure only)

---

## Phase 2 — Read-only analytics pilot (Weeks 9–10)

**Objective:** Lowest-risk Zoho value — executive BI without write paths.

| Integration | Model | Scope |
|-------------|-------|-------|
| **Zoho Analytics** | Read only | Nightly export of anonymised/aggregated Pleerity metrics |

| Activity | Detail |
|----------|--------|
| Scheduled export job | Leads funnel, conversion, MRR summary |
| Analytics workspace | Pre-built dashboards, no PII where avoidable |
| Validate staleness SLO | < 24h acceptable for BI |

**Exit criteria:**

- [ ] Dashboards usable by leadership
- [ ] No write path to Pleerity or Zoho CRM
- [ ] DPIA covers exported fields

**Rollback:** Disable export job; Analytics becomes stale (no platform impact)

---

## Phase 3 — Optional CRM replica (Weeks 11–14)

**Objective:** One-way Pleerity → Zoho CRM for sales visibility — **only if Phase 0 business case confirmed**.

| Integration | Model | Scope |
|-------------|-------|-------|
| **Zoho CRM** | One-way sync | Leads + converted accounts only |

| Activity | Detail |
|----------|--------|
| Field mapping registry | Pleerity lead fields → Zoho Lead/Contact |
| Event triggers | create, update, stage change, convert |
| Idempotent upsert | `pleerity_lead_id` as external key |
| Suppression | Do not sync properties, billing, compliance |
| Sandbox pilot | 100 test leads end-to-end |
| Production pilot | Limited lead subset or new leads only |

**Exit criteria:**

- [ ] Sync lag < 15 minutes (event-driven) or < 1 hour (batch)
- [ ] Zero Zoho-originated leads in Pleerity
- [ ] Sales team confirms UI value
- [ ] Conflict rate = 0 on authoritative fields

**Rollback:** Disable sync job; Zoho becomes stale; Pleerity unaffected

**Skip condition:** If sales uses Pleerity `AdminLeadsPage` exclusively — **skip entire phase**.

---

## Phase 4 — Optional marketing broadcast (Weeks 15–18)

**Objective:** Zoho Campaigns for promotional email — **only if Kit/Postmark gap proven**.

| Integration | Model | Scope |
|-------------|-------|-------|
| **Zoho Campaigns** | Event-driven export | Prospect/newsletter audiences only |

| Activity | Detail |
|----------|--------|
| Suppression export | Unsubscribes, active clients, lifecycle suppressions |
| Audience sync | `newsletter_subscribers` + cold leads (marketing consent) |
| Unsubscribe sync back | Webhook → Pleerity suppression list |
| No operational email | Lifecycle emails remain Postmark/orchestrator |

**Exit criteria:**

- [ ] No duplicate sends to suppressed contacts
- [ ] Unsubscribe honoured within 24h in Pleerity
- [ ] Campaign metrics visible; Pleerity lead SoR unchanged

**Rollback:** Disable audience export; stop Campaigns sends

**Skip condition:** Kit meets broadcast needs — **skip entire phase**.

---

## Phase 5 — Optional B2B e-sign (Weeks 19–22)

**Objective:** Zoho Sign for non-standard B2B contracts beyond click-wrap.

| Integration | Model | Scope |
|-------------|-------|-------|
| **Zoho Sign** | Event-driven | Agent/enterprise agreements only |

| Activity | Detail |
|----------|--------|
| Webhook ingress | `document.completed` → Pleerity audit record |
| Link to `issued_agreements` | Supplementary, not replacement for subscription click-wrap |
| Sandbox pilot | Test agreement flow |

**Exit criteria:**

- [ ] Signed PDF stored in Pleerity vault or referenced with audit trail
- [ ] Subscription checkout unchanged
- [ ] Webhook signature verified

**Rollback:** Disable Sign webhooks; manual contract process resumes

**Skip condition:** No B2B custom contract volume — **skip**.

---

## Phase 6 — Steady state & review (Ongoing)

| Activity | Frequency |
|----------|-----------|
| Sync health review | Weekly |
| Token rotation | Quarterly |
| Policy review | Annual |
| Integration value assessment | Annual — disable unused integrations |
| Zoho MA / Desk / SalesIQ re-evaluation | Only if Pleerity capability retires |

---

## Applications explicitly excluded from roadmap

| Application | Reason |
|-------------|--------|
| Zoho Desk | Duplicate support module |
| Zoho Marketing Automation | Duplicate lead automation |
| Zoho SalesIQ | Duplicate support chat |
| Zoho Forms | Duplicate lead capture |
| Zoho WorkDrive (customer) | Compliance vault is platform-owned |
| Zoho Books (customer billing) | Stripe authoritative |
| Zoho Flow (primary orchestrator) | Logic must stay in Pleerity |
| Zoho PageSense | Deferred — consent framework |

---

## Timeline summary

```
Phase 0 ████████ Governance (mandatory)
Phase 1 ████████ Integration foundation (mandatory if any Zoho app)
Phase 2 ████ Analytics (optional, low risk)
Phase 3 ████████ CRM replica (optional, business case required)
Phase 4 ████████ Campaigns (optional, gap proof required)
Phase 5 ████████ Sign (optional, B2B volume required)
```

**Minimum viable programme:** Phase 0 only — no Zoho integration, correct copy, retain Pleerity as sole platform.

**Recommended programme if sales/marketing demand exists:** Phase 0 → 1 → 2 → 3 (CRM one-way).

---

## Resource estimate (indicative)

| Phase | Engineering effort | Ops effort |
|-------|-------------------|------------|
| 0 | 0.5 FTE × 4 weeks | Legal/compliance parallel |
| 1 | 1 FTE × 4 weeks | — |
| 2 | 0.25 FTE × 2 weeks | — |
| 3 | 1 FTE × 4 weeks | Sales UAT |
| 4 | 0.5 FTE × 4 weeks | Marketing UAT |
| 5 | 0.5 FTE × 4 weeks | — |

---

## Success metrics

| Metric | Target |
|--------|--------|
| Pleerity SoR integrity | 100% — no Zoho writes to authoritative collections |
| Sync failure recovery | < 4h mean time to replay |
| Duplicate leads from Zoho | 0 |
| Customer billing via Zoho | 0 |
| Support tickets in Zoho Desk | 0 |
