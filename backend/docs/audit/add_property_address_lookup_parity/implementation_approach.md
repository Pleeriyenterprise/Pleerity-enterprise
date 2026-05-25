# Implementation approach

## Strategy

1. Extract shared **hook** `useUkPostcodeLookup` (calls existing `intakeAPI` — no second provider or route).
2. Extract shared **UI** `UkPostcodeLookupField` for postcode input + suggestions dropdown.
3. Extract **pure helpers** `postcodeLookupApply.js` for suggestion → postcode, lookup → `{ postcode, city, jurisdiction }` with `fillOnlyEmpty` parity.
4. Wire `PropertyCreatePage` to hook + field; preserve manual fallback (type full postcode / address without selecting suggestion).
5. Refactor intake `PropertyCard` to use the same hook/component (behaviour unchanged; council fill remains intake-specific in `onLookupComplete`).
6. Duplicate submit guard: `submitInFlight` ref + `loading` on dashboard create.
7. Submit payload unchanged; `postcode` normalized via `normalizeUkPostcode` before `POST /properties/create`.

## Jurisdiction

- When postcodes.io `country` is one of `Scotland | England | Wales | Northern Ireland`, prefill jurisdiction only if the field is empty (dashboard); intake jurisdiction select unchanged.
- Account default jurisdiction fetch and optional override select preserved.

## Out of scope (per request)

- No change to compliance requirement generation, council DB matching, or intake route handlers.
