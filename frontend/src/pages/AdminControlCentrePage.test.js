/**
 * @jest-environment jsdom
 */
import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
      score_breakdowns: {
        automation: { failed_runs_24h_penalty: 0, heartbeat_stale_penalty: 0 },
        security_risk: { open_security_incidents: 5 },
        revenue: null,
        job_confidence: {
          heuristic: true,
          interpretation: 'Rough index from critical-path job states.',
          healthy_like_critical_jobs: 9,
          total_critical_jobs: 10,
          failed_critical_jobs: 0,
          degraded_critical_jobs: 0,
          missed_critical_jobs: 0,
          never_ran_or_overdue_critical_jobs: 0,
          penalties_applied_points: { from_failed_jobs: 0, from_degraded_jobs: 0, from_missed_jobs: 0 },
        },
      },
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
      business_outcomes_24h: {
        finished_runs: 3,
        outcome_success_sum: 10,
        outcome_failed_sum: 0,
        outcome_attempted_sum: 12,
        mixed_units_diagnostic_only: true,
        mixed_units_warning: 'Do not treat pooled totals as one KPI.',
      },
      outcome_families_24h: [
        {
          family_key: 'queue_processing',
          family_label: 'Queue & retry processing',
          family_disclaimer: 'Queue semantics.',
          finished_runs: 2,
          outcome_success_sum: 4,
          outcome_failed_sum: 0,
          outcome_attempted_sum: 5,
        },
      ],
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
        metadata: {
          threat_detections: { endpoint_probing: 2 },
          signal_tier: 'control_centre_summary',
          signal_tier_note: 'Also in Security section.',
        },
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

  it('shows readable job title for telemetry-flagged job runs and keeps raw id under technical details', async () => {
    render(
      <MemoryRouter>
        <AdminControlCentrePage />
      </MemoryRouter>,
    );
    await screen.findByTestId('control-centre-jobs-flagged');
    expect(screen.getByText('Compliance score recalculation worker')).toBeInTheDocument();
    const flagged = screen.getByTestId('control-centre-jobs-flagged');
    expect(flagged.textContent).toContain('Compliance score recalculation worker');
    expect(screen.getByText(/Telemetry: job runs marked success with zero attempted outcomes/i)).toBeInTheDocument();
    expect(screen.getByText(/automation job runs/i)).toBeInTheDocument();
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

  it('shows grouped outcome families as primary and mixed totals under diagnostics', async () => {
    render(
      <MemoryRouter>
        <AdminControlCentrePage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('control-centre-outcome-families')).toBeInTheDocument();
    expect(screen.getByText('Automation activity by operational family (24h)')).toBeInTheDocument();
    expect(screen.getByText('Queue & retry processing')).toBeInTheDocument();
    expect(screen.getByTestId('control-centre-mixed-unit-diagnostics')).toBeInTheDocument();
    expect(screen.getByText(/Mixed-unit totals across all jobs/i)).toBeInTheDocument();
    expect(screen.getByText('Successful units (Σ, mixed)')).toBeInTheDocument();
  });

  it('shows score factor breakdown panel when API provides score_breakdowns', async () => {
    render(
      <MemoryRouter>
        <AdminControlCentrePage />
      </MemoryRouter>,
    );
    const panel = await screen.findByTestId('control-centre-score-breakdowns');
    expect(within(panel).getByText('What went into these scores (contributing factors)')).toBeInTheDocument();
    fireEvent.click(within(panel).getByText('What went into these scores (contributing factors)'));
    expect(within(panel).getByText('Automation health')).toBeInTheDocument();
    expect(within(panel).getByText(/Penalty from failed runs/i)).toBeInTheDocument();
  });

  it('labels alert signal tier for summary-echo rows', async () => {
    render(
      <MemoryRouter>
        <AdminControlCentrePage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('alert-signal-anomaly-threat_detections')).toHaveTextContent('Summary echo');
  });

  it('shows billing operational narrative when revenue is visible', async () => {
    const snap = buildSnapshot();
    jest.spyOn(adminAPI, 'getControlCentreSnapshot').mockResolvedValue({
      data: {
        ...snap,
        access: { revenue_visible: true, viewer_role: 'ROLE_OWNER' },
        system: {
          ...snap.system,
          scores: { ...snap.system.scores, revenue_health: 82 },
          revenue_excluded_from_status_when_redacted: false,
          score_breakdowns: {
            ...snap.system.score_breakdowns,
            revenue: { past_due_penalty: 0 },
          },
        },
        revenue: {
          revenue_today_pence: 0,
          revenue_this_month_pence: 0,
          paid_charges_today_count: 0,
          paid_charges_month_count: 0,
          active_subscriptions: 1,
          mrr_pence: 1000,
          failed_payments_30d: 0,
          past_due_accounts: 0,
          pending_invoices: 0,
          limited_entitlement_clients: 0,
          stripe_events_failed_recent: 0,
          revenue_at_risk_pence: 0,
          revenue_at_risk_note: 'Heuristic.',
          operational_narrative_lines: ['Line A for triage.', 'Line B for triage.'],
        },
      },
    });
    render(
      <MemoryRouter>
        <AdminControlCentrePage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('control-centre-revenue-narrative')).toBeInTheDocument();
    expect(screen.getByText('Line A for triage.')).toBeInTheDocument();
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
