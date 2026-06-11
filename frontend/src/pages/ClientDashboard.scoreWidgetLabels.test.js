import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ClientDashboard from './ClientDashboard';
import { clientAPI } from '../api/client';
import api from '../api/client';
import { clearOperationalCache } from '../utils/clientOperationalFetch';

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => jest.fn(),
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

jest.mock('../contexts/EntitlementsContext', () => ({
  useEntitlements: () => ({ hasFeature: () => false }),
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
    { property_id: 'p1', nickname: 'One', address_line_1: '1 St', compliance_status: 'GREEN' },
    { property_id: 'p2', nickname: 'Two', address_line_1: '2 St', compliance_status: 'GREEN' },
  ],
  compliance_summary: { total_requirements: 0, compliant: 0, overdue: 0, expiring_soon: 0 },
  onboarding_checklist: { items: [], completed_at: '2020-01-01T00:00:00Z' },
};

function setupMocks({ complianceScore, requirements }) {
  clientAPI.getDashboard.mockResolvedValue({ data: dashboardBody });
  clientAPI.getComplianceSummary.mockResolvedValue({
    data: { properties: dashboardBody.properties, portfolio_score: 55, score_status: 'ok', risk_level: 'High risk' },
  });
  clientAPI.getCommandCenterPrimary.mockResolvedValue({ data: {} });
  clientAPI.getProtectionSnapshot.mockResolvedValue({ data: {} });
  clientAPI.getActivitySince.mockResolvedValue({ data: {} });
  clientAPI.getActiveSystemBanners.mockResolvedValue({ data: { items: [] } });
  clientAPI.getOnboardingChecklist.mockResolvedValue({ data: { items: [], completed_at: '2020-01-01T00:00:00Z' } });
  clientAPI.getValueInsights.mockResolvedValue({ data: {} });
  clientAPI.getDashboardRoiSummary.mockResolvedValue({ data: null });
  clientAPI.getRequirements.mockResolvedValue({ data: { requirements: requirements || [] } });
  api.get.mockImplementation((url) => {
    if (url === '/client/compliance-score') {
      return Promise.resolve({ data: complianceScore });
    }
    if (url.startsWith('/client/compliance-score/trend')) return Promise.resolve({ data: {} });
    if (url.startsWith('/client/score/timeline')) return Promise.resolve({ data: {} });
    if (url === '/profile/notifications') return Promise.resolve({ data: {} });
    return Promise.resolve({ data: {} });
  });
}

describe('ClientDashboard score widget labels', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clearOperationalCache();
  });

  it('shows score-tracked obligations and next renewal labels', async () => {
    setupMocks({
      complianceScore: {
        score: 55,
        grade: 'D',
        color: 'red',
        message: 'High risk',
        score_status: 'ok',
        properties_count: 2,
        stats: { total_requirements: 11, compliant: 4, days_until_next_expiry: 1709 },
        recommendations: [],
      },
      requirements: [
        { requirement_id: 'r1', property_id: 'p1', applicability: 'REQUIRED', status: 'COMPLIANT', compliance_requirement_class: 'DOCUMENT' },
      ],
    });
    render(
      <MemoryRouter>
        <ClientDashboard />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('stat-requirements')).toBeInTheDocument();
    expect(screen.getByText('Score-tracked obligations')).toBeInTheDocument();
    expect(screen.getByText('Valid for scoring')).toBeInTheDocument();
    expect(screen.getByText('Next renewal')).toBeInTheDocument();
    expect(screen.queryByText(/^Requirements$/)).not.toBeInTheDocument();
    expect(screen.getByTestId('stat-expiry')).toHaveTextContent('1+ year');
    expect(screen.queryByText('1709')).not.toBeInTheDocument();
  });

  it('shows registry context when registry count differs from score count', async () => {
    const reqs = Array.from({ length: 13 }, (_, i) => ({
      requirement_id: `r${i}`,
      property_id: 'p1',
      applicability: 'REQUIRED',
      status: 'COMPLIANT',
      compliance_requirement_class: 'DOCUMENT',
    }));
    setupMocks({
      complianceScore: {
        score: 55,
        grade: 'D',
        color: 'red',
        message: 'High risk',
        score_status: 'ok',
        properties_count: 2,
        stats: { total_requirements: 11, compliant: 4, days_until_next_expiry: 30 },
        recommendations: [],
      },
      requirements: reqs,
    });
    render(
      <MemoryRouter>
        <ClientDashboard />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('score-widget-registry-context')).toHaveTextContent(
      '13 tracked in Requirements',
    );
  });

  it('rewrites stale upload-and-verify quick action for assurance lifecycle', async () => {
    setupMocks({
      complianceScore: {
        score: 55,
        grade: 'D',
        color: 'red',
        message: 'High risk',
        score_status: 'ok',
        properties_count: 1,
        stats: { total_requirements: 2, compliant: 1, days_until_next_expiry: 10 },
        recommendations: [
          {
            priority: 'high',
            action: 'Upload and verify evidence for SMOKE_ALARM',
            requirement_code: 'SMOKE_ALARM',
            display_label: 'Smoke alarms',
            property_id: 'p1',
          },
        ],
      },
      requirements: [
        {
          requirement_id: 'req-smoke',
          property_id: 'p1',
          requirement_code: 'smoke_alarm',
          requirement_type: 'smoke_alarm',
          applicability: 'REQUIRED',
          status: 'PENDING',
          compliance_requirement_class: 'DOCUMENT',
          client_lifecycle_state: 'PENDING_REVIEW',
        },
      ],
    });
    render(
      <MemoryRouter>
        <ClientDashboard />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByTestId('quick-action-fix-0')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/Review assurance status/i)).toBeInTheDocument());
    expect(screen.queryByText(/Upload and verify/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('quick-action-fix-0')).toHaveTextContent('View');
  });
});
