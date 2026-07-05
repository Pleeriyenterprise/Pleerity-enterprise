/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ReportsPage from './ReportsPage';

const mockApiGet = jest.fn();

const mockReportCapabilities = {
  canViewReports: true,
  canDownloadReports: true,
  canGeneratePdf: true,
  canGenerateCsv: true,
  canScheduleReportsRead: true,
  canScheduleReportsWrite: true,
  canAuditPackRead: true,
  canAuditPackWrite: true,
  canViewRentOperationsSummary: false,
};

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { role: 'ROLE_CLIENT_ADMIN', client_id: 'c1' },
  }),
}));

jest.mock('../utils/reportCapabilityAccess', () => ({
  ...jest.requireActual('../utils/reportCapabilityAccess'),
  useReportCapabilities: () => mockReportCapabilities,
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

const CATALOG = [
  {
    id: 'compliance_summary',
    name: 'Compliance Summary Report',
    description: 'Executive compliance posture and portfolio overview',
    formats: ['csv', 'pdf'],
    endpoint: '/reports/compliance-summary',
  },
  {
    id: 'requirements',
    name: 'Requirements Report',
    description: 'Operational obligation tracking and action-management report',
    formats: ['csv', 'pdf'],
    endpoint: '/reports/requirements',
  },
  {
    id: 'evidence_readiness',
    name: 'Evidence Readiness Report',
    description: 'Operational audit-preparedness and remediation assessment',
    formats: ['pdf'],
    endpoint: '/reports/generate',
  },
  {
    id: 'audit_evidence_pack',
    name: 'Audit Evidence Pack',
    description: 'Immutable evidentiary archive',
    formats: ['zip'],
    endpoint: '/client/compliance/audit-pack/generate',
  },
];

describe('ReportsPage reporting UX catalog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.assign(mockReportCapabilities, {
      canViewReports: true,
      canDownloadReports: true,
      canGeneratePdf: true,
      canGenerateCsv: true,
      canScheduleReportsRead: true,
      canScheduleReportsWrite: true,
      canAuditPackRead: true,
      canAuditPackWrite: true,
      canViewRentOperationsSummary: false,
    });
    mockApiGet.mockImplementation((url) => {
      if (url === '/reports/available') return Promise.resolve({ data: { reports: CATALOG } });
      if (url === '/client/properties') return Promise.resolve({ data: { properties: [] } });
      if (url === '/reports/schedules') return Promise.resolve({ data: { schedules: [] } });
      if (url === '/reports') return Promise.resolve({ data: { reports: [] } });
      if (url.startsWith('/portal/digests')) return Promise.resolve({ data: { digests: [] } });
      return Promise.resolve({ data: {} });
    });
  });

  it('shows ecosystem guide and report catalog with export grades', async () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('reports-ecosystem-guide')).toBeInTheDocument();
    expect(screen.getByTestId('reports-section-catalog')).toBeInTheDocument();
    expect(screen.getByTestId('report-grade-compliance_summary')).toHaveTextContent('Executive Overview');
    expect(screen.getByTestId('report-grade-audit_evidence_pack')).toHaveTextContent('Evidentiary Archive');
    expect(screen.getAllByText(/Best used for:/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/triage at a glance/i)).not.toBeInTheDocument();
  });

  it('routes specialty reports to dedicated flows', async () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('report-specialty-link-audit_evidence_pack')).toHaveAttribute('href', '/reports/audit-pack');
    expect(screen.getByTestId('report-scroll-evidence-readiness')).toBeInTheDocument();
  });

  it('explains PDF vs CSV in export settings', async () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('format-selection-card')).toHaveTextContent(/PDF — presentation/i);
    expect(screen.getByTestId('format-selection-card')).toHaveTextContent(/CSV — structured/i);
  });
});
