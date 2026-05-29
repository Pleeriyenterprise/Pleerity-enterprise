import {
  composeRequirementStatusBadgeVisibility,
  filterUploadEligibleRequirementsForProperty,
  isRequirementEligibleForDocumentUpload,
  isViewSettledEvidenceCta,
  resolvePropertyEvidenceRegistryPath,
  resolveSettledEvidenceNavigationTarget,
} from './documentEvidenceAuthority';

describe('documentEvidenceAuthority', () => {
  const baseReq = {
    requirement_id: 'r1',
    property_id: 'p1',
    compliance_requirement_class: 'DOCUMENT',
    applicability: 'REQUIRED',
    status: 'COMPLIANT',
    client_lifecycle_state: 'VERIFIED',
    is_tracked: true,
  };

  it('includes action-required requirements for upload dropdown', () => {
    const req = { ...baseReq, status: 'MISSING', client_lifecycle_state: 'ACTION_REQUIRED' };
    expect(isRequirementEligibleForDocumentUpload(req)).toBe(true);
    expect(filterUploadEligibleRequirementsForProperty('p1', [req])).toHaveLength(1);
  });

  it('excludes verified current requirements unless expiring', () => {
    expect(isRequirementEligibleForDocumentUpload(baseReq)).toBe(false);
    expect(
      isRequirementEligibleForDocumentUpload({ ...baseReq, status: 'EXPIRING_SOON' }),
    ).toBe(true);
  });

  it('routes view evidence away from documents queue', () => {
    const req = { ...baseReq };
    const ta = {
      primary_action_label: 'View evidence',
      primary_route: '/documents?property_id=p1&requirement_id=r1',
      primary_action_handler: 'navigate',
    };
    expect(isViewSettledEvidenceCta(req, ta)).toBe(true);
    expect(resolveSettledEvidenceNavigationTarget(req, ta)).toBe(
      '/properties/p1?tab=evidence&requirement_id=r1',
    );
  });

  it('does not rewrite upload_evidence routes for action required', () => {
    const req = {
      ...baseReq,
      status: 'MISSING',
      client_lifecycle_state: 'ACTION_REQUIRED',
    };
    const ta = {
      primary_action_label: 'Upload document',
      primary_route: '/documents?property_id=p1&requirement_id=r1',
      primary_action_handler: 'navigate',
      primary_intent: 'upload_evidence',
    };
    expect(resolveSettledEvidenceNavigationTarget(req, ta)).toBeNull();
  });

  it('deduplicates verified badges', () => {
    const vis = composeRequirementStatusBadgeVisibility(
      baseReq,
      { text: 'Verified' },
      { text: 'Verified' },
      'Verified',
    );
    expect(vis.showTier).toBe(false);
    expect(vis.showEvidence).toBe(false);
  });

  it('builds property evidence registry path', () => {
    expect(resolvePropertyEvidenceRegistryPath('p9', 'r9')).toBe(
      '/properties/p9?tab=evidence&requirement_id=r9',
    );
  });
});
