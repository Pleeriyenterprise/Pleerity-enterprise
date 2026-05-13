import { todayTaskOperationalGuidance } from './todayTaskOperationalGuidance';

describe('todayTaskOperationalGuidance', () => {
  it('returns compliance-job guidance for COMPLIANCE work orders', () => {
    const g = todayTaskOperationalGuidance({
      source_type: 'work_order',
      metadata: { work_order_kind: 'COMPLIANCE' },
    });
    expect(g?.whyMatters).toMatch(/compliance requirement/i);
    expect(g?.whatToDo).toMatch(/Open the job/i);
  });

  it('returns maintenance guidance for non-compliance work orders', () => {
    const g = todayTaskOperationalGuidance({
      source_type: 'work_order',
      metadata: { work_order_kind: 'MAINTENANCE' },
    });
    expect(g?.whyMatters).toMatch(/repair or maintenance/i);
  });

  it('returns missing-evidence guidance for upload_evidence tasks', () => {
    const g = todayTaskOperationalGuidance({
      source_type: 'requirement',
      primary_action_type: 'upload_evidence',
      metadata: { action_type: 'missing_document' },
      filter_tags: ['compliance'],
    });
    expect(g?.whyMatters).toMatch(/cannot be treated as evidenced/i);
  });
});
