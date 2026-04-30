# PR5 policy-backed portfolio override — one-tenant rollout monitoring (internal)

**Audience:** engineering, support leads, on-call.  
**Scope:** phased rollout using **tenant allowlist only**. This runbook does **not** authorise global PR5 enablement.

---

## 1. Environment variables

| Variable | Purpose |
|----------|---------|
| `FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE` | Master switch. Must be `true` / `1` / `yes` (case-insensitive) for any tenant to use the policy-backed path. |
| `FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE_TENANT_ALLOWLIST` | Comma-separated `client_id` values. **Only** listed tenants receive PR5 behaviour when the master switch is on. |

**Correct pattern for one test tenant:**

```text
FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE=true
FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE_TENANT_ALLOWLIST=<single-client-uuid>
```

Verify in a shell (replace UUID):

```powershell
python -c "import os; os.environ['FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE']='true'; os.environ['FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE_TENANT_ALLOWLIST']='<uuid>'; from services.portfolio_risk_override_flag import is_feature_policy_backed_portfolio_override_enabled; print('allowed:', is_feature_policy_backed_portfolio_override_enabled('<uuid>')); print('other:', is_feature_policy_backed_portfolio_override_enabled('00000000-0000-0000-0000-000000000001'))"
```

---

## 2. Allowlist warning (critical)

- **Never** set `FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE=true` with an **empty** allowlist unless you intend **all** tenants to receive PR5 (allowlist empty ⇒ flag code treats as “all allowed”).
- **Never** commit production secrets or real tenant UUIDs into git in `.env`; use host / deployment secrets manager.
- **One-tenant pilot:** keep the allowlist to **a single `client_id`** until the stability gate (section 5) is satisfied.
- After every deploy, confirm a **non-allowlisted** tenant still evaluates **PR5 off** via `is_feature_policy_backed_portfolio_override_enabled`.

---

## 3. Diagnostic command (read-only)

From `backend/` (with `MONGO_URL`, `DB_NAME` set for the target environment):

```bash
python -m scripts.diagnose_portfolio_risk_override --client-id <CLIENT_ID>
```

Optional bounded discovery (do **not** use for routine monitoring of many tenants during pilot):

```bash
python -m scripts.diagnose_portfolio_risk_override --all-tenants --limit <N>
```

**Inspect in output:**

- `feature_policy_backed_portfolio_override_enabled` — must be `true` only for allowlisted tenants.
- `legacy_override_output`, `policy_override_output`, `effective_override_output`
- `effective_override_output.override_output_source`, `fallback_applied`, `fallback_reason_codes`
- `runtime_health` (reconciliation, drift, gap checkpoint)
- `hiua_operational_uncertainty` (counts, gap details, digest-style copy fields)
- `critical_escalation_latch_active` (if present)

---

## 4. Fields to monitor (pilot tenant)

| Area | Field(s) | What “good” usually looks like |
|------|-----------|--------------------------------|
| PR5 selection | `effective_override_output.override_output_source` | `policy` when gates pass; `legacy` when flag off; `legacy_fallback` only when fallback is intentional. |
| Fallback | `effective_override_output.fallback_applied` | `false` when policy path is authoritative. |
| Fallback reasons | `effective_override_output.fallback_reason_codes` | `[]` when not falling back; non-empty must map to known gates (coverage, drift, reconciliation in progress, aggregate unavailable, etc.). |
| Digest observability | Top-level digest payload: `override_output_source`, `fallback_applied`, `fallback_reason_codes` | Same values as `score_block.effective_override_output` (mirrors for reporting; no separate logic). |
| HIUA | `hiua_operational_uncertainty.hiua_open_gap_count`, `hiua_gap_details` | Track **deltas** week-to-week; spikes often correlate with new open gaps or applicability still `UNKNOWN` on high-impact codes. |
| Reconciliation | `runtime_health.gap_reconciliation_checkpoint`, `policy_jobs_completed`, `drift_detected` | Completed + no drift for steady policy selection; investigate if fallback appears alongside drift. |
| Risk language | `effective_override_output.risk_override_reasons`, `policy_override_output.risk_override_reasons` | No **Critical** with empty reasons; policy path should carry canonical reason codes. |
| Support copy | HIUA digest/command-centre strings in diagnostic | Operational uncertainty wording; not “confirmed breach” for UNKNOWN applicability. |

---

## 5. Stability gate before adding tenants

Do **not** add a second tenant to the allowlist until **all** of the following have held for the **pilot** tenant:

1. **At least one monthly digest cycle** — digest generated/sent; payload shows consistent `override_output_source` / fallback mirrors; HIUA and portfolio wording acceptable to support; no unexplained headline jumps vs prior period narrative.
2. **At least one gap reconciliation cycle** — checkpoint shows **completed** (and failures/drift understood if any); `fallback_reason_codes` not flapping without cause.
3. **No unexplained regressions** — no new `legacy_fallback` without matching `fallback_reason_codes`; no empty Critical reason lists on policy output; HIUA count changes explained by data (e.g. new `UNKNOWN` + high-impact open gaps).

Document dates and owner for (1)–(3) in the change ticket before expanding allowlist.

---

## 6. Rollback steps

**Fast rollback (single tenant):**

1. Remove the pilot `client_id` from `FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE_TENANT_ALLOWLIST`, **or** set allowlist to a non-production UUID that is never used, **or** set `FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE` to `false` / unset.
2. Redeploy or reload process env (whatever your platform requires).
3. Re-run the diagnostic for the tenant: `effective_override_output.override_output_source` should return to **`legacy`** (flag off), with legacy override semantics.
4. Notify support: portfolio risk language reverts to legacy path for that tenant.

**Full PR5 off (all tenants):**

- Set `FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE` unset / `false`. Allowlist becomes irrelevant.

**Data / latch:** persistent latch documents are tenant-scoped; rollback env does not delete Mongo data. If support reports confusion after rollback, use existing admin/data procedures — do not ad-hoc delete latch rows without ticket.

---

## 7. What not to do

- Do **not** enable “global” PR5 by turning the flag on with an **empty** allowlist in production.
- Do **not** expand the allowlist until section 5 is satisfied.
- Do **not** change `POLICY_CLASSIFICATION_VERSION` or persisted gap policy fields as part of routine monitoring (separate change control).
- Do **not** treat HIUA as a confirmed mandatory breach; it is **operational uncertainty** when applicability is `UNKNOWN` on high-impact codes.
- Do **not** use severity-only gap counts as the sole signal for policy breach language — policy path uses predicate-backed counters and strict lanes.

---

## 8. Escalation notes

### 8.1 `fallback_reason_codes` non-empty

| Code (examples) | Typical meaning | First actions |
|-----------------|-----------------|----------------|
| `POLICY_FIELDS_INCOMPLETE` / coverage-style | Policy aggregate coverage below gate | Check `gap_engine.policy.policy_coverage_percent` vs threshold in runtime health; requirement policy field backfill. |
| `RECONCILIATION_IN_PROGRESS` | Gap reconciliation not completed | Inspect `runtime_health.gap_reconciliation_checkpoint`; wait for successful completion or fix job failures. |
| `POLICY_DRIFT_DETECTED` | Checkpoint / drift signal | Coordinate with whoever owns policy backfill/reconcile jobs; compare gap vs requirement truth. |
| `POLICY_AGGREGATE_UNAVAILABLE` | Gap engine / aggregate error path | Check logs for `aggregate_gap_counts_for_client` failures; tenant may correctly fall back to legacy until fixed. |

Escalate to **platform/compliance engineering** if codes persist after reconciliation completed and coverage is high — possible product bug or data skew.

### 8.2 HIUA spike (`hiua_open_gap_count` up materially)

- **Likely causes:** new open `compliance_gaps` on high-impact codes with `applicability_state` still `UNKNOWN`; data import; jurisdiction/applicability pipeline lag.
- **First actions:** run diagnostic; review `hiua_gap_details` (requirement_code, gap_kind, property_id). Compare to requirements collection for those `requirement_id`s.
- **Support:** use HIUA tooltip/digest copy — “eligibility not confirmed”; action is **confirm applicability**, not assume legal outcome.
- Escalate if count rises **without** matching gap rows (possible bug in HIUA read-time predicate) — **engineering** with diagnostic JSON attached.

### 8.3 Unexpected Critical / High language

- Compare **legacy** vs **policy** vs **effective** blocks in the diagnostic on the same day.
- If **effective** is `legacy_fallback`, read `fallback_reason_codes` first — headline may follow legacy for explainable gates.
- If **policy** shows Critical with **empty** reasons, treat as **defect** — escalate engineering (should not occur with current explainability rules).

---

## 9. Revision control

Update this runbook when:

- Allowlist process changes (e.g. new env for staging vs prod).
- New canonical `PolicyReasonCode` values affect support scripts.
- Digest field names for PR5 observability change.

**Owner:** compliance platform team (nominate in ticket).
