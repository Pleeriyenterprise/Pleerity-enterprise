# PRELAUNCH-TODAY-SATISFIED-REQUIREMENT-ATTENTION-DRIFT-01

**Classification:** VERIFIED_OPERATIONALLY (local + staging pilot)

## Problem

Today and Command Centre showed action-required tasks for requirements already satisfied (e.g. verified Gas Safety, declaration-recorded Legionella) because priority streams used legacy status/gap heuristics without authoritative truth convergence.

## Root causes

1. Legacy gap bridge keyed on `status` PENDING/MISSING despite `truth_presentation_stage=verified`
2. Command Centre primary stream used `project_requirement_row_client_runtime` without full enrich
3. `requirement_has_active_negative_actionability` ignored evidence authority and truth presentation
4. `today_task_is_actionable` did not suppress satisfied / suppressed take_action tasks
5. Operational cache invalidation not wired on authority sync

## Repair

Centralised `requirement_attention_eligibility_service.py` and wired into:

- Gap inference + priority streams (full + primary)
- Unified tasks lifecycle guard (via `requirement_has_active_negative_actionability`)
- Today non-actionable filter
- Authority sync cache invalidation

## Staging verification (Nancy pilot)

- No satisfied Gas Safety / Legionella forbidden phrases in Today
- Cross-surface samples: zero satisfied leaks
- Browser screenshots: `screenshots/01_today.png`, `02_command_center.png`
