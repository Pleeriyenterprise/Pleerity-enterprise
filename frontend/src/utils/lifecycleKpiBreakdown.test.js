import {
  hasLifecycleKpiBreakdown,
  lifecycleKpiBreakdownEntries,
  lifecycleKpiBreakdownFromStats,
} from './lifecycleKpiBreakdown';

describe('lifecycleKpiBreakdown', () => {
  it('returns null when breakdown absent', () => {
    expect(lifecycleKpiBreakdownFromStats({})).toBeNull();
    expect(hasLifecycleKpiBreakdown({})).toBe(false);
  });

  it('detects non-zero breakdown rows', () => {
    const stats = {
      lifecycle_kpi_breakdown: {
        certificate_expiring: 0,
        review_due: 2,
        event_action_required: 0,
        tenancy_term_ending: 0,
        occupancy_review_due: 0,
        operational_action_required: 0,
      },
      lifecycle_kpi_effective_mode: 'shadow',
    };
    expect(hasLifecycleKpiBreakdown(stats)).toBe(true);
    expect(lifecycleKpiBreakdownEntries(stats)).toEqual([
      { key: 'review_due', label: 'Review due', count: 2 },
    ]);
  });

  it('ignores all-zero breakdown', () => {
    const stats = {
      lifecycle_kpi_breakdown: {
        certificate_expiring: 0,
        review_due: 0,
        event_action_required: 0,
        tenancy_term_ending: 0,
        occupancy_review_due: 0,
        operational_action_required: 0,
      },
    };
    expect(hasLifecycleKpiBreakdown(stats)).toBe(false);
  });
});
