# Zoho Field Mapping Registry

**Source:** `services/integrations/zoho/registry.py`

## CRM (Pleerity → Zoho Leads)

| Pleerity field | Zoho field | Notes |
|----------------|------------|-------|
| lead_id | Pleerity_Lead_ID | **External key** |
| email | Email | |
| first_name | First_Name | |
| last_name | Last_Name | |
| phone | Phone | |
| stage | Lead_Status | Read replica |
| lead_score | Lead_Score | |
| status | Pleerity_Status | |
| source_platform | Lead_Source | |
| service_interest | Pleerity_Service_Interest | |
| client_id | Pleerity_Client_ID | Post-conversion |

**Inbound blocked fields:** lead_id, email, stage, status, client_id, lead_score, converted_at

## Analytics export (aggregates only)

See `ANALYTICS_EXPORT_METRICS` in registry — no row-level PII.

## Campaigns audience

email, marketing_consent, subscribed_at, source

## Books export

stripe_payout, stripe_fee, subscription_revenue_summary, refund_summary (line types)

## Sign categories

**Allowed:** vendor, partnership, employment, nda, b2b_agreement, internal  
**Forbidden:** subscription_clickwrap, compliance_evidence, customer_agreement

## WorkDrive categories

**Allowed:** internal, vendor, hr, governance, b2b_signed, finance  
**Forbidden:** compliance_evidence, customer_vault, requirement_evidence, property_evidence
