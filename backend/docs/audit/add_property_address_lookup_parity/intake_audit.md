# Intake postcode/address lookup audit

**Date:** 2026-05-20

## APIs (single implementation)

| Endpoint | Route | Backend |
|----------|-------|---------|
| Autocomplete | `GET /api/intake/postcode-autocomplete?q=` | `backend/routes/intake.py` → postcodes.io |
| Lookup | `GET /api/intake/postcode-lookup/{postcode}` | Same; returns canonical postcode, `suggested_city`, council match, `country` |

## Frontend (before parity)

- **Intake:** `IntakePage.js` → `PropertyCard` inline state: debounced autocomplete, dropdown select, blur lookup, `intakeAPI.autocompletePostcode` / `lookupPostcode`.
- **Normalization:** `frontend/src/utils/ukPostcode.js` (`sanitizePostcodeFieldInput`, `normalizeUkPostcode`, `isFullUkPostcode`).
- **Fields filled on lookup:** `postcode` (canonical), `city` (if empty), `council_name` / `council_code` (if empty). Street lines **not** provided by API (`suggested_address: null`); user enters `address_line_1` manually.
- **Jurisdiction:** manual select on intake; lookup `country` can map to portfolio labels but intake did not auto-set jurisdiction pre-refactor.

## Dashboard gap (remediated)

- `PropertyCreatePage.js` had manual postcode/city only — no autocomplete or lookup.
