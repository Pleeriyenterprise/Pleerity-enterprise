# Production promotion repository reconciliation 07

**Programme:** `PRODUCTION-PROMOTION-EXECUTION-07`  
**Freeze captured:** 2026-08-17T06:32Z

## Promotion freeze

| Field | Value |
| --- | --- |
| Local branch | `develop` |
| Local HEAD | `fb138ae5b8234d9e354f6f5175c2fd02b1f944c7` |
| `origin/develop` | `fb138ae5b8234d9e354f6f5175c2fd02b1f944c7` |
| `origin/main` (pre-merge) | `89217062481b4eb858a8b530ec90c83de067a4be` |
| Local-only develop commits | none |
| Remote-only develop commits | none |
| Staged diff | empty |
| Untracked (working tree) | 376 paths — classified below, **not** merged |

`git rev-list --left-right --count origin/main...origin/develop` at freeze: **40 22**.

The 40 commits reachable from `main` but not from `develop` are **first-parent history already incorporated in merge `89217062`**, plus that merge commit itself. They are not post-89217062 unique production application commits. `origin/main` HEAD was still `89217062`.

## Promotion candidate

```text
PROMOTION_DEVELOP_SHA = fb138ae5b8234d9e354f6f5175c2fd02b1f944c7
PROMOTION_APPLICATION_SHA = fb138ae5b8234d9e354f6f5175c2fd02b1f944c7
```

No unverified application commits after the soaked SHA. Not `BLOCKED_BY_UNVERIFIED_DEVELOP_DRIFT`.

Last application commits inside that SHA:

| Concern | SHA |
| --- | --- |
| CC frontend circuit | `f88ce26d` |
| CC backend Suspend Billing | `02533d50` |
| Mongo prevention + scheduler health | `a5bfccfd`, `9b76213e`, `7d8e3648` |
| Docs-only after app | `7c77391a`, `fb138ae5` (HEAD; soaked on staging) |

Develop-only vs main (22 commits): Zoho integration layer, Mongo operational safeguards, Commercial Controls, and their evidence. `render.production.yaml` unchanged. No migration files in the delta.

## Merge preview

`git merge-tree --write-tree origin/main origin/develop` succeeded: tree `2952fb52`. No conflicts.

Merging (not fast-forward) preserves 20 `main`-only production-promotion evidence files that `develop` lacks.

## Working-tree classification

| Class | What |
| --- | --- |
| `AUDIT_EVIDENCE` | Local 06 soak pack (`MONGODB_*_06.md`, `PRODUCTION_PROMOTION_FINAL_GATE_06.md`, live JSON). Preserved; **excluded from application merge**. |
| `UNRELATED_WORK` | Gallery PDFs, Zoho extra local docs, untracked orchestration module, hundreds of historic audit folders. |
| `TEMPORARY` | `backend/tmp_*.py` including soak probes. |
| `SECRET` / `DO_NOT_COMMIT` | `backend/.cc_preflight_token.txt` (gitignored on develop); local uncommitted `.gitignore` `.env*` line — **not** merged. |
| `PROMOTION_REQUIRED` | None in the dirty tree. Application promotion used `origin/develop` only. |

Isolation method: merge executed in worktree `C:\pleerity-workspace\ppe-07-main` so the dirty develop tree and 06 files were not touched.

## Merge result

| Field | Value |
| --- | --- |
| Strategy | `ort` merge (not fast-forward) |
| Merge SHA | `b6b7ddf553482fa2797f317ce69296b21a494230` |
| `origin/develop` ancestor of merge | yes |
| Pre-promotion `origin/main` ancestor of merge | yes |
| 06 soak files in merge | **absent** (correct) |
| Push | `89217062..b6b7ddf5  main -> main` (no force) |

## Phase 17 — evidence commit (after promotion)

06 soak files were **not** in merge `b6b7ddf5`. They are committed to `develop` after production was live so a pre-promotion staging restart could not reset the soak clock.
