import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AdminComplianceRegistryPublishQueuePage from './AdminComplianceRegistryPublishQueuePage';
import { adminAPI } from '../../api/client';

jest.mock('../../components/admin/UnifiedAdminLayout', () => ({
  __esModule: true,
  default: ({ children }) => <div>{children}</div>,
}));

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isOwner: () => true,
    isAdmin: () => true,
    isSupport: () => true,
  }),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

jest.mock('../../api/client', () => ({
  adminAPI: {
    listComplianceRegistryPublishQueue: jest.fn(),
    getComplianceRegistryPublishedActive: jest.fn(),
    listComplianceRegistryPublishedHistory: jest.fn(),
    getComplianceRegistryPublishImpact: jest.fn(),
    getComplianceRegistryPublishQueueReview: jest.fn(),
    approveComplianceRegistryPublishQueue: jest.fn(),
    rejectComplianceRegistryPublishQueue: jest.fn(),
    submitComplianceRegistryPublishQueue: jest.fn(),
    publishComplianceRegistryPublishQueue: jest.fn(),
    createComplianceRegistryPublishQueue: jest.fn(),
    syncPropertyRequirementsFromRegistry: jest.fn(),
    revertComplianceRegistryPublishedToVersion: jest.fn(),
  },
}));

describe('AdminComplianceRegistryPublishQueuePage governance flow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    adminAPI.listComplianceRegistryPublishQueue.mockResolvedValue({
      data: {
        items: [
          {
            queue_id: 'q-1',
            status: 'submitted',
            title: 'Queue A',
            draft_entry_ids: ['d-1'],
          },
        ],
      },
    });
    adminAPI.getComplianceRegistryPublishedActive.mockResolvedValue({ data: { active: true, version: 1, entry_count: 2 } });
    adminAPI.listComplianceRegistryPublishedHistory.mockResolvedValue({ data: { items: [] } });
    adminAPI.getComplianceRegistryPublishImpact.mockResolvedValue({
      data: { impact: { draft_count: 1, per_draft: [], display_regions_union: [] }, rematerialisation: { detail: 'x' } },
    });
    adminAPI.getComplianceRegistryPublishQueueReview.mockResolvedValue({
      data: {
        review_ack_token: 'tok-1',
        touched_entries: [
          {
            entry_key: 'GAS_SAFETY|DEFAULT',
            conditions_summary: 'All properties',
            field_diff_vs_current_live: [{ path: 'why_it_matters_short', current: 'a', proposed: 'b' }],
            client_preview_by_jurisdiction: {
              ENGLAND: {
                requirement_card: { name: 'Gas Safety' },
                why_it_matters_short: 'short',
                why_it_matters_long: 'long',
                cta: { primary_action_mode: 'upload_document', cta_label_override: 'Upload' },
                action_links: [{ key: 'x' }],
              },
            },
          },
        ],
        warnings: [],
        current_live_published: { version: 1, entry_count: 2 },
        proposed_published_after_approval: { entry_count: 2 },
        rematerialisation: { detail: 'sync needed' },
      },
    });
    adminAPI.approveComplianceRegistryPublishQueue.mockResolvedValue({ data: {} });
    adminAPI.rejectComplianceRegistryPublishQueue.mockResolvedValue({ data: {} });
  });

  it('requires preview before approve and sends review_ack_token', async () => {
    render(<AdminComplianceRegistryPublishQueuePage />);
    await waitFor(() => expect(screen.getByText('Queue A')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    expect(adminAPI.approveComplianceRegistryPublishQueue).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'View / Preview' }));
    await waitFor(() => expect(adminAPI.getComplianceRegistryPublishQueueReview).toHaveBeenCalledWith('q-1'));

    fireEvent.click(screen.getByRole('button', { name: 'Approve from reviewed preview' }));
    await waitFor(() =>
      expect(adminAPI.approveComplianceRegistryPublishQueue).toHaveBeenCalledWith('q-1', { review_ack_token: 'tok-1' }),
    );
  });

  it('reject requires reason and submits reason when provided', async () => {
    render(<AdminComplianceRegistryPublishQueuePage />);
    await waitFor(() => expect(screen.getByText('Queue A')).toBeInTheDocument());

    const promptSpy = jest.spyOn(window, 'prompt').mockReturnValueOnce('   ');
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));
    expect(adminAPI.rejectComplianceRegistryPublishQueue).not.toHaveBeenCalled();

    promptSpy.mockReturnValueOnce('needs legal review');
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));
    await waitFor(() =>
      expect(adminAPI.rejectComplianceRegistryPublishQueue).toHaveBeenCalledWith('q-1', { reason: 'needs legal review' }),
    );
    promptSpy.mockRestore();
  });
});

