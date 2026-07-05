import React from 'react';
import { render, screen, within } from '@testing-library/react';
import ClientPortalLayout from './ClientPortalLayout';

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
    getInAppNotifications: jest.fn(() => Promise.resolve({ data: { items: [] } })),
    getInAppNotificationsUnreadCount: jest.fn(() => Promise.resolve({ data: { unread_count: 0 } })),
    getPortalContext: jest.fn(() => Promise.resolve({ data: { server_time: '2026-01-01T00:00:00Z' } })),
    getDashboard: jest.fn(() => Promise.resolve({ data: { client: { customer_reference: 'CRN-1' } } })),
  },
}));

describe('ClientPortalLayout hierarchy navigation', () => {
  beforeEach(() => {
    const { default: api, clientAPI } = require('../api/client');
    api.get.mockResolvedValue({ data: { has_avatar: false } });
    clientAPI.getDashboard.mockResolvedValue({ data: { client: { customer_reference: 'CRN-1' } } });
    clientAPI.getPortalContext.mockResolvedValue({ data: { server_time: '2026-01-01T00:00:00Z' } });
    clientAPI.getInAppNotifications.mockResolvedValue({ data: { items: [] } });
    clientAPI.getInAppNotificationsUnreadCount.mockResolvedValue({ data: { unread_count: 0 } });
  });

  it('renders desktop primary tabs without horizontal overflow classes', async () => {
    render(
      <ClientPortalLayout>
        <div>child</div>
      </ClientPortalLayout>,
    );

    const desktopNav = await screen.findByTestId('portal-desktop-nav');
    expect(desktopNav.className).not.toMatch(/overflow-x-auto/);
    expect(desktopNav.className).toMatch(/overflow-visible/);

    const desktop = within(desktopNav);
    expect(desktop.getByRole('link', { name: /Today/i })).toBeInTheDocument();
    expect(desktop.getByRole('link', { name: /Command center/i })).toBeInTheDocument();
    expect(desktop.getByRole('link', { name: /Requirements/i })).toBeInTheDocument();
    expect(desktop.getByRole('button', { name: /Operations/i })).toBeInTheDocument();
    expect(desktop.getByRole('button', { name: /^More$/i })).toBeInTheDocument();
    expect(desktop.queryByRole('link', { name: /^Calendar$/i })).not.toBeInTheDocument();
  });

  it('exposes grouped secondary items in More menu with keyboard attributes', async () => {
    render(
      <ClientPortalLayout>
        <div>child</div>
      </ClientPortalLayout>,
    );

    const desktopNav = await screen.findByTestId('portal-desktop-nav');
    const moreTrigger = within(desktopNav).getByRole('button', { name: /^More$/i });
    expect(moreTrigger).toHaveAttribute('aria-haspopup', 'menu');
    expect(moreTrigger).toHaveAttribute('aria-expanded', 'false');

    const menu = document.getElementById('portal-more-menu');
    expect(menu).toHaveAttribute('role', 'menu');
    expect(within(menu).getByRole('menuitem', { name: /Calendar/i })).toBeInTheDocument();
    expect(within(menu).getByRole('menuitem', { name: /Settings/i })).toBeInTheDocument();
  });

  it('renders mobile sectioned navigation', async () => {
    render(
      <ClientPortalLayout>
        <div>child</div>
      </ClientPortalLayout>,
    );

    const mobileNav = await screen.findByTestId('portal-mobile-nav');
    expect(within(mobileNav).getByText('Operations')).toBeInTheDocument();
    expect(within(mobileNav).getByText('More')).toBeInTheDocument();
    expect(within(mobileNav).getByRole('link', { name: /Today/i })).toBeInTheDocument();
  });
});
