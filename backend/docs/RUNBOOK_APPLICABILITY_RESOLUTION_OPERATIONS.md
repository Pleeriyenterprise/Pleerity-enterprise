# Applicability Resolution Operations — Internal Runbook

Internal admin / ops only. **Not** a customer-facing API. All paths are tenant-scoped by `client_id` (and requirement/property as applicable).

---

## 1. Queue endpoint

| Item | Detail |
|------|--------|
| **Method / path** | `GET /api/admin/ops/clients/{client_id}/applicability-resolution-queue` |
| **Auth** | Admin route guard; no separate role gate beyond ops admin access for this router. |
| **Query params** | `limit` — integer, default `50`, range **1–100**; `cursor` — optional, pass **`next_cursor`** from the previous response (lexicographic pagination on `requirement_id`). |
| **404** | Returned if `client_id` does not exist in `clients`. |
| **Semantics** | Rows where **pipeline** applicability is **`UNKNOWN`** and impact is high (high-impact codes and/or mandatory + HIGH/CRITICAL policy criticality). Pagination is **bounded** by `limit`. |
| **Response highlights** | Per item: pipeline / effective / `applicability_resolution_source`, root-cause codes, operational fields (`priority_band`, `open_gap_count`, HIUA counts, `evidence_state`, `last_updated_at` / `age_seconds`, `recommended_next_action`), **`operator_action_wiring`** (POST template, per-command availability, **`resolution_reason_code_options`**). Envelope may include `queue_operational_scan_truncated` and `priority_band_order` when HIUA gap enumeration hits its cap. |

**Read-only:** this endpoint does not mutate data.

---

## 2. Operator command endpoint

| Item | Detail |
|------|--------|
| **Method / path** | `POST /api/admin/ops/clients/{client_id}/requirements/{requirement_id}/applicability-operator` |
| **Auth** | Admin route guard **and** **`require_owner_or_admin`**. |
| **Body (JSON)** | `command` — one of `MARK_REQUIRED`, `MARK_NOT_REQUIRED`, `REVOKE_OVERRIDE`; **`resolution_reason_code`** — required string (closed enum, see §3); **`notes`** — optional string. |
| **Actor** | Derived from the authenticated admin user (`type: user`, `id` from portal user id / id / sub). **400** if user id cannot be resolved. |
| **Errors** | **400** validation (command, reason code, actor); **404** requirement not found; message in `detail`. |

**Writes:** updates the **requirement** (provenance + flat mirrors + legacy `applicability_state` as implemented), runs **gap snapshot sync** for that requirement (`sync_compliance_gaps_for_requirement` with **`audit_lifecycle=False`** and **`run_operational_bridge=False`**), then appends **applicability resolution audit** (see §6).

---

## 3. Required reason codes (`resolution_reason_code`)

Must be **exactly** one of (case-insensitive input; stored normalised uppercase):

- `DATA_CORRECTION_PENDING`
- `DUPLICATE_REQUIREMENT`
- `HMO_CONFIRMED`
- `INSUFFICIENT_PROPERTY_METADATA`
- `JURISDICTION_REQUIRED`
- `MANUAL_LEGAL_REVIEW`
- `OTHER_GOVERNED`
- `PROPERTY_TYPE_EXEMPT`
- `REGISTRY_ERROR`

**All three commands** (`MARK_REQUIRED`, `MARK_NOT_REQUIRED`, `REVOKE_OVERRIDE`) require a valid `resolution_reason_code` on the POST body (validated before execute). Use **`notes`** only as supplementary context; justification must align with the chosen code.

Source of truth in code: `services/applicability_operator_resolution_reasons.py` (`APPLICABILITY_OPERATOR_REASON_CODES`).

---

## Decision Boundaries and Governance Rules

These rules sit **above** day-to-day API mechanics. They exist to keep **pipeline truth**, **provenance**, and **audit** trustworthy.

- **Overrides are exception handling, not a substitute for pipeline truth** — `MARK_REQUIRED` / `MARK_NOT_REQUIRED` change **effective** applicability and resolution **source**; they do **not** repair missing jurisdiction, property metadata, registry linkage, or provenance initialisation. Treat persistent **pipeline** `UNKNOWN` as a signal to fix upstream data, materialisation, or policy inputs—not to mask them with standing overrides.

- **Pattern of UNKNOWN across similar requirements → investigate root cause** — When many obligations show the same **pipeline** UNKNOWN pattern (same property, jurisdiction, code family, or tenant-wide provenance gap), run **root-cause and remediation** (queue `root_cause_codes`, `recommended_next_action`, provenance backfill, registry work). **Do not** use bulk operator overrides to clear queue volume without understanding the systemic defect.

- **Marks require operational context** — Use **`MARK_REQUIRED`** and **`MARK_NOT_REQUIRED`** only after reviewing **supporting context**: queue row, requirement + property fields, gap snapshot, and any relevant internal ticket or legal note. The **`resolution_reason_code`** must honestly reflect that review; **notes** should tie to traceable work (e.g. ticket id).

- **Revoke when pipeline truth is restored** — Once **pipeline** applicability and supporting data are corrected so **effective** outcomes should follow the pipeline again, **`REVOKE_OVERRIDE`** should be applied **where appropriate** so the tenant is not left on a permanent operator fork. Document the revoke in audit-linked follow-up.

- **Do not suppress operational noise without investigation** — HIUA, queue depth, or gap counts are **signals**, not nuisances to silence via overrides. Using overrides to “quiet” dashboards without confirming applicability facts erodes trust and breaks the link between **audit narrative** and **actual remediation**.

- **Preserve provenance and audit integrity** — Do not work around the system (manual Mongo edits to provenance/audit, forged reason codes, or vague `notes`). The **append-only** applicability resolution audit and structured reason codes exist for **compliance and incident reconstruction**; governance depends on them remaining accurate and complete.

---

## 4. Staging test workflow

Recommended order:

1. **Environment** — `MONGO_URL`, `DB_NAME` (e.g. staging). From repo root `backend/`, ensure Python path and env match the target cluster.
2. **Discover queue** — `GET` the queue for a known test `client_id`; pick a row with `pipeline_applicability_state: UNKNOWN` and desired `requirement_id` / property context.
3. **Baseline (optional)** — In Mongo or internal tools, note current `requirements` row: pipeline, effective, source, `operator_override_active`, and any open `compliance_gaps` for that `requirement_id`.
4. **Execute operator command** — `POST` with a valid `resolution_reason_code` and minimal `notes` (e.g. ticket id). Prefer **`MARK_REQUIRED`** or **`MARK_NOT_REQUIRED`** only on **disposable or clearly labelled test** requirements.
5. **Automated diagnostic (optional)** — From `backend/`:
   ```bash
   python -m scripts.diagnostic_operator_mark_required --client-id <CLIENT_ID> --requirement-id <REQUIREMENT_ID> --json
   ```
   - Read-only: omits **`--apply`** (use after you have already POSTed via API or another tool).
   - **Mutating:** `--apply` runs **`MARK_REQUIRED`** with a fixed service actor and reason `MANUAL_LEGAL_REVIEW` — **use only on throwaway staging rows**.
6. **Regression tests (CI / local)** — `pytest tests/test_applicability_operator_actions.py`, `tests/test_applicability_resolution_queue.py`, `tests/test_applicability_resolution_e2e.py` validate service behaviour with mocks / in-memory store.

---

## 5. Verification checklist (after `MARK_REQUIRED` / `MARK_NOT_REQUIRED`)

Use the queue + DB checks as appropriate:

| # | Check |
|---|--------|
| 1 | **Requirement** — `effective_applicability_state` matches command intent (`REQUIRED` / `NOT_REQUIRED`); **`pipeline_applicability_state` unchanged** by operator mark/revoke path (pipeline is snapshot-only for marks). |
| 2 | **Source** — For marks: **`applicability_resolution_source`** is **`OPERATOR_OVERRIDE`** when override is active and valid. After **`REVOKE_OVERRIDE`**: effective and source follow **pipeline** selector (see execute return / stored row). |
| 3 | **Legacy mirror** — Flat **`applicability_state`** aligned with effective as per PR4 `$set` behaviour. |
| 4 | **Open gaps** — For that `client_id` + `requirement_id`, open **`compliance_gaps`** documents show **`effective_applicability_state`** (and related snapshot fields) **consistent with the updated requirement** without waiting for a separate batch reconciliation job. |
| 5 | **Queue (if still pipeline UNKNOWN)** — Item may **remain** on the applicability resolution queue while pipeline is still UNKNOWN; read model should show **effective** + **source** reflecting operator override when active. |
| 6 | **API response** — POST returns `ok`, `command`, `pipeline_applicability_state`, `effective_applicability_state`, `applicability_resolution_source`. |

---

## 6. Audit verification

### 6.1 Applicability resolution audit (PR4 / operator)

| Item | Detail |
|------|--------|
| **Collection** | `applicability_resolution_audit` (constant `COLLECTION_NAME` in `applicability_resolution_audit.py`). |
| **Write** | **Append-only** `insert_one` per successful operator command (after requirement update and best-effort gap sync). |
| **Event types** | `OPERATOR_MARK_REQUIRED`, `OPERATOR_MARK_NOT_REQUIRED`, `OPERATOR_REVOKE_OVERRIDE`. |
| **Typical fields** | `client_id`, `property_id`, `requirement_id`, `event_type`, `pipeline_applicability_state`, `effective_applicability_state`, `applicability_resolution_source`, `actor`, `resolution_reason_code`, optional `notes`, `created_at`, `event_id`. |

**Verify:** query by `client_id`, `requirement_id`, sort `created_at` descending; confirm latest row matches the command just executed and matches the requirement read model at write time.

### 6.2 Gap lifecycle audit (`audit_logs`)

Operator-driven gap sync uses **`audit_lifecycle=False`**, so **COMPLIANCE_GAP_OPENED / COMPLIANCE_GAP_RESOLVED** should **not** be emitted from that path. **`run_operational_bridge=False`** avoids new **COMPLIANCE_GAP_ISSUE_CREATED** / maintenance issue side-effects from this path.

**Caveat:** other jobs or evidence flows may still write `COMPLIANCE_GAP_*` entries for the same tenant or requirement — correlate by **timestamp** and **metadata** / `resource_id`, not assumption of silence.

---

## 7. HIUA verification

| Item | Detail |
|------|--------|
| **Definition** | HIUA is a **read-time** signal on **persisted open `compliance_gaps`**, via `derive_hiua_signal_for_open_gap` in `hiua_operational_uncertainty.py`. It does **not** change scoring predicates. |
| **After operator mark** | Once gap snapshots carry **effective applicability** consistent with the requirement (post `sync_compliance_gaps_for_requirement`), HIUA should **drop** for gaps that previously tripped only on UNKNOWN effective applicability. |
| **Queue / tenant summaries** | Queue items expose `hiua_active`, `hiua_open_gap_count`; tenant-wide scans use bounded gap reads elsewhere (e.g. `hiua_tenant_operational_summary`). |
| **Truncation** | Queue response may set `queue_operational_scan_truncated` when HIUA enumeration hits the configured cap — HIUA counts on the page can be incomplete under extreme gap volume. |

**Verify:** for the target `requirement_id`, inspect open gaps and/or queue item HIUA fields; re-run queue page after POST if needed.

---

## 8. Revoke override workflow

| Step | Action |
|------|--------|
| 1 | Confirm **`operator_override_active`** (or nested provenance) shows an **active** override on the requirement. |
| 2 | **`POST`** with `command: REVOKE_OVERRIDE` and a valid **`resolution_reason_code`**. |
| 3 | **Expect** — Override cleared; **effective** applicability and **`applicability_resolution_source`** revert to **pipeline**-derived values; legacy `applicability_state` updated to match effective. **Pipeline** snapshot unchanged by revoke. |
| 4 | **Gaps** — Gap snapshot sync runs again (quiet mode); open gaps should reflect **post-revoke** effective applicability. |
| 5 | **Audit** — New row with `event_type: OPERATOR_REVOKE_OVERRIDE`. |
| 6 | **Queue** — If pipeline remains UNKNOWN and impact rules still match, the requirement can **remain** on the applicability resolution queue with **source PIPELINE** again. |

**Note:** `REVOKE_OVERRIDE` does not embed operator override metadata on the provenance block the same way as mark commands; reason code is still required for the audit trail.

---

## 9. Warnings about production use

- **Owner/Admin only** on the operator POST — treat as **high-impact** configuration; every successful command is **audited** with actor identity.
- **Legal / policy** — Operator commands encode **operational** resolution of applicability ambiguity; they do **not** replace registry or legal sign-off. Use **`MANUAL_LEGAL_REVIEW`** (or other codes) **accurately**.
- **Customer impact** — Effective applicability drives downstream compliance behaviour; **wrong** `MARK_REQUIRED` / `MARK_NOT_REQUIRED` can change obligation treatment for a tenant.
- **No silent rollback** — Mistakes require a **follow-up** command (e.g. revoke + pipeline fix, or a new mark with a correct reason code and notes).
- **Gap sync failures** — Requirement update **commits** even if gap sync logs warnings; see §10. **Stale HIUA** is possible until sync succeeds or is retried manually (re-run evidence sync / gap sync paths if operational procedures allow).

---

## 10. Known limitations and retry / failure cases

| Scenario | Behaviour |
|----------|-----------|
| **Invalid `resolution_reason_code`** | **400**; no DB writes. |
| **Requirement not found** | **404**; no DB writes. |
| **Post-update `find_one` returns nothing** | Logged warning; **gap sync skipped**; applicability resolution audit **still appended**; requirement row may still be updated from prior `update_one`. Investigate replication / filter mismatch. |
| **`sync_compliance_gaps_for_requirement` returns `errors`** | Logged warning only; operator audit still written. Inspect `errors` in logs; may need ops follow-up (evidence authority, property doc, runtime eligibility). |
| **`sync_compliance_gaps_for_requirement` raises** | Caught and logged; audit still written. |
| **Runtime surface exclusion** | If `requirement_row_eligible_on_client_runtime_surfaces` is false for the refreshed row, sync may **resolve** open gaps as `runtime_excluded` — **pre-existing** sync semantics; understand tenant/property visibility before marking. |
| **HIUA cap on queue page** | `queue_operational_scan_truncated: true` → HIUA counts may be **lower bounds**; use tenant HIUA summary or direct gap queries for investigations. |
| **Concurrent updates** | Last writer wins on `requirements`; coordinate with other operators/materialization jobs. |
| **Retry** | Safe to **re-read** queue and requirement after a failure response; idempotent **re-mark** may be acceptable if business rules allow (audit will show multiple events). |

---

## 11. Quick reference — HTTP

```http
GET /api/admin/ops/clients/{client_id}/applicability-resolution-queue?limit=50&cursor=
POST /api/admin/ops/clients/{client_id}/requirements/{requirement_id}/applicability-operator
Content-Type: application/json

{"command":"MARK_REQUIRED","resolution_reason_code":"MANUAL_LEGAL_REVIEW","notes":"OPS-1234 optional"}
```

---

## 12. Related code and docs

- Operator execute: `services/applicability_operator_actions.py`
- Reason codes: `services/applicability_operator_resolution_reasons.py`
- Queue: `services/applicability_resolution_queue.py`
- Applicability audit: `services/applicability_resolution_audit.py`
- Gap sync: `services/compliance_gap_sync.py`
- Staging diagnostic script: `scripts/diagnostic_operator_mark_required.py`
- Provenance / operator overview: `docs/APPLICABILITY_PROVENANCE_LEGACY_APPLICABILITY_STATE.md` (if present in tree)

---

*Document version: aligned with backend services as of internal ops + PR4 gap sync follow-up. For enum or field changes, update this runbook when code changes.*
