import {
  SCORE_WIDGET_LABEL_OBLIGATIONS,
  SCORE_WIDGET_LABEL_RENEWAL,
  SCORE_WIDGET_LABEL_VALID,
  SCORE_WIDGET_TOOLTIP_OBLIGATIONS,
  SCORE_WIDGET_TOOLTIP_RENEWAL,
  SCORE_WIDGET_TOOLTIP_VALID,
  countRegistryTrackedRequirements,
  formatNextRenewalDisplay,
  isAssuranceQuickAction,
  pickNearestRenewalFromRequirements,
  resolveQuickActionDisplayText,
  resolveScoreWidgetRenewalDisplay,
} from './dashboardScoreWidgetLabels';

describe('dashboardScoreWidgetLabels', () => {
  it('exports converged labels not legacy Requirements', () => {
    expect(SCORE_WIDGET_LABEL_OBLIGATIONS).toBe('Score-tracked obligations');
    expect(SCORE_WIDGET_LABEL_VALID).toBe('Valid for scoring');
    expect(SCORE_WIDGET_LABEL_RENEWAL).toBe('Next renewal');
    expect(SCORE_WIDGET_LABEL_OBLIGATIONS).not.toMatch(/^Requirements$/);
  });

  it('exports tooltip copy for score projection', () => {
    expect(SCORE_WIDGET_TOOLTIP_OBLIGATIONS).toMatch(/grouping similar rules/i);
    expect(SCORE_WIDGET_TOOLTIP_VALID).toMatch(/score model/i);
    expect(SCORE_WIDGET_TOOLTIP_RENEWAL).toMatch(/Estimated dates/i);
  });

  it('formatNextRenewalDisplay caps far-future dates', () => {
    expect(formatNextRenewalDisplay(1709, { isEstimated: true }).headline).toBe('1+ year estimated');
    expect(formatNextRenewalDisplay(400, { isEstimated: false }).headline).toBe('1+ year');
    expect(formatNextRenewalDisplay(30).headline).toBe('30');
    expect(formatNextRenewalDisplay(null).headline).toBe('No upcoming renewal');
  });

  it('resolveScoreWidgetRenewalDisplay uses api days with estimated flag from requirements', () => {
    const future = new Date();
    future.setUTCDate(future.getUTCDate() + 2000);
    const reqs = [
      {
        requirement_id: 'r1',
        status: 'COMPLIANT',
        due_date: future.toISOString(),
        date_source: 'SYSTEM_ESTIMATED',
      },
    ];
    const out = resolveScoreWidgetRenewalDisplay(1709, reqs);
    expect(out.headline).toBe('1+ year estimated');
    expect(out.detail).toMatch(/1709 days/);
  });

  it('countRegistryTrackedRequirements counts attention-view rows only', () => {
    const n = countRegistryTrackedRequirements([
      { applicability: 'REQUIRED', status: 'COMPLIANT', compliance_requirement_class: 'DOCUMENT' },
      { applicability: 'NOT_REQUIRED', status: 'NOT_REQUIRED' },
      { compliance_requirement_class: 'OBLIGATION', status: 'COMPLIANT' },
    ]);
    expect(n).toBe(1);
  });

  it('resolveQuickActionDisplayText replaces upload-and-verify for assurance rows', () => {
    const req = { client_lifecycle_state: 'PENDING_REVIEW', display_label: 'Smoke alarms' };
    expect(isAssuranceQuickAction('Upload and verify evidence for X', req)).toBe(true);
    expect(resolveQuickActionDisplayText('Upload and verify evidence for X', req, 'Smoke alarms')).toMatch(
      /Review assurance status/i,
    );
    expect(resolveQuickActionDisplayText('Upload and verify evidence for X', req, 'Smoke alarms')).not.toMatch(
      /Upload and verify/i,
    );
  });

  it('pickNearestRenewalFromRequirements ignores overdue rows', () => {
    const past = new Date();
    past.setUTCDate(past.getUTCDate() - 10);
    const future = new Date();
    future.setUTCDate(future.getUTCDate() + 5);
    const picked = pickNearestRenewalFromRequirements([
      { status: 'OVERDUE', due_date: past.toISOString() },
      { status: 'COMPLIANT', due_date: future.toISOString() },
    ]);
    expect(picked.daysUntil).toBeGreaterThanOrEqual(4);
    expect(picked.daysUntil).toBeLessThanOrEqual(6);
  });
});
