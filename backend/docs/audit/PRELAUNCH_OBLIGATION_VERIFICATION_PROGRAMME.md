# Pre-launch obligation operational verification programme

**Programme ID:** `PRELAUNCH-OPS-VERIFY-01`  
**Type:** Bounded launch-readiness exercise (operational proof, not governance expansion)  
**Inventory source:** `prelaunch_obligation_inventory_staging.json` (staging `pleerity_staging`, captured 2026-05-20)  
**Harness reuse:** `scripts/ops_verify_01_{capture,manifest,snapshot,classify}.py` — one bundle per `(client_id, property_id, requirement_code)`

## Boundaries (non-negotiable)

- Do **not** widen G1/E1/F1, add constitutional RCs, or redesign authority/recalc/registry/applicability.
- Do **not** force-test obligations on properties where they are not applicable.
- Do **not** classify from implementation, API-only checks, or replay-governance analysis alone.
- Each test: real client session, real browser, applicable property, real evidence action, DB snapshots, async convergence wait, UI refresh attestation.
- Inventory pass is **read-only**; failures → preserve evidence, honest classification, narrow remediation unit only.

---

## Step 1 — Requirement coverage inventory

**Supported universe (30 codes)** = union of:
- `requirements_catalog` seed (**15** codes in `database._seed_requirements_catalog`)
- `build_requirement_plan_for_property` planner emissions (e.g. `occupation_contract`, `hmo_fire_risk*`, registrations, communal HMO rows)
- `DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE` (**15** explicit policy keys + registration slugs loop)
- Staging materialised `requirements` rows (**30** distinct `requirement_type` values)

**Default evidence policy** (when not in explicit map): `LEGACY_DOCUMENT_UPLOAD` — primary `DOCUMENT_UPLOAD` only (`effective_evidence_resolution` fallback).

### Inventory table

| Code | Catalog | Policy workflow | Evidence modes | Planner / jurisdiction notes | Staging rows | Client surfaced (sample) | Candidate test property |
|------|---------|-----------------|----------------|---------------------------|--------------|--------------------------|-------------------------|
| `gas_safety` | Yes | LEGACY_DOCUMENT_UPLOAD | DOCUMENT_UPLOAD | Core; gas supply rules | 49 | Yes — multi | Pilot `d35a58ae` (Wales HMO) or `13b370bd` (England) |
| `eicr` | Yes | LEGACY_DOCUMENT_UPLOAD | DOCUMENT_UPLOAD | Core | 49 | Yes | Pilot `d35a58ae` |
| `epc` | Yes | LEGACY_DOCUMENT_UPLOAD | DOCUMENT_UPLOAD | Core | 49 | Yes | Pilot `d35a58ae` |
| `legionella` | Yes | EXTERNAL_ASSESSMENT | STRUCTURED + DOCUMENT | Core / JOB class | 49 | Yes | Pilot `d35a58ae` |
| `fire_alarm` | Yes | LEGACY_DOCUMENT_UPLOAD | DOCUMENT_UPLOAD | Fire-detection alias family | 49 | Yes | Pilot `d35a58ae` (OPS-VERIFY B/D) |
| `hmo_license` | Yes | LEGACY_DOCUMENT_UPLOAD | DOCUMENT_UPLOAD | HMO / licence_required | 22 | Yes | Pilot `d35a58ae` |
| `hmo_fire_risk_evidence` | — | GUIDED_EVIDENCE_RESOLUTION | DOC + contractor + checklist | HMO fire evidence | 21 | Yes | Pilot `d35a58ae` |
| `occupation_contract` | — | Wales → `wales_occupation_contract` policy | STRUCTURED + DOCUMENT (Wales) | Wales only; aliases `wales_occupation_contract` | 10 | Yes (Wales) | Pilot `d35a58ae` (OPS-VERIFY A/C) |
| `hmo_fire_risk` | — | GUIDED_EVIDENCE_RESOLUTION | Multi | Alias of `hmo_fire_risk_evidence` | 49 | Yes (deduped) | Use evidence slug on pilot, not duplicate test |
| `fire_risk_assessment` | Yes | GUIDED_EVIDENCE_RESOLUTION | Multi | HMO FRA catalog | 3 | Yes | `666d2ce6` (Wales, client `6bcc43c0`) |
| `portable_appliance_test` | Yes | LEGACY_DOCUMENT_UPLOAD | DOCUMENT_UPLOAD | Optional PAT | 49 | Yes | `989adf3c` (England) |
| `deposit_pi` | Yes | GUIDED_DECLARATION | STRUCTURED + DOCUMENT | England/Scotland tenancy | 13 | Yes | `e95c5b5a` (England) |
| `how_to_rent` | Yes | TENANT_DELIVERY | STRUCTURED + DOCUMENT | England | 13 | Yes | `e95c5b5a` |
| `right_to_rent` | Yes | GUIDED_DECLARATION | STRUCTURED + DOCUMENT | England | 8 | Yes | `e95c5b5a` |
| `tenancy_agreement` | Yes | GUIDED_DECLARATION | STRUCTURED + DOCUMENT | UK | 14 | Yes | `e95c5b5a` or `76c5b548` (Scotland) |
| `scotland_landlord_registration` | — | REGISTRATION_TRACKING | STRUCTURED + DOCUMENT | Scotland | 7 | Yes | `def23b30` (Scotland) |
| `landlord_registration_ni` | — | REGISTRATION_TRACKING | STRUCTURED + DOCUMENT | NI | 8 | Yes | `f1c7b5df` (NI) or pilot NI props |
| `rent_smart_wales` | — | REGISTRATION_TRACKING | STRUCTURED + DOCUMENT | Wales | 2 | Yes | `2e9c2f5f` (Wales) |
| `wales_occupation_contract` | — | GUIDED_DECLARATION | STRUCTURED + DOCUMENT | Wales planner slug | 2 | Yes | `2e9c2f5f` (Wales) |
| `landlord_registration` | — | REGISTRATION_TRACKING | STRUCTURED + DOCUMENT | England | 4 | **No** surfaced sample | NEEDS_APPLICABLE_PROPERTY + surface check |
| `lead_testing` | — | EXTERNAL_ASSESSMENT | STRUCTURED + DOCUMENT | Scotland Repairing Standard | **0** | No | IMPLEMENTED_NOT_MATERIALISED |
| `smoke_heat_alarms` | — | GUIDED_EVIDENCE_RESOLUTION | Multi | Alarm family policy | **0** | No | TEST_DATA_REQUIRED |
| `smoke_alarms` | Yes | LEGACY (alias) | DOCUMENT | Fire-detection family | 4 | **No** | NOT_CLIENT_VISIBLE_BY_DESIGN (alias) |
| `co_alarms` | Yes | LEGACY (alias) | DOCUMENT | Fire-detection family | 4 | **No** | NOT_CLIENT_VISIBLE_BY_DESIGN (alias) |
| `fire_detection` | Yes | LEGACY | DOCUMENT | Canonical detection | 1 | **No** | NEEDS_APPLICABLE_PROPERTY |
| `emergency_lighting` | — | LEGACY | DOCUMENT | HMO materialised | 22 | **No** | NOT_CLIENT_VISIBLE_BY_DESIGN (pilot signed-off) |
| `fire_extinguisher` | — | LEGACY | DOCUMENT | HMO materialised | 22 | **No** | NOT_CLIENT_VISIBLE_BY_DESIGN (pilot signed-off) |
| `communal_cleaning` | — | LEGACY | DOCUMENT | Communal HMO | 8 | **No** | NOT_CURRENT_LAUNCH_SCOPE (no client surface) |
| `communal_fire_doors` | — | LEGACY | DOCUMENT | Communal HMO | 8 | **No** | NOT_CURRENT_LAUNCH_SCOPE |
| `property_licence` | — | LEGACY | DOCUMENT | Selective licensing | 2 | **No** | NEEDS_APPLICABLE_PROPERTY |

**Wales HMO pilot client-visible set (signed-off B1, 8 types):**  
`eicr`, `legionella`, `epc`, `gas_safety`, `hmo_license`, `fire_alarm`, `hmo_fire_risk_evidence`, `occupation_contract` on `6fd5ac4c` / `d35a58ae`.

---

## Step 2 — Operational test matrix

| Matrix status | Count | Codes |
|---------------|------:|-------|
| **READY_FOR_OPERATIONAL_TEST** | 22 | All surfaced rows with staging property + applicable jurisdiction (see inventory) |
| **NEEDS_APPLICABLE_PROPERTY** | 3 | `fire_detection`, `landlord_registration`, `property_licence` |
| **NOT_CLIENT_VISIBLE_BY_DESIGN** | 5 | `emergency_lighting`, `fire_extinguisher`, `smoke_alarms`, `co_alarms`, `hmo_fire_risk` (dedupe — test `hmo_fire_risk_evidence` only) |
| **IMPLEMENTED_NOT_MATERIALISED** | 1 | `lead_testing` |
| **TEST_DATA_REQUIRED** | 1 | `smoke_heat_alarms` |
| **NOT_CURRENT_LAUNCH_SCOPE** | 2 | `communal_cleaning`, `communal_fire_doors` |
| **BLOCKED_BY_PRODUCT_POLICY** | 0 | — |

*Pilot 8 are all **READY** on `d35a58ae`; 5 still lack per-type operational closure (see roll-up).*

---

## Step 3 — Per-requirement operational test paths (READY)

**Common protocol (all READY items):**

1. `ops_verify_01_capture --init-bundle --slug-suffix {cid}_{pid}_{code}`
2. `--phase baseline` (requirement row, authority, CERs, documents, queue fingerprint, client API enrich sample)
3. Browser: login staging client → property compliance → obligation card → primary CTA (or `/documents?...&focus=upload` for LEGACY_DOCUMENT)
4. `--phase post-submit` (+ correlation id / cer_id from network tab)
5. Wait ≤15 min → `--phase convergence`
6. Hard refresh → UI notes + screenshots → `ops_verify_01_classify`
7. Bundle under `docs/audit/ops_verify_01_{slug}/`

### Pilot Wales HMO (`6fd5ac4c` / `d35a58ae`) — launch-critical

| Code | Req ID (pilot) | Mode | Entry | Expected system | Prior evidence |
|------|----------------|------|-------|-----------------|----------------|
| `occupation_contract` | `488269bb-…` | STRUCTURED (+ supporting) | Property `?open=resolve` / guided modal | CER `PENDING_REVIEW`; authority `MISSING`→review path; recalc DONE | **Partial** OPS-VERIFY A/C |
| `fire_alarm` | `69fc66fe-…` | DOCUMENT primary | `/documents?…&requirement_code=fire_alarm&focus=upload` | Document + CER link; verify path | **VERIFIED** OPS-VERIFY B/D |
| `legionella` | `537da91b-…` | STRUCTURED (+ doc secondary) | Guided “Record Legionella…” | CER; queue; authority coherent post-433800ce | **Partial** — post-fix pre-submit; doc-upload path open |
| `eicr` | (resolve at baseline) | DOCUMENT | Documents deeplink `requirement_code=eicr` | Document-primary CER; optional admin verify | **IMPLEMENTED_NOT_VERIFIED** |
| `epc` | (baseline) | DOCUMENT | Documents deeplink | Same as eicr pattern | **IMPLEMENTED_NOT_VERIFIED** |
| `gas_safety` | (baseline) | DOCUMENT | Documents deeplink | CP12 document; expiry on row | **IMPLEMENTED_NOT_VERIFIED** |
| `hmo_license` | (baseline) | DOCUMENT | Documents / obligation card | Licence doc; authority | **IMPLEMENTED_NOT_VERIFIED** |
| `hmo_fire_risk_evidence` | (baseline) | GUIDED (doc or checklist) | Guided resolution modal | CER multi-mode; contractor/checklist if chosen | **IMPLEMENTED_NOT_VERIFIED** |

### Non-pilot READY (sequenced after pilot)

| Code | Client / property (staging sample) | Primary mode | Notes |
|------|-----------------------------------|--------------|-------|
| `deposit_pi` | `94fd6021` / `e95c5b5a` | STRUCTURED | Conditional deposit fields validation |
| `how_to_rent` | `94fd6021` / `e95c5b5a` | STRUCTURED | TENANT_DELIVERY workflow |
| `right_to_rent` | `94fd6021` / `e95c5b5a` | STRUCTURED | Follow-up date rules |
| `tenancy_agreement` | `94fd6021` / `e95c5b5a` | STRUCTURED | |
| `scotland_landlord_registration` | `ec0b091b` / `def23b30` | STRUCTURED | REGISTRATION_TRACKING |
| `landlord_registration_ni` | `6a614499` / `f1c7b5df` | STRUCTURED | NI jurisdiction |
| `rent_smart_wales` | `6bcc43c0` / `2e9c2f5f` | STRUCTURED | Wales registration |
| `wales_occupation_contract` | `6bcc43c0` / `2e9c2f5f` | STRUCTURED | Distinct from `occupation_contract` slug |
| `fire_risk_assessment` | `6bcc43c0` / `666d2ce6` | GUIDED multi | Wales HMO |
| `portable_appliance_test` | `5db7bba1` / `989adf3c` | DOCUMENT | England |

---

## Step 4 — Execution discipline

- **One requirement per run**; no batch UI walks.
- Do not reuse post-submit snapshots across codes (Journey C terminal state on pilot conflated shared snapshots — per-code bundles required).
- Admin verify step only when product path requires `PENDING_REVIEW` → `VERIFIED` for launch narrative.
- Classify only after convergence + refresh.

---

## Step 5 — Classifications (current state)

| Code | Classification | Notes |
|------|----------------|-------|
| `fire_alarm` | **VERIFIED_OPERATIONALLY** | OPS-VERIFY-01 B + D |
| `occupation_contract` | **VERIFIED_OPERATIONALLY** (watchlist) | OPS-VERIFY A/C; clean greenfield pre-submit not attested |
| `legionella` | **VERIFIED_OPERATIONALLY** (watchlist) | Post-submit + TRUST fix 433800ce; doc-upload + admin verify open |
| `eicr`, `epc`, `gas_safety`, `hmo_license`, `hmo_fire_risk_evidence` | **IMPLEMENTED_NOT_VERIFIED** | Visible on pilot; no dedicated per-type run |
| All other READY (non-pilot) | **IMPLEMENTED_NOT_VERIFIED** | Surfaced + property exists; execution not started |
| `emergency_lighting`, `fire_extinguisher` | **NOT_APPLICABLE_FOR_SELECTED_PROPERTY** (pilot) | Materialised but runtime-excluded — by design |
| `lead_testing` | **IMPLEMENTED_NOT_MATERIALISED** | Policy exists; 0 staging rows |
| `smoke_heat_alarms` | **TEST_DATA_REQUIRED** | Policy exists; 0 rows |
| `communal_*` | **NOT_CURRENT_LAUNCH_SCOPE** | No client surface |
| `landlord_registration`, `fire_detection`, `property_licence` | **NEEDS_APPLICABLE_PROPERTY** | Materialised; no surfaced walk target in scan |

---

## Step 6 — Evidence bundle schema (per test)

```
docs/audit/ops_verify_01_{cid}_{pid}_{code}/
  ops_verify_01_run_manifest.json      # run manifest
  ops_verify_01_baseline_*.json
  ops_verify_01_post_submit_*.json
  ops_verify_01_convergence_*.json
  ops_verify_01_classifications.json
  ops_verify_01_ui_notes.md
  screenshots/*.png
  watchlist.md                         # non-blocking observations
```

---

## Step 7 — Roll-up (pre-execution programme state)

| Metric | Value |
|--------|------:|
| Total supported requirement codes | **30** |
| Explicit evidence-policy codes | **15** + 4 registration slugs |
| Catalog seed codes | **15** |
| Staging materialised types | **30** |
| Client-surfaced types (40-client scan) | **19** |
| **READY_FOR_OPERATIONAL_TEST** | **22** |
| **VERIFIED_OPERATIONALLY** (pilot + prior runs) | **3** (`fire_alarm`, `occupation_contract`, `legionella`) |
| **IMPLEMENTED_NOT_VERIFIED** (launch-visible gap) | **5** on pilot + **14** off-pilot READY |
| Blocked by product policy | **0** |
| Need test data / materialisation | **2** (`lead_testing`, `smoke_heat_alarms`) |
| User-visible by design exclusions (pilot) | **2** (`emergency_lighting`, `fire_extinguisher`) |
| Not launch scope | **2** communal |

### Top launch-blocking issues

1. **Pilot core documents not operationally closed per type** — `eicr`, `epc`, `gas_safety`, `hmo_license`, `hmo_fire_risk_evidence` lack per-requirement browser+DB proof on `d35a58ae`.
2. **England/Scotland/Wales obligation stacks unverified** — deposit, RTR, How to Rent, registrations (14 READY off-pilot).
3. **`lead_testing` / `smoke_heat_alarms`** — cannot test without provisioning applicable Scotland/modern alarm property.

### Non-blocking watchlist

- Legionella: pipeline `applicability_state` vs client overlay; admin verify for open CERs; secondary document path.
- Occupation contract: greenfield first structured submit on clean property.
- Shared pilot snapshot conflation in early OPS-VERIFY manifest (remediated by per-code bundles going forward).
- `hmo_fire_risk` dedupe — do not double-test if `hmo_fire_risk_evidence` passes.

---

## Step 8 — Recommended next test order

1. `gas_safety` — pilot, DOCUMENT, highest regulatory weight  
2. `eicr` — pilot, DOCUMENT  
3. `epc` — pilot, DOCUMENT  
4. `hmo_license` — pilot, DOCUMENT  
5. `hmo_fire_risk_evidence` — pilot, GUIDED (one mode only per run)  
6. `legionella` — pilot, DOCUMENT_UPLOAD secondary path (STRUCTURED already exercised)  
7. `occupation_contract` — pilot, greenfield STRUCTURED if clean baseline available  
8. `deposit_pi` → `how_to_rent` → `right_to_rent` → `tenancy_agreement` (England `e95c5b5a`)  
9. `scotland_landlord_registration` → `rent_smart_wales` / `wales_occupation_contract`  
10. `landlord_registration_ni` → `fire_risk_assessment` → `portable_appliance_test`  
11. Provision **TEST_DATA_REQUIRED** / **IMPLEMENTED_NOT_MATERIALISED** only if launch scope expands  

---

## Launch-readiness risk summary

**Operational confidence is high for evidence workflow mechanics** (structured submit, document upload, supporting-only, admin verify alignment) on the Wales HMO pilot, but **launch readiness for “every applicable obligation” is not met**: only 3/8 pilot-visible types have operational classification; 0/14 off-pilot READY types have been executed under this programme.

**Risk level:** **MEDIUM–HIGH** for multi-jurisdiction launch; **LOW–MEDIUM** for Wales HMO-only cohort if remaining 5 pilot types complete with no new `TRUST_RISK` or `SYSTEM_OUTCOME_UNPROVEN`.

**Gate:** Do not widen governance to clear gaps — use narrow remediation units per failed classification only.

---

## CONDITION_STANDARD_ACTIVE_STANDARD (Phase 1 — separate programme)

**Programme id:** `PRELAUNCH-OPS-VERIFY-CONDITION-STANDARD-01`  
**Family:** `CONDITION_STANDARD_ACTIVE_STANDARD`  
**Proof mode:** `operational_convergence` (not document-upload closure)

| Obligation | Pilot materialisation | OPS status |
|------------|----------------------|------------|
| `fitness_for_human_habitation` | Allowlisted — admin path only | **`VERIFIED_OPERATIONALLY`** (2026-05-23) — registry remediation `FITNESS_FOR_HUMAN_HABITATION\|ENGLAND` published (v24); same-run browser OPS passed — bundle `ops_verify_01_6bcc43c0_3a69dcbd_fitness_for_human_habitation/` |
| `repairing_standard` | Allowlisted — admin path only | **`VERIFIED_OPERATIONALLY`** (2026-05-22) — matrix/inspect/CTA/disclosure/refresh + `?open=resolve` → issues/remediation; bundle `ops_verify_01_ec0b091b_def23b30_repairing_standard/` |

**Prerequisites before OPS:** invoke pilot materialisation; confirm `tenancy_active`; jurisdiction gate (FFHH ≠ Scotland; RS = Scotland); maintenance workflows enabled.

**Classifications:** `VERIFIED_OPERATIONALLY`, `ASYNC_CONVERGENCE_PARTIAL`, `USER_VISIBLE_GAP`, `TRUST_RISK_PRESENT`, `SYSTEM_OUTCOME_UNPROVEN`, `TEST_DATA_REQUIRED`.

**Spec:** `docs/audit/CONDITION_STANDARD_ACTIVE_STANDARD_OPS.md`
