# Books Webhook Consistency Report

**Programme:** ZOHO AUTOMATED INTEGRATION IMPLEMENTATION  
**Document type:** Implementation review and hardening decision record  
**Date:** 2026-07-09  
**Status:** **Option B implemented**

---

## 1. Problem statement

The environment variable matrix review identified an architectural inconsistency:

| Layer | Stated behaviour |
|-------|------------------|
| **Documentation** (`ZOHO_WEBHOOK_POLICY.md`) | All webhook endpoints use HMAC-SHA256 via `X-Zoho-Signature`; secret resolution `ZOHO_{INTEGRATION}_WEBHOOK_SECRET` → `ZOHO_WEBHOOK_SECRET` |
| **Implementation (Sign, Campaigns, CRM)** | HMAC verified before handler logic |
| **Implementation (Books)** | Route returned rejection **without** HMAC verification |

Additionally, `ZOHO_BOOKS_WEBHOOK_SECRET` was implied by the generic pattern but not documented in `zoho_integration.env.example` and not consumed by code.

---

## 2. Review scope

| File | Role |
|------|------|
| `routes/integrations/zoho/webhooks.py` | Webhook route definitions |
| `services/integrations/zoho/webhooks/handlers.py` | Inbound handler logic |
| `services/integrations/zoho/webhooks/verifier.py` | HMAC verification |
| `services/integrations/zoho/config.py` | `zoho_webhook_secret(integration)` |
| `services/integrations/zoho/adapters/books.py` | Books authority boundary (`inbound_rejected`) |
| `docs/zoho_integration.env.example` | Env var reference |
| `ZOHO_WEBHOOK_POLICY.md` | Webhook security policy |

**Out of scope:** OAuth, feature flags, Render configuration, scheduler cron, outbound Books export.

---

## 3. Option evaluation

### Option A — Keep current implementation (document-only fix)

| Variant | Assessment |
|---------|------------|
| **Remain as-is** | **Rejected.** When `ZOHO_INTEGRATION_ENABLED=true`, unauthenticated callers could POST to `/webhooks/books` and receive a structured rejection, confirming endpoint existence. Other integrations require HMAC first. Weakens defence-in-depth. |
| **Remove route** | **Rejected.** Endpoint is registered in sandbox readiness docs for Zoho Books webhook URL registration. Removal would require re-adding later and does not improve consistency with CRM (which also always rejects but retains verified endpoint). |
| **Document-only correction** | **Insufficient.** Would leave security model inconsistent and leave `ZOHO_BOOKS_WEBHOOK_SECRET` undocumented/unused. |

### Option B — Consistent HMAC verification (selected)

| Criterion | Assessment |
|-----------|------------|
| Architectural consistency | Aligns Books with CRM reject-only pattern: verify → reject |
| Security | **Strengthens** — no unauthenticated access when integration layer enabled |
| Complexity | Minimal — reuses existing `verify_zoho_webhook_signature` and `zoho_webhook_secret("books")` |
| SoR boundaries | Unchanged — all inbound Books operations still rejected |
| Feature flags | Unchanged — no flags enabled |
| Future value | Endpoint can be registered in Zoho Books sandbox without later security retrofit |

**Decision: Option B.**

---

## 4. Implementation summary

### 4.1 Route (`webhooks.py`)

Books webhook now mirrors CRM:

1. `_guard()` — 404 when `ZOHO_INTEGRATION_ENABLED=false`
2. Read raw body
3. `verify_zoho_webhook_signature(raw, X-Zoho-Signature, zoho_webhook_secret("books"))`
4. Parse JSON payload
5. Call `reject_books_inbound(payload)`

Secret resolution (unchanged in `config.py`):

```
ZOHO_BOOKS_WEBHOOK_SECRET → ZOHO_WEBHOOK_SECRET → "" (401 if empty)
```

### 4.2 Handler (`handlers.py`)

`reject_books_inbound` aligned with `reject_crm_inbound`:

- Calls `ZohoBooksAdapter.execute("inbound_rejected", …)` directly (authority boundary)
- Logs `log_zoho_webhook_event(integration="books", event_type="inbound_rejected", …)`
- Does **not** route through `zoho_integration_service.run_sync` (which incorrectly required `ZOHO_BOOKS_SYNC_ENABLED=true` to reach adapter logic)

**Response (unchanged contract):**

```json
{
  "accepted": false,
  "reason": "books_inbound_forbidden",
  "message": "books_inbound_writes_forbidden"
}
```

### 4.3 Documentation and env reference

| Artifact | Change |
|----------|--------|
| `zoho_integration.env.example` | Added `ZOHO_BOOKS_WEBHOOK_SECRET` |
| `ZOHO_WEBHOOK_POLICY.md` | Explicit Books HMAC requirement; per-integration secret table |
| `ZOHO_SANDBOX_READINESS_REPORT.md` | Added Books webhook secret to secrets table; clarified HMAC applies to all four endpoints |

---

## 5. Authority and SoR confirmation

| Requirement | Status |
|-------------|--------|
| Pleerity remains authoritative platform | ✓ No inbound Books writes |
| Books cannot create or modify customer data | ✓ Always rejected |
| Books cannot modify billing authority | ✓ Stripe/Pleerity SoR unchanged |
| Books cannot trigger customer lifecycle changes | ✓ No DB mutations on Books webhook |
| Webhook behaviour fully documented | ✓ Policy + sandbox readiness updated |
| Documentation matches implementation | ✓ |
| No undocumented env vars | ✓ `ZOHO_BOOKS_WEBHOOK_SECRET` now in env example |

---

## 6. Webhook security model (post-hardening)

All four endpoints share one model:

```
Request → flag guard (404 if disabled)
       → HMAC verify (401 if secret missing or signature invalid)
       → handler (allowed action OR authority rejection)
```

| Endpoint | Post-verification behaviour |
|----------|----------------------------|
| Sign | Process completion when `ZOHO_SIGN_SYNC_ENABLED=true` |
| Campaigns | Unsubscribe when Campaigns flags on |
| CRM | **Always rejected** (`crm_inbound_forbidden`) |
| Books | **Always rejected** (`books_inbound_forbidden`) |

**Books inbound is intentionally unsupported as a write path.** The endpoint exists for webhook registration consistency and verified rejection of any Zoho Books push events. Outbound Books export remains a separate, flag-gated sync operation (`ZOHO_BOOKS_SYNC_ENABLED`).

---

## 7. Operational notes

- **No Render secrets added** as part of this change.
- **No feature flags enabled.**
- When Books webhook is registered in Zoho sandbox (Programme B / later), set `ZOHO_BOOKS_WEBHOOK_SECRET` or shared `ZOHO_WEBHOOK_SECRET` in Render staging only.
- Until integration layer is enabled, all webhook routes return **404** (stealth mode unchanged).

---

## 8. Test evidence

See `REGRESSION_TEST_RESULTS.md` (Books webhook section). New tests:

- `test_books_webhook_requires_hmac_when_enabled` — 401 without signature
- `test_books_webhook_verifies_and_rejects_inbound` — 200 with valid HMAC, `books_inbound_forbidden`
- `test_webhook_routes_404_when_disabled` — extended to cover Books route

---

## 9. Conclusion

Option B delivers a single consistent webhook security model across Sign, Campaigns, CRM, and Books. Books inbound remains permanently rejected; HMAC verification is now mandatory before rejection, matching CRM. Documentation and implementation fully agree. No ambiguity remains regarding Books inbound support status: **intentionally rejected after verified delivery; never a System of Record write path.**
