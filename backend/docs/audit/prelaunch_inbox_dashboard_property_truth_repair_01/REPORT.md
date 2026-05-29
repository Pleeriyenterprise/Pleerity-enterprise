# PRELAUNCH-INBOX-DASHBOARD-PROPERTY-TRUTH-REPAIR-01

Generated: 2026-05-29T11:45:00+00:00

## Classification

**PARTIAL** — fixes committed; staging browser still on pre-fix bundle (Today summary 0 / Dashboard 14 mismatch reproduced).

## Root cause (Today)

`ClientTasksPage.load()` stored the entire `fetchOperational()` wrapper `{ data, fromCache, refreshing }` in React state instead of `hit.data`.  
`payload.tasks` was therefore undefined → all bucket counts rendered **0** while `ClientDashboard.fetchTodayInbox()` correctly used `hit.data`.

## Remediation

1. **ClientTasksPage.js** — unwrap `.data` for today items, requirements, and compliance summary fetches.
2. **PropertyDetailPage.js** — use shared `getPropertyDisplayName()` for header; populate identity fields from compliance detail.
3. **portfolio.py** — compliance-detail response includes address identity fields + canonical `property_name`.
4. **rent_attention_projection.py** — sync `summary.urgent_count` after rent merge.
5. Today UI — category-filter and bucket-continuation disclosure banners.

## API proof (nancy@yopmail.com staging)

| Source | Count |
|--------|-------|
| `/today/items` urgent/upcoming/in_progress | 24 / 8 / 8 (sum **40**) |
| Dashboard Today KPI (same endpoint + alignment) | Should match after deploy |
| Command Centre urgent actions | 22 (urgent-only slice) |

## Browser (pre-deploy)

- Today summary: 0 / 0 / 0 (confirms bug on live bundle)
- Property detail: still “Unnamed property” on pre-fix bundle

## Blockers

- Vercel frontend deploy with Today + PropertyDetail fixes
- Post-deploy browser re-run for **VERIFIED_OPERATIONALLY**
