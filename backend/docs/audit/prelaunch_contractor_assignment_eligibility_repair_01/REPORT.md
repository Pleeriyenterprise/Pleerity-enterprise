# PRELAUNCH-CONTRACTOR-ASSIGNMENT-ELIGIBILITY-REPAIR-01

## Summary

Repairs contractor assignment eligibility authority and recovery UX for the assign-contractor modal.

## Root cause

`contractor_location_matches_property` compared portfolio labels (England, Scotland, …) and free-text regions as postcode fragments. Contractors with `region: England` failed against property postcodes (e.g. `B1 1AA`) before the service-region gate. Funnel counts were internally consistent (not a frontend drop bug); the modal explained exclusions but offered no operational recovery path.

## Changes

- **Backend:** Portfolio vs postcode location matching with `property_jurisdiction`; `recovery_guidance`, `exclusion_samples`, and `property_postcode` on assignable-contractors API.
- **Frontend:** Recovery action cards, excluded-contractor review, refresh, improved empty-state copy; assign button disabled without selection.

## Runtime (pre-deploy sample)

- 100 jobs sampled on staging: 90 with ≥1 eligible, 10 with 0 eligible (mostly Scotland / NI portfolio mismatch).
- Dropdown API payload matches eligible count (no frontend drop).
- Recovery UX bundle flags not yet on CDN — deploy required for browser proof.

## Classification

**PARTIAL** — code and unit tests complete; staging CDN deploy pending for **VERIFIED_OPERATIONALLY**.
