# Marketing Funnel Analytics & Email Nurture — Audit

**Purpose:** Check the codebase against the task requirements. Identify what is implemented, what is missing, and any conflicts. Propose the safest implementation path without duplicating or conflicting with existing behaviour.

---

## DATA SOURCES (task vs codebase)

| Task requirement | Codebase reality | Notes |
|------------------|------------------|--------|
| "submissions collection (type=lead)" | **`leads`** collection (no unified "submissions" with type=lead) | Admin submissions API exposes `leads` as type=lead. Use **`leads`** as source of truth for marketing funnel. |
| clients collection | **`clients`** exists | subscription_status (PENDING, ACTIVE, TRIALING, etc.), lifecycle_status, created_at, billing_plan. |
| stripe_events / subscription records | Stripe webhooks update **clients** (subscription_status, billing_plan); **orders** have stripe_payment_status, pricing; no separate stripe_events aggregation for MRR | MRR must be derived from **clients** + billing_plan (plan registry has prices) or from **orders** revenue in period. |
| portal_users | **`portal_users`** exists | Links to client_id; can infer "portal activated" (user exists for client). |
| UTM in submission.metadata.utm | **Leads** have **top-level** `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` (no nested metadata.utm) | Use `lead.utm_source` etc. for attribution. Optionally normalize to `metadata.utm` for future consistency. |

**Conclusion:** Use **leads**, **clients**, **portal_users**, and **orders** (or client billing) for the marketing funnel. Do not assume a "submissions" collection; treat "submissions (type=lead)" as **leads** everywhere.

---

## EXISTING ANALYTICS (avoid duplication / conflict)

| Existing | Purpose | Conflict with task? |
|----------|---------|---------------------|
| **GET /api/admin/analytics/overview** | Event-based KPIs from **analytics_events**: lead_captured, intake_submitted, checkout_started, payment_succeeded, provisioning_completed, activation_email_sent, password_set, first_doc_uploaded. Conversion rates, leads_by_source (from event.source), median times. | **Different funnel**: event-driven (lead_captured → intake → checkout → paid → provisioned → activation → password → first_doc). Task wants **stage-based**: leads → trial_started → portal_activated → paid. **Do not replace** overview; add a **separate** marketing-funnel API. |
| **GET /api/admin/analytics/funnel** | Same event-based stages (Lead Captured, Intake Submitted, …). | Same as above. Keep as-is. |
| **GET /api/admin/analytics/conversion-funnel** | **Order funnel**: drafts → converted drafts → paid orders → completed orders (from orders collection). | Different metric (order conversion). Keep. |
| **AdminAnalyticsDashboard.js** | Single page at `/admin/analytics`; fetches summary, services, SLA, customers, conversion-funnel, overview, funnel (events), failures. | No "Marketing Funnel" section yet. Add as **new section/tab** or **new route** (e.g. `/admin/analytics/marketing-funnel` or tab "Marketing Funnel" on same page). |

**Recommendation:** Introduce a **new** backend endpoint (e.g. **GET /api/admin/analytics/marketing-funnel**) and a **new** UI section "Marketing Funnel" under Admin → Analytics. Leave existing overview/funnel/conversion-funnel endpoints and their UI unchanged.

---

## SECTION 1 — KPI CARDS (task vs current)

| KPI | Task | Current | Gap |
|-----|------|---------|-----|
| visitors | "if available; else placeholder" | Not in analytics; no website analytics ingestion found | **Placeholder** (e.g. "—" or "N/A") until a source exists. |
| leads_count | type=lead, date filter | overview uses **analytics_events** (lead_captured); lead count by date exists in **leads** | **Add** count from **leads** collection with created_at in range (not only events). |
| trials_count | "clients with status=trial" | clients have **subscription_status** (e.g. TRIALING, ACTIVE). No literal "trial" lifecycle stage in schema. | **Define**: trials_count = clients where subscription_status in (TRIALING, trialing) **or** lifecycle_status indicates trial if present. Prefer **subscription_status = TRIALING**. |
| paid_count | "active subscriptions" | clients with subscription_status ACTIVE (and TRIALING for "active" access) | **paid_count** = clients with subscription_status = ACTIVE (exclude TRIALING for "paid" if task implies paid only). Clarify: task "trials" vs "paid" → use TRIALING for trials, ACTIVE for paid. |
| conversion_rate | paid_count / leads_count | overview has lead_to_paid from events | **Add** conversion_rate = (paid_count / leads_count) * 100 when leads_count > 0 (from collections, not only events). |
| mrr | MRR | Revenue in analytics is from **orders** (total_pence in period); no recurring MRR aggregate found | **Add** MRR: derive from **clients** with subscription_status = ACTIVE and billing_plan (map plan → monthly amount via plan_registry or config), or from Stripe subscription recurring amount if stored. If not stored, MRR can be placeholder or computed from orders revenue (approximation). |

---

## SECTION 2 — FUNNEL (task vs current)

| Task | Current | Gap |
|------|---------|-----|
| Stages: leads → trial_started → portal_activated → paid | Event funnel: lead_captured → intake → checkout → paid → provisioned → activation_email_sent → password_set → first_doc_uploaded | **Different semantics.** Implement **marketing funnel** stages: (1) **leads** (count from leads in range), (2) **trial_started** (clients created in range with subscription_status TRIALING or first subscription_status set to TRIALING), (3) **portal_activated** (portal_users with client_id in set of clients in range), (4) **paid** (clients subscription_status ACTIVE in range). Conversion % between each stage. |
| Conversion % between each | Event funnel has step_conversion_percent | Same idea; apply to the four marketing stages above. |

**Recommendation:** In the new **marketing-funnel** endpoint, compute four stages from **leads** + **clients** + **portal_users** (and optionally analytics_events for "trial_started" if you track trial start explicitly). Use **created_at** and subscription_status for client-based stages.

---

## SECTION 3 — SOURCE ATTRIBUTION (task vs current)

| Task | Current | Gap |
|------|---------|-----|
| Group by submission.metadata.utm.source | overview: **leads_by_source** from analytics_events.**source** (event field) | **Different source**: task wants **UTM source** (e.g. organic, facebook). Leads have **utm_source** (and utm_medium, etc.) at top level. |
| Show: leads, trials, paid, conversion % | overview only leads count by source | **Add** source breakdown from **leads**: group by **utm_source** (or "Direct"/"unknown" if null). For each source: count leads, count trials (clients with that UTM or linked via lead_id→client), count paid, conversion % = paid/leads. **Linking lead→client**: use lead_audit_logs or conversion event (lead_id on client?) or match by email. Need to confirm how lead→client link is stored. |

**Note:** If lead→client link is only in analytics_events (e.g. lead_captured with lead_id, then payment_succeeded with client_id), attribution by utm_source requires joining leads (by lead_id) to events then to clients. If clients store lead_id or email, we can join leads → clients by email for attribution. **Recommendation:** Prefer storing **lead_id** on **clients** when converting (if not already); else use email match or analytics_events to link lead → client for source attribution.

---

## SECTION 4 — LEAD SCORE (task vs current)

| Task | Current | Gap |
|------|---------|-----|
| lead_score 0–100: portfolio_size, urgency, email domain, pricing_viewed, demo_clicked | Leads have **intent_score** (LOW/MEDIUM/HIGH) from calculate_intent_score (source, service_interest, has_phone, message). No portfolio_size, no "pricing_viewed"/"demo_clicked" tracking in lead doc. | **Add** optional **lead_score** (0–100). Backend: compute from existing fields (intent_score, company_name, message_summary) + if available: portfolio_size (from intake or lead?), urgency (keyword?), tags (pricing_viewed, demo_interested). Store in **lead** doc (e.g. **metadata.lead_score** or top-level **lead_score**). Frontend: **AdminLeadsPage** — add badge column (High / Medium / Low from score bands). |
| Store in submission.metadata.lead_score | Lead doc has **source_metadata**; no metadata.lead_score | Add **lead_score** (and optionally **metadata.lead_score** for consistency with task wording). |

**Recommendation:** Add **lead_score** (integer 0–100) to lead document. Compute from: intent_score mapping (e.g. HIGH→60, MEDIUM→35, LOW→10) + optional future signals (portfolio_size, tags). Display badge (e.g. High ≥60, Medium 30–59, Low <30) in leads table. Do not remove **intent_score**; keep both (intent_score = qualification, lead_score = composite for funnel/attribution).

---

## SECTION 5 — CONVERSION TIMING (task vs current)

| Task | Current | Gap |
|------|---------|-----|
| avg_days_lead_to_trial | overview has **median_seconds** (paid_to_provisioned, provisioned_to_password_set, password_set_to_first_value) | **Add** avg_days **lead → trial**: need "trial start" timestamp. Trial = client created with subscription_status TRIALING, or first time subscription_status set to TRIALING. Use **clients.created_at** as proxy for "trial start" if no separate trial_start_at. Lead created_at from **leads**. Match lead→client by lead_id on client or by email. Compute average (lead.created_at → client.created_at) in days. |
| avg_days_trial_to_paid | — | **Add** avg_days **trial → paid**: need first TRIALING date and first ACTIVE date per client. If only subscription_status and updated_at are stored, use client.updated_at when status changed to ACTIVE (or use stripe_events / webhook logs if stored). Approximate: clients who have been TRIALING then ACTIVE — use provisioning_completed or password_set as "trial start" and payment_succeeded or subscription_status ACTIVE timestamp as "paid". Simplest: from **analytics_events** — median_seconds(lead_captured, payment_succeeded) and (provisioning_completed or first_doc_uploaded) to (payment_succeeded) if that reflects trial→paid. **Recommendation:** Use **clients**: for converted clients, use created_at as "trial start" and a "paid_at" or first subscription_status=ACTIVE update time if stored; else derive from orders or analytics_events. |

---

## SECTION 6 — EMAIL PERFORMANCE (Nurture) (task vs current)

| Task | Current | Gap |
|------|---------|-----|
| Track open rate, click rate, conversion after email | **message_logs** and Postmark webhooks (delivery, bounce, etc.) exist. No dedicated "nurture open/click" aggregation. | **Add** (later phase): aggregate by template_key or event_type (e.g. checklist_nurture_1..5), count sent/open/click from message_logs; count conversions (lead→client) after each email. "Conversions influenced by nurture" = clients linked to lead that received nurture. |
| "Conversions influenced by nurture sequence" | Not present | New metric: count clients whose lead_id (or email) had nurture_stage > 0 or received any checklist_nurture email. |

**Recommendation:** Phase 2: add analytics aggregation from **message_logs** (and optional Postmark webhook open/click) for nurture template keys; add "Conversions influenced by nurture" in marketing-funnel response. Phase 1 can expose a placeholder or "N/A".

---

## UI REQUIREMENTS (task)

| Requirement | Current | Gap |
|-------------|---------|-----|
| Date filter (7d, 30d, 90d, custom) | Analytics already has period (7d, 30d, 90d) and from_date/to_date in overview/funnel | Reuse same pattern for marketing-funnel API and new UI. |
| Export CSV | Some analytics/reports have CSV export | **Add** export CSV for marketing funnel (KPIs + funnel + source breakdown + timing). |
| Mobile responsive | Admin dashboard uses responsive layout | Use same layout patterns (grid, cards). |
| Only Admin/Owner | **require_owner_or_admin** or **admin_route_guard** used on analytics | Use **require_owner_or_admin** for marketing-funnel endpoint and restrict Marketing Funnel view to same roles. |

---

## PART 1 — EMAIL NURTURE SEQUENCE (task vs current)

| Task | Current | Gap |
|------|---------|-----|
| Trigger: submission.type=lead, metadata.lead_magnet="Landlord Compliance Checklist v1" | **Leads** from **COMPLIANCE_CHECKLIST** source_platform; no metadata.lead_magnet field. Nurture in **lead_nurture_service**: 5-email sequence, trigger by source_platform and marketing_consent. | **Align trigger**: keep source_platform=COMPLIANCE_CHECKLIST; optionally add **metadata.lead_magnet** = "Landlord Compliance Checklist v1" when capturing checklist lead. Add tag **checklist_download** and sequence name **checklist_nurture_v1** in lead doc or audit. |
| 6 emails over 14 days | Current sequence is **5** emails (nurture_stage 0..4). Task specifies 6 emails (Day 0, 2, 4, 7, 10, 14). | **Extend** to 6 emails and adjust schedule (Day 0, 2, 4, 7, 10, 14). |
| If convert → stop sequence | Already: convert_lead / merged / status change stops nurture (should_skip_nurture checks status, merged, etc.). | Verify and document; no change if already stopping on convert. |
| If no open after 3 emails → resend best-performing subject | Not implemented | **Advanced**: requires open tracking (Postmark/webhook) and a "best subject" variant store. Phase 2. |
| Tags: pricing_viewed, demo_interested | Not in lead doc | **Add** optional tags or **source_metadata** fields when tracking pricing/demo clicks (e.g. from frontend or UTM). Backend can set lead.tags or lead.source_metadata.pricing_viewed when event received. |

**Recommendation:** (1) Add **checklist_download** tag and **checklist_nurture_v1** sequence identifier when starting checklist nurture. (2) Extend to 6 emails with Day 0, 2, 4, 7, 10, 14 and align subject/body with task copy. (3) Leave "no open after 3 → resend" and pricing_viewed/demo_interested for Phase 2 once open tracking and event pipeline exist.

---

## CONFLICTS AND SAFEST OPTIONS

1. **"Submissions (type=lead)" vs leads collection**  
   **Resolution:** Use **leads** collection everywhere. Do not create a new "submissions" aggregation for type=lead; admin_submissions already maps type=lead to leads.

2. **"submission.metadata.utm" vs lead.utm_source**  
   **Resolution:** Use **lead.utm_source** (and utm_medium, etc.) for attribution. Optionally also write a normalized **metadata.utm** on lead for future consistency; not required for Phase 1.

3. **Two funnel definitions (event funnel vs marketing funnel)**  
   **Resolution:** **Keep both.** Do not change existing overview/funnel. Add **GET /api/admin/analytics/marketing-funnel** returning: kpis (visitors placeholder, leads_count, trials_count, paid_count, conversion_rate, mrr), funnel (leads, trial_started, portal_activated, paid), source_breakdown (by utm_source), conversion_timing (avg_days_lead_to_trial, avg_days_trial_to_paid), and optionally nurture_conversions placeholder.

4. **Trials definition**  
   **Resolution:** **trials_count** = clients with subscription_status in (`TRIALING`, `trialing`). **paid_count** = clients with subscription_status = `ACTIVE` (and optionally PAID if used). If Stripe sends "trialing" and later "active", this matches.

5. **Lead score vs intent_score**  
   **Resolution:** Keep **intent_score**. Add **lead_score** (0–100) as a separate, computed field (from intent_score + optional portfolio/urgency/tags). Use lead_score for "Lead Quality" in funnel dashboard and badge in leads table.

6. **MRR source**  
   **Resolution:** If recurring amounts per plan are in plan_registry or config, compute MRR from clients (subscription_status=ACTIVE) × monthly amount per billing_plan. Else expose **placeholder** or use sum of orders revenue in period as approximation until Stripe/subscription data is stored.

---

## IMPLEMENTATION ORDER (recommended)

1. **Backend: GET /api/admin/analytics/marketing-funnel**  
   - Query params: from_date, to_date, period (7d, 30d, 90d).  
   - Return: kpis (visitors placeholder, leads_count, trials_count, paid_count, conversion_rate, mrr placeholder or computed), funnel (4 stages), source_breakdown (from leads.utm_source), conversion_timing (avg_days_lead_to_trial, avg_days_trial_to_paid).  
   - Use require_owner_or_admin.  
   - Data: leads (created_at, utm_source), clients (created_at, subscription_status, lead_id or match by email), portal_users (client_id), orders/billing for MRR if available.

2. **Frontend: Marketing Funnel section**  
   - Under Admin → Analytics: new tab or route "Marketing Funnel" that calls the new endpoint.  
   - Date filter (7d, 30d, 90d, custom), KPI cards, funnel viz, source table, conversion timing, export CSV.  
   - Mobile responsive; Admin/Owner only (same as analytics).

3. **Lead score**  
   - Backend: compute lead_score (0–100) from intent_score + optional fields; write to lead (e.g. lead_score or metadata.lead_score). Either on lead create/update or on-demand when loading marketing-funnel / leads list.  
   - Frontend: AdminLeadsPage — add Lead Score badge column (High/Medium/Low).

4. **Nurture alignment**  
   - Add checklist_download tag and checklist_nurture_v1 when starting checklist sequence.  
   - Optionally extend to 6 emails (Day 0, 2, 4, 7, 10, 14) and align copy with task.  
   - Defer "no open after 3 resend" and open/click metrics to Phase 2.

5. **Export CSV**  
   - GET /api/admin/analytics/marketing-funnel/export?same params, return CSV (summary + funnel + source breakdown).

6. **Section 6 (nurture metrics)**  
   - Phase 2: open/click from message_logs; "Conversions influenced by nurture" in marketing-funnel response.

---

## FILES TO TOUCH (minimal)

- **Backend:** `routes/analytics.py` (add marketing-funnel and export); optionally `services/lead_service.py` (lead_score computation); `services/lead_nurture_service.py` (tags, 6th email if desired).  
- **Frontend:** New component or section for Marketing Funnel (e.g. under `AdminAnalyticsDashboard.js` as tab, or `AdminMarketingFunnelPage.js` + route); `AdminLeadsPage.js` (lead score badge).  
- **Docs:** This audit; optionally update `docs/SUBMISSIONS_PIPELINE.md` or analytics docs if you add metadata.utm or lead_score to lead schema.

No changes to existing overview/funnel/conversion-funnel endpoints or their current UI behaviour.
