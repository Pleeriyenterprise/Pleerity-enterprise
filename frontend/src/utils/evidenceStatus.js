/**
 * Compliance requirement status chips for UI (documents vs requirements).
 * Backend statuses: COMPLIANT, VALID, EXPIRING_SOON, OVERDUE, PENDING, MISSING, FAILED, etc.
 * PENDING is split by whether a document is already linked: no file vs awaiting verification.
 *
 * Prefer `workflow_class` from API enrichment when present — aligns with backend resolver semantics.
 */
import { CheckCircle, Clock, AlertTriangle, XCircle, FileText, HelpCircle } from 'lucide-react';
import { documentVerificationAwaitingSubline } from '../domain/presentDomain';
import { isConditionStandardWorkflowHint, isMultiEvidenceStyleWorkflow } from './workflowSemantics';

function awaitingVerificationSubline() {
  const s = documentVerificationAwaitingSubline();
  return s || 'Portfolio user confirms on the Documents tab; automation may still be processing.';
}

export const EVIDENCE_STATUS_CONFIG = {
  VALID: { icon: CheckCircle, text: 'Valid', className: 'bg-green-100 text-green-700 border-green-200' },
  COMPLIANT: { icon: CheckCircle, text: 'Valid', className: 'bg-green-100 text-green-700 border-green-200' },
  EXPIRING_SOON: { icon: Clock, text: 'Expiring soon', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  OVERDUE: { icon: AlertTriangle, text: 'Overdue', className: 'bg-red-100 text-red-700 border-red-200' },
  EXPIRED: { icon: XCircle, text: 'Overdue', className: 'bg-red-100 text-red-700 border-red-200' },
  MISSING: { icon: FileText, text: 'No document uploaded', className: 'bg-gray-100 text-gray-700 border-gray-200' },
  PENDING: { icon: FileText, text: 'No document uploaded', className: 'bg-gray-100 text-gray-700 border-gray-200' },
  FAILED: { icon: XCircle, text: 'Overdue', className: 'bg-red-100 text-red-700 border-red-200' },
  PENDING_VERIFICATION: { icon: HelpCircle, text: 'Awaiting verification', className: 'bg-amber-100 text-amber-800 border-amber-200' },
  NOT_REQUIRED: { icon: HelpCircle, text: 'Not applicable', className: 'bg-gray-100 text-gray-600 border-gray-200' },
};

const NO_DOC_CHIP = { icon: FileText, text: 'No document uploaded', className: 'bg-gray-100 text-gray-700 border-gray-200' };
/** Certificate-style DOCUMENT_UPLOAD workflows — avoid implying operational remediation closure. */
const CERTIFICATE_GAP_CHIP = {
  icon: FileText,
  text: 'Certificate evidence missing',
  className: 'bg-gray-100 text-gray-700 border-gray-200',
};
const MULTI_COMPONENT_CHIP = {
  icon: FileText,
  text: 'Evidence incomplete',
  className: 'bg-gray-100 text-gray-700 border-gray-200',
};
const ASSESSMENT_GAP_CHIP = {
  icon: FileText,
  text: 'Assessment incomplete',
  className: 'bg-gray-100 text-gray-700 border-gray-200',
};
const VERIFY_CHIP = { icon: Clock, text: 'Awaiting verification', className: 'bg-amber-100 text-amber-800 border-amber-200' };

function _workflowClass(row) {
  return String(row?.workflow_class || '').trim().toUpperCase();
}

function _requirementCode(row) {
  return String(row?.canonical_requirement_code || row?.canonical_code || row?.requirement_code || row?.requirement_type || '')
    .trim()
    .toLowerCase();
}

function _isActiveStandardRow(row) {
  return isConditionStandardWorkflowHint(row?.workflow_class, row);
}

function _tenancyAgreementStatusText(row) {
  const code = _requirementCode(row);
  if (code !== 'tenancy_agreement') return '';
  return String(row?.tenancy_agreement_status_text || '').trim();
}

export function workflowAwareMissingEvidenceLabel(row) {
  const wf = _workflowClass(row);
  const tenancyStatus = _tenancyAgreementStatusText(row);
  if (tenancyStatus) return tenancyStatus;
  if (_isActiveStandardRow(row)) return 'Condition status needs review';
  if (wf === 'DOCUMENT_UPLOAD' || wf === 'LEGACY_DOCUMENT_UPLOAD') {
    return 'Certificate or evidence document missing — action required';
  }
  if (wf === 'GUIDANCE_ONLY') return 'Guidance item — review recommended';
  if (wf === 'GUIDED_DECLARATION') return 'Declaration not recorded — action required';
  if (wf === 'TENANT_DELIVERY') return 'Delivery record missing — action required';
  if (wf === 'REGISTRATION_TRACKING') return 'Registration details not recorded — action required';
  if (wf === 'EXTERNAL_ASSESSMENT_EVIDENCE') return 'Assessment not recorded — action required';
  if (isMultiEvidenceStyleWorkflow(wf)) return 'Required evidence incomplete';
  return 'Evidence missing — action required';
}

/**
 * @param {string} status
 * @param {object} [row] requirement row with optional evidence_doc_id
 */
export function getEvidenceStatus(status, row) {
  const key = (status || '').toUpperCase().trim();
  const linked = !!(row && row.evidence_doc_id);
  const tenancyStatus = _tenancyAgreementStatusText(row);
  if (key === 'PENDING' && linked) return { ...VERIFY_CHIP, subline: awaitingVerificationSubline() };
  if (key === 'MISSING' || key === 'MISSING_EVIDENCE' || (key === 'PENDING' && !linked)) {
    const wf = _workflowClass(row);
    let chip = NO_DOC_CHIP;
    if (isMultiEvidenceStyleWorkflow(wf)) chip = MULTI_COMPONENT_CHIP;
    else if (wf === 'EXTERNAL_ASSESSMENT_EVIDENCE') chip = ASSESSMENT_GAP_CHIP;
    else if (wf === 'DOCUMENT_UPLOAD' || wf === 'LEGACY_DOCUMENT_UPLOAD') chip = CERTIFICATE_GAP_CHIP;
    return { ...chip, subline: workflowAwareMissingEvidenceLabel(row) };
  }
  if (key === 'PENDING_VERIFICATION') {
    const cfg = EVIDENCE_STATUS_CONFIG.PENDING_VERIFICATION;
    return { ...cfg, subline: awaitingVerificationSubline() };
  }
  if (key === 'OVERDUE' || key === 'EXPIRED' || key === 'FAILED') {
    const cfg = EVIDENCE_STATUS_CONFIG[key] || EVIDENCE_STATUS_CONFIG.OVERDUE;
    return { ...cfg, subline: 'Overdue — affecting compliance.' };
  }
  const base = EVIDENCE_STATUS_CONFIG[key] || EVIDENCE_STATUS_CONFIG.PENDING;
  if (tenancyStatus && (key === 'VALID' || key === 'COMPLIANT')) return { ...base, subline: tenancyStatus };
  return base;
}
