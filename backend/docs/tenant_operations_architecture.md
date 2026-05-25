# Tenant operations architecture

**Status:** `IMPLEMENTATION_READY`  
**Principle:** Tenants are **operational participants**; property remains the authority anchor.

## Target model

```
Property (authority anchor)
 └── Occupancy / Tenancy (operational aggregation tab)
      ├── Applicability (occupancy, tenancy_active) — property record
      ├── Active tenants — portal_users + tenant_assignments
      ├── Tenancy lifecycle — coarse move_state from tenancy_active
      ├── Rent status — derived from rent_ledger_service (read-only)
      ├── Open maintenance — maintenance_issues + work_orders (read-only)
      ├── Certificate requests — tenant_requests
      ├── Compliance pack delivery — tenant_delivery_proofs
      ├── Reminder history — rent_reminder_events
      ├── Upcoming visits — work_orders + calendar timeline projection
      ├── Portal activity — invite / login labels (no session internals)
      └── Operational alerts — composite attention (not Today authority)

Standalone: Tenant Operations workspace (/tenants/*) — roster + workflows
```

## Authority ownership

| Domain | Owner | This layer |
|--------|-------|------------|
| Rent ledger / payments | `rent_operations` + `rent_ledger_service` | Read-only projection + deep link |
| Issues / work orders | `maintenance_issues_service` / `work_orders` | Read-only + deep link |
| Tenant CRUD / invite | `client.py` tenant routes | Deep link only |
| Scheduling | `client_calendar_timeline_service` | Read-only events |
| Today attention order | G1 Today | **Not overridden** |
| Reports | G7 derived exports | **Not overridden** |
| Tenant portal actions | F7 `/api/tenant/*` | **Not exposed to landlord aggregation as mutation** |

## Projection semantics

| Data | Live vs derived |
|------|-----------------|
| Rent counts / balances | Live from ledger collections |
| Open issues | Live query |
| Calendar visits | Derived timeline (same as G6) |
| Alerts on panel | **Derived composite** for property context only |

## Synchronization rules

- **scheduled ≠ resolved** — visit rows include explicit notes; WO completed ≠ tenant satisfaction.
- **reminder sent ≠ rent paid** — reminder history labelled accordingly.
- **reported issue ≠ closed** — issue status shown; no green closure from schedule alone.
- **delivery sent ≠ tenant acknowledged** — delivery status from proof service only.

## API

`GET /api/client/properties/{property_id}/occupancy-operational-summary`

- Gates: `tenant_portal`, `RENT_OPERATIONS`, `MAINTENANCE_WORKFLOWS` flags control section population.
- Always returns property applicability; never writes cross-domain state.

## UI

- `PropertyOccupancyTenancyPanel` — progressive disclosure sections.
- `PropertyDetailPage` tab `occupancy` — does not remove Operating financial snapshot (rent authority link preserved).

## Non-goals (this phase)

- Tenancy entity / CRM expansion
- Tenant rent payment portal
- Replacing VERIFY-02 G6/G7 proofs
- G8 execution (plan only)
