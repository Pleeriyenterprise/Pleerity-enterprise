import React from 'react';
import { render, screen } from '@testing-library/react';
import {
  formatRiskSignalRegenOutcomeSummary,
  getRiskSignalRegenDisplayLastRun,
} from './riskSignalRegenWorkerAdminSummary';

/** Mirrors Automation Centre markup for risk_signal_regen_worker (job column). */
function RiskRegenAutomationCentreSummary({ lastRun }) {
  const bundle = formatRiskSignalRegenOutcomeSummary(lastRun);
  return (
    <div data-testid="risk-regen-outcome-summary">
      {bundle.headlineLines.map((t, i) => (
        <div key={i}>{t}</div>
      ))}
    </div>
  );
}

describe('getRiskSignalRegenDisplayLastRun', () => {
  it('merges inventory outcome_metrics when job-runs window lacks them', () => {
    const runInfo = { lastRun: { id: 'a', status: 'success', finished_at: 't', outcome_metrics: {} } };
    const invInfo = {
      last_run_id: 'a',
      last_status: 'success',
      last_finished_at: 't',
      last_outcome_status: 'conditional_no_output',
      last_outcome_metrics: { queue_empty: true, regenerated_count: 0 },
    };
    const lr = getRiskSignalRegenDisplayLastRun(runInfo, invInfo);
    expect(lr.outcome_metrics.queue_empty).toBe(true);
  });
});

describe('formatRiskSignalRegenOutcomeSummary', () => {
  it('shows no-work wording for empty queue', () => {
    const b = formatRiskSignalRegenOutcomeSummary({
      status: 'success',
      outcome_status: 'conditional_no_output',
      outcome_metrics: { queue_empty: true, attempted_count: 0, regenerated_count: 0 },
    });
    expect(b.headlineLines.join(' ')).toMatch(/no risk signal refresh work was waiting/i);
    expect(b.headlineLines.join(' ').toUpperCase()).not.toContain('NO_WORK_ELIGIBLE');
    expect(b.headlineLines.join(' ').toUpperCase()).not.toContain('BLOCKED');
  });

  it('shows skipped count and does not equate skips to refreshed properties', () => {
    const b = formatRiskSignalRegenOutcomeSummary({
      status: 'success',
      outcome_status: 'conditional_no_output',
      outcome_metrics: {
        queue_empty: false,
        attempted_count: 2,
        skipped_feature_flag_count: 2,
        regenerated_count: 0,
        failed_count: 0,
      },
    });
    const t = b.headlineLines.join('\n');
    expect(t).toMatch(/2.*skipped.*predictive maintenance/i);
    expect(t).toMatch(/no risk signals were refreshed/i);
    expect(t).not.toMatch(/refreshed for 2/i);
  });

  it('shows refreshed count on success', () => {
    const b = formatRiskSignalRegenOutcomeSummary({
      status: 'success',
      outcome_status: 'success',
      outcome_metrics: { regenerated_count: 4, skipped_feature_flag_count: 0, failed_count: 0 },
    });
    expect(b.headlineLines[0]).toMatch(/4.*propert/i);
    expect(b.headlineLines[0].toLowerCase()).toContain('refreshed');
  });

  it('shows failed and degraded metrics', () => {
    const failed = formatRiskSignalRegenOutcomeSummary({
      status: 'failed',
      outcome_status: 'failed',
      outcome_metrics: { failed_count: 2, regenerated_count: 0, skipped_feature_flag_count: 0 },
    });
    expect(failed.headlineLines.some((l) => /failed/i.test(l))).toBe(true);

    const deg = formatRiskSignalRegenOutcomeSummary({
      status: 'degraded',
      outcome_status: 'degraded',
      outcome_metrics: { failed_count: 1, regenerated_count: 2, skipped_feature_flag_count: 1 },
    });
    expect(deg.headlineLines.join('\n')).toMatch(/2.*propert/i);
    expect(deg.headlineLines.join('\n')).toMatch(/1.*refresh attempt/i);
    expect(deg.headlineLines.join('\n')).toMatch(/skipped/i);
  });

  it('renders Automation Centre–style summary for queue-empty run', () => {
    render(
      <RiskRegenAutomationCentreSummary
        lastRun={{
          status: 'success',
          outcome_status: 'conditional_no_output',
          outcome_metrics: { queue_empty: true, attempted_count: 0 },
        }}
      />,
    );
    expect(screen.getByTestId('risk-regen-outcome-summary')).toHaveTextContent(
      /no risk signal refresh work was waiting/i,
    );
  });

  it('does not use raw outcome_kind as primary label', () => {
    const b = formatRiskSignalRegenOutcomeSummary({
      status: 'success',
      outcome_status: 'conditional_no_output',
      outcome_metrics: {
        outcome_kind: 'BLOCKED',
        skipped_feature_flag_count: 1,
        regenerated_count: 0,
        failed_count: 0,
      },
    });
    const joined = b.headlineLines.join(' ');
    expect(joined.toUpperCase()).not.toContain('BLOCKED');
    expect(joined.toUpperCase()).not.toContain('OUTCOME_KIND');
    expect(JSON.stringify(b.technicalPayload)).toContain('BLOCKED');
  });
});
