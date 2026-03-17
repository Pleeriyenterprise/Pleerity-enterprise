# Pleerity Platform — User Value Audit

**Objective:** Evidence-based assessment of whether the platform answers the key questions that make it valuable enough for users to stay, pay, and rely on it. Strict and specific; no marketing language.

**Scope:** Client portal (landlord/user), admin/ops, and tenant flows. Based on actual implementation (routes, services, UI), not aspirations.

---

## 1. Executive summary

Pleerity has a **real compliance and operations backbone**: evidence-based scoring, requirements with status (overdue/expiring/missing), work orders with assign/status/invoice, risk signals with create-issue/create-WO, priority actions that rank next steps, and an explanation layer (“why it matters”, “recommended action”). **The platform can answer “am I compliant?” and “what’s missing or expiring?”** and can surface “what should I do next?” with links into the product.

**But the experience is fragmented.** Compliance lives on Dashboard + Compliance Score + Property detail; operations live under Operations (issues, work orders, approvals, risk signals, contractors); “next” lives in Priority actions and Action required cards. There is **no single inbox or task list** that unifies “do this next” with “mark done” and “see it through.” Several dashboard KPIs are **placeholders** (SLA breaches, This month’s spend, Contractor perf. all show “—”). Admin has **placeholder pages** (Ops Compliance, Ops Audit). **Financial and operational impact** (spend, cost of non-compliance, ROI of fixing items) is **not** answered in the UI. **Trust signals** (data freshness, automation health, confidence in recommendations) are weak or absent for the client user.

**Verdict:** The platform is **moderately value-complete** for a user who is willing to click through multiple sections and who already values compliance tracking. It is **not yet** a coherent “Property Compliance OS” that reduces mental load and answers “exactly what to do and how urgent” in one place. Retention risk is highest where the promise (“one place to stay compliant and run operations”) collides with empty tiles, placeholders, and scattered flows.

---

## 2. Value question audit table

| # | Question | Answered today? | Modules/screens that support it | Where it breaks down | Experience type |
|---|----------|-----------------|----------------------------------|----------------------|-----------------|
| **1** | **Am I compliant right now?** | **Yes, partially** | Client Dashboard (score/100, grade, risk band), Compliance Score page (portfolio + property trend, drivers), Property detail (requirement status, evidence). Backend: `compliance_scoring_service`, `compliance_scoring` (evidence-based). | Score is evidence-based only; no legal verdict. “Compliant” is implied by score/grade, not a single “Yes/No” headline. Property/portfolio split requires user to know where to look. | **Partial** — clear number and grade, but not a single definitive “You are / are not compliant” with one-click drill. |
| **2** | **What exactly is missing, expiring, overdue, or risky?** | **Yes** | Property detail (requirements table: status, impact, evidence), Compliance Score (drivers, breakdown), Dashboard (portfolio summary: overdue count, expiring soon, missing evidence), Risk signals (Operations), Priority actions (ranked list). Explanation engine for compliance alerts and risk. | List is spread: property-level requirements, portfolio summary, risk signals, priority actions. No single “master list” with due dates and one place to act. Urgent items are in Property detail and in Priority actions; duplication and navigation cost. | **Partial** — data exists and is accurate; presentation is multi-screen. |
| **3** | **What should I do next?** | **Yes** | Priority actions (client + admin): ranked list with title, description, recommended_url, recommended_action_label. Client Dashboard and Property detail show this list; links go to /properties/x, /operations/work-orders, /compliance-score, etc. | Next step is a **link**, not a task. No “mark done” or “snooze” in the priority list; no guarantee the linked page offers the one obvious action (e.g. “Upload document” → property evidence, but upload is on Documents/Evidence flow). Order is by priority score, not by due date or user context. | **Partial** — “what” is clear; “do it here and close the loop” is not. |
| **4** | **How urgent is it?** | **Partially** | Priority actions have `severity` (critical/high/medium/low) and `priority` (numeric) used for ranking. Risk signals have risk_level. Requirements have status (OVERDUE, EXPIRING_SOON, etc.). Property/dashboard show overdue and expiring counts. | Severity/urgency is **not** consistently visible in the client UI (e.g. priority list does not show “Critical” or “Due in 7 days”). No single “urgent vs not urgent” filter or badge across all item types. Due dates appear in requirement/evidence context, not in the priority action card. | **Partial** — urgency exists in the model and in some screens; not surfaced as a clear, consistent UX. |
| **5** | **Can I act on it directly inside the platform?** | **Yes, for many items** | Create work order (Property, Operations), assign contractor (WO drawer, contractor recommendation), upload/confirm evidence (Documents, Property Evidence), create issue/WO from risk signal (Risk Signals), approve/reject invoice (Approvals), record invoice from WO (client). | Some actions are “go to this page” then act (e.g. “Review compliance” → property); no inline “Upload” or “Create WO” from the priority list. Admin “View client” opens client panel (fixed); other admin actions use Link to ops routes. Contractor invoice submission is not in-platform (admin/client only). | **Partial** — core actions exist in-app; not all from a single “task” surface. |
| **6** | **Can I track the action from start to finish?** | **Partially** | Work order: create → assign → status updates → (optional) invoice → approval. Issue: create (e.g. from risk signal) → status updates → close/resolve. Evidence: upload → confirm expiry → score recalc. Risk signal → issue/WO link stored. | No **unified** timeline: issue timeline not in UI (audit exists); WO has status but no single “job timeline” with all events. “Priority action → I did it → it disappears from my list” is not implemented; list is recomputed from backend state, so completing an action can remove it, but there is no explicit “done” or progress indicator. | **Partial** — per-entity lifecycle exists; cross-entity and user-visible “from start to finish” is weak. |
| **7** | **Can I trust the platform’s recommendations and automation?** | **Partially** | Explanation engine: “why it matters” and “recommended action” for risk, compliance, contractor score. Contractor recommendation uses trade/credential/region and performance. Risk signals have reasons and recommended_action. Compliance alerts have legal context (e.g. gas safety). | No “confidence” or “last run” for risk/signals. Automation (scheduled jobs) is admin-side; client does not see “last score recalc” or “data as of.” Recommendations are rule-based and documented, but trust is implicit, not reinforced in UI. | **Partial** — explanations help; transparency and freshness are underused. |
| **8** | **Can I see the operational and financial impact of issues?** | **No** | Work order has optional cost_estimate_min/max (shown in WO detail). Dashboard has “This month’s spend” and “Contractor perf.” tiles but both show **“—”** (not populated). No portfolio spend, no “cost of non-compliance,” no impact of fixing vs not fixing. | Financial impact is **not** answered. Operational impact (e.g. “2 SLA breaches this month”) exists in backend/priority actions but **SLA breaches** KPI on dashboard is hardcoded “—”. | **Missing** — impact is not surfaced. |
| **9** | **Does the platform reduce my mental load and decision burden?** | **Partially** | Single dashboard with score, grade, portfolio summary, priority actions, and “Action required” (issues + risk signals). One place to see “next steps.” Setup checklist and “complete setup” banner. | Mental load is **increased** by fragmentation: Dashboard vs Compliance Score vs Property vs Operations (issues, WOs, approvals, risk, contractors). “Open issues” tile is actually **work orders** with OPEN/ASSIGNED (misleading). No single “my tasks” or “inbox” that aggregates and lets user tick off. | **Partial** — reduces load for “see score and next steps”; increases load for “do everything in one flow.” |
| **10** | **Does the platform feel complete enough that I would keep using it instead of leaving?** | **Uncertain** | Core loops exist: score → requirements → evidence; risk → issue/WO → contractor → invoice → approval; priority actions → links. Feature gating (maintenance_workflows, predictive_maintenance, contractor_network, invoicing) means some users see fewer capabilities. | Empty KPIs (“—”) and placeholder admin pages (Ops Compliance, Ops Audit) signal incompleteness. No financial or impact view weakens “why pay for this.” For power users, the platform can replace spreadsheets and email for compliance + ops; for light users, the multiplicity of sections may feel heavy without a clear “one place to work.” | **Partial** — viable for engaged users; risk of “promise > delivery” for others. |

---

## 3. Biggest user-value strengths

1. **Evidence-based compliance score** — Deterministic, stored, with trend and “what changed”; portfolio and property level; grade and risk band. Gives a real answer to “how compliant am I?”
2. **Requirements and evidence** — Clear status (overdue, expiring soon, missing, compliant), impact on score, and evidence tab with upload/confirm; explanation engine adds legal context and recommended action.
3. **Priority actions engine** — Ranked, cross-domain (compliance, certs, missing docs, risk, work orders, approvals); client and admin; links into the product. Surfaces “what should I do next?”
4. **Risk → action** — Create issue and create work order from risk signal, with link back; explanation for “why it matters” and what to do.
5. **Work order and approval chain** — Create WO, assign contractor (with recommendation and “why this matters”), status flow, record invoice from WO, approve/reject. End-to-end chain is implemented.
6. **Explanation layer** — Risk, compliance alert, and contractor score each have “why it matters” and “recommended action,” which supports trust and clarity.
7. **Admin operational priorities** — Filter by client (with CRN + name), strict client filter when one client selected, “View client” and other actions stay in-app (Link/button fixes).

---

## 4. Biggest retention risks

1. **Empty or misleading KPIs** — “SLA breaches,” “This month’s spend,” “Contractor perf.” on client dashboard all show “—”. “Open issues” counts work orders in OPEN/ASSIGNED, not maintenance issues. Users infer the product is incomplete or broken.
2. **No single “inbox” or task list** — Next steps are in Priority actions and Action required, but there is no unified “my tasks” with due dates, one-click action, and “done.” Users must remember which screen to use.
3. **Admin placeholders** — `/admin/ops/compliance` and `/admin/ops/audit` are placeholder pages (“will show content when the module is implemented”). Admins see the platform as unfinished.
4. **No financial/impact view** — No portfolio spend, no “cost of non-compliance,” no ROI of fixing items. Landlords cannot answer “what is this costing me?” or “what do I gain by staying compliant?”
5. **Fragmented flows** — Compliance (Dashboard, Compliance Score, Property), Operations (Issues, Work orders, Approvals, Risk signals, Contractors), and Priority actions live in different sections. Completing “one thing” often requires several clicks and context switches.
6. **Trust and freshness** — No visible “data as of” or “last run” for score or risk; no client-facing automation health. Reduces confidence in recommendations.

---

## 5. Where the platform still feels fragmented

- **“Compliance”** is Dashboard + Compliance Score page + Property detail (requirements + evidence). There is no single “Compliance” screen that shows status + list + actions in one view.
- **“Operations”** is a menu with Issues, Work orders, Approvals, Risk signals, Contractors. Each is a separate list/detail; no unified “operations inbox” or “jobs to do.”
- **“What to do next”** is in Priority actions (and partly in Action required), but acting means leaving the list and going to another URL; there is no “do it here” or “mark done” in the list.
- **Admin** mixes full implementations (dashboard, risk dashboard, maintenance, contractors) with placeholders (Ops Compliance, Ops Audit), so the “Ops” area feels half-built.
- **Client vs plan** — Feature flags (maintenance_workflows, predictive_maintenance, contractor_network, invoicing) mean different users see different tiles and flows; the value proposition is not consistent across segments.

---

## 6. Highest-leverage improvements to increase satisfaction and retention

1. **Populate or remove dashboard KPIs** — Either wire “SLA breaches,” “This month’s spend,” and “Contractor perf.” to real data, or remove/hide them. Fix “Open issues” to show actual open issues (or rename to “Open work orders”) so the dashboard is truthful.
2. **Single “Tasks” or “Inbox” view** — One list (or filtered view) that merges priority actions, overdue/expiring requirements, and open issues/WOs with due date and one primary action (e.g. “Upload,” “Create WO,” “Approve”). Reduces mental load and answers “what should I do next?” in one place.
3. **Replace or implement admin Ops Compliance and Ops Audit** — Either implement minimal content (e.g. compliance summary, audit log list) or replace with “Coming soon” and a clear roadmap so admins don’t feel the product is broken.
4. **Surface urgency consistently** — Show severity or “Due in X days” on priority action cards and in any task list; add an “urgent” filter or badge so “how urgent is it?” is visible at a glance.
5. **One financial metric** — At least “This month’s spend” or “Spend YTD” from invoices/approved amounts so the “financial impact” question has one concrete answer.
6. **Trust and freshness** — “Score as of …” and “Risk signals updated …” (or “Last run …”) on dashboard or score/risk sections to reinforce that data is current and automation is running.

---

## 7. Final judgment

- **Not yet value-complete** — The platform would be here if core loops (score, requirements, WO, approvals) were missing or broken. They are implemented and usable.
- **Strongly value-complete** — The platform would be here if one place answered all 10 questions with minimal friction, no placeholders, and clear impact. It does not.

**Conclusion: Moderately value-complete.**

The platform delivers real value for “am I compliant?”, “what’s missing/expiring?”, and “what should I do next?”, and users can act (upload, create WO, assign, invoice, approve) and track (WO/issue lifecycle, evidence) inside the product. The explanation layer and priority actions improve clarity and trust. However, fragmentation (many sections, no single task list), empty KPIs, admin placeholders, and missing financial/impact views create retention risk. Users who are motivated to stay on top of compliance and operations can rely on it; users who expect a single, obvious “control centre” and visible impact may feel the promise is stronger than the experience. Prioritising the highest-leverage improvements above would move the product toward a coherent Property Compliance OS without requiring a full redesign.
