# Before vs after UX flow

## Before

| Page | Behaviour | User perception |
|------|-----------|-----------------|
| **Today** | Page chrome visible; large grey pulse skeleton blocks with no copy | “Is it broken? Is there no data?” |
| **Command Center** | Full-page shell + 4-row skeleton until primary bundle returns; secondary = tiny grey text | Long blank wait; secondary feels invisible |
| **Dashboard** | Full-page shell + 6-row skeleton; KPI row shows `…` with no explanation | KPI area feels empty; no progress signal |

Loading, empty, and error states were visually similar (grey blocks / ellipsis).

## After

| Page | Loading | Empty | Error |
|------|---------|-------|-------|
| **Today** | `PortalLoadingState` with staged checklist + title “Loading your operational inbox…” | Existing `today-genuinely-empty` alert (unchanged semantics) | `ErrorBanner` + **Retry** |
| **Command Center** | Staged “Analysing portfolio health…” while primary loads; primary content renders as soon as bundle arrives | Existing all-clear card | `ErrorBanner` (unchanged) |
| **Dashboard** | Staged page loader + KPI card previews with per-card messages; widgets progressively replace loaders | `KPI_NO_DATA` / section empty copy (unchanged) | `ErrorBanner` + Retry (unchanged) |

## Progressive disclosure

- **Command Center:** Primary projection unblocks page render; secondary risks / portfolio / jobs show `PortalCardLoading` independently.
- **Dashboard:** Shell + KPI cards render during initial fetch; each KPI/widget replaces its own loader when data arrives (`tasksDigest`, `valueInsights`, `protectionSnapshot`, etc.).
- **Today:** Header and filters remain visible; only inbox body shows loading panel until `payload` arrives.

## Analytics (new)

`portal_loading_started` → `portal_loading_completed` with `portal_loading_duration_ms` per page (`today`, `command_center`, `dashboard`).
