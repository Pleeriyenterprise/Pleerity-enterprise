# Review authority decision report

**Programme:** PRELAUNCH-CER-AUTHORITY-GOVERNANCE-DECISION-01  
**Generated:** 20260531T130149Z

## Decision summary

| Review type | Owner | Mechanism | Requirement families |
|-------------|-------|-----------|---------------------|
| Certificate verification | **Pleerity platform admin** | `GET /api/admin/documents/pending-verification` + verify | D — PLATFORM_VERIFIED |
| Organisation internal verify | **Landlord org admin** (admin-like client role) | `POST .../compliance-evidence/{id}/verification` | B — ORG_ADMIN_REVIEWED |
| Automated governance closure | **System governance guards** | `sync_requirement_evidence_authority` + guards | A — SELF_CERTIFIED |
| Operational follow-up closure | **Landlord + guard resolution** | external_assessment / multi_evidence guards | C — PLATFORM_OVERSIGHT_OPTIONAL |
| Risk-triggered review | **Pleerity platform admin (escalation queue)** | manual_review_flag, mismatch, abuse | E — ESCALATION overlay |
| No review required | **N/A** | Record-on-file satisfies when guards pass | A subset (e.g. how_to_rent delivery) |

## Explicit non-decisions (current drift — to be fixed in implementation)

- CER `PENDING_REVIEW` MUST NOT imply platform admin review unless governance_family = D or E trigger active.
- Generic "Awaiting review" MUST NOT appear for families A, C default path, or B without org queue enrollment.

## Scalability

| Path | Scale implication |
|------|-------------------|
| Platform verified (D) | Bounded by certificate upload volume — existing ops model |
| Self-certified (A) | Scales horizontally — no human queue |
| Org reviewed (B) | Scales with customer orgs — platform not in path |
| Platform oversight optional (C) | Default no queue; sample/escalation only — avoids review overload |
| Escalation (E) | Small queue — high-signal only |

## Staffing

- **Platform ops:** Document verification (existing) + escalation queue (new, small).
- **No platform staffing** for default CER self-cert or org-review paths.
- **Org admins:** Optional verify for B-family; customer-managed.

## Trust implications

- Self-certified paths MUST disclose "not independent verification" (already in client_evidence_disclosure).
- Platform verified (D) remains highest trust tier for certificates.
- Org-reviewed (B) trust boundary is organisation, not Pleerity legal attestation.

## Abuse risks

- Self-certified without guards → score inflation. **Mitigation:** governance guards mandatory before VERIFIED_CURRENT.
- Fake org verify → **Mitigation:** audit trail on verify actor; escalation on contradiction.
- Supporting upload only → perceived completion. **Mitigation:** truth labels (Supporting evidence uploaded).

## Legal exposure

- UI must not imply Home Office / professional verification where product disclosure says otherwise (right_to_rent, legionella).
- "Platform verification pending" only for D-family and E-escalation.

## Families inventory

- **A (2 types):** how_to_rent, smoke_heat_alarms
- **B (8 types):** deposit_pi, landlord_registration, landlord_registration_ni, rent_smart_wales, right_to_rent, scotland_landlord_registration, tenancy_agreement, wales_occupation_contract
- **C (5 types):** fire_risk_assessment, hmo_fire_risk, hmo_fire_risk_evidence, lead_testing, legionella
- **D (15 types):** document-primary certificates (see cer_governance_matrix.json)
