import { resolveAssignModalFocusTarget } from './assignContractorModalFocus';

describe('assignContractorModalFocus', () => {
  it('focuses add form when expanded', () => {
    expect(resolveAssignModalFocusTarget({ showAddContractorForm: true, eligibleCount: 3 })).toBe('add_name');
  });

  it('focuses select when contractors are available', () => {
    expect(resolveAssignModalFocusTarget({ showAddContractorForm: false, eligibleCount: 2 })).toBe('select');
  });

  it('focuses early-network CTA when none qualify', () => {
    expect(resolveAssignModalFocusTarget({ showAddContractorForm: false, eligibleCount: 0 })).toBe('early_network_cta');
  });
});
