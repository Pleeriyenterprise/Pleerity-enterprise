import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import AdminBillingPage from './AdminBillingPage';
import api from '../api/client';

jest.mock('./AdminPendingPaymentsPage', () => () => <div data-testid="pending-payments-page" />);

const mockNavigate = jest.fn();
const mockSetSearchParams = jest.fn();

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [
      {
        get: (k) => (k === 'client' ? 'client-1' : null),
      },
      mockSetSearchParams,
    ],
  };
});

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn(), info: jest.fn(), warning: jest.fn() },
}));

describe('AdminBillingPage payment history states', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    mockNavigate.mockReset();
    mockSetSearchParams.mockReset();
  });

  function mockCommonApi({ receipts = [] }) {
    jest.spyOn(api, 'get').mockImplementation((url) => {
      if (url === '/admin/billing/statistics') return Promise.resolve({ data: {} });
      if (url === '/admin/billing/clients/client-1') {
        return Promise.resolve({
          data: {
            client_id: 'client-1',
            contact_email: 'a@test.com',
            contact_name: 'Client A',
            entitlement_status: 'ENABLED',
            plan_name: 'Solo',
            plan_code: 'PLAN_1_SOLO',
            max_properties: 1,
            current_property_count: 1,
            subscription_status: 'ACTIVE',
          },
        });
      }
      if (String(url).startsWith('/admin/billing/clients/client-1/receipts?')) {
        return Promise.resolve({ data: { receipts } });
      }
      return Promise.resolve({ data: {} });
    });
    jest.spyOn(api, 'post').mockResolvedValue({ data: { success: true } });
  }

  it('empty payment history shows required empty-state copy', async () => {
    mockCommonApi({ receipts: [] });
    render(<AdminBillingPage />);
    expect(await screen.findByText('No payment history recorded yet.')).toBeInTheDocument();
  });

  it('renders populated and failed rows; disables unavailable actions with reason', async () => {
    mockCommonApi({
      receipts: [
        {
          receipt_key: 'subscription:INV-100',
          source: 'subscription',
          invoice_number: 'INV-100',
          date_issued: '2026-04-20T10:00:00Z',
          amount_display: '£19.00',
          payment_status: 'PAID',
          payment_method: 'Card (Stripe)',
          payment_reference_display: 'INV-100',
          stripe_reference_display: 'in_100',
          download_available: true,
          resend_available: true,
          failed_attempt_marker: false,
        },
        {
          receipt_key: 'subscription:INV-101',
          source: 'subscription',
          invoice_number: 'INV-101',
          date_issued: '2026-04-21T10:00:00Z',
          amount_display: '£19.00',
          payment_status: 'FAILED',
          payment_method: 'Card (Stripe)',
          payment_reference_display: 'INV-101',
          stripe_reference_display: 'in_101',
          download_available: false,
          resend_available: false,
          download_unavailable_reason: 'Receipt PDF is not available yet.',
          resend_unavailable_reason: 'Receipt email requires a stored receipt PDF.',
          failed_attempt_marker: true,
          failed_attempt_reason: 'Payment requires support follow-up.',
        },
      ],
    });
    render(<AdminBillingPage />);

    expect((await screen.findAllByText('INV-100')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('INV-101').length).toBeGreaterThan(0);
    expect(screen.getByText('Failed payment recorded')).toBeInTheDocument();

    const downloadDisabled = screen.getByTestId('receipt-download-subscription:INV-101');
    const resendDisabled = screen.getByTestId('receipt-resend-subscription:INV-101');
    expect(downloadDisabled).toBeDisabled();
    expect(resendDisabled).toBeDisabled();
    expect(downloadDisabled).toHaveAttribute('title', 'Receipt PDF is not available yet.');
    expect(resendDisabled).toHaveAttribute('title', 'Receipt email requires a stored receipt PDF.');
  });

  it('renders lifecycle/access/reconciliation visibility consistently', async () => {
    mockCommonApi({ receipts: [] });
    jest.spyOn(api, 'get').mockImplementation((url) => {
      if (url === '/admin/billing/statistics') return Promise.resolve({ data: {} });
      if (url === '/admin/billing/clients/client-1') {
        return Promise.resolve({
          data: {
            client_id: 'client-1',
            contact_email: 'a@test.com',
            contact_name: 'Client A',
            entitlement_status: 'ENABLED',
            plan_name: 'Solo',
            plan_code: 'PLAN_1_SOLO',
            max_properties: 1,
            current_property_count: 1,
            subscription_status: 'ACTIVE',
            billing_reconciliation_needed: true,
            billing_reconciliation_reason: 'clients_update_failed_after_billing_sync',
            subscription_lifecycle: {
              lifecycle_status_label: 'Cancelling at period end',
              canonical_entitlement_state: 'ENABLED',
              billing_lifecycle_state: 'CANCEL_AT_PERIOD_END',
            },
          },
        });
      }
      if (String(url).startsWith('/admin/billing/clients/client-1/receipts?')) {
        return Promise.resolve({ data: { receipts: [] } });
      }
      return Promise.resolve({ data: {} });
    });

    render(<AdminBillingPage />);

    const lifecycleCard = await screen.findByTestId('subscription-lifecycle-card');
    const inLifecycle = within(lifecycleCard);
    expect(inLifecycle.getByText('Lifecycle status')).toBeInTheDocument();
    expect(inLifecycle.getByText('Cancelling at period end')).toBeInTheDocument();
    expect(inLifecycle.getByText('Access state')).toBeInTheDocument();
    expect(inLifecycle.getByText('ENABLED')).toBeInTheDocument();
    expect(inLifecycle.getByText('Reconciliation needed')).toBeInTheDocument();
    expect(inLifecycle.getByText('Reconciliation reason')).toBeInTheDocument();
    expect(inLifecycle.getByText('clients_update_failed_after_billing_sync')).toBeInTheDocument();
    expect(screen.getByText('Reconciliation required: clients_update_failed_after_billing_sync')).toBeInTheDocument();
    expect(screen.getByText('No payment history recorded yet.')).toBeInTheDocument();
  });
});

