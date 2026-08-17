# MongoDB Environment Isolation Roadmap

**Audit ID:** `MONGODB-STORAGE-REMEDIATION-AND-LIFECYCLE-GOVERNANCE-01`  
**Date:** 2026-08-06  
**Status:** Roadmap only — **no migration in this implementation**

---

## Problem

Staging and production databases share one Atlas Flex cluster and therefore one **5 GB data+index** quota. Staging telemetry alone exceeded production and blocked **both** environments’ writes.

Logical isolation (`DB_NAME`) is correct; **physical** isolation is not.

---

## Recommendation

| Option | Description | Prefer |
|--------|-------------|--------|
| **A. Separate Atlas clusters** | `pleerity-prod` cluster + `pleerity-staging` cluster | **Yes** |
| **B. Separate Atlas projects** | Stronger blast-radius / billing / IAM separation | Yes if org policy requires |
| **C. Stay on shared Flex** | Continue remediation-only | Interim only |

---

## Benefits

- Staging certification cannot fill production write quota  
- Independent backup/restore and scaling  
- Clearer cost attribution  
- Safer destructive staging experiments  

---

## Migration approach (future)

1. Provision staging cluster; create `pleerity_staging`.  
2. Copy required seed/fixtures (not full telemetry).  
3. Point staging Render `MONGO_URL` at new cluster; keep `DB_NAME=pleerity_staging`.  
4. Verify staging health, login, schedulers.  
5. Leave production cluster with `pleerity_production` only; drop staging DB from old cluster after soak.  
6. Update runbooks / CLI defaults to refuse cross-cluster URIs without explicit flags.

---

## Rollback

Repoint staging `MONGO_URL` to previous cluster URI; no production change required if prod URI never moved.

---

## Cost / ops impact

- Additional Flex or dedicated tier monthly cost for staging  
- Dual connection secrets in Render  
- Dual monitoring (already scans sibling DB names when on shared cluster; simplify after split via `MONGO_STORAGE_SCAN_DBS`)

---

## Logical isolation (already enforced)

- Render blueprints set distinct `DB_NAME`  
- `deployment_environment_guard` blocks staging↔production DB misuse  
- Cleanup utility refuses production  

Physical split remains the durable fix for shared-quota failure mode.
