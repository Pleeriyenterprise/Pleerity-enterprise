# S2 risk assessment

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-PLANNING-01

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| R1 | API label change confuses customers when flag=active | Medium | High | Shadow mode; staged activation; legacy mirror fields |
| R2 | Class A shows Under review | Medium | High | Queue gate unit tests; class_a_review_leaks metric = 0 |
| R3 | Frontend still uses legacy fallbacks — user sees no improvement | High | Medium | Expected until S3; document; API fields ready |
| R4 | Enrich latency regression | Low | Medium | Projector pure function; benchmark p95 |
| R5 | Cognition/CTA still contradict badge | Medium | High | S2 updates cognition + actionability consumers |
| R6 | Reports still show retired phrases | High | Low | Deferred S4 — document known drift |
| R7 | Shadow log volume | Medium | Low | Sampling after 72h |
| R8 | Incorrect workflow class resolution | Medium | High | Fixture per canonical code; sign-off matrix |
| R9 | Satisfaction coupling reintroduces review language | Medium | High | Projector runs after satisfaction; satisfaction cannot override |
| R10 | Rollback confusion (flag vs deploy) | Low | Medium | Runbook in ROLLBACK_STRATEGY.md |

**Overall S2 risk:** **MEDIUM-HIGH** — first runtime phase; mitigated by shadow mode and no data migration.
