import { renderHook } from '@testing-library/react';
import {
  DOC_CAPABILITY,
  getCapabilityDeniedMessage,
  isCapabilityDeniedApiError,
  useDocumentCapabilities,
} from './documentCapabilityAccess';

jest.mock('../contexts/LifecycleRuntimeContext', () => ({
  useLifecycleRuntime: jest.fn(),
}));

const { useLifecycleRuntime } = require('../contexts/LifecycleRuntimeContext');

describe('documentCapabilityAccess', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('maps runtime grants to document capability flags', () => {
    useLifecycleRuntime.mockReturnValue({
      capabilityAllowed: (capabilityId, action) => {
        if (capabilityId === DOC_CAPABILITY.VIEW && action === 'read') return true;
        if (capabilityId === DOC_CAPABILITY.UPLOAD && action === 'write') return true;
        if (capabilityId === DOC_CAPABILITY.BULK_ZIP && action === 'write') return false;
        if (capabilityId === DOC_CAPABILITY.AI_EXTRACTION_ADVANCED && action === 'write') return true;
        return false;
      },
      getCapabilityGrant: jest.fn(),
    });

    const { result } = renderHook(() => useDocumentCapabilities());

    expect(result.current.canViewDocuments).toBe(true);
    expect(result.current.canUploadDocuments).toBe(true);
    expect(result.current.canBulkZipUpload).toBe(false);
    expect(result.current.canUseAdvancedExtraction).toBe(true);
  });

  it('parses capability_denied API payloads', () => {
    const error = {
      response: {
        data: {
          detail: {
            error: 'capability_denied',
            message: 'Document upload is not available in this account state.',
            capability_id: DOC_CAPABILITY.UPLOAD,
          },
        },
      },
    };
    expect(isCapabilityDeniedApiError(error)).toBe(true);
    expect(getCapabilityDeniedMessage(error)).toBe(
      'Document upload is not available in this account state.',
    );
  });
});
