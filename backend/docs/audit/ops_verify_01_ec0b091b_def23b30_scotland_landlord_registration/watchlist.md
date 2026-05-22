# Scotland landlord registration — OPS-VERIFY watchlist

## Classification (post-remediation)
**VERIFIED_OPERATIONALLY** — same-run browser + persistence + inspect + refresh (2026-05-22).

## Pilot
- **client_id:** `ec0b091b-105d-4b78-9711-7ab143999cef`
- **property_id:** `def23b30-efa5-41f9-a9cc-7fb69f9e9024`
- **requirement_id:** `3708620b-82fb-4d90-9f17-5b800777e554`

## Remediation applied
1. Property resolve deeplink waits for `loading === false`, opens guided modal before stripping query, stub row when requirements list not yet hydrated.
2. Scotland bounded applicability reconciliation (backend overlay + frontend suppress N/A CTA).
3. CRA dev `setupProxy.js` for `/api` → `:8000` when `REACT_APP_BACKEND_URL` unset.

## Non-blocking watchlist
- Prior diagnostic CER remains on property; run used pre-existing baseline (cer_count 1 → delta +1 on new submit).
- Authority stays `MISSING` with `PENDING_REVIEW` non-document status (expected; no false VERIFIED_CURRENT).
- `GET /compliance-detail` 404 for pilot property (requirements list fallback OK).
- Local OPS harness also proxies `/api` in Playwright when env proxy absent.

## Next registration-stack obligation
**May proceed** to `rent_smart_wales` under same OPS-VERIFY standard.
