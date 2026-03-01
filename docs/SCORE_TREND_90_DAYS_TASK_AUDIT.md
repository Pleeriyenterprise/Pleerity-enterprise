# Score Trend (90 days) – Task vs codebase audit

**Task:** Upgrade "Score Trend (90 days)" block to an enterprise-grade trend chart with Portfolio/Property toggle.  
**Reference:** Attached design shows Portfolio|Property toggle, summary stats (Current, 30-day delta, Best/Worst in 90 days), line chart with muted risk bands, legend, thin line, subtle grid.

---

## 1. Current implementation (no duplication)

### 1.1 Backend – two separate data flows

| Item | Current state | Location |
|------|----------------|----------|
| **Portfolio trend (snapshot-based)** | `compliance_score_history`: `client_id`, `date_key` (YYYY-MM-DD), `score`, `grade`, `color`, `breakdown`, `stats`, `created_at`. Daily snapshot job writes one row per client per day. | `services/compliance_trending.py`: `capture_daily_snapshot`, `get_score_trend` |
| **Portfolio trend API** | `GET /api/client/compliance-score/trend?days=30&include_breakdown` → returns `data_points` [{date, score, …}], `sparkline`, `change_7d`, `change_30d`, `min_score`, `max_score`, `latest_score`. **Default days=30**, not 90. | `routes/client.py` ~73; `compliance_trending.get_score_trend` |
| **Portfolio trend (event-based)** | `score_events`: SCORE_RECALCULATED events with `score_after`. Timeline buckets by week/day; if no events, **fallback = current score as single point** (placeholder line). | `services/score_events_service.py`: `get_timeline` |
| **Timeline API** | `GET /api/client/score/timeline?days=90&interval=week` → returns `points` [{date, score}], `last_updated_at`. **Portfolio only**; no property-level endpoint. | `routes/client.py` ~109 |
| **Daily snapshot job** | Runs at **02:00 UTC** (not 00:10). Calls `capture_all_client_snapshots()` → `capture_daily_snapshot(client_id)` per active client. Writes only to **compliance_score_history** (portfolio). **Does not** write per-property daily snapshots. | `server.py` CronTrigger(hour=2, minute=0); `job_runner.run_compliance_score_snapshots` |
| **Property-level history** | `property_compliance_score_history`: written on **every** recalc (event-driven), not once per day. Fields: `property_id`, `client_id`, `score`, `breakdown_summary`, `created_at`, `reason`, `actor`. No `date_key`; multiple entries per day possible. | `compliance_scoring_service.recalculate_and_persist`; `database.py` indexes |

### 1.2 Frontend – Score Trend card

| Item | Current state | Location |
|------|----------------|----------|
| **Data source for card** | **Score Trend (90 days)** card uses **score/timeline** (event-based), **not** compliance-score/trend. Fetches `GET /api/client/score/timeline?days=90&interval=week`. | `ClientDashboard.js`: `fetchScoreTimeline` → `setScoreTimeline` |
| **Chart** | **Sparkline** (minimal SVG): small width/height, no axes, no grid, no risk bands. Shows `scoreTimeline.points` as line + area; trend direction from first vs last point. | `components/Sparkline.js`; Card content ~551–567 |
| **Summary stats** | Only "Net change last 30 days" (derived from `scoreTimeline.points` in a useMemo). No "Current", "Best in 90 days", "Worst in 90 days" in the card. | `ClientDashboard.js` netChange30, line 568–571 |
| **Toggle** | **None.** No Portfolio | Property toggle; no property dropdown. | — |
| **Empty state** | "Trend will appear after the first score update." When timeline returns a single point (fallback), a flat line is shown (task says "no placeholder line remain"). | ~593–596 |
| **Chart library** | **recharts** is in `package.json` but **not used** anywhere in the frontend. Sparkline is custom SVG. | `frontend/package.json` (recharts) |

### 1.3 Unused / alternate

- **GET /api/client/compliance-score/trend** is called by `fetchScoreTrend` → `setScoreTrend`, but the **Score Trend (90 days) card does not use `scoreTrend`**; it uses `scoreTimeline` from score/timeline. So snapshot-based trend exists in API but is not wired to the 90-day card.
- **score_events** timeline can be sparse (only when recalc runs); task explicitly says "do NOT compute trend purely from current state" and "Implement daily snapshot storage", so event-based timeline alone does not satisfy the task.

---

## 2. Task requirements vs current state

| Requirement | Task | Current | Gap / conflict |
|-------------|------|---------|----------------|
| **Data source** | Daily snapshot storage; do NOT compute trend purely from current state. | Portfolio: daily snapshots in `compliance_score_history` (02:00). Card uses **event-based** timeline (sparse; fallback = current score). | **Conflict:** Card uses event timeline; task wants snapshot-based trend. Snapshot data exists but is not used for the 90-day card. |
| **Collections** | 1) score_history_portfolio: { user_id, date, score_int, created_at } 2) score_history_property: { user_id, property_id, date, score_int, created_at } | 1) compliance_score_history: client_id, date_key, score (+ grade, color, breakdown, stats). 2) property_compliance_score_history: per **recalc** (not daily), no date_key. | **Naming/schema:** Task uses "user_id"; app is client-scoped → **client_id** is correct. Task wants **score_int** and simple date; current has extra fields. Property: no **daily** snapshot collection. |
| **Job time** | Daily at 00:10 server time. | 02:00 UTC. | Minor: align to 00:10 or keep 02:00 and document. |
| **Job scope** | For each active user: compute portfolio score → store; compute each property score → store. | Only portfolio snapshot per client. No per-property daily snapshot. | **Gap:** Property daily snapshots not implemented. |
| **API** | GET /api/score-trend/portfolio?days=90 → [{date, score}]; GET /api/score-trend/property/{id}?days=90 → [{date, score}]; summary stats (current, delta_30, best_90, worst_90). | GET /api/client/compliance-score/trend?days=30 (portfolio, snapshot); GET /api/client/score/timeline?days=90 (portfolio, events). No property trend endpoint. No /api/score-trend/*. | **Path:** Prefer extending under `/api/client/` (client_route_guard). Add property trend endpoint. Return or compute summary stats. |
| **Default** | Default = Portfolio trend. | Card is portfolio-only. | Align: default Portfolio. |
| **Toggle** | Portfolio \| Property; if Property → dropdown, then chart for that property. | No toggle; no property dropdown. | **Missing:** Toggle + property selector + load property trend. |
| **Chart** | Real line chart; replace placeholder; single line; muted risk bands; thin line; subtle grid; muted colours. | Sparkline (no axes/grid/bands). recharts available but unused. | **Missing:** Full line chart with risk bands, grid, summary stats. |
| **Summary stats** | Current score, 30-day delta, Best in 90 days, Worst in 90 days. | Only 30-day net change derived from timeline. | **Missing:** Current, best_90, worst_90 in API/UI. |
| **Footer** | e.g. "Calculated across all tracked items". | "Last updated …" only. | Optional copy. |
| **Mobile** | Stack controls; responsive. | Card is responsive; no toggle to stack. | Ensure toggle/dropdown stack on small screens. |
| **Performance** | Lazy-load chart; fixed height; avoid layout shift. | No lazy load; fixed height on Sparkline. | Use fixed height for new chart; lazy-load if needed. |

---

## 3. Conflicts and recommended resolution

### 3.1 Snapshot vs event-based trend

- **Conflict:** Task requires daily snapshots; the 90-day card currently uses event-based timeline (and fallback current score = placeholder).
- **Recommendation:** Use **snapshot-based** trend for the card. Keep `compliance_score_history` as the source for **portfolio** trend (already daily). Add **property-level daily snapshot** storage and feed the **property** trend from that. Do **not** add a second portfolio collection "score_history_portfolio" with a different schema; extend usage of `compliance_score_history` for portfolio and add one new collection only for **property** daily snapshots (see 3.2). Deprecate or repurpose the card’s use of score/timeline for the **line** (timeline can stay for "What Changed" or other uses).

### 3.2 New collections vs existing

- **Task:** score_history_portfolio, score_history_property with user_id, date, score_int.
- **Recommendation:**  
  - **Portfolio:** Keep **compliance_score_history** (client_id, date_key, score). Treat as the portfolio trend source; ensure 90-day window and summary stats from it. Use **client_id** (no new "user_id" collection).  
  - **Property:** Add a single new collection, e.g. **property_score_daily** (or keep task name **score_history_property**): `client_id`, `property_id`, `date` (YYYY-MM-DD), `score` (int), `created_at`. One document per (property_id, date). Index (client_id, property_id, date). Do **not** duplicate portfolio data into a second portfolio collection.

### 3.3 API paths

- **Task:** GET /api/score-trend/portfolio and GET /api/score-trend/property/{id}.
- **Recommendation:** Keep client APIs under existing prefix and guard. Add or extend:  
  - **GET /api/client/compliance-score/trend?days=90** (or **GET /api/client/score-trend/portfolio?days=90**) → portfolio points + summary (current, delta_30, best_90, worst_90) from `compliance_score_history`.  
  - **GET /api/client/score-trend/property/{property_id}?days=90** (new) → property points + summary from the new property daily snapshot collection.  
  Use **client_route_guard** and validate property belongs to client. Avoid a separate `/api/score-trend/*` mount without auth so no duplication or security gap.

### 3.4 Job schedule

- **Task:** 00:10 server time. **Current:** 02:00 UTC.  
- **Recommendation:** Either move snapshot job to 00:10 UTC or leave at 02:00 and document as "daily early morning". If 00:10 is mandatory, add one job at 00:10 that runs portfolio + property snapshots; do not run two separate snapshot jobs (no duplication).

### 3.5 Frontend: one source for the card

- **Recommendation:** Drive the **Score Trend (90 days)** card from the **snapshot-based** trend API (portfolio or property), not from score/timeline. Remove dependency on score/timeline for the chart so the "placeholder" single-point line goes away once 90-day snapshot data is used. Keep timeline API for "What Changed" or elsewhere if needed.

---

## 4. Implementation checklist (no code yet)

- **Backend**  
  - [ ] Add **property_score_daily** (or score_history_property) collection and index (client_id, property_id, date).  
  - [ ] Extend daily snapshot job: for each active client, (1) write portfolio snapshot to **compliance_score_history** (existing), (2) for each property compute score and upsert **property_score_daily** for today’s date. Optionally align job time to 00:10.  
  - [ ] Expose portfolio trend for 90 days: extend or add GET that returns `[{date, score}]` + summary (current, delta_30, best_90, worst_90) from `compliance_score_history`.  
  - [ ] Add GET /api/client/score-trend/property/{property_id}?days=90 returning points + same summary from **property_score_daily**, with client_route_guard and property ownership check.  
- **Frontend**  
  - [ ] Replace Sparkline with a **line chart** (e.g. recharts) in the Score Trend card: single line, fixed height, thin line, subtle grid.  
  - [ ] Add **muted risk bands** behind the chart (Critical 0–39, At Risk 40–59, Moderate 60–79, Healthy 80+) using existing risk band semantics; add legend.  
  - [ ] Add **Portfolio | Property** segmented toggle; when Property, show **property dropdown** (user’s properties), load property trend and summary.  
  - [ ] Show **summary stats**: Current score, 30-day change, Best in 90 days, Worst in 90 days (from API or derived from points).  
  - [ ] Ensure responsive layout (stack controls on mobile), no placeholder line (use snapshot data only), optional footer e.g. "Calculated across all tracked items".

---

## 5. File reference

| Area | Files |
|------|--------|
| Portfolio snapshot & trend | `backend/services/compliance_trending.py`, `backend/routes/client.py` (compliance-score/trend), `backend/job_runner.py` (run_compliance_score_snapshots), `server.py` (cron) |
| Event timeline | `backend/services/score_events_service.py`, `backend/routes/client.py` (score/timeline) |
| Property history | `backend/services/compliance_scoring_service.py` (property_compliance_score_history), `backend/routes/admin.py` (get_property_compliance_score_history) |
| Dashboard card | `frontend/src/pages/ClientDashboard.js` (Score Trend card, fetchScoreTimeline, netChange30), `frontend/src/components/Sparkline.js` |
| Risk bands / design | `frontend/src/utils/riskLabel.js`, design attachment (risk bands, legend) |
| DB indexes | `backend/database.py` (compliance_score_history, property_compliance_score_history, score_events) |

This audit is the single reference for implementing the Score Trend (90 days) upgrade without duplicating or conflicting with existing snapshot and timeline behaviour.
