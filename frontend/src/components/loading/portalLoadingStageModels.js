/**
 * Reusable stage definitions for portal loading UX (copy is illustrative — pages pass overrides).
 */

export const PORTAL_LOADING_PAGES = {
  today: 'today',
  command_center: 'command_center',
  dashboard: 'dashboard',
};

/** @typedef {'pending' | 'active' | 'complete'} PortalLoadingStageStatus */
/** @typedef {{ id: string, label: string, status?: PortalLoadingStageStatus }} PortalLoadingStage */

/** @returns {PortalLoadingStage[]} */
export function todayLoadingStages() {
  return [
    { id: 'requirements', label: 'Checking requirements' },
    { id: 'compliance', label: 'Reviewing compliance' },
    { id: 'inbox', label: 'Building action list' },
  ];
}

/** @returns {PortalLoadingStage[]} */
export function commandCenterLoadingStages() {
  return [
    { id: 'portfolio', label: 'Loading portfolio summary' },
    { id: 'priorities', label: 'Ranking next actions' },
    { id: 'recommendations', label: 'Preparing recommendations' },
  ];
}

/** @returns {PortalLoadingStage[]} */
export function dashboardLoadingStages() {
  return [
    { id: 'workspace', label: 'Loading workspace' },
    { id: 'compliance', label: 'Preparing compliance overview' },
    { id: 'operations', label: 'Gathering operational signals' },
  ];
}

export const PORTAL_LOADING_FOOTER_NOTE =
  'Large portfolios may take a little longer while we prioritise your data.';
