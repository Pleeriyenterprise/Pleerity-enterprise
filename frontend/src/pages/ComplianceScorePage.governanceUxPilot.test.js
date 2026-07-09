import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ComplianceScorePage from './ComplianceScorePage';
import api from '../api/client';

jest.mock('../api/client', () => ({
  __esModule: true,
  default: { get: jest.fn() },
}));

jest.mock('../context/GuidedEvidenceModalContext', () => ({
  useGuidedEvidenceModal: () => ({ openGuidedEvidence: jest.fn() }),
}));

jest.mock('../utils/reportCapabilityAccess', () => ({
  ...jest.requireActual('../utils/reportCapabilityAccess'),
  useReportCapabilities: () => ({ canGeneratePdf: false, canGenerateCsv: false }),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

function baseScore(overrides = {}) {
  return {
    score: 72,
    grade: 'B',
    color: 'amber',
    message: 'Test message',
    score_status: 'ok',
    stats: { total_requirements: 2, compliant: 1, expiring_soon: 0, overdue: 0 },
    properties_count: 1,
    drivers: [],
    ...overrides,
  };
}

describe('ComplianceScorePage governance UX pilot', () => {
  beforeEach(() => {
    api.get.mockReset();
  });

  it('Phase 2: ≥2 requirements show portfolio supplement only (export suppressed)', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/client/compliance-score') {
        return Promise.resolve({ data: baseScore({ stats: { total_requirements: 2, compliant: 1, expiring_soon: 0, overdue: 0 } }) });
      }
      if (url === '/client/dashboard') {
        return Promise.resolve({ data: { properties: [{ property_id: 'p1' }] } });
      }
      if (url === '/client/requirements') {
        return Promise.resolve({
          data: {
            requirements: [
              { requirement_id: 'r1', semantic_state: 'PARTIALLY_COMPLETE', status: 'COMPLIANT' },
              { requirement_id: 'r2', semantic_state: 'VERIFIED_CURRENT', status: 'COMPLIANT' },
            ],
          },
        });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });

    render(
      <MemoryRouter>
        <ComplianceScorePage />
      </MemoryRouter>,
    );

    const supplement = await screen.findByTestId('governance-ux-pilot-portfolio-supplement');
    expect(supplement).toHaveTextContent(/Certain compliance items remain under assessment/i);
    expect(supplement.textContent.toLowerCase()).not.toMatch(/additional evidence required/);
    expect(supplement.textContent.toLowerCase()).not.toMatch(/fully compliant|everything current|all properties compliant/);

    expect(screen.queryByTestId('governance-ux-pilot-export-note')).toBeNull();
  });

  it('Phase 2: single requirement shows export note only (portfolio suppressed)', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/client/compliance-score') {
        return Promise.resolve({ data: baseScore() });
      }
      if (url === '/client/dashboard') {
        return Promise.resolve({ data: { properties: [{ property_id: 'p1' }] } });
      }
      if (url === '/client/requirements') {
        return Promise.resolve({
          data: {
            requirements: [{ requirement_id: 'r1', semantic_state: 'PARTIALLY_COMPLETE', status: 'COMPLIANT' }],
          },
        });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });

    render(
      <MemoryRouter>
        <ComplianceScorePage />
      </MemoryRouter>,
    );

    const exportNote = await screen.findByTestId('governance-ux-pilot-export-note');
    expect(exportNote).toHaveTextContent(/Some records may still require additional evidence/i);
    expect(exportNote.textContent.toLowerCase()).not.toMatch(/fully compliant/);

    expect(screen.queryByTestId('governance-ux-pilot-portfolio-supplement')).toBeNull();
  });

  it('omits pilot supplement and export note when only VERIFIED_CURRENT pilot semantics are present', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/client/compliance-score') {
        return Promise.resolve({ data: baseScore() });
      }
      if (url === '/client/dashboard') {
        return Promise.resolve({ data: { properties: [] } });
      }
      if (url === '/client/requirements') {
        return Promise.resolve({
          data: {
            requirements: [{ requirement_id: 'r1', semantic_state: 'VERIFIED_CURRENT', status: 'COMPLIANT' }],
          },
        });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });

    render(
      <MemoryRouter>
        <ComplianceScorePage />
      </MemoryRouter>,
    );

    await screen.findByTestId('compliance-score-page');
    expect(screen.queryByTestId('governance-ux-pilot-portfolio-supplement')).toBeNull();
    expect(screen.queryByTestId('governance-ux-pilot-export-note')).toBeNull();
  });

  it('omits pilot surfaces when requirements lack pilot semantic signals', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/client/compliance-score') {
        return Promise.resolve({ data: baseScore() });
      }
      if (url === '/client/dashboard') {
        return Promise.resolve({ data: { properties: [] } });
      }
      if (url === '/client/requirements') {
        return Promise.resolve({
          data: {
            requirements: [{ requirement_id: 'r1', status: 'COMPLIANT' }],
          },
        });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });

    render(
      <MemoryRouter>
        <ComplianceScorePage />
      </MemoryRouter>,
    );

    await screen.findByTestId('compliance-score-page');
    expect(screen.queryByTestId('governance-ux-pilot-portfolio-supplement')).toBeNull();
    expect(screen.queryByTestId('governance-ux-pilot-export-note')).toBeNull();
  });
});
