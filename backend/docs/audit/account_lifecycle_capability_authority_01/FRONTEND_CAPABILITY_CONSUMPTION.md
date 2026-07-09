# Frontend Capability Consumption

**Programme:** ACCOUNT-LIFECYCLE-CAPABILITY-AUTHORITY-01  
**Authority version:** `account_capability_v1`  
**Parent:** `ACCOUNT_FEATURE_CAPABILITY_MATRIX.md`

Phase 8 audit: every client portal page and its capability consumption. **Policy:** no component infers subscription state from Stripe or `canonical_entitlement_state`.

---

## Global shell

| Component | Current consumption | Required consumption | Fallback |
|-----------|--------------------|-----------------------|----------|
| `ProtectedRoute` | JWT only | `CAP_AUTH_LOGIN` + lifecycle-contract | Redirect login |
| `ClientPortalLayout` | portal-context poll | `polling_policy` from contract | Circuit breaker |
| `EntitlementsContext` | `/client/entitlements` features | Effective `CAP_*` map | Lifecycle screen |
| `EntitlementProtectedRoute` | `requiredFeature` | `requiredCapabilities[]` | Upgrade or recovery CTA |
| `ErrorBanner` | Raw API detail | Safe string only | Never render objects |

---

## Page matrix

| Route | Capabilities | Portal mode behaviour | Read-only | Upgrade | Recovery |
|-------|--------------|----------------------|-----------|---------|----------|
| `/dashboard` | `CAP_DASHBOARD_VIEW` | Full or recovery screen | READ_ONLY widgets | Plan gates | BILLING_RECOVERY redirect |
| `/today` | `CAP_TODAY_VIEW`, `CAP_TODAY_ACT` | Full or locked | DENY actions | — | Recovery screen |
| `/command-center` | `CAP_CMD_CTR_VIEW` | Full or locked | READ widgets | Plan | Recovery |
| `/work-queue` | `CAP_WORK_QUEUE_VIEW` | Same as today | — | — | Recovery |
| `/properties` | `CAP_PROP_VIEW` | Full / read / locked | View only | — | Export CTA |
| `/properties/create` | `CAP_PROP_CREATE` | Hide if DENY | — | — | — |
| `/properties/:id` | `CAP_PROP_VIEW`, edit caps | Tab gating | View tabs | `hasFeature` → PLAN_GATED only | — |
| `/requirements` | `CAP_REQ_VIEW`, `CAP_REQ_RESOLVE` | Full / read | No resolve | — | — |
| `/documents` | `CAP_DOC_VIEW`, `CAP_DOC_UPLOAD` | Full / read | No upload | ZIP upgrade | — |
| `/reports/*` | `CAP_REPORT_*` | Catalog / read | Download only | PDF/CSV plan | — |
| `/compliance-score` | `CAP_SCORE_*` | Full / read | View only | Trend upgrade | — |
| `/calendar` | `CAP_CALENDAR_VIEW` | Plan + lifecycle | — | Plan | — |
| `/assistant` | `CAP_AI_ASSISTANT` | Lifecycle + plan | — | Future plan | — |
| `/settings/billing` | `CAP_BILLING_*`, `CAP_SUB_*` | Always in recovery modes | — | — | Primary CTA |
| `/settings/*` | `CAP_PROFILE_*` | Profile always except DELETED | — | — | — |
| `/integrations` | `CAP_INTEGRATION_WEBHOOKS` | EntitlementProtectedRoute | — | Upgrade | — |
| `/operations/*` | `CAP_OPS_*` | Ops flags + lifecycle | — | Per feature | — |
| `/tenant/*` | `CAP_TENANT_*` | Plan + lifecycle | — | Upgrade | — |
| `/audit-log` | `CAP_AUDIT_LOG_VIEW` | Lifecycle | — | Export plan | — |
| `/help` | `CAP_SUPPORT_ACCESS` | Always | — | — | — |

---

## Polling by portal mode

| Component | FULL_ACCESS | BILLING_RECOVERY | SUSPENDED |
|-----------|-------------|------------------|-----------|
| Entitlements fetch | On focus | **Off** | **Off** |
| portal-context | On focus | **Off** | **Off** |
| Dashboard cache | On mount | **Off** | **Off** |
| Today items | On mount | **Off** | **Off** |

---

## Defect correlation (audit)

| Page | Defect | Classification |
|------|--------|----------------|
| `/today` | Error Boundary on 403 detail | CUSTOMER_EXPERIENCE_GAP |
| `/properties` | 403 storm | PORTAL_MODE_GAP |
| All routes | Mount while cancelled | PORTAL_MODE_GAP |

---

**Note:** This content supports Phase 8 acceptance criteria and is referenced from `ACCOUNT_CAPABILITY_AUTHORITY_EVIDENCE.json`. Primary deliverable list uses the eight named files; frontend audit is incorporated here and in the feature matrix.

---

**Outcome:** Frontend capability consumption audit complete
