# CRM_FIELD_MAPPING_REGISTRY

**Phase:** `PHASE_C_ZOHO_CRM_IMPLEMENTATION_01`  
**Date:** 2026-07-14  
**Code source:** `services/integrations/zoho/registry.py` (`CRM_FIELD_MAP`)

Legend:

- **Sync direction:** `OUT` = Pleerity → Zoho only  
- **Conflict policy:** Pleerity wins; Zoho mirror overwritten on update  
- **Update policy:** Always push on successful outbound sync when field present  

| Pleerity owner | CRM field | Direction | Conflict policy | Update policy | Notes |
|---|---|---|---|---|---|
| `lead_id` (Pleerity) | `Pleerity_Lead_ID` | OUT | Immutable identity | Set on create; must not change meaning | External key; lookup identity |
| `email` | `Email` | OUT | Pleerity wins | Update on sync | Required for outbound payload |
| `first_name` | `First_Name` | OUT | Pleerity wins | Update when present | |
| `last_name` | `Last_Name` | OUT | Pleerity wins | Update when present | Required for Zoho Leads create |
| `phone` | `Phone` | OUT | Pleerity wins | Update when present | |
| `stage` | `Lead_Status` | OUT | Pleerity wins | Update (incl. lost) | Status-only lost mirror |
| `lead_score` | `Lead_Score` | OUT | Pleerity wins | Update when present | Numeric |
| `status` | `Pleerity_Status` | OUT | Pleerity wins | Update when present | Custom field |
| `source_platform` | `Lead_Source` | OUT | Pleerity wins | Update when present | |
| `service_interest` | `Pleerity_Service_Interest` | OUT | Pleerity wins | Update when present | Custom field |
| `created_at` | `Pleerity_Created_At` | OUT | Pleerity owns | Push ISO string | Custom field |
| `updated_at` | `Pleerity_Updated_At` | OUT | Pleerity owns | Push ISO string | Custom field |
| `client_id` | `Pleerity_Client_ID` | OUT | Pleerity owns | Update after convert | Custom field |

## Explicit non-maps (authority)

Billing, properties, compliance evidence, portal users, Stripe IDs, credentials — **never** mapped.

## Inbound

All mapped Zoho fields and Pleerity authority fields are blocked on inbound validation. Webhook handler always rejects CRM inbound writes.
