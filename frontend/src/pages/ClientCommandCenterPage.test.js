/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ClientCommandCenterPage from './ClientCommandCenterPage';
import { clientAPI } from '../api/client';
import { COMMAND_CENTER_COMPLIANCE_SNAPSHOT_UNAVAILABLE } from '../utils/scoreFreshnessUi';
import { clearOperationalCache } from '../utils/clientOperationalFetch';

jest.mock('../api/client', () => ({
  clientAPI: {
    getCommandCenterPrimary: jest.fn(),
    getCommandCenterSecondary: jest.fn(),
    getComplianceSummary: jest.fn(),
    getRequirements: jest.fn(),
    postAnalyticsEvent: jest.fn(() => Promise.resolve({ data: { ok: true } })),
  },
  parseApiError: (_e, d) => d || 'Error',
}));

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { role: 'ROLE_CLIENT_ADMIN', client_id: 'c1', email: 't@test.com' },
  }),
}));

jest.mock('../utils/operationalCapabilityAccess', () => ({
  useCommandCentreCapabilities: () => ({
    canViewCommandCentre: true,
    canUseOpsMaintenance: false,
    canUseOpsPredictive: false,
    canUseOpsContractors: false,
    canUseOpsApprovals: false,
    canWriteOpsMaintenance: false,
    canWriteOpsPredictive: false,
    canWriteOpsApprovals: false,
    canUseOpsRent: false,
  }),
  getCapabilityDeniedMessage: (_e, fallback) => fallback,
  isCapabilityDeniedApiError: () => false,
}));

jest.mock('../components/client/RequirementIntelligenceModal', () => {
  return function MockIntelModal({ open }) {
    return open ? <div data-testid="view-requirement-modal">intel-open</div> : null;
  };
});

const mockOpenGuidedEvidence = jest.fn();
jest.mock('../context/GuidedEvidenceModalContext', () => ({
  useGuidedEvidenceModal: () => ({
    openGuidedEvidence: (...args) => mockOpenGuidedEvidence(...args),
  }),
}));

describe('ClientCommandCenterPage requirement intel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clearOperationalCache();
    mockOpenGuidedEvidence.mockClear();
    clientAPI.getCommandCenterPrimary.mockResolvedValue({
      data: {
        urgent_actions: [
          {
            id: 'requirement:req-cc-1',
            source_type: 'requirement',
            source_id: 'req-cc-1',
            property_id: 'p-cc-1',
            requirement_id: 'req-cc-1',
            jurisdiction: 'England',
            property_label: 'Laurel Gardens',
            title: 'Gas safety',
            primary_action_label: 'Upload',
            primary_action_url: '/documents?property_id=p-cc-1&requirement_id=req-cc-1',
            metadata: { action_type: 'missing_document' },
          },
        ],
        compliance_status_summary: {
          score: 70,
          grade: 'C',
          message: 'Action needed',
          color: 'amber',
        },
      },
    });
    clientAPI.getCommandCenterSecondary.mockResolvedValue({
      data: {
        upcoming_risks: [],
        recent_activity: [],
        compliance_status_summary: {},
      },
    });
    clientAPI.getComplianceSummary.mockResolvedValue({
      data: {
        properties: [{ property_id: 'p-cc-1', nickname: 'Laurel Gardens' }],
      },
    });
    clientAPI.getRequirements.mockResolvedValue({
      data: {
        requirements: [
          {
            requirement_id: 'req-cc-1',
            property_id: 'p-cc-1',
            compliance_requirement_class: 'DOCUMENT',
            applicability: 'REQUIRED',
            status: 'PENDING',
          },
        ],
      },
    });
  });

  it('opens RequirementIntelligenceModal from a requirement-backed priority row', async () => {
    render(
      <MemoryRouter>
        <ClientCommandCenterPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.queryByTestId('command-center-loading')).not.toBeInTheDocument();
    });
    const btn = await screen.findByTestId('command-center-open-requirement-intel');
    fireEvent.click(btn);
    expect(await screen.findByTestId('view-requirement-modal')).toBeInTheDocument();
  });

  it('calls openGuidedEvidence when urgent priority primary action is guided_evidence_resolution', async () => {
    const guidedBundle = {
      data: {
        urgent_actions: [
          {
            id: 'requirement:req-cc-1',
            source_type: 'requirement',
            source_id: 'req-cc-1',
            property_id: 'p-cc-1',
            requirement_id: 'req-cc-1',
            jurisdiction: 'England',
            property_label: 'Laurel Gardens',
            title: 'Gas safety',
            primary_action_type: 'guided_evidence_resolution',
            primary_action_label: 'Add compliance evidence',
            primary_action_url: '',
            metadata: {
              action_type: 'missing_document',
              take_action: {
                primary: {
                  kind: 'guided_evidence_resolution',
                  property_id: 'p-cc-1',
                  requirement_id: 'req-cc-1',
                  label: 'Add compliance evidence',
                },
              },
            },
          },
        ],
        upcoming_risks: [],
        compliance_status_summary: {
          score: 70,
          grade: 'C',
          message: 'Action needed',
          color: 'amber',
        },
      },
    };
    // All fetches need the same payload (Strict Mode / duplicate effect may call twice).
    clientAPI.getCommandCenterPrimary.mockResolvedValue(guidedBundle);
    render(
      <MemoryRouter>
        <ClientCommandCenterPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.queryByTestId('command-center-loading')).not.toBeInTheDocument();
    });
    const btn = await screen.findByRole('button', { name: /Add compliance evidence/i });
    fireEvent.click(btn);
    expect(mockOpenGuidedEvidence).toHaveBeenCalledWith(
      expect.objectContaining({
        propertyId: 'p-cc-1',
        requirement: expect.objectContaining({ requirement_id: 'req-cc-1' }),
      }),
    );
  });
});

describe('ClientCommandCenterPage compliance snapshot degraded UX', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clearOperationalCache();
    mockOpenGuidedEvidence.mockClear();
    clientAPI.getCommandCenterPrimary.mockResolvedValue({
      data: {
        urgent_actions: [],
        upcoming_risks: [],
      },
    });
    clientAPI.getCommandCenterSecondary.mockResolvedValue({
      data: { upcoming_risks: [], recent_activity: [], compliance_status_summary: {} },
    });
    clientAPI.getComplianceSummary.mockResolvedValue({ data: { properties: [] } });
    clientAPI.getRequirements.mockResolvedValue({ data: { requirements: [] } });
  });

  it('shows bundle degraded copy when compliance_status_summary is absent', async () => {
    render(
      <MemoryRouter>
        <ClientCommandCenterPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.queryByTestId('command-center-loading')).not.toBeInTheDocument();
    });
    const degraded = screen.getByTestId('command-center-compliance-degraded');
    expect(degraded).toHaveTextContent(COMMAND_CENTER_COMPLIANCE_SNAPSHOT_UNAVAILABLE);
  });

  it('shows score_status_message under degraded copy when summary omits score and status', async () => {
    clientAPI.getCommandCenterPrimary.mockResolvedValue({
      data: {
        urgent_actions: [],
        upcoming_risks: [],
        compliance_status_summary: {
          score_status_message: 'Upstream aggregation delayed.',
        },
      },
    });
    render(
      <MemoryRouter>
        <ClientCommandCenterPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.queryByTestId('command-center-loading')).not.toBeInTheDocument();
    });
    expect(screen.getByTestId('command-center-compliance-degraded')).toHaveTextContent(
      'Upstream aggregation delayed.',
    );
  });
});
