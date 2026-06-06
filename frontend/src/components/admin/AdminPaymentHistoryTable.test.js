import React from 'react';
import { render, screen } from '@testing-library/react';
import AdminPaymentHistoryTable from './AdminPaymentHistoryTable';

describe('AdminPaymentHistoryTable', () => {
  it('shows exact empty-state copy', () => {
    render(<AdminPaymentHistoryTable rows={[]} loading={false} error="" />);
    expect(screen.getByText(/No payment history rows in this view/i)).toBeInTheDocument();
  });

  it('renders retry timeline fields from backend', () => {
    render(
      <AdminPaymentHistoryTable
        rows={[
          {
            receipt_key: 'subscription:INV-1',
            invoice_number: 'INV-1',
            payment_status: 'FAILED',
            retry_state_label: 'Awaiting retry',
            next_retry_at_utc: '2026-04-30T10:00:00Z',
            grace_period_ends_at_utc: '2026-05-02T10:00:00Z',
            download_available: false,
            resend_available: false,
          },
        ]}
        loading={false}
        error=""
      />
    );
    expect(screen.getByText('Awaiting retry')).toBeInTheDocument();
    expect(screen.getByText(/Next retry:/i)).toBeInTheDocument();
    expect(screen.getByText(/Grace period ends:/i)).toBeInTheDocument();
  });

  it('shows View Stripe invoice link for ledger rows with hosted URL', () => {
    render(
      <AdminPaymentHistoryTable
        rows={[
          {
            receipt_key: 'subscription_ledger:in_abc',
            invoice_number: 'PLEERITY-1001',
            source_detail: 'subscription_payment_ledger',
            financial_evidence_ledger_row: true,
            payment_method: 'Card (Stripe) — ledger',
            hosted_invoice_url: 'https://invoice.stripe.com/i/test_ledger',
            download_available: false,
            resend_available: false,
          },
        ]}
        loading={false}
        error=""
        compact
      />
    );
    const link = screen.getByRole('link', { name: /View Stripe invoice/i });
    expect(link).toHaveAttribute('href', 'https://invoice.stripe.com/i/test_ledger');
    expect(link).toHaveAttribute('target', '_blank');
    expect(screen.queryByText(/^Download$/)).not.toBeInTheDocument();
  });

  it('shows unavailable copy for ledger rows without Stripe URL', () => {
    render(
      <AdminPaymentHistoryTable
        rows={[
          {
            receipt_key: 'subscription_ledger:in_xyz',
            source_detail: 'subscription_payment_ledger',
            download_available: false,
            resend_available: false,
            hosted_invoice_unavailable_reason: 'No hosted invoice URL on ledger row yet.',
          },
        ]}
        loading={false}
        error=""
        compact
      />
    );
    expect(screen.getByText(/Stripe invoice unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Download$/)).not.toBeInTheDocument();
  });

  it('keeps Download for non-ledger rows with PDF', () => {
    render(
      <AdminPaymentHistoryTable
        rows={[
          {
            receipt_key: 'subscription:INV-100',
            invoice_number: 'INV-100',
            source_detail: 'subscription_checkout',
            download_available: true,
            resend_available: true,
          },
        ]}
        loading={false}
        error=""
        compact
      />
    );
    expect(screen.getByRole('button', { name: /Download/i })).toBeEnabled();
    expect(screen.queryByText(/View Stripe invoice/i)).not.toBeInTheDocument();
  });
});
