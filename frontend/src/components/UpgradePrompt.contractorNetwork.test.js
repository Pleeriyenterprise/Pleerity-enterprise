import { getFeatureDisplayInfo } from './UpgradePrompt';

describe('UpgradePrompt contractor_network', () => {
  it('maps contractor_network to Professional plan', () => {
    const info = getFeatureDisplayInfo('contractor_network', null);
    expect(info.requiredPlan).toBe('PLAN_3_PRO');
    expect(info.requiredPlanName).toMatch(/Professional/i);
  });
});
