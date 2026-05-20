import React from 'react';
import { render, screen } from '@testing-library/react';
import AdminClientControlPanelPage from './AdminClientControlPanelPage';
import { adminAPI } from '../api/client';

jest.mock('../components/admin/UnifiedAdminLayout', () => ({ children }) => <div>{children}</div>);
jest.mock('../components/admin/AccountEnvironmentBadge', () => () => null);
jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { portal_user_id: 'admin-1' },
    isAdmin: () => true,
    isOwner: () => false,
  }),
}));
jest.mock('../hooks/useStepUpApi', () => ({ useStepUpApi: () => ({ request: (fn) => fn({}), modal: null }) }));
jest.mock('@/utils/portalNotifications', () => ({ toast: { error: jest.fn(), success: jest.fn(), info: jest.fn() } }));

jest.mock('../components/admin/pilot/ClientPromoRecoveryControls', () => ({
  __esModule: true,
  default: ({ clientId }) => (
    <div data-testid="client-promo-recovery-controls">Promo &amp; Recovery Controls for {clientId}</div>
  ),
}));

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ clientId: 'intake-client-1' }),
    Link: ({ children }) => <span>{children}</span>,
  };
});

describe('AdminClientControlPanelPage promo recovery', () => {
  beforeEach(() => {
    jest.spyOn(adminAPI, 'getClientCommandCentreTaskActivity').mockResolvedValue({ data: { items: [] } });
    jest.spyOn(adminAPI, 'getClientAgreementsSummary').mockResolvedValue({ data: null });
    jest.spyOn(adminAPI, 'getClientControlPanel').mockResolvedValue({
      data: {
        identity: {
          client_id: 'intake-client-1',
          email: 'stranded@example.com',
          status: 'INTAKE_PENDING',
        },
        account_state: { onboarding_stage: 'INTAKE_PENDING' },
        subscription_billing: { receipts: [], receipts_meta: { total: 0 } },
        compliance_overview: {},
        operations: {},
        activity_timeline: { payments: [], login_events: [], system_actions: [] },
        operational_snapshot: { onboarding_checklist: { onboarding_status: 'INTAKE_PENDING' } },
      },
    });
  });

  it('renders Promo & Recovery Controls on overview for admin', async () => {
    render(<AdminClientControlPanelPage />);
    expect(await screen.findByTestId('client-promo-recovery-controls')).toBeInTheDocument();
    expect(screen.getByText(/Promo & Recovery Controls for intake-client-1/)).toBeInTheDocument();
  });
});
