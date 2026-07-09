/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ClientIssuesPage from './ClientIssuesPage';
import { clientAPI } from '../api/client';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
  useNavigate: () => jest.fn(),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock('../utils/operationalCapabilityAccess', () => ({
  useOperationalExecutionCapabilities: () => ({
    canUseOpsMaintenance: true,
    canWriteOpsMaintenance: true,
    canUseOpsContractors: true,
    canWriteOpsContractors: true,
    canUseOpsPredictive: true,
    canWriteOpsPredictive: true,
    canUseOpsApprovals: true,
    canWriteOpsApprovals: true,
  }),
}));

jest.mock('../utils/CapabilityProtectedRoute', () => ({
  OperationalCapabilityProtectedRoute: ({ children }) => children,
}));

jest.mock('../components/client/ContractorNetworkLockedModal', () => ({
  ContractorNetworkLockedModal: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'contractor-network-locked-modal' });
  },
}));

jest.mock('../components/client/PlanRestrictedActionModal', () => ({
  PlanRestrictedJobModal: () => null,
  openPlanRestrictedJobGate: jest.fn(),
}));

jest.mock('../api/client', () => ({
  __esModule: true,
  clientAPI: {
    getMaintenanceIssues: jest.fn(),
    getProperties: jest.fn(),
    getMaintenanceIssue: jest.fn(),
  },
}));

describe('ClientIssuesPage initial render', () => {
  beforeEach(() => {
    clientAPI.getMaintenanceIssues.mockResolvedValue({
      data: { issues: [], total: 0 },
    });
    clientAPI.getProperties.mockResolvedValue({ data: { properties: [] } });
  });

  it('renders without ReferenceError and mounts contractor lock modal wiring', async () => {
    render(
      <MemoryRouter>
        <ClientIssuesPage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { name: /Issues/i })).toBeInTheDocument();
    expect(screen.getByTestId('contractor-network-locked-modal')).toBeInTheDocument();
  });
});
