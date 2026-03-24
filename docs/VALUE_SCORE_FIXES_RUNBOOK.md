# Value / trust fixes — short runbook

Companion to **`VALUE_SCORE_FIXES_REPORT.md`**. Describes **current** behaviour and how to verify the “no misleading placeholders” rule after future changes.

---

## 1. How client tasks are generated

1. Client opens **`/tasks`** → `GET /api/client/tasks` (optional `property_id`).
2. Server runs **`get_unified_tasks_for_client`**:
   - Pulls **`_fetch_client_actions`** (priority action engine): requirements (overdue / expiring / missing doc), active risk signals, **SLA breached/near-breach work orders**, **open work orders** (OPEN / ASSIGNED / IN_PROGRESS; de-duplicated against SLA rows), pending invoice approvals, open maintenance issues.
   - Maps each action to a task with **sections** (urgent / upcoming / in_progress), **urgency_level**, **timing_label** (due/overdue text), **primary_action_url**.
   - Applies **client_task_state** overrides (snooze, dismiss, done, hidden).
   - Appends **recently_completed** from requirements (COMPLIANT/VALID) and invoices (approved/paid) in a **14-day** window.
3. **Inbox actions** (snooze/dismiss/done) are **overlay only** — underlying compliance/WO/approval state unchanged until user completes the real flow.

**Verify:** Create one item per source (requirement overdue, risk, SLA WO, **non-SLA open WO**, pending approval, open issue); confirm each appears and CTA navigates to the correct screen. **Property filter:** Tasks UI passes `property_id` to `GET /api/client/tasks` when a property is selected.

---

## 2. How KPIs are computed (dashboard)

| KPI | Source | Notes |
|-----|--------|--------|
| Compliance score / grade | `GET /api/client/compliance-score`, portfolio summary, command-center bundle | After load: **“No data yet”** / **N/A** (compact) instead of indefinite `—` |
| Open **issues** | `GET /api/client/maintenance/issues/open-count` | **Issues collection**, not work orders |
| Work orders (SLA) | Client dashboard loads WO list with SLA filter for counts/cards | Distinct from “issues” |
| Maintenance spend (month) | `GET /api/client/finance/maintenance-spend-this-month` | **Paid** invoices, **UTC month**, invoicing-gated |
| Task counts (digest) | From **`getCommandCenter`** | Summary counts for tiles; **tab visibility refetch** also calls **`getCommandCenter`** (same params as initial load, including optional `property_id` scope) |

**Verify:** With invoicing off, spend tile must **not** appear. With maintenance off, issues/WO tiles follow existing gates.

---

## 3. How freshness timestamps work (today)

Returned inside **`/api/client/tasks`** (`freshness` object) and related digests:

- **`score_updated_at`:** From portfolio compliance **catalog** payload (`get_portfolio_compliance_from_catalog` → `updated_at`).
- **`risk_signals_updated_at`:** Latest **`risk_signals`** document for client (`updated_at` or `generated_at`).
- **`tasks_refreshed_at`:** Set to **current request time** (API generation instant), not a persisted job cursor.

The **`automation_status`** collection stores **`last_score_recalc_at`** (after queue-based compliance recalc in `job_runner`) and **`last_risk_refresh_at`** (after risk signal generation for a property in `risk_signal_service`). Unified tasks / command-centre **`freshness`** also includes catalog **`score_updated_at`** and latest **`risk_signals`** row timestamps.

The **client dashboard** and **Tasks** summary show compliance/risk freshness plus, when present, **last automated score recalc** and **last automated risk refresh**, with **“May be outdated”** if score data is older than **48h** or risk data older than **72h** (heuristic).

**Verify:** After a recalc job and a risk generation run, `GET /api/client/command-center` should include `freshness.last_automation_*` fields; UI strip lists them when set.

---

## 4. “No placeholders” rule (QA checklist)

After changes, confirm:

1. **No indefinite `—`** on primary KPI tiles once loading finished — use **0**, **“No data yet”**, or **hide** the tile.
2. **Open issues** label matches **issues** count, not work orders.
3. **Spend** label matches business definition (**paid** vs **approved** — document in UI subtitle).
4. **Tasks** CTAs deep-link to the screen that resolves the item (upload, approval, WO, issue, risk).
5. **Feature gates** respected (invoicing, maintenance, predictive).

---

## 5. Admin ops — compliance & audit (implemented)

- **`/admin/ops/compliance`** — **`AdminOpsCompliancePage`**: table from **`GET /api/admin/ops/compliance-clients-summary`** (requirement aggregates per client; optional single-client filter loads portfolio score on demand). Links to client record and ops/risk.
- **`/admin/ops/audit`** — **`AdminOpsAuditPage`**: paged table from **`GET /admin/audit-logs`** with filters (client id, action, date range) + links to main admin, automation, ops overview.

**Verify:** Open both routes signed in as admin; compliance summary returns rows when requirements exist; audit page loads events and pagination works.

---

## 6. Contractor invoice loop (current)

- **UI:** `ContractorDashboardPage.js` — work order detail → **Submit invoice** (completed-type statuses); `submitInvoice` API.
- **Client:** Approvals workspace lists pending invoices.

**Verify:** Submit as contractor → appears under client **Approvals** → approve/reject flows and audit entries per `approval_service` / `AuditAction` map.
