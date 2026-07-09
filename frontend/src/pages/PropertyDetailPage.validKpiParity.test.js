import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import PropertyDetailPage from './PropertyDetailPage';
import { clientAPI } from '../api/client';

const mockNavigate = jest.fn();
const mockHasFeature = jest.fn(() => false);

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ propertyId: 'prop-a' }),
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
  useGuidedEvidenceModal: () => ({ openGuidedEvidence: jest.fn() }),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

function matrixRow(id, code, status) {
  return {
    requirement_id: id,
    property_id: 'prop-a',
    requirement_code: code,
    display_name: code,
    status,
  };
}

function stubApis() {
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
}

describe('PropertyDetailPage Valid KPI parity', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    usePropertyWorkflowCapabilities.mockImplementation(() =>
      require('../testUtils/propertyWorkflowTestCapabilities').defaultPropertyWorkflowTestCaps(mockHasFeature),
    );
    mockNavigate.mockReset();
    stubApis();
  });

  it('Valid for scoring uses kpis.status_valid and matches VALID filter count (Property A pattern)', async () => {
    const matrix = [
      matrixRow('r-gas', 'gas_safety', 'PENDING'),
      matrixRow('r-leg', 'legionella', 'PENDING'),
      matrixRow('r-hmo', 'hmo_fire_risk', 'PENDING'),
    ];
    jest.spyOn(clientAPI, 'getComplianceDetail').mockResolvedValue({
      data: {
        property_name: 'Cottage',
        matrix,
        kpis: {
          compliant: 2,
          status_valid: 0,
          lifecycle_satisfied_count: 2,
          missing: 1,
          overdue: 0,
          expiring_30: 0,
        },
      },
    });

    render(<PropertyDetailPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Compliance' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Valid for scoring \(0\)/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Valid for scoring \(0\)/i }));

    await waitFor(() => {
      expect(screen.getByText(/No requirements match what you are viewing/i)).toBeInTheDocument();
    });
  });

  it('Valid for scoring filter shows COMPLIANT rows (Property B pattern)', async () => {
    const matrix = [
      matrixRow('r-eicr', 'eicr', 'COMPLIANT'),
      matrixRow('r-epc', 'epc', 'COMPLIANT'),
      matrixRow('r-leg', 'legionella', 'COMPLIANT'),
    ];
    jest.spyOn(clientAPI, 'getComplianceDetail').mockResolvedValue({
      data: {
        property_name: 'Flat',
        matrix,
        kpis: {
          compliant: 3,
          status_valid: 3,
          lifecycle_satisfied_count: 3,
          missing: 0,
          overdue: 0,
          expiring_30: 0,
        },
      },
    });

    render(<PropertyDetailPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Compliance' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Valid for scoring \(3\)/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Valid for scoring \(3\)/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/eicr|epc|legionella/i).length).toBeGreaterThanOrEqual(3);
    });
  });
});
