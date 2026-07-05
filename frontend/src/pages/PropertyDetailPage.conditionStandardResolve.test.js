import React from 'react';
import { render, waitFor } from '@testing-library/react';
import PropertyDetailPage from './PropertyDetailPage';
import { clientAPI } from '../api/client';

const mockNavigate = jest.fn();
const mockOpenGuidedEvidence = jest.fn();
const mockHasFeature = jest.fn(() => false);
let mockLocationSearch = '?open=resolve&requirement_id=req-rs';

jest.mock('../utils/propertyCapabilityAccess', () => {
  const actual = jest.requireActual('../utils/propertyCapabilityAccess');
  return {
    ...actual,
    usePropertyWorkflowCapabilities: jest.fn(),
  };
});

const { usePropertyWorkflowCapabilities } = require('../utils/propertyCapabilityAccess');

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { portal_user_id: 'user-1' } }),
}));

jest.mock('../context/GuidedEvidenceModalContext', () => ({
  useGuidedEvidenceModal: () => ({ openGuidedEvidence: mockOpenGuidedEvidence }),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ propertyId: 'prop-1' }),
    useNavigate: () => mockNavigate,
    useLocation: () => ({
      pathname: '/properties/prop-1',
      search: mockLocationSearch,
      hash: '',
    }),
  };
});

function conditionStandardRow(reqId = 'req-rs') {
  return {
    requirement_id: reqId,
    property_id: 'prop-1',
    requirement_code: 'repairing_standard',
    requirement_type: 'repairing_standard',
    display_name: 'Repairing Standard',
    status: 'PENDING',
    workflow_family: 'CONDITION_STANDARD_ACTIVE_STANDARD',
    ops_verification_family: 'CONDITION_STANDARD_ACTIVE_STANDARD',
    take_action: {
      primary: {
        label: 'Manage related issues',
        route: '/operations/issues?property_id=prop-1',
        kind: 'navigate',
        handler: 'navigate',
        intent: 'view_guidance',
      },
    },
  };
}

function guidedRow(reqId = 'req-guided') {
  return {
    requirement_id: reqId,
    property_id: 'prop-1',
    requirement_code: 'gas_safety',
    requirement_type: 'gas_safety',
    display_name: 'Gas safety',
    status: 'MISSING',
    take_action: {
      primary: {
        label: 'Resolve requirement',
        route: null,
        kind: 'guided_evidence_resolution',
        handler: 'guided_evidence',
        intent: 'guided_evidence_resolution',
      },
    },
  };
}

function stubPropertyApis(matrix) {
  jest.spyOn(clientAPI, 'getProperties').mockResolvedValue({
    data: { properties: [{ property_id: 'prop-1', nickname: 'Prop 1', address_line_1: '1 Street' }] },
  });
  jest.spyOn(clientAPI, 'getComplianceDetail').mockResolvedValue({
    data: { matrix, kpis: {}, property_score: 0 },
  });
  jest.spyOn(clientAPI, 'getPropertyRequirements').mockResolvedValue({
    data: { requirements: matrix },
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
}

describe('PropertyDetailPage ?open=resolve condition-standard', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    usePropertyWorkflowCapabilities.mockImplementation(() =>
      require('../testUtils/propertyWorkflowTestCapabilities').defaultPropertyWorkflowTestCaps(mockHasFeature),
    );
    mockNavigate.mockReset();
    mockOpenGuidedEvidence.mockReset();
    mockLocationSearch = '?open=resolve&requirement_id=req-rs';
  });

  it('routes repairing_standard resolve deeplink to operational issues surface', async () => {
    stubPropertyApis([conditionStandardRow()]);

    render(<PropertyDetailPage />);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/operations/issues?property_id=prop-1');
    });
    expect(mockOpenGuidedEvidence).not.toHaveBeenCalled();
    const stripCall = mockNavigate.mock.calls.find(
      (args) =>
        typeof args[0] === 'object' &&
        args[0]?.pathname === '/properties/prop-1' &&
        args[0]?.search === '',
    );
    expect(stripCall).toBeUndefined();
  });

  it('still strips resolve query for guided non-condition-standard rows', async () => {
    mockLocationSearch = '?open=resolve&requirement_id=req-guided';
    stubPropertyApis([guidedRow()]);

    render(<PropertyDetailPage />);

    await waitFor(() => {
      expect(mockOpenGuidedEvidence).toHaveBeenCalled();
    });
    expect(mockNavigate).toHaveBeenCalledWith(
      expect.objectContaining({ pathname: '/properties/prop-1', search: '' }),
      { replace: true },
    );
  });
});
