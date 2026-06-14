# Follow-Up Audit — Staging-Only Registry Keys (5)

**Date:** 2026-06-14  
**Context:** Phase 2 production repair merges **19** coverage-patch keys. Staging published registry v24 contains **24** keys. These **5** keys exist in staging but are **not** in `published_registry_coverage_patch_specs.py` and will **not** be created by the approved repair.

**Evidence source:** Phase 1 `evidence_report.json` (staging published entries).

---

## Summary table

| registry_key | Jurisdiction | Staging requirement type | Recommend for production? |
|--------------|--------------|--------------------------|---------------------------|
| `FITNESS_FOR_HUMAN_HABITATION\|ENGLAND` | England | OBLIGATION | **Defer** — product/legal review |
| `FITNESS_FOR_HUMAN_HABITATION\|WALES` | Wales | OBLIGATION | **Defer** — product/legal review |
| `LEAD_TESTING\|SCOTLAND` | Scotland | DOCUMENT | **Conditional add** — if Scottish portfolio in pilot |
| `RENT_SMART_WALES_REGISTRATION\|WALES` | Wales | DOCUMENT | **Yes for Wales pilot** — separate publish |
| `REPAIRING_STANDARD\|SCOTLAND` | Scotland | OBLIGATION | **Conditional add** — if Scottish portfolio in pilot |

---

## 1. `FITNESS_FOR_HUMAN_HABITATION|ENGLAND`

**Staging editorial (short):**  
*"Unsafe or unhealthy rental conditions can place tenants at risk and may lead to legal disputes, enforcement action, or landlord repair obligations."*

**Business impact if absent in production:**

- England landlords lose a governed registry overlay for **Homes (Fitness for Human Habitation) Act 2018** obligations in client-facing matrix copy and CTAs.
- Does **not** block core certificate compliance (gas, EICR, EPC, etc.) for the current England pilot properties.
- Risk: habitability issues surfaced only via ad-hoc maintenance/issues flows, not as a first-class obligation row.

**Recommendation:** **Defer.** HHSRS/habitability is ongoing obligation semantics (not document-expiry shaped). Requires product decision on evidence model (`OBLIGATION` vs document upload) before production publish. Not blocking Phase 2 pilot GO for certificate-focused properties.

---

## 2. `FITNESS_FOR_HUMAN_HABITATION|WALES`

**Staging editorial:** Same short copy as England row; Wales scope.

**Business impact if absent:**

- Wales landlords miss Renting Homes / habitability-adjacent client messaging in registry overlay.
- Pilot client properties appear England-focused (Cliftonwood / Barbican); **no immediate Wales property impact** for current pilot.

**Recommendation:** **Defer** until Wales portfolio onboarded and habitability obligation model signed off (same rationale as England).

---

## 3. `LEAD_TESTING|SCOTLAND`

**Staging editorial (short):**  
*"Exposure to lead hazards can create serious health risks, particularly for children and vulnerable occupants living in older residential properties."*

**CTA:** Upload lead hazard assessment report

**Business impact if absent:**

- Scottish pre-1919 / high-risk properties would not get registry-driven lead assessment messaging or structured evidence CTA.
- Codebase has lead-testing declaration constants (`LEAD_TESTING_*` in `compliance_evidence_record_service.py`) — platform can support evidence, but **no published registry key** in production means no overlay for planner/materialisation from registry.

**Recommendation:** **Conditional add** in a follow-up publish **if** production onboard Scottish properties or pre-1919 stock. **Not required** for current England pilot client.

---

## 4. `RENT_SMART_WALES_REGISTRATION|WALES`

**Staging editorial (short):**  
*"Rent Smart Wales registration helps demonstrate compliance with Welsh private rented sector registration and licensing obligations."*

**Business impact if absent:**

- Wales landlords cannot see governed Rent Smart Wales registration obligation in compliance matrix.
- Operational code already references `RENT_SMART_WALES` in scoring v2 and `client_applicability_coherence.py` — **runtime/scoring partial support exists** without published registry overlay.
- Gap is **client-facing registry copy + materialisation path**, not zero backend awareness.

**Recommendation:** **Yes for Wales production portfolio** — publish in a **separate editorial publish** after Phase 2 repair, when first Wales landlord enters production. **Not blocking** current England pilot.

---

## 5. `REPAIRING_STANDARD|SCOTLAND`

**Staging editorial (short):**  
*"Maintaining properties in line with the Scottish repairing standard helps protect tenant safety, property condition, and legal housing compliance obligations."*

**CTA:** Complete property review

**Business impact if absent:**

- Scottish landlords miss repairing-standard obligation overlay (property condition review, not single certificate).
- Similar to FFHH: ongoing obligation semantics; distinct from certificate expiry workflow.

**Recommendation:** **Conditional add** when Scottish residential portfolio is in production scope. **Defer** for England-only pilot.

---

## Phase decision

| Question | Answer |
|----------|--------|
| Block Phase 2 19-key repair? | **No** |
| Block pilot GO after Phase 2? | **No** for England certificate-focused pilot |
| Follow-up workstream | Editorial publish queue for 5 keys by jurisdiction as portfolio expands |

---

## Suggested follow-up actions (not executed)

1. Product sign-off on `OBLIGATION`-type keys (FFHH England/Wales, Repairing Standard Scotland).
2. Add patch specs or admin editorial publish for Wales keys when Wales client onboarded.
3. Re-run Phase 1 registry diff after any follow-up publish to confirm prod/staging convergence.
