/** @jest-environment node */
import {
  assignmentReadyCount,
  earlyNetworkSupportText,
  EARLY_NETWORK_ASSIGNMENT_READY_THRESHOLD,
  isEarlyNetworkMode,
  networkCoverageLevel,
  COVERAGE_LEVEL,
} from './assignContractorEarlyNetwork';
import { assignDropdownEmptyMessage } from './assignContractorRecovery';

describe('assignContractorEarlyNetwork', () => {
  const sparseDiag = {
    visible_in_directory: 16,
    excluded_not_assignment_ready: 6,
    excluded_location_postcode: 9,
    excluded_maintenance_trade: 1,
    eligible: 0,
  };

  it('detects early network when eligible is zero and coverage gap exists', () => {
    expect(isEarlyNetworkMode({ diagnostics: sparseDiag, eligibleCount: 0 })).toBe(true);
  });

  it('does not activate when eligible contractors exist', () => {
    expect(isEarlyNetworkMode({ diagnostics: { ...sparseDiag, eligible: 2 }, eligibleCount: 2 })).toBe(false);
  });

  it('computes assignment-ready count from diagnostics', () => {
    expect(assignmentReadyCount(sparseDiag)).toBe(10);
  });

  it('activates when assignment-ready pool is below threshold', () => {
    const diag = {
      visible_in_directory: 5,
      excluded_not_assignment_ready: 0,
      excluded_maintenance_trade: 5,
      eligible: 0,
    };
    expect(assignmentReadyCount(diag)).toBeLessThan(EARLY_NETWORK_ASSIGNMENT_READY_THRESHOLD);
    expect(isEarlyNetworkMode({ diagnostics: diag, eligibleCount: 0 })).toBe(true);
  });

  it('builds operational support copy with postcode and jurisdiction', () => {
    const text = earlyNetworkSupportText({ jobJurisdiction: 'Scotland', propertyPostcode: 'G73 4BA' });
    expect(text).toMatch(/G73 4BA/);
    expect(text).toMatch(/Scotland/);
    expect(text).not.toMatch(/database|matching failure|eligibility engine/i);
  });

  it('scaffolds coverage level without recommendations', () => {
    expect(networkCoverageLevel({ eligible: 0, visible_in_directory: 3, excluded_not_assignment_ready: 0 })).toBe(
      COVERAGE_LEVEL.LOW
    );
    expect(networkCoverageLevel({ eligible: 3, visible_in_directory: 16 })).toBe(COVERAGE_LEVEL.HIGH);
  });
});

describe('assignContractorRecovery empty copy', () => {
  it('uses operational empty-state wording', () => {
    const msg = assignDropdownEmptyMessage({
      filteredCount: 0,
      eligibleTotal: 0,
      filterStats: {},
      diagnostics: { eligible: 0, visible_in_directory: 10 },
      tradeTypeFilter: 'all',
      contractorFilter: '',
    });
    expect(msg.headline).toMatch(/cover this property area/i);
    expect(msg.detail).toMatch(/add a contractor directly/i);
  });
});
