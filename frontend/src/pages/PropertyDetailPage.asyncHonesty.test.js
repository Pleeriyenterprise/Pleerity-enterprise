/**
 * @jest-environment jsdom
 */
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import PropertyDetailPage from './PropertyDetailPage';
import { clientAPI } from '../api/client';
import { PROPERTY_DETAIL_STORED_VS_PREVIEW_NOTE } from '../utils/scoreFreshnessUi';

const mockNavigate = jest.fn();
const mockOpenGuidedEvidence = jest.fn();
const mockHasFeature = jest.fn(() => false);

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ propertyId: 'prop-1' }),
    useNavigate: () => mockNavigate,
  };
});

jest.mock('../contexts/EntitlementsContext', () => ({
  useEntitlements: () => ({ hasFeature: mockHasFeature }),
}));

jest.mock('../context/GuidedEvidenceModalContext', () => ({
  useGuidedEvidenceModal: () => ({ openGuidedEvidence: mockOpenGuidedEvidence }),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

describe('PropertyDetailPage async honesty (stored vs preview)', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    mockNavigate.mockReset();
    mockOpenGuidedEvidence.mockReset();

    jest.spyOn(clientAPI, 'getProperties').mockResolvedValue({
      data: { properties: [{ property_id: 'prop-1', nickname: 'Prop 1', address_line_1: '1 Street' }] },
    });
    jest.spyOn(clientAPI, 'getMaintenanceWorkOrders').mockResolvedValue({ data: { jobs: [] } });
    jest.spyOn(clientAPI, 'getMaintenanceIssues').mockResolvedValue({ data: { issues: [] } });
    jest.spyOn(clientAPI, 'getPredictiveInsights').mockResolvedValue({ data: { items: [] } });
    jest.spyOn(clientAPI, 'getPropertyRiskSignals').mockResolvedValue({ data: { items: [] } });
    jest.spyOn(clientAPI, 'getCommandCenter').mockResolvedValue({ data: { tasks: [] } });
    jest.spyOn(clientAPI, 'getPropertyAssets').mockResolvedValue({ data: { assets: [] } });
    jest.spyOn(clientAPI, 'getDocuments').mockResolvedValue({ data: { documents: [] } });
    jest.spyOn(clientAPI, 'getPropertyEvidence').mockResolvedValue({ data: { records: [] } });
    jest.spyOn(clientAPI, 'getPropertyTimeline').mockResolvedValue({ data: { items: [] } });
  });

  it('shows stored-vs-preview note, score_status_message, and last_calculated on Compliance tab when explainability loads', async () => {
    jest.spyOn(clientAPI, 'getComplianceDetail').mockResolvedValue({
      data: {
        matrix: [],
        kpis: {},
        score: 82,
        score_status: 'ok',
        risk_level: 'LOW',
        last_calculated_at: '2026-04-01T12:00:00.000Z',
        score_status_message: 'Score reflects last completed batch.',
      },
    });
    jest.spyOn(clientAPI, 'getPropertyRequirements').mockResolvedValue({ data: { requirements: [] } });
    jest.spyOn(clientAPI, 'getPropertyComplianceScoreExplanation').mockResolvedValue({
      data: {
        authoritative: { score: 82, score_status: 'ok' },
        operational_preview: { live_engine_snapshot: { effective_jurisdiction_label: 'England' } },
      },
    });

    render(<PropertyDetailPage />);
    await screen.findByRole('button', { name: 'Compliance' });

    fireEvent.click(screen.getByRole('button', { name: 'Compliance' }));

    const note = await screen.findByTestId('property-compliance-stored-vs-preview-note');
    expect(note).toHaveTextContent(PROPERTY_DETAIL_STORED_VS_PREVIEW_NOTE);
    expect(note).toHaveTextContent('Score reflects last completed batch.');
    expect(note).toHaveTextContent('Last calculated:');
  });
});
