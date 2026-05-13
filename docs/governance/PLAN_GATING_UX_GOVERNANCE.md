# Plan gating & upgrade discoverability — UX governance (client portal)

**Document type:** Presentation and UX hierarchy rules only.  
**Authority:** Does not change entitlements, enforcement, pricing, Stripe mappings, plan codes, API contracts, scoring, workflows, async semantics, routing, or backend permissions.

**Related:** [Design system governance](./DESIGN_SYSTEM_GOVERNANCE.md) §13, [Presentation language governance](./PRESENTATION_LANGUAGE_GOVERNANCE.md).

---

## 1. Purpose

- Preserve **honest** discoverability of higher-tier capabilities without creating a “crippled product” perception for Solo and lower tiers.
- Reduce cognitive load and hostility while keeping **backend truth** visible (limits, 403s, async recalculation remain authoritative).

---

## 2. Approved gating language (examples)

Use **scale**, **operational maturity**, **portfolio growth**, **automation**, and **collaboration** framing:

- “Included with the {tier} plan for portfolio-scale workflows and optional automation.”
- “Designed for larger portfolios / multi-property operations.”
- “Recommended when you add portfolio-scale automation.”
- “Advanced reporting for growing landlord operations.”
- “Tenant collaboration tools for larger operations.”
- “View plans in Billing” / “Compare plans in Billing” (neutral, factual).

Job gating (compliance / maintenance):

- Title: “Designed for portfolio-scale job workflows” (or equivalent calm headline).
- Body: clarify what remains **available on the current plan** (upload evidence, manage requirements, log issues).

Property limits:

- “Portfolio capacity for your plan” — state numeric limits clearly; avoid red destructive styling for a **plan boundary** (not a safety failure).

---

## 3. Forbidden wording & patterns

**Avoid:**

- “Locked feature”, “Upgrade required” (as headline or toast), “Not available on your plan” (punitive tone).
- Fake urgency (“Act now”, “Don’t miss out”), fear (“You are non-compliant until you upgrade” — **never** tie upgrade to legal guarantee).
- Implying upgrade **guarantees** compliance, verification, elimination of risk, or replacement of landlord judgement.
- Giant red lock banners, stacked modal + aggressive error toast for the same gate.
- Salesy manipulation or entitlement shaming.

---

## 4. CTA hierarchy rules

1. **Primary CTA:** Operational task completion or next honest step (upload, log issue, view requirements, continue work, back to dashboard).
2. **Secondary CTA:** Optional tier discoverability — at most one, typically “View plans in Billing” as outline or ghost.
3. **Never reverse** this order on high-stress or remediation-adjacent flows.

Pure upgrade modals (no operational escape): a single neutral path to Billing is acceptable; dismiss/continue is primary when `onDismiss` is provided.

---

## 5. Discoverability principles

- **One calm message** per surface where possible: headline + short supporting copy + **one** billing/discoverability CTA.
- **Non-salesy, enterprise-calm** tone — operational trust over hype.
- **No fake access:** UI must not imply features work when API returns 403 or `feature_enabled: false`.
- **Authoritative limitations stay visible** — rephrase, don’t hide caps or denial reasons from the backend.

---

## 6. High-stress workflow rules

Applies to uploads, overdue workflows, evidence submission, renewals, risk resolution, job completion, and similar:

- Do **not** lead with billing CTAs or error-tier toasts for plan eligibility.
- Prefer **modal or inline** calm copy; avoid **toast.error** for expected plan boundaries when a structured surface exists or `toast.info` / `notify` minor tier is enough.
- If a gated capability appears inside these flows, move heavy discoverability to **overview / settings / post-success** where possible; keep the stressed path **completable**.

---

## 7. Solo-respect principles

- Solo should feel **complete** for core compliance operations.
- Avoid “toy plan” signals: excessive disabled chrome, empty modules that look broken, repeated lock icons in nav.
- Prefer **educational, aspirational** cards for advanced modules (maintenance automation, webhooks, white-label, advanced extraction) without unlocking backend behaviour.

---

## 8. Operational trust & async honesty

Copy and layout must **not** imply that upgrading:

- Guarantees compliance outcomes or regulator-grade finality.
- Automates legal responsibility or professional judgement.
- Guarantees verification or instant score finality.

Preserve existing patterns for pending recalculation, evidence review, propagation delays, and authority boundaries.

### 8.1 `propagation_notice` (L-009) — client display scope

When the API returns optional `propagation_notice` on document mutations, the **standard client** may show a **read-only** dismissible callout using the **server-provided `message`** (no paraphrase that weakens deferral semantics). Surfaces in-repo: **Documents** (upload + apply-extraction) and **Bulk upload** (ZIP + multi-file). This is **informational honesty**, not a replacement for KPI-authoritative requirement rows or persisted headline score semantics (`COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`).

### 8.2 Workspace framing (support-burden reduction)

Short **orientation** copy (headers, one-line descriptions, empty states) may clarify **which surface is for what** (e.g. Today vs Dashboard) and **async boundaries** (upload → confirm → recalc), provided it stays calm, non-marketing, and does not override plan-gating rules in §2–7. Implementation hub: `frontend/src/utils/workspaceOrientationCopy.js`.

---

## 9. Upgrade discoverability standards

- Reuse **`GovernedUpgradeDiscoverCard`**, **`DiscoverabilityHint`**, **`ScaleAutomationCallout`**, **`ExpansionCapabilityCard`**, and **`GrowthCapabilityPanel`** (`frontend/src/components/client/PlanGatingDiscoverability.jsx`) for consistency.
- **`UpgradePrompt`** variants should use neutral/slate chrome; avoid amber “warning” treatment for normal tier boundaries.
- Billing deep links may continue to use `buildSafeQueryPath('/settings/billing', { upgrade_to: ... })` — no change to routing contracts here.

---

## 10. Mobile gating standards

- Full-width primary operational buttons first; billing discoverability below the fold is acceptable.
- Avoid modals that trap scroll on small viewports; use existing portal modal scroll classes.
- Same CTA hierarchy as desktop — operational tap target first.

---

## 11. Enterprise calmness

- Prefer **layers / neutral iconography** over **locks** for tier discoverability.
- Limit **Electric Teal** on primary buttons to operational completion or single intentional discoverability where no operational alternative exists.
- Align with brand tokens in `DESIGN_SYSTEM_GOVERNANCE.md`.

---

## 12. Discoverability budgeting & anti-fatigue

**Goal:** Healthy feature awareness without “constant subtle upsell” or psychological exhaustion.

**Rules:**

- **One primary discoverability slot** per major viewport region (e.g. do not show `UpgradeRequired` + full `UpgradePrompt` + header billing CTA for the same reports intent).
- **Avoid stacking** a full discoverability card, a second marketing preview card, and a lock-heavy header control on one screen — merge, collapse (`GrowthCapabilityPanel`), or downgrade to **`DiscoverabilityHint`**.
- **Dashboard budget:** When a plan comparison / next-tier strip is visible, **suppress** parallel upgrade nudges and redundant “capacity” CTAs that duplicate Billing — one calm path to Billing is enough.
- **Session / path:** Do not repeat the same long-form upgrade card on every adjacent page; use **contextual** hints on the natural surface (Reports → reports; Integrations → integrations; Notifications → SMS).

**Reference components:** `DiscoverabilityHint`, `ScaleAutomationCallout`, `ExpansionCapabilityCard`, `GrowthCapabilityPanel`, `GovernedUpgradeDiscoverCard` — `frontend/src/components/client/PlanGatingDiscoverability.jsx`.

---

## 13. Discoverability hierarchy (presentation types)

| Type | Use when | Weight |
|------|-----------|--------|
| **Passive** | Optional education, non-blocking | Collapsed `GrowthCapabilityPanel`, footnote, inline sentence |
| **Contextual** | User is on the natural surface for the capability | `DiscoverabilityHint`, `ScaleAutomationCallout` |
| **Operational** | Gate blocks an action but workarounds exist | `PlanRestrictedJobModal` (ops first, Billing ghost) |
| **Expansion** | First visit to a gated module or dedicated settings | `GovernedUpgradeDiscoverCard` or `UpgradePrompt` card **once** |

---

## 14. Mobile discoverability limits

- Same budgeting as desktop; **prefer progressive disclosure** (`details` / collapsible) so discoverability does not consume the first screen above operational actions.
- **No** repeated billing CTAs while scrolling a single view — keep **one** text link or one outline button per screen for tier discovery.

---

## 15. Change control

- Changes to this document should accompany PRs that touch plan-gated **presentation** in the client portal.
- Any PR that changes **enforcement** or **entitlements** is out of scope for this governance path and must be reviewed under product/compliance process separately.

**Owner:** Frontend + product copy liaison.  
**Last updated:** 2026-05-13 (L-009 read-only propagation on Documents/Bulk upload; discoverability budgeting; governance cross-refs).
