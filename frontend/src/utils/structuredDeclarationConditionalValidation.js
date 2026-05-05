/** Must match backend RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE. */
export const RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE =
  'Enter a follow-up check date for time-limited Right to Rent checks.';

/** Fallback when policy omits rules (e.g. registry-only evidence_resolution). Mirrors server defaults. */
export const RIGHT_TO_RENT_STRUCTURED_DECLARATION_CONDITIONAL_RULES = [
  {
    id: 'follow_up_date_when_time_limited_or_follow_up',
    when_any: [
      { field: 'right_to_rent_status', equals: 'time_limited' },
      { field: 'follow_up_required', equals: true },
    ],
    require_non_empty_fields: ['follow_up_date'],
    message: RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE,
  },
];

export function conditionalRuleValueMatches(actual, expected) {
  if (expected === true || expected === false) {
    if (typeof actual === 'boolean') return actual === expected;
    if (typeof actual === 'string') {
      const u = actual.trim().toUpperCase();
      if (expected === true) return ['YES', 'TRUE', '1', 'Y'].includes(u);
      return ['NO', 'FALSE', '0', 'N'].includes(u);
    }
    return false;
  }
  if (typeof expected === 'string') {
    return String(actual ?? '')
      .trim()
      .toLowerCase() === expected.trim().toLowerCase();
  }
  return actual === expected;
}

/**
 * @param {Array<{ when_any: Array<{field: string, equals: unknown}>, require_non_empty_fields: string[], message: string }>} rules
 * @param {Record<string, { answer?: unknown }>} structuredPayload checklist payload (same shape as API structured_fields)
 * @returns {string|null} first error message or null
 */
export function evaluateStructuredDeclarationConditionalRules(rules, structuredPayload) {
  if (!Array.isArray(rules) || !rules.length || !structuredPayload || typeof structuredPayload !== 'object') {
    return null;
  }
  const getAns = (id) => {
    const row = structuredPayload[id];
    if (row && typeof row === 'object' && 'answer' in row) return row.answer;
    return null;
  };
  const nonEmpty = (id) => {
    const v = getAns(id);
    if (v == null) return false;
    if (typeof v === 'string') return v.trim() !== '';
    return true;
  };
  for (const rule of rules) {
    const whenAny = rule.when_any;
    if (!Array.isArray(whenAny)) continue;
    const matched = whenAny.some((cond) => {
      if (!cond || !cond.field) return false;
      return conditionalRuleValueMatches(getAns(cond.field), cond.equals);
    });
    if (matched) {
      const fields = rule.require_non_empty_fields || [];
      for (const fid of fields) {
        if (!nonEmpty(fid)) return rule.message || null;
      }
    }
  }
  return null;
}
