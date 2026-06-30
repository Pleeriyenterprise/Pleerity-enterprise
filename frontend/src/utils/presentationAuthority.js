/**
 * Presentation authority helpers (PRESENTATION-AUTHORITY-ALIGNMENT-01).
 *
 * Parses backend semantic fields and exposes governed copy — no lifecycle inference.
 * @see backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md
 */
import {
  COUNT_SEMANTICS_EXPLANATION,
  RECOMMENDATION_LENS,
} from './lifecycleAuthorityCopy';

export const TRACKED_ATTENTION_SEMANTICS_KEY = 'tracked_attention_document_job_excludes_obligation';

/**
 * @param {Record<string, unknown>|null|undefined} setupStatus
 */
export function parsePortalRequirementCounts(setupStatus) {
  const s = setupStatus && typeof setupStatus === 'object' ? setupStatus : {};
  const raw = Number(s.requirements_count);
  const runtime = s.requirements_runtime_visible_count;
  const tracked = s.requirements_tracked_attention_count;
  const hasSemanticFields = runtime != null && tracked != null;
  return {
    rawApplicable: Number.isFinite(raw) ? raw : null,
    runtimeVisible: hasSemanticFields ? Number(runtime) : null,
    trackedAttention: hasSemanticFields ? Number(tracked) : null,
    semanticsKey: String(s.requirements_count_semantics || TRACKED_ATTENTION_SEMANTICS_KEY),
    hasSemanticFields,
  };
}

/**
 * Primary headline count for onboarding/setup — prefer tracked attention; fall back to raw.
 * @param {ReturnType<typeof parsePortalRequirementCounts>} counts
 */
export function primaryTrackedCountDisplay(counts) {
  if (counts.trackedAttention != null) return counts.trackedAttention;
  if (counts.runtimeVisible != null) return counts.runtimeVisible;
  return counts.rawApplicable ?? 0;
}

/**
 * @param {ReturnType<typeof parsePortalRequirementCounts>} counts
 */
export function requirementCountFootnote(counts) {
  const applicable = counts.rawApplicable ?? counts.runtimeVisible;
  const tracked = counts.trackedAttention;
  if (applicable == null || tracked == null || applicable <= tracked) return null;
  return COUNT_SEMANTICS_EXPLANATION;
}

/**
 * @param {ReturnType<typeof parsePortalRequirementCounts>} counts
 */
export function requirementCountHeadlineLines(counts) {
  const applicable = counts.rawApplicable ?? counts.runtimeVisible ?? counts.trackedAttention ?? 0;
  const tracked = counts.trackedAttention ?? counts.runtimeVisible ?? applicable;
  if (counts.hasSemanticFields && applicable > tracked) {
    return {
      primary: tracked,
      primaryLabel: 'Actively tracked',
      secondary: applicable,
      secondaryLabel: 'Requirements identified',
      footnote: COUNT_SEMANTICS_EXPLANATION,
    };
  }
  return {
    primary: primaryTrackedCountDisplay(counts),
    primaryLabel: counts.hasSemanticFields ? 'Actively tracked' : 'Requirements created',
    secondary: null,
    secondaryLabel: null,
    footnote: null,
  };
}

/**
 * Documents setup wizard — backend checklist authority only.
 * @param {Record<string, unknown>|null|undefined} checklistState
 */
export function shouldShowDocumentsSetupStep(checklistState) {
  const sp = checklistState?.setup_presentation;
  if (sp && typeof sp === 'object') {
    return sp.documents_step_recommended === true;
  }
  return false;
}

export { RECOMMENDATION_LENS };

/**
 * @param {'onboarding'|'operational'|'triage'|'kpi'} lens
 */
export function recommendationLensLabel(lens) {
  return RECOMMENDATION_LENS[lens] || RECOMMENDATION_LENS.operational;
}
