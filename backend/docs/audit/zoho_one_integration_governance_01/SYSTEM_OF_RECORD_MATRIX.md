# Stage Z3 — System of Record Matrix

**Programme:** STAGE Z — ZOHO ONE INTEGRATION GOVERNANCE & ARCHITECTURE AUDIT  
**Rule:** Each entity has exactly one authoritative source.

| Entity | System of Record | Collection / Service | Zoho role (if any) |
|--------|------------------|----------------------|-------------------|
| **Leads** | **Pleerity** | `leads`, `LeadService` | None (optional read replica in Zoho CRM) |
| **Contacts (CRM)** | **Pleerity** | Embedded in `leads`, `contact_submissions` | None |
| **Clients (accounts)** | **Pleerity** | `clients` | None |
| **Organisations (CVP)** | **Pleerity** | `clients` (INDIVIDUAL/COMPANY/AGENT) | None |
| **Organisations (ClearForm)** | **Pleerity** | `clearform_organizations` | None |
| **Users (portal)** | **Pleerity** | `portal_users` | None |
| **Properties** | **Pleerity** | `properties` | None |
| **Requirements / compliance** | **Pleerity** | `requirements`, evidence authority | None |
| **Compliance records** | **Pleerity** | Requirements + CEG index (derived) | None |
| **Documents (customer)** | **Pleerity** | `documents` + filesystem vault | None |
| **Audit logs (platform)** | **Pleerity** | `audit_logs` | Read-only export |
| **Operational timeline** | **Pleerity (derived)** | `operational_evidence_events` | None — not SoR |
| **Support tickets** | **Pleerity** | `support_tickets`, `support_service` | None |
| **Support conversations** | **Pleerity** | `support_conversations` | None |
| **Marketing contacts (newsletter)** | **Pleerity** | `newsletter_subscribers` + Kit sync | Optional Campaigns audience |
| **Marketing content** | **Pleerity** | CMS (`cms_pages`, marketing routes) | None |
| **Contracts (subscription)** | **Pleerity** | `agreement_acceptances`, `issued_agreements` | Zoho Sign for non-standard B2B only |
| **Payments** | **Stripe** | Stripe API | None |
| **Subscriptions** | **Stripe → Pleerity mirror** | `client_billing` | None |
| **Invoices (subscription)** | **Stripe → Pleerity receipts** | `stripe_checkout_invoices`, GridFS | None |
| **Invoices (maintenance ops)** | **Pleerity** | `invoices` | None |
| **Lifecycle state** | **Pleerity (derived)** | `account_lifecycle_state_resolver` | None |
| **Capabilities / entitlements** | **Pleerity (derived)** | Runtime contract + `plan_registry` | None |
| **Discovery prospects** | **Pleerity** | `discovery_prospects` → import → `leads` | None |
| **Risk-check leads** | **Pleerity** | `risk_leads` → sync `leads` | None |

## Authority chain (must not be bypassed)

```
Stripe → client_billing → lifecycle resolver → runtime contract → capabilities → routes
```

Zoho integrations **must not** write to `clients`, `client_billing`, `leads` (except governed import adapter), `requirements`, or `portal_users` without explicit governance programme.

## ClearForm boundary

ClearForm (`clearform_*` collections) is a **separate product namespace**. Zoho integrations for CVP must not conflate ClearForm users/orgs with CVP clients.
