# Stage Z8 — Governance Gap Analysis

**Programme:** STAGE Z — ZOHO ONE INTEGRATION GOVERNANCE & ARCHITECTURE AUDIT  
**Date:** 2026-07-09

## Purpose

Identify governance artefacts and controls required **before** any Zoho integration implementation begins.

---

## Governance requirement matrix

| Domain | Current state (verified) | Gap | Priority | Required artefact |
|--------|-------------------------|-----|----------|-------------------|
| **Master Data Policy** | Partial — ILP authority stack defines billing/lifecycle | No explicit MDM for CRM/marketing entities | **P0** | `MASTER_DATA_POLICY.md` |
| **System of Record Policy** | Implicit in `ACCOUNT_PLATFORM_AUTHORITY_STACK.md` | Zoho not addressed | **P0** | `SYSTEM_OF_RECORD_POLICY.md` (extend ILP) |
| **Synchronisation Policy** | None for third-party | No sync rules, direction, frequency | **P0** | `SYNCHRONISATION_POLICY.md` |
| **Conflict Resolution Policy** | Lead dedup in `lead_service.py` only | No cross-system conflict rules | **P0** | `CONFLICT_RESOLUTION_POLICY.md` |
| **Integration Standards** | Kit integration exists as precedent | No general adapter standard | **P1** | `INTEGRATION_STANDARDS.md` |
| **Security Requirements** | Render secrets, admin auth | No Zoho OAuth lifecycle policy | **P0** | `ZOHO_SECURITY_REQUIREMENTS.md` |
| **Secret Management** | Render env vars | No rotation/revocation runbook for Zoho tokens | **P0** | Secret rotation runbook |
| **Audit Logging** | `audit_logs` mature | No integration-specific audit schema | **P1** | Integration audit event types |
| **API Governance** | Internal API versioning informal | No external API rate/scope registry | **P1** | Zoho API scope registry |
| **Monitoring & Alerting** | Production monitoring exists | No sync health dashboards | **P1** | Sync SLO definitions |
| **Failure Recovery** | Job runner retry patterns | No dead-letter/replay for integrations | **P1** | Integration DLQ design |
| **Data Protection / DPIA** | Privacy policy mentions Zoho (premature) | DPIA for Zoho PII export not done | **P0** | DPIA sign-off |
| **Legal / marketing alignment** | Docs claim Zoho integrated | **False claims in production copy** | **P0** | Copy correction (non-code) |

---

## Policy detail — what each must contain

### 1. Master Data Policy (P0)

Must define:

- Canonical identifiers (`lead_id`, `client_id`, `stripe_customer_id`)
- Which systems may create vs update vs read each entity
- Field-level ownership (e.g. email owned by Pleerity)
- GDPR erasure propagation order (Pleerity first → Zoho purge)

### 2. System of Record Policy (P0)

Must extend ILP stack to state explicitly:

- Pleerity is SoR for all customer-facing entities
- Stripe is SoR for payments
- Zoho apps are **never** SoR for leads, clients, billing, compliance, support
- Exception process for any future SoR change (architecture board approval)

### 3. Synchronisation Policy (P0)

Must define:

- Allowed sync directions per integration
- Sync frequency (real-time event vs batch)
- Idempotency requirements
- Maximum staleness SLO (e.g. Zoho replica < 15 min behind)
- Pause/kill switch procedure

### 4. Conflict Resolution Policy (P0)

Must define:

- Detection (timestamp, version vector, or Pleerity-wins default)
- Escalation path for manual resolution
- Prohibition on silent overwrites of Pleerity authoritative fields
- Logging requirements for every conflict

### 5. Integration Standards (P1)

Must define (Kit integration as template):

- Adapter interface in `services/integrations/`
- Webhook ingress validation pattern
- Mapping registry (YAML or DB collection)
- Test requirements (contract tests, sandbox fixtures)
- No business logic in Zoho Flow for authoritative paths

### 6. Security Requirements (P0)

Must define:

- OAuth 2.0 with minimum scopes
- Token storage (Render secrets, encrypted at rest)
- Token rotation schedule (90-day max)
- Webhook HMAC verification
- PII minimisation in outbound payloads
- Sandbox vs production Zoho org isolation
- Operator access — no shared Zoho credentials

### 7. Secret Management (P0)

Must define:

- Who provisions Zoho OAuth apps
- Rotation procedure without downtime (dual-token window)
- Revocation on employee offboarding
- Audit trail for secret access

### 8. Audit Logging (P1)

Extend `audit_logs` with integration event types:

- `integration.sync.started` / `completed` / `failed`
- `integration.webhook.received` / `rejected`
- `integration.entity.pushed` / `skipped`
- Correlation ID linking Pleerity entity → Zoho record ID

### 9. API Governance (P1)

- Document Zoho API modules in use per integration
- Rate limit budgets (Zoho CRM: 5000 calls/day default tier)
- Circuit breaker thresholds
- Version pinning strategy

### 10. Monitoring & Alerting (P1)

- Sync lag metric
- Error rate by integration
- Dead-letter queue depth
- Alert routes (ops channel, PagerDuty equivalent)

### 11. Failure Recovery (P1)

- Dead-letter store with replay API (admin-only)
- Idempotent replay semantics
- Manual reconciliation playbook
- Integration pause flag in feature flags / env

---

## Organisational governance

| Role | Responsibility |
|------|----------------|
| Architecture owner | Approves SoR and sync direction |
| Engineering lead | Implements integration service to standards |
| DPO / compliance | Signs DPIA, reviews PII flows |
| Operations | Monitors sync health, runs recovery |
| Sales/marketing stakeholder | Confirms Zoho CRM/Campaigns need before build |

---

## Approval gates (before implementation)

| Gate | Approver | Evidence |
|------|----------|----------|
| G1 — Audit complete | Architecture owner | This audit pack (9 documents) |
| G2 — Policies published | Compliance + engineering | P0 policies signed |
| G3 — DPIA complete | DPO | DPIA document |
| G4 — Integration design | Engineering lead | Technical design doc |
| G5 — Sandbox pilot | Ops + QA | Pilot test report |
| G6 — Production enable | Architecture owner | Go-live checklist |

**No implementation until G1–G4 are complete. Production enable requires G5–G6.**

---

## Immediate actions (no code)

1. **Correct legal/marketing copy** that falsely states Zoho is integrated.
2. **Publish P0 policies** before any OAuth app is created in production Zoho org.
3. **Confirm business demand** for Zoho CRM and Campaigns — default is no integration.
4. **Assign architecture owner** for integration programme.

---

## Gap summary

| Priority | Count | Status |
|----------|-------|--------|
| P0 (blocking) | 7 | **Not started** |
| P1 (required before production) | 5 | **Not started** |
| Existing foundation | ILP stack, audit_logs, notification orchestrator, Kit precedent | **Usable** |

**Governance maturity for Zoho integration: Not ready — policies and DPIA required.**
