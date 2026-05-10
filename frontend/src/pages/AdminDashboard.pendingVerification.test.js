import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DashboardOverview } from './AdminDashboard';

jest.mock('../api/client', () => {
  const apiGet = jest.fn();
  return {
    __esModule: true,
    default: { get: apiGet },
    adminAPI: {
      globalSearch: jest.fn().mockResolvedValue({ data: { results: [] } }),
      getClients: jest.fn(),
      getPriorityActions: jest.fn(),
      getPendingVerificationDocuments: jest.fn(),
      verifyDocument: jest.fn(),
      getDocumentAiAssistance: jest.fn(),
      getDocumentVerificationHelpers: jest.fn(),
      recordDocumentExternalVerification: jest.fn(),
      applyDocumentAiFieldAction: jest.fn(),
      resolveEvidenceMatch: jest.fn(),
      backfillEvidenceMatch: jest.fn(),
    },
    parseApiError: jest.fn((e, fallback) => fallback || 'error'),
    parseStructuredApiDetail: jest.fn(() => ({})),
  };
});

jest.mock('@/utils/portalNotifications', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

describe('AdminDashboard pending verification queue', () => {
  it('renders V2 review state, assurance, and validation warning/failure counts', async () => {
    const clientModule = await import('../api/client');
    const api = clientModule.default;
    const { adminAPI } = clientModule;

    api.get.mockResolvedValue({
      data: {
        stats: {
          total_clients: 1,
          total_properties: 1,
          active_clients: 1,
          pending_clients: 0,
          unverified_documents_count: 1,
        },
        compliance_overview: { GREEN: 0, AMBER: 0, RED: 0 },
        recent_activity: [],
        server_feature_flags: { evidence_review_v2_enabled: false },
      },
    });
    adminAPI.getClients.mockResolvedValue({ data: { clients: [] } });
    adminAPI.getPriorityActions.mockResolvedValue({ data: { actions: [], total: 0 } });
    adminAPI.getPendingVerificationDocuments.mockResolvedValue({
      data: {
        documents: [
          {
            document_id: 'doc-v2-1',
            client_id: 'client-1',
            property_id: 'prop-1',
            requirement_id: 'req-1',
            client_name: 'Client One',
            crn: 'CRN-1',
            uploaded_at: '2026-04-28T06:00:00Z',
            evidence_review_state: 'ACCEPTED_UNVERIFIED',
            assurance_tier: 'HUMAN_ACCEPTED',
            latest_validation_snapshot: {
              validation_status: 'WARN',
              warnings: ['MISSING_EXPIRY_DATE'],
              failures: ['PROPERTY_ADDRESS_MISMATCH'],
            },
            ai_assistance: {
              extraction_warnings: ['LOW_EXTRACTION_CONFIDENCE'],
              ai_flags: ['POSSIBLE_ADDRESS_MISMATCH'],
              anomaly_risk_score: 0.71,
            },
          },
        ],
        total: 1,
        returned: 1,
        has_more: false,
      },
    });

    render(
      <MemoryRouter>
        <DashboardOverview onShowDrilldown={() => {}} onSelectClient={() => {}} />
      </MemoryRouter>
    );

    await waitFor(() => expect(adminAPI.getPendingVerificationDocuments).toHaveBeenCalled());

    expect(screen.getByText('Accepted (unverified)')).toBeInTheDocument();
    expect(screen.getByText('Human accepted')).toBeInTheDocument();
    expect(screen.getByText('WARN · 1 warning(s), 1 failure(s)')).toBeInTheDocument();
    expect(screen.getByText('1 warning(s), 1 flag(s)')).toBeInTheDocument();
    expect(screen.getByText('High (0.71)')).toBeInTheDocument();
    expect(screen.getByTestId('evidence-review-v2-disabled-hint')).toBeInTheDocument();
    expect(screen.queryByTestId('ai-review-doc-doc-v2-1')).not.toBeInTheDocument();
  });

  it('requires override reason before AI field override action', async () => {
    const clientModule = await import('../api/client');
    const api = clientModule.default;
    const { adminAPI } = clientModule;

    api.get.mockResolvedValue({
      data: {
        stats: {
          total_clients: 1,
          total_properties: 1,
          active_clients: 1,
          pending_clients: 0,
          unverified_documents_count: 1,
        },
        compliance_overview: { GREEN: 0, AMBER: 0, RED: 0 },
        recent_activity: [],
        server_feature_flags: { evidence_review_v2_enabled: true },
      },
    });
    adminAPI.getClients.mockResolvedValue({ data: { clients: [] } });
    adminAPI.getPriorityActions.mockResolvedValue({ data: { actions: [], total: 0 } });
    adminAPI.getPendingVerificationDocuments.mockResolvedValue({
      data: {
        documents: [{ document_id: 'doc-v2-1', client_id: 'c1', property_id: 'p1', requirement_id: 'r1', uploaded_at: '2026-04-28T06:00:00Z' }],
        total: 1, returned: 1, has_more: false,
      },
    });
    adminAPI.getDocumentAiAssistance.mockResolvedValue({
      data: {
        ai_assistance: {
          extracted_fields: { certificate_number: 'CERT-1' },
          original_extracted_fields: { certificate_number: 'CERT-1' },
          field_reviews: {},
          anomaly_flags: [],
        },
      },
    });
    adminAPI.getDocumentVerificationHelpers.mockResolvedValue({
      data: { helpers: [] },
    });

    render(
      <MemoryRouter>
        <DashboardOverview onShowDrilldown={() => {}} onSelectClient={() => {}} />
      </MemoryRouter>
    );

    await waitFor(() => expect(adminAPI.getPendingVerificationDocuments).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId('ai-review-doc-doc-v2-1'));
    await waitFor(() => expect(adminAPI.getDocumentAiAssistance).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByPlaceholderText('Override value')).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText('Override value'), { target: { value: 'CERT-2' } });
    fireEvent.click(screen.getByText('Override'));
    expect(adminAPI.applyDocumentAiFieldAction).not.toHaveBeenCalled();
  });

  it('does not show irrelevant verification helper links for unsupported requirement types', async () => {
    const clientModule = await import('../api/client');
    const api = clientModule.default;
    const { adminAPI } = clientModule;

    api.get.mockResolvedValue({
      data: {
        stats: { total_clients: 1, total_properties: 1, active_clients: 1, pending_clients: 0, unverified_documents_count: 1 },
        compliance_overview: { GREEN: 0, AMBER: 0, RED: 0 },
        recent_activity: [],
        server_feature_flags: { evidence_review_v2_enabled: true },
      },
    });
    adminAPI.getClients.mockResolvedValue({ data: { clients: [] } });
    adminAPI.getPriorityActions.mockResolvedValue({ data: { actions: [], total: 0 } });
    adminAPI.getPendingVerificationDocuments.mockResolvedValue({
      data: { documents: [{ document_id: 'doc-v2-2', client_id: 'c1', uploaded_at: '2026-04-28T06:00:00Z' }], total: 1, returned: 1, has_more: false },
    });
    adminAPI.getDocumentAiAssistance.mockResolvedValue({ data: { ai_assistance: { extracted_fields: {}, original_extracted_fields: {}, field_reviews: {}, anomaly_flags: [] } } });
    adminAPI.getDocumentVerificationHelpers.mockResolvedValue({ data: { helpers: [] } });

    render(
      <MemoryRouter>
        <DashboardOverview onShowDrilldown={() => {}} onSelectClient={() => {}} />
      </MemoryRouter>
    );

    await waitFor(() => expect(adminAPI.getPendingVerificationDocuments).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId('ai-review-doc-doc-v2-2'));
    await waitFor(() => expect(adminAPI.getDocumentVerificationHelpers).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId('external-verification-method')).toBeInTheDocument());
    expect(screen.getByText(/No external helper sources configured/i)).toBeInTheDocument();
    expect(screen.queryByText('Open official source')).not.toBeInTheDocument();
  });
});

