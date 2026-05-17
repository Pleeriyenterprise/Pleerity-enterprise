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
    await waitFor(() => expect(screen.getByText('Declaration')).toBeInTheDocument());
    const input = document.querySelector('input[type="file"]');
    const file = new File(['x'], 'proof.pdf', { type: 'application/pdf' });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /upload supporting files/i }));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(toast.success.mock.calls[0][0]).toMatch(/complete and submit the form below/i);
    expect(clientAPI.postComplianceEvidence).not.toHaveBeenCalled();
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
