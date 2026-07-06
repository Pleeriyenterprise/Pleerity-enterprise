# Account Background Runtime Authority (ILP-6)

**Programme:** ILP-6 — Background Processing Runtime Authority  
**Governance mapping:** Original governance **ILP-8 Background Services** — see `ACCOUNT_LIFECYCLE_GOVERNANCE_IMPLEMENTATION_MAPPING.md`  
**Service:** `backend/services/account_background_runtime_authority.py`  
**Policy version:** `account_background_runtime_v1`

---

## Purpose

Background jobs, schedulers, queue workers, and notification dispatch must not independently decide whether a customer is active, cancelled, expired, suspended, read-only, archived, or deleted.

All background processing consumes the **Account Lifecycle Runtime Contract**:

- `lifecycle_state`
- `capabilities`
- `background_policy`
- `communication_policy`
- `retention_policy` (where relevant)
- `runtime_version`

Legacy fields (`subscription_status`, `entitlement_status`, `enforce_feature`, `FEATURE_MATRIX`) are **not** decision inputs in jobs.

---

## Decision model

```json
{
  "decision": "CONTINUE | PAUSE | SKIP | TERMINATE | RETENTION_ONLY",
  "client_id": "...",
  "job_type": "...",
  "lifecycle_state": "...",
  "portal_mode": "...",
  "background_policy_key": "reminders | digest | scheduled_reports | ...",
  "background_policy_action": "CONTINUE | PAUSE | TERMINATE | REVOKE | DRAIN_PAUSE",
  "reason": "...",
  "runtime_version": 123,
  "policy_version": "account_background_runtime_v1",
  "required_capability": "CAP_NOTIF_EMAIL | ...",
  "capability_grant": "ALLOW | DENY | ...",
  "safe_to_retry": true,
  "idempotency_key": "bg:{client_id}:{job_type}:{runtime_version}:{suffix}"
}
```

| Runtime `background_policy` action | Guard decision |
|-----------------------------------|----------------|
| CONTINUE | CONTINUE |
| PAUSE / REVOKE | SKIP |
| TERMINATE | TERMINATE |
| DRAIN_PAUSE | PAUSE |

`READ_ONLY` / `ARCHIVED` / `ACCOUNT_DELETED` with CONTINUE maps to `RETENTION_ONLY` where applicable.

`UNKNOWN` lifecycle → safe `SKIP` with diagnostics.

---

## API

| Function | Use |
|----------|-----|
| `BackgroundRuntimeAuthority.evaluate(client_id, job_type, contract=...)` | Core evaluation |
| `evaluate_background_runtime(db, client_id, job_type, **kwargs)` | Convenience wrapper |
| `gate_client_background_job(db, client_id, job_type)` | Returns `(allowed, decision)` + logs suppression |
| `resolve_notification_job_type(template_key, template, event_type)` | Map notification templates to job types |
| `apply_queue_runtime_suppression(db, collection_name, item_id, decision)` | Auditable queue skip/reschedule/terminate |

---

## Job type → policy key

See `JOB_BACKGROUND_POLICY_KEYS` in the service module. Examples:

| job_type | background_policy key | Optional capability |
|----------|----------------------|---------------------|
| `daily_reminders` | `reminders` | `CAP_NOTIF_EMAIL` |
| `monthly_digest` | `digest` | `CAP_NOTIF_EMAIL` |
| `scheduled_reports` | `scheduled_reports` | `CAP_REPORT_SCHEDULE` |
| `compliance_monitoring` | `compliance_monitoring` | — |
| `compliance_recalc` | `score_recalculation` | — |
| `risk_signals` | `risk_recalculation` | — |
| `compliance_recalc_queue` | `queue_processing` | — |
| `renewal_reminders` | `reminders` | `CAP_NOTIF_EMAIL` + `email_billing` comm policy |

---

## Observability

Suppressed work emits structured logs:

- `background_runtime_decision` — per decision
- `background_job_suppressed` — extra payload via `log_background_decision`

No sensitive customer data in logs.

---

## Governance inputs

- `ACCOUNT_LIFECYCLE_POLICY_AUTHORITY.md`
- `ACCOUNT_BACKGROUND_CAPABILITY_MATRIX.md`
- `ACCOUNT_LIFECYCLE_RUNTIME_CONTRACT.md`
- `ACCOUNT_BACKGROUND_PROCESSING_POLICY.md`
