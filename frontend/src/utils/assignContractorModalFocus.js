/**
 * Determines which control should receive focus when the assign-contractor modal opens.
 */
export function resolveAssignModalFocusTarget({ showAddContractorForm, eligibleCount }) {
  if (showAddContractorForm) return 'add_name';
  if (Number(eligibleCount) > 0) return 'select';
  return 'early_network_cta';
}
