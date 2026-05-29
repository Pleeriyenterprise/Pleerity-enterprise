/**
 * Canonical frontend operational authority contract.
 * Frontend may present, group, format, elevate, and rank — but must not invent authority.
 * All primary/list guidance resolves from server envelopes in documented precedence order.
 */
import {
  getOperationalCognition,
  getListGuidance,
  heroPrimaryFromCognition,
  truthWarningsFromCognition,
} from './operationalCognition';

/** @typedef {'operational_cognition'|'take_action'|'business_actions'|'operational_continuation'|'next_actions'|null} AuthoritySource */

/**
 * Canonical primary action resolution — no client invention beyond server fields.
 * @param {Record<string, unknown>|null|undefined} entity
 * @returns {{ label: string, key?: string, url?: string, continuation?: boolean, authority_source: AuthoritySource }|null}
 */
export function resolveCanonicalPrimaryAction(entity) {
  if (!entity || typeof entity !== 'object') return null;

  const hero = heroPrimaryFromCognition(getOperationalCognition(entity));
  if (hero?.label) {
    return {
      label: String(hero.label).trim(),
      key: hero.key,
      url: hero.url,
      continuation: hero.continuation,
      authority_source: 'operational_cognition',
    };
  }

  const cont = entity.operational_continuation;
  if (cont?.has_active_lineage && cont?.continuation_cta?.label) {
    const cta = cont.continuation_cta;
    return {
      label: String(cta.label).trim(),
      key: cta.key,
      url: cta.url,
      continuation: true,
      authority_source: 'operational_continuation',
    };
  }

  const ta =
    entity.take_action?.primary ||
    entity.metadata?.take_action?.primary;
  if (ta?.label) {
    return {
      label: String(ta.label).trim(),
      key: ta.intent || ta.id,
      url: ta.route,
      continuation: Boolean(ta.continuation),
      authority_source: 'take_action',
    };
  }

  const nextActions = entity.next_actions;
  if (Array.isArray(nextActions) && nextActions[0]?.label) {
    const n = nextActions[0];
    return {
      label: String(n.label).trim(),
      key: n.id,
      url: n.url,
      authority_source: 'next_actions',
    };
  }

  const actions = entity.business_actions;
  if (Array.isArray(actions) && actions.length) {
    const primary = actions.find((a) => a?.primary) || actions[0];
    if (primary?.label) {
      return {
        label: String(primary.label).trim(),
        key: primary.intent || primary.id,
        url: primary.route || primary.navigate,
        authority_source: 'business_actions',
      };
    }
  }

  return null;
}

/**
 * Whether entity carries any server-derived operational authority (not client-invented).
 * @param {Record<string, unknown>|null|undefined} entity
 */
export function hasServerOperationalAuthority(entity) {
  return resolveCanonicalPrimaryAction(entity) != null;
}

/**
 * Degraded or stale operational truth on an entity.
 * @param {Record<string, unknown>|null|undefined} entity
 */
export function isDegradedOperationalEntity(entity) {
  const cog = getOperationalCognition(entity);
  if (!cog) return false;
  if (cog.degraded_state?.active) return true;
  if (cog.stale_state?.active) return true;
  const lg = cog.list_guidance;
  if (lg?.degraded_warning || lg?.stale_warning) return true;
  return truthWarningsFromCognition(cog).length > 0;
}

export { getListGuidance, getOperationalCognition, heroPrimaryFromCognition, truthWarningsFromCognition };
