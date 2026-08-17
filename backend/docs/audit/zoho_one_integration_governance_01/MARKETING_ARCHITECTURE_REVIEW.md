# Stage Z6 — Marketing Architecture Review

**Programme:** STAGE Z — ZOHO ONE INTEGRATION GOVERNANCE & ARCHITECTURE AUDIT  
**Date:** 2026-07-09  
**Method:** Codebase verification + Zoho capability mapping

## Question

Should Zoho Campaigns, Marketing Automation, SalesIQ, Forms, Analytics, and PageSense become Pleerity's marketing ecosystem?

## Answer

**No — not as the authoritative marketing stack.** Pleerity already owns lead capture, nurture, lifecycle communications, and newsletter operations. Zoho marketing tools may serve as **optional adjuncts** for specific functions (broadcast email, executive BI) only under strict boundaries.

---

## Current Pleerity marketing stack (verified)

| Function | Implementation | Authority |
|----------|----------------|-----------|
| Lead capture | `routes/leads.py`, public contact, risk-check, discovery import | Pleerity `leads` |
| Lead scoring / pipeline | `lead_service.py`, `AdminLeadsPage.js` | Pleerity |
| Nurture / sequences | `lead_automation_service.py`, `job_runner.py` scheduled jobs | Pleerity |
| Lifecycle emails | `notification_orchestrator.py` + Postmark | Pleerity |
| Newsletter | `newsletter_subscribers`, Kit (ConvertKit) via `kit_integration` | Pleerity SoR, Kit sync |
| CMS / website content | CMS routes, marketing pages | Pleerity |
| Consent | `consent.py`, cookie policy alignment docs | Pleerity |
| Conversion tracking | Lead events, checkout abandonment, conversion attribution | Pleerity |
| Support chat (sales assist) | `support_chatbot.py`, `SupportChatWidget.js` | Pleerity |

---

## Capability assessment by Zoho app

### Lead capture

| App | Fit | Recommendation |
|-----|-----|----------------|
| **Zoho Forms** | Low | **Reject** — Pleerity has governed public APIs; Zoho forms create duplicate ingest paths |
| **Zoho SalesIQ** | Low on portal | **Reject** on authenticated surfaces; optional marketing-site widget only with consent review |
| **Zoho Campaigns** | N/A for capture | Capture stays Pleerity; Campaigns for audience only |

**Rule:** All production lead capture flows must call `LeadService.create_lead` (or governed adapters). No parallel Zoho-native lead creation.

### Lead nurturing

| App | Fit | Recommendation |
|-----|-----|----------------|
| **Zoho Marketing Automation** | **Poor** | **Reject** — duplicates `lead_automation_service.py`, behavioural triggers, and lifecycle-gated comms |
| **Zoho Campaigns** | Partial | Broadcast/nurture **only** for marketing-list contacts not in operational sequences |
| **Pleerity** | **Authoritative** | Retain all product-led nurture, compliance-gap triggers, inactive-user detection |

### Customer journeys

Pleerity journeys are **lifecycle-bound** (lead → client → provisioning → active → churn risk). Zoho MA journey builders would:

- Bypass `account_customer_communication_authority.py`
- Send to clients who should be suppressed (billing dispute, legal hold, etc.)
- Create untracked sends outside `audit_logs`

**Recommendation:** Customer journeys remain Pleerity-owned. Zoho may run **prospect-only** journeys for exported cold audiences.

### Behaviour tracking

| App | Fit | Recommendation |
|-----|-----|----------------|
| **Zoho PageSense** | Medium | **Defer** — requires cookie consent alignment (`COOKIE_POLICY_ALIGNMENT_CHECK.md` already flags Zoho) |
| **Zoho Analytics** | Medium | Read-only aggregation of Pleerity-exported events |
| **Pleerity** | High | Lead events, automation rules, Stripe/lifecycle events already tracked |

### Conversion optimisation

PageSense A/B testing is viable only after:

1. Consent framework explicitly covers Zoho tracking cookies
2. No conflict with in-house analytics on checkout/lead funnels
3. Clear separation: marketing site vs authenticated portal

**Phase 1:** Do not integrate PageSense.

### Marketing reporting

| Source | Role |
|--------|------|
| Pleerity admin dashboards | Operational truth (leads, conversion, pipeline) |
| `reporting_service.py` | Immutable customer/compliance reports |
| Zoho Analytics | **Supplementary** executive BI on exported Pleerity data |
| Zoho Campaigns reports | Campaign-specific metrics only — not lead SoR |

### Customer segmentation

| Segment type | Owner |
|--------------|-------|
| Leads (pipeline stage, score) | Pleerity |
| Clients (plan, lifecycle, capabilities) | Pleerity |
| Newsletter subscribers | Pleerity `newsletter_subscribers` (+ Kit) |
| Marketing broadcast audiences | Export from Pleerity — never authoritative |

Segmentation for **operational** comms must use Pleerity lifecycle state. Segmentation for **promotional** comms may use Zoho Campaigns lists built from nightly exports.

### Return on investment

| Integration | ROI expectation | Risk |
|-------------|-----------------|------|
| Marketing Automation | **Negative** — rebuild + conflict | High |
| Campaigns | Low–Medium — if Kit insufficient for broadcast | Medium |
| SalesIQ | Low — duplicate chat | High |
| Forms | **Negative** — duplicate capture | Medium |
| Analytics | Medium — BI without SoR transfer | Low |
| PageSense | Uncertain — consent cost | Medium |

---

## Recommended marketing architecture

```
                    ┌─────────────────────────────┐
                    │   Website / Public Forms   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   Pleerity Lead Management   │
                    │   (capture, score, nurture)    │
                    └──────────────┬──────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│ Postmark        │    │ Kit (newsletter)     │    │ Zoho Campaigns  │
│ (lifecycle ops) │    │ (subscriber sync)    │    │ (optional promo)│
└─────────────────┘    └─────────────────────┘    └─────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │ Zoho Analytics (read-only)   │
                    └─────────────────────────────┘
```

### Integration rules (marketing)

1. **Single lead ingest path** — Pleerity APIs only in production.
2. **Single operational email authority** — `notification_orchestrator.py`.
3. **Suppression export** — nightly export of unsubscribes, lifecycle suppressions, and active clients to any Zoho sender.
4. **No Zoho MA** — retain Pleerity automation jobs.
5. **Kit vs Campaigns** — prove Kit gap before adding Campaigns; do not run both on same list without dedup.
6. **Correct legal copy** — remove false Zoho integration claims until integrations are live.

---

## Verdict

| App | Marketing ecosystem role |
|-----|-------------------------|
| Campaigns | Optional adjunct — broadcast only |
| Marketing Automation | **Exclude** |
| SalesIQ | **Exclude** (portal); marketing site TBD |
| Forms | **Exclude** |
| Analytics | Read-only BI layer |
| PageSense | **Defer** |

**Pleerity remains the marketing system of record for leads, clients, and operational communications.**
