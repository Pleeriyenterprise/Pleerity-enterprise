# Post-launch accepted conditions 07

**Programme:** `PRODUCTION-PROMOTION-EXECUTION-07`  
These remain **non-blocking**. Promotion success does not close them.

Owner defaults to **Platform engineering** unless a named owner is assigned in ops.

## Post-launch priority

| Item | Owner | Priority | Rationale | Target |
| --- | --- | --- | --- | --- |
| Separate production and staging Atlas deployments | Platform engineering | P1 post-launch | Shared Flex: blast radius and combined 54% utilisation. Writes currently `ok`. | Next infra window after launch |
| Governed live retention enablement | Platform engineering + ops | P1 post-launch | Flag remains off. OEP is largest staging collection; production will accrue similar telemetry. Enablement is a commercial/ops decision, not this release. | Separate change programme |

## Post-launch normal

| Item | Owner | Priority | Rationale | Target |
| --- | --- | --- | --- | --- |
| Storage budgets / budgeting UX | Platform engineering | P2 | Monitor + thresholds exist; UX is improvement. | Backlog |
| Periodic staging Stripe reconciliation | Billing engineering | P2 | 27 historic staging ACTIVE rows with missing `sub_*` (CC-04). Not production live drift. | Scheduled staging job |
| Pentest / CSRF / secrets rotation | Security | P2 | Last automated readiness 2026-07-09. | Pre-GA security review |
| Historic P2 closeout (staging `daily_reminders` RECOVERED-open; delivery-unknown) | Ops | P3 | Non-P0; lifecycle residue. | Soak-follow-up ops |
| `risk_signal` `BLOCKED` job_run persist | Platform engineering | P3 | Bounded idle-skip classifier gap (622 docs in 32h soak). | Optional skip-rule review |
| Production admin fixture for CC execute smoke | Ops | P2 | Production panel execute was NOT_EXERCISED this promotion. | Internal fixture only |
| Pre-existing `resolve_greeting` NameError in DB-email finaliser | Platform engineering | P2 | Fails five notification orchestrator unit tests; present on pre-promotion `main`. Staging CC Postmark still delivered via other render paths. Do not treat as introduced by this merge. | Separate small fix |
| Vercel `pleerity-enterprise-9jjg` Git “Production” on `main` | Platform engineering | P3 | Main push also built 9jjg Production; staging API still baked. Confirm project production-branch settings so staging alias is not later built with live API. | Infra hygiene |

Do not convert these into launch blockers without new runtime evidence.
