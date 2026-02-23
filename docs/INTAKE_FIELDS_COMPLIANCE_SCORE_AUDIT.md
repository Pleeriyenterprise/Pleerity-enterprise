# Intake Fields vs Compliance Score & Dashboard — Audit

**Question:** Are the intake form fields (and selected options) from the screenshots incorporated into compliance score calculation and dashboard determination? Should they be, and have they been implemented?

---

## 1) Intake fields shown in your screenshots

| Screenshot / Section | Field(s) | Stored on property? | Used in score/catalog? |
|---------------------|----------|----------------------|-------------------------|
| Property Type       | property_type (House, Flat, Bungalow, etc.) | Yes (intake submit) | **Indirect**: not in requirement_catalog applicability; provisioning uses it for requirement generation. |
| Bedrooms            | bedrooms (number) | Yes | **Yes**: `compliance_scoring._multiplier()` uses bedrooms (e.g. PROPERTY_LICENCE when bedrooms >= 5). |
| Occupancy           | occupancy (Single Family, Multi Family, Student Let, etc.) | Yes | **Yes**: `_multiplier()` uses occupancy (e.g. PROPERTY_LICENCE when occupancy != single_family). |
| Is this an HMO?     | is_hmo (toggle) | Yes | **Yes**: `requirement_catalog` adds PROPERTY_LICENCE when is_hmo; scoring uses is_hmo in multipliers. |
| Is a licence required? | licence_required (Yes/No/Unsure) | Yes | **Yes**: PROPERTY_LICENCE applicable when licence_required == "YES" (or cert_licence/licence_type). |
| Licence Type        | licence_type (Selective, Additional, Mandatory HMO) | Yes | **Yes**: PROPERTY_LICENCE applicable when licence_type non-empty. |
| Licence Status      | licence_status (Applied, Pending, etc.) | Yes | Stored; not used in applicability (status is informational). |
| Who manages / Send reminders to | managed_by, send_reminders_to | Yes | **No** for score; used for **notifications/reminders**. |
| Do you have these certificates? | cert_gas_safety, cert_eicr, cert_epc, cert_licence (Yes/No/Unsure) | Yes | **Yes**: GAS_SAFETY_CERT only applicable when cert_gas_safety == "YES"; cert_licence/licence_type drive PROPERTY_LICENCE. |

---

## 2) Implementation status

### 2.1 Storing intake data on the property

- **Where:** `backend/routes/intake.py` (intake submit) creates properties with:
  - `property_type`, `bedrooms`, `occupancy`, `is_hmo`, `licence_required`, `licence_type`, `licence_status`
  - `cert_gas_safety`, `cert_eicr`, `cert_epc`, `cert_licence`
  - `managed_by`, `send_reminders_to`, `local_authority`, etc.
- **When:** At intake submit (before payment). Properties exist with this data when provisioning runs.
- **Conclusion:** The intake fields you see are persisted on the **property** document.

### 2.2 Compliance score and dashboard

- **Applicable requirements** (`backend/services/requirement_catalog.py`):
  - **GAS_SAFETY_CERT:** only if `cert_gas_safety == "YES"` (so “Yes, I have it” → scored; “No”/“Unsure” → not penalised).
  - **PROPERTY_LICENCE:** if `is_hmo` **or** `licence_required == "YES"` **or** `cert_licence == "YES"` **or** `licence_type` non-empty.
  - **EICR/EPC:** always applicable.
  - **Tenancy / deposit:** only if `tenancy_active` / `deposit_taken` true (not collected in intake; portal-only).
- **Scoring** (`backend/services/compliance_scoring.py`):
  - Reads `property_doc` and calls `get_applicable_requirements(property_doc)` → only those requirements are scored.
  - Uses `is_hmo`, `occupancy`, `bedrooms` in `_multiplier()` for weighting (e.g. PROPERTY_LICENCE for HMO / occupancy / bedrooms).
- **Dashboard:** Uses the same property data and compliance score; “tracked items” and score reflect applicability and multipliers above.

So: **Yes, the intake fields that are stored on the property are incorporated into compliance score calculation and into what the dashboard shows** (which requirements apply and how they’re weighted). Licence status and “who manages / send reminders to” are stored and used for display/reminders, not for score applicability.

### 2.3 Frontend mapping

- IntakePage uses values `YES` / `NO` / `UNSURE` with labels like “Yes, I have it” / “No, I don’t have it” / “Unsure” for certificate questions, and sends them as `cert_gas_safety`, etc. So the options selected in the form do affect applicability (e.g. Gas Safety only when “Yes, I have it” → `YES`).

---

## 3) Gaps / nuances

| Item | Status | Note |
|------|--------|------|
| Property type (House vs Flat vs etc.) | Stored only | Not used in requirement_catalog for applicability; EICR/EPC apply to all. Provisioning may use it for requirement generation. |
| tenancy_active / deposit_taken | Not from intake | Used by catalog for tenancy/deposit requirements but not collected in intake; user can set in portal. So those requirements don’t apply until set in portal. |
| Licence status (Applied/Pending/Approved/Expired) | Stored only | Informational; not used to turn licence requirement on/off (that’s driven by licence_required / licence_type / is_hmo). |
| “Who manages” / “Send reminders to” | Stored | Affect notifications only, not score. |

---

## 4) Should intake fields contribute?

**Recommendation: Yes, and they already do.**

- **Why they should:** Intake captures property type, HMO, licence need, occupancy, bedrooms, and whether they have certain certificates. Using this for applicability and weighting keeps the score and dashboard aligned with what the user declared (e.g. no gas safety penalty if they said “No” to having gas safety; licence only when they said a licence is required or it’s an HMO).
- **Current behaviour:** That’s how it’s implemented: intake → property document → requirement_catalog + compliance_scoring. So the options selected in the intake form do affect the calculation and what’s on the dashboard.

---

## 5) Summary

| Question | Answer |
|----------|--------|
| Are these intake fields incorporated into compliance score calculation? | **Yes** for: is_hmo, licence_required, licence_type, cert_* (gas/eicr/epc/licence), bedrooms, occupancy. property_type is stored; tenancy/deposit are portal-only. |
| Do selected options affect the calculation? | **Yes**: e.g. “Yes, I have it” for Gas Safety → Gas Safety requirement applicable; “No” licence required + not HMO → licence not applicable; HMO on → licence applicable; occupancy/bedrooms affect multipliers. |
| Are they supposed to contribute to dashboard/score? | **Yes** — and they do. Applicable requirements and weights are derived from property data that is populated from intake. |
| Have they been implemented? | **Yes**: intake submit writes to property; requirement_catalog and compliance_scoring read from property; dashboard uses the same pipeline. |
| Recommendation | **Keep intake driving score/dashboard** as now. Optionally: (1) add tenancy_active/deposit_taken to intake if you want them to drive tenancy/deposit requirements from day one; (2) use property_type in catalog if you ever need type-specific rules (e.g. different rules for commercial). |
