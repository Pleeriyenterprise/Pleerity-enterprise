# Placement Review — Phase 2

**Programme:** ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01  

## Decision: extend in place

Phase 2 content lives in the **same tab and API** as Phase 1. No new admin route or competing dashboard.

## Cross-links preserved

| Need | Location |
|------|----------|
| Fleet billing / recovery checkout | Billing Centre |
| Platform scheduler / ingress health | System Health |
| Compliance overview | Control Panel Compliance tab |
| Full activity audit | Control Panel Activity & Audit tab |

## UI layering (top → bottom)

1. Customer Health Summary (new)
2. Authority chain (new)
3. Lifecycle + billing mirror (existing, compact)
4. Runtime diagnostics (new)
5. Background processing (new)
6. Communications (new)
7. Webhook diagnostics (enhanced)
8. Operational timeline (new)
9. Governed actions (existing)
10. Export support bundle (new)
11. Recent lifecycle audit (existing)

## Duplication avoided

- Does not replicate System Health job registry
- Does not replicate Billing Centre sync UI (links only)
- Does not replicate Activity tab full audit search
