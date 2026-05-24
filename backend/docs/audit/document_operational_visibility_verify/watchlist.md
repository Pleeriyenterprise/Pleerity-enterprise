# Document operational visibility watchlist

**Run:** `20260524T224107Z`  
**Classification:** `BLOCKED`

## Blockers

- **Frontend not deployed** — production still serves `main.457d1533.js` without operational-queue UX (`filter-queue-view`, Evidence Registry sections). Backend API at `531f0e74` is live.
- **No automated Vercel/workflow** in repo — frontend deploy may be manual; confirm pipeline before re-run.

## Harness notes

- Reconciliation probe uses `document_type=Other` → immediate `INTENTIONALLY_UNLINKED`, not `RECONCILIATION_REQUIRED`. Use bounded upload without requirement and without Other type for CTA probe.
- Cross-surface 401 on `/today/items` and `/client/command-center` in this run — likely token expiry during long session; re-login before cross-surface reads.
- `/api/version` commit_sha remains `unknown` on Render — behavioural deploy proof used.

## API strengths (pre-browser)

- 21/21 documents carry `document_client_visibility_state` + `document_registry_section`
- Property evidence registry: 1 active, 9 pending review, 4 expiring soon, 1 historical, 6 attachments
- 4 expiry resurfacing documents within 90-day window
- G10 authority distinctions preserved (upload ≠ verified, no hidden reconciliation debt)
