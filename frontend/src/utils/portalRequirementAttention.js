/**
 * Single client-portal rule for which requirement rows count toward urgent / needs-attention surfaces.
 * No API changes — uses fields already on requirement objects (applicability, status, optional is_tracked).
 */

/**
 * @param {Record<string, unknown>|null|undefined} req
 * @returns {boolean}
 */
export function isRequirementIncludedInAttentionViews(req) {
  if (!req || typeof req !== 'object') return false;
  if (req.is_tracked === false || req.tracked === false) return false;
  const cls = String(req.compliance_requirement_class || req.requirement_class || '').toUpperCase();
  if (cls === 'OBLIGATION' || cls === 'SYSTEM') return false;
  if (cls && cls !== 'DOCUMENT' && cls !== 'JOB') return false;
  const app = String(req.applicability || '').toUpperCase().trim();
  if (app === 'NOT_REQUIRED') return false;
  const st = String(req.status || '').toUpperCase();
  if (st === 'NOT_REQUIRED') return false;
  return true;
}

/**
 * @param {Array<Record<string, unknown>>|null|undefined} requirements
 * @returns {Array<Record<string, unknown>>}
 */
export function filterRequirementsForAttentionViews(requirements) {
  if (!Array.isArray(requirements)) return [];
  return requirements.filter(isRequirementIncludedInAttentionViews);
}

/**
 * Requirements for one property (same array shape everywhere — no refetch).
 * @param {string|null|undefined} propertyId
 * @param {Array<Record<string, unknown>>|null|undefined} requirements
 */
export function getRequirementsForProperty(propertyId, requirements) {
  if (propertyId == null || propertyId === '') return [];
  if (!Array.isArray(requirements)) return [];
  const pid = String(propertyId);
  return requirements.filter((r) => String(r.property_id) === pid);
}

/**
 * Tracked / in-scope requirements for a property (Operating + Compliance urgent lists,
 * Today / Command Center / Dashboard inbox alignment). Single helper for all attention flows.
 */
export function getTrackedRequirementsForProperty(propertyId, requirements) {
  return filterRequirementsForAttentionViews(getRequirementsForProperty(propertyId, requirements));
}

/**
 * Map requirement_id → row (GET /client/requirements shape). Used to align inbox/command-center tasks.
 * @param {Array<Record<string, unknown>>|null|undefined} requirements
 * @returns {Map<string, Record<string, unknown>>}
 */
export function requirementMapFromList(requirements) {
  const m = new Map();
  if (!Array.isArray(requirements)) return m;
  for (const r of requirements) {
    if (r?.requirement_id == null || r.requirement_id === '') continue;
    m.set(String(r.requirement_id), r);
  }
  return m;
}

/**
 * Requirement id carried on Today / command-center task payloads (metadata shapes vary).
 * @param {Record<string, unknown>|null|undefined} task
 * @returns {string|null}
 */
export function inboxTaskLinkedRequirementId(task) {
  if (!task || typeof task !== 'object') return null;
  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const st = String(task.source_type || task.source_entity_type || '').toLowerCase();
  const fromSource = st === 'requirement' ? task.source_id : null;
  const rid =
    task.requirement_id ??
    fromSource ??
    meta.requirement_id ??
    meta.linked_property_requirement_id ??
    meta.related_requirement_id;
  if (rid == null || rid === '') return null;
  return String(rid);
}

/**
 * True when the task is tied to a requirement row we treat as out of scope for attention surfaces.
 * @param {Record<string, unknown>|null|undefined} task
 * @param {Map<string, Record<string, unknown>>} requirementsById
 */
export function taskLinksExcludedRequirement(task, requirementsById) {
  if (!(requirementsById instanceof Map) || requirementsById.size === 0) return false;
  const rid = inboxTaskLinkedRequirementId(task);
  if (!rid) return false;
  const req = requirementsById.get(rid);
  if (!req) return false;
  return !isRequirementIncludedInAttentionViews(req);
}

/**
 * Drop tasks for untracked / not-applicable requirements so Today matches Operating / Requirements attention rules.
 * When requirements failed to load (empty map), returns the list unchanged.
 * @param {unknown[]|null|undefined} tasks
 * @param {Map<string, Record<string, unknown>>} requirementsById
 */
export function filterInboxTasksForTrackedRequirements(tasks, requirementsById) {
  if (!Array.isArray(tasks)) return [];
  if (!(requirementsById instanceof Map) || requirementsById.size === 0) return tasks;
  return tasks.filter((t) => !taskLinksExcludedRequirement(t, requirementsById));
}

/**
 * Today inbox sections after tracked-requirement alignment (same logic on Today + Dashboard).
 * @param {Record<string, unknown>|null|undefined} todayPayload GET /client/today/items response body
 * @param {Map<string, Record<string, unknown>>} requirementsById from {@link requirementMapFromList}
 */
export function alignTodayPayloadTaskSections(todayPayload, requirementsById) {
  const raw =
    todayPayload && typeof todayPayload === 'object' && todayPayload.tasks && typeof todayPayload.tasks === 'object'
      ? todayPayload.tasks
      : {};
  const align = (key) => filterInboxTasksForTrackedRequirements(raw[key] || [], requirementsById);
  return {
    urgent: align('urgent'),
    upcoming: align('upcoming'),
    in_progress: align('in_progress'),
    recently_completed: align('recently_completed'),
    snoozed: align('snoozed'),
    hidden: align('hidden'),
  };
}
