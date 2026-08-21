import React from 'react';
import { render, screen } from '@testing-library/react';
import {
  formatComplianceRecalcWorkerOutcomeSummary,
  getComplianceRecalcWorkerDisplayLastRun,
} from './complianceRecalcWorkerAdminSummary';

function RecalcAutomationCentreSummary({ lastRun }) {
  const bundle = formatComplianceRecalcWorkerOutcomeSummary(lastRun);
  return (
    <div data-testid="compliance-recalc-worker-outcome-summary">
      {bundle.headlineLines.map((t, i) => (
        <div key={i}>{t}</div>
      ))}
    </div>
  );
}

describe('getComplianceRecalcWorkerDisplayLastRun', () => {
  it('merges inventory outcome_metrics when job-runs window lacks them', () => {
    const runInfo = { lastRun: { id: 'a', status: 'success', finished_at: 't', outcome_metrics: {} } };
    const invInfo = {
      last_run_id: 'a',
      last_status: 'success',
      last_finished_at: 't',
      last_outcome_status: 'conditional_no_output',
      last_outcome_metrics: { queue_empty: true, attempted_count: 0, success_count: 0 },
    };
    const lr = getComplianceRecalcWorkerDisplayLastRun(runInfo, invInfo);
    expect(lr.outcome_metrics.queue_empty).toBe(true);
  });
});

describe('formatComplianceRecalcWorkerOutcomeSummary', () => {
  it('shows empty-queue wording', () => {
    const b = formatComplianceRecalcWorkerOutcomeSummary({
      status: 'success',
      outcome_status: 'conditional_no_output',
      outcome_metrics: {
        queue_empty: true,
        attempted_count: 0,
        success_count: 0,
        queue_items_seen_batch: 0,
        outcome_kind: 'NO_WORK_ELIGIBLE',
      },
    });
    expect(b.headlineLines[0]).toMatch(/no compliance recalculation work was waiting/i);
    expect(b.headlineLines.join(' ').toUpperCase()).not.toContain('NO_WORK_ELIGIBLE');
    expect(JSON.stringify(b.technicalPayload)).toContain('NO_WORK_ELIGIBLE');
  });

  it('shows contention-only wording without raw outcome_kind in headlines', () => {
    const b = formatComplianceRecalcWorkerOutcomeSummary({
      status: 'success',
      outcome_status: 'success',
      outcome_metrics: {
        queue_empty: false,
        attempted_count: 5,
        queue_items_seen_batch: 5,
        queue_items_claim_skipped: 5,
        queue_items_processed: 0,
        queue_items_failed: 0,
        queue_items_dead: 0,
        success_count: 0,
        failed_count: 0,
        outcome_kind: 'CONTENTION_ONLY',
      },
    });
    const joined = b.headlineLines.join(' ');
    expect(joined).toMatch(/another worker already claimed/i);
    expect(joined).toMatch(/no recalculation work was completed/i);
    expect(joined.toUpperCase()).not.toContain('CONTENTION_ONLY');
    expect(JSON.stringify(b.technicalPayload)).toContain('CONTENTION_ONLY');
  });

  it('shows lifecycle-suppressed wording, not contention', () => {
    const b = formatComplianceRecalcWorkerOutcomeSummary({
      status: 'success',
      outcome_status: 'success',
      outcome_metrics: {
        queue_empty: false,
        attempted_count: 3,
        queue_items_seen_batch: 3,
        queue_items_claim_skipped: 0,
        queue_items_lifecycle_skipped: 2,
        queue_items_lifecycle_paused: 1,
        queue_items_processed: 0,
        queue_items_failed: 0,
        queue_items_dead: 0,
        success_count: 0,
        failed_count: 0,
        outcome_kind: 'LIFECYCLE_SUPPRESSED',
      },
    });
    const joined = b.headlineLines.join(' ');
    expect(joined).toMatch(/account lifecycle does not permit/i);
    expect(joined).toMatch(/not claim contention/i);
    expect(joined).not.toMatch(/another worker already claimed/i);
    expect(joined.toUpperCase()).not.toContain('LIFECYCLE_SUPPRESSED');
    expect(JSON.stringify(b.technicalPayload)).toContain('LIFECYCLE_SUPPRESSED');
  });

  it('shows successful work', () => {
    const b = formatComplianceRecalcWorkerOutcomeSummary({
      status: 'success',
      outcome_status: 'success',
      outcome_metrics: {
        queue_items_seen_batch: 12,
        queue_items_claim_skipped: 0,
        queue_items_processed: 12,
        queue_items_failed: 0,
        queue_items_dead: 0,
        attempted_count: 12,
        success_count: 12,
        failed_count: 0,
        queue_empty: false,
        outcome_kind: 'WORK_PERFORMED',
      },
    });
    expect(b.headlineLines[0]).toMatch(/12 queued compliance recalculation/i);
    expect(b.headlineLines[0]).toMatch(/completed/i);
    expect(b.headlineLines.join(' ').toUpperCase()).not.toContain('WORK_PERFORMED');
  });

  it('shows degraded retry and dead lines', () => {
    const b = formatComplianceRecalcWorkerOutcomeSummary({
      status: 'degraded',
      outcome_status: 'degraded',
      outcome_metrics: {
        queue_items_processed: 8,
        queue_items_failed: 2,
        queue_items_dead: 1,
        success_count: 8,
        failed_count: 3,
        outcome_kind: 'DEGRADED',
      },
    });
    const t = b.headlineLines.join('\n');
    expect(t).toMatch(/8 queued compliance recalculation/i);
    expect(t).toMatch(/2 queue item.*failed and will retry/i);
    expect(t).toMatch(/1 recalculation item.*terminal failure/i);
    expect(t.toUpperCase()).not.toContain('DEGRADED');
  });

  it('shows failed run with dead and retry', () => {
    const b = formatComplianceRecalcWorkerOutcomeSummary({
      status: 'failed',
      outcome_status: 'failed',
      outcome_metrics: {
        queue_items_processed: 0,
        queue_items_failed: 1,
        queue_items_dead: 2,
        success_count: 0,
        failed_count: 3,
        outcome_kind: 'FAILED',
      },
    });
    const t = b.headlineLines.join('\n');
    expect(t).toMatch(/no successful compliance recalculations/i);
    expect(t).toMatch(/retry/i);
    expect(t).toMatch(/terminal failure/i);
  });

  it('renders Automation Centre–style summary for empty queue', () => {
    render(
      <RecalcAutomationCentreSummary
        lastRun={{
          status: 'success',
          outcome_status: 'conditional_no_output',
          outcome_metrics: { queue_empty: true, attempted_count: 0 },
        }}
      />,
    );
    expect(screen.getByTestId('compliance-recalc-worker-outcome-summary')).toHaveTextContent(
      /no compliance recalculation work was waiting/i,
    );
  });
});
