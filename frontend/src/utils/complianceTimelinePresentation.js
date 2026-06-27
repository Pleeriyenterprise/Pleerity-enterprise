/**
 * Compliance Timeline consumer presentation (Phase 2).
 * Single frontend source for customer-facing date display — do not infer locally.
 */

function parseIsoDate(value) {
  if (value == null || value === '') return null;
  try {
    const d = value instanceof Date ? value : new Date(String(value).replace('Z', '+00:00'));
    if (Number.isNaN(d.getTime())) return null;
    return d;
  } catch {
    return null;
  }
}

export function resolveComplianceTimeline(req) {
  return req?.compliance_timeline && typeof req.compliance_timeline === 'object'
    ? req.compliance_timeline
    : null;
}

export function getTimelinePrimaryDateIso(req) {
  if (req?.timeline_primary_date) return req.timeline_primary_date;
  const tl = resolveComplianceTimeline(req);
  if (tl?.primary_date) return tl.primary_date;
  return null;
}

/** ISO date for sorting / urgency — prefers timeline attention anchor. */
export function getTimelineSortDateIso(req) {
  const tl = resolveComplianceTimeline(req);
  const iso = tl?.effective_attention_date || getTimelinePrimaryDateIso(req);
  return iso || null;
}

export function getTimelineSortDate(req) {
  const iso = getTimelineSortDateIso(req);
  return iso ? parseIsoDate(iso) : null;
}

export function getTimelineDateLabel(req) {
  if (req?.timeline_primary_date_label) return req.timeline_primary_date_label;
  const tl = resolveComplianceTimeline(req);
  if (tl?.primary_date_label) return tl.primary_date_label;
  if (req?.date_label) return req.date_label;
  const iso = getTimelinePrimaryDateIso(req);
  if (!iso) return 'No date on file';
  const d = parseIsoDate(iso);
  if (!d) return 'No date on file';
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function isTimelineEstimated(req) {
  const tl = resolveComplianceTimeline(req);
  if (tl && typeof tl.is_estimated === 'boolean') return tl.is_estimated;
  return String(req?.timeline_primary_date_confidence || '').toUpperCase() === 'ESTIMATED';
}

export function isTimelineVerified(req) {
  const tl = resolveComplianceTimeline(req);
  if (tl && typeof tl.is_verified === 'boolean') return tl.is_verified;
  return String(req?.timeline_primary_date_confidence || '').toUpperCase() === 'VERIFIED';
}

export function getTimelinePrimaryConcept(req) {
  return req?.timeline_primary_date_concept
    || resolveComplianceTimeline(req)?.primary_date_concept
    || null;
}

/** Legacy fallback for edit forms only — not for display. */
export function getLegacyEditableDateIso(req) {
  return req?.confirmed_expiry_date || req?.extracted_expiry_date || req?.due_date || null;
}

export function daysUntilTimelineDate(req) {
  const d = getTimelineSortDate(req);
  if (!d) return null;
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const target = new Date(d);
  target.setHours(0, 0, 0, 0);
  return Math.ceil((target - now) / (1000 * 60 * 60 * 24));
}
