/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ComplianceEvidenceResolveModal from './ComplianceEvidenceResolveModal';
import { clientAPI } from '../api/client';
import { toast } from '../utils/portalNotifications';

jest.mock('../api/client', () => ({
  clientAPI: {
    getRequirementEvidenceResolution: jest.fn(),
    uploadComplianceSupportingAttachment: jest.fn(),
    postComplianceEvidence: jest.fn(),
  },
}));

jest.mock('../utils/portalNotifications', () => ({
  toast: { success: jest.fn(), error: jest.fn(), warning: jest.fn() },
}));

const baseRequirement = { requirement_id: 'req-1', requirement_type: 'smoke_heat_alarms' };

describe('ComplianceEvidenceResolveModal TRUST-01', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clientAPI.getRequirementEvidenceResolution.mockResolvedValue({
      data: {
        allowed_evidence_modes: ['STRUCTURED_DECLARATION'],
        guided_methods: [{ evidence_mode: 'STRUCTURED_DECLARATION', label: 'Declaration' }],
        policy: { structured_declaration_checklist_schema: [] },
        operational_cognition: {
          read_only: true,
          cognition_version: 'operational_cognition_v1',
          forbidden_mutations: ['mark_compliant'],
          primary_action: {
            key: 'STRUCTURED_DECLARATION',
            label: 'Complete compliance declaration',
            hint: 'Strongest path',
            source: 'requirement_guidance_v1',
          },
          blockers: [],
          progression_state: { steps: [{ id: 'choose_method', label: 'Choose evidence method', status: 'current' }] },
          operational_truth_flags: {},
          requirement_guidance_v1: {
            strongest_evidence_method: 'STRUCTURED_DECLARATION',
            recommended_evidence_mode: 'STRUCTURED_DECLARATION',
            recommended_next_step: 'Complete compliance declaration',
            weaker_alternative_methods: [],
          },
        },
      },
    });
  });

  it('upload-only success does not imply requirement recorded', async () => {
    clientAPI.uploadComplianceSupportingAttachment.mockResolvedValue({
      data: { document_id: 'doc-1' },
    });
    render(
      <ComplianceEvidenceResolveModal
        open
        onOpenChange={jest.fn()}
        propertyId="prop-1"
        requirement={baseRequirement}
      />,
    );
    await waitFor(() => expect(screen.getByTestId('supporting-upload-truth-banner')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('Declaration')).toBeInTheDocument());
    const input = document.querySelector('input[type="file"]');
    const file = new File(['x'], 'proof.pdf', { type: 'application/pdf' });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /upload supporting files/i }));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(toast.success.mock.calls[0][0]).toMatch(/submit evidence/i);
    expect(clientAPI.postComplianceEvidence).not.toHaveBeenCalled();
  });

  it('shows existing submission banner and attribution toast when CER on file', async () => {
    clientAPI.uploadComplianceSupportingAttachment.mockResolvedValue({
      data: { document_id: 'doc-2' },
    });
    const rowWithCer = {
      requirement_id: 'req-1',
      requirement_type: 'occupation_contract',
      jurisdiction: 'Wales',
      evidence_authority: { primary_evidence_record_id: 'cer_existing' },
    };
    render(
      <ComplianceEvidenceResolveModal
        open
        onOpenChange={jest.fn()}
        propertyId="prop-1"
        requirement={rowWithCer}
      />,
    );
    expect(screen.getByTestId('existing-submission-on-file-banner')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Declaration')).toBeInTheDocument());
    const input = document.querySelector('input[type="file"]');
    fireEvent.change(input, { target: { files: [new File(['x'], 'proof.pdf', { type: 'application/pdf' })] } });
    fireEvent.click(screen.getByRole('button', { name: /upload supporting files/i }));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(toast.success.mock.calls[0][0]).toMatch(/existing submission/i);
    expect(toast.success.mock.calls[0][0]).not.toMatch(/requirement recorded/i);
  });

  it('post-submit summary uses authoritative evidence_record payload', async () => {
    clientAPI.postComplianceEvidence.mockResolvedValue({
      data: {
        workflow_complete: true,
        ok: true,
        authority_synced: true,
        evidence_record: {
          evidence_mode: 'STRUCTURED_DECLARATION',
          created_at: '2026-05-02',
          verification_status: 'PENDING',
          evidence_payload: {
            declaration_statement: 'Authoritative saved declaration',
            structured_fields: {},
          },
        },
      },
    });
    const onOpenChange = jest.fn();
    render(
      <ComplianceEvidenceResolveModal
        open
        onOpenChange={onOpenChange}
        propertyId="prop-1"
        requirement={baseRequirement}
      />,
    );
    await waitFor(() => expect(screen.getByText('Declaration')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('guided-evidence-mode-STRUCTURED_DECLARATION'));
    const declarationField = document.querySelector('[data-testid="compliance-evidence-resolve-modal"] textarea');
    fireEvent.change(declarationField, {
      target: { value: 'Authoritative saved declaration' },
    });
    fireEvent.click(screen.getByRole('button', { name: /submit evidence/i }));
    await waitFor(() => {
      expect(screen.getByTestId('compliance-evidence-submit-summary')).toBeInTheDocument();
    });
    expect(screen.getByText(/Authoritative saved declaration/)).toBeInTheDocument();
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
    fireEvent.click(screen.getByTestId('compliance-evidence-submit-summary-done'));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
