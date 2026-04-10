/**
 * Property timeline & score history: map internal codes to titles + descriptions.
 * Defense in depth vs API — never show raw trigger enums in UI.
 */

const SCREAMING_SNAKE = /^[A-Z][A-Z0-9_]+$/;
const ACTION_OUTCOME_RE = /^ACTION_OUTCOME:\s*([A-Za-z0-9_]+)$/i;

/** Short titles for score_change_log.reason and similar. */
const SCORE_REASON_TITLE = {
  CLIENT_JURISDICTION_UPDATED: 'Jurisdiction updated',
  EXPIRY_RULE: 'Certificate expiry check',
  EXPIRY_JOB: 'Certificate expiry check',
  PROPERTY_UPDATED: 'Property updated',
  SCORE_RECALCULATED: 'Compliance score updated',
  SCHEDULED_PROPERTY_BATCH: 'System update completed',
  DOCUMENT_UPLOADED: 'Document uploaded',
  DOCUMENT_DELETED: 'Document removed',
  DOCUMENT_REMOVED: 'Document removed',
  REQUIREMENT_CHANGED: 'Requirement updated',
  EXPIRY_ROLLOVER: 'Certificate rollover',
  LAZY_BACKFILL: 'Compliance score refreshed',
  PROVISIONING: 'Account provisioning',
  PROPERTY_ADDED: 'Property added',
  TRIGGER_PROVISIONING: 'Account provisioning',
};

/** Optional longer line (subtitle / table detail). */
const SCORE_REASON_DESCRIPTION = {
  CLIENT_JURISDICTION_UPDATED: 'Your portfolio or property region changed, so scoring rules were re-applied.',
  EXPIRY_RULE: 'Expiry rules were applied to requirement dates and the score was refreshed.',
  EXPIRY_JOB: 'A scheduled check refreshed certificate dates and the compliance score.',
  PROPERTY_UPDATED: 'Property details changed; requirements and scoring were refreshed where needed.',
  SCORE_RECALCULATED: 'The compliance score was recalculated from your latest documents and data.',
  SCHEDULED_PROPERTY_BATCH: 'An automated compliance pass ran for this property.',
  DOCUMENT_UPLOADED: 'A document was added or updated.',
  DOCUMENT_DELETED: 'A document was removed.',
  DOCUMENT_REMOVED: 'A document was removed from the property file.',
  REQUIREMENT_CHANGED: 'A requirement changed (status, dates, or document link).',
  EXPIRY_ROLLOVER: 'A certificate or requirement moved into a new expiry window.',
  LAZY_BACKFILL: 'Stored compliance data was refreshed to match current records.',
  PROVISIONING: 'Initial compliance data was set up for your portfolio.',
  PROPERTY_ADDED: 'This property was added to your portfolio.',
};

const ACTION_OUTCOME_TITLE = {
  CERTIFICATE_UPLOADED: 'Certificate uploaded',
  CERTIFICATE_VERIFIED: 'Certificate verified',
  ISSUE_CREATED: 'Issue logged',
  ISSUE_RESOLVED: 'Issue resolved',
  WORK_ORDER_COMPLETED: 'Job completed',
  REQUIREMENT_COMPLETED: 'Requirement completed',
  RISK_SIGNAL_ACKNOWLEDGED: 'Issue acknowledged',
  RISK_SIGNAL_RESOLVED: 'Issue resolved',
};

const ACTION_OUTCOME_DESCRIPTION = {
  CERTIFICATE_UPLOADED: 'A certificate was added; the compliance score was refreshed.',
  CERTIFICATE_VERIFIED: 'Certificate document was verified and the score was updated.',
  ISSUE_CREATED: 'A maintenance or compliance issue was recorded.',
  ISSUE_RESOLVED: 'An issue was resolved and scoring was recalculated.',
  WORK_ORDER_COMPLETED: 'A job was marked complete and the score was updated.',
  REQUIREMENT_COMPLETED: 'A compliance requirement was satisfied.',
  RISK_SIGNAL_ACKNOWLEDGED: 'An issue was acknowledged.',
  RISK_SIGNAL_RESOLVED: 'An issue was closed out.',
};

const SCORE_REASON_COPY_LEGACY = {
  ...SCORE_REASON_DESCRIPTION,
  SCHEDULED_RECALC: 'Scheduled processing updated compliance scoring.',
  REQUIREMENT_STATUS_CHANGED: 'A requirement’s status or dates changed.',
  CERT_DETAILS_CONFIRMED: 'Certificate or document details were confirmed.',
  DOCUMENT_STATUS_CHANGED: 'A document’s status changed.',
};

const LEDGER_EVENT_COPY = {
  SCHEDULED_RECALC: 'Scheduled processing updated compliance scoring.',
  REQUIREMENT_STATUS_CHANGED: 'A requirement’s status or dates changed.',
  CERT_DETAILS_CONFIRMED: 'Certificate or document details were confirmed.',
  DOCUMENT_UPLOADED: 'A document was added or updated.',
  DOCUMENT_STATUS_CHANGED: 'A document’s status changed.',
  DOCUMENT_REMOVED: 'A document was removed from the property file.',
  PROPERTY_ADDED: 'This property was added to your portfolio.',
  PROPERTY_UPDATED: 'Property information was updated.',
};

const FALLBACK_TITLE = 'System update';
const FALLBACK_DESCRIPTION = 'Your compliance position was updated based on the latest data we hold.';

/**
 * @param {string|null|undefined} raw score_change_log.reason or similar
 * @returns {{ title: string, description: string }}
 */
export function presentScoreChangeReason(raw) {
  const s = String(raw ?? '').trim();
  if (!s) {
    return { title: FALLBACK_TITLE, description: '' };
  }

  const actionMatch = s.match(ACTION_OUTCOME_RE);
  if (actionMatch) {
    const suffix = actionMatch[1].toUpperCase();
    const title = ACTION_OUTCOME_TITLE[suffix];
    if (title) {
      return {
        title,
        description: ACTION_OUTCOME_DESCRIPTION[suffix] || '',
      };
    }
    return {
      title: FALLBACK_TITLE,
      description: 'Your compliance position was refreshed after an outcome was recorded.',
    };
  }

  const slug = s.toUpperCase().replace(/\s+/g, '_');
  if (SCORE_REASON_TITLE[slug]) {
    return {
      title: SCORE_REASON_TITLE[slug],
      description: SCORE_REASON_DESCRIPTION[slug] || '',
    };
  }

  if (SCREAMING_SNAKE.test(s)) {
    return { title: FALLBACK_TITLE, description: FALLBACK_DESCRIPTION };
  }

  return { title: s, description: '' };
}

function narrativeForLedgerOrScore(eventType, category) {
  const k = String(eventType || '').trim().toUpperCase();
  if (SCORE_REASON_COPY_LEGACY[k]) return SCORE_REASON_COPY_LEGACY[k];
  if (LEDGER_EVENT_COPY[k]) return LEDGER_EVENT_COPY[k];
  if (category === 'EVIDENCE') return 'Document or certificate activity was recorded for this property.';
  if (category === 'COMPLIANCE') return 'Compliance requirements or scoring were updated.';
  if (category === 'MAINTENANCE') return 'A job or maintenance milestone was recorded.';
  return FALLBACK_DESCRIPTION;
}

function looksLikeInternalCode(value) {
  const t = String(value || '').trim();
  if (!t) return false;
  if (ACTION_OUTCOME_RE.test(t)) return true;
  if (SCREAMING_SNAKE.test(t)) return true;
  return false;
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

  if (looksLikeInternalCode(description)) {
    const pr = presentScoreChangeReason(description);
    description = pr.description || pr.title || FALLBACK_DESCRIPTION;
  } else if (SCREAMING_SNAKE.test(description) && SCORE_REASON_COPY_LEGACY[description]) {
    description = SCORE_REASON_COPY_LEGACY[description];
  }

  if (looksLikeInternalCode(title)) {
    const pr = presentScoreChangeReason(title);
    title = pr.title;
    if (!description) description = pr.description || narrativeForLedgerOrScore(eventType, category);
  } else if (SCREAMING_SNAKE.test(title) && !SCORE_REASON_TITLE[title]) {
    title = presentScoreChangeReason(title).title;
  }

  if (title && description && title.toLowerCase() === description.toLowerCase()) {
    description = narrativeForLedgerOrScore(eventType, category);
  }

  if (!description) {
    if (looksLikeInternalCode(eventType)) {
      const pr = presentScoreChangeReason(eventType);
      description = pr.description || narrativeForLedgerOrScore(eventType, category);
    } else {
      description = narrativeForLedgerOrScore(eventType, category);
    }
  }

  return { title, description };
}

/** Portal analytics (Reports) — allowlisted first-party event keys → labels. */
const PORTAL_ANALYTICS_LABELS = {
  TODAY_PAGE_REQUESTED: 'Today page opened (request)',
  TODAY_PAGE_VIEWED: 'Today page viewed',
  TODAY_PRIMARY_ACTION_TRIGGERED: 'Primary action used',
  activity_since_viewed: 'Activity after Today view',
  today_opened: 'Today hub opened',
};

/**
 * @param {string|null|undefined} eventKey
 * @returns {string} Human label; never raw internal key for known keys; title-cased fallback for unknown snake_case.
 */
export function presentPortalAnalyticsEvent(eventKey) {
  const k = String(eventKey ?? '').trim();
  if (!k) return FALLBACK_TITLE;
  if (PORTAL_ANALYTICS_LABELS[k]) return PORTAL_ANALYTICS_LABELS[k];
  const lower = k.toLowerCase();
  if (PORTAL_ANALYTICS_LABELS[lower]) return PORTAL_ANALYTICS_LABELS[lower];
  if (/^[a-z][a-z0-9_]*$/.test(k)) {
    return k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
  if (SCREAMING_SNAKE.test(k)) {
    return presentScoreChangeReason(k).title;
  }
  return k;
}
