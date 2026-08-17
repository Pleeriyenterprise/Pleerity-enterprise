# Post-launch operational backlog 05

**Programme:** `COMMERCIAL-CONTROLS-CERTIFICATION-CLOSURE-AND-PROMOTION-GATE-05`

These are **not** Commercial Controls certification blockers.

| Item | Class | Justification |
| --- | --- | --- |
| Uninterrupted 24h Mongo soak on current staging SHA | `PRE_LAUNCH_REQUIRED` | Stated production-readiness condition. ~2.2h elapsed; push resets it. |
| Staging/production Atlas cluster separation | `POST_LAUNCH_PRIORITY` | Shared cluster observed in live snapshot (`pleerity_staging` + `pleerity_production`). Isolation is desirable; current fill 53.16% `ok`, writes not at risk. |
| Live operational retention enablement | `POST_LAUNCH_PRIORITY` | Retention remains flagged off from the prevention deploy. Enablement is a separate commercial/ops decision. |
| Storage budgeting improvements | `POST_LAUNCH_NORMAL` | Monitor + thresholds exist; budgeting UX is improvement, not a write-block fix. |
| Periodic staging Stripe reconciliation | `POST_LAUNCH_NORMAL` | 27 historic ACTIVE rows with missing `sub_*` are fixture decay. Recommend a scheduled staging reconcile/report; not a CC blocker. |
| `lifecycle_ops_*` registry exact-match contract | `POST_LAUNCH_NORMAL` | `VALID_INTENTIONAL_EXTENSION`. Do not silently expand allow-lists. |
| Inherited customer-journey re-smoke before first prod cutover | `POST_LAUNCH_NORMAL` | Last full scorecard 2026-07-09. Optional confidence, not a known defect. |
| Pentest / CSRF / secrets rotation | `POST_LAUNCH_NORMAL` | No critical automated finding; not this gate. |

Do not convert roadmap items into launch blockers without new evidence.
