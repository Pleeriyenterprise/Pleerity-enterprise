/**
 * Resolved requirement semantics — single frontend projection for workflow-aware CTAs, evidence copy, and chips.
 *
 * Thin adapter over backend-shaped requirement rows (`workflow_class`, `take_action`, registry_metadata).
 * Does not invent obligation truth; normalizes and delegates to existing resolver + evidence helpers.
 *
 * Progressive adoption: pages should call {@link projectResolvedRequirementSemantics} instead of scattering
 * workflow_class checks. Legacy call sites remain valid until migrated.
 */
import { getEvidenceStatus, workflowAwareMissingEvidenceLabel } from './evidenceStatus';
import { resolveRequirementActionWithRowContext } from './requirementCtaParity';
import { requirementUsesServerTakeActionPrimary } from './requirementTakeActionResolver';
import { resolveClientRequirementLifecycleForPresentation } from './clientPersistedSubmissionPresentation';
import { applyLifecycleAwareCtaPresentation } from './requirementLifecyclePresentation';
import {
  isConditionStandardWorkflowHint,
  isMultiEvidenceStyleWorkflow,
  normalizeWorkflowClass,
} from './workflowSemantics';
import { buildRequirementShapedRowFromPriorityTask } from './taskRequirementRowAdapter';

/**
 * Build a minimal requirement-shaped row from Command Centre / priority task metadata (workflow-aware lines).
 * @param {Record<string, unknown>|null|undefined} meta
 */
export function buildSemanticRowFromTaskMetadata(meta) {
  if (!meta || typeof meta !== 'object') return {};
  /** @type {Record<string, unknown>} */
  const row = {};
  if (meta.workflow_class != null) row.workflow_class = meta.workflow_class;
  const reqCode = meta.requirement_code ?? meta.requirement_type;
  const canonical =
    meta.canonical_requirement_code != null && String(meta.canonical_requirement_code).trim() !== ''
      ? meta.canonical_requirement_code
      : reqCode;
  if (canonical != null) row.canonical_requirement_code = canonical;
  if (reqCode != null) row.requirement_code = reqCode;
  if (meta.requirement_type != null) row.requirement_type = meta.requirement_type;
  if (meta.tenancy_agreement_status_text != null) row.tenancy_agreement_status_text = meta.tenancy_agreement_status_text;
  return row;
}

/**
 * Workflow-aware missing-evidence line for Command Centre / task metadata (same rules as {@link workflowAwareMissingEvidenceLabel}).
 * @param {Record<string, unknown>|null|undefined} meta
 */
export function missingEvidenceLabelFromPriorityTaskMeta(meta) {
  return workflowAwareMissingEvidenceLabel(buildSemanticRowFromTaskMetadata(meta));
}

/**
 * Canonical semantic projection for a requirement row (list, detail, property matrix, Today task merge).
 *
 * @param {Record<string, unknown>|null|undefined} requirement
 * @param {{ pagePropertyId?: string|null }} [options]
 * @returns {{
 *   workflow_class_normalized: string,
 *   workflow_class_present: boolean,
 *   is_multi_evidence_style: boolean,
 *   is_condition_standard: boolean,
 *   server_take_action_primary: boolean,
 *   cta: ReturnType<typeof resolveRequirementActionWithRowContext>,
 *   lifecycle: ReturnType<typeof resolveClientRequirementLifecycleForPresentation>,
 *   missing_evidence_label: string,
 *   evidenceStatusForStatus: (status: string) => ReturnType<typeof getEvidenceStatus>,
 * }}
 */
export function projectResolvedRequirementSemantics(requirement, options = {}) {
  const pagePropertyId = options.pagePropertyId ?? null;
  const row = requirement && typeof requirement === 'object' ? requirement : {};
  const wfRaw = row.workflow_class;
  const workflow_class_normalized = normalizeWorkflowClass(wfRaw);
  const workflow_class_present = String(wfRaw ?? '').trim() !== '';

  const rawCta = resolveRequirementActionWithRowContext(row, pagePropertyId);
  const cta = applyLifecycleAwareCtaPresentation(row, rawCta);

  return {
    workflow_class_normalized,
    workflow_class_present,
    is_multi_evidence_style: isMultiEvidenceStyleWorkflow(wfRaw),
    is_condition_standard: isConditionStandardWorkflowHint(wfRaw, row),
    server_take_action_primary: requirementUsesServerTakeActionPrimary(row),
    cta,
    lifecycle: resolveClientRequirementLifecycleForPresentation(row),
    missing_evidence_label: workflowAwareMissingEvidenceLabel(row),
    evidenceStatusForStatus: (status) => getEvidenceStatus(status, row),
  };
}

/**
 * Merge an API evidence completeness summary with workflow-aware evidence subline when non-redundant (e.g. Today task cards).
 * @param {string|null|undefined} summary
 * @param {ReturnType<typeof projectResolvedRequirementSemantics>|null|undefined} resolvedProjection
 * @param {unknown} statusField merged requirement / task status for chip resolution
 */
export function combineEvidenceSummaryWithResolvedSubline(summary, resolvedProjection, statusField) {
  if (!summary) return '';
  if (!resolvedProjection) return summary;
  const st = String(statusField ?? 'PENDING').toUpperCase();
  const sub = resolvedProjection.evidenceStatusForStatus(st)?.subline;
  if (!sub) return summary;
  const subTrim = sub.trim();
  if (summary.includes(subTrim.slice(0, Math.min(12, subTrim.length)))) return summary;
  return `${summary} — ${subTrim}`;
}

/**
 * Priority task + optional requirements map → resolved semantics (null when task is not requirement-shaped with take_action).
 * @param {Record<string, unknown>|null|undefined} task
 * @param {Map<string, Record<string, unknown>>|null|undefined} requirementsById
 * @param {string|null|undefined} pagePropertyId
 */
export function projectResolvedRequirementFromPriorityTask(task, requirementsById, pagePropertyId = null) {
  const row = buildRequirementShapedRowFromPriorityTask(task, requirementsById);
  if (!row) return null;
  return projectResolvedRequirementSemantics(row, { pagePropertyId });
}

/*
 * FRONTEND_ALIGNMENT_LIMITATION (Phase 2): Dashboard Command Centre tiles, ComplianceScorePage, invoices, and
 * non-requirement Today rows still use local CTA/status helpers; Operations/Maintenance paths unchanged.
 *
 * STATE_MODEL_LIMITATION: COMPLIANT/PENDING/evidence_doc_id coupling remains backend-shaped; this layer projects
 * existing fields only and does not resolve operational closure or coarse status ambiguity.
 */
