/**
 * Property Compliance tab: standardized obligation copy, rule-based explanations (registry),
 * and fallbacks aligned with backend services/explanation_engine.explain_compliance_alert.
 */
import { normalizeRequirementCode, requirementLabel, requirementDocumentUploadLabel } from '../domain/presentDomain';
import { isRequirementMissingDocument } from './propertyDocumentsMatrix';

function legalContextForCode(codeNorm) {
  const c = codeNorm || '';
  let legalContext = '';
  let riskOfNonCompliance = 'Non-compliance can lead to fines, invalid insurance, or legal liability.';
  if (c === 'gas_safety' || c === 'gas_safety_certificate' || c === 'cp12') {
    legalContext =
      'UK law requires annual gas safety inspections by a Gas Safe registered engineer. A valid certificate must be provided to tenants.';
    riskOfNonCompliance =
      'If the certificate expires while a tenant occupies the property, you may face fines or legal liability.';
  } else if (c.includes('eicr') || c === 'electrical_safety' || c === 'portable_appliance_test') {
    legalContext = 'Electrical Installation Condition Reports are required for rental properties at least every 5 years (England).';
    riskOfNonCompliance = 'Missing or overdue EICR can affect tenant safety and leave you exposed to enforcement action.';
  } else if (c === 'epc') {
    legalContext = 'An Energy Performance Certificate is required for rental properties; minimum E rating applies.';
    riskOfNonCompliance = 'Letting without a valid EPC can result in penalties.';
  } else if (c === 'hmo_license') {
    legalContext = 'An HMO licence is mandatory for properties that meet the licensing criteria in your area.';
    riskOfNonCompliance = 'Operating an unlicensed HMO can lead to significant fines and rent repayment orders.';
  } else if (c === 'fire_risk_assessment' || c === 'fire_alarm' || c === 'fire_detection') {
    legalContext =
      'Fire safety requirements (e.g. risk assessment, alarm inspection) are required for many rental and HMO properties.';
    riskOfNonCompliance = 'Failure to comply can result in enforcement and liability in the event of fire.';
  } else {
    legalContext =
      'This requirement is part of your compliance framework. Keeping evidence up to date helps maintain your score and reduces risk.';
  }
  return { legalContext, riskOfNonCompliance };
}

/**
 * Same structure as GET .../requirements/explanation (why_it_matters, recommended_action_text).
 * Safe to call for any requirement row from the property matrix.
 */
export function registryFallbackComplianceExplanation(req) {
  const codeNorm = normalizeRequirementCode(req?.requirement_code || req?.requirement_type || '');
  const status = String(req?.status || '').trim().toUpperCase();
  const title =
    (req?.title && String(req.title).trim()) ||
    (codeNorm ? requirementLabel(req.requirement_code || req.requirement_type) : '') ||
    'Requirement';
  const { legalContext, riskOfNonCompliance } = legalContextForCode(codeNorm);
  const hasDoc = !!req?.evidence_doc_id;

  let why_it_matters;
  if (status === 'PENDING' && hasDoc) {
    why_it_matters = `${legalContext} A document is on file but still needs to be confirmed so your compliance record stays accurate. ${riskOfNonCompliance}`;
  } else if (['OVERDUE', 'EXPIRED'].includes(status)) {
    why_it_matters = `${legalContext} ${riskOfNonCompliance} This item is overdue or expired.`;
  } else if (status === 'EXPIRING_SOON') {
    why_it_matters = `${legalContext} ${riskOfNonCompliance} This item is expiring soon; renew and upload evidence before the due date.`;
  } else if (status === 'PENDING' || status === 'MISSING' || status === 'MISSING_EVIDENCE') {
    why_it_matters = `${legalContext} Evidence or documentation is missing. ${riskOfNonCompliance}`;
  } else {
    why_it_matters = `${legalContext} ${riskOfNonCompliance}`;
  }

  const explanation_text = `${title}: ${why_it_matters}`;

  let recommended_action_text;
  if (status === 'PENDING' && hasDoc) {
    recommended_action_text = 'Open the Documents tab and confirm details for this obligation, or wait if the file is still being processed.';
  } else if (['OVERDUE', 'EXPIRED'].includes(status)) {
    recommended_action_text = 'Upload renewed evidence and update dates, or mark as not applicable if this obligation does not apply.';
  } else if (status === 'EXPIRING_SOON') {
    if (codeNorm.includes('gas')) {
      recommended_action_text = 'Schedule a Gas Safe inspection and upload the new certificate when complete.';
    } else if (codeNorm.includes('eicr') || codeNorm === 'electrical_safety') {
      recommended_action_text = 'Arrange an EICR inspection and upload the report when complete.';
    } else {
      recommended_action_text = 'Schedule the required inspection or renewal and upload evidence when complete.';
    }
  } else if (status === 'PENDING' || status === 'MISSING' || status === 'MISSING_EVIDENCE') {
    recommended_action_text = 'Upload the required document or evidence for this obligation.';
  } else {
    recommended_action_text = 'Review this obligation on the Documents tab and confirm or update evidence as needed.';
  }

  return {
    explanation_text,
    why_it_matters,
    recommended_action_text,
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
    return 'There is no linked document on file for this obligation yet.';
  }
  if (s === 'PENDING' && hasDoc) {
    return 'A document is linked; it still needs to be confirmed on the Documents tab (or processing may be in progress).';
  }
  if (['OVERDUE', 'EXPIRED'].includes(s)) {
    if (due) {
      return `${est ? 'Estimated ' : ''}Due date has passed (${String(due).slice(0, 10)}). Renew and upload evidence.`;
    }
    return 'This obligation is past its due date. Renew and upload evidence.';
  }
  if (s === 'EXPIRING_SOON') {
    if (days != null && days >= 0) {
      return `Due within ${days} day${days === 1 ? '' : 's'}. Plan renewal before the deadline.`;
    }
    if (due) {
      return `${est ? 'Estimated ' : ''}Due ${String(due).slice(0, 10)}. Renew before it expires.`;
    }
    return 'This obligation is due soon. Plan renewal before the deadline.';
  }
  if (['COMPLIANT', 'VALID'].includes(s) && hasDoc) {
    return 'Evidence is on file and this obligation is currently in a valid state.';
  }
  if (['NOT_APPLICABLE', 'NOT_REQUIRED', 'WAIVED'].includes(s)) {
    return 'This obligation is marked as not applicable or waived for this property.';
  }
  return 'Review the current status and due date in the table above.';
}

/** Standardised status nouns for the obligations matrix. */
export function complianceObligationStatusLabel(r) {
  const s = String(r?.status || '').toUpperCase();
  if (['NOT_APPLICABLE', 'NOT_REQUIRED', 'WAIVED'].includes(s)) return 'Not applicable';
  if (['OVERDUE', 'EXPIRED'].includes(s)) return 'Overdue';
  if (s === 'EXPIRING_SOON') return 'Expiring';
  if (isRequirementMissingDocument(r)) return 'Missing evidence';
  return 'Valid';
}

/** Standardised primary action: Upload | Renew | Review (+ requirement-specific upload label). */
export function complianceObligationPrimaryAction(r) {
  const s = String(r?.status || '').toUpperCase();
  const code = r?.requirement_code || r?.requirement_type;
  if (isRequirementMissingDocument(r)) {
    return { verb: 'upload', label: requirementDocumentUploadLabel(code) };
  }
  if ((s === 'PENDING' && r?.evidence_doc_id) || s === 'PENDING_VERIFICATION') {
    return { verb: 'review', label: 'Review' };
  }
  if (['OVERDUE', 'EXPIRED', 'EXPIRING_SOON'].includes(s) && r?.evidence_doc_id) {
    return { verb: 'renew', label: 'Renew' };
  }
  if (['OVERDUE', 'EXPIRED', 'EXPIRING_SOON'].includes(s) && !r?.evidence_doc_id) {
    return { verb: 'upload', label: requirementDocumentUploadLabel(code) };
  }
  if (r?.evidence_doc_id) {
    return { verb: 'review', label: 'Review' };
  }
  return { verb: 'upload', label: requirementDocumentUploadLabel(code) };
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
    const title = rowTitle(first) || 'this obligation';
    if (act.verb === 'upload') return `Next: ${act.label} for ${title}.`;
    if (act.verb === 'renew') return `Next: Renew evidence for ${title}.`;
    return `Next: Review ${title} on the Documents tab.`;
  }
  const { missing, expiring, overdue } = summarizeRequirementCounts(requirements);
  if (missing > 0) {
    return `Next: Upload evidence for ${missing} obligation${missing === 1 ? '' : 's'} with missing documents.`;
  }
  if (overdue > 0) {
    return `Next: Address ${overdue} overdue obligation${overdue === 1 ? '' : 's'}.`;
  }
  if (expiring > 0) {
    return `Next: Plan renewal for ${expiring} obligation${expiring === 1 ? '' : 's'} due soon.`;
  }
  if (requirements.length > 0) {
    return 'Next: Periodically review obligations and keep evidence up to date on the Documents tab.';
  }
  return 'Next: Complete property setup so applicable obligations appear here.';
}
