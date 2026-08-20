/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ClientIssuesPage from './ClientIssuesPage';
import { clientAPI } from '../api/client';
import { useOperationalExecutionCapabilities } from '../utils/operationalCapabilityAccess';
import * as contractorNetworkEntitlement from '../utils/contractorNetworkEntitlement';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
  useNavigate: () => jest.fn(),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock('../utils/operationalCapabilityAccess', () => ({
  useOperationalExecutionCapabilities: jest.fn(),
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

const FULL_CAPABILITIES = {
  canUseOpsMaintenance: true,
  canWriteOpsMaintenance: true,
  canUseOpsContractors: true,
  canWriteOpsContractors: true,
  canUseOpsPredictive: true,
  canWriteOpsPredictive: true,
  canUseOpsApprovals: true,
  canWriteOpsApprovals: true,
};

function assignableIssue(overrides = {}) {
  return {
    issue_id: 'iss-assign-1',
    status: 'ready_for_work_order',
    linked_work_order_id: 'wo-1',
    description: 'Bathroom sink leak',
    property_id: 'prop-oak',
    category: 'plumbing',
    severity: 'medium',
    created_at: '2026-08-20T10:00:00Z',
    ...overrides,
  };
}

describe('ClientIssuesPage initial render', () => {
  beforeEach(() => {
    useOperationalExecutionCapabilities.mockReturnValue(FULL_CAPABILITIES);
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

  it('renders assignable issues without throwing and keeps assignment unlocked when entitled', async () => {
    const spy = jest.spyOn(contractorNetworkEntitlement, 'isIssueAssignContractorLocked');
    clientAPI.getMaintenanceIssues.mockResolvedValue({
      data: { issues: [assignableIssue()], total: 1 },
    });
    render(
      <MemoryRouter>
        <ClientIssuesPage />
      </MemoryRouter>,
    );
    expect(await screen.findAllByRole('button', { name: /Assign contractor/i })).not.toHaveLength(0);
    expect(screen.queryByTestId('issue-primary-assign-locked')).not.toBeInTheDocument();
    expect(spy).toHaveBeenCalled();
    const [primary, hasNetwork] = spy.mock.calls[0];
    expect(primary.key).toBe('assign_contractor');
    expect(hasNetwork).toBe(true);
    spy.mockRestore();
  });

  it('uses canonical lock helper and locked presentation when contractor network is not entitled', async () => {
    useOperationalExecutionCapabilities.mockReturnValue({
      ...FULL_CAPABILITIES,
      canUseOpsContractors: false,
      canWriteOpsContractors: false,
    });
    const spy = jest.spyOn(contractorNetworkEntitlement, 'isIssueAssignContractorLocked');
    clientAPI.getMaintenanceIssues.mockResolvedValue({
      data: { issues: [assignableIssue({ issue_id: 'iss-locked-1' })], total: 1 },
    });
    render(
      <MemoryRouter>
        <ClientIssuesPage />
      </MemoryRouter>,
    );
    expect(await screen.findAllByTestId('issue-primary-assign-locked')).not.toHaveLength(0);
    expect(spy).toHaveBeenCalled();
    expect(contractorNetworkEntitlement.isIssueAssignContractorLocked(spy.mock.calls[0][0], false)).toBe(true);
    spy.mockRestore();
  });
});
