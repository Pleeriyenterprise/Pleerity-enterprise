# PRELAUNCH-CONTRACTOR-QUOTE-VISIT-RUNTIME-TRUTH-VERIFY-01 — REPORT

**Classification:** VERIFIED_OPERATIONALLY  
**Commit:** `03e06200` (staging API + frontend)  
**Captured:** 2026-05-30T17:30:39Z

## Runtime seed (Part 1)

| Field | Value |
|-------|-------|
| client_id | `6fd5ac4c-3fd4-4112-ade7-156977deb49f` |
| property_id | `d35a58ae-3c81-491c-9694-1d021dd3b8ad` |
| work_order_id | `3a7eecbb-4c8e-45c3-970c-2578f7ffec32` |
| contractor_id | `a1f2e3b4-c5d6-4789-a012-3456789abcde` |
| contractor_portal_user | `f2-ops-heating-wales@yopmail.com` |
| workflow_mode | QUOTE_FIRST |
| price_status (seed) | AWAITING_QUOTE |
| schedule_status (seed) | — |
| canonical_status | SCHEDULED |
| visit_before_quote (post-fix) | **blocked** (HTTP 400) |

## Pre-fix runtime mismatches (proved)

1. **METRIC_LIST_DRIFT** — `jobs.active` (43) included waiting-on-client jobs; frontend execution tile (41) excluded them; section header showed `(N assigned)` with empty active list.
2. **CONTRACTOR_PORTAL_TRUTH_MISMATCH** — Urgent actions said “You're up to date” when jobs were in waiting-on-client queue.
3. **CONTRACTOR_PORTAL_TRUTH_MISMATCH** — Drawer next action showed dead “Open job” CTA when already open.
4. **QUOTE_VISIT_GATING_DRIFT** — QUOTE_FIRST allowed `propose_schedule` before quote approval (HTTP 200 on AWAITING_QUOTE job).

## Post-fix verification (Parts 2–10)

| Part | Result | Evidence |
|------|--------|----------|
| Contractor metrics | **PASS** | `execution_active` 41 = frontend 41; `waiting_on_client` 6 |
| Urgent actions | **PASS** | Browser: no false up-to-date; waiting copy when applicable |
| Drawer / Open job UX | **PASS** | Browser: waiting drawer has no dead Open job button |
| Quote negotiation (v1→rev→v2→rev→v3→approve) | **PASS** | `quote_negotiation_browser_runtime.json` |
| Visit negotiation (propose→reschedule×2→confirm) | **PASS** | `visit_negotiation_browser_runtime.json` |
| QUOTE_FIRST visit gating | **PASS** | API 400: “Visit times can be proposed only after the client approves your quote…” |
| Landlord Approve and authorise | **PASS** | `landlord_approve_v3` HTTP 200 in quote loop |
| Progress parity | **PASS** | Landlord/contractor price + schedule status match |
| Notifications | **PARTIAL** | API state transitions verified; contractor in-app N/A; email not probed |
| Cross-surface consistency | **PASS** | Dashboard, drawer, landlord job aligned post-fix |

## Remediation applied (Part 11)

- `contractor_dashboard_summary`: `jobs.execution_active`, `jobs.waiting_on_client`
- `contractor_may_propose_visit` + schedule API gate for QUOTE_FIRST
- `contractor_portal_waiting_on_others` helper
- `ContractorDashboardPage`: urgent waiting copy, active empty state, drawer waiting presentation
- `JobPage`: waiting presentation for navigation-only next action

## Browser proof

Screenshots: `screenshots/contractor_dashboard.png`, `contractor_drawer.png`, `landlord_job.png`

Harness: `backend/tmp_prelaunch_contractor_quote_visit_runtime_truth_verify_01.py`

## Screenshot-reported job (Blessing Bolon / Laurel Gardens EPC)

Job IDs from user screenshots (`e28d401f…`) were not in Nancy tenant scope (404). Audit used tenant-scoped seed on Wales property with same workflow semantics.
