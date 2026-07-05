import { useMemo } from 'react';
import { useLifecycleRuntime } from '../contexts/LifecycleRuntimeContext';
import { extractCapabilityDeniedFromError } from './capabilityRuntime';

/** Governed Runtime Contract capability ids for the Documents domain. */
export const DOC_CAPABILITY = {
  VIEW: 'CAP_DOC_VIEW',
  UPLOAD: 'CAP_DOC_UPLOAD',
  BULK_ZIP: 'CAP_DOC_BULK_ZIP',
  AI_EXTRACTION_ADVANCED: 'CAP_AI_EXTRACTION_ADVANCED',
};

/**
 * Runtime Contract capability consumption for Documents UI.
 */
export function useDocumentCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewDocuments: capabilityAllowed(DOC_CAPABILITY.VIEW, 'read'),
      canUploadDocuments: capabilityAllowed(DOC_CAPABILITY.UPLOAD, 'write'),
      canBulkZipUpload: capabilityAllowed(DOC_CAPABILITY.BULK_ZIP, 'write'),
      canUseAdvancedExtraction: capabilityAllowed(DOC_CAPABILITY.AI_EXTRACTION_ADVANCED, 'write'),
      getCapabilityGrant,
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

/**
 * @param {unknown} error
 * @param {string} fallback
 * @returns {string | null} message when capability_denied, else null
 */
export function getCapabilityDeniedMessage(error, fallback = 'Action not permitted') {
  const detail = extractCapabilityDeniedFromError(error);
  return detail?.message || null;
}

/**
 * @param {unknown} error
 * @param {string} fallback
 * @returns {boolean} true when a capability_denied toast message was present
 */
export function isCapabilityDeniedApiError(error) {
  return Boolean(extractCapabilityDeniedFromError(error));
}
