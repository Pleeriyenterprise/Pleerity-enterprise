/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AdminControlCentrePage from './AdminControlCentrePage';
import { adminAPI } from '../api/client';

jest.mock('../components/admin/UnifiedAdminLayout', () => function MockLayout({ children }) {
  return <div data-testid="mock-admin-layout">{children}</div>;
});

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

function buildSnapshot() {
  return {
    generated_at: new Date().toISOString(),
    access: { revenue_visible: false, viewer_role: 'ROLE_ADMIN' },
    system: {
      status: 'healthy',
      overall_automation_health: 'healthy',
      last_system_check_at: new Date().toISOString(),
      scores: { automation_health: 90, security_risk: 5, revenue_health: null, job_confidence: 88 },
      observability_db_name: 'pleerity_test',
      revenue_excluded_from_status_when_redacted: true,
    },
    automation: {
      total_tracked_jobs: 10,
      total_job_runs_recorded: 100,
      healthy_critical_jobs: 9,
      failed_critical_jobs: 0,
      degraded_critical_jobs: 0,
      missed_critical_jobs: 0,
      never_ran_overdue_critical_jobs: 0,
      failed_runs_24h: 0,
      degraded_runs_24h: 0,
      last_completed_latest_critical_path: null,
      next_scheduled_run_earliest: null,
      open_operational_incidents: 0,
      business_outcomes_24h: { finished_runs: 3, outcome_success_sum: 10, outcome_failed_sum: 0, outcome_attempted_sum: 12 },
      jobs_flagged_no_expected_outcome: [
        { job_name: 'compliance_recalc_worker', recommended_action: 'Verify configuration.', last_completed: null },
      ],
      job_states_sample: { compliance_recalc_worker: { state: 'healthy' } },
    },
    security: {
      summary: {
        authentication_activity: { failed_attempts: 0 },
        incidents: { open: 0, recent: [], recent_truncated: false, recent_omitted_count: 0 },
        threat_detections: {},
        file_document_access: {},
        system_integrity: {},
        payment_webhook_integrity: {},
      },
      failed_login_attempts_7d: 0,
      suspicious_activity: {
        open_security_incidents: 0,
        threat_detections_7d: {
          endpoint_probing: 2,
          token_reuse_multi_ip: 1,
          cross_user_data_access_probe: 1,
        },
        cross_user_access_attempts_7d: 0,
      },
      webhook_validation_failures_7d: 0,
      token_misuse_7d: 0,
      document_access_violations_7d: 0,
      security_incidents_resolved_7d: 0,
    },
    revenue: { redacted: true, reason: 'Revenue metrics require Owner role (ROLE_OWNER).' },
    engagement: {
      new_clients_7d: 0,
      provisioned_clients_total: 1,
      portal_users_active_client_roles: 1,
      portal_users_inactive_30d_client_roles: 0,
      onboarding_completion_rate_percent: 50,
      document_uploads_7d: 0,
      total_properties_scored: 3,
      compliance_status_by_property: { GREEN: 1, UNKNOWN: 2 },
      compliance_numeric_score_buckets: { '80_100': 1, unknown: 2 },
    },
    alerts: [
      {
        id: 'anomaly:threat_detections',
        category: 'anomaly',
        severity: 'MEDIUM',
        timestamp: new Date().toISOString(),
        status: 'open',
        title: 'Security threat detections (7d window)',
        detail: "Aggregated detection counts: {'endpoint_probing': 2}",
        required_action: 'Triage',
        link_path: '/admin/security',
        metadata: { threat_detections: { endpoint_probing: 2 } },
      },
    ],
    scoring_notes: {
      automation_health: '100 minus weighted penalties … stale delivery_unknown.',
    },
  };
}

describe('AdminControlCentrePage', () => {
  beforeEach(() => {
    jest.spyOn(adminAPI, 'getControlCentreSnapshot').mockResolvedValue({ data: buildSnapshot() });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('shows human threat labels in summary without raw keys in summary container', async () => {
    render(
      <MemoryRouter>
        <AdminControlCentrePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(adminAPI.getControlCentreSnapshot).toHaveBeenCalled());
    expect(await screen.findByText('Endpoint probing')).toBeInTheDocument();
    const summary = screen.getByTestId('control-centre-threat-summary');
    expect(summary.textContent).not.toMatch(/endpoint_probing/);
    expect(summary.textContent).not.toMatch(/token_reuse_multi_ip/);
    const raw = screen.getByTestId('control-centre-threat-raw-json');
    expect(raw.textContent).toContain('endpoint_probing');
  });

  it('shows readable job title for flagged jobs and keeps raw id under technical details', async () => {
    render(
      <MemoryRouter>
        <AdminControlCentrePage />
      </MemoryRouter>,
    );
    await screen.findByTestId('control-centre-jobs-flagged');
    expect(screen.getByText('Compliance score recalculation worker')).toBeInTheDocument();
    const flagged = screen.getByTestId('control-centre-jobs-flagged');
    expect(flagged.textContent).toContain('Compliance score recalculation worker');
    expect(screen.getByText('Technical id')).toBeInTheDocument();
  });

  it('shows non-authoritative snapshot copy and Unclassified for UNKNOWN', async () => {
    render(
      <MemoryRouter>
        <AdminControlCentrePage />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/Non-authoritative DB snapshot/i)).toBeInTheDocument();
    expect(screen.getByText('Unclassified')).toBeInTheDocument();
    expect(screen.queryByText(/^UNKNOWN$/)).not.toBeInTheDocument();
    expect(screen.getByText('No score stored')).toBeInTheDocument();
  });

  it('uses human labels for automation outcome tallies (not raw counter names)', async () => {
    render(
      <MemoryRouter>
        <AdminControlCentrePage />
      </MemoryRouter>,
    );
    expect(await screen.findByText('Successful units (summed)')).toBeInTheDocument();
    expect(screen.queryByText(/Σ success_count/)).not.toBeInTheDocument();
  });

  it('humanizes scoring note text for delivery confirmation wording', async () => {
    render(
      <MemoryRouter>
        <AdminControlCentrePage />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/delivery confirmation still pending/i)).toBeInTheDocument();
    expect(screen.queryByText(/delivery_unknown/)).not.toBeInTheDocument();
  });

  it('shows automation engine status as words, not raw enum in primary line', async () => {
    render(
      <MemoryRouter>
        <AdminControlCentrePage />
      </MemoryRouter>,
    );
    await screen.findByText('Automation engine status:');
    expect(screen.getByTestId('automation-engine-tech-details')).toBeInTheDocument();
    expect(screen.getByText(/overall_automation_health:/)).toBeInTheDocument();
  });
});
