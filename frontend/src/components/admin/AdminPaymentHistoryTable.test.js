import React from 'react';
import { render, screen } from '@testing-library/react';
import AdminPaymentHistoryTable from './AdminPaymentHistoryTable';

describe('AdminPaymentHistoryTable', () => {
  it('shows exact empty-state copy', () => {
    render(<AdminPaymentHistoryTable rows={[]} loading={false} error="" />);
    expect(screen.getByText('No payment history recorded yet.')).toBeInTheDocument();
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
});
