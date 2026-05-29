import {
  resolveCanonicalPrimaryAction,
  hasServerOperationalAuthority,
  isDegradedOperationalEntity,
} from './operationalAuthorityContract';

describe('operationalAuthorityContract', () => {
  it('prefers operational_cognition primary_action', () => {
    const entity = {
      operational_cognition: {
        primary_action: { key: 'upload', label: 'Upload evidence', url: '/documents' },
      },
      take_action: { primary: { label: 'Wrong' } },
      business_actions: [{ label: 'Also wrong', primary: true }],
    };
    const r = resolveCanonicalPrimaryAction(entity);
    expect(r.authority_source).toBe('operational_cognition');
    expect(r.label).toBe('Upload evidence');
  });

  it('uses operational_continuation before take_action', () => {
    const entity = {
      operational_continuation: {
        has_active_lineage: true,
        continuation_cta: { label: 'Continue job', key: 'view_workflow', url: '/operations/jobs/x' },
      },
      take_action: { primary: { label: 'Create job' } },
    };
    const r = resolveCanonicalPrimaryAction(entity);
    expect(r.authority_source).toBe('operational_continuation');
    expect(r.continuation).toBe(true);
  });

  it('falls back to business_actions without inventing labels', () => {
    const entity = {
      business_actions: [{ label: 'Record payment', primary: true, intent: 'record_rent_payment' }],
    };
    const r = resolveCanonicalPrimaryAction(entity);
    expect(r.authority_source).toBe('business_actions');
    expect(r.label).toBe('Record payment');
  });

  it('returns null when no server authority present', () => {
    expect(resolveCanonicalPrimaryAction({})).toBeNull();
    expect(hasServerOperationalAuthority({})).toBe(false);
  });

  it('detects degraded operational entity', () => {
    expect(
      isDegradedOperationalEntity({
        operational_cognition: { degraded_state: { active: true, reason: 'pressure_fallback' } },
      }),
    ).toBe(true);
  });
});
