# Watchlist — F4 post-remediation

## Classification (staging API, pre-deploy)

`FAIL_OPERATIONAL` — remediation code **implemented locally**; staging Render API **not yet deployed** with F4 governance fixes.

Run `20260523T170410Z` on staging reproduces pre-remediation failure mode:
- `signal_acknowledged_on_propagation` FAIL (deployed API does not auto-acknowledge on create-issue)
- Regen worker deletes active signal mid-lifecycle → 404 before resolve
- G9/G10 partial (signal absent on repeated read / closure resolve)

## Remediation implemented (code)

1. **Regen merge + retention** (`risk_signal_regen_governance.py`, `generate_risk_signals_for_property`)
2. **Propagation lifecycle** (`acknowledged` on create-issue; `remediation_in_progress` on WO)
3. **G9 replay** (`risk_signal_issue_idempotency.py` — open linked issue replay)

## Integration evidence (local code + staging Mongo)

`regen_behaviour_evidence.json` — PASS: signal `rs_2006b6155ccf` survived regen with stable `signal_id`.

## Required before VERIFIED_OPERATIONALLY

1. **Deploy** remediation to staging (`Render`/main)
2. **Same-run F4 rerun** (`tmp_ops_runtime_04_risk_signals_execute.py`) on deployed staging
3. Confirm: signal stable through lifecycle, G9/G10 PASS, convergence PASS

## F5

**NO** — F4 not `VERIFIED_OPERATIONALLY`.
