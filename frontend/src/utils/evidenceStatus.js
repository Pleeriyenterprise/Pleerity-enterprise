/**
 * Evidence status chip config (no legal verdict language).
 * Backend statuses: COMPLIANT, VALID, EXPIRING_SOON, OVERDUE, PENDING, MISSING, FAILED, etc.
 */
import { CheckCircle, Clock, AlertTriangle, XCircle, FileText, HelpCircle } from 'lucide-react';

export const EVIDENCE_STATUS_CONFIG = {
  VALID: { icon: CheckCircle, text: 'Valid', className: 'bg-green-100 text-green-700 border-green-200' },
  COMPLIANT: { icon: CheckCircle, text: 'Valid', className: 'bg-green-100 text-green-700 border-green-200' },
  EXPIRING_SOON: { icon: Clock, text: 'Expiring soon', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  OVERDUE: { icon: AlertTriangle, text: 'Overdue', className: 'bg-red-100 text-red-700 border-red-200' },
  EXPIRED: { icon: XCircle, text: 'Overdue', className: 'bg-red-100 text-red-700 border-red-200' },
  MISSING: { icon: FileText, text: 'Missing evidence', className: 'bg-gray-100 text-gray-700 border-gray-200' },
  PENDING: { icon: FileText, text: 'Missing evidence', className: 'bg-gray-100 text-gray-700 border-gray-200' },
  FAILED: { icon: XCircle, text: 'Overdue', className: 'bg-red-100 text-red-700 border-red-200' },
  PENDING_VERIFICATION: { icon: HelpCircle, text: 'Needs review', className: 'bg-blue-100 text-blue-700 border-blue-200' },
};

export function getEvidenceStatus(status) {
  const key = (status || '').toUpperCase().trim();
  return EVIDENCE_STATUS_CONFIG[key] || EVIDENCE_STATUS_CONFIG.PENDING;
}
