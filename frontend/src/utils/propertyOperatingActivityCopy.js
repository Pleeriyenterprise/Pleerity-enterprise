/**
 * User-facing copy for property Operating tab activity (defense in depth vs timeline API).
 */

import { presentScoreChangeReason } from './timelinePresent';

/**
 * @param {string|null|undefined} s
 * @returns {string|null|undefined}
 */
export function humanizeOperatingActivityText(s) {
  if (s == null || typeof s !== 'string') return s;
  const t = s.trim();
  if (!t) return t;
  return presentScoreChangeReason(t).title;
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
