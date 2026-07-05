import React from 'react';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ComplianceScorePage from './ComplianceScorePage';
import api from '../api/client';

jest.mock('../api/client', () => ({
  __esModule: true,
  default: { get: jest.fn() },
}));

const mockNavigate = jest.fn();
const mockOpenGuidedEvidence = jest.fn();

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

jest.mock('../utils/reportCapabilityAccess', () => ({
  ...jest.requireActual('../utils/reportCapabilityAccess'),
  useReportCapabilities: () => ({
    canGeneratePdf: false,
    canGenerateCsv: false,
  }),
}));

jest.mock('../context/GuidedEvidenceModalContext', () => ({
  useGuidedEvidenceModal: () => ({ openGuidedEvidence: mockOpenGuidedEvidence }),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

function baseScore(overrides = {}) {
  return {
    score: 50,
    grade: 'C',
    color: 'amber',
    message: 'Test',
    stats: { total_requirements: 2, compliant: 0, expiring_soon: 0, overdue: 1 },
    properties_count: 1,
    drivers: [],
    ...overrides,
  };
}

function wrap(ui) {
  return <MemoryRouter>{ui}</MemoryRouter>;
}

/**
 * Prefer desktop score-driver table. Waits for the loaded page (drivers markup is absent during skeleton state).
 */
async function getScoreDriversScope() {
  await screen.findByTestId('compliance-score-page');
  const desktop = screen.queryAllByTestId('score-drivers-table-desktop')[0];
  if (desktop) return within(desktop);
  return within(await screen.findByTestId('score-drivers-cards-mobile'));
}

describe('ComplianceScorePage score drivers CTA integrity', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockOpenGuidedEvidence.mockReset();
    api.get.mockReset();
  });

  it('renders open requirement navigation when no canonical take_action primary authority', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/client/compliance-score') {
        return Promise.resolve({
          data: baseScore({
            drivers: [
              {
                property_id: 'p1',
                property_name: 'Prop',
                requirement_id: 'r1',
                requirement_name: 'Gas',
                status: 'MISSING_EVIDENCE',
                evidence_uploaded: false,
                actions: ['UPLOAD', 'VIEW'],
              },
            ],
          }),
        });
      }
      if (url === '/client/dashboard') {
        return Promise.resolve({ data: { properties: [{ property_id: 'p1', nickname: 'Prop' }] } });
      }
      if (url === '/client/requirements') {
        return Promise.resolve({
          data: {
            requirements: [
              {
                requirement_id: 'r1',
                property_id: 'p1',
                requirement_code: 'gas_safety',
                compliance_requirement_class: 'DOCUMENT',
                status: 'MISSING',
              },
            ],
          },
        });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });

    render(wrap(<ComplianceScorePage />));

    const desktop = await getScoreDriversScope();
    expect(await desktop.findByTestId('score-driver-nav-requirement')).toBeInTheDocument();
    expect(desktop.getByRole('button', { name: /open requirement/i })).toBeInTheDocument();
    expect(desktop.queryByText(/server-confirmed/i)).not.toBeInTheDocument();
    expect(desktop.queryByRole('button', { name: /upload document/i })).not.toBeInTheDocument();
    expect(desktop.queryByRole('button', { name: /confirm details/i })).not.toBeInTheDocument();
    expect(desktop.queryByRole('button', { name: /view requirement/i })).not.toBeInTheDocument();
  });

  it('does not expose synthetic driver heuristics as clickable remediation routes', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/client/compliance-score') {
        return Promise.resolve({
          data: baseScore({
            drivers: [
              {
                property_id: 'p1',
                property_name: 'Prop',
                requirement_id: 'r1',
                requirement_name: 'Gas',
                status: 'MISSING_EVIDENCE',
                evidence_uploaded: false,
                actions: ['UPLOAD'],
              },
            ],
          }),
        });
      }
      if (url === '/client/dashboard') {
        return Promise.resolve({ data: { properties: [{ property_id: 'p1' }] } });
      }
      if (url === '/client/requirements') {
        return Promise.resolve({
          data: {
            requirements: [
              {
                requirement_id: 'r1',
                property_id: 'p1',
                compliance_requirement_class: 'DOCUMENT',
                status: 'MISSING',
              },
            ],
          },
        });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });

    render(wrap(<ComplianceScorePage />));

    const desktop = await getScoreDriversScope();
    await desktop.findByTestId('score-driver-nav-requirement');
    expect(desktop.queryByText(/server-confirmed/i)).not.toBeInTheDocument();
    const docLinks = desktop.queryAllByRole('link', { name: /document/i });
    expect(docLinks.filter((el) => el.getAttribute('href')?.includes('/documents'))).toHaveLength(0);
  });

  it('renders canonical take_action primary and navigates on click', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/client/compliance-score') {
        return Promise.resolve({
          data: baseScore({
            drivers: [
              {
                property_id: 'p1',
                property_name: 'Prop',
                requirement_id: 'r1',
                requirement_name: 'Gas',
                status: 'MISSING_EVIDENCE',
                evidence_uploaded: false,
                actions: ['UPLOAD'],
              },
            ],
          }),
        });
      }
      if (url === '/client/dashboard') {
        return Promise.resolve({ data: { properties: [{ property_id: 'p1' }] } });
      }
      if (url === '/client/requirements') {
        return Promise.resolve({
          data: {
            requirements: [
              {
                requirement_id: 'r1',
                property_id: 'p1',
                compliance_requirement_class: 'DOCUMENT',
                status: 'MISSING',
                take_action: {
                  primary: {
                    label: 'Server primary label',
                    route: '/documents?property_id=p1&requirement_id=r1',
                    handler: 'navigate',
                  },
                  secondary: null,
                  supporting_external_links: [],
                },
              },
            ],
          },
        });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });

    render(wrap(<ComplianceScorePage />));

    const desktop = await getScoreDriversScope();
    const primary = await desktop.findByTestId('score-driver-canonical-primary');
    expect(primary).toHaveTextContent('Server primary label');
    fireEvent.click(primary);
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalled();
    });
    const arg = mockNavigate.mock.calls[0][0];
    expect(String(arg)).toContain('/documents');
  });

  it('keeps two driver rows with same requirement_id but different gap_key as separate canonical surfaces', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/client/compliance-score') {
        return Promise.resolve({
          data: baseScore({
            drivers: [
              {
                property_id: 'p1',
                property_name: 'Prop',
                requirement_id: 'r1',
                requirement_name: 'Gas',
                gap_key: 'g1',
                status: 'MISSING_EVIDENCE',
                evidence_uploaded: false,
                actions: ['UPLOAD'],
              },
              {
                property_id: 'p1',
                property_name: 'Prop',
                requirement_id: 'r1',
                requirement_name: 'Gas',
                gap_key: 'g2',
                status: 'NEEDS_CONFIRMATION',
                evidence_uploaded: true,
                actions: ['CONFIRM'],
              },
            ],
          }),
        });
      }
      if (url === '/client/dashboard') {
        return Promise.resolve({ data: { properties: [{ property_id: 'p1' }] } });
      }
      if (url === '/client/requirements') {
        return Promise.resolve({
          data: {
            requirements: [
              {
                requirement_id: 'r1',
                property_id: 'p1',
                compliance_requirement_class: 'DOCUMENT',
                status: 'PENDING',
                take_action: {
                  primary: {
                    label: 'Canonical one',
                    route: '/properties/p1#compliance',
                    handler: 'navigate',
                  },
                  secondary: null,
                  supporting_external_links: [],
                },
              },
            ],
          },
        });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });

    render(wrap(<ComplianceScorePage />));

    const desktop = await getScoreDriversScope();
    const primaries = await desktop.findAllByTestId('score-driver-canonical-primary');
    expect(primaries).toHaveLength(2);
    expect(primaries[0]).toHaveTextContent('Canonical one');
    expect(primaries[1]).toHaveTextContent('Canonical one');
  });

  it('uses resolved evidence semantics for canonical requirement rows (multi-evidence incomplete)', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/client/compliance-score') {
        return Promise.resolve({
          data: baseScore({
            drivers: [
              {
                property_id: 'p1',
                property_name: 'Prop',
                requirement_id: 'r1',
                requirement_name: 'Fire alarm evidence',
                status: 'MISSING_EVIDENCE',
                evidence_uploaded: false,
              },
            ],
          }),
        });
      }
      if (url === '/client/dashboard') {
        return Promise.resolve({ data: { properties: [{ property_id: 'p1' }] } });
      }
      if (url === '/client/requirements') {
        return Promise.resolve({
          data: {
            requirements: [
              {
                requirement_id: 'r1',
                property_id: 'p1',
                requirement_code: 'fire_alarm',
                workflow_class: 'MULTI_EVIDENCE',
                status: 'MISSING',
                take_action: {
                  primary: {
                    label: 'Resolve',
                    route: '/properties/p1?open=resolve&requirement_id=r1',
                    handler: 'guided_evidence',
                  },
                },
              },
            ],
          },
        });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });

    render(wrap(<ComplianceScorePage />));
    const desktop = await getScoreDriversScope();
    expect(await desktop.findByText('Evidence incomplete')).toBeInTheDocument();
    expect(desktop.queryByText('Not uploaded')).not.toBeInTheDocument();
  });
});
