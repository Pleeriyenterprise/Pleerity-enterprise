# Account Capability Enforcement Matrix

**Programme:** ILP-4-CAPABILITY-ENFORCEMENT-01  
**Authority:** `ACCOUNT_CAPABILITY_AUTHORITY.md`, `ACCOUNT_CAPABILITY_CATALOG.md`  
**Status:** ILP-4 in progress — billing client routes, read API, webhooks, profile, assistant, calendar, compliance workflow, rent, approvals, maintenance, contractors, tenant, branding, evidence pack, analytics routes capability-governed

---

## ILP-4 migrated routes — customer billing (`routes/billing.py`, `routes/client_billing.py`)

### `routes/billing.py` (customer `/api/billing/*`)

| Endpoint | Method | Capability | Action | Notes |
|----------|--------|------------|--------|-------|
| `/api/billing/status` | GET | `CAP_BILLING_VIEW` | read | Subscription status dashboard |
| `/api/billing/payment-method-summary` | GET | `CAP_BILLING_PAYMENT_METHODS` | read | Masked card summary |
| `/api/billing/invoices` | GET | `CAP_BILLING_INVOICES` | read | Stripe invoice history |
| `/api/billing/checkout` | POST | `CAP_BILLING_CHECKOUT` | write | Step-up retained after capability |
| `/api/billing/portal` | POST | `CAP_SUB_MANAGE` | write | Stripe billing portal session |
| `/api/billing/cancel` | POST | `CAP_SUB_CANCEL` | write | Subscription cancellation |
| `/api/billing/plans` | GET | — | — | Public plan catalogue (unchanged) |

No `enforce_feature()` / subscription entitlement checks in handlers. Stripe integration unchanged.

### `routes/client_billing.py` (full module)

| Endpoint | Method | Capability | Action |
|----------|--------|------------|--------|
| `/api/client/billing/receipts` | GET | `CAP_BILLING_INVOICES` | read |
| `/api/client/billing/receipt/latest` | GET | `CAP_BILLING_INVOICES` | read |
| `/api/client/billing/receipt/{id}` | GET | `CAP_BILLING_INVOICES` | read |
| `/api/client/billing/receipt/{id}/download` | GET | `CAP_BILLING_INVOICES` | read |

**Runtime contract rows added:** `CAP_BILLING_INVOICES`, `CAP_BILLING_PAYMENT_METHODS`, `CAP_SUB_CANCEL` (billing-exempt grants mirror `CAP_BILLING_VIEW` / `CAP_SUB_MANAGE`).

**Existing rows consumed:** `CAP_BILLING_VIEW`, `CAP_BILLING_CHECKOUT`, `CAP_SUB_MANAGE`.

**Out of scope:** `routes/webhooks.py` inbound Stripe receivers, `routes/admin_billing.py`, billing engine, jobs.

**Lifecycle test coverage:** `test_account_capability_enforcement_billing_client.py` — `ACTIVE`, `TRIAL`, `GRACE_PERIOD`, `CANCELLATION_SCHEDULED`, `CANCELLED_IMMEDIATE`, `SUBSCRIPTION_EXPIRED`, `READ_ONLY`, `SUSPENDED`, `ARCHIVED`, `ACCOUNT_DELETED`, `UNKNOWN`; recovery caps never blocked in governed recovery lifecycles.

---

## ILP-4 migrated routes — read API and webhooks

### `routes/client_read_api.py` (full module)

| Route area | Capability | Action | Notes |
|------------|------------|--------|-------|
| `GET/POST/DELETE /api/client/integrations/read-api-keys*` | `CAP_INTEGRATION_READ_API` | read / write | Key list read; create/revoke write |
| `GET /api/client-data/v1/*` | `CAP_EXPORT_API` | read | API-key auth plane (after token resolve) |

No `plan_registry.enforce_feature("webhooks")` in handlers.

**Runtime contract rows added:** `CAP_INTEGRATION_READ_API`, `CAP_EXPORT_API`, `CAP_INTEGRATION_WEBHOOKS` (plan key `webhooks`).

### `routes/webhooks_config.py` (full module)

| Route area | Capability | Action |
|------------|------------|--------|
| `GET /api/webhooks/events`, `/stats`, `/deliveries`, `GET /api/webhooks`, `GET /api/webhooks/{id}` | `CAP_INTEGRATION_WEBHOOKS` | read |
| `POST /api/webhooks`, `PATCH/DELETE /api/webhooks/{id}`, test/enable/disable/regenerate-secret | `CAP_INTEGRATION_WEBHOOKS` | write |

**Out of scope:** `routes/webhooks.py` inbound Stripe/Postmark receivers (no client entitlement gates).

---

## ILP-4 migrated routes — profile, assistant, and calendar

### `routes/profile.py` (full module)

| Route area | Capability | Action | Notes |
|------------|------------|--------|-------|
| `GET /api/profile/me`, notifications, avatar | `CAP_PROFILE_VIEW` | read | |
| `PATCH /api/profile/me`, notification prefs, avatar upload | `CAP_PROFILE_EDIT` | write | |
| In-app notification read/dismiss/cta | `CAP_PROFILE_EDIT` | write | |
| `GET /api/profile/system-banners/active` | `CAP_PROFILE_VIEW` | read | `require_auth` + `assert_client_capability` (invited users) |
| `POST /api/profile/system-banners/{id}/dismiss` | `CAP_PROFILE_EDIT` | write | |

No `enforce_feature()` / subscription entitlement checks in handlers.

**Runtime contract row added (matrix only, not yet routed):** `CAP_PROFILE_JURISDICTION` — jurisdiction routes remain on `client.py` (out of scope).

### `routes/assistant.py` (full module)

| Route area | Capability | Action |
|------------|------------|--------|
| `GET /api/assistant/snapshot` | `CAP_AI_ASSISTANT` | read |
| `GET /api/assistant/conversation/{id}/status` | `CAP_AI_ASSISTANT` | read |
| `POST /api/assistant/ask`, `/chat`, `/escalate` | `CAP_AI_ASSISTANT` | write |

Rate limits retained. No plan-registry gates.

### `routes/calendar.py` (full module)

| Route area | Capability | Action | Notes |
|------------|------------|--------|-------|
| `GET /api/calendar/events`, `/expiries`, `/upcoming` | `CAP_CALENDAR_VIEW` | read | |
| `GET /api/calendar/export.ics` | `CAP_CALENDAR_VIEW` | read | Replaces `plan_registry.enforce_feature(compliance_calendar)` |
| `GET /api/calendar/subscription-url` | `CAP_CALENDAR_VIEW` | read | Same |

No separate calendar write capability in catalog — export/subscription are read under `CAP_CALENDAR_VIEW`.

**Runtime contract rows added:** `CAP_CALENDAR_VIEW` (plan key `compliance_calendar`); `CAP_PROFILE_JURISDICTION` (no plan key, for future `client.py` jurisdiction routes).

---

## ILP-4 migrated routes — rent operations and approvals

### `routes/client_rent_operations.py` (full module)

| Route group | Capability | Action | Notes |
|-------------|------------|--------|-------|
| `/api/client/operations/rent/capabilities` | `CAP_OPS_RENT` | read | Handshake |
| `/api/client/operations/rent/tenancies*` | `CAP_OPS_RENT` | read / write | List read; create/close write |
| `/api/client/operations/rent/schedules/preview` | `CAP_OPS_RENT` | read | Preview only |
| `/api/client/operations/rent/schedules*` | `CAP_OPS_RENT` | read / write | List read; create write |
| `/api/client/operations/rent/summary` | `CAP_OPS_RENT` | read | |
| `/api/client/operations/rent/ledgers*` | `CAP_OPS_RENT` | read / write | Patch ledger, payments, reminders write |
| `/api/client/operations/rent/payments` | `CAP_OPS_RENT` | write | |
| `/api/client/operations/expenses*` | `CAP_OPS_RENT` | read / write | |
| `/api/client/properties/{id}/financial-snapshot` | `CAP_OPS_RENT` | read | |

No `get_effective_flags()` / `RENT_OPERATIONS` ops-flag gates in handlers. Router-level `client_route_guard` retained.

**Runtime contract row added:** `CAP_OPS_RENT` (plan key `rent_operations`).

### `routes/client_approvals.py` (full module)

| Endpoint | Method | Capability | Action |
|----------|--------|------------|--------|
| `/api/client/invoices` | POST | `CAP_OPS_APPROVALS` | write |
| `/api/client/finance/maintenance-spend-this-month` | GET | `CAP_OPS_APPROVALS` | read |
| `/api/client/approvals` | GET | `CAP_OPS_APPROVALS` | read |
| `/api/client/approvals/export` | GET | `CAP_OPS_APPROVALS` | read |
| `/api/client/approvals/{invoice_id}` | GET | `CAP_OPS_APPROVALS` | read |
| `/api/client/approvals/{invoice_id}` | PATCH | `CAP_OPS_APPROVALS` | write | Step-up auth retained |

No `get_effective_flags()` / `INVOICING` ops-flag gates in handlers.

**Runtime contract row added:** `CAP_OPS_APPROVALS` (plan key `compliance_engine` per catalog).

---

## ILP-4 migrated routes — compliance workflow, execution, and compliance pack

### `routes/api_compliance_workflow.py` (full module, `/api/*`)

| Route area | Capability | Action | Notes |
|------------|------------|--------|-------|
| `GET /api/requirements/{id}` | `CAP_REQ_VIEW` | read | |
| `POST /api/requirements/{id}/jobs` | `CAP_OPS_COMPLIANCE_REVIEW` + `CAP_OPS_MAINTENANCE` | write | Replaces `COMPLIANCE_ENGINE` + `MAINTENANCE_WORKFLOWS` ops flags |
| `POST /api/requirements/{id}/mark-not-applicable` | `CAP_REQ_MARK_N_A` | write | |
| `POST /api/requirements/{id}/reopen` | `CAP_REQ_RESOLVE` | write | |
| `POST /api/requirements/{id}/documents` | `CAP_DOC_UPLOAD` | write | |
| `GET /api/jobs/{id}` | `CAP_OPS_MAINTENANCE` | read | |
| `POST /api/jobs/{id}/*` (mutations) | `CAP_OPS_MAINTENANCE` | write | Schedule, booking, quote, completion, close, cancel |
| `POST /api/jobs/{id}/verify` | `CAP_OPS_MAINTENANCE` + `CAP_OPS_COMPLIANCE_REVIEW` | write | Compliance closeout only |
| `GET /api/jobs/{id}/assignable-contractors` | `CAP_OPS_MAINTENANCE` + `CAP_OPS_CONTRACTORS` | read | |
| `POST /api/contractors`, assign-contractor routes | `CAP_OPS_MAINTENANCE` + `CAP_OPS_CONTRACTORS` | write | |
| `GET /api/today/items` | `CAP_TODAY_VIEW` | read | |
| `POST /api/today/items/{id}/*` | `CAP_TODAY_ACT` | write | snooze, dismiss, restore, mark-reviewed |

**Legacy removed:** `get_effective_flags`, `COMPLIANCE_ENGINE`, `MAINTENANCE_WORKFLOWS`, `CONTRACTOR_NETWORK` gates.

### `routes/client_compliance_execution.py` (full module)

| Route area | Capability | Action |
|------------|------------|--------|
| `POST .../work-orders/book` | `CAP_REQ_RESOLVE` + `CAP_OPS_MAINTENANCE` | write |
| `GET .../contractor-routing` | `CAP_REQ_RESOLVE` + `CAP_OPS_MAINTENANCE` | read |
| Contractor routing mutations / lists | above + `CAP_OPS_CONTRACTORS` | read / write |

### `routes/compliance_delivery_audit.py` (client routes only)

| Endpoint | Capability | Action | Replaces |
|----------|------------|--------|----------|
| `POST /api/client/compliance/tenant-delivery` | `CAP_TENANT_MANAGE` + `CAP_REPORT_GENERATE_PDF` | write | `tenant_portal` + `reports_pdf` |
| `GET /api/client/compliance/tenant-deliveries` | `CAP_TENANT_MANAGE` | read | ungated → capability-gated |
| `POST /api/client/compliance/audit-pack/generate` | `CAP_REPORT_AUDIT_PACK` | write | `reports_pdf` |
| `GET /api/client/compliance/audit-pack/{id}/download` | `CAP_REPORT_AUDIT_PACK` | read | `reports_pdf` |

### `routes/client.py` (compliance-pack subset)

| Endpoint | Capability | Action | Replaces |
|----------|------------|--------|----------|
| `GET /api/client/compliance-pack/{id}/preview` | `CAP_REPORT_DOWNLOAD` | read | ungated |
| `GET /api/client/compliance-pack/{id}/download` | `CAP_REPORT_DOWNLOAD` | read | `reports_pdf` |

**Runtime contract row added:** `CAP_OPS_COMPLIANCE_REVIEW` (plan key `compliance_engine`).

**Existing rows consumed:** `CAP_REQ_VIEW`, `CAP_REQ_RESOLVE`, `CAP_REQ_MARK_N_A`, `CAP_DOC_UPLOAD`, `CAP_OPS_MAINTENANCE`, `CAP_OPS_CONTRACTORS`, `CAP_TODAY_VIEW`, `CAP_TODAY_ACT`, `CAP_TENANT_MANAGE`, `CAP_REPORT_GENERATE_PDF`, `CAP_REPORT_AUDIT_PACK`, `CAP_REPORT_DOWNLOAD`.

---

## ILP-4 migrated routes — maintenance and contractors

### `routes/client_maintenance.py` (full module)

| Route group | Capability | Action | Notes |
|-------------|------------|--------|-------|
| `/api/client/maintenance/work-orders*` (list, get, create, patch, schedule, evidence file, ICS) | `CAP_OPS_MAINTENANCE` | read / write | Schedule mutations are write |
| `/api/client/maintenance/issues*` | `CAP_OPS_MAINTENANCE` | read / write | Timeline and open-count are read |
| `/api/client/maintenance/operational-issue-suggestions*` | `CAP_OPS_MAINTENANCE` + `CAP_OPS_PREDICTIVE` | write | Dismiss and convert |
| `/api/client/maintenance/work-orders/{id}/recommend-contractors` | `CAP_OPS_MAINTENANCE` + `CAP_OPS_CONTRACTORS` | read | |
| `/api/client/maintenance/work-orders/{id}/assignable-contractors` | `CAP_OPS_MAINTENANCE` | read | |
| `/api/client/maintenance/work-orders/{id}/contractor-routing*` | `CAP_OPS_MAINTENANCE` + `CAP_OPS_CONTRACTORS` | read / write | Generate uses contractors write |
| `/api/client/maintenance/properties/{id}/assets*` | `CAP_OPS_MAINTENANCE` **or** `CAP_OPS_PREDICTIVE` | read / write | Either capability grants access |
| `/api/client/maintenance/predictive-insights` | `CAP_OPS_PREDICTIVE` | read | |
| `/api/client/maintenance/properties/{id}/events*` | `CAP_OPS_PREDICTIVE` | read / write | |
| `/api/client/maintenance/risk-signals*` | `CAP_OPS_PREDICTIVE` | read / write | Create issue/wo also requires `CAP_OPS_MAINTENANCE` write |
| `/api/client/maintenance/risk-signals/{id}/arrange-compliance-inspection` | `CAP_OPS_PREDICTIVE` + `CAP_OPS_MAINTENANCE` | write | `COMPLIANCE_ENGINE` ops flag retained (compliance workflow out of scope) |

No `enforce_feature()` / ops-flag permission gates in handlers. Router-level `client_route_guard` retained.

**Runtime contract rows added:** `CAP_OPS_CONTRACTORS` (plan key `contractor_network`), `CAP_OPS_PREDICTIVE` (plan key `predictive_maintenance`). `CAP_OPS_MAINTENANCE` (plan key `maintenance_workflows`) was already in matrix.

### `routes/client.py` (contractor subset)

| Endpoint | Method | Capability | Action |
|----------|--------|------------|--------|
| `/api/client/contractors` | GET | `CAP_OPS_CONTRACTORS` | read |
| `/api/client/contractors/{contractor_id}/explanation` | GET | `CAP_OPS_CONTRACTORS` | read |
| `/api/client/contractors/{contractor_id}/submit-to-network` | POST | `CAP_OPS_CONTRACTORS` | write |
| `/api/client/contractors` | POST | `CAP_OPS_CONTRACTORS` | write |
| `/api/client/contractors/{contractor_id}/rate` | POST | `CAP_OPS_CONTRACTORS` | write |

---

## ILP-4 migrated routes — tenant and branding (`routes/client.py`)

| Endpoint | Method | Capability | Action | Notes |
|----------|--------|------------|--------|-------|
| `/api/client/tenants/invite` | POST | `CAP_TENANT_MANAGE` | write | Admin role check retained |
| `/api/client/tenants` | GET | `CAP_TENANT_MANAGE` | read | |
| `/api/client/tenant-messages` | GET | `CAP_TENANT_MESSAGES` | read | |
| `/api/client/tenant-requests` | GET | `CAP_TENANT_MANAGE` | read | |
| `/api/client/tenant-requests/{id}/start-compliance-job` | POST | `CAP_TENANT_MANAGE` | write | |
| `/api/client/tenant-requests/{id}` | PATCH | `CAP_TENANT_MANAGE` | write | |
| `/api/client/tenants/{id}/assign-property` | POST | `CAP_TENANT_MANAGE` | write | |
| `/api/client/tenants/{id}/unassign-property/{property_id}` | DELETE | `CAP_TENANT_MANAGE` | write | |
| `/api/client/tenants/{id}` | DELETE | `CAP_TENANT_MANAGE` | write | |
| `/api/client/tenants/{id}/resend-invite` | POST | `CAP_TENANT_MANAGE` | write | |
| `/api/client/branding` | GET | `CAP_BRANDING_VIEW` | read | `feature_enabled` via `CAP_BRANDING_WHITE_LABEL` |
| `/api/client/branding` | PUT | `CAP_BRANDING_EDIT` | write | |
| `/api/client/branding/reset` | POST | `CAP_BRANDING_EDIT` | write | |
| `/api/client/branding/logo` | GET | `CAP_BRANDING_VIEW` | read | |
| `/api/client/branding/logo` | POST | `CAP_BRANDING_EDIT` | write | |
| `/api/client/branding/preview` | GET | `CAP_BRANDING_EDIT` | read | |
| `/api/client/properties/{id}/occupancy-operational-summary` | GET | `CAP_PROP_VIEW` | read | Tenant slice: `CAP_TENANT_PORTAL` evaluate |

No `enforce_feature()` in these handlers.

**Runtime contract rows added:** `CAP_TENANT_MANAGE`, `CAP_TENANT_MESSAGES`, `CAP_BRANDING_VIEW`, `CAP_BRANDING_EDIT`, `CAP_BRANDING_WHITE_LABEL`.

---

## ILP-4 migrated routes — evidence pack, analytics, activity-since (`routes/client.py`)

| Endpoint | Method | Capability | Action | Notes |
|----------|--------|------------|--------|-------|
| `/api/client/analytics/summary` | GET | `CAP_COMPLIANCE_ACTIVITY` | read | |
| `/api/client/analytics/events` | POST | `CAP_COMPLIANCE_ACTIVITY` | write | |
| `/api/client/activity-since` | GET | `CAP_COMPLIANCE_ACTIVITY` | read | |
| `/api/client/activity-since/acknowledge` | POST | `CAP_COMPLIANCE_ACTIVITY` | write | |
| `/api/client/evidence-pack/jobs` | POST | `CAP_REPORT_AUDIT_PACK` | write | Plan via runtime `audit_log_export`; rate limit retained |
| `/api/client/evidence-pack/jobs` | GET | `CAP_REPORT_AUDIT_PACK` | read | |
| `/api/client/evidence-pack/jobs/{id}/file` | GET | `CAP_REPORT_AUDIT_PACK` | read | |

No `enforce_feature()` in these handlers. Router-level `client_route_guard` retained for auth on non-migrated routes.

**Explicitly not migrated:** rent ops, approvals, integrations, assistant, profile, billing, onboarding extras, entitlements.

---

## ILP-4 migrated routes — dashboard, command centre, today/task, ledger (`routes/client.py`)

| Endpoint | Method | Capability | Action | Notes |
|----------|--------|------------|--------|-------|
| `/api/client/dashboard` | GET | `CAP_DASHBOARD_VIEW` | read | `include_score_headline=true` → in-handler `CAP_SCORE_VIEW` read |
| `/api/client/dashboard/roi-summary` | GET | `CAP_DASHBOARD_VIEW` | read | |
| `/api/client/command-center` | GET | `CAP_CMD_CTR_VIEW` | read | |
| `/api/client/protection-snapshot` | GET | `CAP_CMD_CTR_VIEW` | read | |
| `/api/client/priority-actions` | GET | `CAP_TODAY_VIEW` | read | |
| `/api/client/tasks/digest` | GET | `CAP_TODAY_VIEW` | read | |
| `/api/client/tasks` | GET | `CAP_TODAY_VIEW` | read | |
| `/api/client/priorities` | GET | `CAP_TODAY_VIEW` | read | |
| `/api/client/work-queue` | GET | `CAP_TODAY_VIEW` | read | |
| `/api/client/tasks/activity` | GET | `CAP_TODAY_VIEW` | read | |
| `/api/client/tasks/record-intent` | POST | `CAP_TODAY_ACT` | write | |
| `/api/client/tasks/override` | POST | `CAP_TODAY_ACT` | write | |
| `/api/client/ledger` | GET | `CAP_LEDGER_VIEW` | read | |
| `/api/client/ledger/export.csv` | GET | `CAP_LEDGER_EXPORT` | read | |

No `enforce_feature()` in 2C-2 handlers. Router-level `client_route_guard` retained for auth on non-migrated routes.

**Explicitly not migrated (remaining ILP-4):** rent ops, approvals, integrations, assistant, profile, billing, onboarding extras, entitlements.

---

## ILP-4 migrated modules — properties, portfolio, score/requirement (`routes/client.py` subset)

### `routes/properties.py` (full)

| Endpoint | Method | Capability | Action | Notes |
|----------|--------|------------|--------|-------|
| `/api/properties/create` | POST | `CAP_PROP_CREATE` | write | Plan property limit via `plan_registry.enforce_property_limit()` retained |
| `/api/properties/{id}` | PATCH | `CAP_PROP_EDIT` | write | `is_active=false` → in-handler `CAP_PROP_ARCHIVE` write |
| `/api/properties/{id}/requirements/mark-not-applicable` | POST | `CAP_REQ_MARK_N_A` | write | **Option A** — distinct from `CAP_REQ_RESOLVE` |
| `/api/properties/{id}/requirements/{id}` | PATCH | `CAP_REQ_RESOLVE` | write | `applicability=NOT_REQUIRED` → in-handler `CAP_REQ_MARK_N_A` write |
| `/api/properties/list` | GET | `CAP_PROP_VIEW` | read | |
| `/api/properties/bulk-import` | POST | `CAP_PROP_IMPORT` | write | |
| `/api/properties/upcoming-deadlines` | GET | `CAP_REQ_VIEW` | read | |
| `/api/properties/{id}/requirements` | GET | `CAP_REQ_VIEW` | read | |
| `/api/properties/{id}/requirements/sync` | POST | `CAP_REQ_RESOLVE` | write | |

No delete route exists; `CAP_PROP_DELETE` matrix row added for governance only. No `enforce_feature()` / `client_route_guard` in module.

### `routes/portfolio.py` (full)

| Endpoint | Method | Capability | Action |
|----------|--------|------------|--------|
| `/api/portfolio/compliance-summary` | GET | `CAP_SCORE_VIEW` | read |
| `/api/portfolio/properties/{id}/compliance-detail` | GET | `CAP_PROP_VIEW` | read |
| `/api/portfolio/properties/{id}/score-history` | GET | `CAP_SCORE_TREND` | read |
| `/api/portfolio/properties/{id}/timeline` | GET | `CAP_REQ_VIEW` | read |
| `/api/portfolio/properties/{id}/evidence` | GET | `CAP_EVIDENCE_VIEW` | read |
| `/api/portfolio/audit-timeline` | GET | `CAP_COMPLIANCE_ACTIVITY` | read |

Router-level `client_route_guard` removed. No hybrid permission logic in handlers.

### `routes/client.py` (2C-1 subset — score / property / requirement)

| Endpoint | Method | Capability | Action |
|----------|--------|------------|--------|
| `/api/client/compliance-score` | GET | `CAP_SCORE_VIEW` | read |
| `/api/client/compliance-score/trend` | GET | `CAP_SCORE_TREND` | read |
| `/api/client/score/timeline` | GET | `CAP_SCORE_TREND` | read |
| `/api/client/score-trend/portfolio` | GET | `CAP_SCORE_TREND` | read |
| `/api/client/score-trend/property/{id}` | GET | `CAP_SCORE_TREND` | read |
| `/api/client/score/changes` | GET | `CAP_SCORE_TREND` | read |
| `/api/client/compliance/activity` | GET | `CAP_COMPLIANCE_ACTIVITY` | read |
| `/api/client/compliance-score/explanation` | GET | `CAP_SCORE_EXPLAIN` | read |
| `/api/client/properties/{id}/compliance-score/explanation` | GET | `CAP_SCORE_EXPLAIN` | read |
| `/api/client/compliance-score/snapshot` | POST | `CAP_SCORE_SNAPSHOT` | write |
| `/api/client/properties` | GET | `CAP_PROP_VIEW` | read | (2A pilot, retained) |
| `/api/client/properties/{id}/requirements` | GET | `CAP_REQ_VIEW` | read |
| `/api/client/properties/{id}/requirements/explanation` | GET | `CAP_REQ_VIEW` | read |
| `/api/client/requirements` | GET | `CAP_REQ_VIEW` | read |
| `/api/client/properties/{id}/requirements/mark-not-applicable` | POST | `CAP_REQ_MARK_N_A` | write | **Changed from `CAP_REQ_RESOLVE` (Option A)** |

**Explicitly not migrated in 2C-1:** see Phase 2C-2 for dashboard/command-centre/today/ledger; 2C-3+ for evidence-pack and ops routes.

---

## Runtime contract extensions (2C-2)

New `_BASE_CAPABILITY_MATRIX` rows (schema unchanged):

| Capability | Plan key | Distinct from |
|------------|----------|---------------|
| `CAP_LEDGER_VIEW` | — (lifecycle matrix) | `CAP_SCORE_VIEW` |
| `CAP_LEDGER_EXPORT` | `reports_csv` | `CAP_LEDGER_VIEW` |

Plan keys added for existing caps used by 2C-2 routes: `CAP_DASHBOARD_VIEW`, `CAP_CMD_CTR_VIEW` → `compliance_dashboard`.

Portal ceilings updated for `BILLING_RECOVERY`, `READ_ONLY`, `SUSPENDED` (ledger read mirrors score view in recovery/read-only; export denied).

---

## Phase 2B Wave 1 migrated modules (CAP_* only)

### `routes/client_compliance_evidence.py` (full)

| Endpoint | Method | Capability | Action |
|----------|--------|------------|--------|
| `/api/client/compliance-evidence/org-review-queue` | GET | `CAP_EVIDENCE_VIEW` | read |
| `/api/client/properties/{id}/requirements/{id}/evidence-resolution` | GET | `CAP_EVIDENCE_VIEW` | read |
| `/api/client/properties/{id}/requirements/{id}/compliance-evidence` | GET | `CAP_EVIDENCE_VIEW` | read |
| `/api/client/properties/{id}/requirements/{id}/compliance-evidence` | POST | `CAP_REQ_RESOLVE` | write |
| `/api/client/properties/{id}/requirements/{id}/compliance-evidence/{id}/verification` | POST | `CAP_REQ_RESOLVE` | write |

### `routes/reports.py` (client routes — full)

| Endpoint | Method | Capability | Action | Notes |
|----------|--------|------------|--------|-------|
| `/api/reports/generate` | POST | `CAP_REPORT_GENERATE_PDF` | write | |
| `/api/reports`, `/api/reports/list` | GET | `CAP_REPORT_VIEW` | read | |
| `/api/reports/score-drivers.csv` | GET | `CAP_REPORT_GENERATE_CSV` | write | |
| `/api/reports/score-explanation.pdf` | GET | `CAP_REPORT_GENERATE_PDF` | write | |
| `/api/reports/compliance-summary` | GET | `CAP_REPORT_VIEW` + format assert | read/write | `format=pdf` → `CAP_REPORT_GENERATE_PDF`; `format=csv` → `CAP_REPORT_GENERATE_CSV` |
| `/api/reports/requirements` | GET | `CAP_REPORT_VIEW` + format assert | read/write | same pattern |
| `/api/reports/{report_id}/download` | GET | `CAP_REPORT_DOWNLOAD` | read | |
| `/api/reports/artifacts/{artifact_id}/download` | GET | `CAP_REPORT_DOWNLOAD` | read | |
| `/api/reports/available` | GET | `CAP_REPORT_VIEW` | read | |
| `/api/reports/schedules` | GET | `CAP_REPORT_SCHEDULE` | read | |
| `/api/reports/schedules` | POST | `CAP_REPORT_SCHEDULE` | write | |
| `/api/reports/schedules/{id}` | DELETE | `CAP_REPORT_SCHEDULE` | write | |
| `/api/reports/schedules/{id}/toggle` | PATCH | `CAP_REPORT_SCHEDULE` | write | |
| `/api/reports/professional/*` | GET | `CAP_REPORT_GENERATE_PDF` | write | compliance-summary, requirements, expiry-schedule |
| `/api/reports/professional/audit-log` | GET | `CAP_AUDIT_LOG_EXPORT` | read | |
| `/api/reports/audit-logs` | GET | — | — | **Admin only** (`admin_route_guard`); not customer lifecycle |

`CAP_REPORT_AUDIT_PACK` added to runtime matrix for governed audit-pack flows; **deferred** to Wave 2 (`client.py` evidence-pack routes).

No `enforce_feature()` remains in `reports.py` client handlers.

### `routes/documents.py` (client routes — full)

| Endpoint | Method | Capability | Action | Notes |
|----------|--------|------------|--------|-------|
| `/api/documents` | GET | `CAP_DOC_VIEW` | read | |
| `/api/documents/{id}/file` | GET | `CAP_DOC_VIEW` | read | |
| `/api/documents/{id}/extraction` | GET | `CAP_DOC_VIEW` | read | |
| `/api/documents/{id}/details` | GET | `CAP_DOC_VIEW` | read | |
| `/api/documents/upload` | POST | `CAP_DOC_UPLOAD` | write | |
| `/api/documents/bulk-upload` | POST | `CAP_DOC_BULK_ZIP` | write | |
| `/api/documents/zip-upload` | POST | `CAP_DOC_BULK_ZIP` | write | |
| `/api/documents/validate` | POST | `CAP_DOC_UPLOAD` | write | |
| `/api/documents/{id}` | DELETE | `CAP_DOC_UPLOAD` | write | |
| `/api/documents/{id}/apply-extraction` | POST | `CAP_DOC_UPLOAD` | write | |
| `/api/documents/{id}/reject-extraction` | POST | `CAP_DOC_UPLOAD` | write | |
| `/api/documents/{id}/reconcile-linkage` | POST | `CAP_DOC_UPLOAD` | write | |
| `/api/documents/analyze/{id}` | POST | `CAP_DOC_VIEW` | read | `return_advanced=true` → in-handler `CAP_AI_EXTRACTION_ADVANCED` write |

Admin routes (`/api/documents/admin/*`, verify/reject) remain **`admin_route_guard`** — not customer lifecycle.

No `enforce_feature()` / `require_feature()` remains in client document handlers.

---

## Phase 2A pilot routes (retained)

| Endpoint | Method | Capability | Action | File |
|----------|--------|------------|--------|------|
| `/api/client/properties` | GET | `CAP_PROP_VIEW` | read | `routes/client.py` |
| `/api/client/properties/{id}/requirements/mark-not-applicable` | POST | `CAP_REQ_MARK_N_A` | write | `routes/client.py` |
| `/api/reports/{report_id}/download` | GET | `CAP_REPORT_DOWNLOAD` | read | `routes/reports.py` |
| `/api/documents` | GET | `CAP_DOC_VIEW` | read | `routes/documents.py` |

- Dependency: `client_require_capability()` / `assert_client_capability()` in `middleware/capability_gating.py`
- Denied responses: governed `capability_denied` payload via `capability_denied_http_detail()`
- Tests: `test_account_capability_enforcement_pilot.py`, `test_account_capability_enforcement_wave1.py`, `test_account_capability_enforcement_wave2c1.py`, `test_account_capability_enforcement_wave2c2.py`

---

## Runtime contract extensions (2C-1)

New `_BASE_CAPABILITY_MATRIX` rows (schema unchanged):

| Capability | Plan key | Distinct from |
|------------|----------|---------------|
| `CAP_PROP_ARCHIVE` | — (lifecycle matrix) | `CAP_PROP_EDIT` |
| `CAP_PROP_DELETE` | — (matrix row; no route) | `CAP_PROP_ARCHIVE` |
| `CAP_PROP_IMPORT` | `document_upload_bulk_zip` | `CAP_PROP_CREATE` |
| `CAP_REQ_MARK_N_A` | — (lifecycle matrix) | **`CAP_REQ_RESOLVE` — not aliased (Option A)** |
| `CAP_REQ_COMPLETE` | — (matrix row; no route in 2C-1) | `CAP_REQ_RESOLVE` |
| `CAP_SCORE_EXPLAIN` | `compliance_score` | `CAP_SCORE_VIEW` |
| `CAP_SCORE_TREND` | `score_trending` | `CAP_SCORE_VIEW` |
| `CAP_SCORE_SNAPSHOT` | `compliance_score` | `CAP_SCORE_TREND` |
| `CAP_COMPLIANCE_ACTIVITY` | `compliance_dashboard` | `CAP_DASHBOARD_VIEW` |

Portal ceilings updated for `BILLING_RECOVERY`, `READ_ONLY`, `SUSPENDED` (read grants for score explain/trend/activity mirror `CAP_SCORE_VIEW` in recovery/read-only modes).

---

## Runtime contract extensions (Wave 1)

New `_BASE_CAPABILITY_MATRIX` rows (schema unchanged):

| Capability | Plan key | Distinct from |
|------------|----------|---------------|
| `CAP_REPORT_GENERATE_CSV` | `reports_csv` | `CAP_REPORT_GENERATE_PDF` |
| `CAP_AUDIT_LOG_EXPORT` | `audit_log_export` | `CAP_REPORT_VIEW` |
| `CAP_REPORT_AUDIT_PACK` | `audit_log_export` (matrix row; route deferred) | `CAP_AUDIT_LOG_EXPORT` |
| `CAP_DOC_BULK_ZIP` | `zip_upload` | `CAP_DOC_UPLOAD` |
| `CAP_AI_EXTRACTION_ADVANCED` | `ai_extraction_advanced` | `CAP_AI_ASSISTANT` |

Portal ceilings updated for `BILLING_RECOVERY`, `READ_ONLY`, `SUSPENDED`.

---

## Purpose

This document is the implementation verification checklist for `CAP_*` enforcement.

| Column | Meaning |
|--------|---------|
| **Capability** | Governed `CAP_*` identifier |
| **Runtime status** | Whether ILP-2 resolver produces a grant |
| **Enforcement status** | Phase 0–1 service / Phase 2+ route wiring |
| **Expected grant** | ACA matrix intent |
| **Read-only behaviour** | `READ` contract grant → `READ_ONLY` enforcement semantic |
| **Recovery path** | From `customer_experience.primary_cta` |
| **Regression** | Test reference |

---

## Enforcement semantics

| Contract grant | Enforcement semantic | Read action | Write action |
|----------------|---------------------|-------------|--------------|
| `ALLOW` | ALLOW | ✓ | ✓ |
| `READ` | **READ_ONLY** | ✓ | ✗ (governed reason) |
| `LIMITED` | LIMITED | ✓ | ✓ (grace-limited) |
| `DENY` | DENY | ✗ | ✗ |
| `HIDDEN` | HIDDEN | ✗ | ✗ |
| `PLAN_GATED` | Pre-resolved to ALLOW/DENY in contract | per resolved grant | per resolved grant |

**Source of truth:** `CapabilityEnforcementService` → Runtime Contract `capabilities` map only.

---

## Runtime-resolved capabilities (49) — ENFORCEMENT_READY

Wave 1 added five capabilities; Phase 2C-1 adds nine; Phase 2C-2 adds two ledger caps to the prior 47-capability runtime set.

| Capability | Runtime | Enforcement (2C-2) | Tests |
|------------|---------|---------------------|-------|
| `CAP_DASHBOARD_VIEW` | ✓ | **2C-2 client dashboard** | wave2c2 lifecycle matrix |
| `CAP_CMD_CTR_VIEW` | ✓ | **2C-2 command-centre + protection-snapshot** | wave2c2 lifecycle matrix |
| `CAP_TODAY_VIEW` | ✓ | **2C-2 today/tasks/priorities/work-queue** | wave2c2 lifecycle matrix |
| `CAP_TODAY_ACT` | ✓ | **2C-2 tasks/override + record-intent** | wave2c2 lifecycle matrix |
| `CAP_LEDGER_VIEW` | ✓ | **2C-2 ledger** | wave2c2 lifecycle matrix |
| `CAP_LEDGER_EXPORT` | ✓ | **2C-2 ledger CSV** | wave2c2 lifecycle matrix |

| Capability | Runtime | Enforcement (2C-1) | Tests |
|------------|---------|---------------------|-------|
| `CAP_PROP_VIEW` | ✓ | pilot + **2C-1 properties/portfolio/client** | wave2c1 lifecycle matrix |
| `CAP_PROP_CREATE` | ✓ | **2C-1 properties** | wave2c1 lifecycle matrix |
| `CAP_PROP_EDIT` | ✓ | **2C-1 properties** | wave2c1 lifecycle matrix |
| `CAP_PROP_ARCHIVE` | ✓ | **2C-1 properties** (conditional) | wave2c1 lifecycle matrix |
| `CAP_PROP_DELETE` | ✓ | matrix only (no route) | — |
| `CAP_PROP_IMPORT` | ✓ | **2C-1 properties** | wave2c1 lifecycle matrix |
| `CAP_REQ_VIEW` | ✓ | **2C-1 properties/portfolio/client** | wave2c1 lifecycle matrix |
| `CAP_REQ_RESOLVE` | ✓ | pilot evidence write + **2C-1 properties** | wave1 + wave2c1 |
| `CAP_REQ_MARK_N_A` | ✓ | **2C-1 properties + client** | wave2c1 lifecycle matrix |
| `CAP_REQ_COMPLETE` | ✓ | matrix only (no route in 2C-1) | — |
| `CAP_SCORE_VIEW` | ✓ | **2C-1 client + portfolio** | wave2c1 lifecycle matrix |
| `CAP_SCORE_EXPLAIN` | ✓ | **2C-1 client** | wave2c1 lifecycle matrix |
| `CAP_SCORE_TREND` | ✓ | **2C-1 client + portfolio** | wave2c1 lifecycle matrix |
| `CAP_SCORE_SNAPSHOT` | ✓ | **2C-1 client** | wave2c1 lifecycle matrix |
| `CAP_COMPLIANCE_ACTIVITY` | ✓ | **ILP-4 client analytics/activity-since + 2C-1 client + portfolio** | wave2c1 + evidence_pack_analytics lifecycle matrix |

| Capability | Runtime | Enforcement (Wave 1) | Tests |
|------------|---------|------------------------|-------|
| `CAP_EVIDENCE_VIEW` | ✓ | **Wave 1 routes** | wave1 lifecycle matrix |
| `CAP_REQ_RESOLVE` | ✓ | pilot + **Wave 1 evidence write** | wave1 lifecycle matrix |
| `CAP_REPORT_VIEW` | ✓ | **Wave 1 reports** | wave1 lifecycle matrix |
| `CAP_REPORT_GENERATE_PDF` | ✓ | **Wave 1 reports** | wave1 + plan-gated |
| `CAP_REPORT_GENERATE_CSV` | ✓ | **Wave 1 reports** | wave1 + plan-gated |
| `CAP_REPORT_DOWNLOAD` | ✓ | pilot + **Wave 1 reports** | wave1 lifecycle matrix |
| `CAP_REPORT_SCHEDULE` | ✓ | **Wave 1 reports** | wave1 lifecycle matrix |
| `CAP_AUDIT_LOG_EXPORT` | ✓ | **Wave 1 reports** | wave1 lifecycle matrix |
| `CAP_REPORT_AUDIT_PACK` | ✓ | **ILP-4 client evidence-pack jobs** | evidence_pack_analytics lifecycle matrix |
| `CAP_DOC_VIEW` | ✓ | pilot + **Wave 1 documents** | wave1 lifecycle matrix |
| `CAP_DOC_UPLOAD` | ✓ | **Wave 1 documents** | wave1 lifecycle matrix |
| `CAP_DOC_BULK_ZIP` | ✓ | **Wave 1 documents** | wave1 lifecycle matrix |
| `CAP_AI_EXTRACTION_ADVANCED` | ✓ | **Wave 1 analyze advanced** | wave1 + plan-gated |

(Remaining 25 capabilities from Phase 0–1 remain service-only until Wave 2+.)

---

## Wave 2C-2 lifecycle test coverage

`test_account_capability_enforcement_wave2c2.py` parametrizes:

`ACTIVE`, `TRIAL`, `GRACE_PERIOD`, `CANCELLATION_SCHEDULED`, `READ_ONLY`, `CANCELLED_IMMEDIATE`, `SUBSCRIPTION_EXPIRED`, `SUSPENDED`, `ARCHIVED`, `UNKNOWN`

Across ledger view/export, dashboard, command-centre, today tasks read, and today act write.

---

## Wave 2C-1 lifecycle test coverage

`test_account_capability_enforcement_wave2c1.py` parametrizes:

`ACTIVE`, `TRIAL`, `GRACE_PERIOD`, `CANCELLATION_SCHEDULED`, `READ_ONLY`, `CANCELLED_IMMEDIATE`, `SUBSCRIPTION_EXPIRED`, `SUSPENDED`, `ARCHIVED`, `UNKNOWN`

Across property view/create/edit/archive/import, requirement view/resolve/mark-not-applicable, score explain/trend/snapshot, compliance activity, and portfolio score-history/audit-timeline/compliance-summary.

---

## Wave 1 lifecycle test coverage

`test_account_capability_enforcement_wave1.py` parametrizes:

`ACTIVE`, `TRIAL`, `GRACE_PERIOD`, `CANCELLATION_SCHEDULED`, `READ_ONLY`, `CANCELLED_IMMEDIATE`, `SUBSCRIPTION_EXPIRED`, `SUSPENDED`, `ARCHIVED`, `UNKNOWN`

Across evidence read/write, reports view/CSV/schedule/audit-log, documents list/delete/details/analyze-advanced.

---

## Deferred (remaining ILP-4 backend)

- Onboarding extras, entitlements, jobs, sessions, frontend
- `client_route_guard` capability integration for remaining non-migrated routes
- Resolver matrix extension for remaining catalog-gap capabilities

---

## Deliverables

| Component | Path |
|-----------|------|
| Enforcement service | `backend/services/account_capability_enforcement.py` |
| Runtime contract | `backend/services/account_lifecycle_runtime_contract.py` |
| Route helpers | `backend/middleware/capability_gating.py` |
| Wave 1 routes | `client_compliance_evidence.py`, `reports.py`, `documents.py` |
| 2C-1 routes | `properties.py`, `portfolio.py`, `client.py` (score/requirement subset) |
| 2C-2 routes | `client.py` (dashboard/command-centre/today/ledger subset) |
| Unit tests | `test_account_capability_enforcement.py` |
| Pilot tests | `test_account_capability_enforcement_pilot.py` |
| Wave 1 tests | `test_account_capability_enforcement_wave1.py` |
| 2C-1 tests | `test_account_capability_enforcement_wave2c1.py` |
| 2C-2 tests | `test_account_capability_enforcement_wave2c2.py` |
| Audit evidence | `docs/audit/account_lifecycle_ilp_04/` |

---

## Regression proof (2C-2)

- Dashboard, command-centre, today/task, and ledger routes use `client_require_capability()` only — no `enforce_feature()` in 2C-2 handlers
- `CAP_LEDGER_VIEW` / `CAP_LEDGER_EXPORT` added to runtime matrix; export plan-gated via `reports_csv`
- Optional dashboard score headline uses in-handler `CAP_SCORE_VIEW` assert
- Evidence-pack, analytics, tenant, and ops routes **not** migrated

---

## Regression proof (2C-1)

- `CAP_REQ_MARK_N_A` is **not** aliased to `CAP_REQ_RESOLVE` (Option A governance decision)
- `properties.py` and `portfolio.py` module-complete — no `enforce_feature()` / hybrid guards
- `client.py` 2C-1 subset only; router-level `client_route_guard` retained for non-migrated routes

---

## Regression proof (Wave 1)

- `client_route_guard` unchanged in `middleware/__init__.py`
- Runtime Contract **schema** unchanged (new capability rows only)
- `client.py` evidence-pack routes **not** migrated
- Non-Wave-1 routes may still use `enforce_feature()`
- Frontend unchanged
