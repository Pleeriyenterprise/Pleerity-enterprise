/**
 * Compliance requirement status chips for UI (documents vs requirements).
 * Backend statuses: COMPLIANT, VALID, EXPIRING_SOON, OVERDUE, PENDING, MISSING, FAILED, etc.
 * PENDING is split by whether a document is already linked: no file vs awaiting verification.
 */
import { CheckCircle, Clock, AlertTriangle, XCircle, FileText, HelpCircle } from 'lucide-react';
import { documentVerificationAwaitingSubline } from '../domain/presentDomain';

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
const VERIFY_CHIP = { icon: Clock, text: 'Awaiting verification', className: 'bg-amber-100 text-amber-800 border-amber-200' };

/**
 * @param {string} status
 * @param {object} [row] requirement row with optional evidence_doc_id
 */
export function getEvidenceStatus(status, row) {
  const key = (status || '').toUpperCase().trim();
  const linked = !!(row && row.evidence_doc_id);
  if (key === 'PENDING' && linked) return { ...VERIFY_CHIP, subline: awaitingVerificationSubline() };
  if (key === 'MISSING' || key === 'MISSING_EVIDENCE' || (key === 'PENDING' && !linked)) return NO_DOC_CHIP;
  if (key === 'PENDING_VERIFICATION') {
    const cfg = EVIDENCE_STATUS_CONFIG.PENDING_VERIFICATION;
    return { ...cfg, subline: awaitingVerificationSubline() };
  }
  return EVIDENCE_STATUS_CONFIG[key] || EVIDENCE_STATUS_CONFIG.PENDING;
}
