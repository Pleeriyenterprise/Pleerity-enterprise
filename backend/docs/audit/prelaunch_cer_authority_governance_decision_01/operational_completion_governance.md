# Operational completion governance

**Programme:** PRELAUNCH-CER-AUTHORITY-GOVERNANCE-DECISION-01

## Completion states (authoritative)

| State | Definition | Score typical | Legal completeness |
|-------|------------|---------------|-------------------|
| **Missing** | No authoritative submission | MISSING (0) | Not met |
| **Evidence-submitted-only** | CER or doc exists but guards incomplete | NEEDS_REVIEW (0.5) | Not met |
| **Partially complete** | Multi-component / follow-up open | NEEDS_REVIEW (0.5) | Not met |
| **Awaiting follow-up** | Assessment remediation unresolved | NEEDS_REVIEW (0.5) | Not met |
| **Operationally complete** | All governance guards pass; may be unverified | NEEDS_REVIEW or VALID per family | May be met for self-cert |
| **Formally verified** | VERIFIED_CURRENT or platform doc verified | VALID (1.0) | Met per product scope |

## Distinctions (mandatory)

1. **Evidence presence** — `primary_evidence_record_id` or document on file. Necessary not sufficient.
2. **Operational completion** — governance guards satisfied (`evidence_completeness.is_complete`, follow-up resolved).
3. **Verification completion** — human or platform verify action OR auto-close policy for self-cert family.
4. **Score contribution** — `map_authority_to_scoring_status` only.
5. **Legal completeness** — landlord statutory duty; product tracks evidence not legal advice.

## Closure modes by family

- **A:** `governance_guard_auto_close` — no human verify default.
- **B:** `registration_tracking_record_guard` / declaration recorded; org verify optional.
- **C:** `external_assessment_followup_guard` — follow-up must resolve.
- **D:** `admin_document_verify_plus_authority_sync`.
- **E:** Escalation queue resolution overlay.

## Forbidden conflation

- MUST NOT treat CER submit as operational complete when components incomplete.
- MUST NOT treat supporting vault upload as submission.
- MUST NOT show "verified" language when authority is UPLOADED_UNCONFIRMED unless label says "Evidence recorded".
