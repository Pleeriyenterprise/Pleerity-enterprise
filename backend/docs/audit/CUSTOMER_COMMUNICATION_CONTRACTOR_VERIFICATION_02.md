# Contractor assigned verification 02

## Contract fix

Audit 01: caller passed `body` while the ADMIN_MANUAL contractor layout renders `message`.

`maintenance_service` now builds HTML via `_contractor_assignment_message_html` and passes **`message`** (HTML) and `body` (plain), plus `contractor_assignment_layout=True`, `job_link`, `cta_label`. Orchestrator uses EmailService for that layout.

Unit test asserts work order id, property, description, and job link appear in the HTML.

The assignment `else` branch for non-quote maintenance jobs was restored (it had been dropped during the first patch).

## Live staging

Attempted:

1. MAINTENANCE WO `e8aced55-…` → assign `grace@yopmail.com` / `smithelectronics@yopmail.com` → **400** capability/trade mismatch.
2. COMPLIANCE EICR WO `cacd535d-…` → recommend-contractors returned **no eligible contractors** (vetting, portal, trade, area). Direct assign of Smith Electronics (`execution_capabilities=compliance`) still **400** (`contractor_verified_qualifies_for_requirement` for `eicr`).

No `CONTRACTOR_ASSIGNED` / contractor `ADMIN_MANUAL` send occurred after SHA `a9a2efd3`.

**Residual:** live contractor email unproven because staging has no assignable yopmail contractor for the test WOs. Copy contract is unit-proven. Do not treat HTTP 400 eligibility as a message-content PASS.
