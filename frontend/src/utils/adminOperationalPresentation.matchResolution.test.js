import {
  getEvidenceVerifyActionPresentation,
  getMatchResolutionActionPresentation,
  getMatchResolutionSuccessToast,
} from './adminOperationalPresentation';

describe('admin match vs verify presentation', () => {
  it('match approve override is distinct from verify', () => {
    const match = getMatchResolutionActionPresentation('approve_override');
    const verify = getEvidenceVerifyActionPresentation();
    expect(match.label).not.toBe(verify.label);
    expect(match.label).toContain('link');
    expect(verify.label).toContain('Verify');
    expect(getMatchResolutionSuccessToast('approve_override')).toMatch(/verification is still required/i);
  });

  it('reject toast does not imply verified', () => {
    expect(getMatchResolutionSuccessToast('reject_evidence')).toMatch(/rejected/i);
    expect(getMatchResolutionSuccessToast('reject_evidence')).not.toMatch(/verified/i);
  });
});
