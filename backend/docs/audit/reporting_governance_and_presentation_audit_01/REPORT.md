# REPORTING-GOVERNANCE-AND-PRESENTATION-AUDIT-01

Audited at: 2026-06-04T06:26:42+00:00 (staging consistency) / 2026-06-04T06:40:00+00:00 (closeout)
Primary classification: **REPORT_TRUTH_DRIFT**

## 1. Reporting architecture

The reporting system is **multi-lane**, not a single pipeline:

| Lane | Examples | Engine |
|------|----------|--------|
| Server compliance CSV/PDF data | Compliance summary, requirements, score drivers, score explanation | `reporting_service`, `calculate_compliance_score`, ReportLab |
| Governed audit bundle | Audit Evidence Pack (property ZIP) | `compliance_audit_evidence_pack_service` + GridFS |
| Client-rendered PDF | Compliance/requirements PDF from JSON, monthly digest PDF | jsPDF on `ReportsPage` |
| Professional branded PDF | `/reports/professional/*` | ReportLab + branding resolver |
| Operational / admin | Rent summary card, admin reports hub, ledger CSV | Separate services |

Full inventory: **22 surfaces** in `report_inventory_runtime.json`.

**Evidence Reminders Report:** no dedicated export — reminders are **email jobs** (`daily_reminders`, `COMPLIANCE_EXPIRY_REMINDER`), not a downloadable report type.

## 2. Operational truth convergence

Reports pull from **three lenses** that are not always aligned:

1. **Persisted scores** — `compliance_score`, `compliance_last_calculated_at` on properties; portfolio mean for headline.
2. **Live portal projection** — `calculate_compliance_score` stats/drivers; `compute_client_portal_requirement_stats` after alias dedupe.
3. **Raw DB fields** — e.g. property `compliance_status` in compliance summary CSV without live recompute (dashboard recomputes RAG on fetch).

Non-authoritative previews (matrix catalog/legacy) are correctly labeled in portfolio API but must not appear in regulator-facing packs.

See `source_of_truth_runtime.json`.

## 3. Propagation (code trace; staging read-only)

Lifecycle/evidence changes update requirement rows **immediately**; **score headline** and scheduled email CSVs lag **async recalc** (seconds–minutes). Evidence Readiness **re-download** always rebuilds from **current** data — stored `score_at_time` is metadata only.

Mutation matrix A–J: `propagation_runtime.json`.

## 4. Consistency (staging — nancy@yopmail.com)

| Surface | total / compliant |
|---------|-------------------|
| Dashboard (`/client/compliance-score` stats) | 43 / 1 |
| Compliance summary CSV | 49 / 2 |
| Requirements page (tracked, lifecycle-valid-like) | 47 / 0 |
| Requirements report CSV rows | 49 |

All four `alignment_checks` failed → **count_drift_detected: true**.

This confirms reporting truth can diverge from dashboard and from the Requirements page in the same session. Aligns with prior `DASHBOARD-SCORE-WIDGET-SEMANTIC-CONVERGENCE-01` (COUNT_CONVERGENCE_DRIFT).

## 5. Presentation quality

| Tier | Surfaces |
|------|----------|
| REGULATOR_READY / AUDIT_READY | Governed **Audit Evidence Pack** only (manifest, checksums, export identity) |
| CLIENT_PRESENTABLE | Server ReportLab evidence readiness, professional PDFs, CSV summaries (with disclaimers) |
| INTERNAL_OPERATIONAL_ONLY | Score drivers CSV, rent ops card, portal analytics, admin exports |

Client **jsPDF** reports are **not** regulator-ready (no immutable artifact, weaker governance block).

Strict assessment: `presentation_runtime.json`.

## 6. Export engine

- **No HTML-to-PDF** — ReportLab platypus + openpyxl (admin) + client jsPDF.
- **Deterministic** server templates; **non-deterministic** evidence readiness re-fetch over time.
- **Scalability:** `to_list(10000)` requirements per sync export; property-scoped audit pack mitigates evidence volume.

Details: `export_engine_runtime.json`.

## 7. Governance / scalability

- Hourly **report export rate limits** per client/admin.
- **Audit pack:** immutable GridFS + audit log.
- **Weak points:** evidence readiness snapshot metadata without frozen PDF; dual evidence-pack products; scheduled CSV timing vs recalc.

Details: `scalability_governance_runtime.json`.

## 8. Classification summary

| Class | Finding |
|-------|---------|
| REPORT_TRUTH_DRIFT | Cross-surface count/status divergence; re-download drift |
| GOVERNANCE_GAP | Legacy evidence-pack ZIP vs governed audit pack |
| EXPORT_ENGINE_GAP | ReportLab + jsPDF dual engine |
| SCALABILITY_GAP | Large sync exports |
| PRESENTATION_GAP | jsPDF cosmetic/governance gap (cosmetic severity) |
| NO_MATERIAL_GAP | Audit pack v2 contract, score driver headers, rate limits |

## 9. Commit / push

Pending in this closeout step (see git status after commit).

## Recommended next priorities (audit only — no redesign executed)

1. **Converge requirement counts** — single stats function for dashboard, compliance summary CSV, and requirements page (or explicit per-surface labels).
2. **Freeze or relabel Evidence Readiness re-download** — bind PDF bytes at generation or print “current data as of {timestamp}”.
3. **Recompute or label property RAG** in compliance summary export vs dashboard.
4. **Product copy governance** — distinguish governed audit pack from legacy evidence-pack ZIP.
5. **Server-side PDF only** for client “professional” downloads where regulator/lender sharing is implied.
