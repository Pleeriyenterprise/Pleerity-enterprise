import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ClientPortalLayout from './ClientPortalLayout';
import { clientAPI } from '../api/client';

jest.mock('react-router-dom', () => ({
  NavLink: ({ children, to, className, end: _end, onClick, ...props }) => (
    <a
      href={typeof to === 'string' ? to : '#'}
      className={typeof className === 'function' ? className({ isActive: false }) : className}
      onClick={onClick}
      {...props}
    >
      {children}
    </a>
  ),
  useNavigate: () => jest.fn(),
  useLocation: () => ({ pathname: '/requirements' }),
}));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { role: 'ROLE_CLIENT_ADMIN', client_id: 'client-1', portal_user_id: 'pu-1' },
    logout: jest.fn(),
    isClient: true,
  }),
}));

jest.mock('../contexts/LifecycleRuntimeContext', () => ({
  usePortalMode: () => ({
    portalMode: 'FULL_ACCESS',
    navigationPolicy: {
      landing_route: '/today',
      locked_routes: [],
      read_only_routes: [],
      hidden_routes: [],
    },
    customerExperience: { heading: '', current_state_label: 'Active' },
    runtimeAvailable: true,
  }),
  useLifecycleRuntime: () => ({
    loading: false,
    error: null,
    runtimeAvailable: true,
    portalMode: 'FULL_ACCESS',
    warnings: [],
    capabilityAllowed: () => true,
    getCapabilityGrant: () => ({ allowed: true }),
  }),
}));

jest.mock('../utils/accountCapabilityAccess', () => ({
  usePortalNavigationCapabilities: () => ({
    navHasFeature: () => true,
    showReports: true,
    showBilling: true,
    showCalendar: true,
    showAssistant: true,
    invoicingEnabled: true,
  }),
  useProfileCapabilities: () => ({
    canEditProfile: true,
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
    getInAppNotifications: jest.fn(),
    getInAppNotificationsUnreadCount: jest.fn(),
    markInAppNotificationRead: jest.fn(() => Promise.resolve({})),
    markAllInAppNotificationsRead: jest.fn(() => Promise.resolve({})),
    dismissInAppNotification: jest.fn(() => Promise.resolve({})),
    getPortalContext: jest.fn(() => Promise.resolve({ data: { server_time: '2026-01-01T00:00:00Z' } })),
    getDashboard: jest.fn(() => Promise.resolve({ data: { client: { customer_reference: 'CRN-1' } } })),
  },
}));

async function openBell() {
  fireEvent.click(screen.getByRole('button', { name: /notifications/i }));
}

describe('ClientPortalLayout notification bell', () => {
  beforeEach(() => {
    const { default: api } = require('../api/client');
    api.get.mockResolvedValue({ data: { has_avatar: false } });
    clientAPI.getDashboard.mockResolvedValue({ data: { client: { customer_reference: 'CRN-1' } } });
    clientAPI.getPortalContext.mockResolvedValue({ data: { server_time: '2026-01-01T00:00:00Z' } });
  });

  it('shows the unread item when count is 1', async () => {
    clientAPI.getInAppNotifications.mockResolvedValue({
      data: { items: [{ notification_id: 'N1', title: 'Action needed', is_read: false }] },
    });
    clientAPI.getInAppNotificationsUnreadCount.mockResolvedValue({ data: { unread_count: 1 } });
    render(
      <ClientPortalLayout>
        <div>child</div>
      </ClientPortalLayout>,
    );
    await waitFor(() => expect(screen.getByLabelText('1 unread')).toBeInTheDocument());
    await openBell();
    expect(await screen.findByText('Action needed')).toBeInTheDocument();
    expect(screen.queryByText('No notifications yet.')).not.toBeInTheDocument();
  });

  it('shows empty copy only when count is 0 and list is empty', async () => {
    clientAPI.getInAppNotifications.mockResolvedValue({ data: { items: [] } });
    clientAPI.getInAppNotificationsUnreadCount.mockResolvedValue({ data: { unread_count: 0 } });
    render(
      <ClientPortalLayout>
        <div>child</div>
      </ClientPortalLayout>,
    );
    await openBell();
    expect(await screen.findByText('No notifications yet.')).toBeInTheDocument();
  });

  it('does not treat list API failure as an empty inbox', async () => {
    clientAPI.getInAppNotifications.mockRejectedValue(new Error('network'));
    clientAPI.getInAppNotificationsUnreadCount.mockResolvedValue({ data: { unread_count: 1 } });
    render(
      <ClientPortalLayout>
        <div>child</div>
      </ClientPortalLayout>,
    );
    await waitFor(() => expect(screen.getByLabelText('1 unread')).toBeInTheDocument());
    await openBell();
    expect(await screen.findByText(/couldn't load notifications/i)).toBeInTheDocument();
    expect(screen.queryByText('No notifications yet.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('does not show empty copy when count is 1 and list is empty', async () => {
    clientAPI.getInAppNotifications.mockResolvedValue({ data: { items: [] } });
    clientAPI.getInAppNotificationsUnreadCount.mockResolvedValue({ data: { unread_count: 1 } });
    render(
      <ClientPortalLayout>
        <div>child</div>
      </ClientPortalLayout>,
    );
    await waitFor(() => expect(screen.getByLabelText('1 unread')).toBeInTheDocument());
    await openBell();
    expect(await screen.findByText(/not shown here/i)).toBeInTheDocument();
    expect(screen.queryByText('No notifications yet.')).not.toBeInTheDocument();
  });
});
