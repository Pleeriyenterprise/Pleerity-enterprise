# Zoho Webhook Policy

**Programme:** ZOHO AUTOMATED INTEGRATION IMPLEMENTATION

## Endpoints (flag-gated — 404 when disabled)

| Path | Integration | Action |
|------|-------------|--------|
| `POST /api/internal/integrations/zoho/webhooks/sign` | Sign | B2B completion → audit record |
| `POST /api/internal/integrations/zoho/webhooks/campaigns` | Campaigns | Unsubscribe → Pleerity suppression |
| `POST /api/internal/integrations/zoho/webhooks/crm` | CRM | **Always rejected** |
| `POST /api/internal/integrations/zoho/webhooks/books` | Books | **Always rejected** |

## Verification

All four webhook endpoints use the same verification model before any handler logic runs:

- HMAC-SHA256 via `X-Zoho-Signature` header over the **raw request body**
- Secret resolution: `ZOHO_{INTEGRATION}_WEBHOOK_SECRET` → fallback `ZOHO_WEBHOOK_SECRET`
  - Sign → `ZOHO_SIGN_WEBHOOK_SECRET`
  - Campaigns → `ZOHO_CAMPAIGNS_WEBHOOK_SECRET`
  - CRM → `ZOHO_CRM_WEBHOOK_SECRET`
  - Books → `ZOHO_BOOKS_WEBHOOK_SECRET`
- Missing secret → **401** `webhook_secret_not_configured`
- Invalid signature → **401** `invalid_signature`

**Books note:** Inbound Books operations are **always rejected** after successful signature verification. HMAC is required for consistency and endpoint protection; it does **not** enable Books as a System of Record.

## Allowed inbound actions

| Event | Pleerity action |
|-------|-----------------|
| Sign document.completed | Create audit metadata via Sign adapter |
| Campaigns unsubscribe | Update `newsletter_subscribers`, `leads.followup_status` |

## Prohibited

- CRM lead create/update
- Books billing write
- Any write to `client_billing`, `clients`, `leads` creation from Zoho
