# PRELAUNCH-CONTRACTOR-ASSIGNMENT-ELIGIBILITY-REPAIR-01 watchlist

- Classification: **PARTIAL** until staging deploy proves recovery UX + England portfolio location fix on live bundle.
- Re-run `tmp_prelaunch_contractor_assignment_eligibility_repair_01.py` after deploy; expect `assign-contractor-recovery` testid in main.js.
- Scotland / Northern Ireland jobs with zero eligible may remain correctly blocked until contractors declare those service regions.
- Properties missing postcodes rely on portfolio jurisdiction matching — ensure property jurisdiction is set at intake.
- Today / Command Centre assign CTAs route to job detail modal — no separate eligibility surface.
- Confirm assign button disabled when no contractor selected after deploy.
