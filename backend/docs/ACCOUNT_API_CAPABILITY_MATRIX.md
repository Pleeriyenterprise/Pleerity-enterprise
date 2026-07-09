# Account API Capability Matrix

**Programme:** ACCOUNT-LIFECYCLE-CAPABILITY-AUTHORITY-01  
**Authority version:** `account_capability_v1`  
**Parent:** `ACCOUNT_CAPABILITY_AUTHORITY.md`

Audits customer-facing APIs. **Two-phase check (policy):** lifecycle capability grant → plan PLAN_GATED overlay.

**Failure behaviour:** Lifecycle DENY → safe string + `lifecycle_redirect` (ILP-4). Plan DENY → `upgrade_required` with feature key. Never return raw `canonical_entitlement_state` to frontend.

---

## Global guards

| Guard | Applies | Lifecycle dependency | Capability |
|-------|---------|---------------------|------------|
| JWT auth | All `/api/client/*` | ARCHIVED/DELETED → 401/403 | `CAP_AUTH_LOGIN` |
| `client_route_guard` | Non-billing `/api/client/*` | SUSPENDED/CANCELLED → 403 | Shell block bundle |
| Billing exempt | `/api/billing/*` | Always reachable for recovery | `CAP_BILLING_*` |

---

## Authentication (`/api/auth/*`)

| Endpoint | Method | Required capabilities | Portal mode | Failure |
|----------|--------|----------------------|-------------|---------|
| `/api/auth/login` | POST | `CAP_AUTH_LOGIN` | Not ARCHIVED/DELETED | 401 + message |
| `/api/auth/logout` | POST | `CAP_AUTH_LOGOUT` | Any authenticated | 200 |
| `/api/auth/refresh` | POST | `CAP_AUTH_SESSION_RECOVERY` | Valid refresh | 401 session expired |
| `/api/auth/forgot-password` | POST | `CAP_AUTH_PASSWORD_RESET` | Public | 200/404 safe |

---

## Billing (`/api/billing/*`)

| Endpoint | Method | Required capabilities | Lifecycle | Failure |
|----------|--------|----------------------|-----------|---------|
| `/api/billing/status` | GET | `CAP_BILLING_VIEW` | All except DELETED | 200 |
| `/api/billing/checkout` | POST | `CAP_BILLING_CHECKOUT` | PAYMENT_REQUIRED, recovery | 403 lifecycle |
| `/api/billing/cancel` | POST | `CAP_SUB_CANCEL` | ACTIVE, TRIAL, GRACE | 403 |
| `/api/billing/invoices` | GET | `CAP_BILLING_INVOICES` | Billing exempt | 200 |
| `/api/billing/payment-methods` | * | `CAP_BILLING_PAYMENT_METHODS` | Billing exempt | 403 |

---

## Client core (`/api/client/*`)

| Endpoint | Method | Required capabilities | Plan gate | Failure |
|----------|--------|----------------------|-----------|---------|
| `/api/client/dashboard` | GET | `CAP_DASHBOARD_VIEW` | `compliance_dashboard` | 403 lifecycle / upgrade |
| `/api/client/portal-context` | GET | `CAP_DASHBOARD_VIEW` | — | 403 → no poll storm |
| `/api/client/entitlements` | GET | `CAP_PROFILE_VIEW` | — | 403 lifecycle |
| `/api/client/entitlements/context` | GET | `CAP_DASHBOARD_VIEW` | — | 403 safe |
| `/api/client/lifecycle-contract` | GET | `CAP_PROFILE_VIEW` | — | **Future ILP-2** |
| `/api/client/properties` | GET | `CAP_PROP_VIEW` | — | 403 / READ tier |
| `/api/client/properties` | POST | `CAP_PROP_CREATE` | — | 403 |
| `/api/client/properties/{id}` | PATCH | `CAP_PROP_EDIT` | — | 403 |
| `/api/client/properties/{id}/requirements` | GET | `CAP_REQ_VIEW` | — | 403 / READ |
| `/api/client/requirements` | GET | `CAP_REQ_VIEW` | — | 403 / READ |
| `/api/client/properties/{id}/requirements/mark-not-applicable` | POST | `CAP_REQ_MARK_N_A` | — | 403 |
| `/api/client/documents` | GET | `CAP_DOC_VIEW` | — | 403 / READ |
| `/api/client/compliance-score` | GET | `CAP_SCORE_VIEW` | `compliance_score` | 403 |
| `/api/client/compliance-score/explanation` | GET | `CAP_SCORE_EXPLAIN` | `compliance_score` | 403 |
| `/api/client/score-trend/*` | GET | `CAP_SCORE_TREND` | `score_trending` | 403 |
| `/api/client/command-center` | GET | `CAP_CMD_CTR_VIEW` | `compliance_dashboard` | 403 |
| `/api/client/priority-actions` | GET | `CAP_TODAY_VIEW` | — | 403 |
| `/api/client/tasks/*` | * | `CAP_TODAY_ACT` | — | 403 |
| `/api/client/ledger` | GET | `CAP_LEDGER_VIEW` | — | 403 / READ |
| `/api/client/ledger/export.csv` | GET | `CAP_LEDGER_EXPORT` | `reports_csv` | 403 |
| `/api/client/evidence-pack/jobs` | POST/GET | `CAP_REPORT_AUDIT_PACK` | `audit_log_export` | 403 |
| `/api/client/analytics/*` | * | `CAP_COMPLIANCE_ACTIVITY` | `compliance_dashboard` | 403 |
| `/api/client/onboarding/*` | * | `CAP_BILLING_CHECKOUT` | — | Onboarding scope |
| `/api/client/settings/jurisdiction` | * | `CAP_PROFILE_JURISDICTION` | — | 403 |
| `/api/client/branding/*` | * | `CAP_BRANDING_EDIT` | `white_label_reports` | 403 upgrade |
| `/api/client/contractors/*` | * | `CAP_OPS_CONTRACTORS` | ops flag | 403 |
| `/api/client/tenants/*` | * | `CAP_TENANT_MANAGE` | `tenant_portal` | 403 |
| `/api/client/compliance-pack/{id}/*` | GET | `CAP_REPORT_DOWNLOAD` | `reports_pdf` | 403 |

---

## Today (`/api/today/*`)

| Endpoint | Method | Required capabilities | Failure |
|----------|--------|----------------------|---------|
| `/api/today/items` | GET | `CAP_TODAY_VIEW` | 403 safe string (not object) |
| `/api/today/items/{id}/act` | POST | `CAP_TODAY_ACT` | 403 |

---

## Documents (`/api/documents/*`)

| Endpoint | Method | Required capabilities | Plan gate | Failure |
|----------|--------|----------------------|-----------|---------|
| `/api/documents/upload` | POST | `CAP_DOC_UPLOAD` | `document_upload_single` | 403 |
| `/api/documents/bulk-zip` | POST | `CAP_DOC_BULK_ZIP` | `zip_upload` | 403 upgrade |
| `/api/documents/{id}` | GET | `CAP_DOC_VIEW` | — | 403 / READ |
| `/api/documents/{id}` | DELETE | `CAP_DOC_DELETE` | — | 403 |
| `/api/documents/{id}/replace` | POST | `CAP_DOC_REPLACE` | `document_upload_single` | 403 |

---

## Reports (`/api/reports/*`)

| Endpoint | Method | Required capabilities | Plan gate | Failure |
|----------|--------|----------------------|-----------|---------|
| `/api/reports/catalog` | GET | `CAP_REPORT_VIEW` | — | 403 |
| `/api/reports/generate/pdf/*` | POST | `CAP_REPORT_GENERATE_PDF` | `reports_pdf` | 403 |
| `/api/reports/generate/csv/*` | POST | `CAP_REPORT_GENERATE_CSV` | `reports_csv` | 403 |
| `/api/reports/download/*` | GET | `CAP_REPORT_DOWNLOAD` | `reports_pdf` | 403 / READ |
| `/api/reports/schedule/*` | * | `CAP_REPORT_SCHEDULE` | `scheduled_reports` | 403 |
| `/api/reports/share/*` | POST | `CAP_REPORT_SHARE` | `reports_pdf` | 403 |

---

## Client maintenance / operations (`/api/client/maintenance/*`, etc.)

| Endpoint prefix | Required capabilities | Ops flag |
|-----------------|----------------------|----------|
| `/api/client/maintenance/*` | `CAP_OPS_MAINTENANCE` | `maintenance_workflows` |
| `/api/client/compliance-evidence/*` | `CAP_EVIDENCE_*` | — |
| `/api/client/compliance-execution/*` | `CAP_REQ_RESOLVE` | `compliance_engine` |
| `/api/client/rent-operations/*` | `CAP_OPS_RENT` | — |
| `/api/client/approvals/*` | `CAP_OPS_APPROVALS` | `compliance_engine` |

---

## Integrations (`/api/client-data/v1/*`)

| Endpoint | Required capabilities | Plan gate |
|----------|----------------------|-----------|
| Read API routes | `CAP_INTEGRATION_READ_API` | `webhooks` |
| Webhook config | `CAP_INTEGRATION_WEBHOOKS` | `webhooks` |

---

## API authorisation pattern (target)

```python
# Policy — not implemented
grant = capability_resolver(client, "CAP_REPORT_GENERATE_PDF")
if grant == DENY:
    raise lifecycle_forbidden(redirect="/settings/billing")
if grant == PLAN_GATED and not plan_allows("reports_pdf"):
    raise upgrade_required("reports_pdf")
```

**Current:** `plan_registry.enforce_feature` only — **API_MAPPING_GAP** (ACA-004).

---

## Inconsistencies (audit)

| Issue | Classification |
|-------|----------------|
| Some 403 return string; others structured dict with `canonical_entitlement_state` | API_MAPPING_GAP |
| Billing exempt but entitlements 403 causes frontend storm | PORTAL_MODE_GAP |
| Read tier not implemented for recovery states | SECURITY_GAP / ACA-009 |

---

**Outcome:** `ACCOUNT_API_CAPABILITY_MATRIX_COMPLETE`
