import {
  buildCommandCenterVerdict,
  hasCommandCenterContinuationDebt,
  isCommandCenterAllClearEmpty,
  isCommandCenterPressureDegraded,
} from './clientCommandCenter';

describe('command center false-calm hardening', () => {
  const calmInputs = {
    urgentCount: 0,
    predictiveEnabled: false,
    riskCount: 0,
    activeJobsLength: 0,
    summary: { color: 'green', requirements_overdue: 0 },
    propertiesAtRisk: 0,
  };

  it('blocks all-clear when pressure_degraded is true', () => {
    expect(
      isCommandCenterAllClearEmpty({
        ...calmInputs,
        pressureDegraded: true,
      }),
    ).toBe(false);
  });

  it('blocks all-clear when continuation debt exists', () => {
    expect(
      isCommandCenterAllClearEmpty({
        ...calmInputs,
        continuationDebt: true,
      }),
    ).toBe(false);
  });

  it('blocks all-clear when operational debt count is positive', () => {
    expect(
      isCommandCenterAllClearEmpty({
        ...calmInputs,
        operationalDebtCount: 2,
      }),
    ).toBe(false);
  });

  it('allows all-clear only when fully calm and not degraded', () => {
    expect(isCommandCenterAllClearEmpty(calmInputs)).toBe(true);
  });

  it('detects pressure degraded from bundle fields', () => {
    expect(isCommandCenterPressureDegraded({ pressure_degraded: true })).toBe(true);
    expect(isCommandCenterPressureDegraded({ pressure_status: 'degraded' })).toBe(true);
    expect(isCommandCenterPressureDegraded({ pressure_status: 'ok' })).toBe(false);
  });

  it('detects continuation debt from tasks_digest_summary', () => {
    expect(hasCommandCenterContinuationDebt({ tasks_digest_summary: { urgent_continuation: 1 } })).toBe(true);
    expect(hasCommandCenterContinuationDebt({ tasks_digest_summary: { urgent_continuation: 0 } })).toBe(false);
  });

  it('verdict avoids calm tone when pressure is degraded', () => {
    const v = buildCommandCenterVerdict({
      urgentCount: 0,
      riskCount: 0,
      predictiveEnabled: false,
      summary: { color: 'green' },
      propertiesAtRisk: 0,
      breachedJobCount: 0,
      blockedJobCount: 0,
      awaitingProofCount: 0,
      pressureDegraded: true,
      pressureMessage: 'Metrics refreshing.',
    });
    expect(v.tone).not.toBe('calm');
    expect(v.line).toContain('refreshing');
  });
});
