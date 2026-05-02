# Unified Compliance Work Queue — tenant wireframe & copy spec (v1)

**Product value gap:** PVG-001  
**Companion:** `UNIFIED_COMPLIANCE_WORK_QUEUE_DESIGN.md` (authority, DTO, scope lock)  
**Aligns with:** `PROPERTY_COMPLIANCE_OS_GAP_AND_RETENTION_AUDIT.md` (trust, continuity, cognitive load — no false completeness)

**Document type:** UX + copy specification for **tenant** client implementation. **Not** runtime code.

---

## 1. Page purpose

**Primary job:** Give the tenant a **single, sortable, filterable list** of open compliance and operational work that already exists in the priority/unified pipeline — so users can answer **“What needs attention across my properties?”** without stitching Today, Command Centre, and property pages mentally.

**Honest scope (v1):**

- This page is a **work queue**, not a **compliance verdict** for the whole portfolio (headline score remains on dashboard / score surfaces per Stream B honesty).
- Actions are **the same** primary routes as Today/unified tasks (resolver-backed or operations URLs per Stream D) — **no new shortcuts** and **no** raw gap `recommended_*` as primary CTA.
- **Secondary** surface: it does **not** replace Today (inbox) or Command Centre (snapshot) as the default home.

**One-line product string (optional hero subtext):**  
*“All open work in one list — same next steps as elsewhere, sorted the way you need.”*

---

## 2. Entry point / navigation label

| Element | Spec |
|---------|------|
| **Nav label (primary)** | **Work queue** (sentence case; avoid “Unified” in user-visible chrome — internal name stays UCWQ). |
| **Alternative if product prefers** | **Open work** — must be user-tested for clarity vs “Work queue.” |
| **Do not use in nav** | “Remediation,” “Correlation,” “Priority stream,” “Tasks v2” — internal or engineering terms. |
| **Dashboard entry** | **One click** from main client dashboard: text link or card, e.g. **“View work queue”** with short supporting line: *“See every open item by property and urgency.”* |
| **Deep link** | Route TBD by implementation (e.g. `/client/work-queue`); bookmarkable. |
| **Breadcrumb (if shell provides)** | `Home` → `Work queue` (or `Dashboard` → `Work queue`). |

**Relationship copy (small “?” or info popover near title, optional v1):**

- *“Your inbox (Today) is still where you snooze or dismiss items for your view. This list shows **all open work** you can sort and filter — it doesn’t replace your inbox.”*

---

## 3. Empty state copy

**When:** API returns **zero** rows after filters (not an error).

**Headline:**  
**You’re all caught up**

**Body:**  
*There’s no open work in this view right now. If you use **Today** to hide or snooze items, those items may still need action — check Today or your properties.*

**Primary button:**  
**Go to Today** (or **Open Command Centre** if product prefers CC-first — pick one default).

**Secondary link:**  
**Back to dashboard**

**When:** True empty (no items at all, no filters applied) — same copy is acceptable; add one line if distinguishable:  
*Open work will appear here when you have compliance or operational items to complete.*

**Error / load failure:** Not empty state — use standard app error pattern + retry; do not claim “caught up.”

---

## 4. Row layout (v1)

**Layout principle:** **One primary row** visible without expand; **expand** (chevron / “Details”) reveals IDs and optional secondary link — **no** score strip in v1.

### 4.1 Default row (collapsed)

ASCII wireframe (logical reading order **top → bottom, left → right**):

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Urgency badge]  Title line (single line, truncate with ellipsis)        │
│                  Subtitle / property line (property name + address chip)  │
│                  Status line (closure_summary_user — one line, muted)     │
│                                                        [Primary button]   │
└──────────────────────────────────────────────────────────────────────────┘
```

| Zone | Content | Source |
|------|---------|--------|
| **Left: urgency** | Pill/badge — see §5 | `urgency_band` |
| **Title** | Task/priority title from unified row | `title` |
| **Subtitle** | Property: **{name}** · optional short context from `subtitle` | `property_id` + `subtitle` |
| **Status line** | Single sentence — see §6 | `closure_summary_user` |
| **Right: action** | One **primary** button | `primary_action_label` + `primary_action_url` / handler |

**Inbox overlay hint:** If `show_inbox_overlay_note` is true, show a **small text** under status line (not a second button):  
*“Snoozed or hidden in Today — still may need action.”* (see §6)

### 4.2 Expanded row (optional v1)

- **Related IDs** (for power users): requirement, gap, signal, WO, issue, invoice — **collapsed** in `<details>` or accordion, **not** in default view.
- **Secondary CTA** only if unified task already exposes secondary — mirror Today behaviour; **do not invent** a second resolver path.

---

## 5. Urgency badge copy

**Three badges only** — map from design `urgency_band`:

| `urgency_band` | Badge text (max ~2 words) | Visual note (product + design system) |
|----------------|---------------------------|----------------------------------------|
| **Urgent** | **Urgent** | Highest emphasis (e.g. destructive or strong accent — follow design tokens). |
| **Soon** | **Soon** | Medium emphasis. |
| **Watch** | **Watch** | Lowest emphasis; still visible — not “informational greyed out” to the point of invisible. |

**Tooltip / `aria-label` on badge (long form):**

- Urgent: *“Needs attention now — overdue, breached SLA, or high severity.”*
- Soon: *“Needs attention in the near term.”*
- Watch: *“Lower immediate pressure — still open.”*

**Do not** show internal `_urgency_level` strings (`critical`, `high`) to users.

---

## 6. Closure / status line copy

**Field:** `closure_summary_user` — **one** line, **muted** body text, max **~120 characters** where possible; truncate with “…” + expand for full line if needed.

**Templates (pick one per row state — assembler maps from existing truth):**

| Situation | Suggested line |
|-----------|----------------|
| Open compliance gap / obligation not met | **“Compliance action needed.”** |
| Requirement compliant / gap resolved for item | **“Cleared for compliance.”** or **“No open compliance issue for this item.”** |
| WO / issue active (operational) | **“Operational follow-up — contractor or maintenance.”** |
| Risk signal (risk layer only) | **“Portfolio risk — review recommended.”** (does not claim gap closed) |
| Inbox-only overlay (`show_inbox_overlay_note`) | **“Snoozed or hidden in Today — not resolved.”** |

**Hard rules:**

- Never use **“Complete”** or **“Done”** for inbox dismiss/snooze alone.
- Never imply **statutory compliance** from **risk dismiss** or **WO complete** without compliance template above.

**Page-level help (link “How this list works” or inline once):**

1. *Hiding an item in Today doesn’t clear a compliance obligation.*  
2. *Finishing a job or closing an issue doesn’t always mean every compliance check is satisfied.*

---

## 7. Action button rules

| Rule | Detail |
|------|--------|
| **Single primary** | One **primary** button per row; label = `primary_action_label` from unified task (after resolver/overlay). |
| **Requirement-backed** | Must use **canonical** `take_action` path — same as Property Detail / Today when `metadata.take_action` present. |
| **Risk / WO / issue / approval** | Use **operations** URL behaviour from server — **do not** route risk through requirement resolver. |
| **Forbidden** | Primary label/URL from **raw** `compliance_gaps.recommended_*` when resolver overlay exists (Stream D R2). |
| **Disabled state** | **Avoid** disabled primary without explanation. If URL missing, show **“View details”** to property/requirement fallback **only** if server provides fallback — never dead click. |
| **Secondary action** | Only if present on unified task; **not** required for v1 minimal row. |

**Button verb guidance:** Prefer server-provided label; do not override with “Fix compliance” unless server sends it.

---

## 8. Filters and sorting

### 8.1 Filters (v1)

| Filter | Control | Options |
|--------|---------|---------|
| **Property** | Dropdown or searchable select (multi-property clients) | **All properties** + each property with ≥1 row in current dataset |
| **Urgency** | Segmented control or checkboxes | **All** · Urgent · Soon · Watch |
| **Type** (source_system coarse) | Optional multi-select or simple dropdown | **All** · Compliance · Risk · Work order · Issue · Approval *(labels user-friendly; map to `source_system` in impl)* |

**v1:** **No** free-text search (deferred v2).

### 8.2 Sorting

| Sort | Default | Notes |
|------|---------|-------|
| **Default** | **Most urgent first** — reuse unified `_impact_score` ordering from API | Same relative order users expect from Today priority |
| **User toggles (optional v1)** | Property A–Z · Oldest first | If shipped, persist in session only |

**Expose sort** as a simple dropdown: **“Sort: Recommended (urgency)”** as default.

---

## 9. Mobile layout

| Requirement | Spec |
|-------------|------|
| **Stack** | Urgency badge + title + subtitle + status + **full-width primary button** (touch target ≥ 44px height). |
| **Truncation** | Title **2 lines max** then ellipsis; status line **2 lines max**. |
| **Filters** | **Bottom sheet** or **full-screen overlay** — not wide horizontal scroll of chips only. |
| **Expand** | Tap row to expand details (or chevron) — avoid hover-only. |
| **Sticky** | Optional sticky **filter/sort** bar under header when scrolling long lists. |

---

## 10. What not to show in v1

Aligned with `UNIFIED_COMPLIANCE_WORK_QUEUE_DESIGN.md` **Explicit v2 deferrals** and audit **trust** bar:

| Do not show | Reason |
|-------------|--------|
| Per-row **compliance score** or **score delta** | PVG-004 / v2; avoid implying this list is “the score.” |
| **tenant_request / tenant_message** rows | v2 + Stream D D-P06 |
| Raw **gap recommended URL** as primary | Rule R2 |
| **Internal** keys in default row (`gap_key`, `remediation_key`) | Power user expand only; optional |
| **Support correlation JSON** or “correlation view” language | Non-authoritative; support-only |
| **Three separate** jargon badges for closure | v1 uses **one** `closure_summary_user` line |
| **“Compliant”** for inbox dismiss | Trust-breaking |
| Full-text **search** | v2 |
| **Applicability** / “why this rule applies” | PVG-003 / v2 |

---

## 11. Accessibility notes

| Area | Requirement |
|------|-------------|
| **Urgency** | Badge **not** color-only — include text (“Urgent”) + `aria-label` with tooltip long form. |
| **Actions** | Primary button has **accessible name** = visible label; if icon-only forbidden for primary. |
| **Expand** | `aria-expanded` on row disclosure; keyboard **Enter/Space** to activate. |
| **List** | Use semantic **list** (`ul`/`li` or `role="list"`) for rows. |
| **Filters** | Focus order: filters → list; announce filter changes (polite live region optional). |
| **Motion** | Respect `prefers-reduced-motion` for expand/collapse. |

---

## 12. Implementation acceptance criteria

**Product / UX**

1. Nav label **Work queue** (or approved alt) appears in client chrome + **one** dashboard entry path.  
2. Empty state matches §3 when count is zero (filtered or unfiltered per product choice — document which).  
3. Each row shows **urgency badge** (§5), **title**, **property context**, **closure_summary_user** (§6), **one primary action** (§7).  
4. `show_inbox_overlay_note` shows the **inbox hint** copy when true — never as green “success.”  
5. **No** v1 elements from §10 ship in tenant UI.  
6. Help or inline copy covers **two** trust clarifications (inbox ≠ compliant; operational ≠ always compliant).

**Technical (ties to design doc)**

7. Data comes **only** from unified/priority pipeline — **no** parallel raw `compliance_gaps` reader for primary CTA.  
8. `urgency_band` derived per **Urgency Mapping v1** (`_urgency_level` → Urgent/Soon/Watch).  
9. Primary CTA respects **Rule R2** — contract/regression tests per `UNIFIED_COMPLIANCE_WORK_QUEUE_DESIGN.md` **Tests needed**.  
10. Sort default matches unified impact ordering; filter dimensions match §8.

**Accessibility**

11. Meets §11 checklist in QA pass.

---

## Document control

**Owner:** Product + UX (primary), engineering review for feasibility.  
**PVG:** PVG-001.  
**Next:** Product **sign-off** on this spec → engineering **In Implementation** for PVG-001 per `PRODUCT_VALUE_GAP_TRACKER.md`.
