# Add Property address lookup parity

**Run:** `add_property_address_lookup_parity`  
**Date:** 2026-05-20

## Classification

**`IMPLEMENTED_TESTS_AND_API_VERIFIED`**

Not **`VERIFIED_OPERATIONALLY`** — full landlord browser walkthrough on dashboard Add New Property (postcode dropdown → select → submit → property detail → requirements) was not executed in this run (no Playwright in repo). Unit tests and staging API checks confirm shared intake endpoints and property create/list.

## Tests run

| Suite | Result |
|-------|--------|
| `frontend` `postcodeLookupApply.test.js` | PASS |
| `frontend` `useUkPostcodeLookup.test.js` | PASS |
| `frontend` `PropertyCreatePage.test.js` | PASS |
| `backend` `test_property_create_payload.py` | PASS (2) |

## API verification (staging)

- `GET /api/intake/postcode-autocomplete?q=SW1A` → 200, suggestions returned.
- `GET /api/intake/postcode-lookup/SW1A1AA` → 200, `suggested_city` Westminster, `country` England.
- Client login `nancy@yopmail.com` → `POST /api/properties/create` → 200; property appears in `GET /api/client/properties` list.

## Browser verification

**Not run.** Manual checklist:

1. Login as provisioned landlord.
2. Dashboard → Add New Property.
3. Type postcode prefix → suggestions appear.
4. Select suggestion → city/postcode filled; enter street in Address Line 1.
5. Submit once → single property created; no double submit.
6. Property list/detail shows normalized postcode/city/jurisdiction.
7. Requirements still present for property type/jurisdiction.
8. Intake wizard property step: postcode autocomplete + council fill unchanged.

## Files changed

- `frontend/src/utils/postcodeLookupApply.js` (+ test)
- `frontend/src/hooks/useUkPostcodeLookup.js` (+ test)
- `frontend/src/components/address/UkPostcodeLookupField.jsx`
- `frontend/src/pages/PropertyCreatePage.js` (+ test)
- `frontend/src/pages/IntakePage.js` (PropertyCard refactor)
- `backend/tests/test_property_create_payload.py`

## Commit / push

Pending commit in workspace; push not performed unless requested.

## Watchlist

- Complete manual browser E2E on staging/local to upgrade to `VERIFIED_OPERATIONALLY`.
- Postcodes that 404 on postcodes.io (e.g. some `M1 1AA` variants) still allow manual entry — document for support if reported.
