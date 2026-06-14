/**
 * @jest-environment jsdom
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
    useLocation: () => ({ hash: '', pathname: '/properties/prop-1', search: '' }),
  };
});

jest.mock('../contexts/EntitlementsContext', () => ({
  useEntitlements: () => ({ hasFeature: mockHasFeature }),
}));

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { portal_user_id: 'user-1', role: 'ROLE_CLIENT_ADMIN' } }),
}));

jest.mock('../context/GuidedEvidenceModalContext', () => ({
  useGuidedEvidenceModal: () => ({ openGuidedEvidence: mockOpenGuidedEvidence }),
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

function mockMobileViewport() {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: jest.fn().mockImplementation((query) => ({
      matches: query.includes('639') || query.includes('767') || query.includes('768'),
      media: query,
      onchange: null,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      addListener: jest.fn(),
      removeListener: jest.fn(),
      dispatchEvent: jest.fn(),
    })),
  });
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 });
}

function makeRequirement(reqId, overrides = {}) {
  return {
    requirement_id: reqId,
    property_id: 'prop-1',
    requirement_code: 'epc',
    requirement_type: 'epc',
    display_name: 'Energy Performance Certificate (EPC)',
    status: 'VALID',
    evidence_doc_id: 'doc-1',
    take_action: {
      primary: {
        label: 'View evidence',
        route: '/documents?property_id=prop-1&requirement_id=req-epc',
        handler: 'navigate',
      },
      secondary: null,
    },
    ...overrides,
  };
}

function stubPropertyDetailApis(requirements) {
  jest.spyOn(clientAPI, 'getProperties').mockResolvedValue({
    data: { properties: [{ property_id: 'prop-1', nickname: 'Prop 1', address_line_1: '1 Street' }] },
  });
  jest.spyOn(clientAPI, 'getComplianceDetail').mockResolvedValue({
    data: {
      property_name: 'Prop 1',
      matrix: requirements,
      kpis: {},
      property_score: 0,
    },
  });
  jest.spyOn(clientAPI, 'getPropertyRequirements').mockResolvedValue({
    data: { requirements },
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

describe('PropertyDetailPage mobile compliance requirement cards', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    mockNavigate.mockReset();
    mockOpenGuidedEvidence.mockReset();
    mockMobileViewport();
  });

  it('does not render the dead inline Details toggle on mobile cards', async () => {
    stubPropertyDetailApis([makeRequirement('req-epc')]);
    render(<PropertyDetailPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Compliance' }));

    await waitFor(() => {
      expect(screen.getByTestId('property-compliance-mobile-requirement-intel-req-epc')).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /^Details$/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Requirement details' }).length).toBeGreaterThanOrEqual(1);
  });

  it('opens RequirementIntelligenceModal from Requirement details on mobile cards', async () => {
    stubPropertyDetailApis([makeRequirement('req-epc')]);
    render(<PropertyDetailPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Compliance' }));

    fireEvent.click(await screen.findByTestId('property-compliance-mobile-requirement-intel-req-epc'));

    await waitFor(() => {
      expect(screen.getByTestId('requirement-intel-modal-stub')).toBeInTheDocument();
    });
    expect(screen.getByTestId('requirement-intel-modal-stub')).toHaveAttribute('data-requirement-id', 'req-epc');
  });

  it('keeps primary compliance CTA working on mobile cards', async () => {
    stubPropertyDetailApis([makeRequirement('req-epc')]);
    render(<PropertyDetailPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Compliance' }));

    fireEvent.click(await screen.findByTestId('property-compliance-mobile-primary-req-epc'));
    expect(mockNavigate).toHaveBeenCalledWith('/properties/prop-1?tab=evidence&requirement_id=req-epc&open=intel');
  });

  it('keeps guided primary CTA working on mobile cards', async () => {
    const guidedReq = makeRequirement('req-legionella', {
      requirement_code: 'legionella',
      requirement_type: 'legionella',
      display_name: 'Legionella Risk Assessment',
      status: 'MISSING',
      evidence_doc_id: null,
      take_action: {
        primary: {
          label: 'Record Legionella risk assessment',
          route: null,
          handler: 'guided_evidence',
        },
        secondary: null,
      },
    });
    stubPropertyDetailApis([guidedReq]);
    render(<PropertyDetailPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Compliance' }));

    fireEvent.click(await screen.findByTestId('property-compliance-mobile-primary-req-legionella'));
    expect(mockOpenGuidedEvidence).toHaveBeenCalledTimes(1);
  });
});
