import { renderHook } from '@testing-library/react';
import {
  REQUIREMENT_CAPABILITY,
  useRequirementCapabilities,
  evaluateRequirementCapabilitiesFromMap,
  REQUIREMENT_LIFECYCLE_GRANT_FIXTURES,
} from './requirementCapabilityAccess';

jest.mock('../contexts/LifecycleRuntimeContext', () => ({
  useLifecycleRuntime: jest.fn(),
}));

const { useLifecycleRuntime } = require('../contexts/LifecycleRuntimeContext');

describe('requirementCapabilityAccess', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('maps runtime grants to requirement capability flags', () => {
    useLifecycleRuntime.mockReturnValue({
      capabilityAllowed: (capabilityId, action) => {
        if (capabilityId === REQUIREMENT_CAPABILITY.VIEW && action === 'read') return true;
        if (capabilityId === REQUIREMENT_CAPABILITY.RESOLVE && action === 'write') return true;
        if (capabilityId === REQUIREMENT_CAPABILITY.MARK_N_A && action === 'write') return false;
        return false;
      },
      getCapabilityGrant: jest.fn(),
    });

    const { result } = renderHook(() => useRequirementCapabilities());

    expect(result.current.canViewRequirements).toBe(true);
    expect(result.current.canResolveRequirements).toBe(true);
    expect(result.current.canMarkRequirementNotApplicable).toBe(false);
  });

  it('evaluates CANCELLED_IMMEDIATE as read-only requirements', () => {
    const flags = evaluateRequirementCapabilitiesFromMap(REQUIREMENT_LIFECYCLE_GRANT_FIXTURES.CANCELLED_IMMEDIATE);
    expect(flags.canViewRequirements).toBe(true);
    expect(flags.canResolveRequirements).toBe(false);
    expect(flags.canMarkRequirementNotApplicable).toBe(false);
  });
});
