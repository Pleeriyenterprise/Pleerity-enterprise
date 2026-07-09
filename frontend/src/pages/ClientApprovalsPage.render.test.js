/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ClientApprovalsPage from './ClientApprovalsPage';
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
    canUseOpsApprovals: true,
    canWriteOpsApprovals: true,
  }),
}));

jest.mock('../utils/CapabilityProtectedRoute', () => ({
  OperationalCapabilityProtectedRoute: ({ children }) => children,
}));

jest.mock('../hooks/useStepUpApi', () => ({
  useStepUpApi: () => ({
    request: (fn) => fn({}),
    modal: null,
  }),
}));

jest.mock('../api/client', () => ({
  __esModule: true,
  clientAPI: {
    getApprovals: jest.fn(),
    getProperties: jest.fn(),
    getContractors: jest.fn(),
    getApproval: jest.fn(),
  },
}));

describe('ClientApprovalsPage initial render', () => {
  beforeEach(() => {
    clientAPI.getApprovals.mockResolvedValue({
      data: { summary: {}, approvals: [], exceptions: [] },
    });
    clientAPI.getProperties.mockResolvedValue({ data: { properties: [] } });
    clientAPI.getContractors.mockResolvedValue({ data: { contractors: [] } });
  });

  it('renders without ReferenceError and mounts step-up modal wiring', async () => {
    render(
      <MemoryRouter>
        <ClientApprovalsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { name: /Approvals/i })).toBeInTheDocument();
    expect(screen.getByText(/Payment responsibility/i)).toBeInTheDocument();
  });
});
