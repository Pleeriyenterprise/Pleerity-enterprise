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

  it('navigates resolve deep-link when guided but not on property page', () => {
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
      pagePropertyId: null,
      navigate,
      openGuidedEvidence,
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
