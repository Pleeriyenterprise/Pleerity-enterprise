# Admin – Compliance Engine (Training Manual)

## 1. Module name
**Compliance Engine (Admin / Operations)**

## 2. Audience
**Admin / internal staff.** Backend compliance logic affects both admin and client views; this manual focuses on admin-facing compliance views and how the engine works.

## 3. Purpose
The “compliance engine” is the set of backend rules and jobs that: (1) define requirements (from catalog or client config), (2) compute requirement status (PENDING, EXPIRING_SOON, OVERDUE, etc.) and property-level compliance status (GREEN/AMBER/RED), (3) drive compliance score, and (4) trigger reminders and digests. Admins need to understand how this works and where to view compliance data (e.g. ops compliance, client context).

## 4. Where to find it in the UI
- **Operations & Compliance:** Sidebar → **Operations & Compliance → Compliance** (e.g. `/admin/ops/compliance`). May show cross-client or client-scoped compliance views.
- **Client context:** When viewing a client, compliance data may appear as requirements list or score.
- **Automation:** Compliance check jobs (e.g. `compliance_check_morning`, `compliance_check_evening`) and status-change detection run on schedule; visible in **Automation Centre** and **System Health**.

## 5. What the user sees
- **Ops Compliance page (if implemented):** List or dashboard of compliance items, possibly filterable by client, property, status, or date. Exact layout **needs runtime confirmation**.
- **Automation Centre:** Jobs such as `compliance_check_morning`, `compliance_check_evening`, and requirement/status update logic. Job states (healthy, degraded, never ran) and last run time.
- **Client-facing compliance:** Clients see Requirements (“Compliance”) and Compliance Score; admins may see the same data in client context.

## 6. Step-by-step actions
| Action | What to do | What happens |
|--------|------------|--------------|
| View compliance by client | Go to Ops → Compliance (or client detail) and select/filter by client | Requirements and statuses for that client’s properties load. |
| Check why a property is RED/AMBER | Inspect requirements for that property; look for OVERDUE, EXPIRING_SOON, or PENDING with past-due dates | Backend logic: OVERDUE/EXPIRED → RED; EXPIRING_SOON or PENDING (missing evidence) → AMBER; else GREEN. |
| Verify compliance jobs ran | Open Automation Centre → find compliance_check_* or related jobs | Check last run, outcome, and any incidents. |
| Trigger recalculation (if supported) | Automation Centre “Run Now” for a recalc job (e.g. compliance_recalc_worker) | Job runs once; use for recovery only. |

## 7. What happens after each action
- View: Data is read-only from stored requirements and computed status.
- Run Now: Job executes; may update requirement statuses and scores; avoid overuse.

## 8. Status/outcome examples
- **Property RED:** At least one requirement is OVERDUE or EXPIRED.
- **Property AMBER:** At least one EXPIRING_SOON or PENDING (or due within threshold); or missing evidence.
- **Property GREEN:** No overdue; no expiring soon; evidence in place where required.
- **Job “never ran”:** Scheduler may not have run yet (e.g. next run in future) or startup/registration issue; see observability docs.

## 9. Common errors or confusing points
- **Requirements catalog vs client-specific:** Some requirements come from a catalog; clients may have requirements added per property. Training: “Catalog defines types; client data has instances and due dates.”
- **Status lags:** Status and score can be updated by scheduled jobs; there may be a delay after evidence upload or date change.
- **Mark as not applicable:** Client can set “not required” with a reason; admin may see that reason in client context.

## 10. Current limitations or known gaps
- Ops Compliance page content and filters **need runtime confirmation**.
- No admin UI to “edit” a requirement’s due date or status directly in some builds; changes may be via client actions or backend only.
- Recalculation frequency is scheduled; no “recalculate now” button in client UI (admin may have Run Now for jobs).

## 11. Notes for training staff
- Use Automation Centre to show “these jobs keep compliance status and scores up to date.”
- When a client says “my score didn’t update,” explain scheduled recalc and possibly trigger Run Now once if policy allows.
- Document where to look for “why is this property RED” (requirements list and due dates).

---

## Trainer walkthrough (5–10 minutes)

1. **Open Operations & Compliance → Compliance** (or equivalent) → show how to filter by client if available.
2. **Open a client with known RED/AMBER property** → show requirements and which statuses drive RED/AMBER.
3. **Open Automation Centre** → point out compliance_check_* and recalc jobs → explain “these run on schedule; don’t use Run Now unless recovering.”
4. **Briefly:** “Clients see the same compliance data on their Compliance and Properties pages; we’re looking at it from the admin side.”
