/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ReportsPage from './ReportsPage';

const mockHasFeature = jest.fn();
const mockApiGet = jest.fn();

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { role: 'ROLE_CLIENT_ADMIN', client_id: 'c1' },
  }),
}));

jest.mock('../contexts/EntitlementsContext', () => ({
  useEntitlements: () => ({
    hasFeature: (...args) => mockHasFeature(...args),
  }),
}));

jest.mock('../api/client', () => ({
  __esModule: true,
  default: {
    get: (...args) => mockApiGet(...args),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
  clientAPI: {
    listEvidencePackJobs: jest.fn().mockResolvedValue({ data: { jobs: [] } }),
    getAnalyticsSummary: jest.fn().mockResolvedValue({ data: {} }),
    createEvidencePackJob: jest.fn(),
    postAnalyticsEvent: jest.fn().mockResolvedValue({}),
    downloadEvidencePackFile: jest.fn(),
  },
}));

describe('ReportsPage audit evidence pack CTA', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockHasFeature.mockImplementation((f) => ['reports_pdf', 'reports_csv'].includes(f));
    mockApiGet.mockImplementation((url) => {
      if (url === '/reports/available') return Promise.resolve({ data: { reports: [] } });
      if (url === '/client/properties') return Promise.resolve({ data: { properties: [] } });
      if (url === '/reports/schedules') return Promise.resolve({ data: { schedules: [] } });
      if (url === '/reports') return Promise.resolve({ data: { reports: [] } });
      if (url.startsWith('/portal/digests')) return Promise.resolve({ data: { digests: [] } });
      return Promise.resolve({ data: {} });
    });
  });

  it('shows a Reports CTA linking to /reports/audit-pack', async () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>
    );

    expect(await screen.findByTestId('reports-audit-evidence-pack-cta')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /open audit evidence pack/i })).toHaveAttribute('href', '/reports/audit-pack');
  });

  it('shows the new reports IA guide, sections, and existing controls', async () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>
    );

    expect(await screen.findByTestId('reports-ecosystem-guide')).toBeInTheDocument();
    expect(screen.getByTestId('reports-section-audit-evidence-packs')).toBeInTheDocument();
    expect(screen.getByTestId('reports-section-compliance-reports')).toBeInTheDocument();
    expect(screen.getByTestId('reports-section-regulatory-system-exports')).toBeInTheDocument();
    expect(screen.getByTestId('reports-section-scheduled-reports')).toBeInTheDocument();
    expect(screen.getByTestId('digests-card')).toBeInTheDocument();
    expect(screen.getByTestId('format-selection-card')).toBeInTheDocument();
  });

  it('uses Regulatory/System Export wording and removes old confusing ZIP label', async () => {
    mockHasFeature.mockImplementation((f) => ['reports_pdf', 'reports_csv', 'audit_log_export'].includes(f));

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Regulatory\/System Export \(CSV ZIP\)/i)).toBeInTheDocument();
    expect(screen.queryByText(/Compliance evidence pack \(ZIP\)/i)).not.toBeInTheDocument();
  });
});
