# Pilot launch governance — residual risk acceptance & positioning

**Product:** Compliance Vault Pro  
**Purpose:** Formal governance artifact for **controlled beta / paid pilot** only — not GA, not “wider launch READY.”  
**Authority:** Aligns with `LAUNCH_AUTHORITY_TRACKER.md`, `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`, and frozen parent domains **L-005, L-008, L-009, L-010** (do not reopen except regression / audit failure / production evidence / launch blocker).

**Commercial truth:** Public pricing and marketing feature lists **must** match `backend/services/plan_registry.py` (`FEATURE_MATRIX`, `PLAN_DEFINITIONS`). Engineering enforcement remains the source of truth.

---

## Part A — Launch tier definition

| Tier | Definition |
|------|------------|
| **Pilot** | Controlled cohort (volume caps, known tenants, staging-tested flows where applicable), explicit residual-risk acceptance below, ops runbooks engaged. |
| **Out of scope for this document** | Unqualified wider launch, GA marketing guarantees, universal automation claims. |

---

## Part B — Accepted risks (pilot)

These are **known and accepted** for pilot operation until revisited (see §Revisit conditions).

| Risk | Mitigation (operational / product) | Customer-facing implication |
|------|-----------------------------------|-----------------------------|
| **L-004** — Narrow pre-authority optimistic requirement mirror on verify before authority sync completes | Fanout markers + `DOCUMENT_VERIFIED` audit metadata; client KPI surfaces use projection authority (`project_requirement_row_client_runtime`); support trained not to treat raw mirror as final truth | Rare transient disagreement between DB mirror and authority during verify; score may lag until queue drains |
| **Async reconciliation** — headline score vs live requirement stats | `compliance_score_pending` / portfolio pending honesty fields where implemented; refresh expectations documented | User may see “pending recalculation” after mutations |
| **Queue** — stuck `RUNNING` rows | Manual reclaim per `AUTHORITY_WRITE_PATH_RECONCILIATION.md` / operator ladder; idempotency reduces duplicates | Occasional delayed score until ops/worker health restored |
| **Notifications** — governed sends (L-008) vs global workflow activation policy | `NOTIFICATION_GOVERNANCE_INVENTORY.json`: workflow family **not** globally “dispatch on”; orchestrator-governed paths per freeze | Some reminder/automation behaviour **environment-dependent**; pilot checklist must confirm what fires in target env |
| **FE `propagation_notice`** — L-009 API returns optional notice; full client inventory was deferred | Backbone honesty on API; **standard client** now surfaces read-only notice on **Documents** + **Bulk upload** when returned | Other surfaces still rely on refresh / score freshness copy until extended |
| **Stripe / billing** — price IDs, test vs prod | Staging validation with **Stripe TEST** only; `PriceConfigMissingError` class = ops/config | Wrong plan SKU → entitlement mismatch until config fixed |
| **Evidence / workflow semantics** — not every obligation is “upload = compliant” | `WORKFLOW_BEHAVIOUR_GOVERNANCE.md` | Misinterpretation if marketing oversimplifies |

---

## Part C — Deferred risks (not accepted as “closed”)

| Item | Disposition |
|------|-------------|
| Eliminate optimistic verify mirror (authority-only promotion) | **DEFERRED_FOR_POST_LAUNCH** — product/legal sign-off |
| Automated stuck-queue reclaim | Deferred engineering / ops design |
| FE consumption of `propagation_notice` on all client routes | **PARTIAL** — read-only display on **Documents** + **Bulk upload** (2026-05-12); extend only with tracker + B-plane row |
| Full chaos / load proof | Deferred observation |
| Formal executive sign-off row in tracker (gate 10) | **Requires business/legal** recording outside this file |

---

## Part D — Operational mitigations

- **Support:** `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` — no direct edits to authoritative score/requirement fields; sanctioned repair paths only; **§12** pre-pilot rehearsal checklist and **§13** instrumentation/analytics gaps for cohort observation. **Rendered email truth:** complete **`NOTIFICATION_OWNERSHIP_READINESS.md`** § *Pilot — rendered truth verification* (Mongo + Postmark preview sign-off) before treating notifications as pilot-closed.
- **Client mental model:** Governed orientation copy (`frontend/src/utils/workspaceOrientationCopy.js`, `docs/governance/PRESENTATION_LANGUAGE_GOVERNANCE.md`) — reduces “wrong screen” tickets; does not replace runbooks or authority docs.
- **Observation:** `BETA_OBSERVATION_AND_TRUST_REVIEW.md` — trust, async confusion, CTA fatigue.
- **Correlation:** Stream C/E/F docs for incident reconstruction.

---

## Part E — Escalation triggers (pilot → stop / narrow / engineering)

- Repeated **wrong-tenant** or **ungoverned send** incidents (notification domain).
- **Silent** entitlement bypass (plan gating regression).
- Spike in **“score wrong”** tickets where validator shows authority inconsistent with headline **after** queue healthy period.
- **Data loss** or unrecoverable billing state in Stripe linkage.

---

## Part F — Excluded guarantees (must not be marketed at pilot)

- Guaranteed legal compliance or regulatory outcome.
- Real-time, infallible compliance truth across all readers at all times.
- Fully autonomous AI compliance agent.
- Universal “all reminders fire” without environment confirmation.

---

## Part G — Observation requirements (before scaling pilot)

- Notification delivery rates (email/SMS) **per env**.
- Queue depth, `RUNNING` stuck frequency, time-to-drain recalc.
- Support taxonomy: verify-window disputes vs true defects.

---

## Part H — Revisit conditions

- Pilot cohort expansion, contractual SLA changes, or **GA-style** marketing require **new** acceptance record + tracker update.
- Any change to **`FEATURE_MATRIX`** requires **synced** public pricing/marketing and CI (`plan_feature_governance_audit.py` per L-010 freeze).

---

## Part I — Pilot positioning (truthful)

### What the product **is** today

- UK landlord **compliance oversight**: obligations tied to published registry / runtime projection, evidence vault, expiry tracking, **compliance score as risk indicator**, portfolio and property views.
- **Governed** document verification and backbone-aware mutations (L-009 scope) with API-level honesty; **plan-gated** reports, ZIP bulk upload, SMS, tenant portal, audit exports per **`FEATURE_MATRIX`**.
- **Structured audit-style exports** for appropriate tiers — **not** a legal verdict.

### What it is **not** yet

- GA-grade “zero residual authority semantics” (gate 1 in tracker remains context for L-004).
- Guaranteed fully automatic compliance detection without user/evidence input.
- A substitute for professional legal advice.

### **Safe** pilot messaging themes

- Compliance **tracking** and **visibility**
- Evidence and document **vault**
- Expiry and renewal **reminders** (plan / env scoped)
- Portfolio **monitoring** and **risk indicator** score
- **Audit-ready workflows** / structured reports (tier-scoped)

### **Unsafe** messaging (forbidden for pilot without legal review)

- “Fully compliant” as a promise
- “AI guarantees accuracy” / autonomous regulatory determination
- “Real-time definitive compliance status everywhere”
- Equating **risk-check funnel PDF** with **in-app governed reports** without clarification

### Short approved positioning line

> **Compliance Vault Pro helps UK landlords track obligations, evidence, and expiries in one place — with plan-based reminders and reports. The compliance score is an informational risk indicator, not legal advice.**

---

## Part J — Unresolved decisions requiring business / legal sign-off

| Decision | Owner |
|----------|--------|
| Pilot **volume**, contractual wording, and liability caps | Legal / commercial |
| Whether L-004 residual is acceptable in **customer contracts** | Legal / product |
| Notification promises in customer-facing SLA | Ops / product |
| Recording formal **gate 10** acceptance in launch committee minutes | Programme sponsor |

---

**Document status:** Living artifact for pilot phase; amend only through governance review.
