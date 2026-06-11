/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ManualJobExecutionModal from './ManualJobExecutionModal';
import { adminAPI } from '../../api/client';

jest.mock('../../api/client', () => ({
  adminAPI: {
    getJobExecutionGovernance: jest.fn(),
    getClients: jest.fn(),
    previewJobExecution: jest.fn(),
    runJobNow: jest.fn(),
    issueConfirmationToken: jest.fn(),
  },
}));

jest.mock('../../utils/adminGovernedMutation', () => ({
  runGovernedAdminMutation: jest.fn(({ mutate }) => mutate({})),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

describe('ManualJobExecutionModal', () => {
  beforeEach(() => {
    adminAPI.getJobExecutionGovernance.mockResolvedValue({
      data: {
        job_id: 'monthly_digest',
        allowed_scopes: ['CLIENT', 'PORTFOLIO_WIDE'],
        accepts_property_ids_filter: true,
        plan_options: [],
        cohort_filter_options: [],
      },
    });
    adminAPI.getClients.mockResolvedValue({
      data: { clients: [{ client_id: 'c1', company_name: 'Acme' }] },
    });
    adminAPI.previewJobExecution.mockResolvedValue({
      data: {
        ok: true,
        estimates: { summary_lines: ['1 client(s) affected'] },
      },
    });
  });

  it('blocks portfolio-wide without confirmation checkbox', async () => {
    render(<ManualJobExecutionModal jobId="monthly_digest" onClose={jest.fn()} />);
    await screen.findByTestId('job-exec-step-scope');
    fireEvent.click(screen.getByTestId('scope-PORTFOLIO_WIDE'));
    fireEvent.click(screen.getByTestId('job-exec-next'));
    fireEvent.click(screen.getByTestId('job-exec-next'));
    expect(screen.getByText(/confirm portfolio-wide/i)).toBeInTheDocument();
  });

  it('walks client scope through to confirm step', async () => {
    render(<ManualJobExecutionModal jobId="monthly_digest" onClose={jest.fn()} />);
    await screen.findByTestId('job-exec-step-scope');
    fireEvent.click(screen.getByTestId('scope-CLIENT'));
    fireEvent.click(screen.getByTestId('job-exec-next'));
    fireEvent.change(screen.getByTestId('job-exec-client-select'), { target: { value: 'c1' } });
    fireEvent.click(screen.getByTestId('job-exec-next'));
    await waitFor(() => expect(adminAPI.previewJobExecution).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId('job-exec-next'));
    expect(screen.getByTestId('job-exec-step-confirm')).toBeInTheDocument();
  });
});
