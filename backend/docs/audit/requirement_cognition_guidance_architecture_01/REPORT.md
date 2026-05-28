# REQUIREMENT-COGNITION-GUIDANCE-ARCHITECTURE-01

Generated: 2026-05-28T22:28:51.284558+00:00

## Classification

**OPERATIONALLY_GUIDED**

Push audit artifacts: **True**

## Summary

Requirement/evidence flows now expose server-authoritative `requirement_guidance_v1` on enriched requirements and the evidence-resolution API. The guided evidence modal elevates a single recommended path via `NextActionHero`, progression steps, collapsed secondary methods, and explicit uploaded≠submitted semantics.

## Blockers

- none

## Samples audited

12 requirements probed on staging.

## Remediation roadmap (if not OPERATIONALLY_GUIDED)

1. Deploy backend + frontend containing `requirement_guidance_v1` and modal guidance panel.
2. Re-run this harness after Render/Vercel deploy completes.
3. Resolve any cross-surface contradictions in `contradiction_matrix`.
4. Confirm browser proof: hero, progression, primary-tier evidence mode in modal screenshot.
