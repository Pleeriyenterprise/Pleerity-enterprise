# Requirement Catalog + Applicability – Gap Analysis

## Goal (task)
Compute per-property **applicable** requirements and evidence inputs for the compliance score engine. Deterministic, no legal verdicts. Do not guess rules beyond spec.

## Current state

| Area | Location | Behaviour |
|------|----------|-----------|
| Applicability | `compliance_scoring.py` `_applicable_weights()` | Gas: `has_gas` or `has_gas_supply` (True = applicable). Licence: `licence_required` in ("YES","TRUE","1"). EICR/EPC always. TENANCY_BUNDLE always. |
| Keys | Same file | Internal keys: `GAS_SAFETY`, `EICR`, `EPC`, `LICENCE`, `TENANCY_BUNDLE`. |
| Property fields loaded | `compliance_scoring_service.py` | `is_hmo`, `bedrooms`, `occupancy`, `licence_required`, `has_gas_supply`, `has_gas`. **Not loaded:** `cert_gas_safety`, `cert_licence`, `licence_type`. |
| Evidence matching | `compliance_scoring.py` | Requirements matched by `requirement_type` (e.g. gas_safety, eicr, epc) via `_req_type_to_key()` to internal key. |
| Provisioning | `provisioning.py` | Creates requirements with `requirement_type`: gas_safety, eicr, epc, hmo_license, etc. |

## Task rules (exact)

- **EICR_CERT:** always applicable.
- **EPC_CERT:** always applicable.
- **GAS_SAFETY_CERT:** applicable **iff** `property_doc.cert_gas_safety == "YES"`. Do not penalize when `cert_gas_safety == "NO"`.
- **PROPERTY_LICENCE:** applicable **iff** any: `is_hmo == true`, `licence_required == "YES"`, `cert_licence == "YES"`, or `licence_type` non-empty.
- **Tenancy:** NOT scored in v1 unless `tenancy_active == true`; if field absent, exclude.
- **Deposit prescribed info:** only if `deposit_taken == true`; if absent, exclude.
- **FIRE_SAFETY_EVIDENCE:** exclude from v1 unless document support exists.

## Conflicts and safest option

1. **Gas applicability**  
   - **Current:** `has_gas` / `has_gas_supply` (True = applicable).  
   - **Task:** `cert_gas_safety == "YES"` only.  
   - **Choice:** Implement task as specified. Properties without `cert_gas_safety` set are not given gas in the applicable list (no penalty). When `gas_present` exists later, it can be used instead; for now only `cert_gas_safety` is used.

2. **Licence applicability**  
   - **Current:** Only `licence_required`.  
   - **Task:** `is_hmo` OR `licence_required == "YES"` OR `cert_licence == "YES"` OR `licence_type` non-empty.  
   - **Choice:** Implement full task rule. Broader applicability is consistent with “licence where any indicator says so”.

3. **Canonical keys**  
   - **Current:** GAS_SAFETY, EICR, EPC, LICENCE, TENANCY_BUNDLE.  
   - **Task:** GAS_SAFETY_CERT, EICR_CERT, EPC_CERT, PROPERTY_LICENCE, (optional) TENANCY_AGREEMENT, etc.  
   - **Choice:** New catalog uses task keys. Scoring uses these keys so breakdown and risk use the same names. Existing API response will show new keys (e.g. `EICR_CERT` instead of `EICR`).

4. **Tenancy in v1**  
   - **Current:** TENANCY_BUNDLE always in applicable weights.  
   - **Task:** Tenancy only when `tenancy_active == true`; if absent, exclude.  
   - **Choice:** Include tenancy-related keys in applicable list only when `tenancy_active == true`. If `tenancy_active` is absent, exclude (no tenancy in v1).

5. **Evidence mapping**  
   - **Task:** GAS_SAFETY_CERT→"gas_safety", EICR_CERT→"eicr", EPC_CERT→"epc", PROPERTY_LICENCE→"licence".  
   - **DB:** Documents/requirements use `requirement_type` e.g. "hmo_license", "gas_safety".  
   - **Choice:** Map PROPERTY_LICENCE to document_type "licence"; in scoring, map requirement_type "hmo_license" (and "licence") to catalog key PROPERTY_LICENCE so existing data still matches.

## Implementation summary

- **New:** `backend/services/requirement_catalog.py` – canonical keys, `get_applicable_requirements(property_doc)`, evidence key → document_type.
- **Changed:** `compliance_scoring.py` – call `get_applicable_requirements()`, build weights only for applicable keys, map requirement_type → catalog key, filter by applicable list, renormalize weights to 100.
- **Changed:** `compliance_scoring_service.py` – load `cert_gas_safety`, `cert_licence`, `licence_type` for property.
- **New tests:** cert_gas_safety="NO" ⇒ no GAS_SAFETY_CERT; is_hmo=true ⇒ PROPERTY_LICENCE; licence_required="YES" ⇒ PROPERTY_LICENCE; base case ⇒ EPC_CERT and EICR_CERT always.
