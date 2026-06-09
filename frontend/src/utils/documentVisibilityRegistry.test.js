import {
  documentAttentionRequired,
  filterDocumentsForQueueView,
} from './documentVisibilityRegistry';

describe('documentVisibilityRegistry', () => {
  it('includes linkage reconciliation docs in attention queue when visibility deferred', () => {
    const doc = {
      document_id: 'd-recon',
      document_linkage_state: 'RECONCILIATION_REQUIRED',
      linkage_reconciliation_required: true,
      visibility_projection_deferred: true,
    };
    expect(documentAttentionRequired(doc)).toBe(true);
    expect(filterDocumentsForQueueView([doc], 'attention')).toHaveLength(1);
  });

  it('excludes settled active evidence from attention queue', () => {
    const doc = {
      document_id: 'd-settled',
      document_attention_required: false,
      document_client_visibility_state: 'ACTIVE_EVIDENCE',
      document_linkage_state: 'LINKED',
    };
    expect(documentAttentionRequired(doc)).toBe(false);
    expect(filterDocumentsForQueueView([doc], 'attention')).toHaveLength(0);
  });
});
