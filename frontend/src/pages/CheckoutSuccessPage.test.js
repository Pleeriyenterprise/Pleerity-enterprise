/**
 * Checkout success route: must never fall through to the marketing homepage.
 * Recovery checkout customers have session_id but no pending_client_id in localStorage.
 */
import React from 'react';
import fs from 'fs';
import path from 'path';
import { render, screen, waitFor } from '@testing-library/react';
import CheckoutSuccessPage from './CheckoutSuccessPage';
import api from '../api/client';

const mockSearch = { current: '' };

jest.mock('react-router-dom', () => {
  const ReactLib = require('react');
  return {
    useNavigate: () => jest.fn(),
    useParams: () => ({}),
    useLocation: () => ({ pathname: '/checkout/success', search: mockSearch.current }),
    useSearchParams: () => [new URLSearchParams(mockSearch.current), jest.fn()],
    MemoryRouter: ({ children }) => children,
    Navigate: () => null,
    Route: () => null,
    Routes: ({ children }) => children,
    Link: ({ children, to, ...props }) => ReactLib.createElement('a', { href: to, ...props }, children),
    NavLink: ({ children, to, ...props }) => ReactLib.createElement('a', { href: to, ...props }, children),
    Outlet: () => null,
  };
});

jest.mock('../api/client', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
  },
}));

const pendingStatus = {
  client_id: 'client-pending',
  customer_reference: 'PLE-001',
  payment_state: 'pending_webhook',
  provisioning_status: 'IN_PROGRESS',
  next_action: 'wait_provisioning',
  password_set: false,
};

const completeStatus = {
  client_id: 'client-ready',
  customer_reference: 'PLE-002',
  payment_state: 'paid',
  provisioning_status: 'COMPLETED',
  next_action: 'set_password',
  password_set: false,
};

describe('CheckoutSuccessPage', () => {
  beforeEach(() => {
    api.get.mockReset();
    mockSearch.current = '';
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  test('App.js registers /checkout/success and does not redirect that path to /', () => {
    const appSrc = fs.readFileSync(path.join(__dirname, '..', 'App.js'), 'utf8');
    expect(appSrc).toMatch(/path="\/checkout\/success"/);
    expect(appSrc).toMatch(/CheckoutSuccessPage/);
    expect(appSrc).not.toMatch(/CheckoutSuccessRedirect/);
    expect(appSrc).not.toMatch(/window\.location\.href = '\//);
  });

  test('direct navigation to /checkout/success does not render marketing homepage', async () => {
    mockSearch.current = '';
    render(<CheckoutSuccessPage />);
    expect(screen.getByTestId('checkout-success-page')).toBeInTheDocument();
    expect(screen.getByTestId('checkout-success-missing-session')).toBeInTheDocument();
    expect(screen.queryByTestId('marketing-home')).not.toBeInTheDocument();
    expect(screen.queryByTestId('hero-cta-primary')).not.toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalled();
  });

  test('navigation with session_id stays on success page and preserves session_id', async () => {
    mockSearch.current = 'session_id=cs_test_abcdefghijklmnopqrstuv';
    api.get.mockResolvedValue({ data: pendingStatus });
    render(<CheckoutSuccessPage />);

    expect(screen.getByTestId('checkout-success-page')).toBeInTheDocument();
    expect(screen.queryByTestId('hero-cta-primary')).not.toBeInTheDocument();

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith(
        '/portal/setup-status',
        expect.objectContaining({
          params: expect.objectContaining({ session_id: 'cs_test_abcdefghijklmnopqrstuv' }),
        })
      );
    });

    expect(screen.getByTestId('checkout-success-session-id')).toHaveTextContent(
      'cs_test_abcdefghijklmnopqrstuv'
    );
    await waitFor(() => {
      expect(screen.getByTestId('checkout-success-pending')).toBeInTheDocument();
    });
  });

  test('invalid session_id shows invalid state, not homepage', async () => {
    mockSearch.current = 'session_id=cs_test_unknownsessionid001';
    api.get.mockRejectedValue({
      response: { status: 404, data: { detail: 'Checkout session not found' } },
    });
    render(<CheckoutSuccessPage />);

    await waitFor(() => {
      expect(screen.getByTestId('checkout-success-invalid-session')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('hero-cta-primary')).not.toBeInTheDocument();
    expect(screen.getByText(/do not start another registration/i)).toBeInTheDocument();
  });

  test('missing session_id does not call setup-status or fall back to homepage', async () => {
    mockSearch.current = '';
    render(<CheckoutSuccessPage />);
    expect(screen.getByTestId('checkout-success-missing-session')).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalled();
    expect(screen.queryByTestId('hero-cta-primary')).not.toBeInTheDocument();
  });

  test('provisioning pending state', async () => {
    mockSearch.current = 'session_id=cs_test_abcdefghijklmnopqrstuv';
    api.get.mockResolvedValue({ data: pendingStatus });
    render(<CheckoutSuccessPage />);

    await waitFor(() => {
      expect(screen.getByTestId('checkout-success-pending')).toBeInTheDocument();
    });
    expect(screen.getByText(/still finishing your account setup/i)).toBeInTheDocument();
    expect(screen.queryByTestId('checkout-success-sign-in')).not.toBeInTheDocument();
  });

  test('provisioning complete state', async () => {
    mockSearch.current = 'session_id=cs_test_abcdefghijklmnopqrstuv';
    api.get.mockResolvedValue({ data: completeStatus });
    render(<CheckoutSuccessPage />);

    await waitFor(() => {
      expect(screen.getByTestId('checkout-success-complete')).toBeInTheDocument();
    });
    expect(screen.getByText(/check your email/i)).toBeInTheDocument();
    expect(screen.getByTestId('checkout-success-progress-link')).toHaveAttribute(
      'href',
      '/onboarding-status?client_id=client-ready&session_id=cs_test_abcdefghijklmnopqrstuv'
    );
    expect(screen.queryByTestId('hero-cta-primary')).not.toBeInTheDocument();
  });
});
