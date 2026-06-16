# Shadow comparison design

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-IMPLEMENTATION-PLAN-01  
**Module:** `backend/services/customer_status_projector_shadow.py`

---

## Comparison trigger

Run `compare_legacy_vs_projector(requirement, legacy_truth, projector_result)` when `mode in (shadow, active)`.

Legacy snapshot captured **immediately before** projector from:
- `truth_presentation_label`
- `truth_presentation_subline`
- `truth_presentation_stage`
- `client_lifecycle_label`

---

## Comparison dimensions

| Dimension | Legacy field | Projector field | Mismatch type |
|-----------|--------------|-----------------|---------------|
| Label | `truth_presentation_label` | `customer_status_label` | `label_mismatch` |
| Subline | `truth_presentation_subline` | `customer_status_subline` | `subline_mismatch` |
| Key | inverse_map(`truth_presentation_stage`) | `customer_status_key` | `key_mismatch` |
| Class | inferred from governance_family + key | `customer_status_class` | `class_mismatch` |
| Review phrase | legacy text | projector text | `retired_phrase_legacy` |
| Review without gate | legacy has review phrase | projector forbids | `review_without_gate` |
| Class forbidden | legacy key in class forbidden set | projector key | `class_forbidden` |
| Escalation | legacy `Escalated for platform review` | `escalation_required` | `escalation_normalization` |
| Verification | legacy `Platform verification pending` | `under_review` or `recorded` | `verification_normalization` |

### Review-related phrase detection

Scan legacy label/subline against `RETIRED_REVIEW_PHRASES` from vocabulary module.

### Escalation-related phrase detection

| Legacy | Expected projector |
|--------|-------------------|
| Escalated for platform review | `Escalation required` |
| Submission on file — escalated for platform review | subline without retired phrase |

### Expected non-divergence (allowlist)

When projector **correctly** fixes drift, log as `expected_normalization` not `label_mismatch`:
- `Platform verification pending` → `Under review` (class B + queue)
- `Platform verification pending` → `Recorded on file` (class A)
- `Escalated for platform review` → `Escalation required`

---

## Divergence event shape

```json
{
  "event": "customer_status_projector_divergence",
  "timestamp": "2026-06-02T12:00:00Z",
  "environment": "staging",
  "flag_mode": "shadow",
  "requirement_id": "<uuid>",
  "client_id": "<uuid>",
  "property_id": "<uuid>",
  "requirement_code": "legionella",
  "governance_family": "SELF_CERTIFIED",
  "queue_backed_review": false,
  "legacy": {
    "truth_presentation_label": "Platform verification pending",
    "truth_presentation_subline": "Our team will verify…",
    "truth_presentation_stage": "platform_verification_pending",
    "client_lifecycle_label": "Platform verification pending"
  },
  "projector": {
    "customer_status_key": "recorded",
    "customer_status_label": "Recorded on file",
    "customer_status_subline": "Self-recorded declaration…",
    "customer_status_class": "A"
  },
  "divergence_type": "expected_normalization",
  "divergence_dimensions": ["label_mismatch", "review_without_gate"],
  "consistency_audit_case": "D3",
  "vocabulary_version": "1.0.0",
  "customer_status_projector_version": "2.0.0"
}
```

### Log safety

| Allowed in log body | Forbidden |
|---------------------|-----------|
| requirement_id, client_id, property_id, requirement_code | Tenant name, address, document content |
| Machine status keys/labels | PII from evidence payloads |
| governance_family, queue flags | User email |

Sink: structured WARNING via existing compliance fanout / Stream E pattern.

---

## Metrics

| Metric | Type | Labels |
|--------|------|--------|
| `customer_status_projector_divergence_total` | counter | `divergence_type`, `requirement_code`, `flag_mode` |
| `customer_status_projector_divergence_rate` | gauge | `environment` |
| `customer_status_class_a_review_leaks` | counter | `requirement_code` |
| `customer_status_retired_phrase_in_projector` | counter | must stay **0** |
| `customer_status_enrich_projector_latency_ms` | histogram | p95 for G4 |

---

## Acceptance thresholds G1–G6

| Gate | Threshold | Measurement |
|------|-----------|-------------|
| **G1** | D1–D12 = **0** on staging cohort (≥12 families) | Manual QA + automated fixtures |
| **G2** | `class_a_review_leaks` = 0 for **7 consecutive days** | Metrics |
| **G3** | `divergence_rate` < **2%** production shadow (excl. allowlisted normalizations) | Metrics |
| **G4** | Enrich p95 latency **≤ +15%** vs baseline | APM |
| **G5** | Backend CI green including shadow fixtures | CI |
| **G6** | Product sign-off on shadow report | Process |

---

## Sampling rules

| Environment | Mode | Sampling |
|-------------|------|----------|
| Staging | shadow | **100%** |
| Production | shadow | **100%** first 72h → **10%** if volume > threshold |
| Production | active | 100% invariant violations; 1% mirror check |

---

## Shadow duration (minimum)

| Environment | Duration |
|-------------|----------|
| Staging | 5 business days at `shadow` after merge |
| Production | 7 calendar days at `shadow` before `active` promotion |

**Do not recommend production `active` until G1–G6 pass.**

---

## Admin explain integration

When admin explain API called, include:

```json
"customer_status_projection_debug": {
  "flag_mode": "shadow",
  "last_divergence": { … },
  "projector_version": "2.0.0"
}
```
