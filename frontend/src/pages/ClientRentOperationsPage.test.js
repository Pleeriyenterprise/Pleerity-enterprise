/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ClientRentOperationsPage from './ClientRentOperationsPage';
import { clientAPI } from '../api/client';

const mockSetSearchParams = jest.fn();

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useSearchParams: () => [new URLSearchParams('tab=attention'), mockSetSearchParams],
  useNavigate: () => jest.fn(),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock('../api/client', () => ({
  __esModule: true,
  clientAPI: {
    getRentSummary: jest.fn(),
    getRentLedgers: jest.fn(),
    getRentExpenses: jest.fn(),
    getRentExpensesSummary: jest.fn(),
    getProperties: jest.fn(),
    getRentLedger: jest.fn(),
    markRentReminderSent: jest.fn(),
    getRentCapabilities: jest.fn(),
  },
}));

jest.mock('../utils/EntitlementProtectedRoute', () => ({
  EntitlementProtectedRoute: ({ children }) => <>{children}</>,
}));

describe('ClientRentOperationsPage', () => {
  beforeEach(() => {
    clientAPI.getRentSummary.mockResolvedValue({
      data: {
        rent_collected_this_month_minor: 120000,
        upcoming_due_count: 2,
        overdue_count: 1,
        partially_paid_count: 0,
        tenancies_with_arrears_count: 1,
        average_payment_delay_days: 3,
        currency: 'GBP',
      },
    });
    clientAPI.getRentLedgers.mockResolvedValue({ data: { ledgers: [], total: 0 } });
    clientAPI.getRentExpenses.mockResolvedValue({ data: { expenses: [], total: 0 } });
    clientAPI.getRentExpensesSummary.mockResolvedValue({
      data: { by_category: [], total_expenses_minor: 0 },
    });
    clientAPI.getProperties.mockResolvedValue({ data: { properties: [] } });
    clientAPI.getRentLedger.mockResolvedValue({ data: {} });
    clientAPI.markRentReminderSent.mockResolvedValue({ data: {} });
    clientAPI.getRentCapabilities.mockResolvedValue({ data: { tenancy_authority: true } });
  });

  it('renders summary cards and tabs', async () => {
    render(
      <MemoryRouter>
        <ClientRentOperationsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('rent-operations-page')).toBeInTheDocument();
    expect(await screen.findByTestId('rent-summary-cards')).toBeInTheDocument();
    expect(screen.getByTestId('rent-tab-attention')).toBeInTheDocument();
    expect(screen.getByTestId('rent-tab-expenses')).toBeInTheDocument();
  });

  it('shows attention empty state when rent activity exists but no attention ledgers', async () => {
    render(
      <MemoryRouter>
        <ClientRentOperationsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('rent-attention-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('rent-empty-state')).not.toBeInTheDocument();
  });
});
