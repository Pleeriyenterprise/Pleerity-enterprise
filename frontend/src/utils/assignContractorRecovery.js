/** Server-aligned recovery guidance for assign-contractor modal (display only — authority stays on API). */

export const EXCLUSION_REASON_LABELS = {
  excluded_not_assignment_ready: 'Not assignment-ready',
  excluded_wrong_client_scope: 'Wrong client scope',
  excluded_property_scope: 'Property scope',
  excluded_location_postcode: 'Location / coverage',
  excluded_execution_capability: 'Job capability',
  excluded_maintenance_trade: 'Trade vs job category',
  excluded_service_region_jurisdiction: 'Service region',
};

export function assignDropdownEmptyMessage({
  filteredCount,
  eligibleTotal,
  filterStats,
  diagnostics,
  tradeTypeFilter,
  contractorFilter,
}) {
  if (filteredCount > 0) return null;

  const q = (contractorFilter || '').trim();
  const tradeNarrowed = tradeTypeFilter && tradeTypeFilter !== 'all';
  const serverEligible = eligibleTotal ?? diagnostics?.eligible ?? 0;
  const directoryTotal = diagnostics?.visible_in_directory ?? 0;

  if (serverEligible > 0 && (tradeNarrowed || q)) {
    const parts = [];
    if (filterStats?.hiddenByTrade > 0) {
      parts.push(`${filterStats.hiddenByTrade} hidden by trade filter`);
    }
    if (filterStats?.hiddenBySearch > 0) {
      parts.push(`${filterStats.hiddenBySearch} hidden by search`);
    }
    return {
      kind: 'client_filter',
      headline: 'No rows match the current trade and search filters.',
      detail:
        parts.length > 0
          ? `${parts.join(' · ')}. ${serverEligible} contractor${serverEligible === 1 ? '' : 's'} ready on this job — widen filters to see them.`
          : `Try "All trades" or clear search — ${serverEligible} ready on this job.`,
    };
  }

  if (serverEligible === 0 && directoryTotal > 0) {
    return {
      kind: 'server_empty',
      headline: 'No contractors qualify for this job yet.',
      detail: 'Use the recovery steps below to update coverage, complete setup, or add a contractor.',
    };
  }

  if (directoryTotal === 0) {
    return {
      kind: 'no_directory',
      headline: 'No contractors in your directory yet.',
      detail: 'Add a contractor below to assign them to this job.',
    };
  }

  return {
    kind: 'unknown',
    headline: 'No contractors to show.',
    detail: 'Adjust filters or refresh the list.',
  };
}

export function groupedExclusionSamples(exclusionSamples) {
  if (!exclusionSamples || typeof exclusionSamples !== 'object') return [];
  return Object.entries(exclusionSamples)
    .filter(([, rows]) => Array.isArray(rows) && rows.length > 0)
    .map(([key, rows]) => ({
      reasonKey: key,
      label: EXCLUSION_REASON_LABELS[key] || key,
      contractors: rows,
    }));
}
