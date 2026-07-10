# Zoho OAuth Architecture Recommendation (Stage O4)

**Programme:** ZOHO OAUTH ARCHITECTURE VALIDATION  
**Date:** 2026-07-10  
**Decision required before:** Multi-integration sync phases (B+) and long-lived refresh token minting

---

## 1. Recommendation

**Adopt Option B: Shared OAuth client, separate refresh token per Zoho business application.**

Do **not** proceed with Option A (current single refresh token) for multi-app integration rollout.

Do **not** adopt Option C unless security policy mandates full client isolation per product.

---

## 2. Options evaluated

### Option A — Single client, single refresh token (current)

| Aspect | Assessment |
|--------|------------|
| **Description** | One `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`; one `ZohoOAuthManager`; one Mongo cache |
| **Zoho compatibility** | **Incompatible** with multi-app model (official docs) |
| **Security** | Single blast radius — one leaked token exposes all authorised apps |
| **Least privilege** | **Poor** — cannot scope tokens per integration |
| **Operational complexity** | **Lowest** — one secret to rotate |
| **Failure isolation** | **Poor** — token revocation affects all integrations |
| **Implementation effort** | Zero (current state) |
| **Phased rollout** | **Blocked** beyond single-app pilot |

**Verdict:** Suitable only for Phase A shell (no API calls) or **single-app** pilot. **Not recommended** for CRM + Analytics + Books + Campaigns + WorkDrive horizon.

---

### Option B — Shared client, per-app refresh tokens (recommended)

| Aspect | Assessment |
|--------|------------|
| **Description** | One Self Client (`ZOHO_CLIENT_ID` / `ZOHO_CLIENT_SECRET`); separate refresh tokens per Zoho app |
| **Example env vars** | `ZOHO_CRM_REFRESH_TOKEN`, `ZOHO_ANALYTICS_REFRESH_TOKEN`, `ZOHO_BOOKS_REFRESH_TOKEN`, `ZOHO_CAMPAIGNS_REFRESH_TOKEN`, `ZOHO_WORKDRIVE_REFRESH_TOKEN` |
| **Zoho compatibility** | **Compatible** — one refresh token per app per official rules |
| **Security** | Tokens scoped per product; compromise of Books token does not authorise CRM |
| **Least privilege** | **Good** — mint only scopes needed per app at each phase gate |
| **Maintainability** | **Good** — one API console client; multiple secrets in Render |
| **Operational complexity** | **Moderate** — 1–5 refresh secrets to rotate over time |
| **Credential rotation** | Per-app rotation without touching other integrations |
| **Failure isolation** | **Good** — Books token expiry does not block CRM |
| **Scalability** | **Good** — add new app = new refresh token + cache slot |
| **Implementation effort** | **Small–Medium** (see migration plan) |

**Verdict:** **Preferred.** Aligns with Zoho platform, Pleerity phased rollout, and governance least-privilege.

---

### Option C — Separate OAuth client per application

| Aspect | Assessment |
|--------|------------|
| **Description** | Distinct client ID/secret/refresh per app (e.g. `ZOHO_CRM_CLIENT_ID`, …) |
| **Zoho compatibility** | **Compatible** |
| **Security** | **Highest** isolation between clients |
| **Least privilege** | **Excellent** |
| **Maintainability** | **Lower** — multiple API console registrations |
| **Operational complexity** | **High** — 5 clients × credentials × rotation procedures |
| **Implementation effort** | **Medium–Large** |

**Verdict:** Justified only if compliance mandates separate OAuth clients per data domain. Overkill for current pilot scope.

---

## 3. Comparison matrix

| Criterion | Option A (current) | Option B (recommended) | Option C |
|-----------|-------------------|----------------------|----------|
| Zoho multi-app compliance | No | Yes | Yes |
| Security / blast radius | Weak | Strong | Strongest |
| Maintainability | High | High | Medium |
| Ops complexity | Low | Medium | High |
| Least privilege | No | Yes | Yes |
| Failure isolation | No | Yes | Yes |
| Phased rollout fit | Poor | **Excellent** | Good |
| Implementation effort | None | **S–M** | M–L |

---

## 4. Per-app scope bundles (mint at phase gates)

When implementing Option B, mint **separate** refresh tokens with these scope strings (EU Self Client, comma-separated, no spaces):

### CRM (`ZOHO_CRM_REFRESH_TOKEN`) — Phase C

```
ZohoCRM.modules.leads.CREATE,ZohoCRM.modules.leads.UPDATE
```

Adjust `leads` if `ZOHO_CRM_MODULE` differs.

### Analytics (`ZOHO_ANALYTICS_REFRESH_TOKEN`) — Phase B

```
ZohoAnalytics.data.create
```

### Books (`ZOHO_BOOKS_REFRESH_TOKEN`) — Books pilot

```
ZohoBooks.accountants.CREATE
```

### Campaigns (`ZOHO_CAMPAIGNS_REFRESH_TOKEN`) — Campaigns pilot

```
ZohoCampaigns.contact.CREATE-UPDATE
```

### WorkDrive (`ZOHO_WORKDRIVE_REFRESH_TOKEN`) — WorkDrive pilot

```
WorkDrive.files.CREATE
```

### Sign

**No OAuth refresh token required** — webhook-only in current implementation.

---

## 5. Target runtime architecture (Option B)

```
ZohoHttpClient.request(integration="crm", ...)
    → ZohoOAuthManager.get_access_token(integration="crm")
        → ZOHO_CRM_REFRESH_TOKEN (env)
        → Mongo cache: token_id="zoho_oauth_access_token_crm"

ZohoHttpClient.request(integration="books", ...)
    → ZohoOAuthManager.get_access_token(integration="books")
        → ZOHO_BOOKS_REFRESH_TOKEN (env)
        → Mongo cache: token_id="zoho_oauth_access_token_books"
```

Shared: `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_ACCOUNTS_URL`, `ZOHO_API_BASE`.

---

## 6. Phase alignment

| Phase | OAuth requirement under Option B |
|-------|----------------------------------|
| **Phase A** | Client ID + secret only; per-app refresh tokens optional until API calls needed |
| **Phase B** | `ZOHO_ANALYTICS_REFRESH_TOKEN` + Analytics scopes |
| **Phase C** | `ZOHO_CRM_REFRESH_TOKEN` + CRM scopes |
| **Campaigns** | `ZOHO_CAMPAIGNS_REFRESH_TOKEN` when flag enabled |
| **Books** | `ZOHO_BOOKS_REFRESH_TOKEN` when flag enabled |
| **WorkDrive** | `ZOHO_WORKDRIVE_REFRESH_TOKEN` when flag enabled |

Enabling a sync flag without its refresh token should produce a clear `no_credentials` / `oauth_not_configured_for_integration` outcome (existing skip pattern).

---

## 7. Documentation corrections required (post-approval)

| Document | Correction |
|----------|------------|
| `ZOHO_SANDBOX_READINESS_REPORT.md` §3.2 | Remove implication that one refresh token can hold all product scopes |
| `zoho_integration.env.example` | Add per-app refresh token placeholders (when implemented) |
| `ZOHO_SECURITY_AND_TOKEN_MANAGEMENT.md` | Document per-app token model |

---

## 8. Decision gate

| If… | Then… |
|-----|-------|
| Leadership approves Option B | Proceed to `ZOHO_OAUTH_MIGRATION_PLAN.md` implementation stage |
| Sandbox T1 unexpectedly **passes** multi-app scopes | Re-open compatibility report with live evidence before discarding Option B |
| Single-app pilot only (CRM forever) | Option A may suffice **only for CRM** — document explicit scope limitation |

---

## 9. Final statement

The current OAuth architecture is **internally coherent** but **externally incompatible** with Zoho's documented one-app-per-refresh-token model for the planned multi-integration roadmap.

**Option B** is the recommended evidence-based path: minimal operational disruption, platform compliance, phased least-privilege, and preserved governance (flags, kill switch, SoR boundaries unchanged).

**No implementation should begin until this recommendation is approved.**
