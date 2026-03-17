# Pleerity Platform — Strict Product Audit

**Goal:** Evaluate whether the platform is strong enough to retain users, become part of their workflow, and support monetization. Evidence-based; no marketing language.

**Basis:** Codebase (routes, services, UI, jobs, plans), existing USER_VALUE_AUDIT.md, and operational docs.

---

## PART 1 — RETENTION ANALYSIS

### 1. Does the system create recurring value (daily, weekly, monthly)?

**Partially.**

- **Daily:** Scheduled jobs include `daily_reminders`, `pending_verification_digest`, `compliance_check_morning`, `compliance_check_evening`, `scheduled_reports`, `compliance_score_snapshots`, `expiry_rollover_recalc`. These can drive email/digest traffic and keep score and requirement status current. Value is **recurring only if** the user receives and acts on reminders/digests; the platform does not expose “next reminder” or “your digest schedule” clearly in the client UI.
- **Weekly:** No dedicated “weekly summary” or weekly cadence is surfaced in the client experience; priority actions and dashboard are on-demand when the user opens the app.
- **Monthly:** `monthly_digest` exists in the job registry; plan-gated or notification-driven monthly value is not clearly visible in the client flows.

**Evidence:** `job_schedule_registry.py` defines daily_reminders, pending_verification_digest, monthly_digest, compliance_check_*, scheduled_reports, compliance_score_snapshots. Client dashboard does not show “Last reminder sent” or “Next digest”; automation is backend-only.

---

### 2. Are there automated insights or reminders that pull users back?

**Yes, but visibility is weak.**

- **Reminders/digests:** Daily reminders, pending verification digest, and monthly digest are implemented as jobs. Whether they send email/in-app and under what preferences is in `notification_orchestrator` and notification preferences. So there **is** a pull mechanism.
- **Insights:** Priority actions (ranked “what to do next”), risk signals (predictive), and score trend / “what changed” are automated insights that give a reason to open the app. They are **pull-by-visit**: user must log in to see them. No “you have 3 urgent items” push or email summary is clearly surfaced in the audit.
- **Weakness:** Client UI does not show “You have X items due this week” or “Last insight update: …” on the dashboard. So the **reason to return** exists in data and jobs, but the **promise of return** (e.g. “Come back to see your next actions”) is under-exploited in the product narrative and UI.

---

### 3. Does the system reduce ongoing operational stress for landlords?

**Partially.**

- **Reduces stress:** Single place for compliance score, requirement status (overdue/expiring/missing), evidence storage, work orders, contractor assignment, invoice approval, and risk signals with “why it matters” and recommended action. Replaces spreadsheets and ad-hoc tracking for users who adopt the full flow.
- **Does not reduce stress enough:** No single “inbox” or task list; completing one thing often requires multiple screens. Empty dashboard KPIs (SLA breaches, This month’s spend, Contractor perf. = “—”) and mislabelled “Open issues” (actually open work orders) create doubt. No financial/impact view (“what is this costing me?”). So stress is reduced **if** the user invests in learning the product; it is **not** reduced at a glance.

---

### 4. Are there features that make leaving the platform inconvenient?

**Moderate.**

- **Data lock-in:** Compliance history, evidence, requirements, work orders, and approvals live in Pleerity. Export is plan-gated (e.g. reports_pdf, score export). There is no visible “export all my data” self-serve flow in the audit, so leaving implies losing access to that history unless they export before churn.
- **Workflow lock-in:** If the landlord runs maintenance, contractors, and approvals inside Pleerity, moving means re-establishing that workflow elsewhere. Contractor portal and job links are tied to the platform.
- **Weakness:** No strong “switching cost” like integrated banking, tenant rent collection, or mandatory tenant use of the portal. So inconvenience is **moderate**, not high.

---

### 5. Would a user lose meaningful operational visibility if they stopped using Pleerity?

**Yes, for active users.**

- They would lose: live compliance score and trend, requirement and expiry status, risk signals, priority action list, work order and issue tracking, contractor assignment and performance context, and approval trail. That is meaningful operational visibility.
- **Caveat:** Users who use Pleerity only for certificate storage and occasional checks would lose less; the more they rely on operations (WOs, contractors, approvals, risk), the more they lose. So retention is stronger for **power users** who embed the full workflow.

---

### Retention weaknesses (summary)

1. Recurring value depends on reminders/digests and on users opening the app; the UI does not reinforce “come back because…” (e.g. next due items, next digest).
2. No single task list or “today’s actions” that creates a daily habit.
3. Empty or misleading KPIs reduce trust and make the product feel incomplete.
4. Switching cost is moderate; no killer lock-in (e.g. payments, mandatory tenant usage).
5. Retention is likely stronger for heavy users than for light or trial users who never adopt operations.

---

## PART 2 — STICKINESS ANALYSIS

### Compliance management workflow

- **Implemented:** Properties, requirements, evidence (upload, confirm expiry), compliance score (portfolio + property), trend, “what changed,” compliance alert explanations. Requirements have status (overdue, expiring soon, missing).
- **Gap:** Compliance is spread across Dashboard, Compliance Score page, and Property detail. No single “compliance hub” where the landlord sees all obligations and acts in one place. Document/evidence upload is in Documents and Property Evidence, not inline in a task list.

**Verdict:** Landlord can manage compliance inside Pleerity, but the workflow is split across screens; not yet a single habit.

---

### Issue reporting workflow

- **Implemented:** Tenant can report issues (API + UI: dashboard modal, property page form). Issues have status lifecycle (open → triaged → … → resolved/closed). Client can create issues; risk signal → create issue is supported.
- **Gap:** Issue timeline/history is not in the UI (audit exists). No tenant photo upload implementation. So issue reporting is **in-platform**; tracking and closure are only partially visible.

**Verdict:** Landlord can receive and track issues in Pleerity; depth of “start to finish” visibility is partial.

---

### Work order management

- **Implemented:** Create WO (property, operations), assign contractor (with recommendation and “why this matters”), status updates, cost estimate (min/max), record invoice from WO, link to risk signal/issue.
- **Gap:** No single “jobs” view that merges issues and work orders with due dates and one-click actions. Contractor invoice submission is not in-platform (admin/client create only).

**Verdict:** Work order lifecycle is in-platform and can replace spreadsheets/email for job tracking; contractor-side invoice submission is still outside.

---

### Contractor interaction

- **Implemented:** Contractor list, recommendation for a WO (trade/credential/region/performance), assign from WO drawer, contractor portal (job link, status, notes, invoice form for job). Contractor explanation (“why this matters”) and performance/reliability context.
- **Gap:** Contractor invoice submission via portal is not implemented (per OPERATIONS_GAP_CLOSURE_SUMMARY). Communication with contractor (messaging, instructions) is not evident as a first-class flow. So **assignment and job context** are in-platform; **invoicing and rich communication** are partial or external.

**Verdict:** Landlord can assign and track contractor work in Pleerity; invoicing and communication still lean on email/other tools.

---

### Document storage

- **Implemented:** Documents per property, evidence linked to requirements, upload and confirm expiry, “documents awaiting confirmation” banner. Plan-gated bulk/zip and reporting.
- **Gap:** No evidence of tenant-facing “document request” or “upload for landlord” as a standard flow. Storage and organisation are landlord-centric.

**Verdict:** Document storage is in-platform and sufficient for landlord evidence; tenant-facing document flows are limited.

---

### Reporting

- **Implemented:** Compliance score export (PDF/CSV plan-gated), score explanation report, scheduled reports job. Professional reports and reporting service exist.
- **Gap:** Dashboard “SLA breaches,” “This month’s spend,” and “Contractor perf.” show “—”. So **scheduled and on-demand reports** exist; **operational and financial reporting** in the main dashboard are not populated, which undermines “one place for all reporting.”

**Verdict:** Reporting exists for compliance and score; operational/financial reporting in the UI is incomplete.

---

### Can a landlord realistically manage their portfolio entirely inside Pleerity?

**Mostly, with caveats.**

- **Inside Pleerity:** Compliance tracking, requirement status, evidence, score, work orders, contractor assignment, approvals, risk signals, priority actions, issue reporting from tenants, and high-level reporting (score, exports).
- **Still likely external:** Day-to-day contractor and tenant communication (email, WhatsApp), contractor invoice submission (contractor sends outside the app), possibly finance (rent, full P&L). No rent collection or full accounting in scope.

**Gaps preventing Pleerity from being the single operations hub:**

1. No unified “inbox” or task list (compliance + operations + approvals in one place).
2. Empty or misleading dashboard KPIs (SLA, spend, contractor perf.).
3. No financial view (spend, cost of non-compliance).
4. Contractor invoicing and some communication remain outside the app.
5. Admin Ops Compliance and Ops Audit are placeholders, so “full ops” is not complete for admins.

---

## PART 3 — MONETIZATION READINESS

### 1. Does the platform solve a problem serious enough to charge for?

**Yes.**

- Regulatory and safety risk (compliance, certificates, gas/EICR/EPC) is serious for landlords. Fines and liability are real. Pleerity addresses “am I compliant?” and “what’s missing or expiring?” with evidence-based score and requirements.
- Operational chaos (maintenance, contractors, approvals) is painful; the platform offers one place for WOs, assignment, and approvals. So the problem is **serious** and **chargeable**.

---

### 2. Does it provide measurable value (time saved, risk reduced, money saved)?

**Partially.**

- **Risk reduced:** Clear status (overdue/expiring/missing) and explanations (legal context, “why it matters”) support risk reduction; the product does not quantify “risk reduced” or “fines avoided” in the UI.
- **Time saved:** One place for compliance and ops reduces context-switching; no in-product “time saved” or “tasks completed” metric.
- **Money saved:** No “cost of non-compliance” or “spend vs budget” or “savings from timely renewals.” Work order cost estimate exists per WO only. So **measurable value** is implied, not shown.

**Weakness:** Without at least one concrete metric (e.g. “This month’s spend,” “Items resolved,” “Certificates renewed”), the case for “worth the subscription” is under-supported in the product.

---

### 3. Are there premium features users would pay extra for?

**Yes.**

- **Evidence:** Plan tiers (Solo £19, Portfolio £39, Pro £79) with property limits (2, 10, 25). Feature gating: maintenance_workflows, predictive_maintenance, contractor_network, invoicing, reports_pdf (and others) create clear upgrade paths.
- **Premium-capable features:** Risk signals and predictive insights, contractor network and recommendation, invoicing and approvals, PDF/advanced reports, compliance packs (plan-gated). These are **premium** relative to basic cert reminders and document storage.

**Weakness:** If lower-tier users see empty tiles (e.g. “SLA breaches —”, “Contractor perf. —”) or placeholder pages, they may not perceive the product as worth paying for. Premium must feel **complete** where it is exposed.

---

### 4. Does the platform appear trustworthy and professional enough to charge money?

**Partially.**

- **Professional:** Structured UI, compliance score methodology, explanation layer, audit trail, and plan/entitlement model support a professional image.
- **Trust gaps:** Empty KPIs and placeholders suggest incompleteness. No visible “data as of” or “last run” for score/risk. No clear “confidence” or data freshness. So **trust** is partially there; **polish and transparency** need improvement to fully justify price.

---

### Strongest monetizable capabilities

1. **Compliance score and requirement tracking** — Core, differentiated from simple reminders.
2. **Risk signals and “what to do next” (priority actions)** — Predictive and orchestration layer.
3. **Work order + contractor + approval chain** — Operations workflow.
4. **Explanation layer** — “Why it matters” and recommended action (trust and clarity).
5. **Plan-gated reporting and compliance packs** — Clear upsell.

---

## PART 4 — COMPETITIVE DIFFERENTIATION

### Typical landlord software (baseline)

- Certificate reminders (email/SMS when certs expire).
- Document storage (upload certs, store by property).
- Maintenance tracking (list of jobs, status).

### What Pleerity adds (evidence from codebase)

| Capability | Implementation | Differentiation |
|------------|----------------|------------------|
| **Predictive risk signals** | Risk signal service, types (boiler, damp, electrical, SLA, cert expiry, etc.), create issue/WO from signal, explanation engine | Beyond reminders: “why this is a risk” and one-click action. |
| **Contractor intelligence** | Recommendation (trade/credential/region/performance), reliability score, “why this matters” explanation, contractor portal for jobs | Beyond a list: ranked recommendations and context. |
| **Operations workflow automation** | Priority actions (compliance + certs + missing docs + risk + WOs + approvals), ranked; scheduled jobs (reminders, digests, score snapshots) | Single “what to do next” that crosses compliance and ops. |
| **Compliance scoring** | Evidence-based score, trend, “what changed,” requirement-level status, legal context in explanations | Beyond “remind me”: “how compliant am I?” and drivers. |

### Where Pleerity truly differentiates

1. **Unified “what to do next”** — Priority actions combine compliance, certificates, missing docs, risk, work orders, and approvals in one ranked list with in-app links.
2. **Risk → action** — Risk signals with create issue / create work order and explanations, not just alerts.
3. **Contractor recommendation + explanation** — Score and “why this matters” for assignment decisions.
4. **Compliance score + trend + explanations** — Score, trend, and legal/context for requirements.

### Where it does not yet differentiate

- Single “inbox” or task list (many competitors also lack this; opportunity).
- Financial/impact view (spend, cost of non-compliance).
- End-to-end contractor invoicing and tenant communication in-app.

---

## PART 5 — USER EXPERIENCE COHERENCE

### Current state: **Closer to a collection of tools than a unified system.**

**Evidence of fragmentation:**

- **Compliance** = Dashboard + Compliance Score page + Property detail (requirements + evidence). No one “Compliance” screen.
- **Operations** = Issues, Work orders, Approvals, Risk signals, Contractors as separate list/detail areas. No unified “operations inbox.”
- **Next steps** = Priority actions and Action required cards; acting means navigating away to another URL. No “do it here” or “mark done” in the list.
- **Admin** = Real implementations (dashboard, risk, maintenance, contractors) alongside placeholder pages (Ops Compliance, Ops Audit).
- **Dashboard** = Mix of real data (score, portfolio summary, priority actions) and placeholders (“—”) for SLA, spend, contractor perf., and mislabelled “Open issues.”

**What would make it feel like a unified property compliance and operations system:**

- One primary “Tasks” or “Inbox” that merges priority actions, overdue/expiring items, and open issues/WOs with due date and one primary action.
- Consistent urgency (e.g. “Due in X days,” severity) across all item types.
- No placeholder KPIs; either real data or hide.
- Single narrative: “Here’s your status, here’s what to do, here’s where you do it.”

---

## PART 6 — USER VALUE TEST

| Question | Answered? | Evidence / gap |
|----------|-----------|-----------------|
| Am I compliant right now? | **Partially** | Score and grade exist; no single “Yes/No” headline with one-click drill. |
| What risks exist in my portfolio? | **Yes** | Risk signals, requirement status (overdue/expiring/missing), priority actions. Spread across screens. |
| What should I do today? | **Partially** | Priority actions list “what”; no single “today’s tasks” with due dates and “mark done.” |
| How urgent is each issue? | **Partially** | Severity/priority in model; not consistently shown (e.g. “Due in 7 days”) in UI. |
| Can I fix the issue directly in the platform? | **Partially** | Create WO, upload evidence, approve invoice, create issue/WO from risk. Not all from one task surface. |
| Can I track the resolution from start to finish? | **Partially** | WO and issue lifecycles exist; no unified timeline; no explicit “done” in priority list. |

**Unanswered or weak:**

- “How much is this costing me?” (no spend view).
- “What’s the cost of not fixing?” (no impact view).
- “When was this last updated?” (no data freshness in client UI).
- “What exactly should I do in the next 24 hours?” (no single today list).

---

## PART 7 — VALUE SCORE

| Dimension | Score (1–10) | Rationale |
|-----------|--------------|-----------|
| **Retention potential** | **5** | Recurring value and reminders exist; no strong habit loop (e.g. daily task list). Empty KPIs and fragmentation weaken stickiness. Power users more likely to stay. |
| **Stickiness** | **5** | Core workflows (compliance, WO, approvals, risk) are in-app; no single hub. Contractor invoicing and some communication still external. Moderate lock-in. |
| **Monetization readiness** | **6** | Problem is chargeable; plan structure and feature gating are clear. Measurable value and trust (e.g. one real financial metric, no placeholders) need work to support price. |
| **Operational completeness** | **5** | Client-side ops (issues, WOs, contractors, approvals) are implemented; admin has placeholders; dashboard has empty tiles; no financial view. |
| **User confidence** | **5** | Explanation layer and structure support confidence; empty KPIs, placeholders, and no “data as of” reduce it. |

**Overall (average of dimensions): ~5.2** — Moderate; viable for retention and monetization with targeted improvements.

---

## PART 8 — FINAL JUDGMENT

**Classification: 3. Valuable platform with moderate retention.**

**Reasoning:**

- **Not 1 (Early prototype):** Core loops (score, requirements, evidence, WOs, approvals, risk, priority actions) are built and shipped. Real data and workflows exist.
- **Not 2 (Useful but not sticky):** The platform **can** become sticky: reminders/digests, score and trend, priority actions, and operations workflow give reasons to return. Stickiness is limited by fragmentation and empty/misleading UI, not by absence of value.
- **Not 4 (Strong operational system ready for monetization):** Empty KPIs, admin placeholders, no financial view, and no single task list prevent “strong” and “ready.” Monetization is possible but not fully justified in-product.
- **Not 5 (Highly defensible):** Differentiation exists (risk signals, contractor intelligence, priority actions, scoring) but is not yet unique or hard to replicate; lock-in and habit are moderate.

So: **Valuable platform with moderate retention.** It delivers real value and can be monetized; retention and perceived value are held back by fragmentation, placeholders, and missing metrics. Addressing the top improvements below would move it toward (4) and strengthen defensibility.

---

## PART 9 — TOP 10 IMPROVEMENTS

1. **Single “Tasks” or “Inbox” view** — One list merging priority actions, overdue/expiring requirements, and open issues/WOs with due date and one primary action. Increases satisfaction and retention by giving “what to do today” in one place.
2. **Populate or remove dashboard KPIs** — Wire “SLA breaches,” “This month’s spend,” and “Contractor perf.” to real data or remove/hide. Fix “Open issues” (use real issues or rename). Improves trust and perceived completeness.
3. **One financial metric** — At least “This month’s spend” or “Spend YTD” from invoices/approved amounts. Supports monetization and answers “what is this costing me?”
4. **Surface urgency consistently** — Show “Due in X days” or severity on priority action cards and in any task list. Improves “how urgent?” and reduces cognitive load.
5. **Replace or implement admin Ops Compliance and Ops Audit** — Real content or clear “Coming soon” + roadmap. Reduces “product is unfinished” perception for admins.
6. **Trust and freshness** — “Score as of …”, “Risk signals updated …” (or “Last run …”) in client UI. Increases confidence in recommendations and automation.
7. **“Come back” narrative** — On dashboard or after login: “You have X items due this week” or “Next digest: …” to reinforce recurring value and habit.
8. **Issue timeline in UI** — Show issue status history (from audit or stored timeline) on issue detail. Improves “track from start to finish” and trust.
9. **Export / data portability** — Clear self-serve “export my data” (properties, requirements, documents metadata, WOs, approvals) for trust and compliance; does not reduce stickiness if value is clear.
10. **Contractor invoice submission** — Allow contractors to submit invoices from the job portal so the full WO → invoice → approval chain is in-platform. Increases stickiness and positions Pleerity as the operations hub.

---

*Audit based on codebase and docs as of the date of creation. Re-run after major releases to keep scores and judgments current.*
