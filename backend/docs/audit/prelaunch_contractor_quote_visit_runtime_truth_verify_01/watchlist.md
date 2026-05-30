# Watchlist — PRELAUNCH-CONTRACTOR-QUOTE-VISIT-RUNTIME-TRUTH-VERIFY-01

## Monitor

- **Legacy jobs** created before visit gating may still have visit proposed + quote unapproved; new proposals are blocked under QUOTE_FIRST.
- **`jobs.active` vs `jobs.execution_active`** — both exposed intentionally; UI uses `execution_active` for contractor-action tile.
- **Blessing Bolon / Laurel Gardens EPC** — not in Nancy staging tenant; reproduce on correct client/contractor pairing if that specific account is in scope.
- **Admin progress surface** — landlord + contractor API parity captured; admin UI not browser-probed this run.
- **Contractor in-app notifications** — out of scope; email delivery not probed; portal state + API transitions used as contractor guidance.

## Optional follow-up

- Browser proof of landlord “Approve and authorise work” click on a live QUOTED compliance job (API loop verified).
- Command Centre / Today cross-links for same work order lineage.
