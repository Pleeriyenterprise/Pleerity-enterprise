# SCORE-RECALCULATION-LATENCY-CONVERGENCE-01

Verified at: 2026-06-03T21:07:05.608584+00:00
Builds on: PROPERTY-COMPLIANCE-SCORE-CONVERGENCE-DRIFT-01 @ 0b7ed60c

## Problem
Requirement truth converged immediately but persisted score/risk cognition could lag during async recalc, showing stale low scores and Elevated risk after satisfied mutations.

## Fix
1. **Pending dominates** — `compliance_score_pending` → `score_status=calculating` even when a numeric snapshot exists
2. **Duplicate enqueue** — re-mark pending while worker job is active
3. **Portfolio honesty** — partial status + pending message when recalc in flight
4. **UI** — Updating… headline, suppress stale risk labels, cognition line during pending
5. **Read-path gap** — enqueue after stale authority refresh

## Classification
PARTIAL

## Tests
Backend: PASS
