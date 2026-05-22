/**
 * Workflow-class helpers — stay aligned with backend requirement_action_resolver +
 * enrich_take_action_envelope_for_client (workflow_class on enriched rows).
 *
 * Phase 1: compatibility shims only; do not invent a parallel workflow taxonomy.
 */

/** @param {unknown} wf */
export function normalizeWorkflowClass(wf) {
  return String(wf || '')
    .trim()
    .toUpperCase();
}

/**
 * Multi-component / guided-selector obligations (alarms, fire risk family).
 * Backend may emit MULTI_EVIDENCE; legacy payloads may still surface GUIDED_EVIDENCE_RESOLUTION as primary_resolution_workflow.
 * @param {unknown} wf
 */
export function isMultiEvidenceStyleWorkflow(wf) {
  const u = normalizeWorkflowClass(wf);
  return u === 'MULTI_EVIDENCE' || u === 'GUIDED_EVIDENCE_RESOLUTION';
}

/**
 * Fitness / repairing condition standards — backend workflow_class is GUIDANCE_ONLY; legacy rows may omit it.
 * @param {unknown} wf
 * @param {Record<string, unknown>|undefined} row
 */
export function isConditionStandardWorkflowHint(wf, row) {
  const u = normalizeWorkflowClass(wf);
  if (u === 'ACTIVE_STANDARD') return true;
  const code = String(row?.canonical_requirement_code || row?.requirement_code || row?.requirement_type || '')
    .trim()
    .toLowerCase();
  return code === 'fitness_for_human_habitation' || code === 'repairing_standard';
}

const CONDITION_STANDARD_ACTIVE_STANDARD_FAMILY = 'CONDITION_STANDARD_ACTIVE_STANDARD';

/**
 * Backend-enriched condition-standard pilot rows (Phase 1).
 * @param {Record<string, unknown>|null|undefined} row
 */
export function isConditionStandardActiveStandardRow(row) {
  if (!row || typeof row !== 'object') return false;
  const wf = String(row.workflow_family || '').trim();
  const ops = String(row.ops_verification_family || '').trim();
  if (wf === CONDITION_STANDARD_ACTIVE_STANDARD_FAMILY && ops === CONDITION_STANDARD_ACTIVE_STANDARD_FAMILY) {
    return true;
  }
  if (wf === CONDITION_STANDARD_ACTIVE_STANDARD_FAMILY || ops === CONDITION_STANDARD_ACTIVE_STANDARD_FAMILY) {
    return isConditionStandardWorkflowHint(row.workflow_class, row);
  }
  return false;
}
