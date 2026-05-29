# Trust-language governance (Compliance Vault Pro)

**Status:** TIER_1 — behavioural authority for **customer-visible operational explanations**  
**Scope:** Scoring guidance, causal explanations, exports, email/timeline copy, KB/assistant messaging, confidence lines, cognition truth boundaries  
**Out of scope:** Scoring calculation logic, API field names, internal enums, admin-only diagnostics

**Principle:** *Transparent operational outcomes, opaque implementation mechanics.*

Companion code: `backend/services/trust_language_governance.py`, `frontend/src/utils/trustLanguageGovernance.js`

Related: `PRESENTATION_LANGUAGE_GOVERNANCE.md` (labels/formatters), `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` (score KPI authority)

---

## 1. Governance categories

### SAFE_OPERATIONAL_LANGUAGE

Use plain operational terms tied to records users can act on:

- accepted evidence / review pending
- overdue actions / expiring records
- maintenance issues / unresolved items
- uploads may not count until accepted
- score may improve when …

### FORBIDDEN_ENGINEERING_LANGUAGE

Must not appear in customer-visible copy:

- scoring engine, weighted contribution, bucket emphasis, model weighting
- heuristic allocation, point distribution, scoring formula
- CVP Score vX, credit in bucket, internal confidence model
- status score / expiry score / document score (internal component labels)

### FORBIDDEN_FALSE_PRECISION

Must not appear in customer-visible copy:

- “+15 points”, “moved by N points”, “Score +N”
- “this guarantees compliance”, deterministic point promises
- exact weighting disclosure

### SAFE_CAUSAL_EXPLANATIONS

Prefer specific operational causes:

- ✅ “Your score improved because electrical safety evidence was accepted.”
- ✅ “Open maintenance issues may reduce this area.”
- ✅ “Uploaded evidence may not affect the score until reviewed.”

Avoid vague-only causality as the **sole** explanation:

- ⚠️ “based on recent activity”
- ⚠️ “recent changes affected your score”
- ⚠️ “system updates”

Timing disclaimers (“may take a few minutes to refresh”) are allowed alongside causal detail.

---

## 2. Explainability tiers

All tiers must be served **simultaneously** — same facts, different depth per surface.

| Tier | Audience | Surfaces | Must show | Must not show |
|------|----------|----------|-----------|---------------|
| **1 — Casual** | Landlords checking status | Dashboard KPI, notifications, empty states | What’s wrong, next step | Weights, formulas, component names |
| **2 — Active** | Operators fixing items | Compliance score areas, drivers, Requirements | Area-level drag, causal hints | Engine architecture, point math |
| **3 — Professional** | Compliance-heavy users | PDF exports, definitions, KB, assistant | Operational reasoning, progression | Model internals, reverse-engineering hints |

---

## 3. Copy authority registry

**Rule:** Extend the registered module for a surface. Do not add parallel hardcoded explanation strings in components/routes.

| Concern | Authority |
|---------|-----------|
| Portal scoring UI | `frontend/src/utils/scoringExplanationCopy.js` |
| Score freshness / async honesty | `frontend/src/utils/scoreFreshnessUi.js` |
| Action confidence lines | `frontend/src/utils/confidenceUxCopy.js` |
| Workspace orientation | `frontend/src/utils/workspaceOrientationCopy.js` |
| Jurisdiction trust | `frontend/src/utils/jurisdictionComplianceCopy.js` |
| Presentation labels | `frontend/src/utils/presentationLanguage.js` |
| Forbidden-term validation | `frontend/src/utils/trustLanguageGovernance.js` |
| PDF / KB seed / email / timeline | `backend/services/scoring_explanation_copy.py` |
| Trend + assistant score context | `backend/services/trust_language_governance.py` |
| Assistant KB runtime | `backend/docs/assistant_kb/*.md` |
| Assistant system prompt | `backend/services/assistant_prompt.py` |

**Dual-source parity:** JS and Python scoring modules must stay aligned on shared keys (area labels, disclaimers). When changing one, update the other or add a parity test failure.

---

## 4. AI / generated response rules

1. Assistant prompt includes `ASSISTANT_TRUST_LANGUAGE_RULES` from governance module.
2. `assistant_retrieval_service` injects `score_explanation` through `filter_assistant_score_context()`.
3. `compliance_trending.get_score_change_explanation()` uses `build_score_trend_explanation()` — causal, no points.
4. Do not invent scoring mechanics, weights, or guarantees in LLM output.
5. Post-filter: `sanitize_customer_copy()` may strip precision leaks from generated text before display (support tooling).

---

## 5. Drift prevention

| Guard | Location |
|-------|----------|
| Forbidden engineering terms | `trustLanguageGovernance.js` + `trust_language_governance.py` |
| Scoring copy unit tests | `scoringExplanationCopy.test.js`, `test_scoring_explanation_copy.py` |
| Governance unit tests | `trustLanguageGovernance.test.js`, `test_trust_language_governance.py` |
| Secondary surface audit | `tmp_prelaunch_scoring_trust_consistency_pdf_kb_01.py` |
| Programme closeout harness | `tmp_prelaunch_trust_language_governance_01.py` |

**Adding new customer explanation copy:**

1. Add to the appropriate authority module in the registry.  
2. Run `validate_customer_copy()` / frontend `validateCustomerCopy()` in tests.  
3. Do not add page-local scoring methodology strings.

---

## 6. Change control

- Normative changes require update to this doc **and** the governance Python/JS modules.
- Scoring **logic** changes do not automatically change trust copy — copy changes are separate PRs.
- Promote audit findings from TIER_3 JSON into this doc when they become rules.
