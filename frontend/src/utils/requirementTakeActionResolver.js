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

/**
 * External / published action links for display. Merges resolver supporting links, API action_links,
 * and materialised published registry links (deduped by URL) so the Requirements page matches enrichment.
 * @param {Record<string, unknown>|undefined} requirement
 */
export function mergeRequirementSupportingLinks(requirement) {
  if (!requirement || typeof requirement !== 'object') return [];
  const out = [];
  const seen = new Set();
  const push = (arr) => {
    if (!Array.isArray(arr)) return;
    for (const x of arr) {
      if (!x || typeof x !== 'object') continue;
      const u = String(x.url || '').trim();
      const key = u || `${String(x.label || '')}|${String(x.key || '')}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(x);
    }
  };
  const ta = requirement.take_action;
  if (ta && typeof ta === 'object' && Array.isArray(ta.supporting_external_links)) {
    push(ta.supporting_external_links);
  }
  if (Array.isArray(requirement.action_links)) push(requirement.action_links);
  const meta = requirement.registry_metadata && typeof requirement.registry_metadata === 'object' ? requirement.registry_metadata : null;
  if (meta && Array.isArray(meta.action_links_published)) push(meta.action_links_published);
  return out;
}

/** @param {Record<string, unknown>|undefined} requirement */
function supportingExternalLinksFromRequirement(requirement) {
  return mergeRequirementSupportingLinks(requirement);
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
  if (code.includes('eicr') || code === 'electrical_safety') return 'Coordinate electrical inspection & upload EICR';
  if (code.includes('gas') || ['cp12', 'gas_safety', 'gas_safety_certificate'].includes(code)) {
    return 'Coordinate Gas Safety inspection & upload certificate';
  }
  if (code.includes('epc')) return 'Coordinate EPC assessment & upload certificate';
  if (code.includes('fire') && code.includes('risk')) return 'Coordinate fire risk assessment & upload evidence';
  if (code.includes('pat') || code.includes('portable_appliance')) return 'Coordinate PAT testing & upload evidence';
  if (code.includes('legionella')) return 'Upload legionella risk assessment';
  const disp = String(requirement?.display_label || '').trim();
  if (disp && disp.toLowerCase() !== 'requirement') return `Coordinate inspection & upload evidence — ${disp}`;
  const rl = requirementLabel(requirement?.requirement_code || requirement?.requirement_type || '');
  if (rl && rl.toLowerCase() !== 'requirement') return `Coordinate inspection & upload evidence — ${rl}`;
  return 'Coordinate inspection & upload compliance evidence';
}

/**
 * @param {Record<string, unknown>} requirement enriched row (may include take_action / action_links from API)
 * @param {Record<string, unknown>} _property reserved for future context (jurisdiction is on requirement from API)
 * @returns {{
 *   actionType: string,
 *   primary_action_label: string,
 *   primary_action_handler: 'navigate' | 'external' | 'none' | 'guided_evidence' | 'guided_evidence_error',
 *   primary_route: string | null,
 *   guided_initial_evidence_mode: string | null,
 *   secondary_action: null | { label: string, handler: 'navigate' | 'external', route: string, external: boolean },
 *   supporting_external_links: Array<{ key?: string, label: string, url: string, external?: boolean, kind?: string }>,
 * }}
 */
/** True when API provided a complete primary CTA — UI should not substitute client-only labels/routes. */
export function requirementUsesServerTakeActionPrimary(requirement) {
  const ta = requirement?.take_action;
  const p = ta?.primary;
  return !!(
    ta &&
    typeof ta === 'object' &&
    p &&
    (p.route || p.kind === 'guided_evidence_resolution' || p.kind === 'direct_evidence_action')
  );
}

function guidedPrimaryLooksIncomplete(primary) {
  const pid = primary?.property_id ?? primary?.propertyId;
  const rid = primary?.requirement_id ?? primary?.requirementId;
  return !(String(pid || '').trim() && String(rid || '').trim());
}

function primaryIntentFromTakeActionPrimary(primary) {
  if (!primary || typeof primary !== 'object') return null;
  const ex = String(primary.intent || '').trim();
  if (ex) return ex;
  const r = String(primary.route || '');
  if (r.includes('/documents')) return 'upload_evidence';
  if (r.includes('/operations/issues/new')) return 'maintenance';
  if (r.includes('#compliance')) return 'view_guidance';
  if (/#req=/.test(r) || r.includes('/properties/')) return 'coordinate_inspection_evidence';
  return 'view_requirement';
}

export function resolveRequirementAction(requirement, _property = {}) {
  if (!requirement || typeof requirement !== 'object') {
    return {
      actionType: REQUIREMENT_ACTION_TYPES.DOCUMENT,
      primary_action_label: 'View details',
      primary_action_handler: 'none',
      primary_route: null,
      primary_intent: null,
      secondary_action: null,
      supporting_external_links: [],
    };
  }
  if (requirement.take_action && typeof requirement.take_action === 'object' && requirement.take_action.primary) {
    const ta = requirement.take_action;
    const sec = ta.secondary || null;
    const prim = ta.primary;
    const isServerUnavailable =
      prim.handler === 'guided_evidence_unavailable' || prim.metadata_incomplete === true;
    const isDirectEvidence =
      prim.kind === 'direct_evidence_action' || prim.handler === 'direct_evidence';
    const isGuidedShape =
      prim.kind === 'guided_evidence_resolution' ||
      prim.handler === 'guided_evidence' ||
      isDirectEvidence;
    const isClientBrokenGuided = isGuidedShape && !isServerUnavailable && guidedPrimaryLooksIncomplete(prim);
    if (isClientBrokenGuided && process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.warn(
        '[requirementTakeActionResolver] evidence modal primary missing property_id or requirement_id — showing safe error CTA (no silent document fallback).',
      );
    }
    const opensEvidenceModal = isGuidedShape && !isServerUnavailable && !isClientBrokenGuided;
    const isGuidedError = isServerUnavailable || isClientBrokenGuided;
    const guidedInitial =
      prim.evidence_mode && isDirectEvidence ? String(prim.evidence_mode) : null;
    return {
      actionType: inferRequirementActionType(requirement),
      primary_action_label: String(ta.primary.label || ''),
      primary_action_handler:
        prim.handler === 'external'
          ? 'external'
          : isGuidedError
            ? 'guided_evidence_error'
            : opensEvidenceModal
              ? 'guided_evidence'
              : 'navigate',
      primary_route: ta.primary.route != null && ta.primary.route !== '' ? String(ta.primary.route) : null,
      primary_intent: primaryIntentFromTakeActionPrimary(ta.primary),
      guided_initial_evidence_mode: guidedInitial,
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

  if (requirement.take_action && typeof requirement.take_action === 'object' && requirement.take_action.suppressed) {
    return {
      actionType: REQUIREMENT_ACTION_TYPES.OBLIGATION,
      primary_action_label: 'View details',
      primary_action_handler: 'none',
      primary_route: null,
      primary_intent: 'suppressed',
      secondary_action: null,
      supporting_external_links: supportingExternalLinksFromRequirement(requirement),
    };
  }

  if (
    process.env.NODE_ENV !== 'production' &&
    requirement.take_action &&
    typeof requirement.take_action === 'object' &&
    !requirement.take_action.primary
  ) {
    // eslint-disable-next-line no-console
    console.warn(
      '[requirementTakeActionResolver] take_action without primary — using client fallback; prefer API envelope from requirement_action_resolver.',
    );
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
      primary_intent: 'view_guidance',
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
      primary_intent: 'maintenance',
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
      primary_intent: 'coordinate_inspection_evidence',
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
  let docLabel = 'Upload document';
  if (code.includes('legionella')) docLabel = 'Upload legionella risk assessment';
  else if (code.includes('gas') || ['cp12', 'gas_safety', 'gas_safety_certificate'].includes(code)) {
    docLabel = 'Upload valid gas safety certificate';
  } else if (code.includes('eicr') || code === 'electrical_safety') docLabel = 'Upload valid EICR certificate';
  else if (code.includes('epc')) docLabel = 'Upload current EPC document';
  else if (code.includes('hmo') && code.includes('licen')) docLabel = 'Upload HMO licence';

  return {
    actionType: REQUIREMENT_ACTION_TYPES.DOCUMENT,
    primary_action_label: docLabel,
    primary_action_handler: 'navigate',
    primary_route: docRoute,
    primary_intent: 'upload_evidence',
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
  if (
    which === 'primary' &&
    (ta.primary?.kind === 'guided_evidence_resolution' || ta.primary?.kind === 'direct_evidence_action')
  ) {
    return null;
  }
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
