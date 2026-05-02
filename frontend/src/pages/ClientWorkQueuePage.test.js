/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ClientWorkQueuePage, { workQueueRowToTask } from './ClientWorkQueuePage';
import { clientAPI } from '../api/client';
import * as ctaRegistry from '../utils/ctaRegistry';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

jest.mock('../api/client', () => ({
  clientAPI: {
    getWorkQueue: jest.fn(),
    getComplianceScore: jest.fn(),
  },
  parseApiError: (_e, d) => d || 'Error',
}));

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { role: 'ROLE_CLIENT_ADMIN', client_id: 'c1', email: 't@test.com' },
  }),
}));

const mockOpenGuidedEvidence = jest.fn();
jest.mock('../context/GuidedEvidenceModalContext', () => ({
  useGuidedEvidenceModal: () => ({
    openGuidedEvidence: (...args) => mockOpenGuidedEvidence(...args),
  }),
}));

describe('ClientWorkQueuePage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockOpenGuidedEvidence.mockClear();
    clientAPI.getComplianceScore.mockResolvedValue({
      data: { score_status: 'ok', score_status_message: null },
    });
  });

  it('does not show portfolio headline strips when score_status is healthy', async () => {
    clientAPI.getWorkQueue.mockResolvedValue({ data: { items: [], summary: { count: 0 } } });
    render(
      <MemoryRouter>
        <ClientWorkQueuePage />
      </MemoryRouter>,
    );
    await screen.findByTestId('work-queue-empty');
    expect(screen.queryByTestId('work-queue-headline-score-processing')).not.toBeInTheDocument();
    expect(screen.queryByTestId('work-queue-headline-score-degraded')).not.toBeInTheDocument();
    expect(screen.queryByTestId('work-queue-headline-score-error')).not.toBeInTheDocument();
  });

  it('renders empty state when API returns no items', async () => {
    clientAPI.getWorkQueue.mockResolvedValue({ data: { items: [], summary: { count: 0 } } });
    render(
      <MemoryRouter>
        <ClientWorkQueuePage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('work-queue-empty')).toBeInTheDocument();
  });

  it('renders row with urgency badge, title, closure line, and primary action', async () => {
    clientAPI.getWorkQueue.mockResolvedValue({
      data: {
        items: [
          {
            queue_item_id: 'requirement:r1',
            source_system: 'requirement',
            remediation_key: 'gk-1',
            property_id: 'p1',
            property_label: 'Laurel Gardens',
            title: 'Gas safety certificate',
            subtitle: 'Due soon',
            urgency_band: 'Urgent',
            primary_action: {
              type: 'review_requirement',
              label: 'View requirement',
              url: '/requirements?property_id=p1',
              inline_supported: false,
            },
            primary_action_authority: 'canonical_take_action',
            closure_summary_user: 'Follow up on this obligation in your compliance view.',
            related_ids: { requirement_id: 'r1', gap_key: 'gk-1' },
            created_at: null,
            updated_at: null,
          },
        ],
        summary: { count: 1 },
      },
    });
    render(
      <MemoryRouter>
        <ClientWorkQueuePage />
      </MemoryRouter>,
    );
    const row = await screen.findByTestId('work-queue-row-requirement:r1');
    expect(row).toBeInTheDocument();
    expect(screen.getByTestId('work-queue-urgency-badge')).toHaveTextContent('Urgent');
    expect(screen.getByTestId('work-queue-closure-line')).toHaveTextContent(
      'Follow up on this obligation in your compliance view.',
    );
    expect(screen.getByTestId('work-queue-primary-action')).toHaveTextContent('View requirement');
  });

  it('primary action uses resolveTaskCta with a unified-task-shaped row', async () => {
    const row = {
      queue_item_id: 'requirement:r1',
      source_system: 'requirement',
      remediation_key: 'gk-1',
      property_id: 'p1',
      property_label: 'Laurel Gardens',
      title: 'Gas safety certificate',
      subtitle: 'Due soon',
      urgency_band: 'Urgent',
      primary_action: {
        type: 'review_requirement',
        label: 'View requirement',
        url: '/requirements?property_id=p1',
        inline_supported: false,
      },
      primary_action_authority: 'canonical_take_action',
      closure_summary_user: 'Follow up on this obligation in your compliance view.',
      related_ids: { requirement_id: 'r1', gap_key: 'gk-1' },
      created_at: null,
      updated_at: null,
    };
    clientAPI.getWorkQueue.mockResolvedValue({
      data: {
        items: [row],
        summary: { count: 1 },
      },
    });
    const spy = jest.spyOn(ctaRegistry, 'resolveTaskCta');
    render(
      <MemoryRouter>
        <ClientWorkQueuePage />
      </MemoryRouter>,
    );
    const btn = await screen.findByTestId('work-queue-primary-action');
    fireEvent.click(btn);
    await waitFor(() => {
      expect(spy).toHaveBeenCalled();
    });
    const shaped = workQueueRowToTask(row);
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({
        id: shaped.id,
        source_type: shaped.source_type,
        primary_action_url: shaped.primary_action_url,
        metadata: expect.objectContaining({
          requirement_id: 'r1',
          gap_key: 'gk-1',
        }),
      }),
      'primary',
    );
    spy.mockRestore();
  });

  it('shows processing headline when score is calculating and clears it after headline refetch resolves to ok', async () => {
    clientAPI.getWorkQueue.mockResolvedValue({ data: { items: [], summary: { count: 0 } } });
    clientAPI.getComplianceScore
      .mockResolvedValueOnce({
        data: { score_status: 'calculating', score_status_message: null },
      })
      .mockResolvedValue({
        data: { score_status: 'ok', score_status_message: null },
      });
    render(
      <MemoryRouter>
        <ClientWorkQueuePage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('work-queue-headline-score-processing')).toBeInTheDocument();
    fireEvent(document, new Event('visibilitychange'));
    await waitFor(() => {
      expect(screen.queryByTestId('work-queue-headline-score-processing')).not.toBeInTheDocument();
    });
  });

  it('uses degraded styling for unavailable score_status, not processing', async () => {
    clientAPI.getWorkQueue.mockResolvedValue({ data: { items: [], summary: { count: 0 } } });
    clientAPI.getComplianceScore.mockResolvedValue({
      data: { score_status: 'unavailable', score_status_message: null },
    });
    render(
      <MemoryRouter>
        <ClientWorkQueuePage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('work-queue-headline-score-degraded')).toBeInTheDocument();
    expect(screen.queryByTestId('work-queue-headline-score-processing')).not.toBeInTheDocument();
  });

  it('shows load-failed headline when compliance score request fails', async () => {
    clientAPI.getWorkQueue.mockResolvedValue({ data: { items: [], summary: { count: 0 } } });
    clientAPI.getComplianceScore.mockRejectedValue(new Error('network'));
    render(
      <MemoryRouter>
        <ClientWorkQueuePage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('work-queue-headline-score-error')).toBeInTheDocument();
    expect(screen.queryByTestId('work-queue-headline-score-processing')).not.toBeInTheDocument();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });
});

describe('workQueueRowToTask', () => {
  it('maps UCWQ row to unified-task shape for ctaRegistry', () => {
    const task = workQueueRowToTask({
      queue_item_id: 'q1',
      source_system: 'requirement',
      primary_action: {
        type: 'upload_evidence',
        label: 'Upload',
        url: '/documents',
        take_action: { primary: { kind: 'direct_evidence_action' } },
      },
      related_ids: { requirement_id: 'r1' },
    });
    expect(task.id).toBe('q1');
    expect(task.metadata.take_action).toEqual({ primary: { kind: 'direct_evidence_action' } });
    expect(task.metadata.requirement_id).toBe('r1');
  });
});
