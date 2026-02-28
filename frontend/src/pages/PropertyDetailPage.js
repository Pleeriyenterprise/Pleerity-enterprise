import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { Button } from '../components/ui/button';
import ErrorBanner from '../components/ErrorBanner';
import {
  ArrowLeft,
  Building2,
  FileText,
  Upload,
  RefreshCw,
  Mail,
  TrendingUp,
  TrendingDown,
  History,
  X,
  MinusCircle,
} from 'lucide-react';
import { SUPPORT_EMAIL } from '../config';
import { getEvidenceStatus } from '../utils/evidenceStatus';
import { formatRiskLabel } from '../utils/riskLabel';
import { toast } from 'sonner';

const NOT_REQUIRED_REASONS = [
  { value: 'no_gas_supply', label: 'No gas supply' },
  { value: 'exempt', label: 'Exempt' },
  { value: 'not_applicable', label: 'Not applicable' },
  { value: 'other', label: 'Other' },
];

export default function PropertyDetailPage() {
  const { propertyId } = useParams();
  const navigate = useNavigate();
  const [property, setProperty] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [complianceDetail, setComplianceDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [scoreHistoryModal, setScoreHistoryModal] = useState(false);
  const [scoreHistoryEntries, setScoreHistoryEntries] = useState([]);
  const [scoreHistoryLoading, setScoreHistoryLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [notApplicableModal, setNotApplicableModal] = useState(null);
  const [notApplicableReason, setNotApplicableReason] = useState('');
  const [notApplicableSubmitting, setNotApplicableSubmitting] = useState(false);

  useEffect(() => {
    const hash = window.location.hash;
    const match = hash && hash.startsWith('#req=') && decodeURIComponent(hash.slice(5)).trim();
    if (match && requirements.length > 0) {
      const el = document.querySelector(`[data-req-code="${match}"]`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [requirements]);

  const fetchData = React.useCallback(async () => {
    try {
      setError(null);
      const propsRes = await clientAPI.getProperties();
      const prop = (propsRes.data.properties || []).find((p) => p.property_id === propertyId);
      setProperty(prop || null);
      try {
        const detailRes = await clientAPI.getComplianceDetail(propertyId);
        if (detailRes?.data) {
          setComplianceDetail(detailRes.data);
          setRequirements(detailRes.data.matrix || []);
          return;
        }
      } catch (_) {
        /* fallback to requirements list */
      }
      const reqsRes = await clientAPI.getPropertyRequirements(propertyId);
      setRequirements(reqsRes.data?.requirements || []);
      setComplianceDetail(null);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load property');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [propertyId]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchData().finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [fetchData]);

  const getStatus = (r) => getEvidenceStatus(r.status);
  const formatDate = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—');
  const daysLeft = (d) => {
    if (!d) return null;
    const diff = Math.ceil((new Date(d) - new Date()) / (1000 * 60 * 60 * 24));
    return diff;
  };
  const isMatrixRow = (r) => r.title != null || r.requirement_code != null;
  const rowTitle = (r) => r.title || r.requirement_type || r.description || r.name || '—';
  const rowExpiry = (r) => r.expiry_date || r.due_date;
  const rowDays = (r) => (r.days_to_expiry != null ? r.days_to_expiry : daysLeft(rowExpiry(r)));
  const rowReqId = (r) => r.requirement_id || r.id;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  if (error && !property) {
    return (
      <div>
        <ErrorBanner
          message={error}
          onRetry={() => navigate('/properties')}
          retryLabel="Back to properties"
        />
      </div>
    );
  }

  const address = property
    ? [property.address_line_1, property.address_line_2, property.postcode].filter(Boolean).join(', ') || 'Unnamed property'
    : 'Property';

  return (
    <div>
      <div className="flex items-center justify-between gap-4 mb-4">
        <Button variant="ghost" size="sm" className="-ml-2" onClick={() => navigate('/properties')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to properties
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
          className="border-gray-200"
          data-testid="property-detail-refresh"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>

      {/* Property header card */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 mb-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-midnight-blue">{address}</h1>
            <div className="flex flex-wrap gap-2 mt-2 text-sm text-gray-600">
              {property?.property_type && <span>{property.property_type}</span>}
              {property?.is_hmo && <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded">HMO</span>}
              {property?.has_gas !== undefined && <span>{property.has_gas ? 'Gas' : 'No gas'}</span>}
            </div>
          </div>
        </div>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        This is an evidence-based status summary. It is not legal advice.
      </p>

      {complianceDetail && (
        <>
          <div className="mb-4 flex flex-wrap gap-4 p-4 rounded-xl border border-gray-200 bg-gray-50">
            <span className="font-medium text-midnight-blue">Evidence readiness score: {(complianceDetail.score != null ? complianceDetail.score : complianceDetail.property_score) ?? '—'}/100</span>
            <span className="font-medium text-midnight-blue">Risk level: {formatRiskLabel(complianceDetail.risk_level)}</span>
            {complianceDetail.risk_index != null && complianceDetail.risk_index > 0 && (
              <span className="text-gray-600">Risk index: {complianceDetail.risk_index}</span>
            )}
            {complianceDetail.last_updated_at && (
              <span className="text-sm text-gray-500">Last updated: {new Date(complianceDetail.last_updated_at).toLocaleString()}</span>
            )}
          </div>
          {(complianceDetail.score_delta != null || complianceDetail.score_change_summary) && (
            <div className="mb-4 flex flex-wrap items-center gap-3 p-3 rounded-lg border border-gray-200 bg-white">
              {complianceDetail.score_delta != null && complianceDetail.score_delta !== 0 && (
                <span className={`inline-flex items-center gap-1 font-medium ${complianceDetail.score_delta > 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {complianceDetail.score_delta > 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                  {complianceDetail.score_delta > 0 ? '+' : ''}{complianceDetail.score_delta} pts
                </span>
              )}
              {complianceDetail.score_change_summary && (
                <span className="text-sm text-gray-600">{complianceDetail.score_change_summary}</span>
              )}
              <Button
                variant="outline"
                size="sm"
                className="text-electric-teal border-electric-teal"
                onClick={async () => {
                  setScoreHistoryModal(true);
                  setScoreHistoryLoading(true);
                  try {
                    const res = await clientAPI.getScoreHistory(propertyId);
                    setScoreHistoryEntries(res.data?.entries ?? []);
                  } catch (_) {
                    setScoreHistoryEntries([]);
                  } finally {
                    setScoreHistoryLoading(false);
                  }
                }}
              >
                <History className="w-3.5 h-3.5 mr-1" />
                View change history
              </Button>
            </div>
          )}
          {scoreHistoryModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setScoreHistoryModal(false)}>
              <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden m-4" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between p-4 border-b">
                  <h3 className="font-semibold text-midnight-blue">Score change history</h3>
                  <button type="button" onClick={() => setScoreHistoryModal(false)} className="p-1 rounded hover:bg-gray-100"><X className="w-5 h-5" /></button>
                </div>
                <div className="p-4 overflow-auto max-h-[60vh]">
                  {scoreHistoryLoading ? (
                    <p className="text-gray-500">Loading…</p>
                  ) : scoreHistoryEntries.length === 0 ? (
                    <p className="text-gray-500">No score change history yet.</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-gray-600">
                          <th className="p-2">Date</th>
                          <th className="p-2">Previous</th>
                          <th className="p-2">New</th>
                          <th className="p-2">Delta</th>
                          <th className="p-2">Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {scoreHistoryEntries.map((e, i) => (
                          <tr key={i} className="border-b border-gray-100">
                            <td className="p-2">{e.created_at ? new Date(e.created_at).toLocaleString() : '—'}</td>
                            <td className="p-2">{e.previous_score ?? '—'}</td>
                            <td className="p-2">{e.new_score ?? '—'}</td>
                            <td className={`p-2 font-medium ${e.delta > 0 ? 'text-green-600' : e.delta < 0 ? 'text-red-600' : ''}`}>{e.delta != null ? (e.delta > 0 ? '+' : '') + e.delta : '—'}</td>
                            <td className="p-2 text-gray-600">{e.reason ?? '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Requirements matrix (from compliance-detail API when available, else requirements list) */}
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 font-medium text-midnight-blue">
          Requirements
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-600">
                <th className="p-3">Requirement</th>
                <th className="p-3">Evidence status</th>
                <th className="p-3">Expiry date</th>
                <th className="p-3">Days left</th>
                <th className="p-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {requirements.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-6 text-center text-gray-500">
                    No requirements returned for this property.
                  </td>
                </tr>
              )}
              {requirements.map((r, idx) => {
                const status = getStatus(r);
                const Icon = status.icon;
                const days = rowDays(r);
                return (
                  <tr key={rowReqId(r) || r.requirement_code || idx} className="border-b border-gray-100 hover:bg-gray-50" data-req-code={r.requirement_code || r.requirement_type || ''}>
                    <td className="p-3 font-medium text-midnight-blue">{rowTitle(r)}</td>
                    <td className="p-3">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded border text-xs ${status.className}`}>
                        <Icon className="w-3.5 h-3.5" />
                        {status.text}
                      </span>
                    </td>
                    <td className="p-3 text-gray-600">{formatDate(rowExpiry(r))}</td>
                    <td className="p-3">{days != null ? (days < 0 ? `${Math.abs(days)} days overdue` : `${days} days`) : '—'}</td>
                    <td className="p-3">
                      <div className="flex flex-wrap gap-2 items-center">
                        {(r.evidence_doc_id && status.text !== 'Missing evidence') ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-electric-teal border-electric-teal"
                            onClick={() => navigate(`/documents?property_id=${propertyId}&requirement_id=${rowReqId(r)}`)}
                          >
                            <FileText className="w-3.5 h-3.5 mr-1" />
                            View document
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-electric-teal border-electric-teal"
                            onClick={() => navigate(`/documents?property_id=${propertyId}&requirement_id=${rowReqId(r)}`)}
                          >
                            <Upload className="w-3.5 h-3.5 mr-1" />
                            Upload
                          </Button>
                        )}
                        {status.text === 'Missing evidence' && (r.requirement_code || r.requirement_type) && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-gray-600 hover:text-gray-800"
                            onClick={() => {
                              setNotApplicableModal({ requirement_code: r.requirement_code || r.requirement_type, title: rowTitle(r) });
                              setNotApplicableReason('not_applicable');
                            }}
                            data-testid="mark-not-applicable"
                          >
                            <MinusCircle className="w-3.5 h-3.5 mr-1" />
                            Mark as not applicable
                          </Button>
                        )}
                        <a
                          href={`mailto:${SUPPORT_EMAIL}?subject=Support request: ${address}`}
                          className="text-sm text-gray-500 hover:text-electric-teal"
                        >
                          Request help
                        </a>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {notApplicableModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => !notApplicableSubmitting && setNotApplicableModal(null)}>
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full m-4 p-4" onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold text-midnight-blue mb-2">Mark as not applicable</h3>
            <p className="text-sm text-gray-600 mb-3">
              &ldquo;{notApplicableModal.title}&rdquo; will be excluded from this property&apos;s score and requirements list. You can change this later from the Requirements tab.
            </p>
            <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
            <select
              value={notApplicableReason}
              onChange={(e) => setNotApplicableReason(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 mb-4"
              data-testid="not-applicable-reason"
            >
              {NOT_REQUIRED_REASONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setNotApplicableModal(null)} disabled={notApplicableSubmitting}>Cancel</Button>
              <Button
                onClick={async () => {
                  setNotApplicableSubmitting(true);
                  try {
                    await clientAPI.markRequirementNotApplicable(propertyId, {
                      requirement_code: notApplicableModal.requirement_code,
                      not_required_reason: notApplicableReason,
                    });
                    toast.success('Requirement marked as not applicable. List will update.');
                    setNotApplicableModal(null);
                    fetchData();
                  } catch (err) {
                    toast.error(err.response?.data?.detail || 'Failed to update');
                  } finally {
                    setNotApplicableSubmitting(false);
                  }
                }}
                disabled={notApplicableSubmitting}
                data-testid="not-applicable-confirm"
              >
                {notApplicableSubmitting ? 'Saving…' : 'Confirm'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
