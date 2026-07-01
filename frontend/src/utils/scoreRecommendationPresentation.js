/**
 * Score recommendation presentation authority (SCORE-RECOMMENDATION-PRESENTATION-AUTHORITY-01).
 *
 * Presentation only — never re-rank, re-score, deduplicate, suppress, or merge backend recommendations.
 * Backend: compliance_score.recommendations / top_next_actions (impact_points order).
 */
import { requirementLabel } from '../domain/presentDomain';
import {
  buildEntityRoute,
  normalizeRouteId,
  resolvePropertyPath,
} from './clientPortalNavigation';
import { getPropertyDisplayName } from './propertyDisplayName';
import {
  isAssuranceQuickAction,
  quickActionSupportingCopy,
  resolveQuickActionDisplayText,
} from './dashboardScoreWidgetLabels';
import { RECOMMENDATION_LENS } from './lifecycleAuthorityCopy';

export const SCORE_RECOMMENDATION_GROUP_THRESHOLD = 4;

export function scoreRecommendationGroupingKey(rec) {
  const code = String(rec?.requirement_code || '').trim().toLowerCase();
  if (code) return `code:${code}`;
  const label = String(rec?.display_label || '').trim().toLowerCase();
  if (label) return `label:${label}`;
  return `action:${String(rec?.action || '').slice(0, 48)}`;
}

/**
 * @param {{ scoreBreakdownByProperty?: unknown[], portfolioProperties?: unknown[], properties?: unknown[] }} sources
 */
export function buildPropertyLookup(sources = {}) {
  const map = new Map();
  const add = (list) => {
    if (!Array.isArray(list)) return;
    for (const p of list) {
      const id = normalizeRouteId(p?.property_id);
      if (id && !map.has(id)) map.set(id, p);
    }
  };
  add(sources.scoreBreakdownByProperty);
  add(sources.portfolioProperties);
  add(sources.properties);
  return map;
}

export function matchRequirementsForRecommendation(rec, requirementsList) {
  const recPropertyId = normalizeRouteId(rec.property_id || rec.related_property_id);
  const recReqId = normalizeRouteId(rec.requirement_id || rec.related_requirement_id);
  const codeLower = String(rec.requirement_code || '').trim().toLowerCase();
  const candidates = (requirementsList || []).filter((r) => {
    const rCode = String(r.requirement_code || r.requirement_type || '').trim().toLowerCase();
    const propOk = recPropertyId ? String(r.property_id || '') === recPropertyId : true;
    const codeOk = codeLower ? rCode === codeLower : true;
    return propOk && codeOk;
  });
  const sorted = [...candidates].sort((a, b) => {
    const rank = (row) => {
      const st = String(row?.status || '').toUpperCase();
      if (st === 'OVERDUE' || st === 'EXPIRED') return 0;
      if (st === 'EXPIRING_SOON') return 1;
      return 2;
    };
    return rank(a) - rank(b);
  });
  const bestReq = sorted[0] || null;
  return {
    candidates: sorted,
    bestRequirementId: recReqId || normalizeRouteId(bestReq?.requirement_id),
    bestPropertyId: recPropertyId || normalizeRouteId(bestReq?.property_id),
    bestReq,
  };
}

export function resolveRecommendationTitle(rec, match, requirementLabelFn = requirementLabel) {
  let actionDisplay = rec.action || '';
  const code = rec.requirement_code;
  const displayLbl = rec.display_label || (code ? requirementLabelFn(code) : '');
  if (code && actionDisplay.includes(code)) {
    actionDisplay = actionDisplay.split(code).join(displayLbl);
  }
  return resolveQuickActionDisplayText(
    actionDisplay,
    match.bestReq,
    displayLbl,
    match.candidates,
  );
}

function parseDueDays(iso) {
  if (!iso) return null;
  try {
    const days = Math.ceil(
      (new Date(String(iso).replace('Z', '+00:00')).getTime() - Date.now()) / 86400000,
    );
    return Number.isFinite(days) ? days : null;
  } catch {
    return null;
  }
}

export function resolveOperationalReason(rec, requirementRow) {
  const action = String(rec?.action || '').toLowerCase();
  if (requirementRow) {
    const st = String(requirementRow.status || '').toUpperCase();
    const due =
      requirementRow.due_date ||
      requirementRow.confirmed_expiry_date ||
      requirementRow.extracted_expiry_date;
    if (st === 'OVERDUE' || st === 'EXPIRED') return 'Prevents overdue compliance';
    if (st === 'EXPIRING_SOON') {
      const days = parseDueDays(due);
      if (days != null && days >= 0) return `Due in ${days} day${days === 1 ? '' : 's'}`;
      return 'Avoids certificate expiry';
    }
    if (st === 'MISSING' || st === 'PENDING') return 'Missing evidence for scoring';
  }
  if (action.includes('renew') && action.includes('expiry')) return 'Avoids certificate expiry';
  if (action.includes('upload')) return 'Improves documented compliance';
  if (action.includes('overdue')) return 'Prevents overdue compliance';
  if (action.includes('verification') || action.includes('assurance')) return 'Improves assurance confidence';
  return 'Addresses an active compliance obligation';
}

export function resolveExpectedOutcome(rec, isAssurance) {
  if (isAssurance) return quickActionSupportingCopy(true);
  const impact = String(rec?.impact || '').trim();
  if (impact) return `Improves compliance score (${impact})`;
  return 'Improves compliance score';
}

export function resolvePriorityPresentation(rec) {
  const p = String(rec?.priority || 'medium').toLowerCase();
  if (p === 'info') return { label: 'Optional', tone: 'neutral' };
  if (p === 'critical' || p === 'high') return { label: 'High priority', tone: 'high' };
  if (p === 'medium') return { label: 'Medium priority', tone: 'medium' };
  return { label: 'Monitor', tone: 'low' };
}

/**
 * @param {Record<string, unknown>} rec Backend recommendation (unchanged authority)
 * @param {object} [options]
 */
export function prepareScoreRecommendationPresentation(rec, options = {}) {
  const {
    requirementsList = [],
    propertyLookup = new Map(),
    requirementLabelFn = requirementLabel,
    lens = RECOMMENDATION_LENS.kpi,
    defaultPropertyId = null,
  } = options;

  const match = matchRequirementsForRecommendation(rec, requirementsList);
  if (!match.bestPropertyId && defaultPropertyId) {
    match.bestPropertyId = normalizeRouteId(defaultPropertyId);
  }
  const propertyMeta = (match.bestPropertyId && propertyLookup.get(match.bestPropertyId)) || {};
  const propertyName =
    getPropertyDisplayName(propertyMeta) ||
    (match.bestPropertyId ? `Property ${String(match.bestPropertyId).slice(0, 8)}` : null);
  const requirementName =
    rec.display_label ||
    (rec.requirement_code ? requirementLabelFn(rec.requirement_code) : 'Requirement');
  const title = resolveRecommendationTitle(rec, match, requirementLabelFn);
  const isAssurance =
    rec.action_kind === 'ASSURANCE_CONFIDENCE_OPPORTUNITY' ||
    rec.priority === 'info' ||
    isAssuranceQuickAction(title, match.bestReq) ||
    match.candidates.some((r) => isAssuranceQuickAction(title, r));

  const fixNowPath = buildEntityRoute(
    {
      requirement_id: match.bestRequirementId,
      property_id: match.bestPropertyId,
      work_order_id: normalizeRouteId(rec.work_order_id || rec.related_work_order_id),
      mode: isAssurance ? 'view' : 'upload',
    },
    '/today',
  );

  return {
    identityKey: `${match.bestPropertyId || ''}|${rec.requirement_code || ''}|${match.bestRequirementId || ''}`,
    groupingKey: scoreRecommendationGroupingKey(rec),
    title,
    requirementName,
    propertyName,
    propertyId: match.bestPropertyId,
    requirementId: match.bestRequirementId,
    jurisdiction:
      propertyMeta.effective_jurisdiction_label ||
      propertyMeta.jurisdiction ||
      propertyMeta.scoring_jurisdiction_bucket ||
      null,
    propertyType: propertyMeta.compliance_basis || propertyMeta.property_type || null,
    operationalReason: resolveOperationalReason(rec, match.bestReq),
    expectedOutcome: resolveExpectedOutcome(rec, isAssurance),
    priority: resolvePriorityPresentation(rec),
    isAssurance,
    primaryCtaLabel: isAssurance ? 'View' : 'Fix now',
    primaryCtaPath: fixNowPath,
    hasPrimaryCta: fixNowPath !== '/today',
    propertyCtaPath: resolvePropertyPath(match.bestPropertyId),
    requirementCtaPath: buildEntityRoute(
      {
        requirement_id: match.bestRequirementId,
        property_id: match.bestPropertyId,
        mode: 'requirement',
      },
      '',
    ),
    lens,
    raw: rec,
  };
}

/**
 * Build display units in backend order. Group only when 4+ share the same grouping key.
 * @param {Array<Record<string, unknown>>} recommendations
 */
export function buildScoreRecommendationDisplayUnits(recommendations, options = {}) {
  const list = Array.isArray(recommendations) ? recommendations : [];
  const threshold = options.groupThreshold ?? SCORE_RECOMMENDATION_GROUP_THRESHOLD;
  const counts = new Map();
  for (const rec of list) {
    const k = scoreRecommendationGroupingKey(rec);
    counts.set(k, (counts.get(k) || 0) + 1);
  }
  const groupable = new Set(
    [...counts.entries()].filter(([, n]) => n >= threshold).map(([k]) => k),
  );
  const consumed = new Set();
  const units = [];
  for (let i = 0; i < list.length; i += 1) {
    if (consumed.has(i)) continue;
    const rec = list[i];
    const key = scoreRecommendationGroupingKey(rec);
    if (groupable.has(key)) {
      const indices = [];
      const items = [];
      list.forEach((r, idx) => {
        if (scoreRecommendationGroupingKey(r) === key) {
          indices.push(idx);
          items.push(r);
          consumed.add(idx);
        }
      });
      units.push({
        type: 'group',
        groupingKey: key,
        items,
        indices,
        firstIndex: Math.min(...indices),
      });
    } else {
      units.push({ type: 'individual', rec, index: i });
      consumed.add(i);
    }
  }
  return units;
}

export function groupPresentationTitle(items, requirementLabelFn = requirementLabel) {
  const first = items[0] || {};
  const name = first.display_label || (first.requirement_code ? requirementLabelFn(first.requirement_code) : 'Requirements');
  return name;
}
