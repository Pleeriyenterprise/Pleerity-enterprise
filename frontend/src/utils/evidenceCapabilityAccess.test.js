import { renderHook } from '@testing-library/react';
import {
  EVIDENCE_CAPABILITY,
  useEvidenceCapabilities,
  evaluateEvidenceCapabilitiesFromMap,
  EVIDENCE_LIFECYCLE_GRANT_FIXTURES,
} from './evidenceCapabilityAccess';

jest.mock('../contexts/LifecycleRuntimeContext', () => ({
  useLifecycleRuntime: jest.fn(),
}));

const { useLifecycleRuntime } = require('../contexts/LifecycleRuntimeContext');

describe('evidenceCapabilityAccess', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('maps runtime grants to evidence capability flags', () => {
    useLifecycleRuntime.mockReturnValue({
      capabilityAllowed: (capabilityId, action) => {
        if (capabilityId === EVIDENCE_CAPABILITY.VIEW && action === 'read') return true;
        if (capabilityId === EVIDENCE_CAPABILITY.DOWNLOAD && action === 'read') return false;
        return false;
      },
      getCapabilityGrant: jest.fn(),
    });

    const { result } = renderHook(() => useEvidenceCapabilities());

    expect(result.current.canViewEvidence).toBe(true);
    expect(result.current.canDownloadEvidence).toBe(false);
  });

  it('evaluates SUSPENDED as deny evidence', () => {
    const flags = evaluateEvidenceCapabilitiesFromMap(EVIDENCE_LIFECYCLE_GRANT_FIXTURES.SUSPENDED);
    expect(flags.canViewEvidence).toBe(false);
    expect(flags.canDownloadEvidence).toBe(false);
  });
});
