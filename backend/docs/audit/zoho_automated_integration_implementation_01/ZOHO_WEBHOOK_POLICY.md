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

- HMAC-SHA256 via `X-Zoho-Signature` header
- Secret: `ZOHO_{INTEGRATION}_WEBHOOK_SECRET` or `ZOHO_WEBHOOK_SECRET`
- Invalid signature → 401

## Allowed inbound actions

| Event | Pleerity action |
|-------|-----------------|
| Sign document.completed | Create audit metadata via Sign adapter |
| Campaigns unsubscribe | Update `newsletter_subscribers`, `leads.followup_status` |

## Prohibited

- CRM lead create/update
- Books billing write
- Any write to `client_billing`, `clients`, `leads` creation from Zoho
