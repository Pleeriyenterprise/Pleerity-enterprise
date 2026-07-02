# Account Lifecycle State Diagram

**Programme:** ACCOUNT-LIFECYCLE-CAPABILITY-AUTHORITY-01  
**Parent:** `ACCOUNT_LIFECYCLE_POLICY_AUTHORITY.md`, `ACCOUNT_CAPABILITY_AUTHORITY.md`  
**Purpose:** Human-readable governance diagram for lifecycle architecture

---

## Authority stack

```mermaid
flowchart TB
    subgraph inputs [Authoritative inputs]
        STRIPE[Stripe payment facts]
        BILLING[client_billing]
        ORG[client_lifecycle_service]
    end

    subgraph policy [Policy layer - ALPA]
        RESOLVER[Lifecycle State Resolver - ILP-1]
        STATE[account_lifecycle_state]
        PM[portal_mode]
    end

    subgraph capability [Capability layer - ACA]
        CAP[Capability resolver]
        GRANTS[CAP_* effective grants]
    end

    subgraph consumers [Consumers]
        FE[Frontend shell]
        API[Customer APIs]
        JOBS[Background jobs]
        COMMS[Communications]
    end

    STRIPE --> BILLING --> RESOLVER
    ORG --> RESOLVER
    RESOLVER --> STATE
    STATE --> PM
    STATE --> CAP
    PM --> CAP
    CAP --> GRANTS
    GRANTS --> FE
    GRANTS --> API
    GRANTS --> JOBS
    GRANTS --> COMMS
```

---

## Lifecycle states and portal modes

```mermaid
flowchart LR
    subgraph onboarding [Onboarding]
        PP[PAYMENT_PENDING]
        TRIAL[TRIAL]
    end

    subgraph active [Active relationship]
        ACTIVE[ACTIVE]
        CS[CANCELLATION_SCHEDULED]
        PF[PAYMENT_FAILED]
        GRACE[GRACE_PERIOD]
    end

    subgraph terminal [Restricted]
        TE[TRIAL_EXPIRED]
        CI[CANCELLED_IMMEDIATE]
        SE[SUBSCRIPTION_EXPIRED]
        RO[READ_ONLY]
        SUSP[SUSPENDED]
    end

    subgraph org_terminal [Organisation terminal]
        ARCH[ARCHIVED]
        DEL[ACCOUNT_DELETED]
    end

    PP -->|checkout| TRIAL
    PP -->|checkout| ACTIVE
    TRIAL -->|convert| ACTIVE
    TRIAL -->|expire| TE
    ACTIVE -->|cancel scheduled| CS
    ACTIVE -->|payment fail| PF
    PF -->|grace window| GRACE
    GRACE -->|pay| ACTIVE
    GRACE -->|timeout| SUSP
    CS -->|period end| SE
    CS -->|resume| ACTIVE
    ACTIVE -->|cancel now| CI
    SE -->|retention timer| RO
    SE -->|renew| ACTIVE
    CI -->|resubscribe| ACTIVE
    TE -->|subscribe| ACTIVE
    RO -->|subscribe| ACTIVE
    SUSP -->|reinstate| ACTIVE
    ACTIVE -->|admin archive| ARCH
    ARCH -->|admin restore| ACTIVE
    ARCH -->|purge| DEL
```

### Portal mode overlay

| State group | Portal mode |
|-------------|-------------|
| ACTIVE, TRIAL, CANCELLATION_SCHEDULED, PAYMENT_FAILED | `FULL_ACCESS` |
| GRACE_PERIOD | `GRACE` |
| TRIAL_EXPIRED, PAYMENT_PENDING | `PAYMENT_REQUIRED` |
| CANCELLED_IMMEDIATE, SUBSCRIPTION_EXPIRED, UNKNOWN | `BILLING_RECOVERY` |
| READ_ONLY, LEGACY | `READ_ONLY` |
| SUSPENDED | `SUSPENDED` |
| ARCHIVED | `ARCHIVED` |
| ACCOUNT_DELETED | `ACCOUNT_DELETED` |

---

## Cancellation flows

```mermaid
flowchart TD
    A[ACTIVE] -->|customer: cancel at period end| CS[CANCELLATION_SCHEDULED]
    CS -->|FULL_ACCESS until date| CS
    CS -->|resume subscription| A
    CS -->|Stripe period end| SE[SUBSCRIPTION_EXPIRED]
    SE -->|portal| BILLING[BILLING_RECOVERY]

    A -->|customer: cancel immediately| CI[CANCELLED_IMMEDIATE]
    CI -->|portal| BILLING
    CI -->|API shell block| DENY[Operational CAP_* DENY]
    BILLING -->|resubscribe| A

    style CS fill:#e8f5e9
    style CI fill:#fff3e0
    style BILLING fill:#e3f2fd
```

**Distinct concepts:** Cancellation scheduled ≠ immediate ≠ expiry. Each maps to different capability grants.

---

## Expiry and read-only flows

```mermaid
flowchart TD
    CS[CANCELLATION_SCHEDULED] -->|period end| SE[SUBSCRIPTION_EXPIRED]
    GRACE[GRACE_PERIOD] -->|unpaid terminal| SE
    A[ACTIVE] -->|unpaid terminal| SE

    SE -->|BILLING_RECOVERY mode| BR[CAP: billing + read tier]
    SE -->|retention policy T-014| RO[READ_ONLY]
    RO -->|READ_ONLY mode| RR[CAP: view/export only]
    RO -->|subscribe| A

    style BR fill:#e3f2fd
    style RR fill:#f3e5f5
```

---

## Suspension flows

```mermaid
flowchart TD
    GRACE[GRACE_PERIOD] -->|grace elapsed| SUSP[SUSPENDED]
    A[ACTIVE] -->|admin / abuse| SUSP
  SUSP -->|payment resolution| A
    SUSP -->|admin reinstatement| A
    SUSP -->|portal| SM[SUSPENDED mode]
    SM -->|CAP_*| DENY[Operational DENY]

    style SM fill:#ffebee
```

---

## Archiving and deletion flows

```mermaid
flowchart TD
    ANY[Any billing state] -->|admin archive| ARCH[ARCHIVED]
    ARCH -->|portal| AM[ARCHIVED mode]
    AM -->|CAP_AUTH_LOGIN| DENY[Login denied]
    ARCH -->|admin reactivate + billing| A[ACTIVE]
    ARCH -->|retention satisfied| DEL[ACCOUNT_DELETED]
    DEL -->|portal| DM[ACCOUNT_DELETED]
    DM -->|all CAP_*| DENY[Permanent deny]

    style AM fill:#eceff1
    style DM fill:#263238,color:#fff
```

---

## Reactivation paths (summary)

```mermaid
flowchart LR
    subgraph from [From]
        GRACE[GRACE_PERIOD]
        CI[CANCELLED_IMMEDIATE]
        SE[SUBSCRIPTION_EXPIRED]
        RO[READ_ONLY]
        SUSP[SUSPENDED]
        ARCH[ARCHIVED]
        TE[TRIAL_EXPIRED]
    end

    subgraph event [Event]
        E1[PAYMENT_RECOVERED]
        E2[SUBSCRIPTION_STARTED]
        E3[ACCOUNT_REACTIVATED]
    end

    subgraph to [To]
        ACTIVE[ACTIVE]
    end

    GRACE -->|R-002| E1 --> ACTIVE
    CI -->|R-005| E2 --> ACTIVE
    SE -->|R-004| E2 --> ACTIVE
    RO -->|R-012| E2 --> ACTIVE
    SUSP -->|R-006 R-007| E3 --> ACTIVE
    ARCH -->|R-008| E3 --> ACTIVE
    TE -->|R-011| E2 --> ACTIVE
```

**Restoration:** Reactivation restores capability grants per `ACCOUNT_REACTIVATION_AUTHORITY.md` scope (Everything / Read-only / Selective).

---

## Lifecycle events (canonical)

```mermaid
flowchart TB
    subgraph creation [Creation]
        AC[ACCOUNT_CREATED]
        TS[TRIAL_STARTED]
    end

    subgraph payment [Payment]
        PF[PAYMENT_FAILED]
        GS[GRACE_STARTED]
        PR[PAYMENT_RECOVERED]
    end

    subgraph subscription [Subscription]
        SS[SUBSCRIPTION_STARTED]
        CR[CANCELLATION_REQUESTED]
        CSD[CANCELLATION_SCHEDULED]
        SC[SUBSCRIPTION_CANCELLED]
        SX[SUBSCRIPTION_EXPIRED]
    end

    subgraph account [Account]
        AR[ACCOUNT_READ_ONLY]
        AS[ACCOUNT_SUSPENDED]
        AA[ACCOUNT_ARCHIVED]
        AD[ACCOUNT_DELETED]
        RX[ACCOUNT_REACTIVATED]
    end

    AC --> TS
    TS --> SS
    SS --> PF --> GS
    GS --> PR --> SS
    SS --> CSD --> SC
    CSD --> SX
    GS --> AS
    SX --> AR
    SC --> RX
    SX --> RX
    AS --> RX
```

---

## Capability resolution (per request)

```mermaid
flowchart TD
    REQ[Customer request] --> AUTH{Authenticated?}
    AUTH -->|no| LOGIN[CAP_AUTH_LOGIN]
    AUTH -->|yes| STATE[Resolve account_lifecycle_state]
    STATE --> PM[Resolve portal_mode]
    PM --> BASE[Lookup ACCOUNT_CAPABILITY_MATRIX]
    BASE --> OVERLAY[Apply PORTAL_MODE_CAPABILITY_MATRIX]
    OVERLAY --> PLAN{PLAN_GATED?}
    PLAN -->|yes| PLANCHECK[plan_registry check]
    PLAN -->|no| EFFECTIVE[Effective grant]
    PLANCHECK --> EFFECTIVE
    EFFECTIVE -->|ALLOW/READ| OK[Execute]
    EFFECTIVE -->|DENY/HIDDEN| SCREEN[Lifecycle screen / 403 safe message]
```

---

## Terminal states reference

| State | Terminal? | Recovery | Capability default |
|-------|-----------|----------|-------------------|
| TRIAL_EXPIRED | Billing terminal | Subscribe | PAYMENT_REQUIRED subset |
| CANCELLED_IMMEDIATE | Billing terminal | Resubscribe | BILLING_RECOVERY |
| SUBSCRIPTION_EXPIRED | Billing terminal | Renew | BILLING_RECOVERY |
| READ_ONLY | Soft terminal | Subscribe | READ grants |
| SUSPENDED | Access terminal | Payment/admin | DENY operational |
| ARCHIVED | Org terminal | Admin only | DENY all customer |
| ACCOUNT_DELETED | Hard terminal | None | DENY all |

---

**Outcome:** `ACCOUNT_LIFECYCLE_STATE_DIAGRAM_COMPLETE`
