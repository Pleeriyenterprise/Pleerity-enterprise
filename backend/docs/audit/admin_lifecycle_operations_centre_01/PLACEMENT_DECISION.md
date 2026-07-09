# Placement Decision — Admin Lifecycle Operations Centre

**Programme:** ADMIN-LIFECYCLE-OPERATIONS-CENTRE-01  
**Decision date:** 2026-07-09 UTC  

## Chosen placement

**New tab: "Lifecycle ops" on the existing Client Control Panel**

- **Frontend:** `AdminClientControlPanelPage.js` → tab id `lifecycle-ops` → `AdminLifecycleOperationsPanel.jsx`
- **Route:** `/admin/clients/:clientId` (same page, new tab)
- **API:** `GET/POST /api/admin/clients/{client_id}/lifecycle-operations/*`

---

## Options evaluated

### Option A — Tab on Client Control Panel (SELECTED)

| Criterion | Assessment |
|-----------|------------|
| Customer context | Already the admin's primary account detail view |
| Search/select flow | Existing client search and deep-link by `clientId` |
| Overlap with billing tab | Billing tab shows summary; lifecycle ops adds authority + actions without removing billing tab |
| Scalability | Per-client panel composes; fleet ops stay in Billing Centre |
| Safety | Actions are governed mutations on an account already under admin review |

**Why selected:** Support workflow is "open client → diagnose → act". Control Panel is the natural anchor. Adds Runtime Contract visibility without a new navigation item.

### Option B — Extend Billing Centre only (REJECTED as sole placement)

Billing Centre is optimized for **fleet** reconciliation, plan changes, and recovery checkout. It already has sync and batch reconcile. Adding Runtime Contract and capability matrix would blur billing vs lifecycle concerns and duplicate client selection UX.

**Disposition:** Deep links from lifecycle ops → Billing Centre for recovery checkout and plan changes.

### Option C — Admin Ops / System Health (REJECTED)

Platform-wide dashboards lack per-customer context and governed per-client mutations.

### Option D — New dedicated page (REJECTED)

Would duplicate client search, break existing admin IA, and fragment account detail. Only justified if no suitable parent exists — audit found Client Control Panel suitable.

### Option E — Extend Billing tab inline (REJECTED)

Billing tab is already dense (receipts, entitlements, webhooks). A separate tab keeps diagnostics readable and allows independent refresh without reloading entire control panel.

---

## Cross-links (avoid duplication)

| Need | Where admin goes |
|------|------------------|
| Recovery checkout / fleet recovery | Billing Centre → Recovery tab (`/admin/billing?tab=recovery&client=...`) |
| Plan change / full billing snapshot | Billing Centre (`/admin/billing?client=...`) |
| Webhook ingress health (platform) | System Health |
| Fleet Stripe batch reconcile | Billing Centre job action |

---

## Implementation summary

```
AdminClientControlPanelPage
  ├── Overview (existing)
  ├── Billing (existing summary)
  ├── Lifecycle ops (NEW) ──► AdminLifecycleOperationsPanel
  │     ├── Read: lifecycle + billing mirror + webhooks + capabilities + audit
  │     └── Write: refresh runtime · reconcile · resume · flag support
  └── … other tabs
```

---

## Acceptance alignment

- Safest placement audited and justified: **yes**
- No duplicated lifecycle authority: **yes** (services delegated)
- No new standalone page unless unsuitable: **yes** (existing structure extended)
