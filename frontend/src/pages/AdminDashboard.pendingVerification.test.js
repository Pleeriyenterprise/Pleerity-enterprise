import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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

const baseStats = {
  total_clients: 1,
  total_properties: 1,
  active_clients: 1,
  pending_clients: 0,
  unverified_documents_count: 1,
};

describe('AdminDashboard pending verification queue', () => {
  it('renders humanised review labels and does not leak raw enums in operational cells', async () => {
    const clientModule = await import('../api/client');
    const api = clientModule.default;
    const { adminAPI } = clientModule;

    api.get.mockResolvedValue({
      data: {
        stats: {
          ...baseStats,
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
            client_name: 'Felix Thompson',
            crn: 'PLC-CUP-2826-000042',
            file_name: 'right-to-rent.pdf',
            uploaded_at: '2026-04-28T06:00:00Z',
            match_outcome: 'MATCH_LIKELY',
            predicted_document_type: 'RIGHT_TO_RENT_EVIDENCE',
            match_confidence: 0.57,
            mismatch_reason_code: 'NO_REQUIREMENT_LINK',
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

    const { container } = render(
      <MemoryRouter>
        <DashboardOverview onShowDrilldown={() => {}} onSelectClient={() => {}} />
      </MemoryRouter>
    );

    await waitFor(() => expect(adminAPI.getPendingVerificationDocuments).toHaveBeenCalled());

    expect(screen.getByText('Accepted on file (not externally verified)')).toBeInTheDocument();
    expect(screen.getByText('Human accepted')).toBeInTheDocument();
    expect(screen.getByText(/Likely match found/)).toBeInTheDocument();
    expect(screen.getByText(/57% confidence/)).toBeInTheDocument();
    expect(screen.getByText('Low confidence')).toBeInTheDocument();
    expect(screen.getByText(/No matching requirement linked yet/)).toBeInTheDocument();
    expect(screen.getByText(/Warnings found/)).toBeInTheDocument();
    expect(screen.getByText(/High-risk anomaly detected/)).toBeInTheDocument();

    const row = screen.getByTestId('pending-verification-row-doc-v2-1');
    expect(row.textContent).not.toContain('MATCH_LIKELY');
    expect(row.textContent).not.toContain('RIGHT_TO_RENT_EVIDENCE');
    expect(row.textContent).not.toContain('NO_REQUIREMENT_LINK');

    fireEvent.click(screen.getByTestId('technical-details-doc-v2-1-toggle'));
    const panel = screen.getByTestId('technical-details-doc-v2-1-panel');
    expect(within(panel).getByText(/MATCH_LIKELY/)).toBeInTheDocument();
    expect(within(panel).getByText(/RIGHT_TO_RENT_EVIDENCE/)).toBeInTheDocument();

    expect(screen.getByTestId('evidence-review-v2-disabled-hint')).toBeInTheDocument();
    expect(screen.queryByTestId('ai-review-doc-doc-v2-1')).not.toBeInTheDocument();
    expect(container.querySelector('[colspan="19"]')).toBeNull();
  });

  it('requires override reason before AI field override action', async () => {
    const clientModule = await import('../api/client');
    const api = clientModule.default;
    const { adminAPI } = clientModule;

    api.get.mockResolvedValue({
      data: {
        stats: { ...baseStats },
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
        stats: { ...baseStats },
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
