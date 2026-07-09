# Architecture Audit — Customer Operations Centre Phase 2

**Programme:** ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01  
**Branch:** `develop`  

## Foundation (unchanged)

Phase 1 **Lifecycle Operations** remains the API and placement anchor:

- Tab on Client Control Panel (`lifecycle-ops` id)
- API prefix `/api/admin/clients/{id}/lifecycle-operations`
- Service `admin_lifecycle_operations_service.py` + governed routes

Phase 2 **extends** via `admin_customer_operations_centre_service.py` — no competing page, router, or authority.

## Naming decision (Phase A)

| Option | Decision |
|--------|----------|
| Tab label **Lifecycle ops** | Renamed → **Customer ops** |
| Panel title | **Customer Operations Centre** |
| API routes | **Unchanged** (`lifecycle-operations`) — backward compatible |
| New standalone page | **Rejected** |

**Reasoning:** Scope now covers health, timeline, communications, background processing, and support bundle — broader than lifecycle alone. Tab label **Customer ops** signals operational breadth without breaking API contracts or duplicating navigation. Internal route id `lifecycle-ops` retained to avoid routing churn.

## Architecture

```
AdminClientControlPanelPage (tab: Customer ops)
  └── AdminLifecycleOperationsPanel (extended UI)
        └── GET lifecycle-operations snapshot
              ├── Phase 1: lifecycle, billing, actions, audit
              └── Phase 2: customer_health, authority_chain,
                           operational_timeline, runtime_diagnostics,
                           background_processing, communications,
                           webhook_diagnostics
        └── POST governed actions + export-support-bundle (ZIP)
```

## Authority reuse

| Phase 2 feature | Authority / service |
|-----------------|---------------------|
| Health indicators | Derived from contract, billing mirror, events |
| Authority chain | Visualises existing resolver chain |
| Timeline | `account_lifecycle_events`, `stripe_events`, `audit_logs`, `message_logs` |
| Runtime diagnostics | `account_lifecycle_runtime_contract`, cache peek |
| Background | `account_background_runtime_authority.evaluate_background_runtime` |
| Communications | `account_customer_communication_authority.evaluate_customer_communication` |
| Support bundle | Snapshot redaction + ZIP export |

No parallel lifecycle truth introduced.
