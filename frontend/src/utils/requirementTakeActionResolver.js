/**
 * Unified Take Action — one primary CTA per requirement, compliance vs maintenance separated.
 * External reference links come from API (`take_action.supporting_external_links` or `action_links`), not hardcoded here.
 * Keep aligned with backend/services/requirement_action_resolver.py (labels, routes).
 */

import { normalizeRequirementCode, requirementLabel } from '../domain/presentDomain';

export const REQUIREMENT_ACTION_TYPES = {
  DOCUMENT: 'DOCUMENT',
  JOB: 'JOB',
  MAINTENANCE: 'MAINTENANCE',
  OBLIGATION: 'OBLIGATION',
};

/** @param {Record<string, unknown>|undefined} requirement */
function supportingExternalLinksFromRequirement(requirement) {
  if (!requirement || typeof requirement !== 'object') return [];
  const ta = requirement.take_action;
  if (ta && typeof ta === 'object' && Array.isArray(ta.supporting_external_links)) {
    return ta.supporting_external_links;
  }
  if (Array.isArray(requirement.action_links)) return requirement.action_links;
  return [];
}

export function inferRequirementActionType(requirement) {
  if (!requirement || typeof requirement !== 'object') return REQUIREMENT_ACTION_TYPES.DOCUMENT;
  const stored = String(requirement.action_type || '').toUpperCase();
  if (Object.values(REQUIREMENT_ACTION_TYPES).includes(stored)) return stored;
  const cls = String(requirement.compliance_requirement_class || requirement.requirement_class || '').toUpperCase();
  if (cls === 'JOB') return REQUIREMENT_ACTION_TYPES.JOB;
  if (cls === 'OBLIGATION' || cls === 'SYSTEM') return REQUIREMENT_ACTION_TYPES.OBLIGATION;
  if (cls === 'DOCUMENT') return REQUIREMENT_ACTION_TYPES.DOCUMENT;
  if (requirement.requires_job && !requirement.requires_document) return REQUIREMENT_ACTION_TYPES.JOB;
  if (requirement.requires_document) return REQUIREMENT_ACTION_TYPES.DOCUMENT;
  return REQUIREMENT_ACTION_TYPES.DOCUMENT;
}

function jobPrimaryLabel(requirement) {
  const code = normalizeRequirementCode(requirement?.requirement_code || requirement?.requirement_type || '');
  if (code.includes('eicr') || code === 'electrical_safety') return 'Book electrical inspection';
  if (code.includes('gas') || ['cp12', 'gas_safety', 'gas_safety_certificate'].includes(code)) return 'Book gas safety inspection';
  if (code.includes('epc')) return 'Book EPC assessment';
  if (code.includes('fire') && code.includes('risk')) return 'Book fire risk assessment';
  if (code.includes('pat') || code.includes('portable_appliance')) return 'Book PAT testing';
  if (code.includes('legionella')) return 'Book legionella assessment';
  const disp = String(requirement?.display_label || '').trim();
  if (disp && disp.toLowerCase() !== 'requirement') return `Book inspection — ${disp}`;
  const rl = requirementLabel(requirement?.requirement_code || requirement?.requirement_type || '');
  if (rl && rl.toLowerCase() !== 'requirement') return `Book inspection — ${rl}`;
  return 'Book inspection / arrange compliance';
}

/**
 * @param {Record<string, unknown>} requirement enriched row (may include take_action / action_links from API)
 * @param {Record<string, unknown>} _property reserved for future context (jurisdiction is on requirement from API)
 * @returns {{
 *   actionType: string,
 *   primary_action_label: string,
 *   primary_action_handler: 'navigate' | 'external' | 'none',
 *   primary_route: string | null,
 *   secondary_action: null | { label: string, handler: 'navigate' | 'external', route: string, external: boolean },
 *   supporting_external_links: Array<{ key?: string, label: string, url: string, external?: boolean, kind?: string }>,
 * }}
 */
export function resolveRequirementAction(requirement, _property = {}) {
  if (!requirement || typeof requirement !== 'object') {
    return {
      actionType: REQUIREMENT_ACTION_TYPES.DOCUMENT,
      primary_action_label: 'View details',
      primary_action_handler: 'none',
      primary_route: null,
      secondary_action: null,
      supporting_external_links: [],
    };
  }
  if (requirement.take_action && typeof requirement.take_action === 'object' && requirement.take_action.primary) {
    const ta = requirement.take_action;
    const sec = ta.secondary || null;
    return {
      actionType: inferRequirementActionType(requirement),
      primary_action_label: String(ta.primary.label || ''),
      primary_action_handler: ta.primary.handler === 'external' ? 'external' : 'navigate',
      primary_route: ta.primary.route ? String(ta.primary.route) : null,
      secondary_action: sec
        ? {
            label: String(sec.label || ''),
            handler: sec.external ? 'external' : 'navigate',
            route: String(sec.route || ''),
            external: !!sec.external,
          }
        : null,
      supporting_external_links: supportingExternalLinksFromRequirement(requirement),
    };
  }

  const pid = requirement.property_id;
  const rid = requirement.requirement_id;
  const code = requirement.requirement_code || requirement.requirement_type || '';
  const hashFrag = code ? `#req=${encodeURIComponent(code)}` : '';
  const cls = String(requirement.compliance_requirement_class || '').toUpperCase();
  const ff = String(requirement.engine_fulfillment_mode || requirement.fulfillment_mode || '').toLowerCase();
  const informational =
    cls === 'OBLIGATION' ||
    cls === 'SYSTEM' ||
    requirement.engine_informational === true ||
    String(requirement.engine_client_visibility || '').toLowerCase() === 'informational' ||
    ff === 'obligation';

  const supporting = supportingExternalLinksFromRequirement(requirement);

  if (informational) {
    return {
      actionType: REQUIREMENT_ACTION_TYPES.OBLIGATION,
      primary_action_label: 'View guidance',
      primary_action_handler: 'navigate',
      primary_route: pid ? `/properties/${pid}#compliance` : '/requirements',
      secondary_action: null,
      supporting_external_links: supporting,
    };
  }

  const at = inferRequirementActionType(requirement);
  if (at === REQUIREMENT_ACTION_TYPES.MAINTENANCE) {
    return {
      actionType: REQUIREMENT_ACTION_TYPES.MAINTENANCE,
      primary_action_label: 'Log issue',
      primary_action_handler: 'navigate',
      primary_route: pid ? `/operations/issues/new?property_id=${encodeURIComponent(String(pid))}` : '/operations/issues',
      secondary_action: null,
      supporting_external_links: supporting,
    };
  }

  const isJob = cls === 'JOB' || ff === 'job';
  const needsDoc = requirement.engine_requires_document_evidence !== false;

  if (isJob) {
    const primaryRoute = pid ? `/properties/${pid}${hashFrag}` : '/requirements';
    let secondary = null;
    if (needsDoc && pid && rid) {
      secondary = {
        label: 'Upload document',
        handler: 'navigate',
        route: `/documents?property_id=${encodeURIComponent(String(pid))}&requirement_id=${encodeURIComponent(String(rid))}`,
        external: false,
      };
    }
    return {
      actionType: REQUIREMENT_ACTION_TYPES.JOB,
      primary_action_label: jobPrimaryLabel(requirement),
      primary_action_handler: 'navigate',
      primary_route: primaryRoute,
      secondary_action: secondary,
      supporting_external_links: supporting,
    };
  }

  const docRoute =
    pid && rid
      ? `/documents?property_id=${encodeURIComponent(String(pid))}&requirement_id=${encodeURIComponent(String(rid))}`
      : pid
        ? `/documents?property_id=${encodeURIComponent(String(pid))}`
        : '/documents';
  return {
    actionType: REQUIREMENT_ACTION_TYPES.DOCUMENT,
    primary_action_label: 'Upload document',
    primary_action_handler: 'navigate',
    primary_route: docRoute,
    secondary_action: null,
    supporting_external_links: supporting,
  };
}

/**
 * Prefer server-normalised take_action on unified inbox tasks when present.
 * @param {Record<string, unknown>} task
 * @param {'primary'|'secondary'} which
 */
export function resolveInboxTaskTakeActionRoute(task, which = 'primary') {
  const ta = task?.metadata?.take_action;
  if (!ta || typeof ta !== 'object') return null;
  if (which === 'primary' && ta.primary?.route) return String(ta.primary.route);
  if (which === 'secondary' && ta.secondary?.route) return String(ta.secondary.route);
  return null;
}

export function resolveInboxTaskTakeActionLabel(task, which = 'primary') {
  const ta = task?.metadata?.take_action;
  if (!ta || typeof ta !== 'object') return null;
  if (which === 'primary' && ta.primary?.label) return String(ta.primary.label);
  if (which === 'secondary' && ta.secondary?.label) return String(ta.secondary.label);
  return null;
}
