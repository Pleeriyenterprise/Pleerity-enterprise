import {
  buildPropertyComplianceResolveQueryLink,
  executeRequirementPrimaryCta,
  resolveRequirementActionWithRowContext,
} from './requirementCtaParity';
import { resolveRequirementAction } from './requirementTakeActionResolver';

describe('resolveRequirementActionWithRowContext', () => {
  it('injects page property_id when the row omits it so guided primary is not marked incomplete', () => {
    const requirement = {
      requirement_id: 'r1',
      take_action: {
        primary: {
          label: 'Record',
          kind: 'guided_evidence_resolution',
          handler: 'guided_evidence',
          route: '',
        },
      },
    };
    const withoutCtx = resolveRequirementAction(requirement, {});
    expect(withoutCtx.primary_action_handler).toBe('guided_evidence_error');

    const withCtx = resolveRequirementActionWithRowContext(requirement, 'p99');
    expect(withCtx.primary_action_handler).toBe('guided_evidence');
  });
});

describe('executeRequirementPrimaryCta', () => {
  it('opens modal on-property when guided and pagePropertyId matches row', () => {
    const openGuidedEvidence = jest.fn();
    const navigate = jest.fn();
    const requirement = {
      property_id: 'p1',
      requirement_id: 'r1',
      take_action: {
        primary: {
          label: 'Resolve',
          kind: 'guided_evidence_resolution',
          handler: 'guided_evidence',
          route: '',
        },
      },
    };
    const { handled } = executeRequirementPrimaryCta({
      requirement,
      pagePropertyId: 'p1',
      navigate,
      openGuidedEvidence,
    });
    expect(handled).toBe(true);
    expect(openGuidedEvidence).toHaveBeenCalledWith(
      expect.objectContaining({ propertyId: 'p1', requirement }),
    );
    expect(navigate).not.toHaveBeenCalled();
  });

  it('opens guided modal for registration resolve deeplink when primary is View submission', () => {
    const openGuidedEvidence = jest.fn();
    const openRequirementIntel = jest.fn();
    const requirement = {
      property_id: 'p1',
      requirement_id: 'r1',
      workflow_class: 'REGISTRATION_TRACKING',
      client_lifecycle_state: 'PENDING_REVIEW',
      evidence_authority: { primary_evidence_record_id: 'cer-1' },
      take_action: {
        primary: {
          label: 'Record registration details',
          kind: 'guided_evidence_resolution',
          handler: 'guided_evidence',
          route: '',
        },
      },
    };
    const { handled, ta } = executeRequirementPrimaryCta({
      requirement,
      pagePropertyId: 'p1',
      navigate: jest.fn(),
      openGuidedEvidence,
      openRequirementIntel,
      guidedInitialOverride: 'STRUCTURED_DECLARATION',
    });
    expect(handled).toBe(true);
    expect(ta.primary_action_label).toBe('View submission');
    expect(openGuidedEvidence).toHaveBeenCalled();
    expect(openRequirementIntel).not.toHaveBeenCalled();
  });

  it('opens requirement intel when primary is View submission', () => {
    const openRequirementIntel = jest.fn();
    const requirement = {
      property_id: 'p1',
      requirement_id: 'r1',
      client_lifecycle_state: 'PENDING_REVIEW',
      take_action: {
        primary: {
          label: 'Record declaration',
          kind: 'guided_evidence_resolution',
          handler: 'guided_evidence',
          route: '',
        },
      },
    };
    const { handled, ta } = executeRequirementPrimaryCta({
      requirement,
      pagePropertyId: null,
      navigate: jest.fn(),
      openGuidedEvidence: jest.fn(),
      openRequirementIntel,
    });
    expect(handled).toBe(true);
    expect(ta.primary_action_label).toBe('View submission');
    expect(openRequirementIntel).toHaveBeenCalledWith(requirement, { scrollToSubmission: true });
  });

  it('navigates resolve deep-link when guided but not on property page', () => {
    const navigate = jest.fn();
    const requirement = {
      property_id: 'p1',
      requirement_id: 'r1',
      take_action: {
        primary: {
          label: 'Resolve',
          kind: 'guided_evidence_resolution',
          handler: 'guided_evidence',
          route: '',
        },
      },
    };
    const { handled } = executeRequirementPrimaryCta({
      requirement,
      pagePropertyId: null,
      navigate,
    });
    expect(handled).toBe(true);
    expect(navigate).toHaveBeenCalledWith(
      buildPropertyComplianceResolveQueryLink('p1', 'r1', {}),
    );
  });
});

describe('buildPropertyComplianceResolveQueryLink', () => {
  it('includes open=resolve, requirement_id, and optional evidence_mode', () => {
    const link = buildPropertyComplianceResolveQueryLink('p9', 'r2', { initialEvidenceMode: 'LEGIONELLA' });
    expect(link).toContain('/properties/p9?');
    expect(link).toContain('open=resolve');
    expect(link).toContain('requirement_id=r2');
    expect(link).toContain('evidence_mode=LEGIONELLA');
  });
});
