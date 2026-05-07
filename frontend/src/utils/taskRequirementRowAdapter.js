/**
 * Adapts unified priority/task payloads into requirement-shaped rows for {@link executeRequirementPrimaryCta}.
 * Client-only; does not change API or resolver authority — only reshapes data already on the task.
 */
import { inboxTaskLinkedRequirementId } from './portalRequirementAttention';

/**
 * Optional fields copied from task.metadata when merging onto a full requirement row or minimal stub.
 * @param {Record<string, unknown>} meta
 */
function taskMetadataFieldsForRequirementRow(meta) {
  if (!meta || typeof meta !== 'object') return {};
  const out = {};
  if (meta.requirement_display && typeof meta.requirement_display === 'object') {
    out.requirement_display = meta.requirement_display;
  }
  if (meta.workflow_class != null) out.workflow_class = meta.workflow_class;
  if (Array.isArray(meta.allowed_evidence_modes)) out.allowed_evidence_modes = meta.allowed_evidence_modes;
  if (meta.evidence_completeness && typeof meta.evidence_completeness === 'object') {
    out.evidence_completeness = meta.evidence_completeness;
  }
  if (meta.evidence_resolution && typeof meta.evidence_resolution === 'object') {
    out.evidence_resolution = meta.evidence_resolution;
  }
  if (meta.guidance_target != null) out.guidance_target = meta.guidance_target;
  if (meta.registry_metadata && typeof meta.registry_metadata === 'object') {
    out.registry_metadata = meta.registry_metadata;
  }
  if (meta.requirement_code != null) out.requirement_code = meta.requirement_code;
  if (meta.requirement_type != null) out.requirement_type = meta.requirement_type;
  if (meta.compliance_requirement_class != null) out.compliance_requirement_class = meta.compliance_requirement_class;
  if (meta.requirement_class != null) out.requirement_class = meta.requirement_class;
  if (meta.display_label != null) out.display_label = meta.display_label;
  if (meta.engine_fulfillment_mode != null) out.engine_fulfillment_mode = meta.engine_fulfillment_mode;
  if (meta.fulfillment_mode != null) out.fulfillment_mode = meta.fulfillment_mode;
  if (meta.engine_informational != null) out.engine_informational = meta.engine_informational;
  return out;
}

/**
 * When a priority task is requirement-backed and carries resolver metadata, returns an object compatible
 * with {@link resolveRequirementAction} / {@link executeRequirementPrimaryCta}. Otherwise null (caller keeps
 * {@link resolveTaskCta}). For workflow/evidence/CTA projection, prefer {@link projectResolvedRequirementFromPriorityTask}
 * in resolvedRequirementViewModel (thin wrapper over this builder).
 *
 * @param {Record<string, unknown>|null|undefined} task
 * @param {Map<string, Record<string, unknown>>|null|undefined} requirementsById from {@link requirementMapFromList}
 * @returns {Record<string, unknown>|null}
 */
export function buildRequirementShapedRowFromPriorityTask(task, requirementsById) {
  if (!task || typeof task !== 'object') return null;
  const st = String(task.source_type || task.source_entity_type || '').toLowerCase();
  if (st !== 'requirement') return null;

  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const takeAction = meta.take_action && typeof meta.take_action === 'object' ? meta.take_action : null;
  if (!takeAction) return null;

  const rid = inboxTaskLinkedRequirementId(task);
  const pid = task.property_id != null && String(task.property_id).trim() !== '' ? String(task.property_id).trim() : null;
  if (!rid || !pid) return null;

  const metaOverlay = taskMetadataFieldsForRequirementRow(meta);
  const jurisdiction =
    task.jurisdiction || task.property_jurisdiction || meta.property_jurisdiction || meta.jurisdiction || undefined;

  const fromMap = requirementsById instanceof Map ? requirementsById.get(String(rid)) : null;
  if (fromMap && typeof fromMap === 'object') {
    return {
      ...fromMap,
      ...metaOverlay,
      requirement_id: String(rid),
      property_id: pid,
      take_action: takeAction,
      ...(jurisdiction != null && jurisdiction !== '' ? { jurisdiction, property_jurisdiction: jurisdiction } : {}),
    };
  }

  return {
    ...metaOverlay,
    requirement_id: String(rid),
    property_id: pid,
    take_action: takeAction,
    ...(jurisdiction != null && jurisdiction !== '' ? { jurisdiction, property_jurisdiction: jurisdiction } : {}),
  };
}
