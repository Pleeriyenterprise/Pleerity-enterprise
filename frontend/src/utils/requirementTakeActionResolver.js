/**
 * Unified Take Action — one primary CTA per requirement, compliance vs maintenance separated.
 * External reference links come from API (`take_action.supporting_external_links` or `action_links`), not hardcoded here.
 * Keep aligned with backend/services/requirement_action_resolver.py (labels, routes).
 *
 * Canonical authority: `resolveCanonicalPrimaryAction` from operationalAuthorityContract — no client invention.
 */

import {
  hasServerOperationalAuthority,
  resolveCanonicalPrimaryAction,
} from './operationalAuthorityContract';

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
  const meta = requirement.registry_metadata && typeof requirement.registry_metadata === 'object' ? requirement.registry_metadata : {};
  if (String(meta.primary_action_mode || '').trim().toLowerCase() === 'hidden') {
    return REQUIREMENT_ACTION_TYPES.OBLIGATION;
  }
  const cls = String(requirement.compliance_requirement_class || requirement.requirement_class || '').toUpperCase();
  if (cls === 'JOB') return REQUIREMENT_ACTION_TYPES.JOB;
  if (cls === 'OBLIGATION' || cls === 'SYSTEM') return REQUIREMENT_ACTION_TYPES.OBLIGATION;
  if (cls === 'DOCUMENT') return REQUIREMENT_ACTION_TYPES.DOCUMENT;
  if (requirement.requires_job && !requirement.requires_document) return REQUIREMENT_ACTION_TYPES.JOB;
  if (requirement.requires_document) return REQUIREMENT_ACTION_TYPES.DOCUMENT;
  return REQUIREMENT_ACTION_TYPES.DOCUMENT;
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
  if (
    ta &&
    typeof ta === 'object' &&
    p &&
    (p.route || p.kind === 'guided_evidence_resolution' || p.kind === 'direct_evidence_action')
  ) {
    return true;
  }
  return hasServerOperationalAuthority(requirement);
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

function mapCanonicalPrimaryToRequirementAction(requirement, canonical) {
  const supporting = supportingExternalLinksFromRequirement(requirement);
  const url = canonical?.url != null ? String(canonical.url).trim() : '';
  const isExternal = /^https?:\/\//i.test(url);
  return {
    actionType: inferRequirementActionType(requirement),
    primary_action_label: String(canonical.label || '').trim(),
    primary_action_handler: isExternal ? 'external' : url ? 'navigate' : 'none',
    primary_route: url || null,
    primary_intent: canonical.key || canonical.authority_source || null,
    authority_source: canonical.authority_source,
    secondary_action: null,
    supporting_external_links: supporting,
  };
}

function authorityMissingRequirementAction(requirement) {
  return {
    actionType: inferRequirementActionType(requirement),
    primary_action_label: 'View requirement',
    primary_action_handler: 'none',
    primary_route: null,
    primary_intent: 'authority_missing',
    authority_missing: true,
    secondary_action: null,
    supporting_external_links: supportingExternalLinksFromRequirement(requirement),
  };
}

export function resolveRequirementAction(requirement, _property = {}) {
  if (
    process.env.NODE_ENV !== 'production' &&
    requirement &&
    typeof requirement === 'object' &&
    !requirement.take_action &&
    !hasServerOperationalAuthority(requirement)
  ) {
    // eslint-disable-next-line no-console
    console.warn(
      '[requirementTakeActionResolver] requirement missing server operational authority — no client fallback (prefer API enrichment).',
    );
  }
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
    const primBase = ta.primary && typeof ta.primary === 'object' ? ta.primary : {};
    const prim = { ...primBase };
    const pidRow = requirement.property_id;
    const ridRow = requirement.requirement_id || requirement.id;
    if (!String(prim.property_id || prim.propertyId || '').trim() && pidRow) {
      prim.property_id = String(pidRow);
    }
    if (!String(prim.requirement_id || prim.requirementId || '').trim() && ridRow) {
      prim.requirement_id = String(ridRow);
    }
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
      primary_route: prim.route != null && prim.route !== '' ? String(prim.route) : null,
      primary_intent: primaryIntentFromTakeActionPrimary(prim),
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
    !requirement.take_action.primary &&
    !hasServerOperationalAuthority(requirement)
  ) {
    // eslint-disable-next-line no-console
    console.warn(
      '[requirementTakeActionResolver] take_action without primary and no canonical authority — authority_missing (prefer API envelope).',
    );
  }

  const canonical = resolveCanonicalPrimaryAction(requirement);
  if (canonical?.label) {
    return mapCanonicalPrimaryToRequirementAction(requirement, canonical);
  }

  return authorityMissingRequirementAction(requirement);
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
