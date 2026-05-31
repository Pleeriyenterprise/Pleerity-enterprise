import {
  applyLifecycleAwareCtaPresentation,
  getLifecycleTierBadge,
  getRequirementLifecycleCardShellClass,
  getRequirementLifecycleIconTone,
  getRequirementLifecycleRowSurfaceClass,
  primaryLabelSuggestsInitialObligation,
} from './requirementLifecyclePresentation';

function rowWithLifecycle(state, overrides = {}) {
  return {
    requirement_id: 'req-x',
    property_id: 'prop-x',
    client_lifecycle_state: state,
    ...overrides,
  };
}

describe('requirementLifecyclePresentation', () => {
  describe('primaryLabelSuggestsInitialObligation', () => {
    it('detects record/upload/add-compliance openers', () => {
      expect(primaryLabelSuggestsInitialObligation('Record tenancy agreement')).toBe(true);
      expect(primaryLabelSuggestsInitialObligation('Upload valid EPC document')).toBe(true);
      expect(primaryLabelSuggestsInitialObligation('Add compliance evidence')).toBe(true);
      expect(primaryLabelSuggestsInitialObligation('View evidence')).toBe(false);
      expect(primaryLabelSuggestsInitialObligation('')).toBe(false);
    });
  });

  describe('applyLifecycleAwareCtaPresentation', () => {
    const baseCta = {
      primary_action_label: 'Record gas safety certificate',
      primary_route: '/properties/p1/documents?requirement_id=r1',
      primary_action_handler: 'navigate',
    };

    it('leaves CTA unchanged for ACTION_REQUIRED', () => {
      const row = rowWithLifecycle('ACTION_REQUIRED');
      const out = applyLifecycleAwareCtaPresentation(row, baseCta);
      expect(out.primary_action_label).toBe('Record gas safety certificate');
    });

    it('maps persisted declaration to View submission for guided_evidence', () => {
      const row = rowWithLifecycle('SATISFIED_UNVERIFIED', {
        truth_presentation_stage: 'declaration_recorded',
        truth_presentation_label: 'Declaration recorded',
        evidence_authority: { state: 'UPLOADED_UNCONFIRMED', primary_evidence_record_id: 'cer_1' },
      });
      const out = applyLifecycleAwareCtaPresentation(row, {
        ...baseCta,
        primary_action_handler: 'guided_evidence',
        primary_action_label: 'Record Wales occupation contract',
      });
      expect(out.primary_action_label).toBe('View submission');
    });

    it('maps PENDING_REVIEW + guided_evidence to View submission', () => {
      const row = rowWithLifecycle('PENDING_REVIEW');
      const out = applyLifecycleAwareCtaPresentation(row, {
        ...baseCta,
        primary_action_handler: 'guided_evidence',
        primary_action_label: 'Upload valid gas safety certificate',
      });
      expect(out.primary_action_label).toBe('View submission');
    });

    it('maps PENDING_REVIEW + documents route to View evidence', () => {
      const row = rowWithLifecycle('PENDING_REVIEW');
      const out = applyLifecycleAwareCtaPresentation(row, {
        ...baseCta,
        primary_route: '/properties/p1/documents',
        primary_action_label: 'Record deposit compliance',
      });
      expect(out.primary_action_label).toBe('View evidence');
    });

    it('maps PENDING_REVIEW otherwise to Review submission', () => {
      const row = rowWithLifecycle('PENDING_REVIEW');
      const out = applyLifecycleAwareCtaPresentation(row, {
        ...baseCta,
        primary_route: '/properties/p1?tab=compliance',
        primary_action_label: 'Record right to rent check',
      });
      expect(out.primary_action_label).toBe('Review submission');
    });

    it('renames upload secondary to additional evidence during review', () => {
      const row = rowWithLifecycle('PENDING_REVIEW');
      const out = applyLifecycleAwareCtaPresentation(row, {
        ...baseCta,
        primary_action_handler: 'guided_evidence',
        primary_action_label: 'Record X',
        secondary_action: { label: 'Upload supporting file', route: '/x' },
      });
      expect(out.secondary_action.label).toBe('Upload additional evidence');
    });

    it('maps SATISFIED_UNVERIFIED guided to View or update evidence', () => {
      const row = rowWithLifecycle('SATISFIED_UNVERIFIED');
      const out = applyLifecycleAwareCtaPresentation(row, {
        ...baseCta,
        primary_action_handler: 'guided_evidence',
        primary_action_label: 'Record tenancy agreement',
      });
      expect(out.primary_action_label).toBe('View or update evidence');
    });

    it('maps VERIFIED navigate to View evidence', () => {
      const row = rowWithLifecycle('VERIFIED');
      const out = applyLifecycleAwareCtaPresentation(row, {
        ...baseCta,
        primary_action_label: 'Upload valid EPC document',
      });
      expect(out.primary_action_label).toBe('View evidence');
    });

    it('does not override when primary copy is not initial-obligation wording', () => {
      const row = rowWithLifecycle('SATISFIED_UNVERIFIED');
      const out = applyLifecycleAwareCtaPresentation(row, {
        ...baseCta,
        primary_action_label: 'Open job',
      });
      expect(out.primary_action_label).toBe('Open job');
    });
  });

  describe('lifecycle chrome helpers', () => {
    it('row surface classes track lifecycle tier', () => {
      expect(getRequirementLifecycleRowSurfaceClass(rowWithLifecycle('ACTION_REQUIRED'))).toContain('border-l-red');
      expect(getRequirementLifecycleRowSurfaceClass(rowWithLifecycle('PENDING_REVIEW'))).toContain('amber');
      expect(getRequirementLifecycleRowSurfaceClass(rowWithLifecycle('SATISFIED_UNVERIFIED'))).toContain('emerald');
      expect(getRequirementLifecycleRowSurfaceClass(rowWithLifecycle('VERIFIED'))).toContain('green');
    });

    it('card shell and icon tone align with lifecycle', () => {
      expect(getRequirementLifecycleCardShellClass(rowWithLifecycle('PENDING_REVIEW'))).toContain('amber');
      expect(getRequirementLifecycleIconTone(rowWithLifecycle('VERIFIED'))).toBe('green');
    });

    it('tier badge supplements only when distinct from primary status', () => {
      expect(getLifecycleTierBadge(rowWithLifecycle('ACTION_REQUIRED'))).toBeNull();
      expect(getLifecycleTierBadge(rowWithLifecycle('PENDING_REVIEW'))).toBeNull();
      expect(getLifecycleTierBadge(rowWithLifecycle('SATISFIED_UNVERIFIED'))?.text).toBe('Evidence on file');
      expect(getLifecycleTierBadge(rowWithLifecycle('VERIFIED'))).toBeNull();
      expect(
        getLifecycleTierBadge(
          rowWithLifecycle('SATISFIED_UNVERIFIED', {
            truth_presentation_tier_supplement: 'Remediation or follow-up may remain open',
            truth_presentation_label: 'Follow-up evidence required',
          }),
        )?.text,
      ).toBe('Remediation or follow-up may remain open');
    });
  });
});
