/**
 * Today execution workspace — re-exports from todayPresentationAuthority (single source of truth).
 * @deprecated Import from todayPresentationAuthority.js for new code.
 */
export {
  TODAY_PRESENTATION_SEMANTIC_DECISION,
  TODAY_PRESENTATION_SEMANTICS,
  buildPropertyByIdMap,
  enrichTaskForExecution,
  pickPrimaryExecutionTask,
  classifyTaskOperationalBucket,
  buildOperationalSections,
  visibleOpenCount,
  buildFalseEmptyStateDisclosure,
  buildListCapDisclosure,
  formatNeedsActionBannerLine,
  buildTodayPresentationModel,
  isTaskAssuranceOnly,
} from './todayPresentationAuthority';
