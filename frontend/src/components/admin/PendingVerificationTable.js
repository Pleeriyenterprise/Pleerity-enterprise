import React from 'react';
import { CheckCircle, Download, Eye, RefreshCw, XCircle } from 'lucide-react';
import { getPendingDocumentOperationalPresentation } from '../../utils/adminOperationalPresentation';
import OperationalTechnicalDetailsPanel from './OperationalTechnicalDetailsPanel';

/**
 * Operational admin pending-verification queue (human labels; raw values in technical drawer).
 */
export default function PendingVerificationTable({
  documents = [],
  total = 0,
  returned = 0,
  hasMore = false,
  loading = false,
  expandedTechnicalDocId,
  onToggleTechnicalDetails,
  onSelectClient,
  evidenceReviewV2Enabled = false,
  onViewDocument,
  onDownloadDocument,
  onOpenAiReview,
  onVerifyDocument,
  onResolveMatch,
  onRejectDocument,
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <RefreshCw className="w-6 h-6 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm" data-testid="pending-verification-table">
        <thead>
          <tr className="border-b border-gray-200 text-left text-gray-600">
            <th className="py-3 pr-4 font-medium">Document</th>
            <th className="py-3 pr-4 font-medium">Requirement</th>
            <th className="py-3 pr-4 font-medium">Suggested match</th>
            <th className="py-3 pr-4 font-medium">Review status</th>
            <th className="py-3 pr-4 font-medium">Uploaded</th>
            <th className="py-3 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {documents.length === 0 ? (
            <tr>
              <td colSpan={6} className="py-4 text-gray-500 text-center">
                No documents matching filters.
              </td>
            </tr>
          ) : (
            documents.filter(Boolean).map((doc, idx) => {
              const op = getPendingDocumentOperationalPresentation(doc);
              const docId = doc?.document_id ?? `row-${idx}`;
              const technicalExpanded = expandedTechnicalDocId === docId;
              return (
                <tr
                  key={docId}
                  className="border-b border-gray-100 hover:bg-gray-50 align-top"
                  data-testid={`pending-verification-row-${doc?.document_id}`}
                >
                  <td className="py-3 pr-4 max-w-xs">
                    <div className="font-medium text-midnight-blue">{op.documentTitle}</div>
                    <button
                      type="button"
                      className="mt-0.5 block text-left text-sm text-gray-700 hover:text-electric-teal"
                      onClick={() => doc?.client_id && onSelectClient?.(doc.client_id)}
                    >
                      {op.clientName}
                      {op.crn && op.crn !== '—' ? (
                        <span className="text-gray-500"> · {op.crn}</span>
                      ) : null}
                    </button>
                    {op.assurance.label !== 'User uploaded' && (
                      <div className="mt-1">
                        <span className={op.assurance.badgeClass} title={op.assurance.helperText}>
                          {op.assurance.label}
                        </span>
                      </div>
                    )}
                    <OperationalTechnicalDetailsPanel
                      doc={doc}
                      expanded={technicalExpanded}
                      onToggle={() => onToggleTechnicalDetails(technicalExpanded ? null : docId)}
                      testId={`technical-details-${doc?.document_id}`}
                    />
                  </td>
                  <td className="py-3 pr-4 max-w-[200px]">
                    <span className={op.requirement.badgeClass} title={op.requirement.helperText}>
                      {op.requirement.label}
                    </span>
                  </td>
                  <td className="py-3 pr-4 max-w-[260px]">
                    <span className={op.suggestedMatch.badgeClass} title={op.suggestedMatch.helperText}>
                      {op.suggestedMatch.label}
                    </span>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span className={op.confidence.badgeClass} title={op.confidence.helperText}>
                        {op.confidence.label}
                      </span>
                      {op.confidence.tierLabel ? (
                        <span className="text-xs text-gray-500">{op.confidence.tierLabel}</span>
                      ) : null}
                    </div>
                    {op.mismatch.label !== '—' && op.mismatch.canonicalValue !== 'NONE' && (
                      <p className="mt-1 text-xs text-gray-600 line-clamp-2" title={op.mismatch.helperText}>
                        {op.mismatch.label}
                      </p>
                    )}
                  </td>
                  <td className="py-3 pr-4">
                    <span className={op.reviewStatus.badgeClass} title={op.reviewStatus.helperText}>
                      {op.reviewStatus.label}
                    </span>
                    {op.validation.label !== 'No validation run yet' && op.validation.label !== '—' && (
                      <p className="mt-1 text-xs text-gray-600" title={op.validation.helperText}>
                        {op.validation.label}
                      </p>
                    )}
                    {op.aiWarnings.label !== '—' && (
                      <p className="mt-0.5 text-xs text-amber-800" title={op.aiWarnings.helperText}>
                        {op.aiWarnings.label}
                      </p>
                    )}
                    {op.anomaly.label !== '—' && (
                      <p className="mt-0.5 text-xs" title={op.anomaly.helperText}>
                        <span className={op.anomaly.badgeClass}>{op.anomaly.label}</span>
                      </p>
                    )}
                  </td>
                  <td className="py-3 pr-4 text-gray-600 whitespace-nowrap">
                    {doc?.uploaded_at ? new Date(doc.uploaded_at).toLocaleString() : '—'}
                  </td>
                  <td className="py-3 text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center justify-end gap-2 flex-wrap">
                      <button
                        type="button"
                        onClick={() => onViewDocument(doc)}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded"
                        title="View document"
                        data-testid={`view-doc-${doc?.document_id}`}
                      >
                        <Eye className="w-3.5 h-3.5" />
                        View
                      </button>
                      <button
                        type="button"
                        onClick={() => onDownloadDocument(doc)}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded"
                        title="Download document"
                        data-testid={`download-doc-${doc?.document_id}`}
                      >
                        <Download className="w-3.5 h-3.5" />
                        Download
                      </button>
                      {evidenceReviewV2Enabled && (
                        <button
                          type="button"
                          onClick={() => onOpenAiReview(doc)}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-indigo-700 bg-indigo-100 hover:bg-indigo-200 rounded"
                          data-testid={`ai-review-doc-${doc?.document_id}`}
                        >
                          AI review
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => onVerifyDocument(doc)}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-green-700 bg-green-100 hover:bg-green-200 rounded"
                        data-testid={`verify-doc-${doc?.document_id}`}
                      >
                        <CheckCircle className="w-3.5 h-3.5" />
                        Verify
                      </button>
                      <button
                        type="button"
                        onClick={() => onResolveMatch(doc)}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-teal-900 bg-teal-100 hover:bg-teal-200 rounded"
                        data-testid={`resolve-match-${doc?.document_id}`}
                      >
                        Resolve match
                      </button>
                      <button
                        type="button"
                        onClick={() => onRejectDocument(doc)}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-red-700 bg-red-100 hover:bg-red-200 rounded"
                        data-testid={`reject-doc-${doc?.document_id}`}
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Reject
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
      {total > 0 && (
        <p className="text-xs text-gray-500 mt-2">
          Showing {returned} of {total}
          {hasMore ? ' (more available)' : ''}.
        </p>
      )}
    </div>
  );
}
