import {
  authorityPermitsVerifiedPresentationLanguage,
  isRightToRentMixedEvidencePendingReview,
  resolveRightToRentMixedEvidenceCtaPresentation,
  shouldPreferGuidedEvidenceOverIntelView,
} from './rightToRentTrustPresentation';
import { applyLifecycleAwareCtaPresentation } from './requirementLifecyclePresentation';
import { requirementStatusSummaryForModal } from './requirementIntelligenceLabels';
import { executeRequirementPrimaryCta } from './requirementCtaParity';
import { isViewExistingSubmissionCta } from './complianceEvidenceSubmissionView';

function rtrRow(overrides = {}) {
  return {
    requirement_id: 'd72d87b0-3c65-461e-a35f-5bffed972e13',
    property_id: '3a69dcbd-74fd-4291-839b-3d52750598a1',
    requirement_code: 'right_to_rent',
    requirement_type: 'right_to_rent',
    workflow_class: 'GUIDED_DECLARATION',
    status: 'PENDING',
    evidence_doc_id: '3be27c21-1416-408d-b823-f895fa9fced7',
    client_lifecycle_state: 'VERIFIED',
    evidence_authority: {
      state: 'UPLOADED_UNCONFIRMED',
      primary_evidence_mode: 'DOCUMENT_UPLOAD',
    },
    ...overrides,
  };
}

describe('rightToRentTrustPresentation', () => {
  it('detects mixed evidence pending review with UPLOADED_UNCONFIRMED authority', () => {
    expect(isRightToRentMixedEvidencePendingReview(rtrRow())).toBe(true);
    expect(authorityPermitsVerifiedPresentationLanguage(rtrRow())).toBe(false);
  });

  it('detects mixed evidence when matrix row omits evidence_authority but links a document', () => {
    expect(
      isRightToRentMixedEvidencePendingReview(
        rtrRow({ evidence_authority: undefined, status: 'PENDING', client_lifecycle_state: null }),
      ),
    ).toBe(true);
  });

  it('does not apply when authority is VERIFIED_CURRENT', () => {
    expect(
      isRightToRentMixedEvidencePendingReview(
        rtrRow({ evidence_authority: { state: 'VERIFIED_CURRENT' } }),
      ),
    ).toBe(false);
  });

  it('overrides guided CTA to Record updated check with structured mode', () => {
    const out = resolveRightToRentMixedEvidenceCtaPresentation(rtrRow(), {
      primary_action_handler: 'guided_evidence',
      primary_action_label: 'Record Right to Rent check',
    });
    expect(out?.primary_action_label).toBe('Record updated check');
    expect(out?.guided_initial_evidence_mode).toBe('STRUCTURED_DECLARATION');
    expect(isViewExistingSubmissionCta(out)).toBe(false);
  });

  it('suppresses View verified evidence for VERIFIED lifecycle with unconfirmed authority', () => {
    const out = applyLifecycleAwareCtaPresentation(rtrRow({ client_lifecycle_state: 'VERIFIED' }), {
      primary_action_handler: 'guided_evidence',
      primary_action_label: 'Record Right to Rent check',
    });
    expect(out.primary_action_label).toBe('Record updated check');
  });

  it('replaces intel missing copy with awaiting-review lines', () => {
    const sum = requirementStatusSummaryForModal(
      rtrRow({ compliance_state: 'MISSING', evidence_state: 'MISSING' }),
    );
    expect(sum.compliance).toBe('Evidence submitted — awaiting review');
    expect(sum.evidenceLine).toBe('Check record on file — awaiting review');
  });

  it('routes view-style CTA to guided evidence for bounded RTR state', () => {
    const openGuidedEvidence = jest.fn();
    const openRequirementIntel = jest.fn();
    const row = rtrRow({
      take_action: {
        primary: {
          label: 'Record Right to Rent check',
          handler: 'guided_evidence',
          kind: 'guided_evidence_resolution',
          property_id: rtrRow().property_id,
          requirement_id: rtrRow().requirement_id,
        },
        contract: 'requirement_take_action_v1',
      },
    });
    const ta = {
      primary_action_handler: 'guided_evidence',
      primary_action_label: 'View submission',
    };
    expect(shouldPreferGuidedEvidenceOverIntelView(row, ta)).toBe(true);
    executeRequirementPrimaryCta({
      requirement: row,
      pagePropertyId: row.property_id,
      navigate: jest.fn(),
      openGuidedEvidence,
      openRequirementIntel,
    });
    expect(openGuidedEvidence).toHaveBeenCalled();
    expect(openRequirementIntel).not.toHaveBeenCalled();
  });
});
