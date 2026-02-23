# Dynamic Core Requirement Framework (UK Landlord) — Task Compliance Audit

**Task:** Implement dynamic core requirement framework for UK landlord properties.

**Audit scope:** Map each task requirement to current implementation; identify gaps, conflicts, and safest options. No implementation in this document.

---

## 1) Property attributes: has_gas_appliances, is_hmo, tenancy_active, furnished (bool|unknown)

| Task requirement | Current state | Location | Gap / conflict |
|------------------|---------------|----------|----------------|
| **has_gas_appliances** (bool\|unknown) | Not present. **has_gas_supply** (bool, default True) and **cert_gas_safety** ("YES"\|"NO"\|"UNSURE") exist. | `backend/models/core.py` Property: `has_gas_supply`, `cert_gas_safety`; `requirement_catalog.py` uses `cert_gas_safety == "YES"` for GAS_SAFETY_CERT. | **Naming / shape mismatch.** Task says "has_gas_appliances"; code uses has_gas_supply + cert_gas_safety. "unknown" could map to UNSURE or optional. |
| **is_hmo** (bool\|unknown) | **is_hmo** exists as **bool** (default False). No "unknown" value. | `backend/models/core.py` Property; `requirement_catalog.py`; PATCH property. | **Partial.** is_hmo present; task asks bool\|unknown (e.g. null/UNKNOWN). |
| **tenancy_active** (bool) | Used in **requirement_catalog.get_applicable_requirements()** via `property_doc.get("tenancy_active")` for tenancy docs. **Not on Property model** in core.py. | `backend/services/requirement_catalog.py` ~67–70; tests pass `tenancy_active` in property_doc. | **Gap.** Not a field on Property model; catalog expects it on the doc. Add to Property and to PATCH/provisioning if task requires it as first-class attribute. |
| **furnished** (bool\|unknown) | Not on Property model. **property_furnished** appears in intake/service_definitions (e.g. "Furnished"\|"Part-Furnished"\|"Unfurnished"), not in core Property. | `backend/services/service_definitions_v2.py`, `gpt_prompt_registry.py`. | **Gap.** Task asks for "furnished" on property; not in Property schema or requirement logic. |

**Conclusion:** Property model has is_hmo, has_gas_supply, cert_gas_safety; missing tenancy_active and furnished as first-class fields. has_gas_appliances is a naming variant of has_gas_supply/cert_gas_safety.

**Recommendation:**  
- **Option A:** Add **tenancy_active** (bool) and **furnished** (Optional[bool] or enum "Furnished"\|"Part"\|"Unfurnished"\|null) to Property model; expose in PATCH and intake. Align task "has_gas_appliances" with existing cert_gas_safety/has_gas_supply (document mapping) or add has_gas_appliances as alias/source.  
- **Option B:** Keep current fields; document that tenancy_active and deposit_taken are optional keys on property_doc (e.g. from intake) and that "has_gas_appliances" is represented by cert_gas_safety/has_gas_supply. Add furnished only if product needs it for requirement rules.

---

## 2) Generate property_requirements dynamically on: property creation, attribute update, provisioning

| Task requirement | Current state | Location | Gap / conflict |
|------------------|---------------|----------|----------------|
| **On property creation** | Requirements generated via **provisioning._generate_requirements()** when properties are created (create property, bulk import). | `backend/services/provisioning.py` _generate_requirements; `backend/routes/properties.py` create + bulk import. | **Done.** |
| **On attribute update** | Property PATCH updates attributes and triggers **compliance recalc** (enqueue_compliance_recalc) when APPLICABILITY_FIELDS change. It does **not** call _generate_requirements or add/remove requirement records. | `backend/routes/properties.py` PATCH ~213–238. | **Gap.** Requirements are not regenerated when attributes change; only score is recalculated. Task says "generate dynamically on attribute update" — could mean (a) recalc applicability only, or (b) add/remove requirement rows. |
| **On provisioning** | _generate_requirements runs during provisioning flow. | provisioning.py. | **Done.** |

**Conclusion:** Generation on creation and provisioning exists. "On attribute update" is only reflected in score applicability (catalog); requirement list is not regenerated.

**Recommendation:**  
- **Clarify:** "Generate dynamically" on attribute update — (1) only recompute which requirements apply for scoring (current behaviour), or (2) actually add/remove requirement records when e.g. is_hmo or has_gas_supply changes.  
- If (2): On PATCH of applicability-related fields, call _generate_requirements again (or a variant that adds/removes requirements by rule) and set applicability per requirement from current property attributes. Risk: existing user-set applicability (e.g. NOT_REQUIRED) could be overwritten; prefer merging with user overrides.

---

## 3) For each requirement: set applicability (REQUIRED/NOT_REQUIRED/UNKNOWN); do not penalise NOT_REQUIRED in score

| Task requirement | Current state | Location | Gap / conflict |
|------------------|---------------|----------|----------------|
| **Applicability on requirement** | **applicability** exists on Requirement (REQUIRED\|NOT_REQUIRED\|UNKNOWN); user set via PATCH requirement. Not set automatically from property attributes when requirements are generated. | `backend/models/core.py` Requirement; `backend/routes/properties.py` PATCH requirement; provisioning _create_requirement_if_not_exists does not set applicability. | **Partial.** Applicability is stored and editable; not derived from property attributes at generation time. |
| **Do not penalise NOT_REQUIRED** | **Done.** NOT_REQUIRED gives status_factor 1.0 for that key (excluded from penalty). | `backend/services/compliance_scoring.py` ~198–210; `is_included_for_calendar` excludes NOT_REQUIRED. | **Done.** |

**Conclusion:** NOT_REQUIRED is already excluded from score and calendar. Applicability is not auto-set from property attributes when requirements are created or when attributes change.

**Recommendation:** If "dynamic" includes deriving applicability from attributes: when generating or updating requirements, set applicability from rules (e.g. no gas → GAS_SAFETY_CERT applicability NOT_REQUIRED; is_hmo → PROPERTY_LICENCE REQUIRED). Use a single place (e.g. requirement_catalog or provisioning) to compute applicability from property_doc and write to requirement records; allow user override via existing PATCH.

---

## 4) Scoring formula per property: valid 70, timeliness 10, no overdue bonus 10, unknown penalty max 10, overdue penalty 20

| Task requirement | Current state | Location | Gap / conflict |
|------------------|---------------|----------|----------------|
| **Fixed component weights** (valid 70, timeliness 10, no overdue 10, unknown max 10, overdue 20) | **Different formula.** Score is a **weighted sum** of per-requirement status_factor (0, 0.1, 0.5, 0.8, 1.0) by BASE_WEIGHTS (e.g. GAS 30, EICR 25, EPC 15, …), normalised to 0–100. No separate "valid", "timeliness", "no overdue bonus", "unknown penalty", "overdue penalty" components. | `backend/services/compliance_scoring.py` compute_property_score; `document_status_service.STATUS_TO_FRACTION`. | **Conflict.** Task specifies a component-based formula (70+10+10−10−20 style); implementation is weighted sum of requirement-level status factors. |

**Conclusion:** Task asks for an explicit 70/10/10/10/20 breakdown; current code uses a different, requirement-weighted model.

**Recommendation:**  
- **Option A:** Implement the task formula literally: compute a single property score from (valid_component = 70 * valid_ratio) + (timeliness = 10) + (no_overdue_bonus = 10 if no overdue else 0) − (unknown_penalty up to 10) − (overdue_penalty up to 20). Requires defining "valid", "timeliness", "unknown" in terms of requirements/dates.  
- **Option B:** Keep current weighted model; document that "valid/timeliness/overdue/unknown" are reflected in the existing status_factor and weights, and that the task numbers are a different spec. If product insists on the 70/10/10/10/20 breakdown, implement Option A in a new scoring path and feature-flag or replace.

---

## 5) Portfolio score = average(property_scores)

| Task requirement | Current state | Location | Gap / conflict |
|------------------|---------------|----------|----------------|
| **Portfolio = average(property_scores)** | **Weighted average** by E(p) = 1 + 0.5*is_hmo + 0.2*(bedrooms>=4) + 0.2*(occupancy != single_family). Not a simple average. | `backend/services/compliance_scoring.py` portfolio_score_and_risk ~327–336. | **Conflict.** Task says average(property_scores); code uses weighted average by property "importance" E(p). |

**Conclusion:** Portfolio is not a simple average.

**Recommendation:** If product requires strict "average(property_scores)", change portfolio_score_and_risk to sum(scores)/len(scores). If current weighting is intentional (e.g. HMO/larger properties count more), document and keep; otherwise align with task.

---

## 6) Calendar: confirmed_expiry_date only; exclude NOT_REQUIRED; expiring soon = 30 days default

| Task requirement | Current state | Location | Gap / conflict |
|------------------|---------------|----------|----------------|
| **Use confirmed_expiry_date only** | Calendar uses **get_effective_expiry_date**: confirmed **else** extracted **else** due_date. So extracted and due_date are used when confirmed is absent. | `backend/utils/expiry_utils.py`; `backend/routes/calendar.py`. | **Conflict.** Task says "confirmed_expiry_date only"; current design (and DOCUMENT_UPLOAD_EXPIRY_REFACTOR_AUDIT) kept "effective" date so items with only extracted date still show. |
| **Exclude NOT_REQUIRED** | **Done.** is_included_for_calendar returns False for NOT_REQUIRED. | expiry_utils; calendar routes. | **Done.** |
| **Expiring soon window = 30 days default** | **Done.** EXPIRING_SOON_DAYS = 30 in expiry_utils; used in get_computed_status and calendar. | `backend/utils/expiry_utils.py` ~12–13. | **Done.** |

**Conclusion:** NOT_REQUIRED and 30-day window are correct. "confirmed_expiry_date only" conflicts with current effective-date rule and with the previous refactor (document upload audit chose Option B: keep effective date).

**Recommendation:** Reuse DOCUMENT_UPLOAD_EXPIRY_REFACTOR_AUDIT decision: if product explicitly requires "calendar only from confirmed", add a calendar-only branch that includes events only when requirement has confirmed_expiry_date set; otherwise keep effective date and document. Align with same product decision for reminders.

---

## 7) Dashboard: provisional score banner if any REQUIRED item missing confirmed expiry; hide when resolved

| Task requirement | Current state | Location | Gap / conflict |
|------------------|---------------|----------|----------------|
| **Provisional score banner** when any REQUIRED requirement has no confirmed_expiry_date | **Not implemented.** Dashboard has an "UNKNOWN applicability" banner (any requirement applicability === UNKNOWN). No banner for "REQUIRED but missing confirmed expiry". | `frontend/src/pages/ClientDashboard.js`; UNKNOWN banner ~214–225. | **Gap.** Need a separate banner: e.g. "Your score is provisional until you confirm expiry dates for tracked items" when there exists a requirement with applicability === REQUIRED and !confirmed_expiry_date. |
| **Hide banner when resolved** | N/A until banner exists. Logic would be: hide when no REQUIRED requirement lacks confirmed_expiry_date. | — | — |

**Conclusion:** No provisional-score banner based on missing confirmed expiry for REQUIRED items.

**Recommendation:** Add a dashboard check: if any requirement has applicability === "REQUIRED" and no confirmed_expiry_date (and optionally no extracted_expiry_date), show a banner such as "Confirm expiry dates for tracked items to finalise your score" with link to requirements/documents. Hide when every REQUIRED requirement has at least one of confirmed_expiry_date or extracted_expiry_date (or product rule: only when all have confirmed_expiry_date).

---

## 8) Replace all UI language: remove "legally required"; use "tracked item"; avoid compliance verdict claims

| Task requirement | Current state | Location | Gap / conflict |
|------------------|---------------|----------|----------------|
| **Remove "legally required"** | Compliance-facing UI already uses "tracked item" in many places (RequirementsPage, ComplianceScorePage, CalendarPage, ClientDashboard). Public/marketing pages still use "legally", "legal requirements", "legally compliant" (Terms, ServicesHub, ServiceDetail, Careers). | `frontend/src/pages/RequirementsPage.js`, ComplianceScorePage, CalendarPage, ClientDashboard (tracked item); TermsPage, ServicesHubPage, ServicePageCMS, ServiceDetailPage, CareersPage (legal wording). | **Partial.** Compliance portal is largely aligned; public pages and some copy still use legal language. |
| **Use "tracked item"** | **Done** in compliance/requirements/score/calendar and dashboard. | As above. | **Done** in core compliance UI. |
| **Avoid compliance verdict claims** | Specs and KB say no "you are compliant/non-compliant"; risk labels and evidence status avoid legal verdict. | `docs/ASSISTANT_SPEC.md`, riskLabel.js, evidenceStatus.js, design-tokens. | **Done** in design/specs and compliance UI. |

**Conclusion:** Core compliance UI uses "tracked item" and avoids verdict language. Remaining "legally required" / "legal" wording is mainly on public/marketing pages (terms, services, careers).

**Recommendation:** Leave public/marketing copy as-is unless product explicitly wants it changed (legal disclaimers in Terms may be intentional). For compliance-only screens, do a final pass for any remaining "required" or "legally required" and replace with "tracked" / "may apply depending on your situation" where appropriate.

---

## Summary table

| # | Requirement | Status | Action |
|---|-------------|--------|--------|
| 1 | Property attributes: has_gas_appliances, is_hmo, tenancy_active, furnished (bool\|unknown) | **Partial** | Add tenancy_active, furnished to Property if needed; align has_gas_appliances with has_gas_supply/cert_gas_safety; consider is_hmo optional/unknown. |
| 2 | Generate requirements on creation, attribute update, provisioning | **Partial** | Creation + provisioning done; attribute update only triggers recalc, not requirement list regeneration. Clarify and optionally add regenerate on attribute update. |
| 3 | Set applicability per requirement; do not penalise NOT_REQUIRED | **Partial** | NOT_REQUIRED not penalised (done). Applicability not set from attributes at generation/update. Optionally derive from property_doc. |
| 4 | Scoring: valid 70, timeliness 10, no overdue 10, unknown 10, overdue 20 | **Conflict** | Current formula is weighted sum of status factors. Implement task formula only if product commits to it; else document and keep current. |
| 5 | Portfolio score = average(property_scores) | **Conflict** | Current is weighted average by E(p). Change to simple average if product requires. |
| 6 | Calendar: confirmed only; exclude NOT_REQUIRED; 30 days | **Partial** | NOT_REQUIRED and 30 days done. "confirmed only" conflicts with effective-date rule; align with product/previous audit. |
| 7 | Dashboard: provisional score banner when REQUIRED missing confirmed expiry | **Missing** | Add banner when any REQUIRED requirement lacks confirmed expiry; hide when resolved. |
| 8 | UI: remove "legally required"; "tracked item"; no verdict claims | **Partial** | Core compliance UI aligned; public pages still use legal wording. Optional pass on compliance-only screens. |

---

## Conflicts and recommended order

1. **Resolve formula conflict (4 & 5):** Decide whether to implement task scoring (70/10/10/10/20) and simple portfolio average, or keep current model and document.
2. **Resolve calendar conflict (6):** Confirm with product whether calendar must use "confirmed_expiry_date only" or keep effective date (consistent with document upload refactor).
3. **Property attributes (1):** Add tenancy_active and furnished if product needs them for rules; align has_gas_appliances naming/semantics.
4. **Dynamic generation on attribute update (2):** Decide if PATCH should regenerate requirement list and/or set applicability from attributes; implement without overwriting user-set NOT_REQUIRED where possible.
5. **Applicability from attributes (3):** If desired, derive applicability when generating/updating requirements from property_doc.
6. **Dashboard provisional banner (7):** Implement once "REQUIRED + missing confirmed expiry" is well-defined.
7. **UI language (8):** Final pass on compliance screens only; leave public/marketing copy unless product requests change.

No duplication with existing certificate-expiry or document-upload work: this task extends property attributes, scoring formula, portfolio aggregation, and dashboard UX; reuse existing applicability, NOT_REQUIRED handling, and expiry_utils where they already match the task.
