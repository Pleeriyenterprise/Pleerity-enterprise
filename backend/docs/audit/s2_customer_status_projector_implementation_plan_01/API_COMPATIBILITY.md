# API compatibility — S2

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-IMPLEMENTATION-PLAN-01

---

## Summary

| Rule | S2 commitment |
|------|---------------|
| No existing field removed | **Confirmed** |
| `customer_status_*` additive | **Confirmed** |
| Legacy fields until S3 | **Confirmed** |
| Reports/emails unchanged | **Confirmed** |
| No Mongo schema change | **Confirmed** |

---

## Field contract by mode

### Fields never removed in S2

| Field | Notes |
|-------|-------|
| `truth_presentation_label` | Legacy authority in shadow; mirrored in active |
| `truth_presentation_subline` | Same |
| `truth_presentation_stage` | Same |
| `truth_presentation_tier_supplement` | Meta |
| `client_lifecycle_state` | Internal enum |
| `client_lifecycle_label` | Customer-visible; source changes in active |
| `client_lifecycle_reason_codes` | Unchanged |
| `review_owner` | Internal — not for customer copy |
| `queue_backed_review` | Internal gate signal |
| `governance_family` | Meta |
| `assurance_tier` | Meta |
| `take_action` | Present; resolution order changes |
| `operational_cognition` | Present; copy source changes |
| `audience_interpretation` | Present; partial read-through |
| `status_label` / `evidence_badge_label` | Canon-specific overrides unchanged (legionella/smoke) — **not** customer_status authority |

### Fields added in S2 (when flag ≠ disabled)

| Field | shadow | active |
|-------|--------|--------|
| `customer_status_key` | additive | additive |
| `customer_status_label` | additive | additive |
| `customer_status_subline` | additive | additive |
| `customer_status_class` | additive | additive |
| `customer_status_reason` | additive | additive |
| `customer_status_overlay` | additive | additive |
| `vocabulary_version` | additive | additive |
| `customer_status_projector_version` | additive | additive |

### Internal/debug fields (optional)

| Field | Consumer |
|-------|----------|
| `_customer_status_shadow` | Admin explain only — omit from public OpenAPI if documented |

---

## Endpoint impact

| Endpoint | S2 change |
|----------|-----------|
| `GET /api/client/...` requirement lists | Additive fields when flag ≠ disabled |
| `GET /api/portfolio/...` | Same |
| Command centre / today backends | Cognition copy source change when active |
| Admin explain | Projector debug additive |
| Report generation | **No change** |
| Email templates | **No change** |

---

## Frontend compatibility (S2)

| Item | Behaviour |
|------|-----------|
| FE not updated in S2 | Continues reading `truth_presentation_label`, `client_lifecycle_label`, local fallbacks |
| shadow mode | **Zero customer impact** — legacy fields unchanged |
| active mode | API legacy fields **mirrored** from projector — FE may still use fallbacks until S3 (partial drift accepted) |

---

## Reports and emails (S4 boundary)

| Module | S2 |
|--------|-----|
| `report_human_language_v1.py` | Unchanged |
| `report_layout_governance.py` | Unchanged |
| `monthly_digest_operational_intelligence.py` | Unchanged |
| `scheduled_report_digest.py` | Unchanged |

---

## Versioning headers

Optional future: `X-Customer-Status-Vocabulary-Version` response header — **out of scope S2** unless trivial; version on row payload sufficient.

---

## Breaking change assessment

| Change | Breaking? |
|--------|-----------|
| Add customer_status_* | No |
| active: truth_presentation_label mirrored | No — same field name |
| active: label values change to vocabulary | **Semantic** — mitigated by shadow soak + S3 FE migration |
| Reorder take_action in enrich | No external contract change if take_action shape unchanged |

**S2 API compatibility: PASS** — additive with documented semantic shift only when `active`.
