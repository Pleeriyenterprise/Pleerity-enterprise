# Performance Validation

**Programme:** COMPLIANCE-TIMELINE-PHASE-1-AND-2-RELEASE-VALIDATION-01  
**Validated at:** 2026-06-02

## Verdict: **INCONCLUSIVE — local micro-benchmark only; no pre-migration baseline; staging not measured**

Performance validation requires comparison against pre-migration baselines on the same environment. No stored baseline artefacts were found for enrich latency or report generation with/without Compliance Timeline.

---

## Local micro-benchmark (uncommitted code, Windows dev machine)

Method: 50 iterations, verified Gas Safety fixture, single process.

| Operation | Mean (ms) | P95 (ms) |
|---|---|---|
| `build_compliance_timeline(row)` | 0.049 | 0.168 |
| `enrich_requirement_dict(row)` (includes timeline + presentation) | 0.540 | 0.517 |

**Interpretation:** Timeline calculation adds sub-millisecond mean overhead per requirement on synthetic data. Full enrich remains sub-millisecond to ~0.5 ms per row locally — not representative of production Mongo-backed enrich at portfolio scale.

---

## Surfaces not measured

| Surface | Status |
|---|---|
| Enrich API response time (staging) | **NOT MEASURED** — programme not deployed |
| Dashboard load with timeline fields | **NOT MEASURED** |
| Report generation (PDF/digest) | **NOT MEASURED** |
| Email generation | **NOT MEASURED** |
| Portfolio-scale enrich (100+ requirements) | **NOT MEASURED** |

---

## Pre-migration baseline

| Baseline artefact | Found |
|---|---|
| Stored enrich p95 before Phase 1 | **No** |
| Stored report generation duration before Phase 2 | **No** |
| APM/dashboard comparison | **Not accessed in this validation** |

---

## Material regression criterion

No material regression can be confirmed or denied without:

1. Deployed staging SHA with programme
2. Repeatable load test on `/api/client/requirements` (or enrich endpoint) with typical portfolio sizes
3. Timed monthly digest + requirements PDF generation before/after on same fixture client

---

## Provisional assessment

Local micro-benchmark suggests **negligible per-row calculator overhead**, but this is **insufficient for production readiness sign-off**. Treat performance gate as **OPEN** until staging measurements with baselines are recorded post-deploy.

## Recommended post-deploy metrics

- Enrich p50/p95 for 1-, 10-, 50-property portfolios
- Requirements list TTFB + client render
- Monthly digest assembly wall time
- Requirements operational PDF generation wall time
