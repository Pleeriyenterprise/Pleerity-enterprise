/**
 * Customer-facing compliance score explanation copy — operational, human-readable, future-safe.
 * Does not describe internal weighting, models, or scoring architecture.
 */

/** @typedef {'legal_core'|'documentation_completeness'|'operational_responsiveness'|'recency_maintenance_confidence'} ScoreAreaKey */

export const SCORE_AREA_LABELS = {
  legal_core: 'Core legal requirements',
  documentation_completeness: 'Accepted evidence',
  operational_responsiveness: 'Maintenance & actions',
  recency_maintenance_confidence: 'Up-to-date records',
};

export const SCORE_AREA_SHORT_LABELS = {
  legal_core: 'Legal',
  documentation_completeness: 'Evidence',
  operational_responsiveness: 'Maintenance',
  recency_maintenance_confidence: 'Renewals',
};

export const SCORE_AREA_DESCRIPTIONS = {
  legal_core:
    'Key certificates and legal obligations for your property and area. Accepted, in-date evidence helps; missing, overdue, or expiring items lower this.',
  documentation_completeness:
    'How many required items have evidence that has been accepted — uploads alone may not count until review is complete.',
  operational_responsiveness:
    'Open maintenance issues and overdue actions can lower your score until they are resolved.',
  recency_maintenance_confidence:
    'Items due soon and open follow-ups can lower your score until renewals or reviews are complete.',
};

export const SCORE_COMPONENTS_SECTION_TITLE = 'How you\'re doing in each area';

export const SCORE_COMPONENTS_SECTION_INTRO =
  'These percentages show how well you are meeting each part of your compliance picture right now — not a fixed formula you can reverse-engineer from counts alone.';

export const SCORE_COMPONENTS_FALLBACK =
  'Area-by-area scores appear here once each property has been fully assessed. Your headline score and recommended actions still reflect your current records.';

export const SCORE_EXPLANATION_DASHBOARD_KPI =
  'Reflects your current requirements, accepted evidence, maintenance items, and upcoming renewals. Updates when you upload documents, confirm dates, or resolve linked work. Guidance only — not legal advice.';

export const SCORE_EXPLANATION_TOGGLE_LABEL = 'What affects this score?';

export const SCORE_FRAMEWORK_TITLE = 'Understanding your compliance score';

export const SCORE_FRAMEWORK_INTRO =
  'Your score reflects what we know about your properties today: required documents, accepted evidence, overdue or expiring items, and open maintenance work. Some requirements matter more than others, but you do not need to calculate that yourself — focus on the actions shown on this page.';

export const SCORE_FRAMEWORK_AREAS_INTRO = 'Each property score looks at four areas:';

export const SCORE_FRAMEWORK_AREA_BULLETS = [
  {
    title: SCORE_AREA_LABELS.legal_core,
    body: 'Required legal and safety obligations for the property and its area — current, accepted evidence helps; gaps and overdue items lower the score.',
  },
  {
    title: SCORE_AREA_LABELS.documentation_completeness,
    body: 'Required items with evidence that has been accepted, not merely uploaded.',
  },
  {
    title: SCORE_AREA_LABELS.operational_responsiveness,
    body: 'Open maintenance issues and overdue actions until they are resolved.',
  },
  {
    title: SCORE_AREA_LABELS.recency_maintenance_confidence,
    body: 'Renewals and follow-ups that are due soon or still open.',
  },
];

export const SCORE_FRAMEWORK_PORTFOLIO =
  'If you have more than one property, your overall score is the average of each property\'s score.';

export const SCORE_FRAMEWORK_RISK_BANDS =
  'Risk bands use the same ranges across the portal: 80–100 lower risk; 60–79 moderate; 40–59 high; 0–39 critical.';

export const SCORE_FRAMEWORK_DISCLAIMER =
  'This score is guidance based on your records in the portal. It is not legal advice and does not certify compliance. Open Compliance score for detail and next steps.';

export const SCORE_METHODOLOGY_INTRO =
  'Your score is based on your current requirements, documents, dates, and maintenance status. It updates when those records change.';

export const SCORE_METHODOLOGY_PORTFOLIO =
  'Your overall score is the average of each property\'s score. Each property is assessed from its own requirements and documents.';

export const SCORE_ADVANCED_DETAILS_TITLE = 'More detail';

export const SCORE_ADVANCED_DETAILS_BODY = [
  'Your score improves when required documents are uploaded and accepted, dates are confirmed, overdue items are cleared, and renewals are kept current.',
  'Your score can fall when evidence is missing or not yet accepted, items become overdue or due soon, or maintenance issues and linked actions stay open.',
  'Accepted evidence means a document has passed review or external verification — an upload on its own may not be enough until it is accepted.',
  SCORE_FRAMEWORK_PORTFOLIO,
];

export const SCORE_PORTFOLIO_TOOLTIP =
  'If you have multiple properties, the number shown is the average of each property\'s score.';

export const SCORE_HEADLINE_DISCLAIMER =
  'Guidance based on your records in the portal. Not legal advice.';

export const SCORE_DEFINITIONS = [
  {
    term: 'Valid',
    definition: 'The requirement is current and within date; documents are accepted where required.',
  },
  {
    term: 'Expiring soon',
    definition: 'The due or expiry date is approaching (typically within the next 30–60 days, depending on the requirement).',
  },
  {
    term: 'Overdue',
    definition: 'The due or expiry date has passed — action is needed.',
  },
  {
    term: 'Applicable vs not applicable',
    definition: 'An item counts only if it applies to this property (for example, gas safety where gas is present). Items marked not applicable are excluded.',
  },
  {
    term: 'Confirmed vs estimated dates',
    definition: 'Confirmed: the date comes from an accepted document or your entry. Estimated: the date is provisional until confirmed.',
  },
  {
    term: 'Tracked requirement',
    definition: 'A compliance item (such as gas safety or EICR) that applies to the property and is included in your score.',
  },
];

export const SCORE_SCOPE_ITEMS = {
  included:
    'Applicable requirements for each property (for example gas safety, EICR, EPC, and licence where configured).',
  excluded:
    'Local council rules unless configured, optional uploads you chose not to track, and evidence not yet uploaded or accepted.',
  tracked:
    'A requirement counts only when it applies to that property.',
  updates:
    'The score refreshes when documents, dates, applicability, or status change.',
};

/**
 * @param {ScoreAreaKey|string|null|undefined} key
 * @returns {string}
 */
export function scoreAreaLabel(key) {
  return SCORE_AREA_LABELS[key] || String(key || 'Score area');
}

/**
 * @param {ScoreAreaKey|string|null|undefined} key
 * @returns {string}
 */
export function scoreAreaDescription(key) {
  return SCORE_AREA_DESCRIPTIONS[key] || '';
}

/** Terms that must not appear in customer-facing scoring explanation copy. */
export { SCORING_EXPLANATION_FORBIDDEN_TERMS } from './trustLanguageGovernance';
