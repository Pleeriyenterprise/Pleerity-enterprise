# OPERATIONS-ENTITLEMENT-DISCOVERY-AND-ACTION-UX-AUDIT-01

**Run:** `20260612T111711Z`  
**Classification:** `PARTIAL`  
**Codes:** `ENTITLEMENT_VISIBILITY_DRIFT`, `ACTIONABILITY_DRIFT`, `CONTRACTOR_ASSIGNMENT_UX_DRIFT`, `PLAN_VALUE_DRIFT`, `LOCKED_FEATURE_UX_DRIFT`

Evidence-only audit. **No product fixes implemented.**

---

## 1. Current entitlement inventory

Authoritative sources: `plan_registry.FEATURE_MATRIX` (commercial) + `ops_compliance_feature_flags.DEFAULTS_BY_PLAN` (operations modules). Full matrix: `operations_entitlement_inventory_runtime.json`.

| Capability | Solo | Portfolio | Professional |
|------------|:----:|:---------:|:------------:|
| Operations nav (Issues/Jobs) | Hidden | Visible | Visible |
| Maintenance jobs API | 403 | 200 | 200 |
| Risk signals | Hidden / 403 | Visible / 200 | Visible / 200 |
| Rent operations | Hidden | Visible | Visible |
| Contractor network | Hidden / 403 | Hidden / 403 | Visible / 200 |
| Tenant portal | Hidden | Hidden | Visible |
| PDF/CSV reports | Hidden | Visible | Visible |
| Audit log export | Hidden | Hidden | Visible |

**Navigation strategy:** gated items are **filtered out** (not shown as locked). Route-level `EntitlementProtectedRoute` shows full-page `UpgradeRequired` when a user deep-links.

**Staging fixtures probed:** Solo `616258a5…`, Portfolio `80f83edd…`, Professional `6fd5ac4c…` (Nancy). See `sessions_runtime.json`.

**Fixture drift:** Sophie Walker (`10b2ddba…`) is documented historically as Portfolio calm but **staging runtime is now `PLAN_1_SOLO`** with all ops flags off.

---

## 2. Contractor assignment UX result

| Scenario | Expected | Observed |
|----------|----------|----------|
| **A — Entitled (Professional)** | CTA + modal + focus select | Hero + section open modal; **focus lands on BUTTON not select** (`modal_focus_target: BUTTON`) |
| **B — Entitled, no contractors** | Early-network CTA focused | Code path exists (`Add contractor for this area`); not browser-probed this run |
| **C — Portfolio (maintenance, no network)** | Locked CTA / no modal | API: `contractor_directory` 403; job-detail blocked UX per code + prior Sophie audit |
| **C — Issues assign CTA** | Should not mislead | **Drift:** `resolveIssuePrimaryAction` emits `assign_contractor` with URL; **no `contractor_network` gate** on Issues page |

**Backend guards:**

- `GET /jobs/{id}/assignable-contractors` — requires `CONTRACTOR_NETWORK` ✓
- `POST /jobs/{id}/assign-contractor` — **only `maintenance_workflows`** (missing `CONTRACTOR_NETWORK`) ✗

Cross-reference: `job_detail_actionability_convergence_01` — Sophie blocked assign (upgrade alert, no section button) PASS.

---

## 3. Locked vs hidden strategy

See `locked_feature_strategy_runtime.json`. Summary:

| Feature | Solo | Portfolio | Pro | Treatment |
|---------|------|-----------|-----|-----------|
| maintenance_workflows | HIDDEN | INCLUDED | INCLUDED | Hide nav when off |
| contractor_network | HIDDEN | LOCKED_UPSELL on job/issues | INCLUDED | Lock CTAs on Portfolio |
| tenant_portal | HIDDEN | HIDDEN | INCLUDED | Route gate |
| Issues `assign_contractor` | N/A | **EXECUTABLE_BUT_BLOCKED** | OK | Needs locked upsell |

---

## 4. Actionability governance

See `operations_actionability_governance_runtime.json`. Key CTAs:

- **Assign contractor (job hero)** — gated by `resolveHeroPrimaryExecution` + `contractor_network` ✓
- **Assign contractor (issues)** — **no frontend `contractor_network` check** ✗
- **Assign contractor (jobs list)** — hidden when `!contractor_network` ✓
- **Exports / tenant portal** — `plan_registry.enforce_feature` on API ✓

---

## 5. Browser / runtime proof

`operations_entitlement_browser_runtime.json` + `screenshots/`.

| Persona | Desktop highlights |
|---------|-------------------|
| **Professional** | Job `e670afc5…` loads; hero "Assign contractor"; modal opens; no upgrade alert; contractors route not gated |
| **Portfolio** | No open assign job in fixture; `/operations/contractors` shows entitlement gate (expected) |
| **Solo** | `/operations/issues` shows entitlement gate (expected) |

**Modal focus:** Professional desktop/mobile — `modal_focus_target: BUTTON` (not contractor select).

---

## 6. Enhancement recommendation (not implemented)

See `operations_entitlement_enhancement_plan.json`.

1. **Modal auto-focus** — focus select when contractors available; focus "Add contractor for this area" when none; mobile scrollIntoView.
2. **Non-entitled assign** — **Recommend locked CTA + upgrade/support modal** on Issues + job hero (not hide; not executable navigation).
3. **Nav rules** — keep hide-when-not-entitled; add locked upsell on near-workflow CTAs only.
4. **Backend** — add `CONTRACTOR_NETWORK` to `POST assign-contractor`; align `UpgradePrompt` min plan to `PLAN_3_PRO`.

---

## 7. Classification rationale

Not `VERIFIED_OPERATIONALLY` because:

- Issues page can show executable-looking assign navigation without `contractor_network`
- Modal does not auto-focus meaningful next control
- `POST assign-contractor` lacks network guard
- Upgrade copy says Portfolio for contractor network; ops default is Professional
- Sophie fixture plan drift on staging

---

## Artifacts

| File | Purpose |
|------|---------|
| `operations_entitlement_inventory_runtime.json` | Plan-feature matrix |
| `contractor_assignment_ux_audit_runtime.json` | Assignment scenarios |
| `locked_feature_strategy_runtime.json` | Locked vs hidden |
| `operations_actionability_governance_runtime.json` | CTA governance |
| `operations_entitlement_enhancement_plan.json` | Minimal safe plan |
| `operations_entitlement_browser_runtime.json` | Staging browser proof |
| `sessions_runtime.json` | API runtime entitlements (redacted) |
| `classifications.json` | Programme classification |
| `screenshots/` | Professional job detail captures |
