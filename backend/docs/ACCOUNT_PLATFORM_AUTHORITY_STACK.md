# Account Platform Authority Stack

**Programme:** ILP-10-PLATFORM-CONVERGENCE-AND-LEGACY-REMOVAL-01  
**Branch:** `develop`

---

## Customer-facing authority hierarchy

```
ILP-1  Lifecycle State Resolver     account_lifecycle_state_resolver.py
         ↓
ILP-2  Runtime Contract             account_lifecycle_runtime_contract.py
         ↓
ILP-4  Capability Enforcement       account_capability_enforcement.py
         ↓
ILP-5  Session Runtime               account_session_runtime_service.py
         ↓
ILP-6  Background Runtime             account_background_runtime_authority.py
         ↓
ILP-7  Lifecycle Response             account_lifecycle_response_authority.py
         ↓
ILP-8  Customer Communication         account_customer_communication_authority.py
         ↓         account_lifecycle_reactivation_authority.py (recovery metadata)
ILP-9  Lifecycle Events               account_lifecycle_event_authority.py
```

**ILP-3 Portal Mode** — presentation layer consuming Runtime Contract (`portal_mode`, `customer_experience`, `navigation_policy`). Not an enforcement authority.

---

## Enforcement entry points

| Concern | Customer entry | Module |
|---------|----------------|--------|
| Permissions | `capability_gating.assert_client_capability` | ILP-4 |
| Route lifecycle block | `_client_context_guard` → Runtime Contract | ILP-2 + ILP-7 |
| Session validity | `session_runtime.apply_session_runtime_validation` | ILP-5 |
| Background jobs | `BackgroundRuntimeAuthority.evaluate` | ILP-6 |
| HTTP denial shape | `lifecycle_denial_for_client`, `capability_denied_http_detail` | ILP-7 |
| Communication send | `evaluate_customer_communication` | ILP-8 |
| Lifecycle events | `publish_lifecycle_event`, `publish_runtime_contract_transition` | ILP-9 |

---

## Frontend consumption

| Concern | Utility / context |
|---------|-------------------|
| Runtime + portal mode | `LifecycleRuntimeContext` |
| Capability checks | `capabilityRuntime.js`, `CapabilityProtectedRoute` |
| Session sync | `sessionRuntimeSync.js` |
| Communication metadata | `communicationRuntime.js` |

---

## Compatibility layers (intentional)

| Layer | Purpose | Remove when |
|-------|---------|-------------|
| `EntitlementProtectedRoute` | Alias to `AccountCapabilityProtectedRoute` | No external imports |
| `EntitlementsContext` | Deprecated; unmounted | Test mock migration |
| `capability_compatibility.py` | feature_key → CAP_* map | plan_registry bridge retired |
| `compare_runtime_with_legacy` | Drift diagnostic | Post release audit |
| `/lifecycle-contract` alias | API transitional | Client migration complete |
| `feature_gating.require_feature` | Governance tests | Tests migrated to CAP_* |

---

## Non-customer domains (out of stack)

- `subscription_operational_events` — admin billing ops
- `lifecycle_kpi_gates` — compliance KPI shadow mode
- `webhook_service` — customer integration webhooks (compliance domain)
- Admin routes — separate guards

---

## Exceptions

None for customer portal permission authority. All customer routes verified against CAP_* enforcement (ILP-4 closeout + ILP-10 convergence tests).
