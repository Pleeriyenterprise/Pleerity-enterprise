# Stream D — CTA producer / consumer matrix (read-only audit)

**Purpose:** Inventory of **client- and admin-facing action producers and consumers** for closed-loop **CTA contract integrity**. This document is **governance only**; it does not change runtime behaviour or copy.

**Companion:** `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` (Stream D), `CLOSED_LOOP_ARCHITECTURAL_GAP_ANALYSIS.md` §3–5 (CTA / routing).

**Named authorities (programme):**

| Concern | Authority |
|--------|-----------|
| Requirement-backed primary CTAs | `services/requirement_action_resolver.py` — `resolve_take_action_envelope`, `resolve_take_action_for_priority_action`, `take_action` contract (`requirement_take_action_v1`). |
| Parity (same contract, different runtime) | **`STREAM_D_CTA_PARITY_ENFORCEMENT.md`** + `tests/fixtures/cta_parity_fixtures.py` + `tests/test_cta_parity_contract.py` (backend freeze); **`frontend/src/utils/requirementTakeActionResolver.js`** (+ tests); optional future FE CI gate per enforcement doc §6. |
| Risk signal **copy** and suggested action codes | `services/risk_signal_service.py` (`RECOMMENDED_ACTIONS`, `SUGGESTED_ACTION_*`). |
| Risk / operations **navigation URL** (not resolver) | Constructed pattern `/operations/risk-signals?signal_id=…` in `client_priority_stream`, `command_center_service._slim_risk`. |

**Risk rating (matrix column):**

| Rating | Meaning |
|--------|---------|
| **High** | User-visible path can diverge from `take_action`, show dead/misleading URLs, or duplicate obligation CTAs vs gap fields. |
| **Medium** | Intentional non-resolver pattern but must stay consistent across surfaces; or admin-only with ops impact. |
| **Low** | Supporting links, digest-only, or clearly labelled non-workflow visibility actions. |

**Language classes (matrix column):** Whether the surface can present **Book**-style (e.g. gas engineer), **Fix** / remediation, **Start maintenance** / WO-centric, or **generic** (View / Review / Open) copy — inferred from module strings and resolver intents, not a guarantee of exact UI string.

---

## 1. Backend producers (labels + URLs)

| ID | Source module | Role | Action label source | Route / URL source | BE / FE authority | Maps to real workflow? | Book / Fix / maint / generic | Bypasses `take_action`? | Client / admin / diagnostic | Risk | Notes |
|----|----------------|------|----------------------|--------------------|-------------------|-------------------------|------------------------------|---------------------------|------------------------------|------|-------|
| D-P01 | `services/requirement_action_resolver.py` | Canonical **requirement** `take_action` envelope | Engine + requirement row + `presentation.label_service.requirement_label`; registry `cta_label_override` | Resolver-built internal routes (`/documents?…`, guided/direct handlers, maintenance path, obligation copy) | **Backend** (contract); **frontend mirrors** resolver JS | Yes (upload, guided evidence, jobs, maintenance, external) | All classes per `action_type` / evidence mode | **No** — this *is* `take_action` | Client (via API payloads) | **High** if FE drifts | JOB envelope intentionally limited vs multi-mode guided evidence (module docstring). `INTENT_BOOK_INSPECTION` aliases coordinated inspection evidence. |
| D-P02 | `services/requirement_action_links.py` | **Supporting** external links (not primary CTA) | `presentation/requirements_action_links.json` + registry overrides | `format_client_external_link` → outbound URLs | **Backend** + static JSON | External registry links | Generic + jurisdiction-specific | N/A (secondary) | Client | **Low** | Primary CTA remains resolver; links capped (`_MAX_CLIENT_LINKS`). |
| D-P03 | `services/compliance_gap_engine.py` | Gap rows: `recommended_url`, `recommended_action_label` | Per-gap templates in engine (e.g. “Upload document”, “Review compliance”, property-scoped `/documents?…`) | Same templates + `req_url` helpers | **Backend** | Partial — points to real surfaces but **not** sole authority for requirement-primary CTA | Generic + upload-style | **Yes** at raw gap object; **`gaps_to_priority_actions`** overlays `take_action.primary` when present | Mixed: raw gap **diagnostic**; enriched row **client** after overlay | **High** without overlay; **Medium** after `gaps_to_priority_actions` | Sets `diagnostic_gap_recommended_*`, `recommended_client_authority` = `canonical_take_action` when `take_action` present. **Rule R2:** do not use raw gap `recommended_*` for requirement-primary CTAs when resolver should win. |
| D-P04 | `services/compliance_gap_engine.gaps_to_priority_actions` | Bridge gap → priority-action dict | After overlay: label/route from `take_action.primary`; else gap template | Same | **Backend** | Yes when aligned to `take_action` | Inherits D-P03 / D-P01 | **No** when `take_action` present | Client (via stream) | **Medium** | Single choke point between gap engine and priority stream. |
| D-P05 | `services/client_priority_stream.py` | **Priority action list** for portal | Compliance: from D-P04; risk: `risk_signal_service` fields + fixed label “Review risk signal”; WO/issue/approval: `label_service` + literals | Risk: **`/operations/risk-signals?signal_id=`** constructed here; WO/issue/approval: operations paths | **Backend** | Yes for ops entities; risk is **review/dismiss** workflow not resolver | Risk copy can imply **Book**/inspect (from `RECOMMENDED_ACTIONS` text); WO **maint**; compliance inherits resolver | **Yes** for risk, WO, approval, issue (by design — not requirement resolver) | Client | **Medium** (risk URL duplicated with CC) | Exceptions: intentional **non-resolver** URLs per tracker. |
| D-P06 | `services/unified_tasks_service.py` | Unified task DTOs: `primary_action_*`, `metadata.take_action` | Requirement overdue/missing/cert: **`resolve_take_action_for_priority_action`** + optional `canonical_take_action` / `resolve_take_action_envelope` fallback; other types: literals / `_primary_action_fields` branch; **`_tenant_request_tasks`** (2026-04-30) attaches **`metadata.take_action`** from resolver when IDs present — **`primary_action_*` for tenant_request remain** hardcoded upload/doc URL; mismatch **`logger.warning`** (`op=tenant_request_cta`) if canonical ≠ standard document navigate | Resolver output or constructed ops URLs from priority row | **Backend** | Yes | Mixed | **Partial** — non-requirement types never use resolver; tenant_request primary still hardcoded | Client | **High** for requirement rows; **Medium** for others | `_primary_action_fields` B1/B2 gap alignment; `test_unified_tasks_tenant_request_cta` for B3 metadata + mismatch log. |
| D-P07 | `services/today_projection_service.py` | Today **`business_actions`** vs visibility | Uses unified task + `resolve_take_action_envelope` contract for requirement-backed cards | From unified task / resolver | **Backend** | Yes (domain CTAs only in business_actions) | Inherits unified | **No** when `metadata.take_action` present | Client | **Medium** | Visibility actions (snooze/dismiss/reviewed) **do not** complete compliance — documented in module docstring. |
| D-P08 | `services/command_center_service.py` | Slim urgent tasks + risk block | Tasks: pass-through `primary_action_*` from unified; risk: `_slim_risk` uses signal fields + **constructed** `cta_url` | `_slim_risk`: `/operations/risk-signals?signal_id=` | **Backend** | Snapshot / navigation | Generic “follow up” | **Yes** for risk CTA URL (intentional) | Client | **Medium** | Partial bundle on subgraph `try/except` — tracker risk. |
| D-P09 | `services/risk_signal_service.py` | Persisted / computed risk signals | `RECOMMENDED_ACTIONS` per `RISK_TYPE_*` (+ client-facing label helpers) | **Not** primary URL authority — URL built in D-P05/D-P08 | **Backend** | Informational + suggested action **codes** | **Book**/inspect language common | **Yes** (separate CTA system) | Client + admin consumers | **Medium** | `recommended_action_client` / `recommended_action` feed copy; **Book a qualified gas engineer**-class strings. |
| D-P10 | `services/requirement_truth.py` | Enrich requirement rows for client | Delegates to resolver for `take_action` | Resolver | **Backend** | Yes | Inherits D-P01 | **No** | Client | **High** | Attachment point for catalog / detail APIs. |
| D-P11 | `services/requirement_client_runtime_surface.py` | Runtime projection `cta_label`, `cta_url`, `cta_action_mode` | From row `take_action.primary` | Same | **Backend** | Yes | Inherits D-P01 | **No** | Client | **Medium** | Hidden primary mode suppresses CTA. |
| D-P12 | `services/catalog_compliance.py` | Portfolio / catalog rows expose `take_action`, `primary_action_intent` | Resolver via enriched row | Resolver | **Backend** | Yes | Inherits D-P01 | **No** | Client | **Medium** | Matrix/catalog consumers should prefer these fields over gap-only. |
| D-P13 | `services/monthly_digest_assembly_service.py` | Email digest deep links | Unified task `primary_action_type` / URL | From digest task builder | **Backend** | Yes | Inherits unified | Depends on digest task source | Client (email) | **Medium** | Uses `_abs_url` with task primary URL. |
| D-P14 | `services/priority_actions.py` | **Admin** priority stream | Hard-coded titles + `/admin/…` URLs | Literal admin routes | **Backend** | Yes (admin ops) | Generic “View …” | **Yes** (no client `take_action`) | **Admin** | **Low** for client contract | Separate product surface; not governed by client resolver. |
| D-P15 | `routes/ops_compliance.py` | Exposes `get_priority_actions_for_admin` | D-P14 | D-P14 | **Backend** | Yes | Admin generic | **Yes** | **Admin** | **Low** | Diagnostic / ops dashboard consumer in Admin SPA. |

---

## 2. Frontend consumers (rendering and navigation)

| ID | Surface (file) | API / data source | Label / route authority | Maps to workflow? | Book / Fix / maint / generic | Bypasses `take_action`? | Client / admin | Risk | Notes |
|----|----------------|-------------------|-------------------------|-------------------|------------------------------|-------------------------|----------------|------|-------|
| D-C01 | **Today** — `frontend/src/pages/ClientTasksPage.js` | `GET /today/items` → unified + `today_projection_service` | **`business_actions`** from server; primary navigation via `resolveTaskCta` (`ctaRegistry.js`) + `requirementTakeActionResolver.resolveInboxTaskTakeActionRoute` | Yes | Mixed | **No** when `metadata.take_action` present | Client | **Medium** | Docstring: operational priorities, not score truth. Visibility actions are inbox-only. |
| D-C02 | **Command Centre** — `frontend/src/pages/ClientCommandCenterPage.js` | `GET /client/command-center` → `command_center_service` | `primary_cta` / `primary_action_url` / `cta_url` from slim task; label sanitization `sanitizeCommandCenterCtaLabel` | Snapshot → execution still in Today / ops | Generic + inherited | Risk rows: **yes** (non-resolver URL pattern) | Client | **Medium** | `RequirementIntelligenceModal` for requirement-backed rows. |
| D-C03 | **Command Centre helpers** — `frontend/src/utils/clientCommandCenter.js` | Same bundle | Prefers `metadata.take_action.primary.label` then `primary_action_label` | N/A | Generic | Resolver-preferred when metadata present | Client | **Medium** | Synthesis copy references Today. |
| D-C04 | **Property Detail** — `frontend/src/pages/PropertyDetailPage.js` | Requirements from client APIs (enriched) | **`resolveRequirementAction`** (`requirementTakeActionResolver.js`) | Yes | Full resolver handler set (guided, external, navigate) | **No** when API sends `take_action` | Client | **High** | Multiple compliance tables; tests `PropertyDetailPage.complianceActions.test.js`. |
| D-C05 | **Requirement Intelligence Modal** — `frontend/src/components/client/RequirementIntelligenceModal.js` | `getRequirementWorkflow` + `seedRequirement` | **`resolveRequirementAction(merged)`** | Yes | Inherits resolver | **No** when merged payload includes `take_action` | Client | **High** | Same FE resolver as Property Detail; merge via `requirementIntelligenceMerge`. |
| D-C06 | **Client Dashboard** — `frontend/src/pages/ClientDashboard.js` | Today inbox + Command Centre widgets | Delegates to same task / CC shapes | Partial | Generic CTAs in widgets | Same as D-C01/D-C02 | Client | **Medium** | KPI vs inbox boundaries documented in dashboard copy. |
| D-C07 | **Compliance score** — `frontend/src/pages/ComplianceScorePage.js` | `/client/compliance-score` + requirements | **Synthetic** `navigateDriverAction` builds `primary_action_url` until drivers hydrated with `take_action` (TODO in file) | Partial | Document-first UPLOAD/VIEW | **Yes** — explicit bypass until hydration | Client | **High** | Tracked technical debt; uses `resolveTaskCta` on synthetic task. |
| D-C08 | **Client risk signals** — `frontend/src/pages/ClientRiskSignalsPage.js` | Risk API | Signal `recommended_action` **text** + separate navigation to WO/issue flows | Partial | **Book**/inspect from backend strings | **Yes** (not `take_action`) | Client | **Medium** | Aligns with D-P09 / operations CTA pattern. |
| D-C09 | **CTA registry** — `frontend/src/utils/ctaRegistry.js` | Unified task shape | Combines **`resolveInboxTaskTakeActionRoute`** with `buildEntityRoute` fallback | Yes | Registry per `source_type` + `action_type` | Fallback can use `primary_action_url` from server | Client | **Medium** | Single client-router for Today-style tasks. |
| D-C10 | **Admin Dashboard** priority table — `frontend/src/pages/AdminDashboard.js` | Admin priority actions API | `recommended_action_label` + `recommended_url` from **admin** producer | Yes | Admin generic | **Yes** | **Admin** | **Low** | Client CTA contract does not apply. |
| D-C11 | **Property Operating Hub** — `frontend/src/components/property/PropertyOperatingHub.jsx` | Risk / signals | `recommended_action` display + WO creation from description | Partial | Maint / risk | **Yes** | Client | **Medium** | Uses human-readable risk copy. |
| D-C12 | **Compliance obligation present** — `frontend/src/utils/complianceObligationPresent.js` | Local merge | **`recommended_action_text`** synthesized (“Next step: …”) | Informational | Generic | **Yes** (not resolver) | Client | **Low–Medium** | Explain copy; not primary navigation authority. |

---

## 3. Intentional non-`take_action` URL patterns (exception table)

| Pattern | Where produced | Rationale | Owner (conceptual) |
|---------|----------------|-----------|---------------------|
| `/operations/risk-signals?signal_id=<id>` | `client_priority_stream`, `command_center_service._slim_risk` | Risk is **not** a requirement; separate navigation contract per tracker | Stream D — risk CTA authority |
| `/operations/work-orders?work_order_id=<id>` | `client_priority_stream` | Work order deep link | Ops / maintenance |
| `/operations/approvals?invoice_id=<id>` | `client_priority_stream` | Invoice approval | Ops |
| `/operations/issues/<id>` | `client_priority_stream` | Issue triage | Ops |
| `/admin/…` | `priority_actions.py` | Admin-only surfaces | Admin ops |

---

## 4. Gap field `recommended_*` vs resolver (duplicate-truth class)

| Stage | Behaviour | Risk mitigations already in repo |
|-------|-----------|-----------------------------------|
| Raw `ComplianceGap` | Always carries template `recommended_url` / `recommended_action_label` | Documented as diagnostic in `gaps_to_priority_actions` (`diagnostic_gap_*`, `recommended_client_authority`) |
| Priority action row | Overwritten when `take_action.primary` has `route` / `label` | `canonical_take_action` attached for downstream |
| `unified_tasks_service._primary_action_fields` | Resolver + `canonical_take_action` override gap fallbacks for requirement compliance action types | `test_today_requirement_cta_authority` |
| **`gaps_to_priority_actions` + `_primary_action_fields` (2026-04-30, Stream D phase 2 first slice)** | When `take_action.primary` / `canonical_take_action.primary` exists, **raw gap `recommended_url` is not** used as the client primary URL if the resolver route is absent; canonical label wins over gap label when canonical envelope is present | `test_compliance_gap_engine_governed`, `test_today_requirement_cta_authority` |

**Residual risk:** Any **new** consumer that reads **Mongo `compliance_gaps`** or legacy gap payloads **directly** (bypassing unified tasks / resolver enrichment) can reintroduce **Rule R2** violations.

---

## 5. Cross-surface summary

- **Single client contract for requirement obligations:** `take_action` from **`requirement_action_resolver`** (backend) with **mandatory parity** to **`requirementTakeActionResolver.js`** (frontend).
- **Today + Command Centre urgent tasks:** ultimately fed by **`client_priority_stream`** → **`unified_tasks_service`**; requirement compliance types **must** go through resolver path in `_primary_action_fields`.
- **Risk:** copy from **`risk_signal_service`**; URL from **constructed operations pattern** — do not route risk through requirement resolver.
- **Admin priority stream:** separate system (`priority_actions`) — does not use client `take_action`.
- **Known bypass / debt:** **Compliance score drivers** (D-C07) until hydrated with canonical `take_action`.

---

## 6. Tests (anchors)

- `backend/tests/test_today_requirement_cta_authority.py` — Today / unified primary vs gap `recommended_*`.
- `backend/tests/test_requirement_action_resolver.py` — resolver envelope.
- `backend/tests/test_compliance_authority_alignment.py`, `test_catalog_compliance_take_action_matrix.py` — catalog / matrix alignment.
- `backend/tests/fixtures/cta_parity_fixtures.py` + `backend/tests/test_cta_parity_contract.py` — **Stream D Phase 4** deterministic parity cases (`P01`–`P10`); see `STREAM_D_CTA_PARITY_ENFORCEMENT.md`.
- `frontend/src/utils/requirementTakeActionResolver.test.js` — frontend parity coverage.

---

## 7. Recommended follow-ups (implementation — out of scope for this matrix)

See tracker **Stream D — implementation phases**: phase 2 (backend gap guardrails), phase 3 (resolver URL validation), phase 4 (parity enforcement — **backend slice** shipped; optional FE CI gate).
