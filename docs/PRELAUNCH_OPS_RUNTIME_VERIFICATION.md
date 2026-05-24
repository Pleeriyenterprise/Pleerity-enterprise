# PRELAUNCH-OPS-RUNTIME-VERIFY-01 — Operational Domain Runtime Verification Charter

**Programme ID:** `PRELAUNCH-OPS-RUNTIME-VERIFY-01`  
**Status:** **COMPLETE** (F1–F8 `VERIFIED_OPERATIONALLY`; operational runtime verification programme closed — **not** launch authorization)  
**Authority:** Governed operational verification only — **not** launch authorization, UK rollout approval, compliance authority redesign, planner redesign, accounting certification, asset-native synthesis rollout, or AI operational orchestration.

---

## 1. Purpose and boundaries

Before launch, operationally verify **real runtime behaviour** of major **operations-domain** workflows using:

- Real client sessions (not mock-only)
- Real browser execution
- Real staging properties
- Real async processing
- Real DB/system verification
- Real refresh persistence
- Real cross-role visibility
- Truthful user-visible semantics

Verify **both**:

1. **User outcome** — what users see, believe, and can act on  
2. **System outcome** — what persists, converges, links, and respects authority

### In scope (operational runtime domains)

Issues · maintenance jobs · work orders · contractor assignment · contractor portal · client ↔ contractor sync · risk signals · operational remediation flows · rent operations · tenant portal operations · tenant operational visibility · operational dashboards/projections

### Explicitly out of scope

Launch authorization · governance expansion · AI scoring redesign · accounting redesign · global planner redesign · asset-native synthesis expansion · marketing/analytics systems · speculative future workflows · **compliance evidence journeys** (see `OPS-VERIFY-01`) · **condition-standard pilots** (`PRELAUNCH-OPS-VERIFY-CONDITION-STANDARD-01`)

### Programme discipline (non-negotiable)

| Do NOT | Do |
|--------|-----|
| Merge operational families into mega-runs | Run **eight bounded families** separately |
| Infer `VERIFIED_OPERATIONALLY` from backend tests alone | Require browser proof + convergence |
| Assume async completion without observation | Wait + re-read per convergence SLA |
| Treat uploads as operational completion | Verify lifecycle + authority + wording |
| Widen rollout posture from verification | Record classification only |
| Collapse ops vs compliance verification | Keep programme boundaries distinct |

---

## 2. Programme architecture

```
Preflight (G0) → Bounded family run → Browser (G1) → User (G2) → System (G3)
    → Async convergence (G4) → Refresh (G5) → Cross-role (G6) → Wording (G7)
    → Trust (G8) → Idempotency (G9) → Authority integrity (G10)
    → Classify → REPORT.md + 07_classification.json → Tracker row
```

Each family produces **one bundle** under `backend/docs/audit/ops_runtime_{family_slug}/`.

**Harness convention (local only, not product code):** `backend/tmp_ops_runtime_{family}_execute.py`

---

## 3. Operational ownership model (mandatory)

**Rule:** Each mutation origin has **exactly one authoritative verification owner family**. Other families may **reference** that proof; they must **not** re-verify the same mutation lifecycle independently.

### 3.1 Mutation origin → authoritative owner

| Mutation origin | Authoritative family | Slug |
|-----------------|----------------------|------|
| Issue create / triage / close / edit | **Family 1** — Issue lifecycle | `ops_runtime_01_issues` |
| Work order create / status / SLA / evidence / complete | **Family 2** — Work orders & jobs | `ops_runtime_02_work_orders` |
| Contractor routing / assignment / portal sync | **Family 3** — Contractor + portal | `ops_runtime_03_contractor` |
| Risk signal regen / signal→issue/WO / dismiss-ack | **Family 4** — Risk propagation | `ops_runtime_04_risk_signals` |
| Cross-surface refresh / projection coherence | **Family 5** — Client operational sync | `ops_runtime_05_client_sync` |
| Rent schedule / payment / reminder / expense / attention | **Family 6** — Rent operations | `ops_runtime_06_rent_ops` |
| Tenant report-issue / report-maintenance / tenant-visible status | **Family 7** — Tenant portal visibility | `ops_runtime_07_tenant_portal` |
| End-to-end chain continuity (integration only) | **Family 8** — Cross-domain integrity | `ops_runtime_08_cross_domain` |

### 3.2 Family 8 anti-duplication rule

**Family 8 validates only:**

- Chain continuity (IDs walkable end-to-end)
- Linkage integrity (`issue_id`, `work_order_id`, `risk_signal_id`, etc.)
- Propagation integrity across family boundaries
- Async convergence **across** families (not re-proving intra-family lifecycle)
- No contradictory cross-domain operational truth

**Family 8 does NOT:**

- Independently own issue lifecycle (Family 1 owns)
- Independently own contractor lifecycle (Family 3 owns)
- Independently own rent lifecycle (Family 6 owns)
- Re-run full browser suites already classified `VERIFIED_OPERATIONALLY` in owner families

**Family 8 method:** Golden-path integration run + **bundle cross-references** to authoritative family `07_classification.json` files. Missing or `FAIL` upstream bundle → Family 8 **BLOCKED** for that chain segment.

### 3.3 Shared dependency fields (required in every bundle)

Each bundle **must** include in `00_preflight.json` and `07_classification.json`:

```json
{
  "authoritative_verification_owner": "ops_runtime_01_issues",
  "mutations_verified_in_this_bundle": ["issue_create", "issue_triage"],
  "shared_dependency_bundle_ids": [
    "ops_runtime_04_risk_signals/07_classification.json"
  ],
  "proof_mode": "operational_browser"
}
```

- **`authoritative_verification_owner`** — slug of family that owns mutations verified here  
- **`shared_dependency_bundle_ids`** — relative paths to upstream bundles **read for linkage only** (not re-verified)  
- **`mutations_verified_in_this_bundle`** — explicit list; anything not listed is out of scope for this run

---

## 4. Bounded operational families (summary)

| # | Family | Objective |
|---|--------|-----------|
| 1 | Issues | Portfolio intake → triage → WO handoff → close; issue vs WO truthfulness |
| 2 | Work orders | WO/job lifecycle, SLA, evidence, monotonic status |
| 3 | Contractor | Client routing + contractor portal cross-role sync |
| 4 | Risk signals | Actionable signals; advisory labelling; regen idempotency |
| 5 | Client sync | Post-mutation surface convergence (hub, property, dashboard, reports) |
| 6 | Rent ops | Browser/runtime rent operational truth (see §8) |
| 7 | Tenant portal | Tenant-originated maintenance + visibility scope |
| 8 | Cross-domain | Integration chain only; references owner bundles |

Detailed checkpoints per family remain in runbooks (`tmp_ops_runtime_*_execute.py` when implemented).

---

## 5. Checkpoint taxonomy

| Code | Layer | Description |
|------|--------|-------------|
| **G0** | Preflight | Env, flags, pilot lock, baseline snapshot, ownership declaration |
| **G1** | Browser | User actions executed; evidence captured |
| **G2** | User outcome | Visible state matches operational truth |
| **G3** | System outcome | DB/API persistence and linkage |
| **G4** | Async convergence | Post-mutation re-read within SLA |
| **G5** | Refresh persistence | Hard/soft reload; no stale UI |
| **G6** | Cross-role | Second principal sees coherent state |
| **G7** | Wording | No forbidden completion/compliance semantics |
| **G8** | Trust | No misleading operational implication |
| **G9** | Idempotency | Duplicate protection under repeat action (see §6) |
| **G10** | Authority integrity | Role + monotonic lifecycle + forbidden transitions (see §7) |

**Minimum for `VERIFIED_OPERATIONALLY`:** G0 + G1 + all family-mandatory checkpoints + G4 (if async) + G5 + G7 + G9/G10 where applicable for that family.

---

## 6. Operational idempotency verification (G9)

Happy-path success is insufficient. Where applicable, each family run **must** include idempotency probes:

| Scenario | Apply to |
|----------|----------|
| Double-click submit / rapid repeat POST | Issue create, WO create, payment record, tenant report |
| Refresh during in-flight mutation | All browser families |
| Repeated async fanout / daily job re-run | Risk regen, rent daily job, reminder processing |
| Retry after network blur (single intentional retry) | Contractor confirm, mark reminder sent |
| Duplicate prevention | risk→issue, risk→WO, reminder keys, period generation |

**Observe:**

- Row counts before/after repeat action  
- Unique key constraints (no duplicate operational rows)  
- UI feedback (disabled button, toast, idempotent success)  
- Race coherence (no contradictory twin records)

**Classification:**

| Finding | Classification |
|---------|----------------|
| Duplicate DB rows from repeat user action without documented multi-create support | **FAIL_SYSTEM** |
| Duplicate rows + user sees double operational debt | **FAIL_SYSTEM** + **TRUST_RISK_PRESENT** |
| Idempotent success (second action no-op, UI honest) | PASS G9 |
| Duplicate rows but hidden from user (single visible debt) | **TRUST_RISK_PRESENT** minimum |

---

## 7. Operational authority integrity (G10)

State convergence alone is insufficient. Verify **who may mutate what** and **monotonic lifecycle rules**.

### 7.1 Questions every authority-sensitive family must answer

- Who may mark a work order complete?  
- Who may reopen?  
- Can a contractor mutate landlord-only states?  
- Can a tenant close operational debt?  
- Can risk signals auto-close issues without user action?  
- Can async jobs overwrite manual landlord state without audit trail?

### 7.2 Required checks

- Role-based mutation authority (client / contractor / tenant / admin observe-only)  
- Monotonic lifecycle rules (e.g. completed → reopen only via explicit action)  
- Forbidden transitions rejected at API (403/404/400 — not silent success)  
- Stale overwrite protection (manual state wins over stale async recalc where designed)  
- Cross-role state precedence (contractor completion visible to client; not inverted)  
- Operational reopen semantics surfaced honestly in UI  

### 7.3 Strong application

| Family | G10 depth |
|--------|-----------|
| 2 Work orders | **Mandatory** |
| 3 Contractor | **Mandatory** |
| 7 Tenant portal | **Mandatory** |
| 8 Cross-domain | **Mandatory** (chain segment authority) |
| 1 Issues | Required for close/reopen |
| 6 Rent ops | Required for payment/reminder authority |

---

## 8. Rent operations — runtime wording (Family 6)

**Prior programme:** `RENT-OPS-OPERATIONAL-VERIFY-01` established **baseline system integrity** (metrics, worker idempotency, RBAC, compliance isolation) on staging.

**This runtime programme:** **Independently verifies browser/runtime operational truth** for rent — attention hierarchy, payment UX, reminder flow, snapshot/report coherence, mobile layout.

**Governance rule (no loophole):**

- Prior DB/API verification **does not** satisfy `VERIFIED_OPERATIONALLY` for Family 6  
- `VERIFIED_SYSTEM_ONLY` from prior rent programme **cannot** be upgraded to `VERIFIED_OPERATIONALLY` without a **new Family 6 browser run** with `proof_mode: operational_browser`  
- Family 6 bundle must list `shared_dependency_bundle_ids` pointing to `rent_ops_verify_01/REPORT.md` as **baseline reference only**

---

## 9. Tenant trust-risk hardening (Family 7)

**Risk weight:** **High** — tenant misinformation is a trust and compliance incident.

### 9.1 Mandatory checkpoint families

| Checkpoint | Description |
|------------|-------------|
| **tenant_visibility_scope_integrity** | Tenant sees only authorized property/issue scope; 404/empty for foreign IDs |
| **tenant_operational_truthfulness** | No false “job completed”, “issue resolved”, “compliant”, or landlord-internal states |

### 9.2 Trust-risk probes (Family 7 + G8)

- False “job completed” while WO still open on landlord side  
- False “issue resolved” while issue open in landlord queue  
- Contractor PII / internal routing notes leaked to tenant  
- Landlord triage notes / internal severity reasoning leaked  
- Stale tenant view after landlord reopen  
- Cross-property leakage (tenant A sees property B)  
- Tenant-visible race (submit twice → duplicate or ghost records)  
- Operational states beyond tenant authorization (waive, assign contractor, etc.)

**Classification:** Any confirmed tenant misinformation → **TRUST_RISK_PRESENT** minimum; data leakage → **FAIL_SYSTEM** + **TRUST_RISK_PRESENT**.

---

## 10. Cross-domain governance (Family 8)

See §3.2. Family 8 **REPORT.md** must contain:

```markdown
## Authoritative upstream bundles
| Chain segment | Owner family | Bundle | Classification |
|---------------|--------------|--------|----------------|
| Issue create | ops_runtime_01_issues | …/07_classification.json | VERIFIED_OPERATIONALLY |
| … | … | … | … |

## Integration-only checkpoints
- G8-X1: ID chain walk
- G8-X2: No contradictory open/closed across roles
- G8-X3: Compliance score unchanged by ops-only chain
```

Family 8 **BLOCKED** if any upstream segment lacks `VERIFIED_OPERATIONALLY` or signed WATCHLIST with explicit chain waiver.

---

## 11. Classification taxonomy (hardened)

| Classification | Criteria |
|----------------|----------|
| **VERIFIED_OPERATIONALLY** | G0+G1 mandatory PASS; browser `proof_mode: operational_browser`; convergence observed; bundle complete; ownership fields populated |
| **VERIFIED_SYSTEM_ONLY** | G3 PASS; browser missing or partial — **not** UX launch evidence for user-facing families |
| **TRUST_RISK_PRESENT** | Misleading wording; false completion semantics; duplicate visible debt; contradictory cross-role states; authority inflation; tenant misinformation; stale reopen contradictions — **blocks upgrade to VERIFIED_OPERATIONALLY** until remediated + browser rerun |
| **WATCHLIST** | Partial PASS; signed owner + re-verify date; explicit waiver scope |
| **FAIL_OPERATIONAL** | User-visible incorrect state |
| **FAIL_SYSTEM** | Persistence/linkage/idempotency/authority defect |
| **BLOCKED** | Preflight or upstream dependency failed |
| **OUT_OF_SCOPE** | Explicitly excluded |

### Upgrade rule (strict)

`VERIFIED_SYSTEM_ONLY` → `VERIFIED_OPERATIONALLY` **only** via a **new** family run with full browser proof. **No administrative upgrade** without bundle evidence.

### TRUST_RISK_PRESENT examples

- Landlord UI implies compliance impact from rent risk signal  
- “Open issues” list shows work orders mislabeled as issues  
- Tenant sees resolved while landlord queue shows open  
- Double payment creates duplicate visible debt without unallocated honesty  
- Contractor can PATCH client-only fields  

---

## 12. Async convergence standards

| Mutation class | Max wait | Re-read |
|----------------|----------|---------|
| Issue + triage | 30s | List + detail |
| WO status / assignment | 60–120s | Client + contractor |
| Risk regen | 120s | Signal list + property |
| Rent daily job | Job run + 60s | Summary + attention |
| Cross-family (F8) | Sum of segment SLAs | Integration surfaces |

**PASS:** User + DB agree after wait; no idempotent duplicate spam.

---

## 13. Artifact / bundle structure

```
backend/docs/audit/ops_runtime_{family_slug}/
  00_preflight.json              # includes authoritative_verification_owner, shared_dependency_bundle_ids
  01_baseline_db.json
  02_browser_actions.jsonl
  03_post_mutation_db.json
  04_async_convergence.json
  05_cross_role.json
  06_refresh_persistence.json
  06b_idempotency.json           # G9 probes
  06c_authority_integrity.json   # G10 probes
  07_classification.json
  REPORT.md                      # commit-safe governance summary
  screenshots/                   # gitignored (local/staging only)
```

**Git policy:** Commit `REPORT.md`, `07_classification.json`, redacted `00_preflight.json`. Exclude passwords, raw screenshots, transient JSON dumps unless redacted.

---

## 14. Execution order

1. Preflight + pilot lock  
2. Family 1 Issues  
3. Family 2 Work orders  
4. Family 3 Contractor  
5. Family 4 Risk signals  
6. Family 5 Client sync  
7. Family 6 Rent ops (browser runtime)  
8. Family 7 Tenant portal  
9. Family 8 Cross-domain (requires upstream bundle refs)

---

## 15. Highest-risk families (governance weight)

| Rank | Family | Primary risk |
|------|--------|--------------|
| 1 | 3 Contractor | Cross-role desync + authority |
| 2 | 7 Tenant portal | Misinformation + scope leakage |
| 3 | 1 Issues | WO/issue conflation |
| 4 | 5 Client sync | Stale projections |
| 5 | 8 Cross-domain | False integration PASS via duplication |
| 6 | 4 Risk signals | Advisory vs compliance confusion |
| 7 | 6 Rent ops | Runtime UX unproven vs baseline |
| 8 | 2 Work orders | SLA/evidence wording |

---

## 16. Suggested pilots (staging)

| Role | Pilot |
|------|-------|
| Primary ops | Wales HMO `6fd5ac4c…` / `d35a58ae…` |
| Rent-dedicated | `rent_ops_verify_01_*` client |
| England secondary | `6bcc43c0…` / `3a69dcbd…` |
| Contractor | Bookable staging contractor linked to pilot WO |
| Tenant | Tenant user assigned to pilot property |

---

## 17. Relationship to other programmes

| Programme | Relationship |
|-----------|--------------|
| **OPS-VERIFY-01** | Compliance **evidence** journeys — separate; do not merge |
| **PRELAUNCH-OPS-VERIFY-CONDITION-STANDARD-01** | Condition-standard pilots — separate |
| **RENT-OPS-OPERATIONAL-VERIFY-01** | Baseline system integrity for rent — Family 6 **depends on** but does not inherit `VERIFIED_OPERATIONALLY` |
| **C2 / E1 / F1** | Compliance convergence/authority — observe-only; ops programme does not replace |
| **PRELAUNCH-OPS-RUNTIME-VERIFY-02** | Client **control-surface** operational cognition — **depends on** VERIFY-01 lineage; does **not** inherit surface coherence from F1–F8 PASS — see [`PRELAUNCH_OPS_RUNTIME_VERIFICATION_02.md`](PRELAUNCH_OPS_RUNTIME_VERIFICATION_02.md) |

---

## 18. Intentionally deferred

- Launch authorization / UK rollout approval  
- Fleet-wide ops rollout from verification PASS  
- Asset-native synthesis expansion  
- Accounting certification / tax reporting verification  
- Compliance authority / planner redesign verification  
- AI operational orchestration  
- Full tenant UI if only API exists (Family 7 → WATCHLIST until UI shipped)  
- Mega-run or combined classifier across all eight families  

---

*Maintainers: update `LAUNCH_AUTHORITY_TRACKER.md` § PRELAUNCH-OPS-RUNTIME-VERIFY-01 after each family classification. Do not conflate with OPS-VERIFY-01 or widen launch posture from this programme.*
