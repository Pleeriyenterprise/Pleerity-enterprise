# Value / trust fixes — codebase inspection report

**Date:** 2026-03-24  
**Purpose:** Map the repo against the strict task brief (unified tasks, KPI truthfulness, spend, urgency, freshness, admin ops pages, optional contractor invoices). **No code changes in this document** — inspection only.

**API naming note:** The brief references `GET /api/portal/tasks`. This codebase mounts the client API under **`/api/client/*`** (FastAPI `client` router), not `/api/portal/*`. Aliasing or renaming would be a **breaking contract change** for the SPA and any integrations. **Safest enterprise approach:** keep **`/api/client/tasks`** as the canonical path; document the mapping in the runbook. Add `/api/portal/*` only if product explicitly requires a second public alias (duplicate surface area).

---

## 1. Client routes & pages (actual)

| Area | Path(s) | Component / behaviour |
|------|---------|------------------------|
| Dashboard | `/dashboard` | `ClientDashboard.js` — score, portfolio, KPI strip, tasks digest, command-center snapshot, priority actions, maintenance spend tile (gated), work order / risk tiles |
| Tasks / Inbox | **`/tasks`** (primary); **`/app/tasks`** → redirect to `/tasks` | `ClientTasksPage.js` — “Command Centre”; `App.js` line ~307, ~352 |
| Nav | Sidebar | `ClientPortalLayout.jsx` — item **Tasks** → `/tasks` |
| Operations | `/operations/*` | Issues, work orders, approvals, risk-signals (separate pages) |
| Property | `/properties/:id` | Includes priority actions strip |

**Brief alignment:** Unified inbox exists at **`/tasks`** with nav + dashboard CTAs (“Open Command Centre”, “All tasks”). Naming mixes **“Command Centre”** (page H1) and **“Tasks”** (nav) — not a functional conflict; consider copy consistency only.

---

## 2. Admin ops routes (actual)

| Path | Implementation |
|------|----------------|
| `/admin/ops` | `AdminOpsOverviewPage.js` — cards to maintenance, contractors, risk, feature-controls |
| **`/admin/ops/compliance`** | **`AdminOpsPlaceholderPage`** — generic placeholder copy |
| **`/admin/ops/audit`** | **`AdminOpsPlaceholderPage`** — generic placeholder copy |
| `/admin/ops/maintenance`, `/contractors`, `/risk`, `/feature-controls` | Real pages |

**Gap vs brief:** Compliance + Audit are **empty placeholders** — highest-trust fix is minimal real lists or an honest “coming soon” with **links** to `GET /admin/audit-logs` (see `admin.py`) and existing client/compliance admin surfaces.

---

## 3. Backend aggregation & endpoints (client)

| Endpoint | Role |
|----------|------|
| **`GET /api/client/tasks`** | Full unified payload: sections (`urgent`, `upcoming`, `in_progress`, `recently_completed`, `snoozed`, `hidden`), `summary`, `freshness`, `spend_this_month`, `activity_feed` — `unified_tasks_service.get_unified_tasks_for_client` |
| `GET /api/client/tasks/digest` | Lighter digest for dashboard cards |
| `GET /api/client/command-center` | Composed snapshot (reuses digest + slim task rows + risks + compliance summary) |
| `GET /api/client/priority-actions` | Ranked list only (orchestration layer) |
| `GET /api/client/finance/maintenance-spend-this-month` | Monthly spend (invoicing-gated) |
| `GET /api/client/maintenance/issues/open-count` | **Real open issues** count (`maintenance_issues_service.count_open_issues`) |
| `POST /api/client/tasks/override` | Inbox overlay: snooze / dismiss / done / restore (does not mutate compliance/WO) |

**Brief vs implementation — duplicate API risk:** Introducing **additional** `GET /api/portal/dashboard-kpis` and `GET /api/portal/freshness` would **overlap** command-center + tasks + existing dashboard fetches unless they **replace** them in one migration. **Safest approach:** extend existing responses (`/client/tasks`, `/client/command-center`, dashboard JSON) with any missing fields; avoid parallel “portal” KPI endpoints unless product mandates a separate BFF.

---

## 4. How unified tasks are built (single source)

1. **`priority_actions._fetch_client_actions`** loads ranked actions from:
   - Overdue / expiring / missing-document **requirements**
   - **Risk signals** (active)
   - **Work orders** with SLA **`breached`** or **`near_breach`** only (not all OPEN/IN_PROGRESS)
   - **Pending invoice approvals**
   - **Open maintenance issues** (multiple non-terminal statuses)
2. **`unified_tasks_service`** maps each action to a task DTO: `urgency_level`, **`metadata.timing_label`** (“Due in X days”, “Overdue by X days”, “Due today”), `primary_action_url`, `filter_tags` (compliance / operations / approvals / risks / overdue).
3. **Overrides** (`client_task_state_service`) merge snooze/dismiss/done/hidden server-side.
4. **Recently completed:** derived from **requirements** moved to COMPLIANT/VALID (14-day window) + **invoices** approved/paid (14-day) — **not** a full audit ledger feed.
5. **Freshness block:** `portfolio` compliance catalog `updated_at`; latest **`risk_signals`** `updated_at`/`generated_at`; `tasks_refreshed_at` = request time.

---

## 5. Gaps vs strict brief (no duplication — additive work only)

| Requirement | Status | Notes |
|-------------|--------|--------|
| Single merged inbox | **Largely done** | `/tasks` + `/api/client/tasks` |
| Merge **all** open WOs (OPEN/ASSIGNED/IN_PROGRESS) | **Gap** | Only **SLA breached / near breach** WOs appear in tasks. Adding generic open WOs would be **additive** in `priority_actions` (new action type or query) — avoid duplicating WO list UI logic on the client. |
| Filter **by property** on Tasks page | **Gap** | API supports `property_id` on `/client/tasks` (verify query param wiring in route); **UI** has type/overdue chips but **no property dropdown** — additive. |
| “Recently resolved” **7 days** + **audit ledger** | **Partial** | Backend uses **14 days**; driven by requirement/invoice state, not audit events. Narrowing window or adding audit-backed rows is additive. |
| “Mark done” must not lie | **Addressed in product copy** | Done/Dismiss/Snooze are explicitly **inbox-only**; help link + toasts. Brief said avoid lying — current UX is honest; **do not** add a fake “completed” without state change. |
| Dashboard no “—” | **Gap** | See §6 |
| Spend metric | **Done** (paid, UTC month) | Brief said approved **or** paid; code uses **`paid` + `paid_at`** only — document or optionally add approved-this-month as second line (additive). |
| Urgency shared component | **Partial** | Tasks page has badges + `timing_label`; dashboard priority cards may differ — extract **one** `UrgencyBadge` / `DueChip` component (additive, no rule changes). |
| Freshness on dashboard | **Partial** | Tasks summary shows score/risk/tasks refreshed; full dashboard hero may not show all three — wire or hide (additive). |
| `automation_status` collection | **Not present** | Freshness is **derived** from catalog + risk_signals + request time. Brief’s keyed collection would be **additive**; avoid duplicating timestamps already on domain documents unless jobs need a single heartbeat row. |
| Stale warning tooltip | **Gap** | Needs policy (e.g. score older than N hours) + UI |
| Admin compliance / audit pages | **Gap** | Placeholders only |
| Contractor invoice loop | **Implemented** | `ContractorDashboardPage.js` — submit invoice modal, `api.submitInvoice`, approvals copy; attachments may be partial — verify backend accepts `attachment_storage_key` if required |
| Unit/integration tests | **Gap** | No `test_*unified*`, `priority_actions`, or spend tests found under repo grep |

---

## 6. “—” and placeholder KPIs (ClientDashboard.js)

Observed patterns (non-exhaustive):

- **Score / grade:** `displayScoreInfo?.score ?? … ?? '—'` when no data loaded.
- **Open issues tile:** shows **`—`** while `openIssuesCountKpi === null` (loading or fetch failed). Count source is **issues**, not WOs — **not misleading** once loaded; **loading** should use skeleton/`…`/`0` per brief.
- **Portfolio table:** property score / risk / overdue / expiring use **`—`** when null.
- **Days until next expiry:** `'—'` when stat missing.
- **Command center compliance:** grade `—` if null.

**Professional approach:** For **end-user-visible metrics**, prefer **`0`**, **“No data yet”**, or **hide the tile** when the feature is off or the fetch failed — never indefinite **`—`** after load completes. **Do not** duplicate tiles; **wire or hide** existing ones.

---

## 7. Plan / feature gating (respect — do not change logic)

- **Invoicing:** `hasFeature('invoicing')` on client; routes use `_require_invoicing_enabled` / effective flags.
- **Maintenance workflows:** work orders, issues, open-issues count.
- **Predictive maintenance:** risk signals, some task inline actions.

Any new UI must **reuse `useEntitlements` / same backend guards** — no new gates.

---

## 8. Mongo collections / models (relevant)

| Collection / area | Use in this scope |
|--------------------|-------------------|
| `requirements` | Compliance tasks, recently completed |
| `work_orders` | SLA-surfaced tasks; contractor portal |
| `maintenance` issues (service) | Open issues count + task items |
| `risk_signals` | Tasks + freshness |
| `invoices` | Approvals tasks, spend, recently completed |
| `client_task_overrides` / activity (via `client_task_state_service`) | Snooze/dismiss/done |
| `audit_logs` | Admin audit API exists; not yet driving client “resolved” feed |
| `compliance_score_history`, `property_compliance_score_history` | Indexed in `database.py`; trend/history elsewhere |
| **`automation_status`** | **Not in codebase** — optional future |

---

## 9. Conflicting instructions (explicit)

1. **API path `/api/portal/*` vs `/api/client/*`:** Duplicate endpoints = two contracts to maintain. **Recommendation:** document equivalence; implement portal alias only if required for external consumers.
2. **“No mark done that lies” vs existing Done/Dismiss:** Product already scopes these as **inbox-only** with education. **Recommendation:** **keep** behaviour; tighten copy if needed — **do not** remove without replacing progress UX.
3. **Spend: approved vs paid:** Brief allows approved; implementation counts **paid** only. **Recommendation:** keep **paid** as “real spend”; if stakeholders want **approved exposure**, add a **second** labelled metric (additive).
4. **Recently resolved window:** Brief says 7 days; code uses **14**. **Recommendation:** align copy + query in one change when scheduled.

---

## 10. Recommended implementation order (updated for repo reality)

1. ~~Inspection doc~~ **This file** + runbook  
2. **Close gaps without duplication:** property filter on Tasks UI; optional open-WO tasks in `priority_actions`; dashboard “—” → 0/hide/copy  
3. Shared urgency component → dashboard + tasks  
4. Freshness on dashboard + optional stale tooltip (derive first; `automation_status` only if jobs cannot expose timestamps)  
5. Admin compliance + audit minimal pages (link to `/admin/audit-logs` and existing APIs)  
6. Tests for aggregation, open-issues count, spend  
7. Contractor attachments audit (optional polish)

---

## 11. Drift / bug to fix when touching dashboard

`ClientDashboard.js` **visibility refetch** still calls **`getTasksDigest`** while initial load uses **`getCommandCenter`**. That can **desync** digest vs command-center after tab focus. **Fix:** refetch `getCommandCenter` (or unified digest source) in the same handler — **single source of truth** (small, non-duplicative fix).
