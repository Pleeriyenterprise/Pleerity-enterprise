import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AdminClientControlPanelPage from './AdminClientControlPanelPage';
import { adminAPI } from '../api/client';
import { toast } from '@/utils/portalNotifications';

jest.mock('../components/admin/UnifiedAdminLayout', () => ({ children }) => <div>{children}</div>);
jest.mock('../components/admin/AccountEnvironmentBadge', () => () => null);
jest.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: { portal_user_id: 'admin-1' } }) }));
jest.mock('../hooks/useStepUpApi', () => ({ useStepUpApi: () => ({ request: (fn) => fn({}), modal: null }) }));
jest.mock('@/utils/portalNotifications', () => ({ toast: { error: jest.fn(), success: jest.fn(), info: jest.fn() } }));

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ clientId: 'client-1' }),
    Link: ({ children }) => <span>{children}</span>,
  };
});

describe('AdminClientControlPanelPage payment history collapsible', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    jest.spyOn(adminAPI, 'getClientCommandCentreTaskActivity').mockResolvedValue({ data: { items: [] } });
    jest.spyOn(adminAPI, 'getClientAgreementsSummary').mockResolvedValue({
      data: { acceptances: [], issued_agreements: [], latest_issuance_failure: null },
    });
    jest.spyOn(adminAPI, 'getComplianceTruthExplain').mockResolvedValue({ data: { status: 'ok' } });
    jest.spyOn(adminAPI, 'getRuntimeRequirementsExplain').mockResolvedValue({ data: { rows: [] } });
    jest.spyOn(adminAPI, 'downloadClientIssuedAgreementPdf').mockResolvedValue({
      data: new Blob(['pdf'], { type: 'application/pdf' }),
      headers: {},
    });
    window.open = jest.fn();
    window.URL.createObjectURL = jest.fn(() => 'blob:test-url');
    window.URL.revokeObjectURL = jest.fn();
    window.confirm = jest.fn(() => true);
    window.prompt = jest.fn(() => 'Incident INC-12345 support retry reason');
    localStorage.setItem('auth_token', 'admin_token');
    localStorage.setItem('user', JSON.stringify({ portal_user_id: 'admin-1', role: 'ROLE_ADMIN' }));
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { href: 'http://localhost/' },
    });
    jest.spyOn(adminAPI, 'startClientImpersonation').mockResolvedValue({
      data: {
        access_token: 'imp_token',
        expires_at: '2099-01-01T00:00:00Z',
        user: { portal_user_id: 'p1', role: 'ROLE_CLIENT', client_id: 'client-1' },
        client: { client_id: 'client-1', name: 'Client One', company_name: 'Acme Ltd', target_email_masked: 'cli***@test.com' },
      },
    });
  });

  it('dropdown opens reliably and shows required empty-state copy', async () => {
    jest.spyOn(adminAPI, 'getClientControlPanel').mockResolvedValue({
      data: {
        identity: { client_id: 'client-1', name: 'Client One', email: 'x@test.com', plan: 'PLAN_1_SOLO', status: 'ACTIVE' },
        account_state: {},
        subscription_billing: { receipts: [], receipts_meta: { total: 0 }, billing_reconciliation_needed: false },
        compliance_overview: {},
        operations: {},
        activity_timeline: { payments: [], login_events: [], system_actions: [] },
        operational_snapshot: {},
      },
    });

    render(<AdminClientControlPanelPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Billing' }));

    const toggle = await screen.findByRole('button', { name: /Payment history & receipts/i });
    fireEvent.click(toggle);

    expect(await screen.findByText('No payment history recorded yet.')).toBeInTheDocument();
    expect(screen.getByText('Open full Admin Billing Centre')).toBeInTheDocument();
  });

  it('agreement section shows explicit empty state and safe PDF behavior', async () => {
    jest.spyOn(adminAPI, 'getClientControlPanel').mockResolvedValue({
      data: {
        identity: { client_id: 'client-1', name: 'Client One', email: 'x@test.com', plan: 'PLAN_1_SOLO', status: 'ACTIVE' },
        account_state: {},
        subscription_billing: { receipts: [], receipts_meta: { total: 0 }, billing_reconciliation_needed: false },
        compliance_overview: {},
        operations: {},
        activity_timeline: { payments: [], login_events: [], system_actions: [] },
        operational_snapshot: {},
      },
    });
    render(<AdminClientControlPanelPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Billing' }));
    fireEvent.click(await screen.findByRole('button', { name: /Agreement acceptance & issuance/i }));
    expect(await screen.findByText('Agreement accepted')).toBeInTheDocument();
    expect(screen.getByText('No issued agreements found for this client.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry issuance/i })).toBeDisabled();
  });

  it('compliance diagnostics are labelled support/internal with hidden raw JSON by default', async () => {
    jest.spyOn(adminAPI, 'getClientControlPanel').mockResolvedValue({
      data: {
        identity: { client_id: 'client-1', name: 'Client One', email: 'x@test.com', plan: 'PLAN_1_SOLO', status: 'ACTIVE' },
        account_state: {},
        subscription_billing: { receipts: [], receipts_meta: { total: 0 }, billing_reconciliation_needed: false },
        compliance_overview: {},
        operations: {},
        activity_timeline: { payments: [], login_events: [], system_actions: [] },
        operational_snapshot: {},
      },
    });
    render(<AdminClientControlPanelPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Compliance' }));
    const diagToggle = await screen.findByRole('button', { name: /Compliance diagnostics/i });
    expect(screen.getByText('Support/internal diagnostics only (read-only; never client-facing).')).toBeInTheDocument();
    fireEvent.click(diagToggle);
    expect(screen.queryByText(/"status": "ok"/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Load client compliance explain/i }));
    await screen.findByText(/Support summary/i);
    expect(screen.getByText(/"status": "ok"/)).not.toBeVisible();
    fireEvent.click(screen.getByText(/Raw compliance explain JSON/i));
    expect(await screen.findByText(/"status": "ok"/)).toBeVisible();
  });

  it('requires impersonation reason + confirmation checkbox and shows target preview', async () => {
    jest.spyOn(adminAPI, 'getClientControlPanel').mockResolvedValue({
      data: {
        identity: {
          client_id: 'client-1',
          name: 'Client One',
          company_name: 'Acme Ltd',
          email: 'client@test.com',
          plan: 'PLAN_1_SOLO',
          status: 'ACTIVE',
        },
        account_state: {},
        subscription_billing: { receipts: [], receipts_meta: { total: 0 }, billing_reconciliation_needed: false },
        compliance_overview: {},
        operations: {},
        activity_timeline: { payments: [], login_events: [], system_actions: [] },
        operational_snapshot: {},
      },
    });
    render(<AdminClientControlPanelPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'View as user…' }));
    expect(await screen.findByText(/You are about to access this customer's account\./i)).toBeInTheDocument();
    expect(screen.getByText(/Client ID:/i)).toBeInTheDocument();
    expect(screen.getByText(/Company:/i)).toBeInTheDocument();
    const confirmBtn = screen.getByTestId('impersonation-confirm');
    expect(confirmBtn).toBeDisabled();
    fireEvent.change(screen.getByTestId('impersonation-reason-input'), { target: { value: 'Incident 12345 support recovery session' } });
    expect(confirmBtn).toBeDisabled();
    fireEvent.click(screen.getByTestId('impersonation-confirm-checkbox'));
    expect(confirmBtn).toBeEnabled();
    fireEvent.click(confirmBtn);
    await waitFor(() =>
      expect(adminAPI.startClientImpersonation).toHaveBeenCalledWith(
        'client-1',
        30,
        expect.objectContaining({ reason: 'Incident 12345 support recovery session' }),
        expect.any(Object),
      ),
    );
  });

  it('shows escalation and onboarding milestone guidance in overview/billing', async () => {
    jest.spyOn(adminAPI, 'getClientControlPanel').mockResolvedValue({
      data: {
        identity: {
          client_id: 'client-1',
          name: 'Client One',
          company_name: 'Acme Ltd',
          email: 'client@test.com',
          plan: 'PLAN_1_SOLO',
          status: 'ACTIVE',
        },
        account_state: { onboarding_stage: 'PROVISIONED' },
        subscription_billing: {
          billing_last_synced_at: '2026-01-01T00:00:00Z',
          receipts: [],
          receipts_meta: { total: 0 },
          billing_reconciliation_needed: false,
        },
        compliance_overview: {},
        operations: {},
        activity_timeline: { payments: [], login_events: [], system_actions: [] },
        operational_snapshot: {},
      },
    });
    render(<AdminClientControlPanelPage />);
    expect(await screen.findByText(/Onboarding incident milestones/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Read-only diagnostic/i).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Billing' }));
    expect(await screen.findByText(/Engineering escalation required/i)).toBeInTheDocument();
  });

  it('renders stitched operational incident timeline with severity and affected object', async () => {
    jest.spyOn(adminAPI, 'getClientControlPanel').mockResolvedValue({
      data: {
        identity: { client_id: 'client-1', name: 'Client One', email: 'x@test.com', plan: 'PLAN_1_SOLO', status: 'ACTIVE' },
        account_state: {},
        subscription_billing: { receipts: [], receipts_meta: { total: 0 }, billing_reconciliation_needed: false },
        compliance_overview: {},
        operations: {},
        activity_timeline: {
          payments: [{ created_at: '2026-02-01T10:00:00Z', status: 'FAILED', payment_id: 'pay_1' }],
          login_events: [],
          system_actions: [
            { action: 'PROVISIONING_FAILED', timestamp: '2026-02-01T10:10:00Z', metadata: { job_id: 'job_1' } },
          ],
        },
        operational_snapshot: {},
      },
    });
    render(<AdminClientControlPanelPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Activity & Audit' }));
    fireEvent.click(await screen.findByRole('button', { name: /Operational incident timeline/i }));
    expect(await screen.findByText(/Engineering escalation required/i)).toBeInTheDocument();
    expect(screen.getByText(/Provisioning failed/i)).toBeInTheDocument();
    expect(screen.getByText(/Affected object: job:job_1/i)).toBeInTheDocument();
  });

  it('handles unavailable agreement PDF download safely', async () => {
    jest.spyOn(adminAPI, 'getClientAgreementsSummary').mockResolvedValue({
      data: {
        acceptances: [],
        issued_agreements: [{ issued_id: 'ISS-1', issued_at: '2026-01-01T00:00:00Z', outcome: 'issued', pdf_download_path: '/x.pdf' }],
        latest_issuance_failure: null,
        retry_eligible: false,
      },
    });
    jest.spyOn(adminAPI, 'downloadClientIssuedAgreementPdf').mockRejectedValue({
      response: { data: { detail: 'PDF unavailable' } },
    });
    jest.spyOn(adminAPI, 'getClientControlPanel').mockResolvedValue({
      data: {
        identity: { client_id: 'client-1', name: 'Client One', email: 'x@test.com', plan: 'PLAN_1_SOLO', status: 'ACTIVE' },
        account_state: {},
        subscription_billing: { receipts: [], receipts_meta: { total: 0 }, billing_reconciliation_needed: false },
        compliance_overview: {},
        operations: {},
        activity_timeline: { payments: [], login_events: [], system_actions: [] },
        operational_snapshot: {},
      },
    });
    render(<AdminClientControlPanelPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Billing' }));
    fireEvent.click(await screen.findByRole('button', { name: /Agreement acceptance & issuance/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Download PDF/i }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('PDF unavailable'));
  });

  it('shows retry only for retryable failed issuance and handles success/failure feedback', async () => {
    jest.spyOn(adminAPI, 'getClientAgreementsSummary').mockResolvedValueOnce({
      data: {
        acceptances: [{ acceptance_id: 'ACC-1', accepted_at: '2026-01-01T00:00:00Z', template_version_id: 'v1' }],
        issued_agreements: [{ issued_id: 'ISS-1', issued_at: '2026-01-02T00:00:00Z', outcome: 'issuance_failed' }],
        latest_issuance_failure: {
          acceptance_id: 'ACC-1',
          payment_reference: 'PAY-1',
          issued_at: '2026-01-02T00:00:00Z',
          failure_reason: 'render failed',
        },
        retry_eligible: true,
      },
    });
    jest.spyOn(adminAPI, 'retryClientAgreementIssue').mockResolvedValue({ data: { ok: true } });
    jest.spyOn(adminAPI, 'getClientControlPanel').mockResolvedValue({
      data: {
        identity: { client_id: 'client-1', name: 'Client One', email: 'x@test.com', plan: 'PLAN_1_SOLO', status: 'ACTIVE' },
        account_state: {},
        subscription_billing: { receipts: [], receipts_meta: { total: 0 }, billing_reconciliation_needed: false },
        compliance_overview: {},
        operations: {},
        activity_timeline: { payments: [], login_events: [], system_actions: [] },
        operational_snapshot: {},
      },
    });
    render(<AdminClientControlPanelPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Billing' }));
    fireEvent.click(await screen.findByRole('button', { name: /Agreement acceptance & issuance/i }));
    const retryBtn = await screen.findByRole('button', { name: /Retry issuance/i });
    expect(retryBtn).toBeEnabled();
    fireEvent.click(retryBtn);
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Agreement issuance retry submitted'));
    expect(adminAPI.retryClientAgreementIssue).toHaveBeenCalledWith(
      'client-1',
      expect.objectContaining({ reason: expect.any(String) }),
    );
  });

  it('shows retry failure feedback when retry endpoint fails', async () => {
    jest.spyOn(adminAPI, 'getClientAgreementsSummary').mockResolvedValue({
      data: {
        acceptances: [{ acceptance_id: 'ACC-1', accepted_at: '2026-01-01T00:00:00Z', template_version_id: 'v1' }],
        issued_agreements: [{ issued_id: 'ISS-1', issued_at: '2026-01-02T00:00:00Z', outcome: 'issuance_failed' }],
        latest_issuance_failure: {
          acceptance_id: 'ACC-1',
          payment_reference: 'PAY-1',
          issued_at: '2026-01-02T00:00:00Z',
          failure_reason: 'render failed',
        },
        retry_eligible: true,
      },
    });
    jest.spyOn(adminAPI, 'retryClientAgreementIssue').mockRejectedValue({
      response: { data: { detail: { error: 'retry blocked' } } },
    });
    jest.spyOn(adminAPI, 'getClientControlPanel').mockResolvedValue({
      data: {
        identity: { client_id: 'client-1', name: 'Client One', email: 'x@test.com', plan: 'PLAN_1_SOLO', status: 'ACTIVE' },
        account_state: {},
        subscription_billing: { receipts: [], receipts_meta: { total: 0 }, billing_reconciliation_needed: false },
        compliance_overview: {},
        operations: {},
        activity_timeline: { payments: [], login_events: [], system_actions: [] },
        operational_snapshot: {},
      },
    });
    render(<AdminClientControlPanelPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Billing' }));
    fireEvent.click(await screen.findByRole('button', { name: /Agreement acceptance & issuance/i }));
    const retryBtn = await screen.findByRole('button', { name: /Retry issuance/i });
    fireEvent.click(retryBtn);
    jest.spyOn(adminAPI, 'retryClientAgreementIssue').mockRejectedValueOnce({
      response: { data: { detail: { error: 'retry blocked' } } },
    });
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('retry blocked'));
  });

  it('shows reconciliation-required banner when backend flag is true', async () => {
    jest.spyOn(adminAPI, 'getClientControlPanel').mockResolvedValue({
      data: {
        identity: { client_id: 'client-1', name: 'Client One', email: 'x@test.com', plan: 'PLAN_1_SOLO', status: 'ACTIVE' },
        account_state: {},
        subscription_billing: {
          receipts: [],
          receipts_meta: { total: 0 },
          lifecycle_status_label: 'cancel_at_period_end',
          canonical_entitlement_state: 'ENABLED',
          billing_reconciliation_needed: true,
          billing_reconciliation_reason: 'clients_update_failed_after_billing_sync',
        },
        compliance_overview: {},
        operations: {},
        activity_timeline: { payments: [], login_events: [], system_actions: [] },
        operational_snapshot: {},
      },
    });
    render(<AdminClientControlPanelPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Billing' }));
    expect(await screen.findByText(/Reconciliation required: clients_update_failed_after_billing_sync/i)).toBeInTheDocument();
    expect(screen.getByText('Lifecycle status')).toBeInTheDocument();
    expect(screen.getByText('Access state')).toBeInTheDocument();
    expect(screen.getByText('Reconciliation required')).toBeInTheDocument();
    expect(screen.getByText('cancel_at_period_end')).toBeInTheDocument();
    expect(screen.getByText('ENABLED')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
  });
});

