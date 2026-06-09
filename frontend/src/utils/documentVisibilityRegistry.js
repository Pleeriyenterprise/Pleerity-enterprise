/**
 * Operational document visibility — queue vs property evidence registry grouping.
 * Consumes canonical backend projections when present; falls back to client derivation.
 */
import { linkageReconciliationRequired } from './documentClientPresentation';

/** @typedef {'attention' | 'all' | 'active_evidence' | 'operational_attachments' | 'historical'} DocumentsQueueView */

export const DOCUMENT_VISIBILITY_STATES = {
  ATTENTION_REQUIRED: 'ATTENTION_REQUIRED',
  ACTIVE_EVIDENCE: 'ACTIVE_EVIDENCE',
  HISTORICAL_OR_SUPERSEDED: 'HISTORICAL_OR_SUPERSEDED',
  OPERATIONAL_ATTACHMENT: 'OPERATIONAL_ATTACHMENT',
};

export const REGISTRY_SECTION_ORDER = [
  { key: 'reconciliation_required', label: 'Reconciliation required', attention: true },
  { key: 'pending_review', label: 'Pending review', attention: true },
  { key: 'expiring_soon', label: 'Expiring soon', attention: true },
  { key: 'active_evidence', label: 'Active evidence', attention: false },
  { key: 'historical_superseded', label: 'Historical / superseded', attention: false },
  { key: 'operational_attachments', label: 'Operational attachments', attention: false },
];

/**
 * @param {Record<string, unknown>} doc
 */
export function documentAttentionRequired(doc = {}) {
  if (doc.document_attention_required === true) return true;
  const vis = String(doc.document_client_visibility_state || '').toUpperCase();
  if (vis === DOCUMENT_VISIBILITY_STATES.ATTENTION_REQUIRED) return true;
  if (linkageReconciliationRequired(doc)) return true;
  return false;
}

/**
 * @param {Record<string, unknown>} doc
 */
export function getClientDocumentVisibilityBadge(doc = {}) {
  const vis = String(doc.document_client_visibility_state || '').toUpperCase();
  if (vis === DOCUMENT_VISIBILITY_STATES.ATTENTION_REQUIRED) {
    return { key: vis, label: String(doc.document_client_visibility_label || 'Attention required'), color: 'bg-amber-100 text-amber-900' };
  }
  if (vis === DOCUMENT_VISIBILITY_STATES.ACTIVE_EVIDENCE) {
    return { key: vis, label: String(doc.document_client_visibility_label || 'Active evidence'), color: 'bg-teal-50 text-teal-900' };
  }
  if (vis === DOCUMENT_VISIBILITY_STATES.HISTORICAL_OR_SUPERSEDED) {
    return { key: vis, label: String(doc.document_client_visibility_label || 'Historical'), color: 'bg-gray-100 text-gray-600' };
  }
  if (vis === DOCUMENT_VISIBILITY_STATES.OPERATIONAL_ATTACHMENT) {
    return { key: vis, label: String(doc.document_client_visibility_label || 'Operational attachment'), color: 'bg-slate-100 text-slate-700' };
  }
  return null;
}

/**
 * @param {Record<string, unknown>[]} documents
 * @param {DocumentsQueueView} view
 */
export function filterDocumentsForQueueView(documents, view = 'attention') {
  const list = Array.isArray(documents) ? documents : [];
  if (view === 'all') return list;
  if (view === 'active_evidence') {
    return list.filter((d) => String(d.document_client_visibility_state || '').toUpperCase() === DOCUMENT_VISIBILITY_STATES.ACTIVE_EVIDENCE);
  }
  if (view === 'operational_attachments') {
    return list.filter((d) => String(d.document_client_visibility_state || '').toUpperCase() === DOCUMENT_VISIBILITY_STATES.OPERATIONAL_ATTACHMENT);
  }
  if (view === 'historical') {
    return list.filter((d) => String(d.document_client_visibility_state || '').toUpperCase() === DOCUMENT_VISIBILITY_STATES.HISTORICAL_OR_SUPERSEDED);
  }
  return list.filter((d) => documentAttentionRequired(d));
}

/**
 * @param {Record<string, unknown>[]} documents
 * @param {Record<string, unknown[]> | null | undefined} registryFromApi
 */
export function groupDocumentsForPropertyRegistry(documents, registryFromApi) {
  if (registryFromApi && typeof registryFromApi === 'object') {
    return REGISTRY_SECTION_ORDER.map(({ key, label, attention }) => ({
      key,
      label,
      attention,
      documents: Array.isArray(registryFromApi[key]) ? registryFromApi[key] : [],
    }));
  }
  const buckets = Object.fromEntries(REGISTRY_SECTION_ORDER.map(({ key }) => [key, []]));
  for (const doc of documents || []) {
    const section = String(doc.document_registry_section || 'pending_review');
    if (buckets[section]) buckets[section].push(doc);
    else buckets.pending_review.push(doc);
  }
  return REGISTRY_SECTION_ORDER.map(({ key, label, attention }) => ({
    key,
    label,
    attention,
    documents: buckets[key] || [],
  }));
}

/**
 * @param {Record<string, unknown>[]} documents
 */
export function countAttentionRequiredDocuments(documents) {
  return (documents || []).filter((d) => documentAttentionRequired(d)).length;
}
