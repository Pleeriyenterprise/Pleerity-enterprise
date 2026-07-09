import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import PropertyDetailPage from './PropertyDetailPage';
import { clientAPI } from '../api/client';

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

jest.mock('../utils/propertyCapabilityAccess', () => {
  const actual = jest.requireActual('../utils/propertyCapabilityAccess');
  return {
    ...actual,
    usePropertyWorkflowCapabilities: jest.fn(),
  };
});

const { usePropertyWorkflowCapabilities } = require('../utils/propertyCapabilityAccess');

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { portal_user_id: 'user-1', role: 'ROLE_CLIENT_ADMIN' } }),
}));

jest.mock('../context/GuidedEvidenceModalContext', () => ({
  useGuidedEvidenceModal: () => ({ openGuidedEvidence: mockOpenGuidedEvidence }),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

function makeRequirement(reqId, takeAction) {
  return {
    requirement_id: reqId,
    property_id: 'prop-1',
    requirement_code: 'gas_safety',
    requirement_type: 'gas_safety',
    display_name: 'Gas safety',
    status: 'MISSING',
    take_action: takeAction,
  };
}

describe('PropertyDetailPage compliance action surfaces', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    mockNavigate.mockReset();
    mockOpenGuidedEvidence.mockReset();
    usePropertyWorkflowCapabilities.mockImplementation(() =>
      require('../testUtils/propertyWorkflowTestCapabilities').defaultPropertyWorkflowTestCaps(mockHasFeature),
    );

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
    jest.spyOn(clientAPI, 'getPropertyComplianceScoreExplanation').mockResolvedValue({ data: {} });
    jest.spyOn(clientAPI, 'getPropertyTimeline').mockResolvedValue({ data: { items: [] } });
  });

  it('renders guided CTA on compliance tab and full matrix for multi-mode requirement', async () => {
    const guidedTakeAction = {
      primary: {
        label: 'Resolve requirement',
        route: null,
        kind: 'guided_evidence_resolution',
        handler: 'guided_evidence',
        intent: 'guided_evidence_resolution',
        property_id: 'prop-1',
        requirement_id: 'req-guided',
      },
      secondary: {
        label: 'Upload document',
        route: '/documents?property_id=prop-1&requirement_id=req-guided',
        kind: 'navigate',
        handler: 'navigate',
      },
    };

    jest.spyOn(clientAPI, 'getComplianceDetail').mockResolvedValue({
      data: {
        matrix: [makeRequirement('req-guided', guidedTakeAction)],
        kpis: {},
        property_score: 0,
      },
    });
    jest.spyOn(clientAPI, 'getPropertyRequirements').mockResolvedValue({
      data: { requirements: [makeRequirement('req-guided', guidedTakeAction)] },
    });

    render(<PropertyDetailPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Compliance' }));

    const urgentGuided = await screen.findByTestId('compliance-urgent-guided-req-guided');
    expect(urgentGuided).toHaveTextContent('Resolve requirement');
    fireEvent.click(urgentGuided);
    expect(mockOpenGuidedEvidence).toHaveBeenCalledTimes(1);

    const matrixAction = await screen.findByTestId('compliance-matrix-action-req-guided');
    expect(matrixAction).toHaveTextContent('Resolve requirement');
    const matrixActionCell = matrixAction.closest('td');
    expect(matrixActionCell).toBeTruthy();
    expect(within(matrixActionCell).queryByRole('button', { name: 'Upload document' })).not.toBeInTheDocument();
    fireEvent.click(matrixAction);
    expect(mockOpenGuidedEvidence).toHaveBeenCalledTimes(2);
  });

  it('uses row property/requirement ids when guided primary omits metadata (parity with Requirements page)', async () => {
    const brokenGuided = {
      primary: {
        label: 'Resolve requirement',
        route: null,
        kind: 'guided_evidence_resolution',
        handler: 'guided_evidence',
        intent: 'guided_evidence_resolution',
      },
    };

    jest.spyOn(clientAPI, 'getComplianceDetail').mockResolvedValue({
      data: { matrix: [makeRequirement('req-broken', brokenGuided)], kpis: {}, property_score: 0 },
    });
    jest.spyOn(clientAPI, 'getPropertyRequirements').mockResolvedValue({
      data: { requirements: [makeRequirement('req-broken', brokenGuided)] },
    });

    render(<PropertyDetailPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Compliance' }));

    const matrixAction = await screen.findByTestId('compliance-matrix-action-req-broken');
    expect(matrixAction).not.toBeDisabled();
    expect(matrixAction).toHaveTextContent('Resolve requirement');

    fireEvent.click(matrixAction);
    await waitFor(() => {
      expect(mockOpenGuidedEvidence).toHaveBeenCalled();
    });
  });

  it('disables guided CTA when property and requirement context are both missing from the row', async () => {
    const brokenGuided = {
      primary: {
        label: 'Resolve requirement',
        route: null,
        kind: 'guided_evidence_resolution',
        handler: 'guided_evidence',
        intent: 'guided_evidence_resolution',
      },
    };
    const row = { ...makeRequirement('req-broken', brokenGuided), property_id: undefined, requirement_id: undefined };

    jest.spyOn(clientAPI, 'getComplianceDetail').mockResolvedValue({
      data: { matrix: [row], kpis: {}, property_score: 0 },
    });
    jest.spyOn(clientAPI, 'getPropertyRequirements').mockResolvedValue({
      data: { requirements: [row] },
    });

    render(<PropertyDetailPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Compliance' }));

    const matrixAction = await screen.findByTestId('compliance-matrix-action-undefined');
    expect(matrixAction).toBeDisabled();

    fireEvent.click(matrixAction);
    await waitFor(() => {
      expect(mockNavigate).not.toHaveBeenCalled();
      expect(mockOpenGuidedEvidence).not.toHaveBeenCalled();
    });
  });
});
