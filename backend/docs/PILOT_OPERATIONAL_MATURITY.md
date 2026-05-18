# Pilot operational maturity

Production-grade pilot lifecycle operations: separated domains, deterministic health/risk scoring, anomaly reporting, and template governance.

## Lifecycle domain separation

Three explicit fields on `clients` (never collapsed into `pilot_status` alone):

| Field | Authority | Examples |
|-------|-----------|----------|
| `pilot_governance_status` | Platform (`pilot_lifecycle_service`) | active, extended, expired, converted, cancelled, comped, paused |
| `pilot_billing_status` | Stripe (`subscription_status`, `billing_lifecycle_state`) | trialing, active, past_due, unpaid, cancelled, incomplete |
| `pilot_entitlement_status` | Entitlement engine (`canonical_entitlement_state`) | enabled, grace_period, suspended, revoked |

`pilot_status` remains the governance mutation source for backward compatibility; reconciliation derives and persists the separated fields via `pilot_lifecycle_domains.sync_lifecycle_domains_to_client`.

## Reconciliation

- **Per-client:** `POST /api/admin/pilot-lifecycle/accounts/{client_id}/reconcile`
- **Scheduled:** job `pilot_lifecycle_reconcile` (hourly) — expiry transitions + `reconcile_pilot_operational_state`
- Inconsistencies are logged to `pilot_lifecycle_audit` (`operational_reconcile_warning`) and upserted into `pilot_operational_anomalies`

## Pilot health scoring (deterministic)

Service: `pilot_operational_health.compute_pilot_health_async`

Factors: onboarding completed, documents uploaded, recent activity, payment method, pilot status, conversion signals, expiry without engagement.

Outputs: `pilot_health_score` (0–100), `pilot_health_band` (`healthy`, `at_risk`, `inactive`, `conversion_ready`), `pilot_health_flags`.

## Conversion risk observability

Persisted on client as `pilot_conversion_risk`:

- `likely_conversion`, `likely_churn`
- `missing_payment_method`, `inactive_before_conversion`
- `approaching_paid_transition`, `pilot_expired_without_conversion`
- `days_remaining`, `onboarding_completed`, `payment_method_collected`

## Anomalies

Collection: `pilot_operational_anomalies`

Fields: `anomaly_code`, `severity`, `detected_at`, `resolved_at`, `resolution_notes`, `context`

Admin: `GET /api/admin/pilot-lifecycle/anomalies`, `POST .../anomalies/{id}/resolve`

## Agreement template governance

`agreement_template_governance.assert_agreement_template_publishable` blocks publish when required placeholders are missing:

- `{{onboarding_fee_line}}`
- `{{pilot_offer_line}}`
- Recurring billing (`{{monthly_fee}}` + subscription language)
- Block key `plan_fees`

Seeded templates in `agreement_seed.DEFAULT_BLOCKS` include all required disclosures.

## Commercial truth

Single authority: `pilot_commercial_truth.py` — agreements, intake, emails, admin summaries must use `commercial_context_from_invite` / `commercial_context_from_client` and `apply_pilot_to_commercial_snapshot`.

## Comp governance

- Owner-only comp: `POST .../comp` requires `require_owner`
- `pilot_comp_review_expires_at` on comp; anomalies for overdue review and excessive comp duration
- `pilot_extension_count` incremented on each extend

## Operational APIs (backend)

| Endpoint | Purpose |
|----------|---------|
| `GET /ops-dashboard` | Accounts + ops summary + open anomalies |
| `GET /accounts/{id}/operational-profile` | Timeline, domains, health, anomalies |
| `POST /accounts/{id}/reconcile` | Manual operational reconcile |
| `POST /accounts/{id}/sync-stripe-payment-method` | PM collection status |

## Notification hooks

`pilot_operational_notifications.emit_pilot_operational_event` logs all events; sends via `notification_orchestrator` only when `event_type` maps to an existing seeded `template_key`. Extend `_EVENT_TEMPLATE_MAP` when dedicated pilot templates are added.

## Operational playbooks

### Conversion

1. Check ops dashboard: `conversion_readiness`, `payment_method_collected`, `days_remaining`
2. If `missing_payment_method` near expiry → client outreach; `sync-stripe-payment-method`
3. On first paid invoice webhook → `converted` governance + `pilot_converted` notification hook

### Churn / expiry

1. Reconcile job marks `expired` when past `pilot_expires_at` / `pilot_extended_until`
2. Review anomalies: `pilot_expired_without_conversion`, `expired_pilot_active_paid_sub`
3. Stripe remains billing authority — do not cancel subs from platform reconcile alone

### Comp review

1. Set `review_expires_at` on comp
2. Resolve `comp_review_overdue` anomalies after owner review
3. Convert or cancel — comp is exceptional, not default operations

## Admin UI (frontend)

Routes (owner/admin only):

| Route | Purpose |
|-------|---------|
| `/admin/pilot-operations` | Ops dashboard, metrics, filterable account table |
| `/admin/pilot-operations/accounts/:clientId` | Operational profile, timeline, anomalies, recovery & governance actions |
| `/admin/pilot-operations/anomalies` | Global open-anomaly list, resolve, reconcile per account |

Nav: **Founding Pilot Operations** (separate from **Founding Pilot Invites**).

### Operational admin workflow

1. Open **Founding Pilot Operations** — review metrics (active, nearing expiry, missing PM, open anomalies).
2. Filter/search the account table by governance, billing, entitlement, health band, or quick flags.
3. Open an account detail page for lifecycle domains, conversion readiness, commercial summary, Stripe linkage, and timeline.
4. Use **Reconcile** or **Sync Stripe PM** when domains or payment-method state look stale (backend authoritative).
5. Run governance actions (extend, set expiry, pause/resume, convert, comp, cancel, onboarding fee policy) with required reason text.

### Anomaly management workflow

1. From the dashboard, open **Anomalies** or use the account detail **Open anomalies** section.
2. Filter by severity; search by client ID, code, or message.
3. **Resolve** with resolution notes (step-up may be required).
4. **Reconcile** the affected account to refresh domains and re-detect issues.
5. **View account** to inspect full operational profile.

Resolved anomaly history and **reopen** are not exposed in admin APIs today (`list_open_anomalies` returns unresolved only).

### Conversion monitoring

- Use backend fields only: `pilot_health_band`, `pilot_health_score`, `pilot_conversion_risk`, `conversion_readiness` on ops summary.
- Watch **days remaining**, **expected paid** date, **payment method collected**, and **likely conversion** / **churn** flags.
- Do not infer scores in the UI — display deterministic backend values.

### Reconciliation & recovery tooling

| UI control | API |
|------------|-----|
| Reconcile (account or anomaly row) | `POST .../accounts/{id}/reconcile` |
| Sync Stripe PM | `POST .../accounts/{id}/sync-stripe-payment-method` |
| Refresh profile | `GET .../operational-profile` |

Mark recovery actions clearly as operational/admin tools; they mutate audit trail and may create reconciliation warnings.

## Deferred work

- In-app comp review reminders (backend anomalies + notification log only today)
- Resolved anomaly history and reopen in admin API/UI
