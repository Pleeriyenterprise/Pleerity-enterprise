/**
 * Integration: Requirements list + GuidedEvidenceModalProvider opens ComplianceEvidenceResolveModal
 * and loads allowed non-document evidence methods from the API.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import * as clientApiModule from '../api/client';
import RequirementsPage from './RequirementsPage';
import { GuidedEvidenceModalProvider } from '../context/GuidedEvidenceModalContext';

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useSearchParams: () => [new URLSearchParams(''), jest.fn()],
    useNavigate: () => jest.fn(),
  };
});

jest.mock('../contexts/EntitlementsContext', () => ({
  useEntitlements: () => ({ hasFeature: () => true }),
}));

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

const guidedRequirement = {
  requirement_id: 'req-guided-1',
  property_id: 'prop-1',
  requirement_type: 'smoke_heat_alarms',
  requirement_code: 'smoke_heat_alarms',
  compliance_requirement_class: 'DOCUMENT',
  status: 'PENDING',
  due_date: '2026-12-31T00:00:00.000Z',
  client_surface_visible: true,
  description: 'Smoke and heat alarms',
  take_action: {
    contract: 'requirement_take_action_v1',
    primary: {
      label: 'Resolve requirement',
      route: null,
      kind: 'guided_evidence_resolution',
      handler: 'guided_evidence',
      intent: 'guided_evidence_resolution',
      property_id: 'prop-1',
      requirement_id: 'req-guided-1',
    },
    secondary: {
      label: 'Upload document',
      route: '/documents?property_id=prop-1&requirement_id=req-guided-1',
      kind: 'navigate',
      handler: 'navigate',
      external: false,
      intent: 'upload_evidence',
    },
    supporting_external_links: [],
  },
};

function renderWithGuided() {
  return render(
    <GuidedEvidenceModalProvider>
      <RequirementsPage />
    </GuidedEvidenceModalProvider>,
  );
}

describe('RequirementsPage guided evidence modal', () => {
  beforeEach(() => {
    jest.spyOn(clientApiModule.clientAPI, 'getProperties').mockResolvedValue({
      data: {
        properties: [
          {
            property_id: 'prop-1',
            nickname: 'Test property',
            address_line_1: '1 Test Street',
          },
        ],
      },
    });
    jest.spyOn(clientApiModule.clientAPI, 'getRequirements').mockImplementation((params) =>
      Promise.resolve({
        data: {
          requirements: [guidedRequirement],
          presentation: { projection: params?.projection || 'full' },
        },
      }),
    );
    jest.spyOn(clientApiModule.clientAPI, 'getDocuments').mockResolvedValue({ data: { documents: [] } });
    jest.spyOn(clientApiModule.clientAPI, 'getRequirementEvidenceResolution').mockResolvedValue({
      data: {
        allowed_evidence_modes: ['STRUCTURED_DECLARATION', 'DOCUMENT_UPLOAD'],
        guided_methods: [
          {
            evidence_mode: 'STRUCTURED_DECLARATION',
            label: 'Structured declaration',
            checklist_schema: [
              { id: 'decl_ok', label: 'Declaration confirmed', answer_type: 'YES_NO', required: true },
            ],
          },
        ],
        primary_client_cta: 'Add compliance evidence',
      },
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('shows one guided CTA and opens modal with allowed evidence methods', async () => {
    renderWithGuided();

    await screen.findByText('1', { selector: '.tabular-nums' });
    expect(clientApiModule.clientAPI.getRequirements).toHaveBeenCalledWith(
      expect.objectContaining({ projection: 'full' }),
    );
    fireEvent.click(await screen.findByRole('button', { name: /Test property/i }));

    const guidedBtn = await screen.findByTestId('requirements-guided-open-req-guided-1');
    expect(guidedBtn).toHaveTextContent('Resolve requirement');

    fireEvent.click(guidedBtn);

    await waitFor(() => {
      expect(screen.getByTestId('compliance-evidence-resolve-modal')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(clientApiModule.clientAPI.getRequirementEvidenceResolution).toHaveBeenCalledWith('prop-1', 'req-guided-1');
    });

    await waitFor(() => {
      expect(screen.getByTestId('guided-evidence-mode-STRUCTURED_DECLARATION')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('guided-evidence-mode-STRUCTURED_DECLARATION'));
    expect(screen.getByText('Declaration confirmed')).toBeInTheDocument();
    expect(screen.getByText('Supporting evidence uploads')).toBeInTheDocument();
    expect(screen.queryByText('Structured fields (JSON object)')).not.toBeInTheDocument();
    expect(screen.queryByText('Checklist answers (JSON object)')).not.toBeInTheDocument();
  });
});
