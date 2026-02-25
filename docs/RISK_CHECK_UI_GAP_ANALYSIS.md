# Risk Check Marketing Funnel UI – Gap Analysis

## Conflict: API shape vs task

- **Task** asks for `POST /api/risk-check/lead` called twice: (1) without email → `{ lead_id, partial_result }`, (2) with email + first_name → full result. Lead created at Step 1.
- **Current backend** has `POST /api/risk-check/preview` (no persistence, no lead_id) and `POST /api/risk-check/report` (creates lead with email in one shot, returns full report + lead_id). No `/lead` endpoint.
- **Decision:** Do **not** add a new `/lead` endpoint. Keep existing `preview` + `report`. Lead is created only at email gate (report). Conversion linking still works: `lead_id` from report is used for activate + intake. This avoids backend change and preserves existing nurture/scoring behaviour.

## Field names (task vs current)

- **property_count:** Task wants select bands (1, 2–5, 6–10, 11–25, 25+). Backend expects integer 1–100. Map bands to a single number (e.g. 1, 3, 8, 18, 30) in the frontend; no backend change.
- **gas_last_date / eicr_last_date:** Task suggests optional date or "I don't know". Backend uses `gas_status` / `eicr_status` (Valid | Expired | Not sure). Keep current status dropdowns; changing to dates would require scoring and backend changes.
- **tracking_method:** Task "Manual / Already use reminders / Not sure". Backend expects specific strings (Manual reminders, Spreadsheet, etc.). Keep backend contract; use friendlier labels in UI that map to existing values.

## Implemented vs missing (UI)

| Item | Status | Action |
|------|--------|--------|
| Route /risk-check | Done | None |
| Homepage/header CTA "Check Your Compliance Risk" | Header done | Add CTA on homepage body |
| State 1: Questions | Exists, different shape | Add task headline/copy; property_count as band select |
| State 2: Partial only (no email on same screen) | Email gate inline with partial | Split: Step 2 = partial + "Get Full Risk Report" only; Step 3 = email gate |
| State 3: Email gate (first_name optional) | Inline today | Dedicated step; first_name optional, email required |
| State 4: Full report + right panel "How monitoring fixes" | Left panel only | Add right panel locked dashboard preview; disclaimer block |
| State 5: CTA + redirect with lead_id | Done | Add optional plan picker; "What happens next" copy |
| Progress indicator Step 1–4 | "Step X of 3" | "Step X of 4" |
| Trust micro-row | Missing | Add under hero |
| Copy (compliance-safe) | Mostly ok | Replace any "non-compliant" wording; add exposure disclaimer |
| Analytics hooks | Missing | Fire events (console or log_event) |
| Frontend tests | Existing | Extend for 4-step flow + activate redirect |

## Non‑negotiable (unchanged)

- No login creation, document uploads, provisioning, or entitlements from /risk-check.
- Intake remains the only path to Stripe + provisioning.
- No change to existing intake wizard beyond accepting lead_id (already done).
