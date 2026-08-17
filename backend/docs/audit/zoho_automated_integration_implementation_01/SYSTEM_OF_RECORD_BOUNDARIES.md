# System of Record Boundaries

**Programme:** ZOHO AUTOMATED INTEGRATION IMPLEMENTATION

## Pleerity authoritative (never Zoho)

| Entity | Collection / service |
|--------|---------------------|
| Leads | `leads`, `LeadService` |
| Clients | `clients` |
| Billing | Stripe + `client_billing` |
| Lifecycle | `account_lifecycle_state_resolver` |
| Compliance evidence | `documents`, evidence authority |
| Support tickets | `support_tickets` |
| Portal users | `portal_users` |
| Audit logs | `audit_logs` |

## Zoho permitted roles

| Integration | Direction | Allowed |
|-------------|-----------|---------|
| Analytics | Pleerity → Zoho | Aggregated metrics only |
| CRM | Pleerity → Zoho | Lead replica; `pleerity_lead_id` external key |
| CRM | Zoho → Pleerity | **Rejected** at webhook |
| Campaigns | Pleerity → Zoho | Audience + suppression export |
| Campaigns | Zoho → Pleerity | Unsubscribe webhook only |
| Sign | Zoho → Pleerity | B2B completion audit record |
| Books | Pleerity → Zoho | Revenue summary export |
| Books | Zoho → Pleerity | **Rejected** |
| WorkDrive | Pleerity → Zoho | Internal/B2B docs only |
| WorkDrive | Customer compliance | **Forbidden** |

## Enforcement

- Adapter `authority_check_outbound()` blocks forbidden categories
- CRM inbound webhook always rejected
- Books inbound webhook always rejected
- Sign rejects `subscription_clickwrap` category
- WorkDrive rejects `compliance_evidence` category
