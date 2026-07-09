import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import PropertyDetailPage from './PropertyDetailPage';
import { clientAPI } from '../api/client';

const mockNavigate = jest.fn();
const mockHasFeature = jest.fn(() => false);
const mockLocation = { hash: '', pathname: '/properties/prop-1', search: '?resolve_requirement=req-review-1' };

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

jest.mock('../components/client/RequirementIntelligenceModal', () => ({
  __esModule: true,
  default: ({ open, requirementId, initialFocusSubmission }) =>
    open ? (
      <div
        data-testid="requirement-intel-modal-stub"
        data-requirement-id={requirementId}
        data-focus-submission={String(initialFocusSubmission)}
      />
    ) : null,
}));

describe('PropertyDetailPage resolve_requirement deeplink', () => {
  beforeEach(() => {
    usePropertyWorkflowCapabilities.mockImplementation(() =>
      require('../testUtils/propertyWorkflowTestCapabilities').defaultPropertyWorkflowTestCaps(mockHasFeature),
    );
    mockNavigate.mockReset();
    jest.spyOn(clientAPI, 'getComplianceDetail').mockResolvedValue({
      data: {
        property_name: 'Test Property',
        matrix: [
          {
            requirement_id: 'req-review-1',
            property_id: 'prop-1',
            requirement_type: 'landlord_registration_ni',
            display_name: 'Landlord Registration Ni',
            truth_presentation_label: 'Organisation review pending',
            evidence_authority: { state: 'UPLOADED_UNCONFIRMED' },
          },
        ],
        property_score: { score: 80 },
        risk_level: 'MEDIUM',
        score_status: 'ok',
      },
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

  it('opens compliance tab and requirement intel with submission focus', async () => {
    render(<PropertyDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId('property-compliance-panel')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByTestId('requirement-intel-modal-stub')).toBeInTheDocument();
    });

    const modal = screen.getByTestId('requirement-intel-modal-stub');
    expect(modal).toHaveAttribute('data-requirement-id', 'req-review-1');
    expect(modal).toHaveAttribute('data-focus-submission', 'true');
    expect(screen.getByTestId('review-context-banner')).toBeInTheDocument();
  });
});
