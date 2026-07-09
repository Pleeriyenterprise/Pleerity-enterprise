import fs from 'fs';
import path from 'path';

const ROUTE = path.join(__dirname, 'CapabilityProtectedRoute.js');

describe('CapabilityProtectedRoute', () => {
  it('consumes LifecycleRuntimeContext capabilityAllowed', () => {
    const src = fs.readFileSync(ROUTE, 'utf8');
    expect(src).toMatch(/useLifecycleRuntime/);
    expect(src).toMatch(/capabilityAllowed/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
  });

  it('maps operational feature keys to runtime capabilities', () => {
    const src = fs.readFileSync(ROUTE, 'utf8');
    expect(src).toMatch(/OPERATIONAL_ROUTE_CAPABILITY/);
    expect(src).toMatch(/OperationalCapabilityProtectedRoute/);
  });
});
