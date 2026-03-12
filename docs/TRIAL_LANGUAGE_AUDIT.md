# Trial and free-trial language audit

**Date:** 2026-02-20  
**Scope:** Remove or replace all copy implying trial access, no-card-required signup, or free trial where no trial is implemented.

---

## Occurrences and classification

| # | File | Exact text | Classification | Action taken |
|---|------|------------|----------------|--------------|
| 1 | `frontend/src/pages/public/FAQPage.js` | `Start Free Trial` (CTA button) | **replace** | → "Get Started" |
| 2 | `frontend/src/pages/public/PricingPage.js` | `Try Compliance Vault Pro. Start with a 14-day trial when you sign up—see pricing for current offer details.` | **replace** | → Neutral CTA, no trial |
| 3 | `frontend/src/clearform/pages/ClearFormLandingPage.jsx` | `5 free credits to get started • No credit card required` | **replace** | Remove "No credit card required"; keep credits line only or reword |
| 4 | `frontend/src/clearform/pages/ClearFormLandingPage.jsx` | `Start free, upgrade when you need more` | **replace** | → "Get started, upgrade when you need more" |
| 5 | `backend/services/lead_nurture_service.py` | `[Start 14-day trial]({base_url}/intake/start)` | **replace** | → "[Get started](...)" |
| 6 | `backend/routes/tenant.py` | `Tenants get free access to compliance packs for their assigned properties.` | **replace** | → "Included access" (docstring) |
| 7 | `frontend/src/pages/public/InsightsHubPage.js` | `Start Free Trial` (link text, 2 places) | **replace** | → "Get Started" |
| 8 | `frontend/src/pages/public/articles/UKLandlordComplianceChecklist2026.js` | `Start Free Trial` (2 places) | **replace** | → "Get Started" |
| 9 | `frontend/src/pages/public/ChecklistThankYouPage.js` | `Start Free Trial of Compliance Vault Pro` | **replace** | → "Get started with Compliance Vault Pro" |
| 10 | `frontend/src/pages/public/ChecklistThankYouPage.js` | Comment: `CTA to Start Free Trial` | **replace** | → "CTA to get started with Compliance Vault Pro" |

---

## Left unchanged (verify / not trial)

| File | Text | Reason |
|------|------|--------|
| `frontend/src/pages/public/PricingPage.js` | Plan name `'Free'` | Plan tier name; may be £0 tier. Business decision. |
| `frontend/src/pages/public/InsightsHubPage.js` | "Free landlord compliance checklist" (meta) | Free PDF resource, not trial. |
| `frontend/src/pages/public/articles/UKLandlordComplianceChecklist2026.js` | "Download the Free Landlord Compliance Checklist" | Free download asset. |
| `frontend/src/pages/public/ChecklistThankYouPage.js` | "free UK Landlord Compliance Master Checklist" | Same. |
| `frontend/src/pages/public/ServicesHubPage.js` | "Book a free consultation" | Free consultation offer. |
| `frontend/src/pages/public/BookingPage.js` | "free consultation", "free 30-minute call" | Same. |
| Backend: `jobs.py`, `portal.py`, `analytics.py`, `stripe_webhook_service.py`, `plan_registry.py`, etc. | `TRIALING`, `trialing`, `trial` in subscription_status / funnel | Technical: Stripe status and analytics. No copy change. |
| `backend/routes/tenant.py` | "free access" in docstring | Replaced with "included access" for consistency. |
| `frontend/src/pages/BillingPage.js` | "14-day money-back guarantee" | Refund policy, not trial. Left unchanged. |

---

## Replacement principle

- Do not imply a trial period.
- Do not imply no credit card required unless the flow truly does not require a card.
- Align with current pricing and checkout (sign up → Stripe checkout; no trial provision).

---

## Files changed (implementation)

| File | Change |
|------|--------|
| `frontend/src/pages/public/FAQPage.js` | "Start Free Trial" → "Get Started" |
| `frontend/src/pages/public/PricingPage.js` | CTA paragraph: removed "14-day trial"; now "Get started with Compliance Vault Pro. Choose a plan below and sign up—no long-term contract." |
| `frontend/src/clearform/pages/ClearFormLandingPage.jsx` | Removed "• No credit card required"; "Start free, upgrade when you need more" → "Get started, upgrade when you need more" |
| `backend/services/lead_nurture_service.py` | Nurture email link "[Start 14-day trial](...)" → "[Get started](...)" |
| `backend/routes/tenant.py` | Docstring "free access" → "included access" |
| `frontend/src/pages/public/InsightsHubPage.js` | "Start Free Trial" → "Get Started" (2 places) |
| `frontend/src/pages/public/articles/UKLandlordComplianceChecklist2026.js` | "Start Free Trial" → "Get Started" (2 places) |
| `frontend/src/pages/public/ChecklistThankYouPage.js` | Button "Start Free Trial of Compliance Vault Pro" → "Get started with Compliance Vault Pro"; comment updated |
| `docs/TRIAL_LANGUAGE_AUDIT.md` | New audit document |

---

## Follow-up changes (admin funnel and lead scoring)

| File | Change |
|------|--------|
| `backend/services/lead_service.py` | Removed "trial" from `high_intent_keywords` so lead scoring does not imply trial offer. |
| `frontend/src/pages/AdminAnalyticsDashboard.js` | Marketing Funnel: comment "Trial" → "Activated"; description "trials" → "activated signups"; KPI and table headers "Trials" → "Activated"; timing labels "lead → trial" / "trial → paid" → "lead → activated" / "activated → paid". |
| `frontend/src/pages/AdminExecutiveOverviewPage.js` | Subscription table header "Trial" → "Trialing" (Stripe status); Growth efficiency "Trials" → "Activated". |
| `backend/routes/analytics.py` | Funnel stage "Trial started" → "Activated"; CSV export headers "Trials" → "Activated", "Avg days lead to trial" → "Avg days lead to activated", "Avg days trial to paid" → "Avg days activated to paid"; doc comments updated. |

Backend API still returns `trials_count` and `avg_days_lead_to_trial` / `avg_days_trial_to_paid` (unchanged) for Stripe compatibility; only user-facing labels now say "Activated".

---

## Remaining areas needing manual business decision

1. **Pricing page plan name `'Free'`** (PricingPage.js) — If there is a £0 plan, "Free" is accurate. If not, consider renaming to "Starter" or removing the free tier from the UI.
2. **ClearForm "5 free credits to get started"** — If ClearForm actually grants 5 free credits without payment, keep. If not, reword or remove.
