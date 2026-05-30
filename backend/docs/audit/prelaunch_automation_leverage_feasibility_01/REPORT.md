# PRELAUNCH-AUTOMATION-LEVERAGE-FEASIBILITY-AUDIT-01 — REPORT

**Classification:** PARTIAL (platform ready for Phase 1; not ready for unsupervised auto-execute)  
**Captured:** 2026-05-30  
**Type:** Feasibility / architecture / ROI audit — **no implementation**

---

## Executive summary

The platform can **safely move toward system-guided operational automation** for **Phase 1** workloads: reminders, nudges, prioritisation, duplicate detection, and draft recommendations. Core infrastructure already exists:

- **NotificationOrchestrator** (idempotency, throttle, plan gate)
- **APScheduler + 48 instrumented jobs**
- **Mongo work queues** with reclaim/dead-letter
- **~292 AuditAction types**
- **Verified work-order quote/visit lineage** (recent operational audits)

**Do not** auto-execute authority-changing actions (assign, approve quote, confirm visit, verify evidence, change compliance claims) without explicit human gates.

---

## 1. Automation readiness (Part 1)

| Readiness bucket | Count | Examples |
|------------------|-------|----------|
| Ready for automation now | 10 | Notifications, quote/visit, Today, contractor onboarding |
| Needs foundation | 8 | Evidence review, document classification, job completion |
| Unsafe / manual only | 0 | — |

**Strongest modules:** quote/visit negotiation, notifications, risk signals (SUGGEST_ONLY), tenant/contractor onboarding.  
**Weakest for auto-execute:** evidence verification, compliance score presentation, admin backlog throughput.

Artifact: `automation_readiness_inventory.json`

---

## 2. Highest-ROI opportunities (Part 2)

**Top 3:**

1. **AUTO-001** — Workflow abandonment nudges (quote/visit/activation)
2. **AUTO-002** — Quote/visit follow-up escalation ladder
3. **AUTO-003** — Today predictive urgency + one-click continuation

These reduce landlord/contractor effort, cut support load on stalled jobs, and build on verified workflow state.

Artifact: `automation_roi_matrix.json`

---

## 3. Safety and trust constraints (Part 3)

All Phase 1 automation should be:

- **auto_notify** or **auto_prioritise** — never **unsafe_auto_execute**
- Routed through **NotificationOrchestrator** with **idempotency_key**
- Audited with **AuditAction**
- Blocked from mutating quote/visit/evidence authority

**Never auto-execute:** approve quote, confirm visit, assign contractor, verify evidence, auto-create WO from risk.

Artifact: `automation_guardrails.json`

---

## 4. Architecture readiness (Part 4)

**Strong:** canonical WO/order/evidence enums, audit trail, notification gateway, background jobs, duplicate idempotency.  
**Gaps:** generic event bus, per-entity **workflow timers**, automation **reconciliation jobs**, unified **confidence scoring**, job registry completeness (2 jobs missing from SLA watchdog registry).

Artifact: `automation_architecture_readiness.json`

---

## 5. Risk register (Part 5)

10 risks identified; 2 critical (wrong evidence match, premature compliance claims).  
Most Phase 1 risks mitigated by notify-only + reconciliation.  
Auto-assign and auto-verify must remain delayed.

Artifact: `automation_risk_register.json`

---

## 6. Phased roadmap (Part 6)

| Phase | Focus | Timeline |
|-------|-------|----------|
| 1 | Nudges, prioritisation, duplicate detection | 0–8 weeks |
| 2 | Assisted classification, remediation drafts | 8–20 weeks |
| 3 | Semi-autonomous matching/escalation | 20–40 weeks |
| 4 | Self-driving compliance with approval gates | 40+ weeks |

**Recommended first programme:** `PRELAUNCH-WORKFLOW-NUDGE-ORCHESTRATION-01`

Artifact: `automation_roadmap.json`

---

## 7. Business value (Part 7)

Highest platform value: workflow nudges, Today prioritisation, compliance remediation drafts, risk pattern detection.  
Monetisation: Phase 1 features fit **Pro plan**; document/remediation intelligence suitable for **AI add-on** tier.

Artifact: `automation_business_value.json`

---

## 8. Classification (Part 8)

- **Overall:** PARTIAL  
- **AUTOMATION_READY modules:** 10  
- **PARTIAL:** 7  
- **FOUNDATION_REQUIRED:** 1 (requirements fan-out)  
- **Phase 1 clearance:** Yes  
- **Phase 2+ clearance:** No (without timers + reconciliation)

Artifact: `classifications.json`

---

## Recommended first automation programme

**PRELAUNCH-WORKFLOW-NUDGE-ORCHESTRATION-01**

Scope: quote/visit/activation abandonment nudges + escalation ladder + Today priority boost for stalled workflow items.

Prerequisites before build:

1. Per-WO workflow timer fields or companion collection
2. Nudge reconciliation scheduled job
3. Register any new jobs in `job_schedule_registry.py`
4. Template keys in `notification_templates` + `email_event_registry`

Explicitly out of scope: auto-assign, auto-approve, auto-confirm, auto-verify.

---

## Watchlist

See `watchlist.md`.
