import {
  daysUntilTimelineDate,
  getTimelineDateLabel,
  getTimelineSortDateIso,
  isTimelineEstimated,
  isTimelineVerified,
} from './complianceTimelinePresentation';

describe('complianceTimelinePresentation', () => {
  const verifiedRow = {
    timeline_primary_date: '2027-06-15',
    timeline_primary_date_label: 'Certificate expires: 15 Jun 2027',
    timeline_primary_date_confidence: 'VERIFIED',
    timeline_primary_date_concept: 'certificate_expiry',
    compliance_timeline: {
      primary_date: '2027-06-15',
      primary_date_label: 'Certificate expires: 15 Jun 2027',
      is_estimated: false,
      is_verified: true,
      effective_attention_date: '2027-06-15',
    },
    due_date: '2026-03-01T00:00:00.000Z',
    date_label: 'Next due: 1 Mar 2026',
  };

  const estimatedRow = {
    timeline_primary_date: '2026-04-01',
    timeline_primary_date_label: 'Estimated compliance date: 1 Apr 2026',
    timeline_primary_date_confidence: 'ESTIMATED',
    compliance_timeline: {
      primary_date: '2026-04-01',
      primary_date_label: 'Estimated compliance date: 1 Apr 2026',
      is_estimated: true,
      is_verified: false,
    },
    due_date: '2026-04-01T00:00:00.000Z',
  };

  it('uses timeline label over legacy date_label and due_date', () => {
    expect(getTimelineDateLabel(verifiedRow)).toBe('Certificate expires: 15 Jun 2027');
    expect(getTimelineSortDateIso(verifiedRow)).toBe('2027-06-15');
  });

  it('detects estimated vs verified from timeline', () => {
    expect(isTimelineVerified(verifiedRow)).toBe(true);
    expect(isTimelineEstimated(verifiedRow)).toBe(false);
    expect(isTimelineEstimated(estimatedRow)).toBe(true);
  });

  it('computes days until from timeline sort date', () => {
    const future = new Date();
    future.setUTCDate(future.getUTCDate() + 10);
    const iso = future.toISOString().slice(0, 10);
    const row = {
      timeline_primary_date: iso,
      compliance_timeline: { primary_date: iso, effective_attention_date: iso },
    };
    const days = daysUntilTimelineDate(row);
    expect(days).toBeGreaterThanOrEqual(9);
    expect(days).toBeLessThanOrEqual(11);
  });

  it('falls back to date_label when timeline fields absent', () => {
    expect(getTimelineDateLabel({ date_label: 'Guide delivery date: 1 Jan 2025' })).toBe(
      'Guide delivery date: 1 Jan 2025',
    );
  });
});
