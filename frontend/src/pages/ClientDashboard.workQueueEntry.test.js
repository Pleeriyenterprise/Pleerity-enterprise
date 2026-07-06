/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ClientDashboard from './ClientDashboard';
import { clientAPI } from '../api/client';
import api from '../api/client';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [new URLSearchParams(), jest.fn()],
  };
});

jest.mock('../api/client', () => {
  const actual = jest.requireActual('../api/client');
  return {
    ...actual,
    __esModule: true,
    default: { get: jest.fn() },
    clientAPI: {
      getDashboard: jest.fn(),
      getComplianceSummary: jest.fn(),
      getCommandCenterPrimary: jest.fn(),
      getProtectionSnapshot: jest.fn(),
      getActivitySince: jest.fn(),
      getActiveSystemBanners: jest.fn(),
      getOnboardingChecklist: jest.fn(),
      getValueInsights: jest.fn(),
      getDashboardRoiSummary: jest.fn(),
      getRequirements: jest.fn(),
      getTodayItems: jest.fn(() => Promise.resolve({ data: {} })),
      postAnalyticsEvent: jest.fn(() => Promise.resolve({})),
      dismissSystemBanner: jest.fn(() => Promise.resolve({})),
    },
  };
});

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { role: 'ROLE_CLIENT', client_id: 'client-1', email: 't@test.com' },
    logout: jest.fn(),
  }),
}));

jest.mock('../utils/operationalCapabilityAccess', () => ({
  useDashboardCapabilities: () => ({
    canViewDashboard: true,
    canViewScore: true,
    canViewCommandCentre: true,
    canViewToday: true,
    canUseOpsMaintenance: false,
    canUseOpsPredictive: false,
    canUseOpsContractors: false,
    canUseOpsApprovals: false,
  }),
  getCapabilityDeniedMessage: (_e, fallback) => fallback,
  isCapabilityDeniedApiError: () => false,
}));

jest.mock('../context/GuidedEvidenceModalContext', () => ({
  useGuidedEvidenceModal: () => ({ openGuidedEvidence: jest.fn() }),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

const dashboardBody = {
  client: { client_id: 'client-1', billing_plan: 'PLAN', plan_code: 'P' },
  properties: [
    {
      property_id: 'p1',
      nickname: 'One',
      address_line_1: '1 St',
      compliance_status: 'GREEN',
      applicability: 'NOT_APPLICABLE',
    },
  ],
  compliance_summary: { total_requirements: 0, compliant: 0, overdue: 0, expiring_soon: 0 },
  onboarding_checklist: { items: [], completed_at: '2020-01-01T00:00:00Z' },
  compliance_score_headline: null,
};

function setupMocks() {
  clientAPI.getTodayItems.mockResolvedValue({
    data: {
      tasks: {
        urgent: [],
        upcoming: [],
        in_progress: [],
        recently_completed: [],
        snoozed: [],
        hidden: [],
      },
    },
  });
  clientAPI.getDashboard.mockResolvedValue({ data: dashboardBody });
  clientAPI.getComplianceSummary.mockResolvedValue({
    data: {
      properties: dashboardBody.properties,
      portfolio_score: 80,
      score_status: 'ok',
      score_status_message: null,
      risk_level: 'Low Risk',
    },
  });
  clientAPI.getCommandCenterPrimary.mockResolvedValue({
    data: {
      tasks_digest_summary: {},
      recent_activity: [],
      freshness: { tasks_refreshed_at: '2026-01-01T00:00:00.000Z' },
    },
  });
  clientAPI.getProtectionSnapshot.mockResolvedValue({ data: {} });
  clientAPI.getActivitySince.mockResolvedValue({ data: {} });
  clientAPI.getActiveSystemBanners.mockResolvedValue({ data: { items: [] } });
  clientAPI.getOnboardingChecklist.mockResolvedValue({ data: { items: [], completed_at: '2020-01-01T00:00:00Z' } });
  clientAPI.getValueInsights.mockResolvedValue({ data: {} });
  clientAPI.getDashboardRoiSummary.mockResolvedValue({ data: null });
  clientAPI.getRequirements.mockResolvedValue({ data: { requirements: [] } });
  api.get.mockImplementation((url) => {
    if (url === '/client/compliance-score') {
      return Promise.resolve({
        data: {
          score: 80,
          grade: 'A',
          color: 'green',
          message: 'Good',
          score_status: 'ok',
          score_status_message: null,
          properties_count: 1,
          stats: {},
          portfolio_last_calculated_at: '2026-03-01T10:00:00.000Z',
        },
      });
    }
    if (url.startsWith('/client/compliance-score/trend')) return Promise.resolve({ data: {} });
    if (url.startsWith('/client/score/timeline')) return Promise.resolve({ data: {} });
    if (url.startsWith('/client/score/changes')) return Promise.resolve({ data: {} });
    if (url === '/profile/notifications') return Promise.resolve({ data: {} });
    return Promise.resolve({ data: {} });
  });
}

describe('ClientDashboard work queue entry', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupMocks();
  });

  it('shows Work queue button linking to /work-queue', async () => {
    render(
      <MemoryRouter>
        <ClientDashboard />
      </MemoryRouter>,
    );
    const link = await screen.findByTestId('dashboard-link-work-queue');
    expect(link).toBeInTheDocument();
    expect(link).toHaveTextContent('Work queue');
  });
});
