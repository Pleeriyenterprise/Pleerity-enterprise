# Security value integration — codebase alignment

This document maps the **“security as visible value”** product brief to the **current Pleerity Enterprise codebase**. It is intended for planning and governance: **what exists**, **what is missing**, **where terminology overlaps**, and **how to extend without duplicating or conflicting** with existing systems.

**Related doc (do not duplicate):** operational auth controls (rate limits, idle session, step-up) are documented in [`SECURITY_RATE_LIMIT_AND_SESSION_POLICY.md`](./SECURITY_RATE_LIMIT_AND_SESSION_POLICY.md). This file focuses on **compliance, operations, billing UX, retention, and cross-cutting audit narrative**.

---

## Executive summary

| Brief area | In codebase today | Gap vs brief |
|------------|-------------------|--------------|
| Compliance + risk | Rule-based **risk signals** (incl. compliance category), levels **low / medium / high / critical**, suggested actions, issue/work-order/inspection flows | Penalty / invalid tenancy **copy** is not a first-class UX pattern; **property-wide “at risk”** is not the same as **work-order SLA “at risk”** |
| Operations | Risk signals, maintenance issues/work orders, contractor portal (JWT + assignment checks), **some** rate limits | **Spam / abnormal issue creation** detection not a dedicated feature; **duplicate submissions** partially covered (public leads, auth); not unified “ops anomaly” layer |
| Billing / invoices | Invoices with **benchmark fit** (below/within/above), `INVOICE_CREATED` audit | **Duplicate invoice** detection not evident in `invoice_service.create_invoice`; **suspicious value** = benchmark flags, not full fraud rules; **client payment liability** disclaimers are product/legal copy |
| Security visibility UX | Client **Risk Signals** page, dashboard digests, admin **System Health** (ops/jobs) | No **client** “System Health & Protection” widget; **failed logins** exist in **audit logs**, not surfaced as a dashboard card; **active sessions** not modeled (stateless JWT) |
| Retention | Billing cancel modal, downgrade FAQ | Cancel/downgrade flow does **not** summarize **open risks / issues / upcoming compliance** |
| Audit | Broad `AuditAction` usage (login success/fail, invoices, documents, admin, risk-signal-derived actions) | “Compliance breach” as a **single** audited event type may need **definition** vs requirement status + existing signals |

---

## Part 1 — Security + compliance

### Implemented (how it works today)

- **Risk signal engine:** `backend/services/risk_signal_service.py` — rule-based, **no ML**. Categories include **`compliance`**, **`operational`**, **`asset`**.
- **Risk levels:** `RISK_LEVEL_LOW | MEDIUM | HIGH | CRITICAL` persisted on stored signals.
- **Compliance-linked inputs:** Overdue / missing / pending requirements feed **compliance churn** and **certificate expiry soon** rules (see `_fetch_requirements_overdue`, `_rule_compliance_churn`, `_rule_certificate_expiry_soon`).
- **Suggested actions:** Codes include `create_issue`, `create_work_order`, `schedule_inspection` (see `SUGGESTED_ACTION_*` and `_suggested_actions_for_signal`).
- **Actions wired:** Service helpers create issues/work orders from signals with audit types such as `ISSUE_CREATED_FROM_RISK_SIGNAL`, `WORK_ORDER_CREATED_FROM_RISK_SIGNAL` (see `risk_signal_service.py`). API routes live under client maintenance (e.g. `schedule_inspection_from_risk_signal_route` in `client_maintenance.py`).
- **UI:** `frontend/src/pages/ClientRiskSignalsPage.js` (and property-level risk UI in `PropertyDetailPage.js`) exposes explanation, filters, and buttons for **issue**, **work order**, **schedule inspection** where actions apply.

### Gaps vs brief

- **“When compliance failures occur → generate risk signals”:** Partially true. Signals are generated on a **job/org schedule** (`job_runner` / `generate_risk_signals_for_org`) and from **requirement state**, not necessarily **immediately** on every status transition. Real-time hooks would be **new** behaviour (design choice: event-driven vs batch).
- **“Mark property as at risk”:** The codebase uses **work-order SLA** fields such as `sla_breach_risk_at` on **work orders** (`job_runner` SLA job), not a single **`properties.at_risk_compliance`** flag. Introducing a property-level flag **without** reconciling it to `risk_signals` and SLA state risks **duplicate semantics**. **Professional recommendation:** treat **`risk_signals`** (+ optional aggregated summary on the property API) as the canonical “property risk” for UX, and use SLA fields only for **work-order** urgency unless product explicitly defines a merged model.
- **UI messaging (penalties, invalid tenancy, etc.):** Not implemented as standard strings tied to signal types. Any such copy should be **jurisdiction-aware** and **legal-reviewed**; avoid hard-coding statutory claims without counsel.

### Conflict / de-duplication note

- **Predictive maintenance gating:** Client visibility of risk signals is tied to **entitlements** (e.g. `predictive_maintenance`). Positioning “security + compliance” for all tiers may require **copy** or **lighter** signals for plans without the feature — avoid silently duplicating the same rules under a second feature flag without a single engine.

---

## Part 2 — Security + operations

### Implemented

- **Contractor portal:** `backend/routes/contractor_portal.py` — JWT + `contractor_route_guard`; work orders scoped to assigned contractor; updates go through `maintenance_service` / `invoice_service` with audits on invoice creation.
- **Risk → suggested ops:** As in Part 1.
- **Rate limiting (abuse):** Auth and many public/sensitive routes (see `SECURITY_RATE_LIMIT_AND_SESSION_POLICY.md`). **Not** a dedicated “spam issue creation” counter per user.

### Gaps

- **Abnormal activity (spam issues, repeated actions):** No dedicated detector surfaced in routes reviewed; could build on **audit_logs** + **rate_limiter** patterns already used for auth/leads.
- **“Secure contractor updates”:** Session is **validated JWT**; audits exist for invoice creation. Broader “every contractor state change” audit coverage should be **verified per endpoint** before marketing “full traceability”.
- **Duplicate submissions (operations):** Partially addressed globally (e.g. lead capture, login); **issue create** endpoints would need explicit **idempotency keys** or per-window limits if product requires it.

### Professional recommendation

- Extend **existing** `rate_limiter` + `AuditAction` patterns for **issue/create** hotspots rather than a second security framework.
- Any “unusual behaviour” scoring should **read from audit_logs** first to avoid a parallel event stream.

---

## Part 3 — Security + billing

### Implemented

- **Invoice submission:** `invoice_service.create_invoice` records amount, **benchmark_min/max**, **`benchmark_fit`** (`below` / `within` / `above` / `none`), and **`INVOICE_CREATED`** audit with metadata (work order, contractor, property, source).
- **Approvals flow:** Client approvals workspace (invoicing feature) consumes pending invoices.

### Gaps

- **Duplicate invoices:** No obvious check in `create_invoice` for duplicate `(work_order_id, reference, amount, contractor_id)` within a time window — **would be new logic** (define “duplicate” carefully to avoid blocking legitimate revisions).
- **Suspicious values:** Benchmark banding exists; **fraud** rules (velocity, outliers vs history) are **not** present.
- **Messaging (client pays contractor; Pleerity not liable):** Product/legal **copy** in UI/terms — not located as a standard component in this audit pass.
- **“Track issue resolution, contractor activity, risk prevented”:** Partially via **audit** + **work order / issue** collections; “risk prevented” is a **metric definition** (not a stored field) unless you add analytics.

### Conflict note

- **Stripe subscription invoices** vs **maintenance contractor invoices** are different domains. The brief’s “when invoices are submitted” should clarify **which** invoice type to avoid implementing rules in the wrong pipeline.

---

## Part 4 — Security visibility (UX)

### Implemented

- **Client:** Compliance/risk visibility via **Risk Signals** and **dashboard**-related APIs (tasks, command centre) — not branded as “security”.
- **Admin:** **System Health** and automation pages monitor **jobs/infrastructure**, not end-user **login security**.

### Gaps

- **Widget:** “System Health & Protection” with **last login, failed attempts, active sessions, compliance risk, security status** — **not** present as specified.
- **Last login / failed attempts:** **Audit logs** capture `USER_LOGIN_SUCCESS` / `USER_LOGIN_FAILED` (and admin variants) in `auth.py`; **no** first-class API optimized for “my recent failed attempts” for the current user dashboard.
- **Active sessions:** JWT access tokens are **stateless** unless you persist sessions or maintain a **session/device registry**. Showing “active sessions” accurately **requires design** (session table, refresh tokens, or “this device only”). **Safest option:** show **last successful login** + **password/session hygiene tips** until a session registry is approved.

### Notification gaps

- **Blocked login attempts / unusual activity / compliance risks:** Email/in-app notification pipelines exist elsewhere (notifications, digests); **unified** “security alerts” product is **not** mapped in this pass.

---

## Part 5 — Retention logic (cancel / downgrade)

### Implemented

- **BillingPage:** Cancel subscription modal (period end vs immediate), downgrade messaging directs to **support** in some paths; FAQ on **data / archive** on downgrade.

### Gaps

- **Before cancel/downgrade:** No aggregated callout of **active risk signals**, **open issues**, **upcoming compliance expiries** in the cancel flow — **new** UX + likely **new API** (aggregate from existing services).

### Professional recommendation

- Implement as a **read-only summary** component reusing **risk_signal_service** + maintenance issue counts + requirements due soon — **no** blocking of legal cancellation without product/legal approval.

---

## Part 6 — Audit logging

### Implemented (examples)

- **Logins:** Success/failure audited (`routes/auth.py`).
- **Contractor-related:** Invoice creation audited; contractor route changes should be checked per handler for full coverage.
- **Admin:** Wide use of `ADMIN_ACTION` and specific actions.
- **Risk-signal-derived actions:** Dedicated audit actions when creating issues/work orders from signals.

### Gaps / precision

- **“Compliance breaches”:** Requirements can be `OVERDUE` / `EXPIRED` in data; a **single** audit event “COMPLIANCE_BREACH” may **duplicate** requirement updates already logged elsewhere. **Recommendation:** define whether marketing “breach” means **regulatory breach** (legal) vs **requirement status** (system) before adding enum values.

---

## Part 7 — Conflicting instructions (explicit)

1. **Earlier engineering rule (from project context):** minimal diffs, no new frameworks, approve before large changes — **vs** this brief’s breadth (widgets, anomaly detection, retention gates). **Resolution:** treat the brief as a **roadmap**; ship **incremental** slices with explicit approval and **reuse** existing services (`risk_signal_service`, `audit`, `rate_limiter`, `invoice_service`).
2. **“Security” vocabulary:** Today “security” docs emphasize **auth abuse and session**. This brief uses “security” for **risk and operations excellence**. **Resolution:** use **“Protection & risk”** or **“Trust & compliance”** in user-facing copy where it overlaps compliance, and keep **“Account security”** for passwords/sessions — reduces confusion with `SECURITY_RATE_LIMIT_AND_SESSION_POLICY.md`.
3. **Property “at risk” vs work-order “at risk”:** Two different mechanisms today; **merging** without a domain model is unsafe. **Resolution:** document the **canonical** meaning in product terms before adding flags.

---

## Suggested implementation order (safest)

1. **UX copy and aggregation only:** retention modal + “protection” widget that **reads existing APIs** (risk summary, open issues count, next expiries) — no new detectors.
2. **Audit completeness pass:** contractor endpoints + issue create — ensure each mutation logs **actor, client_id, resource_id**.
3. **Abuse limits:** targeted `rate_limiter` keys on **issue/create** and **invoice/create** (with config env vars), aligned with existing policy style.
4. **Invoice duplicates / stronger anomaly checks:** after **exact duplicate definition** signed off by ops/finance.
5. **Session registry:** only if “active sessions” is a committed requirement.

---

## How security enhances compliance (for stakeholders)

- **Today:** Compliance stress appears as **stored risk signals** and **requirement-driven rules**, with **actionable** paths (issue, work order, inspection) and **auditability** of those actions.
- **To reach the brief:** Add **user-visible narrative** (consequences, next steps) and **timely** signal generation strategy (event vs batch), without splitting logic into a second risk engine.

## How it supports operations

- **Today:** Work orders, SLA risk timestamps, contractor portal, approvals.
- **To reach the brief:** Layer **lightweight anomaly detection** (reuse audit + rate limits) and **clear “suggested next step”** messaging tied to existing risk signal suggested actions.

## How it protects billing

- **Today:** Invoice benchmark banding + audit trail into approvals.
- **To reach the brief:** Duplicate/suspicion rules and **explicit payment liability** messaging in product copy and terms.

## How it improves retention

- **Today:** Downgrade/cancel explains data/archiving in places.
- **To reach the brief:** Surface **“what you still have at risk”** before churn, using **existing** risk and maintenance data — implemented as **informational**, not as a hard block, unless product/legal requires otherwise.

---

*Document version: aligned to repository scan; update when features ship.*
