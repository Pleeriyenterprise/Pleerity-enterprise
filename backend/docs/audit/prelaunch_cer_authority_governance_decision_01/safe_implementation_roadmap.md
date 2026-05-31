# Safe implementation roadmap (proposal — NOT approved)

**Programme:** PRELAUNCH-CER-AUTHORITY-GOVERNANCE-DECISION-01

## Sequence (mandatory order)

1. **Frontend label convergence** — truth_surface_language_matrix; remove FRONTEND_SUBMISSION_ON_FILE override; dedupe badges.
2. **Governance family metadata** — expose governance_family on enriched requirement payloads (read-only field).
3. **Stale / cognition alignment** — _stale_review_active owner-aware; rename workflow stages.
4. **Admin queue extension** — escalation queue + optional org queue UX; NOT blanket CER pending-verification.
5. **CER authority convergence** — map PENDING_REVIEW to correct authority state per family; no orphan states.
6. **Lifecycle migration** — backfill semantic_state labels; optional data migration for misclassified rows.
7. **Score truth convergence** — verify Today/CC use map_authority_to_scoring_status exclusively.

## Migrations required

- Presentation layer only: phase 1 (no DB).
- Optional: re-sync requirements with governance_family-aware authority promotion.
- Cognition copy: server-side guidance_v1 template updates.

## Unsafe shortcuts (forbidden)

- Auto-verify all CER on submit.
- Add CER to document pending-verification without family filter.
- New review_state collection parallel to evidence_authority.
- Disable governance guards to reduce "stuck" rows.

## Backwards compatibility

- Landlords may see label changes — intentional trust repair.
- Admin ops gain escalation queue — no removal of document queue.
- API verify endpoint unchanged; queue UX added.

## Trust risks if sequence violated

- Implementing admin queue before label fix → ops review items that should self-close.
- Authority migration before family metadata → wrong queue routing.
