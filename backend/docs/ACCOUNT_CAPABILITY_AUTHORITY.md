# Account Capability Authority

**Programme:** ACCOUNT-LIFECYCLE-CAPABILITY-AUTHORITY-01  
**Authority version:** `account_capability_v1`  
**Follows:** ACCOUNT-LIFECYCLE-POLICY-AUTHORITY-01, ACCOUNT-LIFECYCLE-AUTHORITY-AUDIT-01  
**Branch:** develop (governance only — no implementation)

---

## Purpose

Capabilities are the **reusable permission language** of the platform.

| Layer | Governs |
|-------|---------|
| **Lifecycle state** | Customer business relationship |
| **Portal mode** | Customer experience shell |
| **Capability** | What the customer can actually do |

This programme does **not** implement lifecycle behaviour. It defines the capability model every subsystem must consume **together with** Account Lifecycle Policy Authority and Portal Mode Authority.

---

## Authority hierarchy

```
Account Lifecycle Policy Authority (ALPA)
        │ account_lifecycle_state
        ▼
Account Portal Mode Authority (APMA)
        │ portal_mode (experience; never decides permissions alone)
        ▼
Account Capability Authority (ACA)  ← this programme
        │ capability grants (ALLOW | READ | DENY | HIDDEN | PLAN_GATED)
        ▼
┌───────┴───────┬───────────────┬──────────────┐
│ Plan matrix   │ Feature UI    │ API guards   │
│ (plan_registry)│ (hasFeature) │ (enforce_)   │
└───────────────┴───────────────┴──────────────┘
```

**Preserved authorities** (not replaced; consume ACA for access):

- Lifecycle Authority (requirements), Requirement Authority, Evidence Authority, Navigation Authority, Score Authority, Communication Authority, Email Presentation Authority, Report Presentation Authority

**Not modified by this programme:** authentication, authorisation implementation, billing, subscriptions, APIs.

---

## Capability model

### Capability identifier

Format: `CAP_<DOMAIN>_<ACTION>` (e.g. `CAP_PROP_VIEW`).

Stable, versioned, documented in `ACCOUNT_CAPABILITY_CATALOG.md`.

### Capability class

| Class | Meaning |
|-------|---------|
| **Read** | View or download without mutation |
| **Write** | Create, update, delete customer data |
| **Administrative** | Account-level or org configuration |
| **Background** | System/worker execution (no direct UI) |
| **System** | Platform-internal; not customer-facing |
| **Shared** | Cross-cutting (e.g. export) |
| **Customer** | Direct customer portal action |

### Grant levels (lifecycle × portal mode)

| Grant | Meaning |
|-------|---------|
| **ALLOW** | Full operation |
| **READ** | View/export only |
| **DENY** | Not available; lifecycle screen |
| **HIDDEN** | Not shown in navigation |
| **PLAN_GATED** | Allowed only if plan capability also grants |
| **REQUIRES_RENEWAL** | Visible with renewal CTA |
| **REQUIRES_UPGRADE** | Visible with upgrade CTA |
| **REQUIRES_ADMIN** | Admin reinstatement only |
| **REQUIRES_SUPPORT** | Contact support path |

**No inference:** Subsystems resolve grants via `capability_resolver(state, portal_mode, plan)` — never raw Stripe or `canonical_entitlement_state`.

---

## Resolution order (policy)

```
1. account_lifecycle_state  → base grant from ACCOUNT_CAPABILITY_MATRIX
2. portal_mode              → overlay from ACCOUNT_PORTAL_MODE_CAPABILITY_MATRIX
3. plan feature             → PLAN_GATED check (plan_registry keys)
4. ops module flags         → maintenance_workflows, etc. (secondary plan overlay)
5. effective_capability     → ALLOW | READ | DENY | HIDDEN
```

Portal mode **never decides permissions independently** — it consumes capability grants produced by steps 1–2.

---

## Document map

| Document | Content |
|----------|---------|
| `ACCOUNT_CAPABILITY_CATALOG.md` | Every capability: owner, deps, security, audit |
| `ACCOUNT_CAPABILITY_MATRIX.md` | Lifecycle state × capability |
| `ACCOUNT_PORTAL_MODE_CAPABILITY_MATRIX.md` | Portal mode × capability |
| `ACCOUNT_FEATURE_CAPABILITY_MATRIX.md` | Product feature → capability |
| `ACCOUNT_API_CAPABILITY_MATRIX.md` | Customer API → required capabilities |
| `ACCOUNT_BACKGROUND_CAPABILITY_MATRIX.md` | Workers → required capabilities |
| `ACCOUNT_LIFECYCLE_STATE_DIAGRAM.md` | Visual lifecycle architecture |
| `audit/.../FRONTEND_CAPABILITY_CONSUMPTION.md` | Phase 8 page-level capability audit |
| `audit/.../ACCOUNT_CAPABILITY_AUTHORITY_EVIDENCE.json` | Gaps, classifications, roadmap |

---

## Subsystem consumption (policy)

| Subsystem | Must consume |
|-----------|--------------|
| Portal Mode API (ILP-2) | Effective capability set + portal_mode |
| Frontend shell (ILP-3) | Capabilities via lifecycle-contract; not `hasFeature` alone |
| API routes | Required capabilities from API matrix |
| `plan_registry` | Maps plan features → capabilities; does not replace lifecycle |
| `entitlement_access` | Delegates to capability resolver |
| Navigation Authority | `HIDDEN` capabilities filter nav |
| Background jobs | Background capability matrix |
| Notification orchestrator | Communication capabilities + lifecycle |
| Report Presentation Authority | Generation gated by `CAP_REPORT_*` |

---

## Capability evolution (Phase 10)

| Governance rule | Policy |
|-----------------|--------|
| New capability | Register in catalog → matrix → feature map → API map before use |
| Versioning | `account_capability_vN`; breaking grant changes require migration programme |
| Deprecation | `deprecated: true` in catalog; 2-version overlap minimum |
| Migration | Legacy feature keys map to capabilities via compatibility table |
| Audit | Every grant change emits `CAPABILITY_POLICY_CHANGED` (future) |
| Backward compatibility | Old `feature_key` aliases resolve to capabilities until ILP-10 complete |
| Documentation | Catalog is source of truth; code references capability ID in comments only |

---

## Implementation roadmap consumption

| Programme | Capability dependency |
|-----------|----------------------|
| **ILP-1** Lifecycle State Resolver | Publishes `account_lifecycle_state` for matrix lookup |
| **ILP-2** Portal Mode API | Returns `capabilities: { CAP_*: grant }` in lifecycle-contract |
| **ILP-3** Frontend Lifecycle Shell | `useCapabilities()` replaces direct `hasFeature` for lifecycle |
| **ILP-4** API Lifecycle Responses | Endpoints check capability resolver before plan_registry |
| **ILP-5** Session Authority | Unaffected; session separate from capability |
| **ILP-6** Background Processing | Jobs use `ACCOUNT_BACKGROUND_CAPABILITY_MATRIX` |
| **ILP-7** Customer Communications | Send eligibility = communication capabilities |
| **ILP-8** Reactivation | Restores capability grants per reactivation scope |
| **ILP-9** Lifecycle Events | Events trigger capability cache invalidation |
| **ILP-10** Legacy Migration | Maps legacy flags → capability IDs |

**No implementation until ACA + ALPA approved.**

---

## Acceptance

| Criterion | Document |
|-----------|----------|
| Every customer capability uniquely defined | `ACCOUNT_CAPABILITY_CATALOG.md` |
| Every capability has single owner | Catalog |
| Every feature maps to capabilities | `ACCOUNT_FEATURE_CAPABILITY_MATRIX.md` |
| Every customer API maps to capabilities | `ACCOUNT_API_CAPABILITY_MATRIX.md` |
| Every portal mode consumes capabilities | `ACCOUNT_PORTAL_MODE_CAPABILITY_MATRIX.md` |
| Every lifecycle state consumes capabilities | `ACCOUNT_CAPABILITY_MATRIX.md` |
| Background services consume capabilities | `ACCOUNT_BACKGROUND_CAPABILITY_MATRIX.md` |
| Lifecycle diagram produced | `ACCOUNT_LIFECYCLE_STATE_DIAGRAM.md` |
| Integrates with ALPA | Evidence JSON |

---

**Outcome:** `ACCOUNT_CAPABILITY_AUTHORITY_COMPLETE`
