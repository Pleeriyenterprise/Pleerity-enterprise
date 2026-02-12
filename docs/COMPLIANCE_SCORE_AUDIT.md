# Compliance Score Accuracy – Audit & Evidence

## 1. Single production scoring function

**File:** `backend/services/compliance_score.py`  
**Function:** `calculate_compliance_score(client_id: str) -> Dict[str, Any]`

This is the only function that computes the 0–100 compliance score. It is used by:

- **API:** `GET /api/client/compliance-score` (dashboard load) → calls `calculate_compliance_score(user["client_id"])`
- **Trending:** `services/compliance_trending.py` → `capture_daily_snapshot()` and `get_score_trend()` call `calculate_compliance_score(client_id)`
- **Background job:** `server.py` → `run_compliance_score_snapshots()` (daily 02:00 UTC) calls `capture_daily_snapshot()` for each client, which in turn calls `calculate_compliance_score()`

No other code path computes the score. Provisioning does **not** call `calculate_compliance_score`; it only creates requirements and updates property `compliance_status` (RED/AMBER/GREEN) via `_update_property_compliance()`.

---

## 2. DB inputs (collections and fields)

The scorer **only** reads from the database. It does **not** use frontend state, request body, or query parameters for scoring.

| Collection       | Fields read | Purpose |
|------------------|------------|---------|
| **properties**   | `client_id`, `property_id`, `is_hmo` | List client properties; flag HMO for risk/weights |
| **requirements** | `property_id`, `status`, `requirement_type`, `due_date` | Weighted status score, expiry score, overdue penalty, critical-overdue list |
| **documents**    | `property_id`, `requirement_id`, `status` | Only docs with `status == "VERIFIED"` count toward document coverage |

**Detail:**

- **properties:** `find({"client_id": client_id}, {"_id": 0})` → full docs; only `property_id` and `is_hmo` are used in the formula.
- **requirements:** `find({"property_id": {"$in": property_ids}}, {"_id": 0})` → `status`, `requirement_type`, `due_date`, `property_id`.
- **documents:** `find({"property_id": {"$in": property_ids}}, {"_id": 0})` → filtered to `status == "VERIFIED"`; linkage to requirements via `requirement_id`.

**Not used for scoring:** `request` body/query, JWT payload (except `client_id` for which client to score), frontend state, or any in-memory cache. The API passes only `user["client_id"]` from the auth token to `calculate_compliance_score()`.

---

## 3. End-to-end scoring trace (2 properties, manual check)

**Setup:** 1 client, 2 properties, 4 requirements.

**Properties:**

| property_id | is_hmo |
|-------------|--------|
| prop-1      | False  |
| prop-2      | False  |

**Requirements:**

| requirement_id | property_id | requirement_type | status        | due_date   |
|----------------|-------------|-----------------|---------------|------------|
| req-1         | prop-1      | GAS_SAFETY      | COMPLIANT     | 2026-06-01 |
| req-2         | prop-1      | EICR            | COMPLIANT     | 2026-05-15 |
| req-3         | prop-2      | EPC             | EXPIRING_SOON | 2026-03-01 |
| req-4         | prop-2      | LANDLORD_INSURANCE | OVERDUE    | 2025-12-01 |

**Documents:** 3 docs; 2 VERIFIED linked to req-1, req-2; 1 VERIFIED linked to req-3. req-4 has no verified doc.

**Weights (from code):** GAS_SAFETY 1.5, EICR 1.4, EPC 1.2, LANDLORD_INSURANCE 1.0.

**1) Status score (35%)**

- req-1: 1.5 × 100 = 150  
- req-2: 1.4 × 100 = 140  
- req-3: 1.2 × 40  = 48  
- req-4: 1.0 × 0   = 0  
- total_weight = 1.5 + 1.4 + 1.2 + 1.0 = 5.1  
- weighted_points = 150 + 140 + 48 + 0 = 338  
- status_score = 338 / (5.1 × 100) × 100 ≈ **66.27**

**2) Expiry score (25%)**

- Critical (weight ≥ 1.3): GAS_SAFETY due 2026-06-01, EICR 2026-05-15 → nearest critical = EICR ~93 days.  
- effective_min_days = 93 → expiry_score = **100** (≥ 90).

**3) Document score (15%)**

- Requirements with at least one VERIFIED doc: req-1, req-2, req-3 → 3 of 4.  
- verified_doc_rate = 75% → doc_score = **75**.

**4) Overdue penalty (15%)**

- overdue_count = 1 (req-4). critical_overdue = [] (req-4 weight 1.0 < 1.3).  
- overdue_penalty_base = 100 − 25 = 75; critical_penalty = 0.  
- overdue_penalty_score = **75**.

**5) Risk score (10%)**

- hmo_count = 0 → risk_score = **100**.

**Final:**

- final_score = 0.35×66.27 + 0.25×100 + 0.15×75 + 0.15×75 + 0.10×100  
- = 23.19 + 25 + 11.25 + 11.25 + 10 = **80.69** → **81** (rounded).

**Check:** Call `GET /api/client/compliance-score` for this client (with requirements/documents as above); the returned `score` must be **81** and `breakdown` should match the component scores above (status ≈ 66.3, expiry 100, document 75, overdue_penalty 75, risk 100).

---

## 4. Timing: when the score is computed

| When              | How | Uses persisted state only? |
|-------------------|-----|-----------------------------|
| **Dashboard load**| `GET /api/client/compliance-score` → `calculate_compliance_score(client_id)` | Yes: reads only DB (properties, requirements, documents). |
| **Daily 02:00 UTC** | `run_compliance_score_snapshots()` → `capture_daily_snapshot(client_id)` → `calculate_compliance_score(client_id)` | Yes: same DB-only read. |
| **Manual snapshot**| `POST /api/client/compliance-score/snapshot` → `capture_daily_snapshot(client_id)` | Yes: same. |
| **Trend/explanation**| `get_score_trend()` / `get_score_change_explanation()` read `compliance_score_history` (stored snapshots) and optionally call `calculate_compliance_score()` for current score. | Yes: history is persisted; current score again from DB only. |

**Not computed during provisioning.** Provisioning creates requirements and updates property-level `compliance_status` (RED/AMBER/GREEN) only. The 0–100 score is computed only when the API or the daily job runs, and only from persisted data (no requirements → “no requirements” path returns score 100 with message “No requirements to evaluate”).

---

## 5. API output format

**Returned by** `calculate_compliance_score()` and thus by `GET /api/client/compliance-score`:

- **score** (0–100 integer): present.
- **grade** (A–F): present.
- **color**: present (green/amber/red/gray).
- **message**: present.
- **breakdown**: present – `status_score`, `expiry_score`, `document_score`, `overdue_penalty_score`, `risk_score` (all rounded).
- **weights**: present – percentages for status, expiry, documents, overdue_penalty, risk_factor.
- **stats**: present – counts (e.g. total_requirements, compliant, overdue, documents_verified, days_until_next_expiry, etc.).
- **recommendations**: present (top 5).
- **properties_count**: present.
- **enhanced_model**: present (true).

**Gaps (no code change in this audit):**

- **ruleset_version / code version identifier:** Not returned. There is no `ruleset_version` or equivalent in the response. Adding it would require a code change (e.g. constant or version file).
- **score_breakdown when score is null:** The function never returns `score: null`. It returns either a numeric score or, on error, `score: 0` with `grade: "?"` and `error` in the dict. So “missing fields list when score is null” is not applicable today; if a future contract allows `score: null`, a defined structure for `score_breakdown` (e.g. component contributions + list of missing/blocking fields) would need to be specified and implemented.

---

## 6. Bug fix applied during audit

- **Document verification field:** The scorer was checking `d.get("verification_status") == "VERIFIED"` while the rest of the app (and `documents` collection) uses `status` (e.g. `DocumentStatus.VERIFIED` → `"VERIFIED"`). This was corrected to `d.get("status") == "VERIFIED"` so document coverage is based on persisted verification state.

---

## 7. Golden tests (see `test_compliance_score_golden.py`)

Golden-case unit tests added:

- **Case A:** All compliant, valid expiry, docs present → score near 100.
- **Case B:** One critical requirement overdue → score drops by expected amount.
- **Case C:** Missing documents but requirements marked compliant → document coverage penalty only.
- **Case D:** New/unknown requirement type → default weight 1.0.
- **Case E:** No properties or no requirements → score 100 with defined message (no null).

These tests seed minimal DB state (mocked) and assert exact or bounded numeric outputs to lock scoring behavior.
