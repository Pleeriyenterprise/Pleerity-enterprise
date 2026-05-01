# Stream D Phase 4 — CTA parity enforcement (read-only + backend contract)

**Purpose:** Prevent **silent drift** between backend `requirement_action_resolver.py` and frontend `requirementTakeActionResolver.js` for **requirement-backed** client CTAs, without changing routing or runtime behaviour in this slice.

**Companion:** `STREAM_D_CTA_PRODUCER_CONSUMER_MATRIX.md`, `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` (Stream D).

**Authorities:** Backend envelope — `resolve_take_action_envelope`, `resolve_take_action_for_priority_action`; frontend mirror — `frontend/src/utils/requirementTakeActionResolver.js` + `requirementTakeActionResolver.test.js`.

---

## 1. Parity-critical resolver outputs (inventory)

These fields and behaviours **must** stay aligned across Python and JavaScript for obligation CTAs that use the shared contract (`requirement_take_action_v1`):

| Concern | Backend source | Frontend consumer | Why parity-critical |
|---------|----------------|-------------------|---------------------|
| **Intent** | `take_action.primary.intent` (stable string: `upload_evidence`, `view_guidance`, `maintenance`, `coordinate_inspection_evidence`, `guided_evidence_resolution`, `guided_evidence_unavailable`, `direct_evidence_action`) | `primary_intent` derived from `intent` or route heuristics when legacy | Downstream analytics, inbox routing, modal vs navigate |
| **Primary route** | `take_action.primary.route` (`null`/empty for guided/direct/unavailable) | `primary_route` / `resolveInboxTaskTakeActionRoute` | Wrong URL = dead CTA or silent fallback |
| **Primary label** | `take_action.primary.label` | `primary_action_label` | Copy drift breaks trust / compliance tone |
| **Suppression** | `take_action.suppressed` + `primary: null` | `guided_evidence_error` / `none` handler; must **not** substitute upload | Treating suppressed as “upload” is a **compliance UX violation** |
| **Guided vs direct** | `kind` + `handler` (`guided_evidence`, `direct_evidence`, `guided_evidence_unavailable`, `navigate`) | Same shapes drive modal vs router | Modal opens without ids = FE guard + `guided_evidence_error` |
| **Fallback** | Priority projection: empty navigate route → `primary_action_url` `""` for guided/direct; else `str(route)` or **`/dashboard`** when `primary` empty (`resolve_take_action_for_priority_action`) | `ctaRegistry` / task builders must not reintroduce gap `recommended_url` when canonical exists (matrix B1/B2) | Double-truth (Rule R2) |
| **Empty-route semantics** | Guided primary: `route` empty; unavailable: `metadata_incomplete`; direct: `evidence_mode` on primary | FE opens evidence modal only when ids present; else error handler | Prevents silent document fallback |

**Non-parity (intentional):** Risk operations URLs, admin `/admin/…`, digest-only literals — see matrix §3.

---

## 2. Canonical parity fixtures (deterministic)

**Module:** `backend/tests/fixtures/cta_parity_fixtures.py`

**Stable IDs:** `P01` … `P10` — each row defines:

- A **frozen requirement-shaped input** (or explicit `property_id` / `jurisdiction` overrides).
- **Expected envelope** assertions (`resolve_take_action_envelope`): `action_type`, `take_action.suppressed`, `primary` `intent` / `kind` / `handler` / route shape / labels / `evidence_mode` where applicable.
- **Expected priority projection** (`resolve_take_action_for_priority_action` with an explicit **`compliance_engine`** mirroring `unified_tasks_service` merge), **or** `skip_priority_projection`.

**`skip_priority_projection` (P01, P02):** `resolve_take_action_for_priority_action` builds a **synthetic** row that does **not** copy `client_surface_visible` or all `registry_metadata` flags from enriched requirements. Production surfaces normally attach **`canonical_take_action`** / full `take_action` from `resolve_take_action_envelope` on enriched rows. For **suppressed** CTAs, **envelope output is authoritative**; minimal priority-row-only projection is **out of scope** for this parity layer.

**`priority_compliance_engine`:** Non-empty dict (or `resolve_engine_payload_from_code(...)`) so the resolver does **not** silently call `resolve_engine_payload_from_code` with a truthiness bug on `{}` (see `resolve_take_action_for_priority_action`: `if not eng and code:`).

---

## 3. Backend contract tests (frozen behaviour)

**File:** `backend/tests/test_cta_parity_contract.py`

- Parametrises over `all_cta_parity_cases()`.
- Asserts envelope + (unless skipped) priority projection against fixture expectations.
- **`test_cta_parity_fixture_registry_is_stable_length`:** bump **deliberately** when adding `P11+` (keeps docs and CI honest).

**No runtime code changes** — tests fail when resolver output changes; authors must update **fixtures + this doc + frontend** in a coordinated PR.

---

## 4. How frontend parity is validated

| Mechanism | Role |
|-----------|------|
| **`requirementTakeActionResolver.test.js`** | Unit parity for `resolveRequirementAction`, `requirementUsesServerTakeActionPrimary`, `resolveInboxTaskTakeActionRoute`, suppression, guided unavailable, merge of supporting links. |
| **`ComplianceScorePage.scoreDrivers.test.js`** (Stream D — D-C07) | Regression: score-driver remediation uses the same **server-primary gate** (`requirementUsesServerTakeActionPrimary`) + `resolveRequirementAction` as other obligation surfaces; no heuristic driver `actions` as clickable remediation. |
| **Manual cross-check** | When changing `requirement_action_resolver.py`, run FE tests locally and compare `intent` / `kind` / `handler` / route rules against §1 table. |
| **Future CI gate (recommended)** | In the **frontend** repo or monorepo workflow: export fixture JSON from `cta_parity_fixtures` (generated step) or duplicate golden subset in JS — **release-blocking** once product approves (see §6). |

---

## 5. Authoritative fields vs frontend freedom

### 5.1 Authoritative (must match backend when `take_action` is present)

- `take_action.contract` and `take_action.provenance` (read-only display / diagnostics).
- `take_action.primary` / `secondary`: **`intent`**, **`kind`**, **`handler`**, **`route`**, **`label`**, **`evidence_mode`**, **`metadata_incomplete`**, **`property_id`**, **`requirement_id`** for guided/direct.
- **Suppression:** `take_action.suppressed` — frontend must **not** replace with upload/guided CTAs (`requirementTakeActionResolver.js` branch).

### 5.2 Frontend may customise (non-authoritative for obligation routing)

- **Presentation** wrappers (spinner, icon, analytics `data-*`, disabled state) **without** changing label text or target route semantics.
- **Secondary ordering** in layout (e.g. show secondary as inline vs overflow) if URLs unchanged.
- **`mergeRequirementSupportingLinks`** dedupe order for **supporting** links (same URLs) — must remain deduped; label tweaks for accessibility only with product approval.

### 5.3 Frontend must **never** override

- **Primary** label/route when `requirementUsesServerTakeActionPrimary` is true (server-complete primary).
- **Rule R2:** Raw gap `recommended_url` / `recommended_action_label` for **requirement-primary** surfaces when `canonical_take_action` / resolver output exists (matrix §4).
- **Compliance score drivers (D-C07):** Do not present **requirement-primary remediation** labels or routes unless `requirementUsesServerTakeActionPrimary` is true for the joined requirement row (matrix D-C07).
- **Risk / ops** URLs using the requirement resolver — risk stays on `/operations/risk-signals?signal_id=…` contract (matrix §3).
- **Suppressed** or **guided-unavailable** rows: no silent fallback to `/documents` as **primary** intent.

---

## 6. Release-blocking parity rules (proposal)

### 6.1 What counts as drift

- Any change to **`INTENT_*` string values** in Python without matching `requirementTakeActionResolver.js` / tests.
- Any change to **route templates** for the same obligation class (documents query shape, property hash, operations new-issue URL) without FE update.
- Any change to **`resolve_take_action_for_priority_action`** `primary_action_type` / `primary_action_url` / `primary_action_label` mapping for `ACTION_MISSING_DOCUMENT` / `ACTION_OVERDUE_COMPLIANCE` / `ACTION_CERT_EXPIRING_SOON` consumers without unified-task / matrix review.
- New **guided/direct** branch in Python without `kind` / `handler` / `intent` parity in JS.
- Removing or weakening **`skip_priority_projection`** documentation for suppressed rows without proving production always sends `canonical_take_action`.

### 6.2 When CI should fail (backend — implemented)

- **`pytest tests/test_cta_parity_contract.py`** fails on default branch / PR touching `services/requirement_action_resolver.py` or `tests/fixtures/cta_parity_fixtures.py` (path-scoped job optional; minimum: full backend test job includes this module).

### 6.3 When CI should fail (frontend — not implemented here)

- Optional job: parse exported golden JSON or run `requirementTakeActionResolver.test.js` on a schedule; fail if **intent** or **normalised route** class diverges from fixture export.

### 6.4 Coordinated FE / BE updates (required process)

1. Change **Python resolver** (or registry-driven evidence policy that alters resolver branches).
2. Update **`cta_parity_fixtures.py`** + **`test_cta_parity_contract.py`** if expectations move.
3. Update **`requirementTakeActionResolver.js`** + **`requirementTakeActionResolver.test.js`** in the same release train.
4. Update **this doc** §1 / §2 if the inventory or fixture IDs change.
5. PR description must cite **Stream D Phase 4** and list **both** repos if split.

---

## 7. Changelog (doc edits only)

| Date | Change |
|------|--------|
| 2026-05-01 | Initial **Phase 4 parity enforcement** doc + `cta_parity_fixtures` + `test_cta_parity_contract`. |
