import fs from 'fs';
import path from 'path';

const MODAL = path.join(__dirname, 'ContractorNetworkLockedModal.jsx');

describe('ContractorNetworkLockedModal capability consumption', () => {
  it('uses presentation-only feature display without entitlements', () => {
    const src = fs.readFileSync(MODAL, 'utf8');
    expect(src).toMatch(/getFeatureDisplayInfo/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
  });
});
