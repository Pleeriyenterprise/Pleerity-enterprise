import {
  CAPABILITY_DENIED_ERROR,
  GRANT_ALLOW,
  GRANT_DENY,
  GRANT_HIDDEN,
  GRANT_LIMITED,
  GRANT_PLAN_GATED,
  GRANT_READ,
  SEMANTIC_READ_ONLY,
  evaluateCapabilityGrant,
  extractCapabilityDeniedFromError,
  isCapabilityDeniedError,
  isGrantActionAllowed,
  normalizeGrantSemantic,
  normalizeCustomerExperience,
  parseCapabilityDeniedDetail,
} from './capabilityRuntime';

describe('capabilityRuntime primitives', () => {
  it('normalizes READ grant to READ_ONLY semantic', () => {
    expect(normalizeGrantSemantic(GRANT_READ)).toBe(SEMANTIC_READ_ONLY);
    expect(normalizeGrantSemantic(GRANT_ALLOW)).toBe(GRANT_ALLOW);
  });

  it('matches backend read/write grant rules', () => {
    expect(isGrantActionAllowed(GRANT_ALLOW, 'read')).toBe(true);
    expect(isGrantActionAllowed(GRANT_ALLOW, 'write')).toBe(true);
    expect(isGrantActionAllowed(GRANT_READ, 'read')).toBe(true);
    expect(isGrantActionAllowed(GRANT_READ, 'write')).toBe(false);
    expect(isGrantActionAllowed(GRANT_LIMITED, 'read')).toBe(true);
    expect(isGrantActionAllowed(GRANT_LIMITED, 'write')).toBe(true);
    expect(isGrantActionAllowed(GRANT_DENY, 'read')).toBe(false);
    expect(isGrantActionAllowed(GRANT_HIDDEN, 'write')).toBe(false);
    expect(isGrantActionAllowed(GRANT_PLAN_GATED, 'read')).toBe(false);
  });

  it('evaluates capability map entries', () => {
    const caps = { CAP_DOC_VIEW: GRANT_READ, CAP_DOC_UPLOAD: GRANT_ALLOW };
    expect(evaluateCapabilityGrant(caps, 'CAP_DOC_VIEW', 'read').allowed).toBe(true);
    expect(evaluateCapabilityGrant(caps, 'CAP_DOC_VIEW', 'write').allowed).toBe(false);
    expect(evaluateCapabilityGrant(caps, 'CAP_DOC_UPLOAD', 'write').allowed).toBe(true);
    expect(evaluateCapabilityGrant(caps, 'CAP_MISSING', 'read').allowed).toBe(false);
  });

  it('parses governed capability_denied payloads', () => {
    const detail = {
      error: CAPABILITY_DENIED_ERROR,
      message: 'Billing view is not permitted.',
      capability_id: 'CAP_BILLING_VIEW',
      action: 'read',
      grant: GRANT_DENY,
    };
    expect(parseCapabilityDeniedDetail(detail)?.capability_id).toBe('CAP_BILLING_VIEW');
    expect(isCapabilityDeniedError({ response: { data: { detail } } })).toBe(true);
    expect(extractCapabilityDeniedFromError({ response: { data: { detail: 'forbidden' } } })).toBeNull();
  });

  it('normalizes customer_experience object fields for React rendering', () => {
    const normalized = normalizeCustomerExperience({
      heading: 'Suspended',
      reason: { code: 'SUSPENDED' },
      explanation: 42,
      primary_cta: { label: { bad: true }, route: '/billing' },
      secondary_cta: { label: 'Help', route: '/help' },
    });
    expect(normalized.heading).toBe('Suspended');
    expect(normalized.reason).toBe('');
    expect(normalized.explanation).toBe('42');
    expect(normalized.primary_cta).toBeNull();
    expect(normalized.secondary_cta).toEqual({ label: 'Help', route: '/help' });
  });
});
