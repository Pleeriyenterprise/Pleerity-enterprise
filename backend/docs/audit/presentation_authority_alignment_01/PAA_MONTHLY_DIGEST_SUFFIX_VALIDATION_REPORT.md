# PAA-MONTHLY-DIGEST-SUFFIX-VALIDATION-01

**Verdict:** `PAA_MONTHLY_DIGEST_SUFFIX_VALIDATION_PASSED`  
**Run:** 20260630T181500Z  
**Staging backend:** `aa8bf7b7` (includes PAA `8a830365`)

---

## Objective

Prove a fresh post-PAA monthly digest renders **governed requirement suffixes** (`evidence required`, `calendar overdue`) on requirement-based urgent/upcoming lines — not work-order SLA lines.

---

## Cohort (existing staging data)

| Field | Value |
|-------|--------|
| Client | `e1eeb81d-70b4-4c6b-8265-9f9f80d02cd8` |
| CRN | PLE-CVP-2026-000042 |
| Property | Harbour Apartment (`7b76f35d-39f5-45b6-8f36-07628e67bc91`) |
| Why selected | 17 requirements, 1 overdue, **0 open work orders** on property |

No fixture data was inserted. OPS pilot client `6fd5ac4c…` was rejected — its digest `c69fbdb1…` had work-order-only urgent lines (` — urgent`).

---

## Fresh digest generated

| Field | Value |
|-------|--------|
| Digest ID | `87bccbc5-c75e-4fef-b392-3de1c824b6fe` |
| Method | `JobScheduler.send_monthly_digest_for_client(force=true, property_ids=[Harbour Apartment])` |
| Stored in | `digest_logs` (staging Mongo) |
| Delivery status | `failed_pdf` (Stripe test price env missing locally; **content assembly succeeded**) |
| Portal API | `GET /api/portal/digests/87bccbc5…` → **200** |

---

## Governed suffix lines (requirement-based)

| Line | Suffix |
|------|--------|
| Expired: Gas Safety — calendar overdue (Harbour Apartment) | **calendar overdue** (urgent, `upload_evidence`, 136 days overdue) |
| Evidence needed (legacy read): Smoke, Heat & CO Alarms — calendar overdue (Harbour Apartment) | **calendar overdue** (urgent, 16 days overdue) |
| Evidence needed (legacy read): EICR — evidence required (Harbour Apartment) | **evidence required** (upcoming, `upload_evidence`) |
| Evidence needed (legacy read): HMO Fire Safety — due soon (Harbour Apartment) | governed due soon |
| Evidence needed (legacy read): Legionella — due soon (Harbour Apartment) | governed due soon |

---

## Legacy wording check

| Phrase | Present |
|--------|---------|
| ` — missing evidence` (suffix) | **No** |
| `affecting compliance` | **No** |
| `compliance breach` | **No** |
| Work-order-only urgent section | **No** |

---

## Acceptance criteria

| Criterion | Result |
|-----------|--------|
| Requirement-based urgent actions (not work orders only) | **PASS** |
| Governed `calendar overdue` suffix | **PASS** |
| Governed `evidence required` suffix | **PASS** |
| No legacy `missing evidence` suffix | **PASS** |
| Fresh digest persisted and readable via portal API | **PASS** |

**Overall:** PASS

---

## Notes

- HTTP admin trigger was rate-limited (`429`) during an earlier validation session; digest was generated via local job runner against staging Mongo instead.
- PDF/email send failed on missing `STRIPE_TEST_PRICE_*` in local env; this does not affect suffix authority — digest content is stored and portal-readable.

Evidence: `PAA_MONTHLY_DIGEST_SUFFIX_COHORT_PROBE.json`, `PAA_MONTHLY_DIGEST_SUFFIX_VALIDATION_DIGEST.json`, `PAA_MONTHLY_DIGEST_SUFFIX_VALIDATION.json`
