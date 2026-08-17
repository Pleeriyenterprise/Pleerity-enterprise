# Zoho OAuth Sandbox Validation (Stage O3)

**Programme:** ZOHO OAUTH ARCHITECTURE VALIDATION  
**Date:** 2026-07-10  
**Status:** **NOT EXECUTED** — blocked on absence of sandbox OAuth credentials in validation environment

---

## 1. Purpose

Empirically determine whether Pleerity's single-token OAuth model:

1. Successfully mints a refresh token with multi-app scopes, and/or
2. Successfully calls APIs across multiple Zoho products with one access token.

---

## 2. Why sandbox testing was not performed

| Constraint | Status |
|------------|--------|
| No `ZOHO_CLIENT_ID` / `ZOHO_CLIENT_SECRET` / `ZOHO_REFRESH_TOKEN` in agent validation environment | Confirmed — analysis-only exercise |
| Staging Render has no OAuth secrets (Phase A not started) | Confirmed per post-`af0b74fd` verification |
| User constraint: no production credentials | Observed |
| User constraint: no integration flags enabled | Observed |
| User constraint: do not modify staging/production config | Observed |

**No live OAuth calls were made.** Findings in this document are **protocol and checklist only**.

---

## 3. Validation protocol (execute before Phase B+)

Execute in **Zoho EU sandbox** with a **Self Client** registered at `https://api-console.zoho.eu`. Record results in a follow-up amendment to this document.

### Test T1 — Multi-app scope string at Generate Code

**Objective:** Does Zoho permit one authorization code with scopes spanning multiple business apps?

**Procedure:**

1. Open Self Client → Generate Code.
2. Enter comma-separated multi-app scope string (no spaces):

```
ZohoCRM.modules.leads.CREATE,ZohoCRM.modules.leads.UPDATE,ZohoAnalytics.data.create,ZohoBooks.accountants.CREATE,ZohoCampaigns.contact.CREATE-UPDATE,WorkDrive.files.CREATE
```

3. Click CREATE. Record UI outcome.

**Pass criteria for single-token model:** Authorization code generated without error.

**Fail criteria:** Error such as *invalid scope*, *multiple apps*, or forced single-app selection that cannot include all products.

| Result field | Record |
|--------------|--------|
| Outcome | `PASS` / `FAIL` / `PARTIAL` |
| Error message (if any) | |
| Apps selectable in UI | |
| Tester / date | |

---

### Test T2 — Token exchange

**Objective:** Exchange grant code for refresh token.

**Procedure:**

```http
POST https://accounts.zoho.eu/oauth/v2/token
  ?grant_type=authorization_code
  &client_id={ZOHO_CLIENT_ID}
  &client_secret={ZOHO_CLIENT_SECRET}
  &code={grant_code}
```

| Result field | Record |
|--------------|--------|
| HTTP status | |
| `refresh_token` received | yes/no |
| `api_domain` | |

---

### Test T3 — Refresh grant

**Procedure:**

```http
POST https://accounts.zoho.eu/oauth/v2/token
  ?grant_type=refresh_token
  &client_id={ZOHO_CLIENT_ID}
  &client_secret={ZOHO_CLIENT_SECRET}
  &refresh_token={refresh_token}
```

| Result field | Record |
|--------------|--------|
| HTTP status | |
| `access_token` received | yes/no |

**Note:** A successful refresh **does not** validate multi-app API access.

---

### Test T4 — Per-product API probe (no customer sync)

Use access token from T3. **Do not enable Pleerity sync flags.** Direct `curl` only.

| # | Probe | Method | Endpoint | Expected if single-app token |
|---|-------|--------|----------|------------------------------|
| T4a | CRM | GET | `/crm/v6/Leads?fields=id&per_page=1` | 200 if CRM-scoped |
| T4b | Analytics | GET | `/analytics/v2/workspaces` or workspace metadata | 200 only if Analytics-scoped |
| T4c | Books | GET | `/books/v3/organizations` | 200 only if Books-scoped |
| T4d | Campaigns | GET | Campaigns metadata/list endpoint per docs | 200 only if Campaigns-scoped |
| T4e | WorkDrive | GET | WorkDrive metadata endpoint per docs | 200 only if WorkDrive-scoped |

Record HTTP status and error body for each.

---

### Test T5 — Single-app baseline (control)

Repeat T1–T4 with **CRM-only** scopes:

```
ZohoCRM.modules.leads.CREATE,ZohoCRM.modules.leads.UPDATE
```

**Expected:** T4a succeeds; T4b–T4e fail with auth/scope errors.

This establishes baseline behaviour for comparison.

---

### Test T6 — Pleerity runtime (optional, Phase A+)

With flags still off for sync:

1. Set staging secrets only (no flag enablement beyond Phase A if approved).
2. Trigger manual token refresh via admin operational path or forced cache miss.
3. Confirm `zoho_oauth_tokens` document created.

**Does not replace T4** — does not prove multi-app API access.

---

## 4. Predicted outcomes (hypothesis — not verified)

Based on official documentation (`ZOHO_OAUTH_COMPATIBILITY_REPORT.md`):

| Test | Predicted result |
|------|------------------|
| T1 Multi-app scope string | **FAIL** or forced single-app selection |
| T2/T3 Token exchange/refresh | **PASS** if T1 produced a code (for single-app scopes) |
| T4 Multi-app API probes with single-app token | **FAIL** for non-authorised apps |
| T5 CRM-only control | **PASS** for CRM probe only |

These predictions must be confirmed or refuted by sandbox execution.

---

## 5. Sandbox validation verdict (current)

| Verdict | Rationale |
|---------|-----------|
| **INCONCLUSIVE (live)** | No sandbox credentials available for live testing |
| **DOCUMENTED INCOMPATIBILITY (theoretical)** | High-confidence based on Zoho official one-app-per-refresh-token rule |

**Recommendation:** Execute T1–T5 **before** minting long-lived refresh tokens for multi-phase rollout. If T1 fails, proceed with per-app refresh token architecture without further debate.

---

## 6. Safety constraints for future sandbox execution

- Sandbox Zoho org only
- No `ZOHO_*_SYNC_ENABLED=true` during OAuth probes unless testing a single controlled adapter
- No production Render changes
- No customer data export jobs
- Record grant codes and tokens only in secure secret store — not in git

---

## 7. Amendment template (post-execution)

When sandbox tests complete, append:

```markdown
## Amendment — Sandbox execution {DATE}

| Test | Result | Evidence |
|------|--------|----------|
| T1 | | screenshot / error text |
| T2 | | |
| T3 | | |
| T4a–e | | HTTP status per probe |
| T5 | | |

**Updated verdict:** COMPATIBLE / INCOMPATIBLE / PARTIALLY COMPATIBLE
```
