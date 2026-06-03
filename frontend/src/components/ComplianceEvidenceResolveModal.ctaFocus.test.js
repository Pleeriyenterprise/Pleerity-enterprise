/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ComplianceEvidenceResolveModal from './ComplianceEvidenceResolveModal';
import { clientAPI } from '../api/client';
import { focusModalCtaTarget } from '../utils/requirementModalCtaFocus';

jest.mock('../utils/requirementModalCtaFocus', () => {
  const actual = jest.requireActual('../utils/requirementModalCtaFocus');
  return {
    ...actual,
    focusModalCtaTarget: jest.fn(actual.focusModalCtaTarget),
  };
});

jest.mock('../api/client', () => ({
  clientAPI: {
    getRequirementEvidenceResolution: jest.fn(),
    uploadComplianceSupportingAttachment: jest.fn(),
    postComplianceEvidence: jest.fn(),
  },
}));

const baseCognition = {
  read_only: true,
  cognition_version: 'operational_cognition_v1',
  primary_action: {
    key: 'STRUCTURED_DECLARATION',
    label: 'Complete compliance declaration',
    hint: 'Strongest path',
    source: 'requirement_guidance_v1',
  },
  requirement_guidance_v1: {
    strongest_evidence_method: 'STRUCTURED_DECLARATION',
    recommended_evidence_mode: 'STRUCTURED_DECLARATION',
    recommended_next_step: 'Complete compliance declaration',
  },
};

describe('ComplianceEvidenceResolveModal CTA focus', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    const actual = jest.requireActual('../utils/requirementModalCtaFocus');
    focusModalCtaTarget.mockImplementation(actual.focusModalCtaTarget);
    clientAPI.getRequirementEvidenceResolution.mockResolvedValue({
      data: {
        allowed_evidence_modes: ['STRUCTURED_DECLARATION'],
        guided_methods: [{ evidence_mode: 'STRUCTURED_DECLARATION', label: 'Declaration' }],
        policy: { structured_declaration_checklist_schema: [] },
        operational_cognition: baseCognition,
      },
    });
  });

  it('scrolls to declaration form when hero CTA is clicked', async () => {
    focusModalCtaTarget.mockImplementation(() => true);
    render(
      <ComplianceEvidenceResolveModal
        open
        onOpenChange={jest.fn()}
        propertyId="prop-1"
        requirement={{ requirement_id: 'req-1', requirement_type: 'smoke_heat_alarms' }}
      />,
    );
    await waitFor(() => expect(screen.getByTestId('next-action-hero-primary')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('next-action-hero-primary'));
    await waitFor(() => expect(focusModalCtaTarget).toHaveBeenCalled());
    expect(focusModalCtaTarget.mock.calls[0][0].ctaKey).toBe('complete_compliance_declaration');
  });

  it('shows fallback when focus target is missing', async () => {
    focusModalCtaTarget.mockImplementation(() => false);
    clientAPI.getRequirementEvidenceResolution.mockResolvedValue({
      data: {
        allowed_evidence_modes: ['STRUCTURED_DECLARATION'],
        guided_methods: [{ evidence_mode: 'STRUCTURED_DECLARATION', label: 'Declaration' }],
        policy: { structured_declaration_checklist_schema: [] },
        operational_cognition: {
          ...baseCognition,
          primary_action: { key: 'unknown', label: 'Attach supporting files' },
          requirement_guidance_v1: {
            ...baseCognition.requirement_guidance_v1,
            recommended_evidence_mode: null,
          },
        },
      },
    });
    render(
      <ComplianceEvidenceResolveModal
        open
        onOpenChange={jest.fn()}
        propertyId="prop-1"
        requirement={{ requirement_id: 'req-1', requirement_type: 'legionella' }}
      />,
    );
    await waitFor(() => expect(screen.getByTestId('next-action-hero-primary')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('next-action-hero-primary'));
    await waitFor(() => expect(screen.getByTestId('modal-cta-focus-fallback')).toBeInTheDocument());
  });
});
