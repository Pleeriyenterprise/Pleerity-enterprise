# Escalation + cognition governance

**Programme:** PRELAUNCH-CER-AUTHORITY-GOVERNANCE-DECISION-01

## Stale rules (revised — design)

| Condition | Allowed stale? | Owner | Label |
|-----------|----------------|-------|-------|
| Platform doc PENDING_ADMIN_REVIEW | Yes (7d) | platform_admin | Platform verification pending (stale) |
| Org review enqueued | Yes (7d) | org_admin | Organisation review pending (stale) |
| Follow-up unresolved | Yes (configurable) | landlord | Follow-up evidence required (overdue) |
| Self-cert incomplete components | No generic stale | landlord | Additional action still required |
| CER pending, no queue owner | **Forbidden** | — | Must NOT escalate as "stale review" |

## Escalation ownership

| Escalation | Owner | Entry condition |
|------------|-------|-----------------|
| STALE_PLATFORM_VERIFY | platform_admin | EA_PENDING_ADMIN_REVIEW + 7d |
| STALE_ORG_VERIFY | org_admin | B-family + enqueued + 7d |
| FOLLOWUP_OVERDUE | landlord | semantic ASSESSMENT_FOLLOWUP_REQUIRED + due date passed |
| MANUAL_REVIEW | platform_admin_escalation | manual_review_flag |
| OVERDUE_REQUIREMENT | landlord | statutory due date — not review stale |

## Cognition vocabulary migration

Replace `_workflow_stage` values that imply review without owner:

| Current stage | Target stage | Owner |
|---------------|--------------|-------|
| submitted_pending_review | recorded_pending_closure | governance-dependent |
| awaiting_review | platform_verify_pending OR org_verify_pending OR **forbidden** | must resolve owner |

## Today / Command Centre

- STALE_REVIEW flag ONLY when stale rules table permits.
- recommended_next_step MUST name actor: "Complete remaining checklist items" not "Wait for reviewer".
