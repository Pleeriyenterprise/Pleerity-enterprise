import fs from 'fs';
import path from 'path';

const ROOT = path.join(__dirname, '..');

describe('platform hygiene cleanup', () => {
  it('EntitlementsContext.js removed', () => {
    expect(fs.existsSync(path.join(ROOT, 'contexts/EntitlementsContext.js'))).toBe(false);
  });

  it('clientAPI has no getEntitlements wrapper', () => {
    const src = fs.readFileSync(path.join(ROOT, 'api/client.js'), 'utf8');
    expect(src).not.toMatch(/getEntitlements:\s*\(\)/);
    expect(src).toMatch(/getEntitlementsContext/);
  });

  it('retains intentional compatibility alias EntitlementProtectedRoute', () => {
    expect(fs.existsSync(path.join(ROOT, 'utils/EntitlementProtectedRoute.js'))).toBe(true);
  });
});
