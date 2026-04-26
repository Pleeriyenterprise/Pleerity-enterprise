/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import RequirementIntelligenceModal from './RequirementIntelligenceModal';
import { clientAPI } from '../../api/client';

jest.mock('../../api/client', () => ({
  clientAPI: {
    getRequirementWorkflow: jest.fn(),
  },
}));

describe('RequirementIntelligenceModal', () => {
  const noop = () => {};

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
          },
        },
        active_compliance_job: null,
      },
    });

    render(
      <RequirementIntelligenceModal
        open
        requirementId="req-1"
        seedRequirement={null}
        onClose={noop}
        onNavigate={noop}
      />,
    );

    await waitFor(() => {
      expect(screen.queryByTestId('requirement-intel-loading')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('requirement-intel-published-why-badge')).toBeInTheDocument();
    expect(screen.getByTestId('requirement-intel-why-short')).toHaveTextContent('Published why line');
    expect(screen.getByTestId('requirement-intel-action-links')).toHaveTextContent('Guidance');
    expect(screen.getByTestId('requirement-intel-primary-cta')).toHaveTextContent('Upload evidence from API');
    expect(screen.getByTestId('requirement-intel-workflow-label')).toHaveTextContent('Action required');
    expect(screen.getByTestId('requirement-intel-compliance-label')).toHaveTextContent('Evidence missing');
    expect(screen.getByTestId('requirement-intel-published-cta-mode')).toHaveTextContent('document_upload');

    expect(screen.queryByText('MISSING')).not.toBeInTheDocument();
    expect(screen.queryByText('ACTION_REQUIRED')).not.toBeInTheDocument();
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
      <RequirementIntelligenceModal open requirementId="req-2" seedRequirement={null} onClose={noop} onNavigate={noop} />,
    );

    await waitFor(() => {
      expect(screen.queryByTestId('requirement-intel-loading')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('requirement-intel-jurisdiction-why-badge')).toHaveTextContent('Based on England rules');
    expect(screen.getByTestId('requirement-intel-why-short')).toHaveTextContent('England EPC copy');
    expect(screen.queryByText('Wales must not render')).not.toBeInTheDocument();
    expect(screen.queryByText('Flat fallback')).not.toBeInTheDocument();
  });
});
