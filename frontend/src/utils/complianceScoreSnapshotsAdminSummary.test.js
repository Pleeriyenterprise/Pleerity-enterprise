import React from 'react';
import { render, screen } from '@testing-library/react';
import {
  formatComplianceScoreSnapshotsOutcomeSummary,
  getComplianceScoreSnapshotsDisplayLastRun,
} from './complianceScoreSnapshotsAdminSummary';

describe('getComplianceScoreSnapshotsDisplayLastRun', () => {
  it('merges inventory outcome_metrics when job-runs row lacks them', () => {
    const runInfo = { lastRun: { id: 'a', status: 'success', outcome_metrics: {} } };
    const invInfo = {
      last_run_id: 'a',
      last_status: 'success',
      last_outcome_metrics: { clients_considered: 1, clients_succeeded: 1, clients_failed: 0 },
    };
    const lr = getComplianceScoreSnapshotsDisplayLastRun(runInfo, invInfo);
    expect(lr.outcome_metrics.clients_considered).toBe(1);
  });
});

describe('formatComplianceScoreSnapshotsOutcomeSummary', () => {
  it('shows no ACTIVE clients when no work', () => {
    const b = formatComplianceScoreSnapshotsOutcomeSummary({
      status: 'success',
      outcome_status: 'conditional_no_output',
      outcome_metrics: {
        no_clients: true,
        clients_considered: 0,
        clients_succeeded: 0,
        clients_failed: 0,
        outcome_kind: 'NO_WORK_ELIGIBLE',
      },
    });
    expect(b.headlineLines[0]).toMatch(/no active clients/i);
    expect(b.headlineLines.join(' ').toUpperCase()).not.toContain('NO_WORK_ELIGIBLE');
  });

  it('shows clients snapshotted and property lines', () => {
    const b = formatComplianceScoreSnapshotsOutcomeSummary({
      status: 'success',
      outcome_status: 'success',
      outcome_metrics: {
        clients_considered: 3,
        clients_succeeded: 3,
        clients_failed: 0,
        property_snapshots_created: 10,
        property_snapshot_failures: 0,
        property_snapshots_skipped_no_score: 2,
        property_enumeration_failures: 0,
      },
    });
    const t = b.headlineLines.join('\n');
    expect(t).toMatch(/3 of 3.*snapshotted/i);
    expect(t).toMatch(/10.*property.*created/i);
    expect(t).toMatch(/2.*skipped.*no stored compliance score/i);
  });

  it('shows client and property failures', () => {
    const b = formatComplianceScoreSnapshotsOutcomeSummary({
      status: 'degraded',
      outcome_status: 'degraded',
      outcome_metrics: {
        clients_considered: 4,
        clients_succeeded: 3,
        clients_failed: 1,
        property_snapshots_created: 5,
        property_snapshot_failures: 2,
        property_snapshots_skipped_no_score: 0,
      },
    });
    const t = b.headlineLines.join('\n');
    expect(t).toMatch(/3 of 4/i);
    expect(t).toMatch(/1 client snapshot/i);
    expect(t).toMatch(/2 property snapshot failure/i);
  });

  it('keeps raw outcome_kind in technical payload only', () => {
    const b = formatComplianceScoreSnapshotsOutcomeSummary({
      status: 'success',
      outcome_status: 'success',
      outcome_metrics: {
        clients_considered: 1,
        clients_succeeded: 1,
        outcome_kind: 'WORK_PERFORMED',
      },
    });
    expect(b.headlineLines.join(' ').toUpperCase()).not.toContain('WORK_PERFORMED');
    expect(JSON.stringify(b.technicalPayload)).toContain('WORK_PERFORMED');
  });

  it('renders Automation Centre–style block for no-work', () => {
    function SnapUi({ lastRun }) {
      const bundle = formatComplianceScoreSnapshotsOutcomeSummary(lastRun);
      return (
        <div data-testid="compliance-score-snapshots-outcome-summary">
          {bundle.headlineLines.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      );
    }
    render(
      <SnapUi
        lastRun={{
          outcome_status: 'conditional_no_output',
          outcome_metrics: { no_clients: true, clients_considered: 0 },
        }}
      />,
    );
    expect(screen.getByTestId('compliance-score-snapshots-outcome-summary')).toHaveTextContent(
      /no active clients/i,
    );
  });
});
