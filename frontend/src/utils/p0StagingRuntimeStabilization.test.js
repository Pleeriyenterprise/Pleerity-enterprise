import {
  DATABASE_CAPACITY_USER_MESSAGE,
  formatApiErrorDetail,
  formatApiErrorMessage,
  isDatabaseCapacityError,
} from './capabilityRuntime';
import {
  isApiCircuitOpen,
  isGlobalApiPaused,
  recordApiCircuitFailure,
  CIRCUIT_STEP_UP_CHALLENGE_FINGERPRINT,
  resetAllApiCircuits,
} from './apiRequestCircuit';

describe('formatApiErrorDetail', () => {
  it('returns string detail as-is', () => {
    expect(formatApiErrorDetail('Network error', 'fallback')).toBe('Network error');
  });

  it('extracts message from lifecycle denial object (React #31 fix)', () => {
    const detail = {
      error: 'billing_recovery',
      message: 'Your subscription needs attention before you can continue.',
      lifecycle_state: 'CANCELLED_IMMEDIATE',
      portal_mode: 'BILLING_RECOVERY',
    };
    expect(formatApiErrorDetail(detail, 'fallback')).toBe(
      'Your subscription needs attention before you can continue.',
    );
  });

  it('falls back for empty detail', () => {
    expect(formatApiErrorDetail(null, 'fallback')).toBe('fallback');
  });

  it('maps DATABASE_CAPACITY_EXCEEDED to capacity user message', () => {
    expect(
      formatApiErrorDetail({ code: 'DATABASE_CAPACITY_EXCEEDED', detail: 'raw' }, 'fallback'),
    ).toBe(DATABASE_CAPACITY_USER_MESSAGE);
    expect(
      formatApiErrorMessage({
        response: { status: 503, data: { code: 'DATABASE_CAPACITY_EXCEEDED', detail: 'x' } },
      }),
    ).toBe(DATABASE_CAPACITY_USER_MESSAGE);
    expect(
      isDatabaseCapacityError({
        response: { status: 503, data: { code: 'DATABASE_CAPACITY_EXCEEDED' } },
      }),
    ).toBe(true);
  });
});

describe('apiRequestCircuit', () => {
  beforeEach(() => {
    resetAllApiCircuits();
  });

  it('opens circuit after repeated 403 failures', () => {
    const path = 'client/portal-context';
    expect(isApiCircuitOpen(path)).toBe(false);
    for (let i = 0; i < 2; i += 1) {
      recordApiCircuitFailure(path, 403);
    }
    expect(isApiCircuitOpen(path)).toBe(true);
  });

  it('pauses all portal reads after any 429', () => {
    expect(isGlobalApiPaused()).toBe(false);
    recordApiCircuitFailure('client/dashboard', 429);
    expect(isGlobalApiPaused()).toBe(true);
    expect(isApiCircuitOpen('client/requirements')).toBe(true);
  });

  it('pauses longer after security IP block 429', () => {
    resetAllApiCircuits();
    recordApiCircuitFailure('client/requirements', 429, 'Request blocked due to suspicious activity.');
    expect(isGlobalApiPaused()).toBe(true);
  });

  it('does not count STEP_UP_REQUIRED as a circuit failure', () => {
    const path = 'admin/clients/x/commercial-entitlement/execute';
    expect(CIRCUIT_STEP_UP_CHALLENGE_FINGERPRINT).toBe('cc-step-up-circuit-fix-04');
    recordApiCircuitFailure(path, 403, 'Confirm your password to continue.', 'STEP_UP_REQUIRED');
    recordApiCircuitFailure(path, 403, 'Confirm your password to continue.', 'STEP_UP_REQUIRED');
    expect(isApiCircuitOpen(path)).toBe(false);
    expect(isGlobalApiPaused()).toBe(false);
  });

  it('allows immediate retry after cancelled STEP_UP_REQUIRED (circuit stays closed)', () => {
    const path = 'admin/clients/x/commercial-entitlement/execute';
    recordApiCircuitFailure(path, 403, 'Confirm your password.', 'STEP_UP_REQUIRED');
    // operator cancels; submits again — another expected challenge
    recordApiCircuitFailure(path, 403, 'Confirm your password.', 'STEP_UP_REQUIRED');
    expect(isApiCircuitOpen(path)).toBe(false);
  });

  it('still opens circuit on genuine authorization 403s', () => {
    const path = 'admin/clients/x/commercial-entitlement/execute';
    recordApiCircuitFailure(path, 403, 'Forbidden');
    recordApiCircuitFailure(path, 403, 'Forbidden');
    expect(isApiCircuitOpen(path)).toBe(true);
  });
});
