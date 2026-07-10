# Zoho OAuth Compatibility Report (Stage O2)

**Programme:** ZOHO OAUTH ARCHITECTURE VALIDATION  
**Date:** 2026-07-10  
**Basis:** Official Zoho OAuth documentation (accessed 2026-07-10) + Pleerity implementation review

---

## 1. Verdict summary

| Question | Finding | Confidence |
|----------|---------|------------|
| Can one refresh token authenticate requests to **multiple Zoho business applications**? | **No** — officially one Zoho app per refresh token | **High** |
| Can one authorization request include scopes from **multiple Zoho business applications**? | **No** — explicit error `Invalid OAuth Scope` | **High** |
| Can one refresh token span CRM + Analytics + Books + Campaigns + WorkDrive? | **No** — five distinct business apps | **High** |
| Are EU (`accounts.zoho.eu`) rules different? | **No material difference** in token model; DC-specific accounts URL only | **Medium** (EU Self Client UI not live-tested here) |
| Does Self Client bypass the one-app rule? | **No explicit exemption**; UI prompts to select **one** Zoho app | **Medium** |

**Conclusion:** The current **single `ZOHO_REFRESH_TOKEN` architecture is not compatible** with Zoho's documented multi-application OAuth model for the full integration horizon (CRM, Analytics, Books, Campaigns, WorkDrive).

**Partial compatibility:** A token minted for **one** Zoho app may work for that app's API calls only. Other adapters would fail at API time (typically `401` / invalid OAuth token / insufficient scope).

---

## 2. Official sources

| Source | URL | Relevant rule |
|--------|-----|---------------|
| Instance-level OAuth | `https://www.zoho.com/accounts/protocol/oauth/instance-level-oauth.html` | **"Scopes are limited to one Zoho app per refresh token"** |
| Get authorization code (instance) | `https://www.zoho.com/accounts/protocol/oauth/instance-level-oauth/get-auth-code.html` | Error `Invalid OAuth Scope`: *"Scopes of more than one Zoho app are included in the request"* |
| Self Client overview | `https://www.zoho.com/accounts/protocol/oauth/self-client/overview.html` | Authorization code grant → refresh token flow |
| Self Client auth code flow | `https://www.zoho.com/accounts/protocol/oauth/self-client/authorization-code-flow.html` | Multi-scope **comma-separated**; step 5: *"select the **Zoho app**"* |
| Incremental authorization | `https://www.zoho.com/accounts/protocol/oauth/incremental-auth/initiation-request.html` | Append scopes to **existing** refresh token (same-app enhancement) |
| OAuth scope format | `https://www.zoho.com/accounts/protocol/oauth/scope.html` | `service_name.scope_name.OPERATION_TYPE`; multiple scopes **within comma list** |

---

## 3. Question-by-question analysis

### 3.1 One refresh token → multiple Zoho business applications?

**Official position (instance-level OAuth):**

> *"The client must request for scopes of only one Zoho app per refresh token. This is because in the integration context, a refresh token defines authorization between your client and a single Zoho app, not multiple apps."*

**Exceptions documented:** common services only — `ZohoContacts`, `ZohoProfile`, `ZohoFiles`, `AaaServer`. None of these cover CRM, Analytics, Books, Campaigns, or WorkDrive API access.

**Pleerity mapping:**

| Integration | Zoho OAuth service prefix |
|-------------|---------------------------|
| CRM | `ZohoCRM` |
| Analytics | `ZohoAnalytics` |
| Books | `ZohoBooks` |
| Campaigns | `ZohoCampaigns` |
| WorkDrive | `WorkDrive` |

**Answer: No.**

---

### 3.2 One authorization request → multi-app scopes?

**Official error (instance-level get-auth-code):**

| Error code | Condition |
|------------|-----------|
| `Invalid OAuth Scope` | *"Scopes of more than one Zoho app are included in the request (excluding allowed services)"* |

**Self Client Generate Code:** permits comma-separated scopes but prompts administrator to **select one Zoho app** when creating the authorization code. Documentation does not state that cross-app scope strings succeed.

**Answer: No** for instance-level OAuth. **Likely no** for Self Client multi-app scope strings; **not live-verified** in Pleerity sandbox (see `ZOHO_OAUTH_SANDBOX_VALIDATION.md`).

---

### 3.3 Single refresh token for CRM + Analytics + Books + Campaigns + WorkDrive?

Requires five distinct Zoho business app authorizations on one refresh token.

**Answer: No** per §3.1.

---

### 3.4 Regional (EU) differences?

Zoho OAuth uses **datacenter-specific accounts servers**:

| Region | Accounts server (documented) |
|--------|------------------------------|
| EU | `https://accounts.zoho.eu` |
| US | `https://accounts.zoho.com` |
| IN | `https://accounts.zoho.in` |

Pleerity defaults: `ZOHO_ACCOUNTS_URL=https://accounts.zoho.eu`, `ZOHO_API_BASE=https://www.zohoapis.eu`.

**Token model rules** (one app per refresh token, scope format, refresh grant) are documented at the protocol level and apply across DCs. **No EU-specific exemption** to multi-app refresh tokens was found in official documentation.

**Uncertainty:** EU API Console UI behaviour for Self Client multi-app scope entry has **not** been live-tested in this exercise.

---

### 3.5 Self Client limitations

| Aspect | Documented behaviour |
|--------|-------------------|
| Client type | Self Client — no redirect URI required for token exchange |
| Grant flow | Authorization code → access + refresh token |
| Scope entry | Comma-separated; product docs referenced |
| App selection | *"If prompted, select the Zoho app"* — singular |
| Refresh | Standard `grant_type=refresh_token`; no `scope` parameter |
| Client credentials flow | No refresh token — not used by Pleerity |

Self Client does **not** document an override of the one-app-per-refresh-token rule. The instance-level rule is the clearest authoritative statement.

---

## 4. Incremental authorization (scope expansion)

Zoho supports **incremental authorization** (`grant_type=update_scopes_token`) to append scopes to an **existing refresh token**.

**Documented purpose:** enhance permissions on the **same** token — not to add a different Zoho business app to a token authorised for another app.

Cross-app scope requests remain prohibited at initial authorization. Incremental auth does not provide a documented path to merge CRM + Books scopes onto one refresh token if they were never co-authorised as the same app (which is impossible across apps).

---

## 5. Implications for Pleerity implementation

| Scenario | Expected behaviour |
|----------|-------------------|
| Refresh token minted for **CRM scopes only** | CRM adapter may succeed; Analytics/Books/Campaigns/WorkDrive API calls fail |
| Multi-app scope string at Generate Code | Likely rejected (`Invalid OAuth Scope` or invalid scope error) — **pending sandbox test** |
| Single token refresh succeeds | Proves refresh grant works; **does not** prove multi-app API access |
| Phase A (no API calls) | Token compatibility **not exercised** at runtime |
| Operational health `token_valid: true` | Only proves cached access token exists — **not** per-product authorization |

---

## 6. What the current code assumes (implicitly)

1. One refresh token's access token is valid for **all** paths under `zohoapis.eu`.
2. Scopes granted at token mint time cover **all** enabled integrations.
3. No product-specific 401 handling or token fallback exists.

These assumptions conflict with Zoho's documented one-app-per-refresh-token model.

---

## 7. Uncertainties (explicit)

| Item | Status |
|------|--------|
| Live Self Client multi-app scope rejection on EU console | **Not tested** — no sandbox credentials in validation environment |
| Exact API error body when CRM token hits Books endpoint | **Not tested** — typically `401` / `INVALID_OAUTHTOKEN` per product docs |
| Zoho One bundle-specific unified token (undocumented) | **No official evidence found** — do not rely on without Zoho support confirmation |
| Whether Phase A token with **zero product scopes** can refresh | **Likely yes** for token endpoint; product APIs would still fail without scopes |

---

## 8. Compatibility matrix

| Architecture element | Zoho platform compatibility |
|---------------------|----------------------------|
| Single `ZOHO_CLIENT_ID` / `ZOHO_CLIENT_SECRET` | **Compatible** — one OAuth client can obtain multiple refresh tokens |
| Single `ZOHO_REFRESH_TOKEN` for all products | **Incompatible** with multi-app rollout |
| Single Mongo access-token cache | **Compatible only if** single token per environment remains; **incompatible** with per-app tokens without refactor |
| Fixed `ZOHO_API_BASE` for all products | **Compatible** for EU org using `zohoapis.eu` |
| Ignoring `api_domain` from token response | **Acceptable** if `ZOHO_API_BASE` matches org DC |

---

## 9. Final compatibility determination

**The current OAuth architecture is not suitable for long-term multi-application Zoho integration as implemented and documented by Zoho.**

It may function for:

- **Phase A** (credential shell, no product API calls), or
- **Single-app pilots** (e.g. CRM-only Phase C) if the refresh token was minted with that app's scopes only.

It will **not** reliably support enabling Analytics, Books, Campaigns, and WorkDrive on the **same** refresh token without platform behaviour that contradicts official Zoho OAuth documentation.

**Recommended action:** Approve architectural refactor (see `ZOHO_OAUTH_RECOMMENDATION.md`) before minting production refresh tokens or enabling multi-integration sync phases.
