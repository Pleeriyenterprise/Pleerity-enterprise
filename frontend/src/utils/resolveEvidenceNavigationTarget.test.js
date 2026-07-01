import {
  EVIDENCE_NAV_INTENT,
  inferEvidenceNavigationIntent,
  requirementNeedsLinkageReview,
  resolveEvidenceNavigationTarget,
} from './resolveEvidenceNavigationTarget';
import { executeRequirementPrimaryCta } from './requirementCtaParity';
import { resolveSettledEvidenceNavigationTarget } from './documentEvidenceAuthority';

const verifiedDocBase = {
  property_id: 'p1',
  requirement_id: 'r1',
  client_lifecycle_state: 'VERIFIED',
  status: 'COMPLIANT',
  compliance_requirement_class: 'DOCUMENT',
  is_tracked: true,
};

describe('resolveEvidenceNavigationTarget', () => {
  it('routes missing evidence to document operations upload', () => {
    const req = {
      ...verifiedDocBase,
      client_lifecycle_state: 'ACTION_REQUIRED',
      status: 'MISSING',
    };
    const ta = {
      primary_action_label: 'Upload document',
      primary_route: '/documents?property_id=p1&requirement_id=r1',
      primary_intent: EVIDENCE_NAV_INTENT.UPLOAD_EVIDENCE,
    };
    expect(resolveEvidenceNavigationTarget(req, { ta })).toBe(
      '/documents?property_id=p1&requirement_id=r1&focus=upload',
    );
  });

  it('routes needs linkage to document operations review queue', () => {
    const req = {
      ...verifiedDocBase,
      client_lifecycle_state: 'PENDING_REVIEW',
      document_linkage_state: 'RECONCILIATION_REQUIRED',
    };
    expect(resolveEvidenceNavigationTarget(req, { ta: { primary_route: '/documents?property_id=p1' } })).toBe(
      '/documents?property_id=p1&requirement_id=r1',
    );
    expect(requirementNeedsLinkageReview(req)).toBe(true);
  });

  it('routes pending review document to document operations queue', () => {
    const req = {
      ...verifiedDocBase,
      client_lifecycle_state: 'PENDING_REVIEW',
      document_id: 'doc_pending',
      evidence_authority: { effective_verified_document_id: 'doc_pending' },
    };
    const ta = {
      primary_action_label: 'Review uploaded document',
      primary_route: '/documents?property_id=p1&requirement_id=r1',
    };
    expect(resolveEvidenceNavigationTarget(req, { ta })).toBe(
      '/documents?property_id=p1&requirement_id=r1',
    );
  });

  it('routes verified linked document to property evidence registry', () => {
    const req = {
      ...verifiedDocBase,
      document_id: 'doc_1',
      document_client_visibility_state: 'ACTIVE_EVIDENCE',
      evidence_authority: { effective_verified_document_id: 'doc_1' },
    };
    const ta = {
      primary_action_label: 'View evidence',
      primary_route: '/documents?property_id=p1&requirement_id=r1',
    };
    expect(resolveEvidenceNavigationTarget(req, { ta })).toBe(
      '/properties/p1?tab=evidence&requirement_id=r1',
    );
  });

  it('routes verified multiple documents to requirement-scoped registry', () => {
    const req = {
      ...verifiedDocBase,
      document_id: 'doc_a',
      evidence_authority: { effective_verified_document_id: 'doc_a' },
      linked_document_count: 2,
    };
    expect(
      resolveEvidenceNavigationTarget(req, {
        ta: { primary_action_label: 'View evidence', primary_route: '/documents?property_id=p1&requirement_id=r1' },
      }),
    ).toBe('/properties/p1?tab=evidence&requirement_id=r1');
  });

  it('routes verified structured declaration to submission inspect', () => {
    const req = {
      ...verifiedDocBase,
      evidence_authority: {
        state: 'VERIFIED_CURRENT',
        state_reason: 'verified_non_document_evidence',
        primary_evidence_record_id: 'cer_1',
      },
    };
    expect(
      resolveEvidenceNavigationTarget(req, {
        ta: { primary_action_label: 'View evidence' },
        intent: EVIDENCE_NAV_INTENT.VIEW_SUBMISSION,
      }),
    ).toBe('/properties/p1?tab=evidence&requirement_id=r1&open=intel&focus=submission');
  });

  it('routes verified self-certified record to submission inspect', () => {
    const req = {
      ...verifiedDocBase,
      evidence_authority: {
        state: 'VERIFIED_CURRENT',
        state_reason: 'assessment_recorded',
        primary_evidence_record_id: 'cer_self',
      },
      assurance_tier: 'SELF_RECORDED',
    };
    expect(
      resolveEvidenceNavigationTarget(req, {
        ta: { primary_action_label: 'View evidence' },
      }),
    ).toBe('/properties/p1?tab=evidence&requirement_id=r1&open=intel&focus=submission');
  });

  it('routes archived evidence to historical registry view', () => {
    const req = {
      ...verifiedDocBase,
      document_client_visibility_state: 'HISTORICAL_OR_SUPERSEDED',
      document_id: 'doc_old',
      evidence_authority: { effective_verified_document_id: 'doc_old' },
    };
    expect(
      resolveEvidenceNavigationTarget(req, {
        ta: { primary_action_label: 'View evidence' },
      }),
    ).toBe('/properties/p1?tab=evidence&requirement_id=r1');
  });

  it('supports property-scoped requirement rows', () => {
    const req = { requirement_id: 'r9', client_lifecycle_state: 'VERIFIED', status: 'COMPLIANT' };
    expect(
      resolveEvidenceNavigationTarget(req, {
        pagePropertyId: 'p9',
        ta: { primary_action_label: 'View evidence', primary_route: '/documents?property_id=p9&requirement_id=r9' },
      }),
    ).toBe('/properties/p9?tab=evidence&requirement_id=r9');
  });

  it('returns null for portfolio-wide requirement without property context', () => {
    const req = { requirement_id: 'r-port', client_lifecycle_state: 'VERIFIED', status: 'COMPLIANT' };
    expect(
      resolveEvidenceNavigationTarget(req, {
        ta: { primary_action_label: 'View evidence', primary_route: '/documents?requirement_id=r-port' },
      }),
    ).toBeNull();
  });

  it('preserves non-evidence operational routes', () => {
    const req = { ...verifiedDocBase, workflow_family: 'CONDITION_STANDARD_ACTIVE_STANDARD' };
    const ta = {
      primary_action_label: 'Manage related issues',
      primary_route: '/operations/issues?property_id=p1',
      primary_intent: 'view_guidance',
    };
    expect(resolveEvidenceNavigationTarget(req, { ta })).toBe('/operations/issues?property_id=p1');
  });
});

describe('inferEvidenceNavigationIntent', () => {
  it('rewrites upload_evidence intent when lifecycle is verified and label is view evidence', () => {
    const req = { ...verifiedDocBase, document_id: 'd1' };
    const ta = { primary_intent: 'upload_evidence', primary_action_label: 'View evidence' };
    expect(inferEvidenceNavigationIntent(req, ta)).toBe(EVIDENCE_NAV_INTENT.VIEW_SETTLED_EVIDENCE);
  });
});

describe('surface parity via executeRequirementPrimaryCta', () => {
  it('Requirements page CTA: verified linked document opens registry', () => {
    const navigate = jest.fn();
    const requirement = {
      ...verifiedDocBase,
      document_id: 'doc_req',
      evidence_authority: { effective_verified_document_id: 'doc_req' },
      take_action: {
        primary: {
          label: 'View evidence',
          route: '/documents?property_id=p1&requirement_id=r1',
          handler: 'navigate',
        },
      },
    };
    executeRequirementPrimaryCta({ requirement, navigate });
    expect(navigate).toHaveBeenCalledWith('/properties/p1?tab=evidence&requirement_id=r1');
  });

  it('Property Detail CTA: verified linked document opens registry', () => {
    const navigate = jest.fn();
    const requirement = {
      ...verifiedDocBase,
      document_id: 'doc_prop',
      evidence_authority: { effective_verified_document_id: 'doc_prop' },
      take_action: {
        primary: {
          label: 'View evidence',
          route: '/documents?property_id=p1&requirement_id=r1',
          handler: 'navigate',
        },
      },
    };
    executeRequirementPrimaryCta({ requirement, pagePropertyId: 'p1', navigate });
    expect(navigate).toHaveBeenCalledWith('/properties/p1?tab=evidence&requirement_id=r1');
  });
});

describe('resolveSettledEvidenceNavigationTarget parity', () => {
  it('delegates to canonical resolver for view evidence CTAs', () => {
    const req = { ...verifiedDocBase };
    const ta = {
      primary_action_label: 'View evidence',
      primary_route: '/documents?property_id=p1&requirement_id=r1',
      primary_action_handler: 'navigate',
    };
    expect(resolveSettledEvidenceNavigationTarget(req, ta)).toBe(
      '/properties/p1?tab=evidence&requirement_id=r1',
    );
  });
});
