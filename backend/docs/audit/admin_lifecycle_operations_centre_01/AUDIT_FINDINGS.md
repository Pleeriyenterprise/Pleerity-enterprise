# Admin Lifecycle Operations Centre 01 — Audit Findings

**Programme:** ADMIN-LIFECYCLE-OPERATIONS-CENTRE-01  
**Branch:** `develop`  
**Audited:** 2026-07-09 UTC  

## Objective

Determine what admin surfaces already exist for customer lifecycle, billing, Runtime Contract, Stripe, webhooks, and recovery — and what must be extended without duplicating authority or creating unsafe manual overrides.

---

## Existing admin surfaces (inventory)

| Surface | Route / API | What it already provides | Gap for lifecycle ops |
|---------|-------------|--------------------------|------------------------|
| **Client Control Panel** | `/admin/clients/:clientId` · `GET /api/admin/clients/{id}/control-panel` | Account summary, billing tab (mirror fields), webhook last event, reconciliation flags, impersonation, governed mutations | No Runtime Contract view; billing tab is summary-only; no governed per-client reconcile/resume/refresh actions in one place |
| **Billing Centre** | `/admin/billing` · `admin_billing.py` | Per-client sync, payment-ledger reconcile, fleet Stripe batch reconcile, recovery tab, plan changes | Fleet-oriented; deep billing mutations live here by design; not integrated with Runtime Contract diagnostics |
| **System Health** | `/admin/system-health` | Scheduler/job runs, delivery-unknown incidents | Platform-wide; not per-customer lifecycle |
| **Admin Ops Overview** | `/admin/ops` | Operational command centre | Portfolio-level, not account lifecycle |
| **Identity Lifecycle** | `/admin/identity-lifecycle` | Test/dummy identity hygiene | Identity records, not subscription lifecycle |
| **Incidents** | `/admin/incidents` | Incident triage | Not billing/lifecycle diagnostics |
| **Customer lifecycle runtime** | `GET /api/client/lifecycle-runtime` | Full Runtime Contract (customer session only) | Admins had no equivalent read API before this programme |

---

## Duplication analysis

| Capability | Existing location | Decision |
|------------|-------------------|----------|
| Billing sync from Stripe | Billing Centre `POST .../sync` | **Reuse** service layer; lifecycle ops adds per-client governed entry with audit action type `LIFECYCLE_OPS_RECONCILE_STRIPE` |
| Fleet Stripe reconcile | Billing Centre batch job | **Keep** in Billing Centre; lifecycle ops is per-account |
| Recovery checkout generation | Billing Centre Recovery tab | **Link** from lifecycle ops panel; do not duplicate UI |
| Runtime Contract resolve | `resolve_runtime_contract_for_client` | **Reuse**; admin refresh invalidates cache + resolves |
| Resume scheduled cancellation | Customer `POST /api/billing/resume` + `stripe_service.resume_subscription` | **Reuse** Stripe authority; admin path uses `admin_lifecycle_operations_resume` source |
| Webhook replay | Not exposed (intentionally) | **Blocked** in action matrix; reconcile from Stripe is the safe alternative |
| Manual lifecycle state set | None found (good) | **Must not add** |

---

## What was missing (pre-programme)

1. Admin-facing **Runtime Contract** snapshot (lifecycle_state, portal_mode, capabilities, background/communication policy).
2. Unified **per-client** view of billing mirror health, drift, stale scheduled-cancellation detection.
3. **Governed admin actions** with reason, confirmation, step-up (resume), and audit — without bypassing Stripe or resolver.
4. **Action eligibility** explaining why an operation is blocked.
5. **Lifecycle audit timeline** slice on the client detail journey.

---

## What is reused (authority chain)

```
Stripe API
  → billing_stripe_sync_service / stripe_service
  → client_billing mirror
  → subscription_lifecycle_service.sync_subscription_lifecycle
  → account_lifecycle_runtime_contract.resolve_runtime_contract_for_client
  → capability matrix + customer experience
```

Admin routes call these services only. No parallel lifecycle truth in admin layer.

---

## Permissions & governance

- All routes under `admin_route_guard`.
- Write actions use `enforce_governed_admin_action` with policies in `adminActionPolicyRegistry.json`.
- Resume subscription requires step-up (`requires_step_up: true`).
- Frontend uses `runGovernedAdminMutation` and `useStepUpApi` consistent with other admin mutations.

---

## Audit logging

Each write action creates `AuditAction.ADMIN_ACTION` with `action_type`:

- `LIFECYCLE_OPS_REFRESH_RUNTIME`
- `LIFECYCLE_OPS_RECONCILE_STRIPE`
- `LIFECYCLE_OPS_RESUME_SUBSCRIPTION`
- `LIFECYCLE_OPS_SUPPORT_REVIEW_FLAGGED` (audit-only escalation, no state mutation)

---

## Risks identified and mitigated

| Risk | Mitigation |
|------|------------|
| Admin sets lifecycle_state directly | No such endpoint or UI |
| Duplicate billing sync logic | Delegates to `sync_client_billing_from_stripe_subscription_id` + trusted reconciliation source |
| Webhook replay causes double transitions | Replay action blocked; document reconcile alternative |
| Stale mirror misleads admin | Mirror labels in UI; stale scheduled-cancellation warning |
| Governance call signature bug | Fixed: `enforce_governed_admin_action(request, user, action_id, ...)` |

---

## Verdict on audit scope

Existing structures are **suitable for extension** via a new tab on Client Control Panel. Billing Centre remains the home for fleet operations and recovery checkout generation. No new standalone page required.
