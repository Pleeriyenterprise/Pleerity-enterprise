# Presentation language governance (Compliance Vault Pro / Pleerity Enterprise)

**Scope:** User-visible copy only (labels, badges, tables, filters, empty states, helper text).  
**Out of scope:** Backend enums, database values, API contracts, routes, feature keys, orchestration identifiers, scoring, authority semantics, async logic.

This is **presentation-layer governance** — not a terminology redesign of the product model.

---

## Core rules

1. **No raw snake_case or kebab-case in UI**  
   Rendered text must not show tokens like `accepted_unverified`, `pending_sync`, or `compliance_job`.

2. **No raw backend enums in UI**  
   If the API returns a machine token, map it through a **central formatter** before display.

3. **Prefer server-provided human labels when trustworthy**  
   If the API exposes `*_label` fields intended for display, prefer those; still run through sanity checks so obvious schema leakage is not shown verbatim.

4. **Async honesty**  
   Do not hide pending verification, recalculation, propagation delays, or evidence boundaries.  
   **Do** phrase them in calm, operational English (e.g. “Accepted (awaiting verification)”, “Compliance score update pending”).

5. **Admin vs client**  
   - **Client portal:** Short, landlord-readable, operational.  
   - **Admin:** May be more precise for operations, but **still** no raw enums, queue names, feature keys, or orchestration slugs in labels.

6. **Single source of truth for formatting**  
   Use `frontend/src/utils/presentationLanguage.js` (`operationalLabelForToken`, etc.) and existing domain helpers (e.g. `requirementIntelligenceLabels.js`, `presentDomain.js`) instead of ad-hoc `.replace(/_/g, ' ')` in components.

7. **L-009 propagation notices (`propagation_notice`)**  
   On document flows that return this field, render via `propagationNoticeForUi` + **`PropagationNoticeCallout`** (`frontend/src/utils/propagationNoticePresentation.js`, `frontend/src/components/client/PropagationNoticeCallout.jsx`). Prefer the **server `message`**; do not paraphrase into stronger certainty than the API states.

---

## Forbidden patterns in UI code

- `someValue.replace(/_/g, ' ')` as the **only** presentation (leaks unknown tokens and implies “good enough”).
- `value.replace('_', ' ').replace(/\b\w/g, …)` or other naive title-case chains on API tokens (brittle, duplicates formatter logic).
- Rendering `feature_key`, `risk_type`, `status`, or `event.action` directly when values are machine tokens.
- Title-casing internal acronyms without a glossary (prefer mapped labels).
- Page-local enum maps that duplicate `OPERATIONAL_LABEL_BY_KEY` (extend the central map instead).

### Anti-pattern examples

| Anti-pattern | Prefer |
|--------------|--------|
| Showing `sla_breached` | `operationalLabelForToken('sla_breached')` → “SLA deadline missed” |
| Filter `<option value="breached">Breached</option>` | Keep `value="breached"`; label via formatter (“SLA deadline missed”) |
| “SLA overdue” when the state is a missed deadline | “SLA deadline missed” (operationally precise, not softened) |

### Async-honest wording (approved tone)

Keep uncertainty visible where the system is still catching up: e.g. “Awaiting verification”, “Compliance score update pending”, “Updates still applying”, “Evidence review pending”. Do not rephrase these into false certainty (“Verified”, “Complete”, “Synced”) when the API state is still pending.

---

## Required patterns

- **Unknown token:** `operationalLabelForToken(value)` → canonical map or title-cased words as last resort.
- **Requirement / evidence / compliance:** Prefer `requirementIntelligenceLabels` helpers; extend shared maps there or in `presentationLanguage.js` instead of page-local maps.
- **Filters:** `value` sent to the API stays the machine token; **only** the `<SelectItem>` label uses formatters.

---

## Adding new labels

1. Add a canonical entry to `OPERATIONAL_LABEL_BY_KEY` in `presentationLanguage.js` **or** extend the appropriate specialised module (`requirementIntelligenceLabels.js`, etc.).  
2. For labels driven by `presentDomain.js` / `slaStateLabel` / `workOrderStatusLabel`, update **`backend/presentation/domain_labels.json`** (canonical); `npm run build` in the frontend runs `sync-domain-labels` and copies that file to `frontend/src/domain/domain_labels.json` — do not edit only the frontend copy or the next build will overwrite it.  
3. Add/extend a unit test in `presentationLanguage.test.js` or the module’s test file.  
4. Wire the UI to the formatter; **do not** change the value used in `===` comparisons or query params unless explicitly approved as a product change.

---

## Customer mental model & workspace orientation (presentation)

- **Purpose:** Reduce confusion between **Dashboard** (portfolio KPIs / trends), **Today** (operational inbox), **Command Center** (portfolio triage / verdict), **Requirements** (tracked obligations), **Documents** (evidence vault), and **score timing** (stored headline vs uploads), without tours, modal carousels, or marketing rewrite.
- **Rules:** Calm, operational English; preserve async honesty and authority boundaries (`backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`); do not imply instant score finality or legal certainty.
- **Hub:** `frontend/src/utils/workspaceOrientationCopy.js` — extend here rather than scattering duplicate intros across pages.
- **Companion:** Page-level confidence one-liners remain in `frontend/src/utils/confidenceUxCopy.js` where they add non-duplicative emphasis.

### Semantic families (evidence vs tokens)

Avoid implying **one English phrase = one API enum** across different domains:

| Family | Where it applies | Canonical client phrasing |
|--------|------------------|---------------------------|
| **Document vault file row** | `documentListStatusLabel` / Documents filters | File lifecycle: e.g. “Awaiting confirmation”, “Received (confirm to apply)”, “Confirmed” — vault-first, then scoring catches up. |
| **Operational token map** | `operationalLabelForToken` in `presentationLanguage.js` | Workflow / async tokens (e.g. `accepted_unverified`, `pending_verification`, `needs_confirmation`, propagation/recalc keys). Extend the map; do not duplicate ad hoc strings on filters. |
| **Requirement matrix / compliance state** | `requirementIntelligenceLabels.js`, `evidenceStatus.js`, resolver-backed rows | Obligation and evidence pipeline semantics; may differ from vault row wording by design when the API distinguishes user confirm vs staff review. |

When adding a new user-visible status, pick the **family** first, then add or reuse a formatter entry so support and client UI stay aligned.

---

## Review checklist (PRs)

- [ ] No new user-facing string built only from `replace(/_/g, ' ')`.
- [ ] New statuses enums have a formatter entry or documented deferral.
- [ ] Async / pending states remain visible, with honest wording.
- [ ] Admin screens do not expose raw orchestration or feature keys as labels.

---

## Related documents

- `DESIGN_SYSTEM_GOVERNANCE.md` — visual tokens and components.
- `src/utils/requirementIntelligenceLabels.js` — requirement workflow / evidence wording.
