import {
  resolveScoreDriverActionPresentation,
  SCORE_DRIVER_ACTION_LABELS,
} from './ComplianceScorePage.scoreDriverActions';
import { validateCustomerCopy } from '../utils/trustLanguageGovernance';

describe('resolveScoreDriverActionPresentation', () => {
  const driverBase = {
    property_id: 'p1',
    requirement_id: 'r1',
    status: 'MISSING_EVIDENCE',
  };

  it('returns tier A when canonical take_action primary exists', () => {
    const requirements = [
      {
        requirement_id: 'r1',
        property_id: 'p1',
        compliance_requirement_class: 'DOCUMENT',
        status: 'MISSING',
        take_action: {
          primary: { label: 'Upload', route: '/documents?property_id=p1', handler: 'navigate' },
        },
      },
    ];
    const out = resolveScoreDriverActionPresentation(driverBase, requirements);
    expect(out.tier).toBe('A');
    expect(out.sem?.server_take_action_primary).toBe(true);
  });

  it('returns tier B open requirement when no canonical primary but ids present', () => {
    const requirements = [
      {
        requirement_id: 'r1',
        property_id: 'p1',
        compliance_requirement_class: 'DOCUMENT',
        status: 'MISSING',
      },
    ];
    const out = resolveScoreDriverActionPresentation(driverBase, requirements);
    expect(out.tier).toBe('B');
    expect(out.navigation?.label).toBe(SCORE_DRIVER_ACTION_LABELS.openRequirement);
    expect(out.navigation?.route).toContain('/properties/');
    expect(out.navigation?.route).toContain('requirement_id=r1');
  });

  it('returns tier B review property when only property id is known', () => {
    const out = resolveScoreDriverActionPresentation(
      { property_id: 'p1', status: 'MISSING_EVIDENCE' },
      [],
    );
    expect(out.tier).toBe('B');
    expect(out.navigation?.label).toBe(SCORE_DRIVER_ACTION_LABELS.reviewProperty);
  });

  it('returns tier C when no safe navigation target exists', () => {
    const out = resolveScoreDriverActionPresentation({ status: 'MISSING_EVIDENCE' }, []);
    expect(out.tier).toBe('C');
  });

  it('score driver action labels pass trust-language governance', () => {
    for (const label of Object.values(SCORE_DRIVER_ACTION_LABELS)) {
      expect(validateCustomerCopy(label)).toHaveLength(0);
    }
    expect(validateCustomerCopy('No server-confirmed remediation step is available on this summary.')).not.toHaveLength(0);
  });
});
