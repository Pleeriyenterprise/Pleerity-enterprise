/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import RequirementIntelligenceModal from './RequirementIntelligenceModal';
import { GuidedEvidenceModalProvider } from '../../context/GuidedEvidenceModalContext';
import { clientAPI } from '../../api/client';

jest.mock('../../api/client', () => ({
  clientAPI: {
    getRequirementWorkflow: jest.fn(),
    listComplianceEvidence: jest.fn(),
    getDocuments: jest.fn(),
  },
}));

function mockMatchMedia(matchesMobile) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: jest.fn().mockImplementation((query) => ({
      matches: query.includes('639') ? matchesMobile : false,
      media: query,
      onchange: null,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      addListener: jest.fn(),
      removeListener: jest.fn(),
      dispatchEvent: jest.fn(),
    })),
  });
}

function domOrderBefore(a, b) {
  const position = a.compareDocumentPosition(b);
  return (position & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
}

const viewSubmissionWorkflowPayload = {
  requirement: {
    requirement_id: 'req-sub',
    property_id: 'prop-sub',
    display_label: 'Right to rent',
    requirement_type: 'right_to_rent',
    workflow_status: 'PENDING_REVIEW',
    compliance_state: 'PENDING',
    client_lifecycle_state: 'PENDING_REVIEW',
    take_action: {
      primary: {
        label: 'View submission',
        route: null,
        handler: 'guided_evidence',
      },
      supporting_external_links: [],
    },
  },
  active_compliance_job: null,
};

jest.mock('./RequirementModalAssuranceSection', () => ({
  __esModule: true,
  default: () => <section data-testid="requirement-modal-assurance-section" />,
}));

jest.mock('./RequirementSubmissionInspectPanel', () => {
  const React = require('react');
  return {
    __esModule: true,
    default: React.forwardRef(function MockPanel(props, ref) {
      return (
        <section ref={ref} data-testid="requirement-submission-inspect-panel">
          <h3>{props.panelTitle || 'Your submission'}</h3>
          <p data-testid="submission-inspect-content">Persisted declaration text</p>
        </section>
      );
    }),
  };
});

describe('RequirementIntelligenceModal', () => {
  const noop = () => {};
  const wrap = (ui) => <GuidedEvidenceModalProvider>{ui}</GuidedEvidenceModalProvider>;

  beforeEach(() => {
    clientAPI.listComplianceEvidence.mockResolvedValue({ data: { evidence_records: [] } });
    clientAPI.getDocuments.mockResolvedValue({ data: { documents: [] } });
  });

  it('shows submission panel and converged actions when CER exists (view submission context)', async () => {
    clientAPI.listComplianceEvidence.mockResolvedValue({
      data: {
        evidence_records: [{ evidence_record_id: 'cer_1', evidence_mode: 'STRUCTURED_DECLARATION' }],
      },
    });
    clientAPI.getRequirementWorkflow.mockResolvedValue({
      data: {
        requirement: {
          requirement_id: 'req-sub',
          property_id: 'prop-sub',
          display_label: 'Right to rent',
          requirement_type: 'right_to_rent',
          workflow_status: 'PENDING_REVIEW',
          compliance_state: 'PENDING',
          client_lifecycle_state: 'PENDING_REVIEW',
          take_action: {
            primary: {
              label: 'View submission',
              route: null,
              handler: 'guided_evidence',
            },
            supporting_external_links: [],
          },
        },
        active_compliance_job: null,
      },
    });

    const scrollIntoView = jest.fn();
    window.HTMLElement.prototype.scrollIntoView = scrollIntoView;

    render(
      wrap(
        <RequirementIntelligenceModal
          open
          requirementId="req-sub"
          seedRequirement={{
            property_id: 'prop-sub',
            requirement_id: 'req-sub',
            primary_evidence_record_id: 'cer_1',
          }}
          initialFocusSubmission
          onClose={noop}
          onNavigate={noop}
        />,
      ),
    );

    await waitFor(() => {
      expect(screen.getByTestId('requirement-submission-inspect-panel')).toBeInTheDocument();
    });
    expect(screen.getByText('Submission on file')).toBeInTheDocument();
    expect(screen.getByTestId('requirement-modal-context-hero-headline')).toHaveTextContent('Awaiting platform review');
    expect(screen.getByTestId('requirement-intel-update-submission')).toHaveTextContent('Update submission');
    expect(screen.queryByTestId('requirement-intel-view-submission')).not.toBeInTheDocument();
    expect(screen.getByTestId('requirement-intel-link-add_supporting_evidence')).toHaveTextContent('Add supporting evidence');
  });

  it('places submission details before informational guidance sections on mobile', async () => {
    mockMatchMedia(true);
    clientAPI.listComplianceEvidence.mockResolvedValue({
      data: {
        evidence_records: [{ evidence_record_id: 'cer_1', evidence_mode: 'STRUCTURED_DECLARATION' }],
      },
    });
    clientAPI.getRequirementWorkflow.mockResolvedValue({ data: viewSubmissionWorkflowPayload });

    render(
      wrap(
        <RequirementIntelligenceModal
          open
          requirementId="req-sub"
          seedRequirement={{
            property_id: 'prop-sub',
            requirement_id: 'req-sub',
            primary_evidence_record_id: 'cer_1',
          }}
          initialFocusSubmission
          onClose={noop}
          onNavigate={noop}
          onMarkNotApplicable={noop}
        />,
      ),
    );

    await waitFor(() => {
      expect(screen.getByTestId('requirement-submission-inspect-panel')).toBeInTheDocument();
    });

    const submissionPanel = screen.getByTestId('requirement-submission-inspect-panel');
    const whySection = screen.queryByTestId('requirement-intel-section-why');
    if (whySection) {
      expect(domOrderBefore(submissionPanel, whySection)).toBe(true);
    }
    expect(screen.queryByTestId('requirement-intel-section-what')).not.toBeInTheDocument();
  });

  it('shows NA governance disclosure collapsed by default on mobile with actions above it', async () => {
    mockMatchMedia(true);
    clientAPI.listComplianceEvidence.mockResolvedValue({
      data: {
        evidence_records: [{ evidence_record_id: 'cer_1', evidence_mode: 'STRUCTURED_DECLARATION' }],
      },
    });
    clientAPI.getRequirementWorkflow.mockResolvedValue({ data: viewSubmissionWorkflowPayload });

    render(
      wrap(
        <RequirementIntelligenceModal
          open
          requirementId="req-sub"
          seedRequirement={{
            property_id: 'prop-sub',
            requirement_id: 'req-sub',
            primary_evidence_record_id: 'cer_1',
          }}
          initialFocusSubmission
          onClose={noop}
          onNavigate={noop}
          onMarkNotApplicable={noop}
        />,
      ),
    );

    await waitFor(() => {
      expect(screen.getByTestId('requirement-intel-update-submission')).toBeInTheDocument();
    });

    const updateButton = screen.getByTestId('requirement-intel-update-submission');
    const disclosure = screen.getByTestId('na-governed-disclosure-trigger');
    expect(domOrderBefore(updateButton, disclosure)).toBe(true);
    expect(disclosure).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByTestId('governed-not-applicable-compact-copy')).not.toBeInTheDocument();
  });

  it('shows NA governance disclosure expanded by default on desktop', async () => {
    mockMatchMedia(false);
    clientAPI.listComplianceEvidence.mockResolvedValue({
      data: {
        evidence_records: [{ evidence_record_id: 'cer_1', evidence_mode: 'STRUCTURED_DECLARATION' }],
      },
    });
    clientAPI.getRequirementWorkflow.mockResolvedValue({ data: viewSubmissionWorkflowPayload });

    render(
      wrap(
        <RequirementIntelligenceModal
          open
          requirementId="req-sub"
          seedRequirement={{
            property_id: 'prop-sub',
            requirement_id: 'req-sub',
            primary_evidence_record_id: 'cer_1',
          }}
          initialFocusSubmission
          onClose={noop}
          onNavigate={noop}
          onMarkNotApplicable={noop}
        />,
      ),
    );

    await waitFor(() => {
      expect(screen.getByTestId('na-governed-disclosure-trigger')).toHaveAttribute('aria-expanded', 'true');
    });
    expect(screen.getByTestId('governed-not-applicable-compact-copy')).toBeVisible();
  });

  it('toggles NA governance disclosure and keeps full compliance copy available', async () => {
    mockMatchMedia(true);
    clientAPI.listComplianceEvidence.mockResolvedValue({
      data: {
        evidence_records: [{ evidence_record_id: 'cer_1', evidence_mode: 'STRUCTURED_DECLARATION' }],
      },
    });
    clientAPI.getRequirementWorkflow.mockResolvedValue({ data: viewSubmissionWorkflowPayload });

    render(
      wrap(
        <RequirementIntelligenceModal
          open
          requirementId="req-sub"
          seedRequirement={{
            property_id: 'prop-sub',
            requirement_id: 'req-sub',
            primary_evidence_record_id: 'cer_1',
          }}
          initialFocusSubmission
          onClose={noop}
          onNavigate={noop}
          onMarkNotApplicable={noop}
        />,
      ),
    );

    await waitFor(() => {
      expect(screen.getByTestId('na-governed-disclosure-trigger')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('na-governed-disclosure-trigger'));
    expect(screen.getByTestId('governed-not-applicable-compact-copy')).toBeVisible();
    expect(screen.getByTestId('governed-not-applicable-compact-copy')).toHaveTextContent(
      /The requirement stays on record/i,
    );
  });

  it('keeps primary footer actions visible without opening disclosure on mobile viewport', async () => {
    mockMatchMedia(true);
    clientAPI.listComplianceEvidence.mockResolvedValue({
      data: {
        evidence_records: [{ evidence_record_id: 'cer_1', evidence_mode: 'STRUCTURED_DECLARATION' }],
      },
    });
    clientAPI.getRequirementWorkflow.mockResolvedValue({ data: viewSubmissionWorkflowPayload });

    render(
      wrap(
        <RequirementIntelligenceModal
          open
          requirementId="req-sub"
          seedRequirement={{
            property_id: 'prop-sub',
            requirement_id: 'req-sub',
            primary_evidence_record_id: 'cer_1',
          }}
          initialFocusSubmission
          onClose={noop}
          onNavigate={noop}
          onMarkNotApplicable={noop}
        />,
      ),
    );

    await waitFor(() => {
      expect(screen.getByTestId('requirement-intel-primary-actions')).toBeInTheDocument();
    });

    expect(screen.getByTestId('requirement-intel-update-submission')).toBeVisible();
    expect(screen.getByTestId('requirement-intel-link-add_supporting_evidence')).toBeVisible();
    expect(screen.getByTestId('requirement-intel-link-view_documents')).toBeVisible();
  });

  it('renders published why_it_matters, published links, canonical primary CTA, and human workflow labels', async () => {
    clientAPI.getRequirementWorkflow.mockResolvedValue({
      data: {
        requirement: {
          requirement_id: 'req-1',
          property_id: 'prop-1',
          display_label: 'HMO licence',
          workflow_status: 'ACTION_REQUIRED',
          compliance_state: 'MISSING',
          workflow_status_label: 'Action required',
          compliance_state_label: 'Evidence missing',
          take_action: {
            primary: {
              label: 'Upload evidence from API',
              route: '/documents?property_id=prop-1&requirement_id=req-1',
              handler: 'navigate',
            },
            supporting_external_links: [],
          },
          registry_metadata: {
            why_it_matters_short_published: 'Published why line',
            action_links_published: [{ label: 'Guidance', url: 'https://example.com/guidance' }],
            primary_action_mode: 'document_upload',
            evidence_resolution: { allowed_evidence_modes: ['DOCUMENT_UPLOAD'] },
          },
        },
        active_compliance_job: null,
      },
    });

    render(
      wrap(
        <RequirementIntelligenceModal
          open
          requirementId="req-1"
          seedRequirement={null}
          onClose={noop}
          onNavigate={noop}
        />,
      ),
    );

    await waitFor(() => {
      expect(screen.queryByTestId('requirement-intel-loading')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('requirement-intel-published-why-badge')).toBeInTheDocument();
    expect(screen.getByTestId('requirement-intel-why-short')).toHaveTextContent('Published why line');
    expect(screen.getByTestId('requirement-intel-action-links')).toHaveTextContent('Guidance');
    expect(screen.getByTestId('requirement-intel-primary-cta')).toHaveTextContent('Upload evidence from API');
    expect(screen.getByTestId('requirement-intel-workflow-label')).toHaveTextContent('Action needed');
    expect(screen.getByTestId('requirement-intel-compliance-label')).toHaveTextContent('Missing required evidence');
    expect(screen.queryByTestId('requirement-intel-published-cta-mode')).not.toBeInTheDocument();

    expect(screen.queryByText('MISSING')).not.toBeInTheDocument();
    expect(screen.queryByText('ACTION_REQUIRED')).not.toBeInTheDocument();
    expect(screen.queryByText(/Request help/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Book inspection/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('requirement-intel-section-accepted-evidence')).toBeInTheDocument();
    expect(screen.getByText('Document upload')).toBeInTheDocument();
  });

  it('does not render raw UNKNOWN in applicability section', async () => {
    clientAPI.getRequirementWorkflow.mockResolvedValue({
      data: {
        requirement: {
          requirement_id: 'req-u',
          property_id: 'prop-u',
          display_label: 'Test req',
          applicability: 'UNKNOWN',
          workflow_status: 'IN_PROGRESS',
          compliance_state: 'VALID',
          take_action: {
            primary: { label: 'Act', route: '/documents?property_id=prop-u&requirement_id=req-u', handler: 'navigate' },
            supporting_external_links: [],
          },
        },
        active_compliance_job: null,
      },
    });

    render(
      wrap(<RequirementIntelligenceModal open requirementId="req-u" seedRequirement={null} onClose={noop} onNavigate={noop} />),
    );

    await waitFor(() => {
      expect(screen.queryByTestId('requirement-intel-loading')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('requirement-intel-applicability-human')).toBeInTheDocument();
    expect(screen.getByTestId('requirement-intel-applicability-human').textContent).not.toMatch(/\bUNKNOWN\b/i);
  });

  it('shows jurisdiction-specific published why with label (not other regions)', async () => {
    clientAPI.getRequirementWorkflow.mockResolvedValue({
      data: {
        requirement: {
          requirement_id: 'req-2',
          property_id: 'prop-2',
          display_label: 'EPC',
          property_jurisdiction: 'England',
          workflow_status: 'ACTION_REQUIRED',
          compliance_state: 'MISSING',
          workflow_status_label: 'Action required',
          compliance_state_label: 'Evidence missing',
          take_action: {
            primary: { label: 'Act', route: '/documents?property_id=prop-2&requirement_id=req-2', handler: 'navigate' },
            supporting_external_links: [],
          },
          registry_metadata: {
            why_it_matters_by_jurisdiction_published: {
              England: { why_it_matters_short: 'England EPC copy', why_it_matters_long: 'England long' },
              Wales: { why_it_matters_short: 'Wales must not render' },
            },
            why_it_matters_short_published: 'Flat fallback',
          },
        },
        active_compliance_job: null,
      },
    });

    render(
      wrap(<RequirementIntelligenceModal open requirementId="req-2" seedRequirement={null} onClose={noop} onNavigate={noop} />),
    );

    await waitFor(() => {
      expect(screen.queryByTestId('requirement-intel-loading')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('requirement-intel-jurisdiction-why-badge')).toHaveTextContent('Based on England rules');
    expect(screen.getByTestId('requirement-intel-why-short')).toHaveTextContent('England EPC copy');
    expect(screen.queryByText('Wales must not render')).not.toBeInTheDocument();
    expect(screen.queryByText('Flat fallback')).not.toBeInTheDocument();
  });

  it('uses resolved evidence semantics for guided declaration rows', async () => {
    clientAPI.getRequirementWorkflow.mockResolvedValue({
      data: {
        requirement: {
          requirement_id: 'req-gd',
          property_id: 'prop-gd',
          display_label: 'Right to rent',
          workflow_class: 'GUIDED_DECLARATION',
          status: 'MISSING',
          workflow_status: 'ACTION_REQUIRED',
          compliance_state: 'MISSING',
          take_action: {
            primary: {
              label: 'Record declaration',
              route: '/properties/prop-gd?open=resolve&requirement_id=req-gd',
              handler: 'guided_evidence',
            },
            supporting_external_links: [],
          },
        },
        active_compliance_job: null,
      },
    });

    render(
      wrap(<RequirementIntelligenceModal open requirementId="req-gd" seedRequirement={null} onClose={noop} onNavigate={noop} />),
    );

    await waitFor(() => {
      expect(screen.queryByTestId('requirement-intel-loading')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('requirement-intel-evidence-label')).toHaveTextContent(
      'Declaration not recorded — action required',
    );
    expect(screen.getByTestId('requirement-intel-primary-cta')).toHaveTextContent('Record declaration');
  });

  it('shows assurance section for self-recorded review context', async () => {
    clientAPI.listComplianceEvidence.mockResolvedValue({
      data: {
        evidence_records: [
          {
            evidence_record_id: 'cer-op',
            evidence_mode: 'STRUCTURED_DECLARATION',
            verification_status: 'PENDING_REVIEW',
          },
        ],
      },
    });
    clientAPI.getRequirementWorkflow.mockResolvedValue({
      data: {
        requirement: {
          requirement_id: 'req-op',
          property_id: 'prop-op',
          display_label: 'Landlord registration',
          assurance_tier: 'SELF_RECORDED',
          governance_family: 'SELF_CERTIFIED',
          truth_presentation_stage: 'declaration_recorded',
          take_action: { primary: { label: 'View submission', handler: 'guided_evidence' }, supporting_external_links: [] },
        },
        active_compliance_job: null,
      },
    });

    render(
      wrap(
        <RequirementIntelligenceModal
          open
          requirementId="req-op"
          seedRequirement={{
            property_id: 'prop-op',
            requirement_id: 'req-op',
            assurance_tier: 'SELF_RECORDED',
            primary_evidence_record_id: 'cer-op',
          }}
          showAssuranceContext
          onClose={noop}
          onNavigate={noop}
        />,
      ),
    );

    await waitFor(() => {
      expect(screen.getByTestId('requirement-modal-assurance-section')).toBeInTheDocument();
    });
  });
});
