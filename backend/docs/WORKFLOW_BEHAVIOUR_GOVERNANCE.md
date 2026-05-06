# Workflow behaviour governance

**Status:** Authority reference — complements `REQUIREMENT_WORKFLOW_CLASS_DECISION_RECORD.md`.  
**Audience:** Engineers extending resolver, evidence, scoring surfaces, or CTAs.  
**Non-goals:** This document is **not** runtime configuration and must not replace registry, resolver, or evidence authority.

---

## Core principle

**Evidence recorded ≠ compliance proven.**  
**Compliance proven ≠ remediation complete.**  
**Assessment recorded ≠ risk resolved.**  
**Condition-standard closure ≠ document-upload closure.**

Implementations must not collapse distinct workflow mechanics into a single “upload document ⇒ compliant” path unless the workflow class explicitly allows it (see capability matrix in `services/workflow_behaviour_governance.py`).

---

## Governance Authority & Precedence

When contracts conflict, apply this **strictly ordered** hierarchy (highest wins):

1. **Runtime safety restrictions** — platform hard limits that must not be bypassed by policy or UI.
2. **Workflow behaviour governance** — this document plus `services/workflow_behaviour_governance.py` (capabilities, semantics, execution contracts, forbidden representation metadata, additive audit flags).
3. **Published registry `evidence_resolution`** — authoritative evidence modes and workflows where the registry publishes them.
4. **Canonical resolver contracts** — `requirement_action_resolver` / `take_action` envelope and provenance (`TAKE_ACTION_CONTRACT_VERSION`).
5. **Runtime defaults / fallbacks** — e.g. `DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE` when registry is silent.
6. **Frontend display fallbacks** — presentation-only; **must not** contradict 1–4 or imply stronger assurance than the workflow class allows.

**Rules**

- **Lower layers must not contradict higher layers.** If UI copy or a client fallback implies certificate closure on a guided-declaration workflow, the UI is wrong — not the registry row semantics.
- **Frontend fallbacks are presentation-only** — they do not create legal verification, operational safety, or audit defensibility.
- **Workflow governance overrides legacy “upload implies done” assumptions** unless the workflow class explicitly authorises certificate-style closure.
- **Reporting semantics must respect non-equivalence rules** — see **Non-Equivalence Rules**, **Reporting and Audit Surface Semantics**, and **Workflow Execution & System Behaviour Semantics**.

**Consumption inventory:** see `docs/GOVERNANCE_CONSUMPTION_MAP.md` and `services/governance_coverage_registry.py` for Phase 1 surface-level enforcement metadata (CI).

---

## Required statements (contract)

1. **EXTERNAL_ASSESSMENT_EVIDENCE** may record an assessment and supporting documents; **unresolved follow-up actions or incomplete evidence components can leave compliance / operational risk incomplete** even when a row appears satisfied at the summary layer.
2. **ACTIVE_STANDARD / CONDITION_STANDARD** obligations **must not** be marked compliant from **document-only** evidence or upload-primary CTAs; closure tracks **operational convergence** (issues, remediation, read-only signals).
3. **GUIDED_DECLARATION** records a **declared process** (structured declaration); it is **not** external statutory verification.
4. **DOCUMENT_UPLOAD** can **directly satisfy** certificate-style obligations **where** evidence authority and scoring accept uploaded certificates/reports as authoritative for that obligation (gas, EICR, EPC, etc.).
5. **TENANT_DELIVERY** records **delivery proof and declaration**, not legal verification of statutory compliance.

---

## Workflow Semantics and Compliance Meaning

Normative contracts: each workflow class preserves **distinct lifecycle meanings**. Implementation must keep **evidence recorded**, **obligation satisfied**, **remediation complete**, **operational risk resolved**, and **audit history appended** as **separable concepts**.

### DOCUMENT_UPLOAD

| Dimension | Contract |
|-----------|----------|
| **Fundamentally represents** | Certificate/report obligations where an authoritative file is the primary artefact when registry and evidence authority accept uploads. |
| **What evidence means** | Controlled linked documents (plus metadata such as expiry). |
| **What completion means** | Valid evidence + engine/scoring satisfaction — **not** automatic remediation closure elsewhere. |
| **May directly affect compliance confidence** | Yes — **typically strong direct confidence** where scoring maps satisfied obligations to headline inputs (semantic only; no weights here). |
| **May directly resolve operational risk** | Not inherently — unless explicitly coupled to inspection/remediation flows out of band. |
| **Uploads alone sufficient** | **Yes where** policy designates upload as authoritative closure path for that obligation. |
| **Audit / reporting** | Evidence-of-record events append to timeline; renewals/expiry may generate attention independently. |
| **Typical examples** | Gas safety, EICR, EPC, licence certificates. |
| **Explicit non-equivalence** | Evidence presence **≠** remediation done; certificate row **≠** all hazards cleared platform-wide. |

### GUIDED_DECLARATION

| Dimension | Contract |
|-----------|----------|
| **Fundamentally represents** | Structured declaration of facts — **platform record-keeping**, not statutory verification. |
| **Evidence means** | Structured payload primary; documents **supporting**. |
| **Completion means** | Required fields + completeness rules satisfied — **not** Home Office / court / scheme verification. |
| **Compliance confidence** | **Moderate / contextual** — quality and completeness gates matter. |
| **Operational risk resolution** | Not implied by declaration alone. |
| **Uploads alone sufficient** | **No** when structured-first is required. |
| **Audit / reporting** | Declarations append as audit events with disclosure boundaries. |
| **Examples** | Right to Rent, deposit duties, Wales occupation contract, tenancy agreement declarations. |
| **Non-equivalence** | Declaration **≠** verified proof; structured payload **≠** optional add-on to raw PDF-only shortcuts. |

### EXTERNAL_ASSESSMENT_EVIDENCE

| Dimension | Contract |
|-----------|----------|
| **Fundamentally represents** | Structured external assessment + supporting report; assessment drives follow-ups. |
| **Evidence means** | Structured assessment record; upload is **supporting**. |
| **Completion means** | Schema satisfied **may still coexist** with open actions / incomplete completeness. |
| **Compliance confidence** | **Conditional** — improving completeness **does not** automatically imply improved headline confidence without resolving findings. |
| **Operational risk** | Unresolved actions may leave hazard/remediation posture **incomplete** despite uploads. |
| **Upload improving confidence alone** | **Must not** automatically improve compliance confidence without resolving conditional gaps (semantic governance). |
| **Examples** | Legionella, lead testing assessments. |
| **Non-equivalence** | Assessment recorded **≠** remediation complete; report upload **≠** risk resolved. |

### TENANT_DELIVERY

| Dimension | Contract |
|-----------|----------|
| **Represents** | Proof of **delivery** of prescribed materials. |
| **Evidence** | Structured delivery record; uploads corroborate only. |
| **Completion** | Delivery duty record complete — **not** adjudication of tenancy law outcomes. |
| **Confidence** | Delivery-record lane — distinct from certificate confidence. |
| **Uploads alone** | **Insufficient** as sole closure when structured delivery is normative. |
| **Non-equivalence** | File present **≠** lawful delivery proved in court sense. |

### REGISTRATION_TRACKING

| Dimension | Contract |
|-----------|----------|
| **Represents** | Declared registration/scheme facts — **not** automatic regulator confirmation. |
| **Completion** | Structured fields per policy — external registers may disagree. |
| **Confidence** | Registration-record semantics — contextual. |
| **Non-equivalence** | Registration evidence **≠** enrolment verified by authority. |

### MULTI_EVIDENCE

| Dimension | Contract |
|-----------|----------|
| **Represents** | Multiple components/modes — completeness is **component-aware**. |
| **Completion** | Component completeness **may diverge** from headline satisfied status. |
| **Confidence** | Multi-component semantics — one generic upload **must not** stand in for all components. |
| **Non-equivalence** | Headline status **≠** component completeness; presence of one file **≠** all obligations within family met. |

### GUIDANCE_ONLY

| Dimension | Contract |
|-----------|----------|
| **Represents** | Informational / navigation — not certificate closure. |
| **Completion** | Not upload-driven satisfaction semantics. |
| **Confidence** | Guidance lane — not interchangeable with certificate confidence. |
| **Non-equivalence** | Guidance viewed **≠** obligation satisfied as certificate-style. |

### CONDITION_STANDARD / ACTIVE_STANDARD

| Dimension | Contract |
|-----------|----------|
| **Represents** | Operational convergence for habitability/repair standards — **presentation-derived profile** may layer on `GUIDANCE_ONLY` runtime. |
| **Completion** | Operational signals (issues, remediation, read-only summaries) — **not** single-document proof. |
| **Compliance confidence** | Derived from **operational convergence** — unresolved hazards/issues/work orders influence posture. |
| **Document upload** | **Must not** alone resolve confidence or imply standard met. |
| **Non-equivalence** | Document upload **≠** standard satisfied; operational remediation **≠** evidence upload lifecycle. |

---

## Non-Equivalence Rules

Normative rules — **must not** be contradicted by UX, copy, or shortcuts:

1. **Evidence presence** does **not** necessarily imply **compliance completion** for the obligation.
2. **Assessment completion** (fields filled / report attached) does **not** necessarily imply **remediation completion**.
3. **Structured declaration** does **not** imply **statutory or third-party verification**.
4. **Condition-standard** obligations **must not** be closed solely from **document presence**.
5. **Operational remediation** lifecycles and **evidence recording** lifecycles are **separate** states that may advance independently.
6. **Obligation satisfied** (per engine/scoring row) **≠** **operational risk resolved** platform-wide.

---

## Compliance Confidence Interpretation

Workflow classes inform **how score-related confidence should be read semantically** — **not** numeric formulas or weights.

| Workflow class | Confidence interpretation (semantic) |
|----------------|-------------------------------------|
| **DOCUMENT_UPLOAD** | Typically **strong direct** mapping where scoring treats satisfied certificate-type obligations as authoritative inputs. |
| **GUIDED_DECLARATION** | **Moderate / contextual** — declaration completeness and quality gates matter; not external verification. |
| **EXTERNAL_ASSESSMENT_EVIDENCE** | **Conditional** — assessment may improve completeness visibility; unresolved findings may **reduce** operational confidence; **upload alone must not automatically lift compliance confidence**. |
| **CONDITION_STANDARD / ACTIVE_STANDARD** | Confidence from **operational convergence** — hazards/issues/work orders inform posture; **upload alone must not resolve confidence**. |
| **MULTI_EVIDENCE** | **Component-aware** — avoid interpreting headline satisfaction as component completeness. |
| **TENANT_DELIVERY / REGISTRATION_TRACKING** | Record lanes distinct from certificate-equivalent confidence. |
| **GUIDANCE_ONLY** | Informational lane — not certificate confidence. |

---

## Lifecycle Recalculation Semantics

These lifecycle operations are **distinct** and may occur **independently**:

| Operation | Meaning |
|-----------|---------|
| **A. Requirement truth recalculation** | Row-level obligation truth/enrichment refresh from registry + evidence authority rules. |
| **B. Compliance score recalculation** | Portfolio/property scoring refresh — **not** implied by every evidence mutation alone. |
| **C. Risk regeneration** | Predictive / operational risk surfacing — separate pipeline from obligation row truth. |
| **D. Attention / task regeneration** | Today / priorities / inbox projections — orchestration layer, not identical to score or truth. |
| **E. Audit timeline append** | Immutable-style event trail for actions taken — does **not** substitute for A–D. |

Clarifications:

- Not every evidence event implies **score improvement**.
- Not every upload **resolves risk**.
- Not every remediation step **closes** every obligation row.

---

## Forbidden Workflow Collapses

Governance invariants — **must not** ship interpretations or UX that imply:

1. Collapsing **all** workflows into **document-presence** semantics.
2. Treating **assessment report upload** as **remediation closure** by itself.
3. Treating **operational / condition standards** as **certificate obligations**.
4. Interpreting **declarations** as **externally verified proof** without a verification authority.
5. Deriving **condition-standard completion** solely from **uploaded files**.
6. Equating **audit history entries** with **operational risk resolution**.

Machine-readable `forbidden_collapses` tokens live in `services/workflow_behaviour_governance.py` per workflow profile.

---

## Reporting and Audit Surface Semantics

Reporting UIs, CSV/PDF exports, and third-party packs must **not** flatten every obligation into the same **“compliant / not compliant”** story. This section is **semantic governance only** — it does **not** prescribe implementation of any report generator.

**Surfaces referenced below**

| Surface | Meaning |
|---------|---------|
| **Compliance reports** | Portfolio/property obligation summaries and scoring-aligned views. |
| **Audit exports** | Immutable-style timelines of actions and evidence events for audit defence. |
| **Lender / tribunal exports** | Evidence packs or summaries prepared for lenders, insurers, or dispute contexts — **authority-sensitive**. |
| **Operational remediation reports** | Work-order, hazard, inspection, and remediation-progress style narratives (distinct from certificate expiry). |
| **Risk summaries** | Residual exposure / attention prioritisation — not identical to obligation row status. |
| **Expiry reports** | Certificate and dated obligation renewal / overdue posture. |
| **Evidence completeness reports** | Component-level or policy-driven completeness states vs headline satisfaction. |

---

### DOCUMENT_UPLOAD

| Surface | Expected presence |
|---------|-------------------|
| Compliance reports | **Strong** — headline obligation status is typically meaningful here. |
| Audit exports | **Yes** — certificate evidence-of-record events. |
| Lender / tribunal exports | **Yes** — suitable for **certificate-centric evidence packs** where policy allows. |
| Operational remediation reports | **No by default** — certificate rows do not substitute for unrelated hazard/remediation programmes unless explicitly linked elsewhere. |
| Risk summaries | **Yes** — portfolio gaps and overdue certificates. |
| Expiry reports | **Yes** — primary lifecycle surface for dated certificates. |
| Evidence completeness reports | **Yes** — usually aligned with single authoritative artefact; still distinguish **evidence recorded** vs **operational risk resolved**. |

**Narrative emphasis:** Certificate-centric language; expiry and renewal; avoid implying unrelated remediation closure.

---

### GUIDED_DECLARATION

| Surface | Expected presence |
|---------|-------------------|
| Compliance reports | **Yes** — as **declaration-record** lanes, not certificate-equivalent. |
| Audit exports | **Yes** — who recorded, when, amendments. |
| Lender / tribunal exports | **Contextual** — include **only with disclosure** that entries are **declared records**, not regulator verification. |
| Operational remediation reports | **No** — unless the obligation explicitly ties declarations to operational workflows. |
| Risk summaries | **Contextual** — open follow-ups or incomplete declaration gates. |
| Expiry reports | **Usually secondary** — unless policy attaches dated duties to declarations. |
| Evidence completeness reports | **Yes** — structured completeness vs supporting uploads. |

**Narrative emphasis:** Declaration-centric copy; include **actor**, **timestamp**, **supporting evidence presence**, **unresolved follow-ups**. **Must not** imply statutory or external verification automatically.

---

### EXTERNAL_ASSESSMENT_EVIDENCE

| Surface | Expected presence |
|---------|-------------------|
| Compliance reports | **Yes** — often conditional on completeness layers. |
| Audit exports | **Yes** — assessment events and linked reports. |
| Lender / tribunal exports | **Contextual** — disclose conditional findings and open actions. |
| Operational remediation reports | **Strong** — assessment drives hazard/remediation narrative. |
| Risk summaries | **Strong** — unresolved findings weigh on posture. |
| Expiry reports | **Contextual** — **review dates** / reassessment cadence where applicable. |
| Evidence completeness reports | **Strong** — headline satisfied **must not** hide incomplete components. |

**Narrative emphasis:** Findings, **unresolved actions**, **review dates**, **assessor / assessment identity** where available. **Assessment completion must not be reported as remediation completion.**

---

### TENANT_DELIVERY

| Surface | Expected presence |
|---------|-------------------|
| Compliance reports | **Yes** — delivery-duty posture distinct from certificates. |
| Audit exports | **Yes** — structured delivery records and corroborating uploads. |
| Lender / tribunal exports | **Contextual** — “how to rent” style packs; label as **delivery proof**, not adjudication. |
| Operational remediation reports | **No by default**. |
| Risk summaries | **Contextual** — missed delivery / outstanding duties. |
| Expiry reports | **Rare** — unless tied to periodic duties. |
| Evidence completeness reports | **Yes** — structured vs supporting-only uploads. |

**Narrative emphasis:** Delivery and acknowledgement semantics; avoid **certificate-style “compliant”** wording.

---

### REGISTRATION_TRACKING

| Surface | Expected presence |
|---------|-------------------|
| Compliance reports | **Yes** — registration posture as **declared records**. |
| Audit exports | **Yes**. |
| Lender / tribunal exports | **Contextual** — disclose that platform holds **declarations**, not live regulator confirmation. |
| Operational remediation reports | **No by default**. |
| Risk summaries | **Contextual** — missing registration / scheme gaps. |
| Expiry reports | **Contextual** — scheme renewal dates where modelled. |
| Evidence completeness reports | **Yes**. |

**Narrative emphasis:** Registration facts vs external register confirmation; proofs as secondary.

---

### MULTI_EVIDENCE

| Surface | Expected presence |
|---------|-------------------|
| Compliance reports | **Yes** — headline status may diverge from components. |
| Audit exports | **Yes**. |
| Lender / tribunal exports | **Only when completeness narrative is accurate** — packs must list **components**, not a single file. |
| Operational remediation reports | **Contextual** — where components imply inspections or alarms maintenance. |
| Risk summaries | **Yes** — component gaps drive attention. |
| Expiry reports | **Component-dependent**. |
| Evidence completeness reports | **Primary surface** — component grid vs headline. |

**Narrative emphasis:** Never summarise as “one upload satisfies all components.”

---

### GUIDANCE_ONLY

| Surface | Expected presence |
|---------|-------------------|
| Compliance reports | **Informational** — not certificate closure semantics. |
| Audit exports | **Yes** — interactions and acknowledgements where captured. |
| Lender / tribunal exports | **Generally exclude** as proof of technical compliance unless explicitly scoped. |
| Operational remediation reports | **No** — unless routed via maintenance CTAs with distinct semantics. |
| Risk summaries | **Low** — navigation-only unless mapped to operational elsewhere. |
| Expiry reports | **Generally no**. |
| Evidence completeness reports | **Low** — uploads are not authoritative closure. |

**Narrative emphasis:** Guidance and operational routing — avoid **“compliant”** certificate language.

---

### CONDITION_STANDARD / ACTIVE_STANDARD

| Surface | Expected presence |
|---------|-------------------|
| Compliance reports | **Longitudinal / operational** — not a single green/red certificate snapshot. |
| Audit exports | **Yes** — operational summaries and remediation history. |
| Lender / tribunal exports | **Highly contextual** — avoid certificate-pack equivalence; disclose operational posture. |
| Operational remediation reports | **Primary** — issue history, remediation progress, repeat incidents. |
| Risk summaries | **Strong** — unresolved hazards/issues/work orders. |
| Expiry reports | **Not primary** — unless dates attach to statutory notices modelled separately. |
| Evidence completeness reports | **Contextual** — supplementary uploads vs convergence signals. |

**Narrative emphasis:** **Issue history**, **remediation progress**, **unresolved hazards**, **work-order verification**, **repeat incidents**. **Uploads alone must not generate “resolved / compliant” reporting language.**

Machine-readable **reporting visibility** and boolean hints (`supports_lender_export`, `supports_operational_risk_reporting`, etc.) live in `services/workflow_behaviour_governance.py` alongside each workflow profile.

---

## Workflow Execution & System Behaviour Semantics

This section defines **expected system behaviour contracts** when a workflow completes or when evidence mutates: what may be recalculated, what may **not** be conflated, and how score and audit surfaces should be read. It is **governance and audit semantics only** — it does **not** prescribe new runtime schedulers, change scoring formulas, or replace evidence authority.

**Contract columns**

| Letter | Meaning |
|--------|---------|
| **A. User outcome** | What the user achieves after successful workflow completion. |
| **B. System outcome** | What the platform is **expected** to execute or regenerate (when product pipelines exist) — distinct lifecycles may run independently. |
| **C. Completion authority** | Whether the workflow **may** directly satisfy the obligation row (vs informational / operational-only). |
| **D. Score impact semantics** | How strongly the workflow **may** influence compliance confidence / headline score (semantic strength only — **no weights**). |
| **E. Risk / remediation semantics** | Whether unresolved operational risk or remediation may remain after “completion”. |
| **F. Reporting impact** | Which reporting surfaces should reflect updates (see **Reporting and Audit Surface Semantics**). |
| **G. Audit impact** | What should append to audit / history trails. |
| **H. Non-equivalence** | What successful completion **explicitly does not** imply. |

Machine-readable execution fields (`execution_triggers`, `system_execution_effects`, `may_trigger_*`, `completion_authority`, `score_impact_strength`, `non_equivalence_rules`, etc.) are in `services/workflow_behaviour_governance.py` under **`EXECUTION_SEMANTICS_METADATA`** (merged into `get_workflow_capabilities()`). **Runtime engines must not consume these fields until explicitly wired.**

---

## Forbidden compliance representation (language governance)

Certain **high-assurance** words (**compliant**, **verified**, **resolved**, **safe**, **audit-ready**, …) must **not** appear on **primary CTAs** or status surfaces **without** the workflow class and evidence authority that support that assurance.

| Term / phrase | Risk | Typical forbidden context |
|---------------|------|----------------------------|
| **Verified** / verification passed | Implies external or statutory verification | **GUIDED_DECLARATION** primary label without platform disclosure |
| **Audit-ready** | Implies defensible third-party audit outcome | **GUIDED_DECLARATION** primary label |
| **Operationally safe** / completely safe | Implies hazard closure | **EXTERNAL_ASSESSMENT_EVIDENCE** primary label without remediation proof |
| **Fully compliant** / statutorily compliant | Implies certificate-equivalent closure | Non-**DOCUMENT_UPLOAD** workflows |

**Machine-readable:** `FORBIDDEN_REPRESENTATION_GOVERNANCE` and `FORBIDDEN_ASSURANCE_TERMS` in `workflow_behaviour_governance.py`. **Additive audit flags** (e.g. `FORBIDDEN_COMPLIANCE_REPRESENTATION`, `DECLARATION_PRESENTED_AS_AUDIT_READY`) are emitted by `governance_augment_mismatch_flags` using **heuristic** primary-label scans — **audit-only**, no runtime blocking in Phase 1.

---

### DOCUMENT_UPLOAD

**Examples:** gas safety, EICR, EPC, PAT (`portable_appliance_test`), licence certificates, fire alarm certificate style obligations where policy treats upload as authoritative.

| | Contract |
|---|----------|
| **A. User outcome** | Statutory or policy-defined proof uploaded; obligation **may** become satisfied/verified where evidence authority accepts; **expiry tracking** and **renewal reminders** apply where modelled. |
| **B. System outcome** | Evidence authority updated; requirement truth recalculated; compliance gaps **may** narrow; expiry lifecycle and reminders **may** regenerate; audit timeline appended; reports and command-centre priorities **may** refresh. |
| **C. Completion authority** | **MAY** directly satisfy the requirement when registry and evidence authority accept certificate-style closure. |
| **D. Score impact** | **HIGH / direct** — first-class satisfied-obligation input where scoring maps certificates (semantic only). |
| **E. Risk / remediation** | Does **not** imply unrelated **operational remediation** is complete; does **not** imply **tenant delivery** duties are met unless separately tracked. |
| **F. Reporting** | Strong compliance-report and expiry visibility; lender packs where policy allows (see reporting section). |
| **G. Audit** | Certificate evidence-of-record events; renewal/amendment history. |
| **H. Non-equivalence** | Certificate row **≠** all hazards remediated; upload **≠** tenant delivery complete. |

---

### GUIDED_DECLARATION

**Examples:** right to rent, deposit protection (`deposit_pi`), tenancy agreement, Wales occupation contract (where in scope).

| | Contract |
|---|----------|
| **A. User outcome** | Structured declaration recorded; optional supporting evidence attached. |
| **B. System outcome** | Structured evidence record created; requirement truth recalculated; evidence completeness **may** recalculate; follow-up reminders **may** schedule; audit history appended; reports **may** refresh. |
| **C. Completion authority** | **MAY** satisfy the obligation **subject to** completeness and policy rules — **not** automatic on partial payloads. |
| **D. Score impact** | **MODERATE / contextual** — declaration-confidence lane; **lower** than statutory certificate workflows semantically. |
| **E. Risk / remediation** | Does not extinguish unrelated operational risk. |
| **F. Reporting** | Declaration-centric; disclose platform-side record-keeping. |
| **G. Audit** | Declarations and amendments as declared records. |
| **H. Non-equivalence** | **≠** external legal verification; **≠** statutory authority confirmation; **≠** independently verified compliance. |

---

### EXTERNAL_ASSESSMENT_EVIDENCE

**Examples:** legionella, lead testing (Scotland-scoped product intent).

| | Contract |
|---|----------|
| **A. User outcome** | Assessment outcome recorded; findings captured; follow-up actions tracked. |
| **B. System outcome** | Assessment evidence stored; risk projections **may** refresh; remediation follow-up **may** be generated; review scheduling **may** activate; audit timeline updated; operational views **may** refresh. |
| **C. Completion authority** | Assessment completion **may** improve evidence completeness; **must not** alone imply **remediation completion**. |
| **D. Score impact** | **CONDITIONAL** — unresolved high-risk findings **may** reduce operational confidence; assessment upload **≠** automatic score uplift. |
| **E. Risk / remediation** | Unresolved actions **may** leave hazard posture incomplete despite obligation row headlines. |
| **F. Reporting** | Operational risk emphasis; disclose open actions and review dates. |
| **G. Audit** | Assessment events + linked reports; remediation trail separate. |
| **H. Non-equivalence** | Assessment complete **≠** remediation complete; uploaded report **≠** operationally compliant; recorded assessment **≠** risk resolved. |

---

### TENANT_DELIVERY

**Examples:** How to Rent (England & Wales) delivery duty.

| | Contract |
|---|----------|
| **A. User outcome** | Structured delivery record captured; optional proof upload. |
| **B. System outcome** | Same class of regenerations as guided declaration (truth, completeness, gaps, attention, audit, reports) where pipelines exist. |
| **C. Completion authority** | **MAY** satisfy delivery-duty tracking per policy — **not** court adjudication. |
| **D. Score impact** | **MODERATE / contextual** — delivery-record lane. |
| **E. Risk / remediation** | Unrelated operational risk unchanged. |
| **F. Reporting** | Delivery-duty narratives; not certificate packs by default. |
| **G. Audit** | Delivery declarations + corroboration. |
| **H. Non-equivalence** | File present **≠** lawful service proved in court sense. |

---

### REGISTRATION_TRACKING

**Examples:** landlord registration (jurisdiction-specific variants), rent smart Wales, NI registration.

| | Contract |
|---|----------|
| **A. User outcome** | Registration facts declared; optional proof upload. |
| **B. System outcome** | Truth, gaps, attention, audit, reports, optional expiry/review scheduling where modelled. |
| **C. Completion authority** | **MAY** satisfy per policy — **not** regulator live confirmation. |
| **D. Score impact** | **MODERATE / contextual** — registration-record lane. |
| **E. Risk / remediation** | Operational remediation distinct. |
| **F. Reporting** | Registration posture; disclose declared-record semantics. |
| **G. Audit** | Registration events; proofs secondary. |
| **H. Non-equivalence** | Registration document **≠** enrolment verified by authority. |

---

### MULTI_EVIDENCE

**Examples:** smoke / heat / CO alarms family (`smoke_heat_alarms`), HMO fire risk evidence where modelled as multi-component.

| | Contract |
|---|----------|
| **A. User outcome** | Evidence per required component/mode until completeness satisfied. |
| **B. System outcome** | Completeness and truth recalculations; gaps and attention **component-aware**; audit and reports reflect component grid. |
| **C. Completion authority** | **Component-aware** — headline row **must not** substitute for all components. |
| **D. Score impact** | **Multi-component / contextual** — one upload must not stand in for all. |
| **E. Risk / remediation** | Residual exposure possible until all components satisfied. |
| **F. Reporting** | Evidence completeness reports primary. |
| **G. Audit** | Per-component evidence events where captured. |
| **H. Non-equivalence** | Headline satisfied **≠** every component complete. |

---

### GUIDANCE_ONLY

**Examples:** informational obligations without certificate closure.

| | Contract |
|---|----------|
| **A. User outcome** | Guidance consumed or operational route opened. |
| **B. System outcome** | Limited: audit/interaction append; attention **may** refresh; **no** automatic certificate-style score uplift from guidance alone. |
| **C. Completion authority** | **Does not** directly satisfy certificate-style obligations. |
| **D. Score impact** | **LOW / informational** — not interchangeable with certificate confidence. |
| **E. Risk / remediation** | Does not directly clear operational risk. |
| **F. Reporting** | Informational surfaces only. |
| **G. Audit** | Views/acknowledgements where captured — not compliance proofs. |
| **H. Non-equivalence** | Guidance viewed **≠** certificate satisfied. |

---

### CONDITION_STANDARD / ACTIVE_STANDARD

**Examples:** fitness for human habitation, repairing standard (operational convergence).

| | Contract |
|---|----------|
| **A. User outcome** | Remediation lifecycle managed; issues and property condition monitored. |
| **B. System outcome** | Issues, work orders, hazards, and convergence signals evaluated; operational convergence **may** recalculate; audit and operational reports **may** update. |
| **C. Completion authority** | **MUST NOT** complete from **single upload alone**; closure follows operational convergence semantics. |
| **D. Score impact** | **Distributed / operational** — driven by unresolved hazards, remediation age, blocked works, repeat incidents (semantic only). |
| **E. Risk / remediation** | Unresolved hazards/issues **may** remain despite peripheral uploads. |
| **F. Reporting** | Longitudinal operational reporting (see reporting section). |
| **G. Audit** | Operational summaries and remediation history lead narrative. |
| **H. Non-equivalence** | Document upload **≠** compliant condition standard; inspection upload **≠** hazard resolved; closed task **≠** operationally safe without convergence signals. |

---

## Workflow classes

### 1. DOCUMENT_UPLOAD

| Aspect | Policy |
|--------|--------|
| **Purpose** | Certificate/report obligations where a controlled document is the primary artefact of compliance (e.g. gas safety certificate, EICR, EPC). |
| **What evidence means** | Authoritative file(s) linked to the obligation; may include expiry metadata. |
| **What “complete” means** | Valid linked evidence accepted by authority + obligation satisfied per engine/scoring (not expanded here). |
| **Directly satisfy requirement** | Yes — when evidence authority accepts upload path. |
| **Directly affect score** | Yes — via existing scoring hooks for satisfied obligations. |
| **Score recalculation** | Yes — standard obligation updates / registry triggers (unchanged). |
| **Follow-ups** | Expiry / renewal flows may create attention items. |
| **Remediation may remain open** | Typically no for pure certificate rows; separate jobs/issues are orthogonal. |
| **Allowed primary CTAs** | Upload / guided wrapper that lands in document capture; coordinate inspection where configured. |
| **Prohibited CTAs** | Presentation that implies statutory verification beyond evidence-of-record. |
| **Audit / report** | Certificate-style evidence-of-record. |
| **Examples** | `gas_safety`, `eicr`, `epc`, many licence uploads. |
| **Forbidden mistakes** | Treating certificate workflow as “any file suffices” without mode discipline; publishing registry rows with **no** `DOCUMENT_UPLOAD` evidence mode for a DOCUMENT_UPLOAD class reference. |

---

### 2. GUIDED_DECLARATION

| Aspect | Policy |
|--------|--------|
| **Purpose** | Structured checklist capturing landlord-declared facts (Right to Rent, deposit duties, Wales occupation contract, tenancy agreement declarations, etc.). |
| **What evidence means** | Structured payload first; documents are **supporting**. |
| **What “complete” means** | Required declaration fields satisfied **and** policy completeness rules; not external verification. |
| **Directly satisfy requirement** | Yes — when declaration + authority rules say satisfied. |
| **Score impact** | Declaration confidence model — not third-party attestation. |
| **Score recalculation** | Yes when obligation state changes. |
| **Follow-ups** | Optional follow-up fields / dates where schema requires. |
| **Remediation may remain open** | Yes — declaration does not close unrelated operational work. |
| **Allowed primary CTAs** | Guided evidence resolution / direct structured evidence actions. |
| **Prohibited CTAs** | **Upload-only primary** where registry expects structured-first (document-only overrides are drift). |
| **Audit / report** | Structured declaration record; flags when registry allows document-only without structured mode. |
| **Examples** | `right_to_rent`, `deposit_pi` family, `wales_occupation_contract`, `tenancy_agreement`. |
| **Forbidden mistakes** | **GUIDED_DECLARATION_WITHOUT_STRUCTURED_PAYLOAD**; collapsing to “upload PDF = done”. |

---

### 3. TENANT_DELIVERY

| Aspect | Policy |
|--------|--------|
| **Purpose** | Proof of **delivery** of prescribed materials (e.g. How to Rent). |
| **What evidence means** | Structured delivery record; optional supporting upload. |
| **What “complete” means** | Delivery declaration complete per schema — **not** proof of legal outcome. |
| **Directly satisfy requirement** | Yes within applicability. |
| **Score impact** | Delivery record model. |
| **Allowed primary CTAs** | Guided delivery declaration. |
| **Prohibited CTAs** | Upload-primary as sole path when structured delivery is required. |
| **Examples** | `how_to_rent`. |
| **Forbidden mistakes** | Equating “uploaded leaflet” with “lawfully delivered” without structured record. |

---

### 4. REGISTRATION_TRACKING

| Aspect | Policy |
|--------|--------|
| **Purpose** | Scheme / landlord registration facts captured as structured records (Wales, Scotland, NI, etc.). |
| **Evidence** | Structured first; supporting documents secondary. |
| **Complete** | Registration fields + evidence policy — not automatic legal enrolment verification by the platform. |
| **Allowed primary CTAs** | Guided structured capture. |
| **Prohibited CTAs** | Document-only primary where structured registration record is required. |
| **Examples** | `landlord_registration`, `rent_smart_wales`, `scotland_landlord_registration`. |

---

### 5. EXTERNAL_ASSESSMENT_EVIDENCE

| Aspect | Policy |
|--------|--------|
| **Purpose** | External professional assessment workflows (Legionella, lead testing, etc.): structured assessment + optional report upload. |
| **What evidence means** | Structured assessment record; report upload is **supporting**. |
| **What “complete” means** | Assessment schema satisfied; **follow-up actions may still be required** even when status appears satisfied — **ASSESSMENT_COMPLETED_WITH_UNRESOLVED_ACTIONS** when completeness disagrees with satisfaction proxies. |
| **Score impact** | **Assessment conditional** — not a single guaranteed score bump from one upload. |
| **Remediation may remain open** | **Yes** — actions from assessment may require operational follow-through. |
| **Allowed primary CTAs** | Guided assessment / structured modes; not upload-only-as-authority. |
| **Forbidden mistakes** | **LEGIONELLA_EXTERNAL_ASSESSMENT_DOCUMENT_ONLY**-style drift; believing “report uploaded” closes all residual actions. |

---

### 6. MULTI_EVIDENCE

| Aspect | Policy |
|--------|--------|
| **Purpose** | Obligations requiring **multiple evidence components** (e.g. unified domestic alarms: smoke + conditional CO). |
| **What evidence means** | Multiple modes/components; completeness may differ from top-level requirement status. |
| **Complete** | Completeness layer tracks components — **must not** collapse to single generic upload when registry expects components. |
| **Score impact** | Multi-component model; incomplete components may still surface audit signals while headline status is satisfied. |
| **Examples** | `smoke_heat_alarms`, multi-part fire evidence families. |
| **Forbidden mistakes** | One generic document fulfilling every component without tagging / policy discipline. |

---

### 7. GUIDANCE_ONLY

| Aspect | Policy |
|--------|--------|
| **Purpose** | Informational / navigation obligations without certificate-style closure via upload alone. |
| **Directly satisfy requirement** | Generally **no** via upload-only primary CTA. |
| **Score impact** | Guidance-only model — does not behave like certificate satisfaction. |
| **Remediation** | May remain open; separate operational streams apply. |
| **Allowed primary CTAs** | View guidance, operational navigation (issues, remediation). |
| **Prohibited CTAs** | Upload-primary presented as compliance closure. |

---

### 8. ACTIVE_STANDARD / CONDITION_STANDARD (presentation-derived)

| Aspect | Policy |
|--------|--------|
| **Runtime note** | Resolver/runtime may keep **GUIDANCE_ONLY**; governance capability profile **`CONDITION_STANDARD_ACTIVE_STANDARD`** applies to `fitness_for_human_habitation`, `repairing_standard`. |
| **Purpose** | Condition standards monitored via **operational signals** (issues, remediation), not single-document proof. |
| **Complete** | **Operational convergence** — not document upload. |
| **Must not complete from document-only** | **Yes** — single upload must not prove standard met. |
| **Audit** | Condition-standard drift flags (upload-primary, satisfied-without-signals, jurisdiction misuse). |

---

## Machine-readable matrix

Authoritative defaults: `services/workflow_behaviour_governance.py` → `WORKFLOW_CLASS_CAPABILITIES`.

## Enforcement today vs future

| Layer | Today |
|-------|--------|
| **Documentation** | This file + capability module describe intended behaviour. |
| **Runtime** | **Unchanged** — resolver, evidence, scoring paths not altered by governance helpers. |
| **Audit** | **Additive** flags on admin-enriched requirement rows (`requirement_workflow_audit`) — diagnostics only, non-blocking. |

Future work may wire CI or admin dashboards to these flags; **do not** use them to block tenant/client APIs without an explicit product decision.
