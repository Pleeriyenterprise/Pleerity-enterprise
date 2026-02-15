# Entitlement-aware UI gating – test checklist

Use this checklist to verify entitlement gating and 403 handling for **Solo**, **Portfolio**, and **Professional** client logins.

## Solo (PLAN_1_SOLO)

- [ ] **Nav**: Dashboard, Properties, Documents, Calendar, Profile, Plans visible. **Reports, Tenants, Integrations** not in nav.
- [ ] **Direct URL** `/app/reports` → page loads; upgrade prompt or upgrade-required state (no crash).
- [ ] **Direct URL** `/app/tenants` → upgrade-required state + “Back to Dashboard” (no ErrorBoundary).
- [ ] **Direct URL** `/app/integrations` → upgrade-required state + “Back to Dashboard”.
- [ ] **Direct URL** `/app/settings/branding` → upgrade-required state + “Back to Dashboard”.
- [ ] **Documents**: Analyze works (basic only); no “Review & Apply Data” / “Edit” extraction buttons.
- [ ] **Bulk upload**: ZIP mode hidden or disabled; multi-file upload works. If ZIP somehow triggered (e.g. API), 403 → upgrade state.
- [ ] **Notifications**: SMS section shows upgrade card (Professional required); no SMS toggles/inputs.
- [ ] **Reports** (if reached): upgrade prompt for PDF/CSV/scheduled; no crash on 403 from generate/schedules.

## Portfolio (PLAN_2_PORTFOLIO)

- [ ] **Nav**: Dashboard, Properties, Documents, Calendar, **Reports**, Profile, Plans visible. **Tenants, Integrations** not in nav.
- [ ] **Direct URL** `/app/tenants` → upgrade-required state (Pro required).
- [ ] **Direct URL** `/app/integrations` → upgrade-required state.
- [ ] **Direct URL** `/app/settings/branding` → upgrade-required state.
- [ ] **Documents**: Analyze works; “Review & Apply Data” / “Edit” extraction **not** visible (Pro only).
- [ ] **Bulk upload**: ZIP upload available and works.
- [ ] **Reports**: PDF and scheduled reports work; CSV export shows upgrade (Pro) or is hidden.
- [ ] **Notifications**: SMS section shows upgrade card (Pro required).
- [ ] Any 403 from reports/schedules → upgrade state, no crash.

## Professional (PLAN_3_PRO)

- [ ] **Nav**: Dashboard, Properties, Documents, Calendar, Reports, **Tenants**, **Integrations**, Profile, Plans visible.
- [ ] **Direct URL** `/app/tenants`, `/app/integrations`, `/app/settings/branding` → full page content (no gate).
- [ ] **Documents**: Analyze with advanced extraction; “Review & Apply Data” and “Edit” extraction visible and working.
- [ ] **Bulk upload**: ZIP upload works.
- [ ] **Reports**: PDF, CSV, scheduled reports and audit export available; no spurious upgrade prompts.
- [ ] **Notifications**: SMS section visible; can enable and verify phone (or see appropriate errors).
- [ ] No unexpected 403 or upgrade prompts for Pro features.

## 403 handling (any plan)

- [ ] **Documents**: Trigger 403 on analyze (e.g. force `return_advanced=true` for non-Pro) or apply-extraction → “Upgrade required” state with feature/plan; “Back to Dashboard” / “Continue to documents”; no ErrorBoundary.
- [ ] **Reports**: 403 on generate or schedules → upgrade state on page; no crash.
- [ ] **Bulk upload**: 403 on ZIP upload → upgrade state; no crash.
- [ ] **Dashboard**: 403 on dashboard load → existing “Access restricted by plan” (or similar) message; no blank screen / ErrorBoundary.

## Quick smoke

1. Log in as **Solo** → confirm Reports/Tenants/Integrations not in nav; open `/app/tenants` → upgrade screen.
2. Log in as **Portfolio** → Reports in nav; Tenants/Integrations not; open `/app/integrations` → upgrade screen.
3. Log in as **Pro** → all nav items; tenants/integrations/branding pages load; Documents review/apply and CSV/SMS visible.
