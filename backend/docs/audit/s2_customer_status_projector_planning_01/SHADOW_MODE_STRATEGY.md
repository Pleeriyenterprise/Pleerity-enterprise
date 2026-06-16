# Shadow mode strategy

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-PLANNING-01  
**Constraint:** Zero customer impact until flag=active

---

## 1. Flow

```
Legacy derive_truth_presentation()
        ↓
customer_status_projector_v2.project()   [always runs in shadow+active]
        ↓
compare_legacy_vs_projector()
        ↓
log divergence (structured)
        ↓
if flag=shadow: emit LEGACY fields only to API
if flag=active: emit PROJECTOR fields (+ optional legacy mirror)
```

---

## 2. Divergence dimensions

| Dimension | Compare |
|-----------|---------|
| `label` | `truth_presentation_label` vs `customer_status_label` |
| `subline` | `truth_presentation_subline` vs `customer_status_subline` |
| `stage/key` | `truth_presentation_stage` vs inverse-map(`customer_status_key`) |
| `class_violation` | Forbidden badge for resolved class |
| `retired_phrase` | Projector clean but legacy has retired phrase |
| `review_without_gate` | Legacy shows review language; projector forbids |

---

## 3. Logging strategy

| Field | Content |
|-------|---------|
| `event` | `customer_status_projector_divergence` |
| `requirement_id` | Row id |
| `client_id` | Tenant |
| `requirement_code` | Canonical code |
| `legacy_label` | truth_presentation_label |
| `projector_label` | customer_status_label |
| `divergence_type` | label_mismatch \| class_forbidden \| retired_phrase_legacy \| gate_mismatch |
| `governance_family` | Input |
| `queue_backed_review` | Input |
| `flag_mode` | shadow |

**Sink:** `compliance_fanout_log` / structured WARNING (existing Stream E pattern) — no PII in message body beyond ids.

**Sampling:** 100% on staging; production shadow 100% for first 72h then 10% sample if volume high.

---

## 4. Metrics & dashboards

| Metric | Target (staging) |
|--------|------------------|
| `divergence_rate` | Trending down week-over-week |
| `divergence_by_code` | Top 10 requirement codes |
| `d1_d12_residual` | Count per CONSISTENCY_AUDIT case |
| `class_a_review_leaks` | **0** before active |
| `retired_phrase_in_projector` | **0** always |

---

## 5. Acceptance thresholds (staging → active promotion)

| Gate | Threshold |
|------|-----------|
| **G1** | CONSISTENCY_AUDIT D1–D12 = **0** on staging spot-check cohort (min 12 families) |
| **G2** | `class_a_review_leaks` = 0 for 7 consecutive days |
| **G3** | `divergence_rate` < 2% on production shadow (excluding known allowlisted legacy-only codes) |
| **G4** | No P0 regression in enrich latency p95 > +15% |
| **G5** | Backend test suite green including shadow fixtures |
| **G6** | Product sign-off on shadow report |

---

## 6. Shadow duration

| Environment | Minimum shadow |
|-------------|----------------|
| Staging | 5 business days after S2 merge |
| Production | 7 calendar days at `flag=shadow` before `flag=active` |

---

## 7. Customer impact

**None** in shadow — API responses identical to pre-S2 legacy projection.
