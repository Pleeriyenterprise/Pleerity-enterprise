/**
 * Property Compliance tab: obligation copy aligned with canonical requirement narrative + take_action resolver.
 */
import { resolveRequirementAction } from './requirementTakeActionResolver';
import { isRequirementMissingDocument } from './propertyDocumentsMatrix';
import { pickCanonicalWhyItMattersShort } from './requirementCanonicalNarrative';
import { workflowAwareMissingEvidenceLabel } from './evidenceStatus';
import { projectResolvedRequirementSemantics } from './resolvedRequirementViewModel';

function resolvedProjectionForRequirementRow(r) {
  if (!r || typeof r !== 'object' || typeof r.take_action !== 'object') return null;
  return projectResolvedRequirementSemantics(r, { pagePropertyId: r?.property_id || null });
}

/**
 * Inline compliance narrative (short why + next step) — same canonical "why" source as RequirementIntelligenceModal.
 * @param {Record<string, unknown>} req
 * @returns {{ why_it_matters: string, recommended_action_text: string }}
 */
export function canonicalComplianceInlineNarrative(req) {
  const whyShort = pickCanonicalWhyItMattersShort(req);
  const sem = resolvedProjectionForRequirementRow(req);
  const ta = sem?.cta || resolveRequirementAction(req, {});
  const next =
    ta.primary_action_handler !== 'none' && String(ta.primary_action_label || '').trim()
      ? String(ta.primary_action_label).trim()
      : 'Open Requirement details for full guidance.';
  return {
    why_it_matters: whyShort || 'Review this requirement on the Documents tab or open Requirement details for full context.',
    recommended_action_text: `Next step: ${next}`,
  };
}

/** Plain-language “what changed” from the obligation row only (no API). */
export function complianceWhatChangedLine(req) {
  const s = String(req?.status || '').toUpperCase();
  const hasDoc = !!req?.evidence_doc_id;
  const days =
    req?.days_to_expiry != null
      ? req.days_to_expiry
      : null;
  const due = req?.expiry_date || req?.due_date;
  const est = req?.date_source === 'SYSTEM_ESTIMATED';

  if (isRequirementMissingDocument(req)) {
    return 'There is no linked document on file for this requirement yet.';
  }
  if (s === 'PENDING' && hasDoc) {
    return 'A document is linked; it still needs to be confirmed on the Documents tab (or processing may be in progress).';
  }
  if (['OVERDUE', 'EXPIRED'].includes(s)) {
    if (due) {
      return `${est ? 'Estimated ' : ''}Due date has passed (${String(due).slice(0, 10)}). Renew and upload a document.`;
    }
    return 'This requirement is past its due date. Renew and upload a document.';
  }
  if (s === 'EXPIRING_SOON') {
    if (days != null && days >= 0) {
      return `Due within ${days} day${days === 1 ? '' : 's'}. Plan renewal before the deadline.`;
    }
    if (due) {
      return `${est ? 'Estimated ' : ''}Due ${String(due).slice(0, 10)}. Renew before it expires.`;
    }
    return 'This requirement is due soon. Plan renewal before the deadline.';
  }
  if (['COMPLIANT', 'VALID'].includes(s) && hasDoc) {
    return 'A document is on file and this requirement is currently valid.';
  }
  if (['NOT_APPLICABLE', 'NOT_REQUIRED', 'WAIVED'].includes(s)) {
    return 'This requirement is marked as not applicable or waived for this property.';
  }
  return 'Review the current status and due date in the table above.';
}

/** Standardised status nouns for the obligations matrix. */
export function complianceObligationStatusLabel(r) {
  const s = String(r?.status || '').toUpperCase();
  const sem = resolvedProjectionForRequirementRow(r);
  const code = String(r?.canonical_requirement_code || r?.requirement_code || r?.requirement_type || '').trim().toLowerCase();
  const tenancyStatus = String(r?.tenancy_agreement_status_text || '').trim();
  if (code === 'tenancy_agreement' && tenancyStatus) return tenancyStatus;
  if (['NOT_APPLICABLE', 'NOT_REQUIRED', 'WAIVED'].includes(s)) return 'Not applicable';
  if (['OVERDUE', 'EXPIRED'].includes(s)) return 'Overdue';
  if (s === 'EXPIRING_SOON') return 'Expiring';
  if (isRequirementMissingDocument(r)) return sem?.missing_evidence_label || workflowAwareMissingEvidenceLabel(r);
  return 'Valid';
}

/**
 * Property Compliance surfaces (urgent strip, full matrix, etc.): API `take_action.secondary` often
 * duplicates a Documents/upload deep-link while the primary opens guided / record workflows that already
 * allow optional evidence. Suppress that duplicate CTA in the UI only — resolver and routes unchanged.
 * Heuristic is intentionally narrow: `/documents` routes and upload-shaped labels only.
 * @param {{ secondary_action?: { label?: string, route?: string } | null }} taRow
 * @returns {boolean}
 */
export function isRedundantUploadStyleSecondaryAction(taRow) {
  if (!taRow || typeof taRow !== 'object') return false;
  const sec = taRow.secondary_action;
  if (!sec || typeof sec !== 'object') return false;
  const route = String(sec.route || '');
  const label = String(sec.label || '').toLowerCase();
  if (route.includes('/documents')) return true;
  if (/\bupload\b/.test(label)) return true;
  if (label.includes('supporting evidence')) return true;
  if (label.includes('deposit evidence')) return true;
  if (label.includes('signed agreement')) return true;
  if (label.includes('delivery proof')) return true;
  return false;
}

/** Standardised primary action — delegates to unified Take Action resolver (single CTA contract). */
export function complianceObligationPrimaryAction(r) {
  const sem = resolvedProjectionForRequirementRow(r);
  const ta = sem?.cta || resolveRequirementAction(r, {});
  let verb = 'upload';
  if (ta.primary_action_handler === 'guided_evidence') verb = 'resolve';
  if (ta.primary_action_handler === 'guided_evidence_error') verb = 'unavailable';
  else if (ta.actionType === 'JOB') verb = 'book';
  else if (ta.actionType === 'OBLIGATION') verb = 'review';
  return { verb, label: ta.primary_action_label, secondary: ta.secondary_action || null, ta };
}

function summarizeRequirementCounts(reqs) {
  let missing = 0;
  let expiring = 0;
  let overdue = 0;
  reqs.forEach((r) => {
    const s = String(r.status || '').toUpperCase();
    if (isRequirementMissingDocument(r)) missing += 1;
    else if (s === 'EXPIRING_SOON') expiring += 1;
    else if (['OVERDUE', 'EXPIRED'].includes(s)) overdue += 1;
  });
  return { missing, expiring, overdue };
}

/**
 * One-line next step from obligations data only (no extra APIs).
 * @param {(r: object) => string} rowTitle
 */
export function compliancePriorityRecommendedNext(requirements, urgentOrdered, rowTitle) {
  const first = urgentOrdered[0];
  if (first) {
    const act = complianceObligationPrimaryAction(first);
    const title = rowTitle(first) || 'this requirement';
    if (act.verb === 'upload') return `${act.label} for ${title}.`;
    if (act.verb === 'resolve') return `${act.label} for ${title}.`;
    if (act.verb === 'renew') return `Renew documents for ${title}.`;
    return `Review ${title} on the Documents tab.`;
  }
  const { missing, expiring, overdue } = summarizeRequirementCounts(requirements);
  if (missing > 0) {
    return `Upload documents for ${missing} requirement${missing === 1 ? '' : 's'} with nothing on file.`;
  }
  if (overdue > 0) {
    return `Address ${overdue} overdue requirement${overdue === 1 ? '' : 's'}.`;
  }
  if (expiring > 0) {
    return `Plan renewal for ${expiring} requirement${expiring === 1 ? '' : 's'} due soon.`;
  }
  if (requirements.length > 0) {
    return 'Review requirements and keep documents up to date on the Documents tab.';
  }
  return 'Complete property setup so applicable requirements appear here.';
}
