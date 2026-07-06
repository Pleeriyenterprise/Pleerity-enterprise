# Account Runtime Consumers

**Programme:** ACCOUNT-LIFECYCLE-RUNTIME-CONTRACT-01  
**Parent:** `ACCOUNT_LIFECYCLE_RUNTIME_CONTRACT.md`  
**Reconciliation:** `ACCOUNT_LIFECYCLE_GOVERNANCE_IMPLEMENTATION_MAPPING.md`

Inventory of every subsystem: current behavioural input, runtime contract input, migration status.

**ILP-1–7 implemented on develop.** Migration column references **implementation programme** numbers. Remaining cutover work is tracked under reconciled **ILP-10 Platform Convergence**.

**Legend — migration strategy:**

| Code | Meaning |
|------|---------|
| **R** | Replace input with `AccountLifecycleRuntimeContract` |
| **D** | Derive from contract field only |
| **P** | Phase: parallel read during migration, then cutover |
| **K** | Keep orthogonal (not lifecycle behavioural) |

---

## Authentication & session

| Subsystem | Module | Current input | Future input | Fields used | Migration |
|-----------|--------|---------------|--------------|-------------|-----------|
| JWT middleware | `middleware/__init__.py` | JWT claims, session_version | Contract + session_policy | `session_policy.jwt_valid`, `force_reauth` | ✓ ILP-5 (partial legacy paths remain → ILP-10) |
| Login | `routes/auth.py` | credentials, client status | lifecycle_state ARCHIVED/DELETED deny | `lifecycle_state` | ✓ ILP-2 |
| Session refresh | auth routes | session_version | `session_policy`, `runtime_version` | `entitlements_version` | ✓ ILP-5 |

---

## Authorisation

| Subsystem | Module | Current input | Future input | Fields used | Migration |
|-----------|--------|---------------|--------------|-------------|-----------|
| client_route_guard | middleware | `canonical_entitlement_state` (legacy read) | `portal_mode`, `capabilities`, lifecycle denial authority | DENY operational caps | ✓ ILP-4 + ILP-7 (legacy canon read → ILP-10) |
| enforce_feature | plan_registry | feature_key, billing bands | `capabilities[CAP_*]` | Pre-resolved grant | Partial → ILP-10 |
| entitlement_access | services | multiple bands | Contract snapshot | `capabilities` | Partial → ILP-10 |

---

## Frontend shell

| Subsystem | Module | Current input | Future input | Fields used | Migration |
|-----------|--------|---------------|--------------|-------------|-----------|
| ProtectedRoute | `ProtectedRoute.js` | JWT only | `lifecycle-runtime` | `portal_mode` | R (ILP-5) |
| EntitlementsContext | `EntitlementsContext.js` | `/client/entitlements` | `/client/lifecycle-runtime` | `capabilities`, `plan` | P → R (ILP-5) |
| ClientPortalLayout | `ClientPortalLayout.jsx` | portal-context poll | `polling_policy` | `polling_policy.enabled` | R (ILP-5) |
| EntitlementProtectedRoute | `EntitlementProtectedRoute.js` | `requiredFeature` | `requiredCapabilities` + contract | `capabilities` | R (ILP-5) |
| ErrorBanner | `ErrorBanner.jsx` | raw API detail | safe strings from contract errors | — | R (ILP-6) |
| Navigation | nav config | `hasFeature` | `navigation_policy` + capabilities | `hidden_routes`, grants | R (ILP-5) |

---

## Frontend pages

| Page / route | Current input | Future input | Key capabilities | Migration |
|--------------|---------------|--------------|------------------|-----------|
| `/dashboard` | entitlements + dashboard API | contract + API | `CAP_DASHBOARD_VIEW` | ILP-5 |
| `/today` | today API | contract | `CAP_TODAY_VIEW`, `CAP_TODAY_ACT` | ILP-5 |
| `/command-center` | command-center API | contract | `CAP_CMD_CTR_VIEW` | ILP-5 |
| `/properties` | properties API | contract | `CAP_PROP_VIEW` | ILP-5 |
| `/properties/create` | — | contract | `CAP_PROP_CREATE` | ILP-5 |
| `/requirements` | requirements API | contract | `CAP_REQ_VIEW`, `CAP_REQ_RESOLVE` | ILP-5 |
| `/documents` | documents API | contract | `CAP_DOC_*` | ILP-5 |
| `/reports` | reports + enforce_feature | contract | `CAP_REPORT_*` | ILP-5, ILP-6 |
| `/compliance-score` | score API | contract | `CAP_SCORE_*` | ILP-5 |
| `/settings/billing` | `/billing/status`, Stripe fields | contract subset | `CAP_BILLING_*`, `customer_experience` | ILP-3, ILP-5 |
| `/settings/*` profile | profile APIs | contract | `CAP_PROFILE_*` | ILP-5 |
| `/operations/*` | hasFeature ops flags | contract | `CAP_OPS_*` | ILP-5 |
| `/integrations` | webhooks feature | contract | `CAP_INTEGRATION_WEBHOOKS` | ILP-5 |
| `/tenant/*` | tenant_portal feature | contract | `CAP_TENANT_*` | ILP-5 |
| `/assistant` | — | contract | `CAP_AI_ASSISTANT` | ILP-5 |

Full page audit: `FRONTEND_CAPABILITY_CONSUMPTION.md`.

---

## Customer APIs

| API area | Routes | Current input | Future input | Migration |
|----------|--------|---------------|--------------|-----------|
| Client core | `routes/client.py` | guard + enforce_feature | contract capabilities | ILP-4, ILP-6 |
| Documents | `routes/documents.py` | enforce_feature | `CAP_DOC_*` | ILP-4 |
| Reports | `routes/reports.py` | enforce_feature | `CAP_REPORT_*` | ILP-4 |
| Billing | `routes/client_billing.py` | billing exempt | `CAP_BILLING_*` (always allowed subset) | ILP-4 |
| Today | today routes | guard | `CAP_TODAY_*` | ILP-4 |
| Maintenance | `client_maintenance.py` | ops flags | `CAP_OPS_*` | ILP-4 |
| Compliance evidence | `client_compliance_evidence.py` | guard | `CAP_EVIDENCE_*` | ILP-4 |

See `ACCOUNT_API_CAPABILITY_MATRIX.md` for endpoint-level mapping.

---

## Domain authorities (orthogonal logic, lifecycle access from contract)

| Authority | Behaviour logic | Access / visibility input | Migration |
|-----------|----------------|---------------------------|-----------|
| Requirement Authority | obligation semantics | `CAP_REQ_*` from contract | K logic, R access |
| Lifecycle Authority (req) | requirement states | `CAP_REQ_RESOLVE` | K logic, R access |
| Evidence Authority | evidence truth | `CAP_EVIDENCE_*`, `CAP_DOC_*` | K logic, R access |
| Score Authority | score calculation | `CAP_SCORE_*` visibility | K logic, R access |
| Today Authority | task ranking | `CAP_TODAY_*` | K logic, R access |
| Command Centre Authority | aggregation | `CAP_CMD_CTR_VIEW` | K logic, R access |
| Report Presentation Authority | PDF layout | `CAP_REPORT_GENERATE_*` eligibility | K logic, R access |
| Communication Authority | channel rules | `communication_policy` | D from contract |
| Email Presentation Authority | email layout | template_family from contract | D from contract |
| Navigation Authority | nav structure | `navigation_policy` | D from contract |

---

## Background & workers

| Worker | Module | Current input | Future input | Fields | Migration |
|--------|--------|---------------|--------------|--------|-----------|
| Daily reminders | `jobs.py` | `clients.subscription_status`, `entitlement_status` | contract snapshot | `background_policy.reminders`, `communication_policy` | R (ILP-8) |
| Monthly digest | `jobs.py` | same | contract | `background_policy.digest` | R (ILP-8) |
| Scheduled reports | `jobs.py` | ENABLED + feature | contract | `background_policy.scheduled_reports` | R (ILP-8) |
| Compliance check | `jobs.py` | partial | contract | `background_policy.compliance_monitoring` | R (ILP-8) |
| Lifecycle sync | `subscription_lifecycle_service` | Stripe (write path) | **Producer** — invalidates runtime | triggers rebuild | K write, R invalidate |
| Notification orchestrator | `notification_orchestrator.py` | entitlement_status | contract | `communication_policy` | R (ILP-8) |
| Score engine | score services | not gated | contract | `background_policy.score_recalculation` | R (ILP-8) |
| Risk engine | predictive services | ops flags | contract | `background_policy.risk_recalculation` | R (ILP-8) |
| Extraction queue | document workers | partial | contract | `CAP_AI_EXTRACTION_*` | R (ILP-8) |
| Automation centre | admin automation | admin scope | admin contract view | System | K |

---

## Billing (fact source — not behavioural consumer)

| Subsystem | Role | Migration |
|-----------|------|-----------|
| Stripe webhooks | Fact writer → resolver invalidation | K (ILP-9 invalidation) |
| `billing_stripe_sync_service` | Persists facts | K |
| `subscription_lifecycle_service` | Derives bands → feeds ILP-1 | Becomes resolver input (ILP-1) |
| BillingPage checkout | UI + Stripe | Consumes `customer_experience`, `CAP_BILLING_*` | ILP-3 |

Billing APIs remain **recovery surface**; they do not re-derive `portal_mode`.

---

## Admin

| Subsystem | Current input | Future input | Migration |
|-----------|---------------|--------------|-----------|
| Admin client control panel | raw billing fields | contract diagnostic view | P (ILP-2 admin endpoint) |
| Admin billing | Stripe + billing | facts + contract | P |
| Admin reinstatement | manual | triggers resolver rebuild | ILP-9 |

Admin **never** bypasses resolver for customer-facing behaviour.

---

## Mobile (future)

| Consumer | Future input | Notes |
|----------|--------------|-------|
| Native app shell | `GET /api/client/lifecycle-runtime` | Same contract as web |
| Push notifications | `communication_policy` | No local Stripe inference |

---

## Producer vs consumer summary

| Role | Components |
|------|------------|
| **Producers (facts)** | Stripe, billing sync, org lifecycle service |
| **Resolver (single owner)** | ILP-1 + ILP-2 Runtime Contract Resolver |
| **Consumers (read only)** | All rows above |

---

## Cutover order per consumer

1. ILP-2: expose contract API (parallel)
2. ILP-4: API checks contract (backend)
3. ILP-5: frontend provider (parallel with entitlements)
4. ILP-8: jobs load snapshot
5. ILP-10: remove `hasFeature` lifecycle usage, remove guard band reads

---

**Outcome:** `ACCOUNT_RUNTIME_CONSUMERS_COMPLETE`
