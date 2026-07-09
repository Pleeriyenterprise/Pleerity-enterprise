# Permission Model — Admin Lifecycle Operations

**Programme:** ADMIN-LIFECYCLE-OPERATIONS-CENTRE-01  

---

## Route protection

| Layer | Mechanism |
|-------|-----------|
| Router | `dependencies=[Depends(admin_route_guard)]` on `admin_lifecycle_operations` router |
| Per-handler | `admin_route_guard(request)` returns admin user context |
| Role | Standard admin roles (`ROLE_ADMIN`, etc.) via existing admin auth |

Unauthenticated or non-admin callers receive 401/403 from existing middleware.

---

## Governed action policies

Registered in `frontend/src/config/adminActionPolicyRegistry.json` and enforced by `enforce_governed_admin_action` in `admin_action_governance.py`.

| `action_id` | Risk class | Operator level | Reason | Confirmation | Step-up |
|-------------|------------|----------------|--------|--------------|---------|
| `lifecycle_ops_refresh_runtime` | standard_operational | l2_support | required | required | no |
| `lifecycle_ops_reconcile_stripe` | high_impact_operational | billing_specialist | required | required | no |
| `lifecycle_ops_resume_subscription` | high_impact_operational | billing_specialist | required | required | **yes** |
| `lifecycle_ops_mark_support_review` | standard_operational | l2_support | required | no | no |

---

## Frontend governance

| Action | Client mechanism |
|--------|------------------|
| Standard writes | `runGovernedAdminMutation({ actionId, reason, resourceKey, mutate })` |
| Resume subscription | `useStepUpApi` + governed confirmation headers |
| Reason field | Minimum 10 characters (API + UI) |

Confirmation tokens: `POST /api/admin/governance/confirmation-token` with matching `action_id` and `resource_key` (client_id).

---

## What permissions do NOT allow

- Setting `lifecycle_state` or `portal_mode` directly
- Skipping audit log on successful mutation
- Calling Stripe resume without step-up
- Invoking reconcile without reason + confirmation (for policies that require it)

---

## Audit trail

All successful writes append to `audit_logs`:

```json
{
  "action": "ADMIN_ACTION",
  "client_id": "<client_id>",
  "metadata": {
    "action_type": "LIFECYCLE_OPS_*",
    "reason": "...",
    "actor_id": "...",
    "result fields from authority"
  }
}
```

Support review flag is **audit-only** — no lifecycle or billing document mutation.

---

## Operator guidance

| Level | Typical use |
|-------|-------------|
| L2 support | Refresh runtime, flag support review, read snapshots |
| Billing specialist | Reconcile from Stripe, resume scheduled cancellation |

Operator level is advisory in registry; enforcement is via admin role + step-up + confirmation, consistent with other governed admin mutations.
