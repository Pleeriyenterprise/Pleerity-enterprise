/**
 * Presentation-only early-network UX for contractor assignment (eligibility authority stays on API).
 */

/** Assignment-ready contractors in directory below this count suggests a growing regional network. */
export const EARLY_NETWORK_ASSIGNMENT_READY_THRESHOLD = 8;

export const NETWORK_MATURITY_BANNER =
  'Contractor network coverage is still growing in some UK regions. If no suitable contractor appears, you can add one directly and they will automatically receive a portal activation invite.';

export const EARLY_NETWORK_PRIMARY_CTA = 'Add contractor for this area';
export const EARLY_NETWORK_GUIDANCE =
  'You can add a contractor directly or update existing contractor coverage.';
export const EARLY_NETWORK_SECONDARY_HEADER = 'Search existing contractor network (beta)';
export const ELIGIBILITY_EMPTY_SUMMARY = 'No contractors currently qualify for this job yet.';

/** Future coverage-intelligence hooks (not wired to recommendations yet). */
export const COVERAGE_LEVEL = Object.freeze({
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
});

export const COVERAGE_GAP_TRADE_HINTS = Object.freeze([
  'electrician',
  'gas engineer',
  'handyman',
  'fire safety contractor',
]);

export function assignmentReadyCount(diagnostics) {
  if (!diagnostics || typeof diagnostics !== 'object') return 0;
  const visible = Number(diagnostics.visible_in_directory) || 0;
  const notReady = Number(diagnostics.excluded_not_assignment_ready) || 0;
  return Math.max(0, visible - notReady);
}

export function hasCoverageGap(diagnostics) {
  if (!diagnostics || typeof diagnostics !== 'object') return false;
  return (
    (Number(diagnostics.excluded_location_postcode) || 0) > 0 ||
    (Number(diagnostics.excluded_property_scope) || 0) > 0 ||
    (Number(diagnostics.excluded_service_region_jurisdiction) || 0) > 0
  );
}

/**
 * Lightweight UI mode when the directory exists but none qualify for this job yet,
 * typically due to regional coverage still growing.
 */
export function isEarlyNetworkMode({ diagnostics, eligibleCount }) {
  const eligible =
    eligibleCount != null ? Number(eligibleCount) : Number(diagnostics?.eligible) || 0;
  if (eligible > 0) return false;
  const assignmentReady = assignmentReadyCount(diagnostics);
  const belowThreshold = assignmentReady < EARLY_NETWORK_ASSIGNMENT_READY_THRESHOLD;
  return belowThreshold || hasCoverageGap(diagnostics);
}

export function earlyNetworkSupportText({ jobJurisdiction, propertyPostcode } = {}) {
  const pc = (propertyPostcode || '').trim();
  const jj = (jobJurisdiction || '').trim();
  if (pc && jj) {
    return `No suitable contractor currently covers this property area (${pc}, ${jj}).`;
  }
  if (pc) {
    return `No suitable contractor currently covers this property area (${pc}).`;
  }
  if (jj) {
    return `No suitable contractor currently covers this property area in ${jj}.`;
  }
  return 'No suitable contractor currently covers this property area.';
}

/** Scaffold for future coverage intelligence — display/telemetry only today. */
export function networkCoverageLevel(diagnostics) {
  const eligible = Number(diagnostics?.eligible) || 0;
  const directory = Number(diagnostics?.visible_in_directory) || 0;
  const assignmentReady = assignmentReadyCount(diagnostics);
  if (eligible >= 3) return COVERAGE_LEVEL.HIGH;
  if (eligible >= 1) return COVERAGE_LEVEL.MEDIUM;
  if (assignmentReady >= EARLY_NETWORK_ASSIGNMENT_READY_THRESHOLD) return COVERAGE_LEVEL.MEDIUM;
  if (directory === 0) return COVERAGE_LEVEL.LOW;
  return COVERAGE_LEVEL.LOW;
}

export const CONTRACTOR_DIRECTORY_EMPTY_HINT =
  'Your contractor network is still growing in some UK regions. Add contractors from a job assignment when you need coverage for a specific property area.';
