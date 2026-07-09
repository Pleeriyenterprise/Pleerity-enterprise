import fs from 'fs';
import path from 'path';

const SHELL = path.join(__dirname, 'LifecycleShell.jsx');
const RUNTIME = path.join(__dirname, '..', '..', 'utils', 'capabilityRuntime.js');

describe('LifecycleShell keep subscription wiring', () => {
  it('uses resume action instead of passive billing link for primary CTA', () => {
    const src = fs.readFileSync(SHELL, 'utf8');
    expect(src).toMatch(/useResumeSubscription/);
    expect(src).toMatch(/resume_subscription/);
    expect(src).toMatch(/lifecycle-keep-subscription/);
    expect(src).toMatch(/refreshSession\('subscription_resumed'\)/);
  });

  it('allows action-based customer experience CTAs', () => {
    const src = fs.readFileSync(RUNTIME, 'utf8');
    expect(src).toMatch(/cta\.action/);
  });
});
