/**
 * User-facing copy for property Operating tab activity (defense in depth vs timeline API).
 */

const SCORE_CHANGE_REASON_LABELS = {
  CLIENT_JURISDICTION_UPDATED: 'Jurisdiction updated',
  EXPIRY_RULE: 'Certificate expiry updated',
  EXPIRY_JOB: 'Certificate expiry updated',
  PROPERTY_UPDATED: 'Property details updated',
  SCORE_RECALCULATED: 'Compliance score updated',
  SCHEDULED_PROPERTY_BATCH: 'Scheduled compliance update',
  DOCUMENT_UPLOADED: 'Document uploaded',
  DOCUMENT_DELETED: 'Document removed',
  REQUIREMENT_CHANGED: 'Requirement updated',
  EXPIRY_ROLLOVER: 'Expiry rollover',
  LAZY_BACKFILL: 'Compliance score refreshed',
};

/**
 * @param {string|null|undefined} s
 * @returns {string|null|undefined}
 */
export function humanizeOperatingActivityText(s) {
  if (s == null || typeof s !== 'string') return s;
  const t = s.trim();
  if (!t) return t;
  const key = t.toUpperCase();
  if (SCORE_CHANGE_REASON_LABELS[key]) return SCORE_CHANGE_REASON_LABELS[key];
  const slug = t.toUpperCase().replace(/\s+/g, '_');
  if (SCORE_CHANGE_REASON_LABELS[slug]) return SCORE_CHANGE_REASON_LABELS[slug];
  if (/^[A-Z][A-Z0-9_]+$/.test(key)) return 'Update recorded';
  return t;
}

/**
 * @param {object} item
 * @returns {object}
 */
export function humanizeOperatingFeedItem(item) {
  if (!item || typeof item !== 'object') return item;
  const title = humanizeOperatingActivityText(item.title);
  let description = item.description != null ? humanizeOperatingActivityText(item.description) : null;
  if (description && title && description === title) description = null;
  return { ...item, title, description };
}

/**
 * @param {object[]|null|undefined} items
 * @returns {object[]}
 */
export function humanizeOperatingFeedItems(items) {
  if (!Array.isArray(items)) return [];
  return items.map(humanizeOperatingFeedItem);
}
