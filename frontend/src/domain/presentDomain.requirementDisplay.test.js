import { requirementTitleFromRow, slaStateLabel } from './presentDomain';

describe('requirementTitleFromRow', () => {
  const row = {
    requirement_code: 'hmo_license',
    requirement_display: {
      canonical_name: 'HMO / Selective / Additional Licensing',
      short_name: 'HMO Licensing',
      description: '',
      category_label: 'Regulatory',
      primary_cta_label: 'X',
      secondary_cta_label: null,
    },
    display_label: 'HMO licence',
    title: 'Legacy title',
  };

  it('uses short_name for compact surfaces', () => {
    expect(requirementTitleFromRow(row, 'compact')).toBe('HMO Licensing');
  });

  it('uses canonical_name for detail surfaces', () => {
    expect(requirementTitleFromRow(row, 'detail')).toBe('HMO / Selective / Additional Licensing');
  });
});

describe('slaStateLabel', () => {
  it('returns governed client labels for SLA states', () => {
    expect(slaStateLabel('breached')).toBe('SLA deadline missed');
    expect(slaStateLabel('near_breach')).toBe('Near SLA deadline');
  });

  it('returns em dash for unknown states', () => {
    expect(slaStateLabel('unknown_state')).toBe('—');
  });
});

