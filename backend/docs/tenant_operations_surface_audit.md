# Tenant operations surface audit

**Date:** 2026-05-25  
**Scope:** Bounded tenant operational coherence layer (pre-implementation audit)  
**Classification:** `IMPLEMENTATION_READY` (not operational verification)

## Surfaces inventoried

| Surface | Route / API | Role |
|---------|-------------|------|
| Tenant list | `/tenants` · `GET /api/client/tenants` | Invite, assign properties, revoke |
| Tenant requests (messages) | `/tenants/messages` · `GET /api/client/tenant-messages` | Landlord inbox |
| Certificate requests | `/tenants/certificate-requests` · `GET /api/client/tenant-requests` | Cert workflow + compliance job CTA |
| Compliance pack delivery | `/tenants/delivery` · `POST/GET /api/client/compliance/tenant-delivery*` | Email pack + proof |
| Tenant portal | `/tenant/*` · `/api/tenant/*` | Self-service (F7 authority segregated) |
| Property detail | `/properties/:id` | Compliance, maintenance, documents — **no tenancy tab (gap)** |
| Rent operations | `/operations/rent` · `/api/client/operations/rent/*` | Financial authority (VERIFY-02 F6 / rent ops) |
| Maintenance | Property Jobs tab · `/api/client/maintenance/*` | Issue/WO authority |
| Calendar | `/calendar` | Scheduling projection (G6) |

## Operational strengths

- Clear **landlord vs tenant API segregation** (`client_route_guard` vs `tenant_route_guard`).
- Tenant-reported issues flow into **maintenance_issues_service** with `tenant_request` source.
- Compliance pack delivery has **immutable proof records** and provider reconciliation.
- Rent operations remain a **separate financial domain** with ledger truth (no tenant rent portal).

## Authority gaps (pre-layer)

- No **property-scoped tenancy operational view** — operators jump between Tenants workspace, Property tabs, and Rent ops.
- **No first-class tenancy entity** — assignments via `tenant_assignments`; rent uses schedules/ledgers separately.
- **Portal activity** (invite, last login) only visible on tenant list, not on property context.
- Delivery page filtered tenants with wrong field (`property_ids` vs `assigned_properties`) — **fixed in this layer**.

## Tenancy lifecycle gaps

- Property `occupancy` / `tenancy_active` drive compliance applicability but were not surfaced in an operational tenancy panel.
- Move-in/out not modelled explicitly; `tenancy_active` used as coarse signal.

## Duplicated cognitive effort

- Rent snapshot on Property **Operating** tab vs full **Rent operations** page — acceptable if deep-linked (pattern preserved).
- Certificate requests visible in Tenants area only, not on property while reviewing compliance.

## Isolated flows

- Tenant portal certificate request → landlord certificate-requests tab (OK) but not property-linked summary.
- Scheduled visits on calendar not linked from property tenant context.

## VERIFY-01 / VERIFY-02 preservation

- **F7 tenant portal** authority unchanged.
- **G1–G7** classifications untouched; no `VERIFIED_OPERATIONALLY` claim for this layer.
- New aggregation is **read-only** and cites authoritative domains in API response.

## Implementation response

- `GET /api/client/properties/{id}/occupancy-operational-summary`
- Property tab **Occupancy & tenancy**
- Tenants workspace reframed as **Tenant operations** (copy only)
- Future: `VERIFY02_G8_TENANT_OPERATIONS_PLAN.md`
