import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AdminWorkOrderDetailPage from './AdminWorkOrderDetailPage';
import { adminAPI } from '../../api/client';
import { toast } from '@/utils/portalNotifications';

jest.mock('../../components/admin/UnifiedAdminLayout', () => ({ children }) => <div>{children}</div>);
jest.mock('@/utils/portalNotifications', () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ workOrderId: 'wo-1' }),
    useNavigate: () => jest.fn(),
    Link: ({ children }) => <span>{children}</span>,
  };
});

describe('AdminWorkOrderDetailPage operational controls', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    jest.spyOn(adminAPI, 'getRecommendContractors').mockResolvedValue({ data: { contractors: [] } });
    jest.spyOn(adminAPI, 'getContractors').mockResolvedValue({ data: { contractors: [] } });
    jest.spyOn(adminAPI, 'getClients').mockResolvedValue({ data: { clients: [] } });
  });

  it('requires no-access reason and submits canonical action', async () => {
    jest.spyOn(adminAPI, 'getWorkOrder').mockResolvedValue({
      data: {
        work_order_id: 'wo-1',
        work_order_kind: 'MAINTENANCE',
        status: 'IN_PROGRESS',
        evidence_keys: [],
      },
    });
    jest.spyOn(adminAPI, 'adminWorkOrderMarkNoAccess').mockResolvedValue({ data: {} });
    render(<AdminWorkOrderDetailPage />);
    const btn = await screen.findByRole('button', { name: /Mark no access/i });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText(/Reason\/note \(required\)/i), { target: { value: 'Tenant not present' } });
    fireEvent.click(btn);
    await waitFor(() =>
      expect(adminAPI.adminWorkOrderMarkNoAccess).toHaveBeenCalledWith('wo-1', { reason: 'Tenant not present' })
    );
  });

  it('shows disabled-state explanations for unsupported verify/close states', async () => {
    jest.spyOn(adminAPI, 'getWorkOrder').mockResolvedValue({
      data: {
        work_order_id: 'wo-1',
        work_order_kind: 'MAINTENANCE',
        status: 'OPEN',
        evidence_keys: [],
      },
    });
    render(<AdminWorkOrderDetailPage />);
    expect(await screen.findByText('Verify is for compliance jobs only.')).toBeInTheDocument();
    expect(screen.getByText('Close allowed only from COMPLETED or VERIFIED states.')).toBeInTheDocument();
  });

  it('runs verify for compliance jobs and surfaces failure', async () => {
    jest.spyOn(adminAPI, 'getWorkOrder').mockResolvedValue({
      data: {
        work_order_id: 'wo-1',
        work_order_kind: 'COMPLIANCE',
        status: 'COMPLETED',
        evidence_keys: ['document:doc-1'],
      },
    });
    jest.spyOn(adminAPI, 'adminWorkOrderVerify').mockRejectedValue({ response: { data: { detail: 'blocked' } } });
    render(<AdminWorkOrderDetailPage />);
    const btn = await screen.findByRole('button', { name: /Verify job/i });
    fireEvent.click(btn);
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('blocked'));
  });

  it('submits reschedule request with reason only (API contract)', async () => {
    jest.spyOn(adminAPI, 'getWorkOrder').mockResolvedValue({
      data: {
        work_order_id: 'wo-1',
        work_order_kind: 'MAINTENANCE',
        status: 'SCHEDULED',
        evidence_keys: [],
        scheduled_at: '2026-01-01T10:00:00Z',
        schedule_status: 'CONFIRMED',
      },
    });
    jest.spyOn(adminAPI, 'adminWorkOrderRescheduleRequest').mockResolvedValue({ data: {} });
    render(<AdminWorkOrderDetailPage />);
    await screen.findByText(/This records a reschedule request/i);
    fireEvent.change(screen.getByPlaceholderText(/Reason for reschedule request \(required\)/i), {
      target: { value: 'Tenant asked to move visit' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Optional: preferred date/i), {
      target: { value: 'Next Tuesday AM' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Request reschedule/i }));
    await waitFor(() =>
      expect(adminAPI.adminWorkOrderRescheduleRequest).toHaveBeenCalledWith('wo-1', {
        reason: 'Tenant asked to move visit\n\nPreferred window: Next Tuesday AM',
      }),
    );
  });

  it('status override prompts for reason and sends action_reason', async () => {
    jest.spyOn(window, 'confirm').mockReturnValue(true);
    jest.spyOn(window, 'prompt').mockReturnValue('Ops override: unblock billing');
    jest.spyOn(adminAPI, 'getWorkOrder').mockResolvedValue({
      data: {
        work_order_id: 'wo-1',
        work_order_kind: 'MAINTENANCE',
        status: 'IN_PROGRESS',
        evidence_keys: [],
      },
    });
    jest.spyOn(adminAPI, 'updateWorkOrder').mockResolvedValue({ data: {} });
    render(<AdminWorkOrderDetailPage />);
    await screen.findByText(/Override — persisted status/i);
    const selects = screen.getAllByRole('combobox');
    const statusSelect = selects.find((el) => el.value === 'IN_PROGRESS');
    expect(statusSelect).toBeTruthy();
    fireEvent.change(statusSelect, { target: { value: 'COMPLETED' } });
    await waitFor(() =>
      expect(adminAPI.updateWorkOrder).toHaveBeenCalledWith('wo-1', {
        status: 'COMPLETED',
        action_reason: 'Ops override: unblock billing',
      }),
    );
  });
});

