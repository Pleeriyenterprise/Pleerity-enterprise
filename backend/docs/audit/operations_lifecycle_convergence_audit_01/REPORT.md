# Operations Lifecycle Convergence Audit — REPORT

Programme: **OPERATIONS-LIFECYCLE-CONVERGENCE-AUDIT-01**

## 1. Root cause analysis

### A. Premature predictive risk signals (onboarding users)

| Finding | Root cause |
|---------|------------|
| "Repeated repairs" / "Maintenance frequency" on new accounts | Heuristic rules counted **all** issues/work orders in rolling windows, including **compliance-gap bridge** and **system-seeded** records |
| No lifecycle gate | `generate_risk_signals_for_property` had no client-level operational-history eligibility check |
| Engine copy in UI | Raw `reasons[]` strings (e.g. "Same asset/category has 6 issues…") persisted and displayed verbatim |

### B. Non-clickable "Start maintenance job" in risk drawers

| Finding | Root cause |
|---------|------------|
| Button visible but no action | Server `operational_cognition.primary_action.key` is `create_work_order`; client handler only matched `maintenance_job` |
| Silent fallback | Unmatched keys fell through to `setDrawerSignalId()` — no-op when drawer already open |

### C. "Ready for contractor assignment" dead state

| Finding | Root cause |
|---------|------------|
| No assign action in drawer | UI hid all CTAs when `status === ready_for_work_order` |
| List showed "Assign contractor" chip | `ListCognitionChip` read cognition envelope, but drawer ignored it |
| Continuation CTA key | `continuation_cta.key` was always `view_workflow` even when label was "Assign contractor" |

### D. Governance language leakage

| Finding | Root cause |
|---------|------------|
| `MISSING_EVIDENCE`, Gap/Key UUIDs | Issue API returned raw DB `description` without `sanitize_issue_for_customer` |
| Internal issue refs in table | UI displayed `issue_id.slice(0,8)` and raw `source: system` |

## 2. Lifecycle governance map

```
Client onboarding
  └─ Compliance signals OK (certificate expiry, EICR/electrical from obligations, property-age heuristics)
  └─ Predictive operational rules GATED until:
       completed_operational_cycles >= 2
       (non-system, non-compliance-bridge, non-risk-propagation work orders/issues)

Property regen
  └─ Count only qualifying records for recurring / frequency rules
  └─ Suppressed predictive types removed on next regen (unless operational debt)

Issue: triaged → ready_for_work_order (job created)
  └─ Primary action: Assign contractor → /operations/jobs/{id}

Risk signal: active → create_work_order / schedule_inspection
  └─ Cognition key normalized on client → executable handler
```

## 3. Fixes applied

| Area | Change |
|------|--------|
| **Governance** | New `risk_signal_operational_history_governance.py` — eligibility, qualifying record filter, customer-safe reasons |
| **Risk regen** | Recurring / frequency / SLA rules gated; qualifying-only counts |
| **CTA** | `normalizeOperationalPrimaryKey()` + URL navigation for cognition keys |
| **Issues** | `NextActionHero`, row primary actions, assign contractor for `ready_for_work_order` |
| **Continuation** | `continuation_cta.key` from `next_job_actions[0].id` |
| **Language** | `sanitize_issue_for_customer()` wired into cognition attach paths |

## 4. Regression

| Suite | Result |
|-------|--------|
| `test_risk_signal_operational_history_governance.py` | PASS (5) |
| `test_sanitize_issue_for_customer.py` | PASS (1) |
| `test_customer_operational_language_service.py` | PASS |
| `test_risk_signal_regen_governance.py` | PASS |
| `test_operational_cognition_service.py` | 1 pre-existing failure (requirement guidance flag — unrelated) |

## 5. Classification

| Item | Classification |
|------|----------------|
| Premature predictive signals | **LIFECYCLE_GOVERNANCE_GAP** — fixed |
| Dead risk-signal CTA | **CLIENT_KEY_MISMATCH** — fixed |
| Contractor assign dead state | **WORKFLOW_UI_GAP** — fixed |
| Language leakage | **CUSTOMER_LANGUAGE_GAP** — fixed (issues); risk labels already via `domain_labels.json` |

## 6. Remaining watchlist

- **Deploy required** before staging browser proof reflects fixes
- **Existing stale signals** in Mongo need one regen cycle (predictive worker or manual regen) to drop suppressed types
- **PropertyDetailPage** issue drawer still uses legacy CTA guards — align in follow-up
- **Browser E2E** on staging post-deploy: Sophie (onboarding), Nancy (mature), partial-compliance fixture
- Pre-existing `test_requirement_envelope_false_progression` failure — track separately

## 7. Commit / push

Changes are **local only** — commit and push when you approve.
