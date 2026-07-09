import fs from 'fs';
import path from 'path';

const AUTHORITY_UTILS = [
  '../utils/capabilityRuntime.js',
  '../utils/sessionRuntimeSync.js',
  '../utils/communicationRuntime.js',
  '../contexts/LifecycleRuntimeContext.js',
  '../utils/CapabilityProtectedRoute.js',
];

describe('ILP-10 platform convergence', () => {
  it('App.js mounts LifecycleRuntimeContext not EntitlementsProvider', () => {
    const src = fs.readFileSync(path.join(__dirname, '../App.js'), 'utf8');
    expect(src).toMatch(/LifecycleRuntimeContext/);
    expect(src).not.toMatch(/EntitlementsProvider/);
  });

  it.each(AUTHORITY_UTILS)('%s exists for runtime consumption', (file) => {
    expect(fs.existsSync(path.join(__dirname, file))).toBe(true);
  });

  it('EntitlementsContext removed after platform hygiene cleanup', () => {
    expect(fs.existsSync(path.join(__dirname, '../contexts/EntitlementsContext.js'))).toBe(false);
    const app = fs.readFileSync(path.join(__dirname, '../App.js'), 'utf8');
    expect(app).not.toMatch(/EntitlementsContext/);
  });

  it('EntitlementProtectedRoute remains compatibility re-export only', () => {
    const src = fs.readFileSync(path.join(__dirname, '../utils/EntitlementProtectedRoute.js'), 'utf8');
    expect(src).toMatch(/@deprecated/);
    expect(src).toMatch(/AccountCapabilityProtectedRoute/);
  });
});
