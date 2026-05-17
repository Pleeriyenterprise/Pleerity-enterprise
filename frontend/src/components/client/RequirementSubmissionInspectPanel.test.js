/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import RequirementSubmissionInspectPanel from './RequirementSubmissionInspectPanel';
import { clientAPI } from '../../api/client';

jest.mock('../../api/client', () => ({
  clientAPI: {
    listComplianceEvidence: jest.fn(),
    getDocuments: jest.fn(),
  },
}));

describe('RequirementSubmissionInspectPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clientAPI.listComplianceEvidence.mockResolvedValue({
      data: {
        evidence_records: [
          {
            evidence_record_id: 'cer_1',
            evidence_mode: 'STRUCTURED_DECLARATION',
            created_at: '2026-05-01T10:00:00Z',
            verification_status: 'PENDING',
            evidence_payload: {
              declaration_statement: 'Persisted declaration text',
              structured_fields: { check_date: '2026-04-01' },
            },
            linked_document_ids: [],
          },
        ],
      },
    });
    clientAPI.getDocuments.mockResolvedValue({ data: { documents: [] } });
  });

  it('renders latest CER payload from listComplianceEvidence', async () => {
    render(<RequirementSubmissionInspectPanel propertyId="prop-1" requirementId="req-1" />);
    await waitFor(() => {
      expect(screen.getByTestId('submission-inspect-content')).toBeInTheDocument();
    });
    expect(screen.getByText('Persisted declaration text')).toBeInTheDocument();
    expect(screen.getByText('Your submission')).toBeInTheDocument();
    expect(clientAPI.listComplianceEvidence).toHaveBeenCalledWith('prop-1', 'req-1');
  });
});
