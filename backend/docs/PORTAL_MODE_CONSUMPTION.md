# Portal Mode Consumption (ILP-3)

**Programme:** ILP-3-PORTAL-MODE-CONSUMPTION-01  
**Parent:** `ACCOUNT_PORTAL_MODE_AUTHORITY.md`, `ACCOUNT_RUNTIME_API.md`

---

## Purpose

ILP-3 establishes Portal Mode as the **single presentation authority** for the customer portal. Pages consume `GET /api/client/lifecycle-runtime` and render governed copy, banners, and navigation hints.

ILP-3 does **not** enforce permissions. `hasFeature()`, middleware, and API guards remain unchanged until ILP-4.

---

## Architecture

```
GET /api/client/lifecycle-runtime
        ↓
LifecycleRuntimeProvider (App.js)
        ↓
PortalModeContext (usePortalMode)
        ↓
LifecycleShell + page banners + navigation_policy hints
```

---

## Frontend modules

| Module | Role |
|--------|------|
| `contexts/LifecycleRuntimeContext.js` | Fetch/cache runtime contract |
| `components/lifecycle/LifecycleShell.jsx` | Portal-wide lifecycle banner + CTAs |
| `components/lifecycle/LifecycleRuntimeDiagnostics.jsx` | Dev diagnostics (`?lifecycle_debug=1`) |
| `utils/portalNavigationPolicy.js` | Annotate nav items from `navigation_policy` |
| `components/client/ClientPortalPatterns.jsx` | `PortalPageShell` / `PortalPageWithLifecyclePresentation` |

---

## Portal modes

`FULL_ACCESS`, `READ_ONLY`, `GRACE`, `PAYMENT_REQUIRED`, `BILLING_RECOVERY`, `SUSPENDED`, `ARCHIVED`, `ACCOUNT_DELETED`

Each migrated page consumes `portalMode` via `usePortalMode()` or inherits presentation from `LifecycleShell` / `PortalModePageBanner`.

---

## Migration rules

1. **No hybrid inference** — migrated pages must not combine `portalMode` with `subscription_status` / `canonical_entitlement_state` for presentation.
2. **Billing exception (transitional)** — `BillingPage` prefers `customer_experience.current_state_label` when runtime is available; falls back to billing API only when runtime unavailable.
3. **Permissions unchanged** — `hasFeature()` and `EntitlementProtectedRoute` remain authoritative for access.

---

## Page migration inventory

| Page | Integration |
|------|-------------|
| Dashboard | `PortalPageWithLifecyclePresentation` |
| Today | `PortalModePageBanner` |
| Properties | `PortalPageShell` (banner embedded) |
| Property Detail | `PortalPageWithLifecyclePresentation` |
| Requirements | `PortalModePageBanner` |
| Documents | `PortalModePageBanner` |
| Reports | `PortalModePageBanner` |
| Billing | Runtime `customer_experience` for access label |
| Profile | `PortalModePageBanner` |
| Settings | `PortalModePageBanner` in `SettingsLayout` |
| Command Centre | `PortalModePageBanner` |
| Compliance Score | `PortalModePageBanner` |
| All ClientPortal routes | `LifecycleShell` in `ClientPortalLayout` |

---

## Deferred enforcement (ILP-4+)

- Capability grant enforcement
- API mutation guards from `capabilities` map
- Replacing `hasFeature()` for lifecycle decisions
- Session invalidation (ILP-7)

---

## Relation to governance

| Document | Usage |
|----------|-------|
| APMA | Portal mode definitions |
| Runtime Contract | API + schema |
| Customer Experience Authority | Copy templates via `customer_experience` |
| ACA | Capability map consumed in ILP-4 only |
