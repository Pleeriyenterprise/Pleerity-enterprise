import { renderHook } from '@testing-library/react';
import {
  PROPERTY_CAPABILITY,
  SCORE_CAPABILITY,
  usePropertyCapabilities,
  evaluatePropertyCapabilitiesFromMap,
  PROPERTY_LIFECYCLE_GRANT_FIXTURES,
} from './propertyCapabilityAccess';
import { evaluateCapabilityGrant } from './capabilityRuntime';

jest.mock('../contexts/LifecycleRuntimeContext', () => ({
  useLifecycleRuntime: jest.fn(),
}));

const { useLifecycleRuntime } = require('../contexts/LifecycleRuntimeContext');

describe('propertyCapabilityAccess', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('maps runtime grants to property capability flags', () => {
    useLifecycleRuntime.mockReturnValue({
      capabilityAllowed: (capabilityId, action) => {
        if (capabilityId === PROPERTY_CAPABILITY.VIEW && action === 'read') return true;
        if (capabilityId === PROPERTY_CAPABILITY.CREATE && action === 'write') return true;
        if (capabilityId === PROPERTY_CAPABILITY.EDIT && action === 'write') return false;
        if (capabilityId === SCORE_CAPABILITY.EXPLAIN && action === 'read') return true;
        if (capabilityId === SCORE_CAPABILITY.TREND && action === 'read') return false;
        return false;
      },
      getCapabilityGrant: jest.fn(),
    });

    const { result } = renderHook(() => usePropertyCapabilities());

    expect(result.current.canViewProperties).toBe(true);
    expect(result.current.canCreateProperty).toBe(true);
    expect(result.current.canEditProperty).toBe(false);
    expect(result.current.canViewScoreExplain).toBe(true);
    expect(result.current.canViewScoreTrend).toBe(false);
  });

  it('evaluates lifecycle fixtures for READ_ONLY property mutations', () => {
    const caps = PROPERTY_LIFECYCLE_GRANT_FIXTURES.READ_ONLY;
    const flags = evaluatePropertyCapabilitiesFromMap(caps);
    expect(flags.canViewProperties).toBe(true);
    expect(flags.canCreateProperty).toBe(false);
    expect(flags.canEditProperty).toBe(false);
    expect(evaluateCapabilityGrant(caps, SCORE_CAPABILITY.EXPLAIN, 'read').allowed).toBe(true);
  });
});
