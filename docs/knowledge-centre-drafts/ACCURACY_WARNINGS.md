# Accuracy Warnings – Knowledge Centre Drafts

**Use this list when reviewing or publishing draft articles.** Anything marked here should be verified against the live product before publication.

---

## 1. Flows that need product verification

| Area | Warning | Action |
|------|---------|--------|
| **Onboarding / Provisioning** | Exact steps and status labels (e.g. PROVISIONED, PROVISIONING_STARTED) may vary by environment. Setup-status API and onboarding-status page behaviour should be confirmed. | Verify with real onboarding flow and portal/setup-status response. |
| **Compliance pack generation** | Backend service exists (`compliance_pack`); client-facing “download compliance pack” flow and route may be under Reports or tenant; exact UI path not confirmed in this scan. | Confirm where users download packs and what they receive. |
| **Reminder schedule** | Daily reminders run at a fixed time (e.g. 09:00 UTC). Documented as “once per day”; exact time and timezone should be stated or verified. | Confirm schedule and any env-based overrides. |
| **Extraction (evidence)** | “Confirm details” modal and extraction timeout (e.g. 90s) are in code; exact user-facing message for “extraction failed” and retry behaviour may vary. | Verify copy and behaviour in UI. |
| **Feature flags / entitlements** | Client nav items (Operations, Tenants, Billing, etc.) are gated by plan/entitlements. Which plans have which features should be confirmed from plan_registry/config. | Do not list a feature as “available” without confirming plan. |
| **Ops Compliance / Audit / Risk** | `/admin/ops/compliance`, `/admin/ops/audit`, `/admin/ops/risk` currently render placeholder pages. Playbooks that reference “Ops Compliance” should say “when available” or “Needs verification before publication.” | Update when real Ops Compliance/Audit/Risk UIs are implemented. |
| **Run Now (automation)** | “Run Now” is for recovery/testing only; idempotency (e.g. daily_reminders) should be confirmed so we don’t document risk of duplicate sends. | Confirm with backend that Run Now is safe for reminder job. |

---

## 2. UI present; backend or behaviour unclear

| Item | Warning |
|------|---------|
| **Admin Dashboard tabs** | Tabs (Clients, Rules, Templates, Email delivery) exist; order and which tabs are visible to which role should be confirmed at runtime. |
| **Billing / Plans** | Billing page exists; exact plan names, limits, and “upgrade” flows are configuration-dependent. Document only generic “see Billing” or verify plan list. |
| **SMS reminders** | SMS verification and SMS reminder toggles exist; availability may depend on plan or SMS provider config. Label as “if available on your plan.” |
| **Export (PDF/CSV)** | Compliance Score export is gated by entitlement (e.g. reports_pdf). Document as “if your plan includes report export.” |

---

## 3. Partially implemented or placeholder

| Item | Warning |
|------|---------|
| **Ops Compliance** | Admin route exists; page is placeholder. Do not document detailed “Ops Compliance” steps until the page is implemented. |
| **Ops Audit & Logs** | Same as above; placeholder. |
| **Ops Risk & Insights** | Same as above; placeholder. |
| **Timeline** | No dedicated “Timeline” module; calendar and score timeline exist. Use “Calendar” or “Score trend” in docs. |
| **Assets** | No Assets module in client routes. Do not generate user docs for “Assets” until implemented. |

---

## 4. Do not document as live

- Features that are only in design or backlog.
- “Future” or “coming soon” capabilities unless explicitly released.
- ClearForm-specific flows in main platform Help Centre (keep ClearForm docs separate or clearly scoped).

---

## 5. Verification status for generated drafts

- **Draft:** All generated articles are marked **Draft** and **Needs product review** where the flow was inferred from code.
- **Publish only after:** (1) Review against this accuracy list, (2) Spot-check in target environment, (3) Confirm audience (USER vs STAFF vs ADMIN) and category.
