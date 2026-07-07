# P0 Operational Pages Frontend Crashes

**Programme:** P0-OPERATIONAL-PAGES-FRONTEND-CRASHES-01  
**Verdict:** `OPERATIONAL_PAGES_FRONTEND_CRASHES_FIXED`

## Root cause

Both crashes were **incomplete migration wiring** — not capability denial, not Runtime Contract issues, not backend defects.

| Route | Error | Cause | Classification |
|-------|-------|-------|----------------|
| `/operations/issues` | `ContractorNetworkLockedModal is not defined` | JSX rendered without import | **BUG** |
| `/operations/approvals` | `approvalsStepUp is not defined` | `useStepUpApi` imported but never called | **BUG** |

## Fixes

### ClientIssuesPage.js
- Added `ContractorNetworkLockedModal` import (matches ClientJobDetailPage, ClientRiskSignalsPage, ClientIssueDetailPage)
- Added missing `toast` and `reinforcementToastOptions` imports (latent crash on create-issue success path)

### ClientApprovalsPage.js
- Added `const approvalsStepUp = useStepUpApi();` (matches BillingPage `billingStepUp` pattern)
- Preserves step-up modal for approve/reject/mark-paid sensitive actions

## Audit scope

Scanned operational pages for undefined references, missing imports, stale entitlement remnants:
- All scoped pages use `useOperationalExecutionCapabilities` / `OperationalCapabilityProtectedRoute`
- No `useEntitlements` or `EntitlementProtectedRoute` found
- Only ClientIssuesPage lacked ContractorNetworkLockedModal import among pages that render it

## Tests

```
npm test -- --testPathPattern=p0_operational_pages_frontend_crashes_01|ClientIssuesPage.render|ClientApprovalsPage.render|operationalExecution.capability
→ 32 passed

npm run build → Compiled successfully (main.0747bd20.js)
```

Regression guards:
- Static: component import required when JSX references it
- Static: `approvalsStepUp` must be wired via `useStepUpApi()`
- Render: ClientIssuesPage and ClientApprovalsPage mount without ReferenceError

## Staging validation

Post-deploy checklist:
- [ ] Vercel alias points to deployment serving `main.0747bd20.js` or newer
- [ ] `/operations/issues` loads (no ErrorBoundary)
- [ ] `/operations/approvals` loads (no ErrorBoundary)
- [ ] `/operations/work-orders` loads
- [ ] Professional account operational pages accessible when capabilities ALLOW

## Scope boundaries

- develop/staging only
- No production changes
- No merge to main
- Capability gates and Runtime Contract preserved
