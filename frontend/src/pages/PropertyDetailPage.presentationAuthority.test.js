/**
 * PROPERTY-DETAIL-PRESENTATION-AUTHORITY-ALIGNMENT-01
 * Presentation-only KPI alignment — document-backed, declaration, mixed, and jurisdiction scenarios.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import PropertyDetailPage from './PropertyDetailPage';
import { clientAPI } from '../api/client';
import { REPORTING_SEMANTICS_LABELS } from '../utils/reportingSemanticsLabels';

const mockNavigate = jest.fn();
const mockHasFeature = jest.fn(() => false);

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ propertyId: 'prop-mixed' }),
    useNavigate: () => mockNavigate,
  };
});

jest.mock('../utils/propertyCapabilityAccess', () => {
  const actual = jest.requireActual('../utils/propertyCapabilityAccess');
  return {
    ...actual,
    usePropertyWorkflowCapabilities: jest.fn(),
  };
});

const { usePropertyWorkflowCapabilities } = require('../utils/propertyCapabilityAccess');

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { portal_user_id: 'user-1', role: 'ROLE_CLIENT_ADMIN' } }),
}));

jest.mock('../context/GuidedEvidenceModalContext', () => ({
  useGuidedEvidenceModal: () => ({ openGuidedEvidence: jest.fn() }),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

function matrixRow(id, code, status, extra = {}) {
  return {
    requirement_id: id,
    property_id: 'prop-mixed',
    requirement_code: code,
    display_name: code,
    status,
    ...extra,
  };
}

function stubPropertyDetailApis(complianceDetail) {
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
  jest.spyOn(clientAPI, 'getComplianceDetail').mockResolvedValue({ data: complianceDetail });
}

describe('PropertyDetailPage presentation authority alignment', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    usePropertyWorkflowCapabilities.mockImplementation(() =>
      require('../testUtils/propertyWorkflowTestCapabilities').defaultPropertyWorkflowTestCaps(mockHasFeature),
    );
    mockNavigate.mockReset();
  });

  const scenarios = [
    {
      name: 'mixed document-backed and declaration (Wales-style)',
      kpis: { lifecycle_satisfied_count: 7, status_valid: 2, missing: 0, overdue: 0, expiring_30: 0, compliant: 5 },
      matrix: [
        matrixRow('r-eicr', 'eicr', 'COMPLIANT'),
        matrixRow('r-epc', 'epc', 'COMPLIANT'),
        matrixRow('r-leg', 'legionella', 'PENDING', { client_lifecycle_state: 'SATISFIED_UNVERIFIED' }),
        matrixRow('r-wales', 'occupation_contract_wales', 'PENDING', { client_lifecycle_state: 'SATISFIED_UNVERIFIED' }),
        matrixRow('r-fire', 'fire_risk', 'PENDING', { client_lifecycle_state: 'SATISFIED_UNVERIFIED' }),
        matrixRow('r-smoke', 'smoke_co', 'PENDING', { client_lifecycle_state: 'SATISFIED_UNVERIFIED' }),
        matrixRow('r-hmo', 'hmo_fire_risk', 'PENDING', { client_lifecycle_state: 'SATISFIED_UNVERIFIED' }),
      ],
      satisfiedDisplay: '7',
      validDisplay: '2',
      validFilterRows: 2,
    },
    {
      name: 'document-backed only (England)',
      kpis: { lifecycle_satisfied_count: 3, status_valid: 3, missing: 0, overdue: 0, expiring_30: 0, compliant: 3 },
      matrix: [
        matrixRow('r-eicr', 'eicr', 'COMPLIANT'),
        matrixRow('r-epc', 'epc', 'COMPLIANT'),
        matrixRow('r-gas', 'gas_safety', 'COMPLIANT'),
      ],
      satisfiedDisplay: '3',
      validDisplay: '3',
      validFilterRows: 3,
    },
    {
      name: 'declaration-only satisfied',
      kpis: { lifecycle_satisfied_count: 4, status_valid: 0, missing: 0, overdue: 0, expiring_30: 0, compliant: 4 },
      matrix: [
        matrixRow('r-leg', 'legionella', 'PENDING', { client_lifecycle_state: 'SATISFIED_UNVERIFIED' }),
        matrixRow('r-fire', 'fire_risk', 'PENDING', { client_lifecycle_state: 'SATISFIED_UNVERIFIED' }),
        matrixRow('r-smoke', 'smoke_co', 'PENDING', { client_lifecycle_state: 'SATISFIED_UNVERIFIED' }),
        matrixRow('r-hmo', 'hmo_fire_risk', 'PENDING', { client_lifecycle_state: 'SATISFIED_UNVERIFIED' }),
      ],
      satisfiedDisplay: '4',
      validDisplay: '0',
      validFilterRows: 0,
    },
    {
      name: 'mixed satisfied and overdue (Scotland)',
      kpis: { lifecycle_satisfied_count: 2, status_valid: 1, missing: 1, overdue: 1, expiring_30: 0, compliant: 1 },
      matrix: [
        matrixRow('r-eicr', 'eicr', 'COMPLIANT'),
        matrixRow('r-leg', 'legionella', 'PENDING', { client_lifecycle_state: 'SATISFIED_UNVERIFIED' }),
        matrixRow('r-gas', 'gas_safety', 'OVERDUE'),
        matrixRow('r-epc', 'epc', 'PENDING', { missing_required_document: true }),
      ],
      satisfiedDisplay: '2',
      validDisplay: '1',
      validFilterRows: 1,
    },
    {
      name: 'all satisfied non-HMO',
      kpis: { lifecycle_satisfied_count: 5, status_valid: 5, missing: 0, overdue: 0, expiring_30: 0, compliant: 5 },
      matrix: Array.from({ length: 5 }, (_, i) => matrixRow(`r-${i}`, `req_${i}`, 'COMPLIANT')),
      satisfiedDisplay: '5',
      validDisplay: '5',
      validFilterRows: 5,
    },
  ];

  it.each(scenarios)(
    '$name — shows governed labels and API counts without frontend inference',
    async ({ kpis, matrix, satisfiedDisplay, validDisplay, validFilterRows }) => {
      stubPropertyDetailApis({
        property_name: 'Test Property',
        matrix,
        kpis,
      });

      render(<PropertyDetailPage />);

      fireEvent.click(await screen.findByRole('button', { name: 'Compliance' }));

      const validLabel = REPORTING_SEMANTICS_LABELS.compliant_requirement_count.label;

      await waitFor(() => {
        expect(
          screen.getByRole('button', { name: new RegExp(`${validLabel} \\(${validDisplay}\\)`, 'i') }),
        ).toBeInTheDocument();
      });

      const satisfiedSpan = screen.getByTitle(REPORTING_SEMANTICS_LABELS.lifecycle_satisfied_count.tooltip);
      expect(satisfiedSpan.textContent).toContain(satisfiedDisplay);

      expect(screen.getByText(/may legitimately differ/i)).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: new RegExp(`${validLabel} \\(${validDisplay}\\)`, 'i') }));

      if (validFilterRows === 0) {
        await waitFor(() => {
          expect(screen.getByText(/No requirements match what you are viewing/i)).toBeInTheDocument();
        });
      } else {
        await waitFor(() => {
          expect(screen.getAllByRole('row').length).toBeGreaterThan(validFilterRows);
        });
      }
    },
  );

  it('Operating hub shows Requirements satisfied and Valid for scoring tiles from API', async () => {
    stubPropertyDetailApis({
      property_name: 'Cathedral View',
      matrix: [
        matrixRow('r-eicr', 'eicr', 'COMPLIANT'),
        matrixRow('r-epc', 'epc', 'COMPLIANT'),
        matrixRow('r-leg', 'legionella', 'PENDING', { client_lifecycle_state: 'SATISFIED_UNVERIFIED' }),
      ],
      kpis: { lifecycle_satisfied_count: 7, status_valid: 2, missing: 0, overdue: 0, expiring_30: 0, compliant: 5 },
    });

    render(<PropertyDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Requirements satisfied')).toBeInTheDocument();
      expect(screen.getByText('Valid for scoring')).toBeInTheDocument();
    });

    const satisfiedTiles = screen.getAllByText('7');
    const validTiles = screen.getAllByText('2');
    expect(satisfiedTiles.length).toBeGreaterThan(0);
    expect(validTiles.length).toBeGreaterThan(0);
  });
});
