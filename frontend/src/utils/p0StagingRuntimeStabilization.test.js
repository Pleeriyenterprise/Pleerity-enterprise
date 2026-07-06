import { formatApiErrorDetail } from './capabilityRuntime';
import { isApiCircuitOpen, recordApiCircuitFailure, resetAllApiCircuits } from './apiRequestCircuit';

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
});

describe('apiRequestCircuit', () => {
  beforeEach(() => {
    resetAllApiCircuits();
  });

  it('opens circuit after repeated 403 failures', () => {
    const path = 'client/portal-context';
    expect(isApiCircuitOpen(path)).toBe(false);
    for (let i = 0; i < 4; i += 1) {
      recordApiCircuitFailure(path, 403);
    }
    expect(isApiCircuitOpen(path)).toBe(true);
  });
});
