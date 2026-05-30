/** @jest-environment node */
import {
  assignDropdownEmptyMessage,
  groupedExclusionSamples,
} from './assignContractorRecovery';

describe('assignContractorRecovery', () => {
  it('explains client-side trade filter hiding eligible contractors', () => {
    const msg = assignDropdownEmptyMessage({
      filteredCount: 0,
      eligibleTotal: 3,
      filterStats: { hiddenByTrade: 3, hiddenBySearch: 0 },
      diagnostics: { eligible: 3, visible_in_directory: 10 },
      tradeTypeFilter: 'plumbing',
      contractorFilter: '',
    });
    expect(msg.kind).toBe('client_filter');
    expect(msg.detail).toMatch(/3 contractor/);
  });

  it('groups exclusion samples by reason', () => {
    const groups = groupedExclusionSamples({
      excluded_location_postcode: [{ contractor_id: 'c1', name: 'A Co' }],
    });
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe('Location / coverage');
  });
});
