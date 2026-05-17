import React, { forwardRef, useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { clientAPI } from '../../api/client';
import {
  buildComplianceEvidenceRecordDisplay,
  pickLatestComplianceEvidenceRecord,
} from '../../utils/complianceEvidenceSubmissionView';

/**
 * Read-only inspector for the latest non-archived compliance evidence record (TRUST-01).
 */
const RequirementSubmissionInspectPanel = forwardRef(function RequirementSubmissionInspectPanel(
  { propertyId, requirementId, className = '' },
  ref,
) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [latestRecord, setLatestRecord] = useState(null);
  const [linkedDocs, setLinkedDocs] = useState([]);

  useEffect(() => {
    if (!propertyId || !requirementId) {
      setLatestRecord(null);
      setLinkedDocs([]);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError('');
    clientAPI
      .listComplianceEvidence(propertyId, requirementId)
      .then((res) => {
        if (cancelled) return;
        const records = res?.data?.evidence_records;
        const latest = pickLatestComplianceEvidenceRecord(records);
        setLatestRecord(latest);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || err?.message || 'Could not load your submission');
          setLatestRecord(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [propertyId, requirementId]);

  const linkedIds = useMemo(() => {
    const ids = latestRecord?.linked_document_ids;
    if (!Array.isArray(ids)) return [];
    return ids.map((x) => String(x)).filter(Boolean);
  }, [latestRecord]);

  useEffect(() => {
    if (!propertyId || linkedIds.length === 0) {
      setLinkedDocs([]);
      return undefined;
    }
    let cancelled = false;
    clientAPI
      .getDocuments({ property_id: propertyId, requirement_id: requirementId })
      .then((res) => {
        if (cancelled) return;
        const all = Array.isArray(res?.data?.documents) ? res.data.documents : Array.isArray(res?.data) ? res.data : [];
        const idSet = new Set(linkedIds);
        setLinkedDocs(all.filter((d) => idSet.has(String(d.document_id || d.id || ''))));
      })
      .catch(() => {
        if (!cancelled) setLinkedDocs([]);
      });
    return () => {
      cancelled = true;
    };
  }, [propertyId, requirementId, linkedIds]);

  const display = useMemo(() => buildComplianceEvidenceRecordDisplay(latestRecord), [latestRecord]);

  if (!propertyId || !requirementId) return null;

  return (
    <section
      ref={ref}
      className={`rounded-lg border border-gray-200 bg-gray-50/60 p-4 ${className}`.trim()}
      data-testid="requirement-submission-inspect-panel"
      aria-label="Your submission"
    >
      <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-2">Your submission</h3>
      {loading ? (
        <div className="flex items-center gap-2 text-gray-500 text-sm py-2" data-testid="submission-inspect-loading">
          <Loader2 className="w-4 h-4 animate-spin shrink-0" aria-hidden />
          Loading submission…
        </div>
      ) : null}
      {error ? (
        <p className="text-sm text-red-700" data-testid="submission-inspect-error">
          {typeof error === 'string' ? error : 'Could not load your submission'}
        </p>
      ) : null}
      {!loading && !error && !latestRecord ? (
        <p className="text-sm text-gray-600" data-testid="submission-inspect-empty">
          No guided submission on file yet.
        </p>
      ) : null}
      {!loading && !error && latestRecord ? (
        <div className="space-y-3 text-sm" data-testid="submission-inspect-content">
          {display.meta.length > 0 ? (
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-2">
              {display.meta.map((row) => (
                <div key={row.label}>
                  <dt className="text-xs text-gray-500">{row.label}</dt>
                  <dd className="font-medium text-gray-900 break-words">{row.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {display.sections.map((sec) => (
            <div key={sec.title}>
              <p className="text-xs font-medium text-gray-700 mb-1">{sec.title}</p>
              <dl className="space-y-1.5">
                {sec.rows.map((row) => (
                  <div key={`${sec.title}-${row.label}`}>
                    <dt className="text-xs text-gray-500">{row.label}</dt>
                    <dd className="text-gray-900 whitespace-pre-wrap break-words">{row.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
          {linkedIds.length > 0 ? (
            <div data-testid="submission-inspect-documents">
              <p className="text-xs font-medium text-gray-700 mb-1">Supporting documents</p>
              <ul className="list-disc list-inside text-gray-800 space-y-0.5">
                {linkedDocs.length > 0
                  ? linkedDocs.map((d) => (
                      <li key={String(d.document_id || d.id)}>
                        {d.filename || d.original_filename || d.title || String(d.document_id || d.id)}
                      </li>
                    ))
                  : linkedIds.map((id) => <li key={id}>{id}</li>)}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
});

export default RequirementSubmissionInspectPanel;
