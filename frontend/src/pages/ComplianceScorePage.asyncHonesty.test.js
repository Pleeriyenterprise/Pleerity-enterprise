import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ComplianceScorePage from './ComplianceScorePage';
import { COMPLIANCE_SCORE_DRIVERS_VS_HEADLINE_NOTE } from '../utils/scoreFreshnessUi';
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
    stats: { total_requirements: 1, compliant: 0, expiring_soon: 0, overdue: 1 },
    properties_count: 1,
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
    ...overrides,
  };
}

describe('ComplianceScorePage async honesty (slice 1)', () => {
  beforeEach(() => {
    api.get.mockReset();
  });

  it('shows persisted-vs-live note when score drivers are present', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/client/compliance-score') {
        return Promise.resolve({ data: baseScore() });
      }
      if (url === '/client/dashboard') {
        return Promise.resolve({ data: { properties: [{ property_id: 'p1' }] } });
      }
      if (url === '/client/requirements') {
        return Promise.resolve({ data: { requirements: [] } });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });

    render(
      <MemoryRouter>
        <ComplianceScorePage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('compliance-score-drivers-persisted-note')).toHaveTextContent(
      COMPLIANCE_SCORE_DRIVERS_VS_HEADLINE_NOTE,
    );
  });

  it('surfaces score_status_message near headline when API provides it', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/client/compliance-score') {
        return Promise.resolve({
          data: baseScore({
            drivers: [],
            score_status: 'partial',
            score_status_message: 'Portfolio averages 1 of 2 properties.',
          }),
        });
      }
      if (url === '/client/dashboard') {
        return Promise.resolve({ data: { properties: [] } });
      }
      if (url === '/client/requirements') {
        return Promise.resolve({ data: { requirements: [] } });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });

    render(
      <MemoryRouter>
        <ComplianceScorePage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('compliance-score-status-message')).toHaveTextContent(
      'Portfolio averages 1 of 2 properties.',
    );
  });
});
