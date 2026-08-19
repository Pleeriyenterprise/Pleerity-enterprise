# Onboarding Day 2+ content verification 05

Day 0 / Day 1 state-awareness from Remediation 02 was not reopened.

## Authority reused

`has_added_property`, `has_uploaded_certificate`, `monitoring_enabled` from existing onboarding state. No new rules engine.

## Day 2–6 after cleanup

| Day | Change |
| --- | --- |
| 2 | Jurisdiction-neutral; CTA “Add a property…” vs “Review your requirements” |
| 3 | No overclaim of “automation / compliance score as legal”; CTA dashboard |
| 4 | Packs optional; not legal advice |
| 5 | No legal-penalties / insurance-issues fear copy; CTA notification settings |
| 6 | No invented anecdote; reminders follow recorded dates |
| 7 | Left as previously remediated |

Subjects for Day 2–6 aligned with educational copy (no “Why compliance alerts matter” / “How we helped one landlord”).

## Tests

`test_onboarding_day2_adapts_when_property_exists`  
`test_onboarding_day5_not_fear_based`  
Existing Day 0/1/7 unit tests still pass.

Educational messages may still send after some milestones; CTA/context now tracks property/monitoring state.
