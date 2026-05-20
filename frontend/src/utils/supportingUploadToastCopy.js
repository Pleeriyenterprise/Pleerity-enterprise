import { requirementHasPersistedClientSubmission } from './clientPersistedSubmissionPresentation';

/**
 * @param {Record<string, unknown>|null|undefined} requirement
 * @param {number} uploadedCount
 */
export function supportingUploadSuccessToast(requirement, uploadedCount) {
  const n = uploadedCount > 0 ? uploadedCount : 1;
  const files = n === 1 ? 'Supporting document' : 'Supporting documents';
  if (requirementHasPersistedClientSubmission(requirement)) {
    return `${files} added to your existing submission. This does not replace your authoritative record — complete the declaration below and press Submit evidence when ready.`;
  }
  return `${files} uploaded. Complete the structured form below and press Submit evidence to record this requirement.`;
}
