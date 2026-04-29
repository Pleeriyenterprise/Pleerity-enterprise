import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ClientPortalLayout from './ClientPortalLayout';
import { authAPI } from '../api/client';

jest.mock('react-router-dom', () => ({
  NavLink: ({ children, to, className, end: _end, ...props }) => (
    <a
      href={typeof to === 'string' ? to : '#'}
      className={typeof className === 'function' ? className({ isActive: false }) : className}
      {...props}
    >
      {children}
    </a>
  ),
  useNavigate: () => jest.fn(),
  useLocation: () => ({ pathname: '/dashboard' }),
}));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { role: 'ROLE_CLIENT_ADMIN', client_id: 'client-1', portal_user_id: 'pu-1' },
    logout: jest.fn(),
    isClient: true,
  }),
}));

jest.mock('../contexts/EntitlementsContext', () => ({
  useEntitlements: () => ({
    hasFeature: () => true,
    entitlementsLoadFailed: false,
  }),
}));

jest.mock('./SessionIdleGuard', () => ({
  __esModule: true,
  default: ({ children }) => <>{children}</>,
}));

jest.mock('./ui/button', () => ({
  __esModule: true,
  Button: ({ children, ...props }) => <button {...props}>{children}</button>,
}));

jest.mock('../api/client', () => ({
  __esModule: true,
  default: { get: jest.fn(() => Promise.resolve({ data: {} })) },
  authAPI: { stopImpersonation: jest.fn(() => Promise.resolve({})) },
  clientAPI: {
    getInAppNotifications: jest.fn(() => Promise.resolve({ data: { items: [] } })),
    getInAppNotificationsUnreadCount: jest.fn(() => Promise.resolve({ data: { unread_count: 0 } })),
    getPortalContext: jest.fn(() => Promise.resolve({ data: { server_time: '2026-01-01T00:00:00Z' } })),
    getDashboard: jest.fn(() => Promise.resolve({ data: { client: { customer_reference: 'CRN-1' } } })),
  },
}));

describe('ClientPortalLayout impersonation banner', () => {
  let consoleErrorSpy;

  beforeEach(() => {
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    const { default: api, clientAPI } = require('../api/client');
    api.get.mockResolvedValue({ data: { has_avatar: false } });
    clientAPI.getDashboard.mockResolvedValue({ data: { client: { customer_reference: 'CRN-1' } } });
    clientAPI.getPortalContext.mockResolvedValue({ data: { server_time: '2026-01-01T00:00:00Z' } });
    clientAPI.getInAppNotifications.mockResolvedValue({ data: { items: [] } });
    clientAPI.getInAppNotificationsUnreadCount.mockResolvedValue({ data: { unread_count: 0 } });

    localStorage.setItem(
      'impersonation_context',
      JSON.stringify({
        active: true,
        client_id: 'client-1',
        client_name: 'Client One',
        target_email_masked: 'cli***@example.com',
        expires_at: '2099-01-01T00:00:00Z',
      }),
    );
    sessionStorage.setItem('impersonation_admin_token', 'admin-token');
    sessionStorage.setItem('impersonation_admin_user', JSON.stringify({ portal_user_id: 'admin-1' }));
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    consoleErrorSpy.mockRestore();
  });

  it('shows active banner context, duration, and exit action invoking stop flow', async () => {
    render(
      <ClientPortalLayout>
        <div>child</div>
      </ClientPortalLayout>,
    );

    expect(await screen.findByText(/Impersonation active\./i)).toBeInTheDocument();
    expect(screen.getByText(/Client ID: client-1/i)).toBeInTheDocument();
    expect(screen.getByText(/User: cli\*\*\*@example\.com/i)).toBeInTheDocument();
    expect(screen.getByText(/remaining/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Exit impersonation/i }));
    await waitFor(() => expect(authAPI.stopImpersonation).toHaveBeenCalled());
  });
});

