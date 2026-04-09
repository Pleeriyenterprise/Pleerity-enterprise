/**
 * Property timeline: hide internal codes in titles/descriptions (defense in depth vs API).
 */

const SCREAMING_SNAKE = /^[A-Z][A-Z0-9_]+$/;

const SCORE_REASON_COPY = {
  CLIENT_JURISDICTION_UPDATED: 'Your portfolio or property region changed, so scoring rules were re-applied.',
  EXPIRY_RULE: 'Expiry rules were applied to obligation dates and the score was refreshed.',
  EXPIRY_JOB: 'A background check refreshed obligation dates and the compliance score.',
  PROPERTY_UPDATED: 'Property details changed; obligations and scoring were refreshed where needed.',
  SCORE_RECALCULATED: 'The compliance score was recalculated from your latest evidence and data.',
  SCHEDULED_PROPERTY_BATCH: 'An automated compliance pass ran for this property.',
  DOCUMENT_UPLOADED: 'A document was added or updated.',
  DOCUMENT_DELETED: 'A document was removed.',
  REQUIREMENT_CHANGED: 'A requirement changed (status, dates, or evidence link).',
  EXPIRY_ROLLOVER: 'A certificate or obligation moved into a new expiry window.',
  LAZY_BACKFILL: 'Stored compliance data was refreshed to match current records.',
};

const LEDGER_EVENT_COPY = {
  SCHEDULED_RECALC: 'Scheduled processing updated compliance scoring.',
  REQUIREMENT_STATUS_CHANGED: 'An obligation’s status or dates changed.',
  CERT_DETAILS_CONFIRMED: 'Certificate or document details were confirmed.',
  DOCUMENT_UPLOADED: 'A document was added or updated.',
  DOCUMENT_STATUS_CHANGED: 'A document’s status changed.',
  DOCUMENT_REMOVED: 'A document was removed from the property file.',
  PROPERTY_ADDED: 'This property was added to your portfolio.',
  PROPERTY_UPDATED: 'Property information was updated.',
};

function narrativeForLedgerOrScore(eventType, category) {
  const k = String(eventType || '').trim().toUpperCase();
  if (SCORE_REASON_COPY[k]) return SCORE_REASON_COPY[k];
  if (LEDGER_EVENT_COPY[k]) return LEDGER_EVENT_COPY[k];
  if (category === 'EVIDENCE') return 'Document or certificate activity was recorded for this property.';
  if (category === 'COMPLIANCE') return 'Compliance obligations or scoring were updated.';
  if (category === 'MAINTENANCE') return 'A job or maintenance milestone was recorded.';
  return 'Activity was recorded for this property.';
}

/**
 * @param {object} item timeline API item
 * @returns {{ title: string, description: string }}
 */
export function presentPropertyTimelineItem(item) {
  let title = String(item?.title || '').trim() || 'Activity';
  let description = String(item?.description || '').trim();
  const eventType = String(item?.eventType || '').trim();
  const category = String(item?.category || '').trim();

  if (SCREAMING_SNAKE.test(description) && SCORE_REASON_COPY[description]) {
    description = SCORE_REASON_COPY[description];
  } else if (SCREAMING_SNAKE.test(description)) {
    description = narrativeForLedgerOrScore(description, category);
  }

  if (SCREAMING_SNAKE.test(title) && !SCORE_REASON_COPY[title]) {
    title = narrativeForLedgerOrScore(title, category);
  }

  if (title && description && title.toLowerCase() === description.toLowerCase()) {
    description = narrativeForLedgerOrScore(eventType, category);
  }

  if (!description) {
    description = narrativeForLedgerOrScore(eventType, category);
  }

  return { title, description };
}
