import React from 'react';
import { Link } from 'react-router-dom';
import { Eye, Download } from 'lucide-react';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { documentTypeLabel } from '../../domain/presentDomain';
import {
  getClientDocumentLinkageBadge,
  linkageReconciliationRequired,
} from '../../utils/documentClientPresentation';
import { groupDocumentsForPropertyRegistry } from '../../utils/documentVisibilityRegistry';

/**
 * Property Evidence Registry — operational sections (not filesystem folders).
 */
export function PropertyEvidenceRegistrySections({
  evidenceData,
  requirements,
  propertyId,
  evidenceDocStatusLabel,
  linkedRequirementLabelForDocument,
  rowTitle,
  clientVerificationLabelRedundantWithPrimary,
  clientFacingVerificationLabel,
  isPendingConfirmation,
  resolveDocumentsPath,
  navigate,
  onPreview,
  onDownload,
  formatDate,
  canViewEvidence = true,
  canDownloadEvidence = true,
  canUploadDocuments = true,
}) {
  if (!canViewEvidence) return null;

  const sections = groupDocumentsForPropertyRegistry(
    evidenceData?.documents || [],
    evidenceData?.registry,
  ).filter((s) => s.documents.length > 0);

  if (sections.length === 0) return null;

  return (
    <div className="space-y-6" data-testid="property-evidence-registry">
      {sections.map((section) => (
        <div key={section.key} data-testid={`evidence-registry-section-${section.key}`}>
          <div className="flex items-center gap-2 mb-2">
            <h4 className={`text-sm font-semibold ${section.attention ? 'text-amber-900' : 'text-gray-800'}`}>
              {section.label}
            </h4>
            <span className="text-xs text-gray-500">({section.documents.length})</span>
            {section.key === 'expiring_soon' ? (
              <span className="text-xs text-amber-700">Resurfaced for expiry action</span>
            ) : null}
          </div>
          <div className="hidden md:block rounded-xl border border-gray-200 bg-white overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-600 bg-gray-50">
                    <th className="p-3">Document</th>
                    <th className="p-3">Document type</th>
                    <th className="p-3">Linked requirement</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Uploaded at</th>
                    <th className="p-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {section.documents.map((doc) => {
                    const evidencePrimary = evidenceDocStatusLabel(doc);
                    const showVerificationSubline = !clientVerificationLabelRedundantWithPrimary(doc, evidencePrimary);
                    const reqLabel = linkedRequirementLabelForDocument(doc, requirements, rowTitle);
                    const workspaceHref = resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id });
                    const linkageBadge = getClientDocumentLinkageBadge(doc);
                    return (
                      <tr key={doc.document_id} className="border-b border-gray-100 hover:bg-gray-50" data-evidence-req-focus={doc.requirement_id || undefined}>
                        <td className="p-3 font-medium text-midnight-blue">{doc.file_name || doc.original_filename || doc.document_id}</td>
                        <td className="p-3 text-gray-600">{doc.document_type ? documentTypeLabel(doc.document_type) : '—'}</td>
                        <td className="p-3 text-gray-600">{reqLabel}</td>
                        <td className="p-3">
                          <div className="flex flex-col gap-1">
                            <span className="inline-flex px-2 py-1 rounded border text-xs bg-gray-100 text-gray-700 border-gray-200 w-fit">{evidencePrimary}</span>
                            {linkageBadge ? (
                              <span className={`inline-flex px-2 py-0.5 rounded text-[11px] w-fit ${linkageBadge.color}`}>{linkageBadge.label}</span>
                            ) : null}
                            {doc.document_expiry_resurface && doc.document_days_to_expiry != null ? (
                              <span className="text-[11px] text-amber-700">Expires in {doc.document_days_to_expiry} days</span>
                            ) : null}
                            {showVerificationSubline ? (
                              <span className="text-[11px] text-gray-500">{clientFacingVerificationLabel(doc)}</span>
                            ) : null}
                          </div>
                        </td>
                        <td className="p-3 text-gray-600">{doc.uploaded_at ? formatDate(doc.uploaded_at) : '—'}</td>
                        <td className="p-3">
                          <div className="flex flex-wrap gap-1">
                            <Button variant="outline" size="sm" className="text-electric-teal border-electric-teal" onClick={() => onPreview(doc)} data-testid={`property-doc-preview-open-${doc.document_id}`}>
                              <Eye className="w-3 h-3 mr-1" /> View
                            </Button>
                            {canDownloadEvidence ? (
                            <Button variant="outline" size="sm" onClick={() => onDownload(doc)}><Download className="w-3 h-3 mr-1" /> Download</Button>
                            ) : null}
                            {canUploadDocuments && isPendingConfirmation(doc) ? (
                              <Button variant="outline" size="sm" className="border-amber-300 text-amber-700" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id }))}>Confirm details</Button>
                            ) : null}
                            {canUploadDocuments && linkageReconciliationRequired(doc) ? (
                              <Button variant="outline" size="sm" className="border-orange-300 text-orange-800" onClick={() => navigate(resolveDocumentsPath(propertyId))}>Resolve linkage</Button>
                            ) : null}
                          </div>
                          <button type="button" className="mt-1.5 block text-left text-xs text-gray-600 hover:text-midnight-blue underline-offset-2 hover:underline" onClick={() => navigate(workspaceHref)}>
                            Open in Document operations
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          <div className="md:hidden space-y-2">
            {section.documents.map((doc) => {
              const evidencePrimary = evidenceDocStatusLabel(doc);
              const reqLabel = linkedRequirementLabelForDocument(doc, requirements, rowTitle);
              const workspaceHref = resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id });
              return (
                <Card key={doc.document_id} className="border border-gray-200 p-3">
                  <div className="font-medium text-midnight-blue">{doc.file_name || doc.original_filename || doc.document_id}</div>
                  <div className="text-xs text-gray-600 mt-1">{[doc.document_type ? documentTypeLabel(doc.document_type) : null, evidencePrimary, reqLabel !== '—' ? reqLabel : null].filter(Boolean).join(' · ')}</div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    <Button variant="outline" size="sm" onClick={() => onPreview(doc)}>View</Button>
                    {canDownloadEvidence ? (
                    <Button variant="outline" size="sm" onClick={() => onDownload(doc)}>Download</Button>
                    ) : null}
                    {canUploadDocuments && linkageReconciliationRequired(doc) ? (
                      <Button variant="outline" size="sm" onClick={() => navigate(resolveDocumentsPath(propertyId))}>Resolve linkage</Button>
                    ) : null}
                  </div>
                  <button type="button" className="mt-2 text-left text-xs text-gray-600 hover:text-midnight-blue underline-offset-2 hover:underline w-full" onClick={() => navigate(workspaceHref)}>
                    Open in Document operations
                  </button>
                </Card>
              );
            })}
          </div>
        </div>
      ))}
      <p className="text-xs text-gray-500">
        Portfolio-wide attention queue:{' '}
        <Link to="/documents" className="text-electric-teal hover:underline">Document operations</Link>
      </p>
    </div>
  );
}

export default PropertyEvidenceRegistrySections;
