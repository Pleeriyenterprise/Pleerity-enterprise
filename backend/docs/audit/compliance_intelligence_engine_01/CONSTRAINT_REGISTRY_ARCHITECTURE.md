# Constraint Registry Architecture

**Programme:** COMPLIANCE-INTELLIGENCE-ENGINE-01  
**Refinement:** COMPLIANCE-INTELLIGENCE-ENGINE-ARCHITECTURE-REFINEMENT-02

---

## Purpose

Define the **Constraint Registry** — versioned, immutable sets of deterministic constraints applied during CIE calculation.

Every constraint that can affect artefact generation, ranking, or eligibility must be documented as a versioned registry object and pinned in provenance.

---

## Design principles

| Principle | Rule |
|-----------|------|
| Explicitness | No hidden guard clauses — constraints are registry objects |
| Versioning | `constraint_set_version` on every provenance |
| Immutability | Published constraint sets never modified |
| Evaluability | Each constraint has deterministic evaluation semantics |
| Auditability | `constraint_resolution` trace stage records pass/fail per constraint |

---

## Collection

**Name:** `compliance_intelligence_constraint_registry`  
**ID pattern:** `constraints_v{major}.{minor}.{patch}`

---

## Constraint set schema

```json
{
  "constraint_set_id": "constraints_v1.0.0",
  "semantic_version": "1.0.0",
  "published_at": "2026-06-01T00:00:00+00:00",
  "status": "active",
  "supersedes_constraint_set_id": null,
  "description": "CIE v1 deterministic constraint catalogue",
  "constraints": [
    {
      "constraint_id": "legal_jurisdiction_scope",
      "constraint_type": "jurisdiction",
      "severity": "blocking",
      "evaluation": "requirement.jurisdiction_id in scope.jurisdictions",
      "failure_code": "JURISDICTION_OUT_OF_SCOPE"
    },
    {
      "constraint_id": "evidence_completeness_min",
      "constraint_type": "evidence",
      "severity": "blocking",
      "evaluation": "source_decision_ids.length >= 1",
      "failure_code": "INSUFFICIENT_EVIDENCE"
    },
    {
      "constraint_id": "confidence_threshold_publish",
      "constraint_type": "confidence",
      "severity": "warning",
      "parameters": { "min_score": 60 },
      "failure_code": "LOW_CONFIDENCE"
    },
    {
      "constraint_id": "recommendation_eligibility",
      "constraint_type": "eligibility",
      "severity": "blocking",
      "evaluation": "template_match && !blocked_by_dependency",
      "failure_code": "NOT_ELIGIBLE"
    }
  ],
  "content_hash": "sha256:…"
}
```

---

## Constraint categories (v1 catalogue)

| Category | Examples |
|----------|----------|
| Legal constraints | Jurisdiction applicability, legislation effective dates |
| Jurisdiction constraints | Cross-border portfolio rules |
| Portfolio constraints | Scope limits, property count caps |
| Evidence completeness | Minimum decisions/snapshots required |
| Confidence thresholds | Publish vs draft eligibility |
| Commercial constraints | Cost ceiling, effort budget |
| Operational constraints | Capacity limits, WO eligibility |
| Recommendation eligibility | Template match, dependency unblock |

---

## Constraint resolution trace

```json
{
  "stage": "constraint_resolution",
  "registry_refs": {
    "constraint_set_version": "constraints_v1.0.0"
  },
  "metadata": {
    "evaluations": [
      {
        "constraint_id": "evidence_completeness_min",
        "passed": true,
        "failure_code": null
      },
      {
        "constraint_id": "recommendation_eligibility",
        "passed": false,
        "failure_code": "NOT_ELIGIBLE",
        "context": { "blocked_by": "req_abc" }
      }
    ],
    "blocking_failures": ["NOT_ELIGIBLE"]
  },
  "output_hash": "sha256:…"
}
```

When blocking constraints fail, artefact may still be emitted with `insufficient_evidence: true` — provenance records **why**.

---

## Severity model

| Severity | Behaviour |
|----------|-----------|
| `blocking` | Prevents artefact generation or marks insufficient |
| `warning` | Artefact generated; flagged in payload and explainability |
| `informational` | Recorded in trace only |

---

## Relationship to authority engines

Constraints **read** authoritative state — they do not mutate it:

| Constraint source | Read via |
|-------------------|----------|
| Rules | Graph Service / governed read adapter |
| Jurisdiction | Jurisdiction projection |
| Evidence | Snapshots at `as_of` |
| Legislation | Version pins in provenance |

Constraint registry defines **CIE-side evaluation rules** over authoritative data — not replacements for Rules Engine.

---

## Change management

| Event | Behaviour |
|-------|-----------|
| New constraint added | New `constraint_set_version` |
| Threshold changed | New version; comparison shows constraint diff |
| Constraint removed | Deprecate in new version; old provenance retains old set |

---

## Runtime context

`runtime_context_version` on provenance captures ambient execution context affecting constraint evaluation:

- Feature flags active at generation
- Environment (`staging` / `production`)
- Engine mode (`shadow` / `enabled`)

Distinct from constraint set — documents **context** not **rules**.

---

## CIE-2 implication

Recommendation eligibility and priority filtering in CIE-2 must flow through `constraint_resolution` stage with registry pin — not ad-hoc `if` statements without provenance trace.
