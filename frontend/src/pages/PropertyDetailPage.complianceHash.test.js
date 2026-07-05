import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import PropertyDetailPage from './PropertyDetailPage';
import { clientAPI } from '../api/client';

const mockNavigate = jest.fn();
const mockHasFeature = jest.fn(() => true);

const mockLocation = { hash: '#compliance', pathname: '/properties/prop-1', search: '' };

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ propertyId: 'prop-1' }),
    useNavigate: () => mockNavigate,
    useLocation: () => mockLocation,
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
  useGuidedEvidenceModal: () => ({ openGuidedEvidence: jest.fn() }),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

describe('PropertyDetailPage #compliance hash', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    usePropertyWorkflowCapabilities.mockImplementation(() =>
      require('../testUtils/propertyWorkflowTestCapabilities').defaultPropertyWorkflowTestCaps(mockHasFeature),
    );
    jest.spyOn(clientAPI, 'getProperties').mockResolvedValue({
      data: { properties: [{ property_id: 'prop-1', nickname: 'P1', address_line_1: '1 St' }] },
    });
    jest.spyOn(clientAPI, 'getComplianceDetail').mockResolvedValue({
      data: { matrix: [], score: 50, risk_level: 'MEDIUM', score_status: 'ok' },
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

  it('opens Compliance tab when URL hash is #compliance', async () => {
    render(<PropertyDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId('property-compliance-panel')).toBeInTheDocument();
    });

    const tab = screen.getByTestId('property-tab-compliance');
    expect(tab.className).toMatch(/border-electric-teal/);
  });
});
