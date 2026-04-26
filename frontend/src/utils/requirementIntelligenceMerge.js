/**
 * Merge list/matrix seed row with GET /requirements/{id} payload so published registry fields
 * from the client list are not dropped while workflow response wins on canonical keys.
 * @param {Record<string, unknown>|null|undefined} seed
 * @param {Record<string, unknown>|null|undefined} apiRow
 * @returns {Record<string, unknown>|null}
 */
export function mergeRequirementIntelPayload(seed, apiRow) {
  if (!apiRow || typeof apiRow !== 'object') {
    return seed && typeof seed === 'object' ? { ...seed } : null;
  }
  const s = seed && typeof seed === 'object' ? seed : {};
  const a = apiRow;
  const regS = s.registry_metadata && typeof s.registry_metadata === 'object' ? s.registry_metadata : {};
  const regA = a.registry_metadata && typeof a.registry_metadata === 'object' ? a.registry_metadata : {};
  const mergedReg =
    Object.keys(regS).length > 0 || Object.keys(regA).length > 0 ? { ...regS, ...regA } : a.registry_metadata;
  return {
    ...s,
    ...a,
    ...(mergedReg && typeof mergedReg === 'object' ? { registry_metadata: mergedReg } : {}),
  };
}

export { pickWhyItMattersForDisplay, pickCanonicalWhyItMattersShort } from './requirementCanonicalNarrative';
