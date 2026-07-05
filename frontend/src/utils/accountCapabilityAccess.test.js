import {
  ACCOUNT_LIFECYCLE_GRANT_FIXTURES,
  evaluateNavFeatureAllowedFromMap,
  evaluateProfileCapabilitiesFromMap,
  evaluateSupportCapabilitiesFromMap,
  getCapabilityDeniedMessage,
  isCapabilityDeniedApiError,
  NAV_FEATURE_CAPABILITY,
} from './accountCapabilityAccess';
import { GRANT_ALLOW } from './capabilityRuntime';
import { OPS_CAPABILITY } from './operationalCapabilityAccess';

describe('accountCapabilityAccess', () => {
  it('maps nav legacy features to runtime contract capabilities', () => {
    expect(NAV_FEATURE_CAPABILITY.maintenance_workflows.capabilityId).toBe(OPS_CAPABILITY.OPS_MAINTENANCE);
    expect(NAV_FEATURE_CAPABILITY.tenant_portal.capabilityId).toBe('CAP_TENANT_PORTAL');
  });

  it('parses capability_denied payloads', () => {
    const error = {
      response: {
        data: {
          detail: {
            error: 'capability_denied',
            message: 'Profile editing is not available.',
            capability_id: 'CAP_PROFILE_EDIT',
          },
        },
      },
    };
    expect(isCapabilityDeniedApiError(error)).toBe(true);
    expect(getCapabilityDeniedMessage(error)).toBe('Profile editing is not available.');
  });

  describe('lifecycle profile grants', () => {
    it('ACTIVE permits profile view and edit', () => {
      const profile = evaluateProfileCapabilitiesFromMap(ACCOUNT_LIFECYCLE_GRANT_FIXTURES.ACTIVE);
      expect(profile.canViewProfile).toBe(true);
      expect(profile.canEditProfile).toBe(true);
      expect(profile.canEditJurisdiction).toBe(true);
    });

    it('READ_ONLY permits view but denies mutations', () => {
      const profile = evaluateProfileCapabilitiesFromMap(ACCOUNT_LIFECYCLE_GRANT_FIXTURES.READ_ONLY);
      expect(profile.canViewProfile).toBe(true);
      expect(profile.canEditProfile).toBe(false);
      expect(profile.canUseSmsNotifications).toBe(false);
    });

    it('SUSPENDED denies profile access', () => {
      const profile = evaluateProfileCapabilitiesFromMap(ACCOUNT_LIFECYCLE_GRANT_FIXTURES.SUSPENDED);
      expect(profile.canViewProfile).toBe(false);
      expect(profile.canEditProfile).toBe(false);
    });
  });

  describe('lifecycle support grants', () => {
    it('ACTIVE permits support access and requests', () => {
      const support = evaluateSupportCapabilitiesFromMap(ACCOUNT_LIFECYCLE_GRANT_FIXTURES.ACTIVE);
      expect(support.canAccessSupport).toBe(true);
      expect(support.canRequestSupport).toBe(true);
      expect(support.canViewKnowledgeCentre).toBe(true);
    });

    it('READ_ONLY permits knowledge centre read only', () => {
      const support = evaluateSupportCapabilitiesFromMap(ACCOUNT_LIFECYCLE_GRANT_FIXTURES.READ_ONLY);
      expect(support.canViewKnowledgeCentre).toBe(true);
      expect(support.canRequestSupport).toBe(false);
    });
  });

  it('evaluates nav feature gates from capability map', () => {
    const activeWithOps = {
      ...ACCOUNT_LIFECYCLE_GRANT_FIXTURES.ACTIVE,
      CAP_OPS_CONTRACTORS: GRANT_ALLOW,
      CAP_OPS_MAINTENANCE: GRANT_ALLOW,
    };
    expect(evaluateNavFeatureAllowedFromMap(activeWithOps, 'contractor_network')).toBe(true);
    expect(evaluateNavFeatureAllowedFromMap(ACCOUNT_LIFECYCLE_GRANT_FIXTURES.SUSPENDED, 'maintenance_workflows')).toBe(false);
  });
});
