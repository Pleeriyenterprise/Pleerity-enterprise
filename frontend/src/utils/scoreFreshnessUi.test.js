import {
  CALCULATING_SCORE_FALLBACK_MESSAGE,
  COMMAND_CENTER_COMPLIANCE_SNAPSHOT_UNAVAILABLE,
  COMPLIANCE_SCORE_DRIVERS_VS_HEADLINE_NOTE,
  PROPERTY_DETAIL_STORED_VS_PREVIEW_NOTE,
  formatScoreLastCalculatedForUi,
  isNonOkDashboardScoreStatus,
  pickScoreLastCalculatedIso,
  resolveDashboardFreshnessExplanation,
} from './scoreFreshnessUi';

describe('scoreFreshnessUi', () => {
  it('isNonOkDashboardScoreStatus is true for all required non-ok states', () => {
    expect(isNonOkDashboardScoreStatus('calculating')).toBe(true);
    expect(isNonOkDashboardScoreStatus('partial')).toBe(true);
    expect(isNonOkDashboardScoreStatus('stale')).toBe(true);
    expect(isNonOkDashboardScoreStatus('reconciliation_required')).toBe(true);
    expect(isNonOkDashboardScoreStatus('unavailable')).toBe(true);
    expect(isNonOkDashboardScoreStatus('unknown')).toBe(true);
    expect(isNonOkDashboardScoreStatus('ok')).toBe(false);
    expect(isNonOkDashboardScoreStatus('')).toBe(false);
  });

  it('resolveDashboardFreshnessExplanation prefers score_status_message when present', () => {
    expect(resolveDashboardFreshnessExplanation('calculating', '  Server message  ')).toBe('Server message');
  });

  it('resolveDashboardFreshnessExplanation uses calculating fallback when message absent', () => {
    expect(resolveDashboardFreshnessExplanation('calculating', null)).toBe(CALCULATING_SCORE_FALLBACK_MESSAGE);
    expect(resolveDashboardFreshnessExplanation('calculating', '')).toBe(CALCULATING_SCORE_FALLBACK_MESSAGE);
  });

  it('resolveDashboardFreshnessExplanation returns null for ok', () => {
    expect(resolveDashboardFreshnessExplanation('ok', 'ignored')).toBe(null);
  });

  it('resolveDashboardFreshnessExplanation provides defaults for stale/partial without message', () => {
    expect(resolveDashboardFreshnessExplanation('stale', null)).toBe(null);
    expect(resolveDashboardFreshnessExplanation('partial', null)).toBe(null);
  });

  it('resolveDashboardFreshnessExplanation covers reconciliation_required and unavailable without message', () => {
    const r = resolveDashboardFreshnessExplanation('reconciliation_required', null);
    expect(r).toContain('Persisted compliance scores');
    const u = resolveDashboardFreshnessExplanation('unavailable', null);
    expect(u).toContain('not available');
  });

  it('pickScoreLastCalculatedIso prefers portfolio_last_calculated_at', () => {
    expect(
      pickScoreLastCalculatedIso({
        last_calculated_at: '2026-01-02T00:00:00Z',
        portfolio_last_calculated_at: '2026-01-03T00:00:00Z',
      }),
    ).toBe('2026-01-03T00:00:00Z');
  });

  it('formatScoreLastCalculatedForUi returns a readable line', () => {
    const line = formatScoreLastCalculatedForUi('2026-04-15T12:00:00.000Z');
    expect(line).toContain('Portfolio scores last calculated');
    expect(line).toMatch(/2026/);
  });

  it('COMPLIANCE_SCORE_DRIVERS_VS_HEADLINE_NOTE documents drivers vs headline', () => {
    expect(COMPLIANCE_SCORE_DRIVERS_VS_HEADLINE_NOTE).toContain('Driver rows');
    expect(COMPLIANCE_SCORE_DRIVERS_VS_HEADLINE_NOTE).toContain('stored property scores');
  });

  it('COMMAND_CENTER_COMPLIANCE_SNAPSHOT_UNAVAILABLE is factual bundle-degraded copy', () => {
    expect(COMMAND_CENTER_COMPLIANCE_SNAPSHOT_UNAVAILABLE).toContain('could not be loaded in this bundle');
    expect(COMMAND_CENTER_COMPLIANCE_SNAPSHOT_UNAVAILABLE).toContain('Dashboard');
  });

  it('PROPERTY_DETAIL_STORED_VS_PREVIEW_NOTE describes stored headline vs live detail', () => {
    expect(PROPERTY_DETAIL_STORED_VS_PREVIEW_NOTE).toContain('latest stored property score');
    expect(PROPERTY_DETAIL_STORED_VS_PREVIEW_NOTE).toContain('recalculation is pending');
  });
});
