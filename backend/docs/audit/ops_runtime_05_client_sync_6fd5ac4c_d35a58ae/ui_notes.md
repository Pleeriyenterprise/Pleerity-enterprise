# UI notes — F5 client sync (`20260523T184731Z`)

**Classification:** `VERIFIED_OPERATIONALLY`

- Browser auth: **form login** at `/login/client` (no localStorage fallback required).
- Surfaces exercised: `/dashboard`, `/operations/issues`, `/operations/work-orders`, `/operations/risk-signals`, `/operations/issues/{id}`, `/operations/jobs/{wo}`, `/properties/{property_id}`.
- Job detail reload retained marker/WO visibility (refresh persistence).
- List views show portal chrome consistently; marker text may be below fold — issue/WO IDs used as secondary proof in harness.
