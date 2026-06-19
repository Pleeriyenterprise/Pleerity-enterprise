import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AdminDiscoveryReviewPage from './AdminDiscoveryReviewPage';
import { discoveryApi } from '../../../api/discoveryApi';

jest.mock('../../../components/admin/UnifiedAdminLayout', () => ({ children }) => <div>{children}</div>);

jest.mock('../../../api/discoveryApi', () => ({
  discoveryApi: {
    getReviewQueue: jest.fn(),
    getReviewSummary: jest.fn(),
    getReviewDetail: jest.fn(),
    getAuditHistory: jest.fn(),
    approveProspect: jest.fn(),
    rejectProspect: jest.fn(),
    requestChanges: jest.fn(),
    markDuplicate: jest.fn(),
    clearDuplicate: jest.fn(),
    archiveProspect: jest.fn(),
  },
  isDiscoveryModuleEnabled: () => true,
}));

const queueItem = {
  prospect_id: 'prospect-1',
  company_name: 'Acme Ltd',
  contact_name: 'Jane',
  has_email: true,
  has_phone: false,
  provider: 'manual',
  campaign_id: 'camp-1',
  review_status: 'needs_review',
  duplicate_status: 'none',
  platform_quality_score: 82,
  review_priority: 70,
  created_at: '2026-06-18T14:00:00+00:00',
};

describe('AdminDiscoveryReviewPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    discoveryApi.getReviewQueue.mockResolvedValue({ data: { items: [queueItem], total: 1 } });
    discoveryApi.getReviewSummary.mockResolvedValue({
      data: { total_needs_review: 1, total_duplicates: 0, total_approved: 0, high_priority_count: 0 },
    });
    discoveryApi.getReviewDetail.mockResolvedValue({
      data: {
        prospect: { company_name: 'Acme Ltd', provider: 'manual' },
        review_status: 'needs_review',
        duplicate_status: 'none',
        platform_quality_score: 82,
        quality_breakdown: { total: 82 },
        quality_explanation: { breakdown_lines: ['Strong identity'] },
        origin_lineage: [],
        lawful_basis: 'consent',
        marketing_consent: false,
        import_readiness: { eligible: false },
        import_readiness_notice: 'Import readiness only. Import is not enabled in this stage.',
        audit_summary: { lines: ['Events: 0'] },
      },
    });
    discoveryApi.getAuditHistory.mockResolvedValue({ data: { items: [], summary: {} } });
  });

  it('renders page and queue table', async () => {
    render(<AdminDiscoveryReviewPage />);
    expect(await screen.findByText('Discovery Review')).toBeInTheDocument();
    expect(await screen.findByText('Acme Ltd')).toBeInTheDocument();
    expect(screen.getByText('Review queue')).toBeInTheDocument();
  });

  it('renders detail drawer after selecting a row', async () => {
    render(<AdminDiscoveryReviewPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Review/i }));
    await waitFor(() => expect(discoveryApi.getReviewDetail).toHaveBeenCalledWith('prospect-1'));
    expect(await screen.findByText('Prospect detail')).toBeInTheDocument();
    expect(screen.getByText(/Import readiness only/i)).toBeInTheDocument();
  });

  it('reject modal requires notes before confirm', async () => {
    render(<AdminDiscoveryReviewPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Review/i }));
    await waitFor(() => expect(discoveryApi.getReviewDetail).toHaveBeenCalledWith('prospect-1'));
    fireEvent.click(await screen.findByRole('button', { name: /Reject/i }));
    const confirm = await screen.findByRole('button', { name: /Confirm reject/i });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText(/Notes \(required\)/i), {
      target: { value: 'Not eligible' },
    });
    expect(confirm).toBeDisabled();
  });

  it('does not render an import button', async () => {
    render(<AdminDiscoveryReviewPage />);
    await screen.findByText('Discovery Review');
    expect(screen.queryByRole('button', { name: /import/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/^Import$/i)).not.toBeInTheDocument();
  });
});
