# Account Background Processing Policy (ILP-6)

**Programme:** ILP-6 — Background Processing Runtime Authority  
**Authority:** Runtime Contract `background_policy` + `communication_policy`

---

## Principle

Background processors **gate** work; they do not **infer** lifecycle from billing or entitlement fields.

Every customer-scoped background action must call `BackgroundRuntimeAuthority` (or `gate_client_background_job`) before mutating state or sending customer communications.

---

## Lifecycle behaviour (summary)

| Lifecycle state | Typical background behaviour |
|-----------------|------------------------------|
| ACTIVE / TRIAL | Continue governed processing |
| GRACE_PERIOD / CANCELLATION_SCHEDULED | Continue where policy allows |
| READ_ONLY | Pause mutations/monitoring/reminders; retention-only where governed |
| CANCELLED_IMMEDIATE / SUBSCRIPTION_EXPIRED | Pause operational jobs; billing recovery comms only where governed |
| SUSPENDED | Pause customer operations; recovery comms if governed |
| ARCHIVED / ACCOUNT_DELETED | Terminate or skip customer jobs; legal retention/tombstone only |
| UNKNOWN | Safe skip with diagnostics |

Authoritative matrix: `resolve_background_policy()` in `account_lifecycle_runtime_contract.py`.

---

## Communication policy

Notification and reminder dispatch must respect `communication_policy`:

- `email_operational` — compliance reminders, digests, operational alerts
- `email_billing` — renewal/grace/subscription lifecycle emails
- `sms` — SMS channel (additional to job-type checks)

Jobs control **whether** sending is allowed. Lifecycle Communication Authority controls **wording**.

---

## Queue semantics

Queue consumers must not silently drop work.

| Guard decision | Queue behaviour |
|----------------|-----------------|
| CONTINUE | Process item |
| SKIP / PAUSE / RETENTION_ONLY | Reschedule to `PENDING` with `runtime_pause_*` metadata |
| TERMINATE | Mark `DEAD` with `runtime_terminated_at` |

Applied to: `compliance_recalc_queue`, `risk_signal_regen_queue`.

---

## Migrated domains (ILP-6)

1. **Reminders & notifications** — `jobs.py` daily reminders; `notification_orchestrator.py` gating
2. **Email/SMS dispatch** — orchestrator runtime + capability checks
3. **Scheduled reports & digests** — `jobs.py` monthly digest + `ScheduledReportJob`
4. **Compliance monitoring** — `jobs.py` compliance status check
5. **Score/risk recalculation** — queue workers + `risk_signals_job`
6. **Deferred** — platform/admin-only jobs (SLA monitors, lead processing, order pipeline) inventoried; customer lifecycle gating deferred to ILP-7/8 where not customer-scoped

---

## Idempotency

Decision keys include `runtime_version` so repeated scheduler ticks do not duplicate pause side-effects when contract is unchanged.

---

## Testing policy (ILP-6)

Targeted tests only during implementation:

- `tests/test_account_background_runtime_authority.py`
- Affected notification orchestrator SMS/plan gate tests
- Full backend regression reserved for ILP-6 closeout gate
