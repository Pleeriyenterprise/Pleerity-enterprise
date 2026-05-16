import { resolveClientRequirementLifecycle } from './clientRequirementLifecycle';

describe('resolveClientRequirementLifecycle', () => {
  it('prefers API client_lifecycle_state', () => {
    const row = {
      client_lifecycle_state: 'PENDING_REVIEW',
      client_lifecycle_label: 'Evidence submitted — review pending',
      client_lifecycle_reason_codes: ['EA_PENDING_ADMIN_REVIEW'],
      status: 'PENDING',
    };
    const r = resolveClientRequirementLifecycle(row);
    expect(r.state).toBe('PENDING_REVIEW');
    expect(r.source).toBe('api');
    expect(r.label).toContain('review');
  });

  it('falls back to pending with linked document', () => {
    const r = resolveClientRequirementLifecycle({
      status: 'PENDING',
      evidence_doc_id: 'd1',
    });
    expect(r.state).toBe('PENDING_REVIEW');
    expect(r.source).toBe('fallback');
  });
});
