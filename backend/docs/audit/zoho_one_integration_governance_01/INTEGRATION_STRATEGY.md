# Stage Z5 — Integration Strategy (per application)

**Programme:** STAGE Z — ZOHO ONE INTEGRATION GOVERNANCE & ARCHITECTURE AUDIT

Integration models: **Do Not Integrate | Read Only | One-Way Sync | Two-Way Sync | Event-Driven | Embedded**

| Application | Recommendation | Model | Rationale |
|-------------|----------------|-------|-----------|
| **Zoho CRM** | Conditional | **One-way sync** (Pleerity → Zoho) | Sales visibility without CRM SoR transfer; avoid bidirectional conflict |
| **Zoho Campaigns** | Conditional | **Event-driven** + read suppression | Broadcast marketing; leads stay Pleerity; sync unsubscribes back |
| **Zoho Marketing Automation** | **Do Not Integrate** | — | Duplicates `lead_automation_service`, nurture jobs |
| **Zoho SalesIQ** | **Do Not Integrate** | — | Conflicts in-house support chat |
| **Zoho Forms** | **Do Not Integrate** | — | Sufficient public capture APIs; adapter only for edge microsites |
| **Zoho Analytics** | **Integrate** | **Read only** | BI on Pleerity exports; no write path |
| **Zoho PageSense** | **Do Not Integrate** (phase 1) | — | Cookie/consent complexity |
| **Zoho Desk** | **Do Not Integrate** | — | Mature Pleerity support module |
| **Zoho WorkDrive** | **Do Not Integrate** (customer) | — | Compliance vault is platform-owned |
| **Zoho Sign** | **Conditional** | **Event-driven** | B2B contracts; webhook → Pleerity audit only |
| **Zoho Books** | **Do Not Integrate** (customer) | — | Stripe authoritative; Books for Pleerity Ltd internal only if needed |
| **Zoho Flow** | **Do Not Integrate** (primary) | — | Pleerity-owned integration layer preferred |

---

## Integration layer architecture (recommended)

```
┌─────────────────────────────────────────────────────────┐
│                  Pleerity Platform                       │
│  (System of Record — leads, clients, billing, support)  │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────▼────────────────┐
          │  Pleerity Integration Service     │
          │  (new — governed, auditable)      │
          │  - idempotent outbound adapters   │
          │  - webhook ingress validators     │
          │  - mapping registry               │
          │  - dead-letter + replay           │
          └───────────────┬────────────────┘
                          │
          ┌───────────────▼────────────────┐
          │  Selected Zoho APIs (OAuth)     │
          │  CRM | Campaigns | Sign | Analytics│
          └─────────────────────────────────┘
```

**Not recommended:** Zoho Flow as the integration brain (logic outside Pleerity audit trail).

---

## Per-model definitions for Pleerity

| Model | Implementation pattern |
|-------|------------------------|
| Read only | Nightly export / Analytics connector; no webhook ingress |
| One-way sync | Outbound job after Pleerity write (lead updated → push Zoho) |
| Event-driven | Webhook ingress → validate → single writer service |
| Embedded | iframe/embed only for internal admin tools — **not** for customer portal |
| Two-way sync | **Deferred** — requires conflict resolution programme |

---

## Security baseline (all integrations)

- OAuth refresh tokens in Render secrets (never commit)
- Per-integration service account
- Webhook HMAC verification
- PII minimisation in outbound payloads
- `audit_logs` entry per sync batch and failure
- Rate limit + circuit breaker on Zoho API client
