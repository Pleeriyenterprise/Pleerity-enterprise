# Recommended Improvements

**Programme:** OPERATIONAL-STABILITY-ROOT-CAUSE-VALIDATION-01

Prioritised by impact. **None suppress monitoring without fixing root cause.**

---

## P1 — Operational (no code required)

1. **Set `PLATFORM_DEPLOY_SUPPRESSION_UNTIL`** in Render deploy hook for planned pushes — reduces P0/P2 transient SLA emails during known ~7–14 min restarts while keeping heartbeat monitoring active.

2. **Resolve or acknowledge open `compliance_check_evening` incident** after confirming 2026-06-28T18:00 run succeeds post-`f2c10442`.

---

## P2 — Already remediated (verify)

3. **`f2c10442` compliance timeline null guard** — fixes Control Centre 500 **and** compliance_check_evening failure. **Verify** on next evening run.

---

## P3 — Optional hardening (product decision)

4. **Failed-run incident path** — SLA watchdog treats failed runs differently from missed runs; consider distinct incident title when job ran but failed (evening compliance ran at 18:00 but incident says "missed SLA" based on last success). Improves administrator clarity — not a false alert.

5. **Deploy-aware grace for P0 jobs with max_delay ≤ 5 min** — only when `PLATFORM_DEPLOY_SUPPRESSION_UNTIL` active. Optional; existing env var may suffice.

6. **SMS delivery_unknown terminal state** — separate track (production acceptance); not related to alert cluster.

---

## Explicitly NOT recommended

- Increasing `HEARTBEAT_STALE_SECONDS`
- Increasing `max_delay_minutes` for risk_signal_regen_worker globally
- Hardcoding healthy during deploy
- Disabling SLA watchdog during deploy

---

## Verdict

Platform requires **operational process improvement** (deploy suppression) and **verification of already-deployed fix** — not architectural rework.
