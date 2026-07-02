# Account Runtime Schema

**Programme:** ACCOUNT-LIFECYCLE-RUNTIME-CONTRACT-01  
**Schema version:** `1.0.0` (`account_lifecycle_runtime_v1`)  
**Parent:** `ACCOUNT_LIFECYCLE_RUNTIME_CONTRACT.md`

---

## JSON Schema (governed)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://pleerity.com/schemas/account-lifecycle-runtime/v1",
  "title": "AccountLifecycleRuntimeContract",
  "type": "object",
  "required": [
    "contract_version",
    "runtime_version",
    "client_id",
    "resolved_at",
    "lifecycle_state",
    "portal_mode",
    "capabilities",
    "plan",
    "customer_experience",
    "background_policy",
    "communication_policy",
    "session_policy",
    "polling_policy"
  ],
  "properties": {
    "contract_version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$", "const": "1.0.0" },
    "runtime_version": { "type": "integer", "minimum": 1 },
    "client_id": { "type": "string" },
    "resolved_at": { "type": "string", "format": "date-time" },
    "policy_pins": {
      "type": "object",
      "properties": {
        "lifecycle_policy": { "type": "string", "example": "account_lifecycle_policy_v1" },
        "capability_authority": { "type": "string", "example": "account_capability_v1" },
        "portal_mode_authority": { "type": "string", "example": "account_lifecycle_policy_v1" }
      }
    },
    "lifecycle_state": {
      "type": "string",
      "enum": [
        "ACTIVE", "TRIAL", "TRIAL_EXPIRED", "PAYMENT_PENDING", "PAYMENT_FAILED",
        "GRACE_PERIOD", "CANCELLATION_SCHEDULED", "CANCELLED_IMMEDIATE",
        "SUBSCRIPTION_EXPIRED", "READ_ONLY", "SUSPENDED", "ARCHIVED",
        "ACCOUNT_DELETED", "UNKNOWN", "LEGACY"
      ]
    },
    "portal_mode": {
      "type": "string",
      "enum": [
        "FULL_ACCESS", "READ_ONLY", "BILLING_RECOVERY", "PAYMENT_REQUIRED",
        "GRACE", "SUSPENDED", "ARCHIVED", "ACCOUNT_DELETED"
      ]
    },
    "lifecycle_context": {
      "type": "object",
      "properties": {
        "state_label": { "type": "string" },
        "state_reason": { "type": "string" },
        "period_end": { "type": ["string", "null"], "format": "date-time" },
        "grace_end": { "type": ["string", "null"], "format": "date-time" },
        "last_event_id": { "type": ["string", "null"] },
        "last_event_type": { "type": ["string", "null"] },
        "transition_pending": { "type": "boolean" }
      }
    },
    "capabilities": {
      "type": "object",
      "description": "Map of CAP_* id → effective grant",
      "additionalProperties": {
        "type": "string",
        "enum": ["ALLOW", "READ", "DENY", "HIDDEN", "PLAN_GATED"]
      }
    },
    "plan": {
      "type": "object",
      "properties": {
        "plan_code": { "type": "string" },
        "plan_name": { "type": "string" },
        "plan_features": {
          "type": "object",
          "description": "feature_key → boolean (read-only facts for PLAN_GATED resolution)",
          "additionalProperties": { "type": "boolean" }
        },
        "ops_modules": {
          "type": "object",
          "description": "maintenance_workflows, predictive_maintenance, etc.",
          "additionalProperties": { "type": "boolean" }
        }
      }
    },
    "customer_experience": {
      "type": "object",
      "required": ["heading", "explanation", "primary_cta"],
      "properties": {
        "heading": { "type": "string" },
        "explanation": { "type": "string" },
        "reason": { "type": "string" },
        "current_state_label": { "type": "string" },
        "available_features": { "type": "array", "items": { "type": "string" } },
        "unavailable_features": { "type": "array", "items": { "type": "string" } },
        "primary_cta": {
          "type": "object",
          "properties": {
            "label": { "type": "string" },
            "route": { "type": "string" }
          }
        },
        "secondary_cta": {
          "type": ["object", "null"],
          "properties": {
            "label": { "type": "string" },
            "route": { "type": "string" }
          }
        },
        "recovery_guidance": { "type": "string" },
        "support_guidance": { "type": "string" },
        "expected_next_step": { "type": "string" }
      }
    },
    "background_policy": {
      "type": "object",
      "properties": {
        "reminders": { "type": "string", "enum": ["CONTINUE", "PAUSE", "TERMINATE"] },
        "digest": { "type": "string", "enum": ["CONTINUE", "PAUSE", "TERMINATE"] },
        "scheduled_reports": { "type": "string", "enum": ["CONTINUE", "PAUSE", "REVOKE", "TERMINATE"] },
        "compliance_monitoring": { "type": "string", "enum": ["CONTINUE", "PAUSE", "TERMINATE"] },
        "score_recalculation": { "type": "string", "enum": ["CONTINUE", "PAUSE", "TERMINATE"] },
        "risk_recalculation": { "type": "string", "enum": ["CONTINUE", "PAUSE", "TERMINATE"] },
        "queue_processing": { "type": "string", "enum": ["CONTINUE", "DRAIN_PAUSE", "TERMINATE"] }
      }
    },
    "communication_policy": {
      "type": "object",
      "properties": {
        "email_operational": { "type": "boolean" },
        "email_billing": { "type": "boolean" },
        "sms": { "type": "boolean" },
        "portal_notifications": { "type": "boolean" },
        "template_family": { "type": "string" }
      }
    },
    "session_policy": {
      "type": "object",
      "properties": {
        "jwt_valid": { "type": "boolean" },
        "force_reauth": { "type": "boolean" },
        "session_version_bump_recommended": { "type": "boolean" },
        "entitlements_version": { "type": "integer" }
      }
    },
    "retention_policy": {
      "type": "object",
      "properties": {
        "tier": { "type": "string", "enum": ["STANDARD", "EXTENDED", "READ_ONLY_WINDOW", "PURGE_ELIGIBLE"] },
        "data_export_allowed": { "type": "boolean" },
        "purge_eligible_at": { "type": ["string", "null"], "format": "date-time" }
      }
    },
    "reactivation_policy": {
      "type": "object",
      "properties": {
        "eligible": { "type": "boolean" },
        "paths": { "type": "array", "items": { "type": "string" } },
        "restoration_scope": { "type": "string", "enum": ["EVERYTHING", "READ_ONLY", "SELECTIVE", "MANUAL_REVIEW"] }
      }
    },
    "polling_policy": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean" },
        "reason": { "type": "string" },
        "circuit_breaker_after_denies": { "type": "integer", "default": 2 }
      }
    },
    "navigation_policy": {
      "type": "object",
      "properties": {
        "landing_route": { "type": "string" },
        "locked_routes": { "type": "array", "items": { "type": "string" } },
        "read_only_routes": { "type": "array", "items": { "type": "string" } },
        "hidden_routes": { "type": "array", "items": { "type": "string" } }
      }
    },
    "audit": {
      "type": "object",
      "description": "Internal diagnostics; omit from customer API in production if sensitive",
      "properties": {
        "resolver_build_id": { "type": "string" },
        "fact_snapshot_hash": { "type": "string" },
        "resolution_ms": { "type": "number" }
      }
    }
  }
}
```

---

## Example response (`GET /api/client/lifecycle-runtime`)

```json
{
  "contract_version": "1.0.0",
  "runtime_version": 42,
  "client_id": "org_abc123",
  "resolved_at": "2026-06-30T14:00:00Z",
  "policy_pins": {
    "lifecycle_policy": "account_lifecycle_policy_v1",
    "capability_authority": "account_capability_v1"
  },
  "lifecycle_state": "CANCELLED_IMMEDIATE",
  "portal_mode": "BILLING_RECOVERY",
  "lifecycle_context": {
    "state_label": "Subscription ended",
    "state_reason": "cancelled_immediate",
    "period_end": null,
    "grace_end": null,
    "last_event_id": "evt_sub_cancelled_001",
    "last_event_type": "SUBSCRIPTION_CANCELLED",
    "transition_pending": false
  },
  "capabilities": {
    "CAP_PROP_VIEW": "READ",
    "CAP_PROP_EDIT": "DENY",
    "CAP_TODAY_VIEW": "DENY",
    "CAP_BILLING_VIEW": "ALLOW",
    "CAP_SUB_RENEW": "ALLOW",
    "CAP_DATA_EXPORT": "READ"
  },
  "plan": {
    "plan_code": "PLAN_2_PORTFOLIO",
    "plan_name": "Portfolio",
    "plan_features": { "reports_pdf": true, "scheduled_reports": true },
    "ops_modules": { "maintenance_workflows": true }
  },
  "customer_experience": {
    "heading": "Your subscription has ended",
    "explanation": "Your data is preserved. Resubscribe to restore full access.",
    "reason": "Subscription cancelled",
    "current_state_label": "Inactive subscription",
    "available_features": ["billing", "profile", "support", "data_export"],
    "unavailable_features": ["dashboard", "properties", "requirements", "reports", "today"],
    "primary_cta": { "label": "Resubscribe", "route": "/settings/billing" },
    "secondary_cta": { "label": "Export my data", "route": "/settings/billing?tab=export" },
    "recovery_guidance": "Choose a plan to reactivate your account.",
    "support_guidance": "Contact support if you need help.",
    "expected_next_step": "Complete resubscription"
  },
  "background_policy": {
    "reminders": "PAUSE",
    "digest": "PAUSE",
    "scheduled_reports": "REVOKE",
    "compliance_monitoring": "PAUSE",
    "score_recalculation": "PAUSE",
    "risk_recalculation": "PAUSE",
    "queue_processing": "DRAIN_PAUSE"
  },
  "communication_policy": {
    "email_operational": false,
    "email_billing": true,
    "sms": false,
    "portal_notifications": false,
    "template_family": "subscription_ended"
  },
  "session_policy": {
    "jwt_valid": true,
    "force_reauth": false,
    "session_version_bump_recommended": false,
    "entitlements_version": 42
  },
  "retention_policy": {
    "tier": "STANDARD",
    "data_export_allowed": true,
    "purge_eligible_at": null
  },
  "reactivation_policy": {
    "eligible": true,
    "paths": ["R-005_immediately_cancelled_restored"],
    "restoration_scope": "EVERYTHING"
  },
  "polling_policy": {
    "enabled": false,
    "reason": "lifecycle_terminal",
    "circuit_breaker_after_denies": 2
  },
  "navigation_policy": {
    "landing_route": "/settings/billing",
    "locked_routes": ["/today", "/dashboard", "/command-center", "/properties/create"],
    "read_only_routes": ["/properties", "/requirements", "/reports"],
    "hidden_routes": ["/operations"]
  }
}
```

---

## Field authority matrix

| Field | Owner | Source facts | Consumers | Mutability | Version bump |
|-------|-------|--------------|-----------|------------|--------------|
| `contract_version` | Platform governance | Schema release | All | Release process | Major schema change |
| `runtime_version` | Runtime Contract Resolver | Any material field change | Client etag, cache | Resolver increment | Any grant/mode change |
| `lifecycle_state` | ILP-1 Resolver | billing + org facts | All | Webhook/admin only via resolver | Yes |
| `portal_mode` | Resolver (derived) | ALPA map | Frontend, nav | Derived | Yes |
| `capabilities` | Resolver (ACA) | state + mode + plan | API, FE, jobs | Derived | Yes |
| `plan` | plan_registry | client_billing | PLAN_GATED resolution | Billing sync | On plan change |
| `customer_experience` | Resolver (derived) | APMA + CX authority | Frontend | Derived | On mode change |
| `background_policy` | Resolver (derived) | ALPA matrix | jobs.py, workers | Derived | Yes |
| `communication_policy` | Resolver (derived) | ALPA + LCA | notification_orchestrator | Derived | Yes |
| `session_policy` | Resolver + session service | transition rules | auth middleware, FE | Event-driven | On bump |
| `retention_policy` | Resolver | retention scheduler | export APIs | Scheduled | Tier change |
| `reactivation_policy` | Resolver | Reactivation Authority | billing, admin | On state change | Yes |
| `polling_policy` | Resolver | CX authority | ClientPortalLayout | Derived | Yes |
| `navigation_policy` | Resolver | Nav + portal mode | Navigation Authority | Derived | Yes |

---

## Caching and TTL

| Store | Key | TTL | Invalidation |
|-------|-----|-----|--------------|
| API process memory | `alrc:{client_id}` | 30s | `runtime_version` change |
| Redis (optional) | `alrc:{client_id}:{runtime_version}` | 60s | Version mismatch |
| Mongo snapshot (optional) | `client_lifecycle_runtime` collection | Until invalidation | Webhook, admin |
| Frontend localStorage | `lifecycle_runtime_version` only | Session | Refetch on mismatch |
| Worker job context | Snapshot at job enqueue | Job lifetime | New job after event |

**Client request header (optional):** `X-Lifecycle-Runtime-Version: 42`  
**Response header:** `X-Lifecycle-Runtime-Version: 42`  
Mismatch → 200 with fresh body; frontend replaces cache.

---

## Capability payload rules

1. Include **all customer-facing** `CAP_*` ids from catalog (sparse maps forbidden in v1 — use HIDDEN for irrelevant).
2. `PLAN_GATED` means lifecycle allows; client must also check `plan.plan_features` or use pre-resolved `ALLOW`/`DENY` in v1.1.
3. v1.0: resolver **pre-resolves** PLAN_GATED to ALLOW/DENY in `capabilities` for customer API simplicity.

---

## Read-only API behaviour

When `portal_mode` is `BILLING_RECOVERY` or `READ_ONLY`:

- Mutating endpoints return 403 with `lifecycle_redirect` and string `message`.
- Read endpoints return 200 when capability grant is `READ` or `ALLOW`.
- Current gap: shell block denies all — ILP-4/ILP-6 fix.

---

## Audit requirements

Every resolver run logs (internal):

- `client_id`, `runtime_version`, `lifecycle_state`, `portal_mode`
- `fact_snapshot_hash`, `policy_pins`, `resolved_at`
- Transition: `previous_runtime_version`, `trigger_event_id`

Customer API omits `audit` block unless admin diagnostic flag.

---

**Outcome:** `ACCOUNT_RUNTIME_SCHEMA_COMPLETE`
