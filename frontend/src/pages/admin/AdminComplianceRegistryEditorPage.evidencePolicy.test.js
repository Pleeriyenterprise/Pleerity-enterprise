import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AdminComplianceRegistryEditorPage from './AdminComplianceRegistryEditorPage';
import { adminAPI } from '../../api/client';

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ entryId: 'entry-1' }),
    Link: ({ children }) => <span>{children}</span>,
  };
});

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ isOwner: () => true, isAdmin: () => true }),
}));

jest.mock('../../components/admin/UnifiedAdminLayout', () => ({ children }) => <div>{children}</div>);
jest.mock('../../components/admin/PrepareRegistryPublishDialog', () => () => null);
jest.mock('../../components/admin/RegistryActionLinksForm', () => () => <div>links-form</div>);
jest.mock('../../components/admin/RegistryConditionsBuilder', () => () => <div>conditions-builder</div>);

jest.mock('@/utils/portalNotifications', () => ({
  toast: { error: jest.fn(), success: jest.fn(), info: jest.fn() },
}));

const baseDraft = {
  entry_id: 'entry-1',
  canonical_code: 'GAS_SAFETY',
  scope_key: 'DEFAULT',
  identity: { name: 'Gas Safety', category: 'REGULATORY' },
  classification: { requirement_type: 'DOCUMENT', criticality: 'HIGH', requires_document: true, requires_job: false, client_surface_visible: true },
  jurisdiction: { display_jurisdictions: ['ENGLAND'] },
  conditions: { logic: 'ALL', rules: [] },
  frequency: { frequency_days: 365, reminder_lead_days: 30 },
  action_behaviour: { primary_action_mode: 'upload_document', cta_label_override: '' },
  action_links: [],
  why_it_matters_short: 'Statutory gas safety compliance.',
  why_it_matters_long: '',
  governance: { needs_review_fields: [] },
};

describe('AdminComplianceRegistryEditorPage evidence policy controls', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    jest.spyOn(adminAPI, 'getComplianceRegistryDraft').mockResolvedValue({ data: baseDraft });
    jest.spyOn(adminAPI, 'getComplianceRegistryDraftCompare').mockResolvedValue({ data: { diff: [] } });
    jest.spyOn(adminAPI, 'getComplianceRegistryControlledFieldOptions').mockResolvedValue({
      data: {
        identity_categories: [{ value: 'REGULATORY', label: 'Regulatory' }],
        requirement_types: [{ value: 'DOCUMENT', label: 'Document' }],
        criticality: [{ value: 'HIGH', label: 'High' }],
        uk_display_regions: [{ value: 'ENGLAND', label: 'England' }],
        primary_action_modes: [{ value: 'upload_document', label: 'Upload document' }],
        evidence_modes: [
          { value: 'DOCUMENT_UPLOAD', label: 'Document upload' },
          { value: 'STRUCTURED_DECLARATION', label: 'Structured declaration' },
        ],
        evidence_resolution_workflows: [{ value: 'GUIDED_EVIDENCE_RESOLUTION', label: 'Guided evidence resolution' }],
        allowed_upload_types: [{ value: 'application/pdf', label: 'application/pdf' }],
      },
    });
    jest.spyOn(adminAPI, 'patchComplianceRegistryDraft').mockResolvedValue({ data: baseDraft });
  });

  it('renders evidence resolution policy section with default label', async () => {
    render(<AdminComplianceRegistryEditorPage />);
    await screen.findByText('Evidence Resolution Policy');
    expect(screen.getAllByText('Using default evidence policy').length).toBeGreaterThan(0);
  });

  it('updates draft payload evidence_resolution when modes selected', async () => {
    render(<AdminComplianceRegistryEditorPage />);
    await screen.findByText('Evidence Resolution Policy');

    fireEvent.click(screen.getByLabelText(/Document upload/i));
    fireEvent.click(screen.getByLabelText(/Structured declaration/i));
    fireEvent.click(screen.getByRole('button', { name: /Save draft/i }));

    await waitFor(() => {
      expect(adminAPI.patchComplianceRegistryDraft).toHaveBeenCalled();
    });
    const payload = adminAPI.patchComplianceRegistryDraft.mock.calls[0][1];
    expect(payload.patch.evidence_resolution.allowed_evidence_modes).toEqual(
      expect.arrayContaining(['DOCUMENT_UPLOAD', 'STRUCTURED_DECLARATION']),
    );
  });
});
