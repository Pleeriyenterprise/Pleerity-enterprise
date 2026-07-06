# ILP-7 Kickoff Audit — API Lifecycle Responses

**Programme (implementation track):** ILP-7-API-LIFECYCLE-RESPONSES-01  
**Governance mapping:** ALPA / Runtime Contract **ILP-6 API Responses** (governance numbering)  
**Branch:** `develop`  
**Prerequisite:** ILP-4 capability enforcement, ILP-5 session runtime, ILP-6 background runtime — **complete**

---

## Objective

Make API denial and recovery responses lifecycle-aware using the Runtime Contract. Frontend and integrations must receive **safe string messages**, **`lifecycle_redirect`**, and **`runtime_version`** on governed denials — never raw entitlement fields or unstructured `detail`.

---

## Current state (audit)

### Already implemented (ILP-4 partial)

| Item | Location | Gap |
|------|----------|-----|
| `capability_denied` payload | `middleware/capability_gating.py` | Uses `recovery.route` not `lifecycle_redirect` |
| `runtime_version` in 403 | `capability_denied_http_detail()` | ✓ present |
| `lifecycle_state`, `portal_mode` | same | ✓ present |
| CAP_* route dependencies | `client_require_capability`, `require_capability` | ✓ on Wave 1–4 routes |
| Read-tier recovery APIs | `routes/client_read_api.py` | Partial — billing recovery reads |

### Not yet governed

| Area | Current behaviour | Required |
|------|-------------------|----------|
| `lifecycle_redirect` field | Missing; `recovery.route` only | Add canonical `lifecycle_redirect` per schema |
| Non-capability 403 paths | Mixed legacy messages | Normalize via central builder |
| Frontend `parseApiError` | May not consume `lifecycle_redirect` | Align consumer (if in scope) |
| Plan deny vs lifecycle deny | Partially unified | Distinct `error_code` + same safe shape |
| Response headers | Session runtime headers (ILP-5) | Add runtime version on capability deny responses |

---

## Governance inputs

- `ACCOUNT_RUNTIME_SCHEMA.md` — 403 shape
- `ACCOUNT_LIFECYCLE_RUNTIME_CONTRACT.md` — mutation deny contract
- `ACCOUNT_API_CAPABILITY_MATRIX.md` — failure behaviour
- `ACCOUNT_CUSTOMER_EXPERIENCE_AUTHORITY.md` — recovery CTAs → redirect routes

---

## Proposed deliverables

1. **`account_api_lifecycle_response_authority.py`** (or extend `capability_gating`) — single builder for governed API denial payloads including `lifecycle_redirect`.
2. **Migrate all capability denial paths** to the central builder (middleware + inline route checks).
3. **Read-tier recovery API audit** — ensure billing/read routes available in `BILLING_RECOVERY`, `SUSPENDED`, `READ_ONLY` per policy.
4. **Targeted tests** — lifecycle states → 403 payload shape; no regression suite until programme gate.
5. **ILP-7 evidence/report** under `backend/docs/audit/account_lifecycle_ilp_07/`.

---

## Out of scope (ILP-7)

- Billing / Stripe changes
- Runtime Contract schema changes (unless blocker)
- Background job policy (ILP-6)
- Session invalidation flows (ILP-5)
- Full backend regression until final programme gate

---

## Testing policy

Same as ILP-5/6: targeted tests only during implementation; full regression at final production-critical ILP gate.

---

## Status

**AUDIT COMPLETE — awaiting implementation approval to begin code changes.**
