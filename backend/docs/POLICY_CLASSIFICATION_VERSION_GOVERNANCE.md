# Policy Classification Version Governance

## Scope

This governs policy-backed portfolio risk classification predicates and reason-code enums.

## Frozen Contract

- `policy_classification_version` is a frozen contract once rollout cohorts are active.
- Canonical reason codes are enums and must not become freeform strings.
- Severity-only critical breach inference is forbidden.

## Change Control (after rollout starts)

Any predicate/classification mapping change requires all of:

1. Version bump (e.g. `v1` -> `v2`)
2. Migration note (field/backfill implications and compatibility)
3. Rollout review approval
4. Rollback review approval

## Runtime Safety

- Portfolio override consumers must remain backward compatible with existing score contract fields.
- During rollout phases, policy-vs-legacy divergence diagnostics must be measurable.
