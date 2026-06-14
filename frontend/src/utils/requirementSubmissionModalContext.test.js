import {
  MODAL_CONTEXT,
  resolveModalFooterActions,
  resolveModalHeroPresentation,
  resolveRequirementSubmissionModalContext,
  shouldSuppressViewSubmissionLink,
} from './requirementSubmissionModalContext';

function row(state, overrides = {}) {
  return {
    requirement_id: 'req-x',
    property_id: 'prop-x',
    client_lifecycle_state: state,
    ...overrides,
  };
}

describe('requirementSubmissionModalContext', () => {
  describe('resolveRequirementSubmissionModalContext', () => {
    it('returns view_submission when opened with initialFocusSubmission and CER exists', () => {
      const merged = row('SATISFIED_UNVERIFIED', {
        primary_evidence_record_id: 'cer_1',
        truth_presentation_stage: 'declaration_recorded',
      });
      const out = resolveRequirementSubmissionModalContext({
        merged,
        hasSubmission: true,
        initialFocusSubmission: true,
        resolved: { primary_action_label: 'View submission', primary_action_handler: 'guided_evidence' },
      });
      expect(out.context).toBe(MODAL_CONTEXT.VIEW_SUBMISSION);
    });

    it('returns view_verified_evidence for VERIFIED lifecycle with focus', () => {
      const merged = row('VERIFIED', { evidence_doc_id: 'doc_1' });
      const out = resolveRequirementSubmissionModalContext({
        merged,
        hasSubmission: true,
        initialFocusSubmission: true,
        resolved: { primary_action_label: 'View evidence', primary_action_handler: 'navigate', primary_route: '/documents' },
      });
      expect(out.context).toBe(MODAL_CONTEXT.VIEW_VERIFIED_EVIDENCE);
    });

    it('returns view_verified_evidence when evidence authority is VERIFIED_CURRENT', () => {
      const merged = row('ACTION_REQUIRED', {
        evidence_authority: { state: 'VERIFIED_CURRENT' },
        truth_presentation_stage: 'verified',
        primary_evidence_record_id: 'cer_1',
      });
      const out = resolveRequirementSubmissionModalContext({
        merged,
        hasSubmission: true,
        initialFocusSubmission: true,
        resolved: { primary_action_label: 'Add compliance evidence' },
      });
      expect(out.context).toBe(MODAL_CONTEXT.VIEW_VERIFIED_EVIDENCE);
    });

    it('returns satisfy_requirement when no submission and action required', () => {
      const merged = row('ACTION_REQUIRED');
      const out = resolveRequirementSubmissionModalContext({
        merged,
        hasSubmission: false,
        initialFocusSubmission: false,
        resolved: { primary_action_label: 'Record Legionella risk assessment', primary_action_handler: 'guided_evidence' },
      });
      expect(out.context).toBe(MODAL_CONTEXT.SATISFY_REQUIREMENT);
    });

    it('converges stale record CTA to view_submission when submission exists', () => {
      const merged = row('SATISFIED_UNVERIFIED', { primary_evidence_record_id: 'cer_1' });
      const out = resolveRequirementSubmissionModalContext({
        merged,
        hasSubmission: true,
        initialFocusSubmission: false,
        resolved: {
          primary_action_label: 'Record Legionella risk assessment',
          primary_action_handler: 'guided_evidence',
        },
      });
      expect(out.context).toBe(MODAL_CONTEXT.VIEW_SUBMISSION);
    });
  });

  describe('resolveModalHeroPresentation', () => {
    it('shows submission recorded hero for view_submission', () => {
      const hero = resolveModalHeroPresentation({
        context: MODAL_CONTEXT.VIEW_SUBMISSION,
        lifecycle: { state: 'SATISFIED_UNVERIFIED' },
        merged: row('SATISFIED_UNVERIFIED'),
        statusEvidenceLine: 'Your assessment is on file.',
      });
      expect(hero.useServerHero).toBe(false);
      expect(hero.headline).toBe('Submission recorded');
      expect(hero.primaryLabel).toBe('Update submission');
      expect(hero.subline).toContain('on file');
    });

    it('shows awaiting review hero for pending review', () => {
      const hero = resolveModalHeroPresentation({
        context: MODAL_CONTEXT.VIEW_SUBMISSION,
        lifecycle: { state: 'PENDING_REVIEW' },
        merged: row('PENDING_REVIEW'),
      });
      expect(hero.headline).toBe('Awaiting platform review');
      expect(hero.primaryLabel).toBe('Update submission');
    });

    it('shows evidence verified hero for view_verified_evidence', () => {
      const hero = resolveModalHeroPresentation({
        context: MODAL_CONTEXT.VIEW_VERIFIED_EVIDENCE,
        lifecycle: { state: 'VERIFIED' },
        merged: row('VERIFIED'),
      });
      expect(hero.headline).toBe('Evidence verified');
      expect(hero.primaryLabel).toBe('View evidence');
    });

    it('defers to server hero for satisfy_requirement', () => {
      const hero = resolveModalHeroPresentation({
        context: MODAL_CONTEXT.SATISFY_REQUIREMENT,
        lifecycle: { state: 'ACTION_REQUIRED' },
        merged: row('ACTION_REQUIRED'),
      });
      expect(hero.useServerHero).toBe(true);
    });
  });

  describe('resolveModalFooterActions', () => {
    it('lists update and supporting evidence for view_submission without view submission', () => {
      const actions = resolveModalFooterActions({
        context: MODAL_CONTEXT.VIEW_SUBMISSION,
        showEditDatesAndApplicability: true,
      });
      const labels = actions.map((a) => a.label);
      expect(labels).toContain('Update submission');
      expect(labels).toContain('Add supporting evidence');
      expect(labels).not.toContain('View submission');
    });

    it('keeps satisfy primary for action required', () => {
      const actions = resolveModalFooterActions({
        context: MODAL_CONTEXT.SATISFY_REQUIREMENT,
        resolved: { primary_action_label: 'Record Legionella risk assessment' },
      });
      expect(actions[0].label).toBe('Record Legionella risk assessment');
    });
  });

  describe('shouldSuppressViewSubmissionLink', () => {
    it('suppresses when viewing submission context', () => {
      expect(shouldSuppressViewSubmissionLink(MODAL_CONTEXT.VIEW_SUBMISSION, false)).toBe(true);
      expect(shouldSuppressViewSubmissionLink(MODAL_CONTEXT.SATISFY_REQUIREMENT, true)).toBe(true);
      expect(shouldSuppressViewSubmissionLink(MODAL_CONTEXT.SATISFY_REQUIREMENT, false)).toBe(false);
    });
  });
});
