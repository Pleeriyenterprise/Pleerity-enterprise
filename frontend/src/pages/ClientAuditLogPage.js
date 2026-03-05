import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { History, FileText, Mail, Shield, Activity, Download, ChevronDown, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';

const TAB_SCORE_HISTORY = 'score-history';
const TAB_ACTIVITY_LOG = 'activity-log';

export default function ClientAuditLogPage() {
  const [searchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const [activeTab, setActiveTab] = useState(() =>
    tabParam === 'score-history' ? TAB_SCORE_HISTORY : TAB_ACTIVITY_LOG
  );
  const [timeline, setTimeline] = useState([]);
  const [timelineLoading, setTimelineLoading] = useState(true);
  const [timelineError, setTimelineError] = useState(null);

  const [ledger, setLedger] = useState({ items: [], next_cursor: null, has_more: false, total: 0 });
  const [ledgerLoading, setLedgerLoading] = useState(false);
  const [ledgerError, setLedgerError] = useState(null);
  const [ledgerFilters, setLedgerFilters] = useState({ property_id: '', trigger_type: '', from_date: '', to_date: '' });
  const [expandedRow, setExpandedRow] = useState(null);
  const [exportingCsv, setExportingCsv] = useState(false);

  useEffect(() => {
    let cancelled = false;
    clientAPI
      .getAuditTimeline(80)
      .then((res) => {
        if (!cancelled && res?.data?.timeline) setTimeline(res.data.timeline);
      })
      .catch((err) => {
        if (!cancelled) {
          setTimelineError(err?.response?.data?.detail || 'Failed to load audit log');
        }
      })
      .finally(() => {
        if (!cancelled) setTimelineLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const loadLedger = useCallback((cursor = null) => {
    setLedgerLoading(true);
    setLedgerError(null);
    const params = {
      limit: 50,
      ...(ledgerFilters.property_id && { property_id: ledgerFilters.property_id }),
      ...(ledgerFilters.trigger_type && { trigger_type: ledgerFilters.trigger_type }),
      ...(ledgerFilters.from_date && { from_date: ledgerFilters.from_date }),
      ...(ledgerFilters.to_date && { to_date: ledgerFilters.to_date }),
      ...(cursor && { cursor }),
    };
    clientAPI
      .getLedger(params)
      .then((res) => {
        if (cursor) {
          setLedger((prev) => ({
            ...res.data,
            items: [...prev.items, ...(res.data.items || [])],
          }));
        } else {
          setLedger(res.data || { items: [], next_cursor: null, has_more: false, total: 0 });
        }
      })
      .catch((err) => {
        setLedgerError(err?.response?.data?.detail || 'Failed to load score history');
      })
      .finally(() => setLedgerLoading(false));
  }, [ledgerFilters]);

  useEffect(() => {
    if (activeTab === TAB_SCORE_HISTORY) loadLedger();
  }, [activeTab, loadLedger]);

  const handleExportCsv = () => {
    setExportingCsv(true);
    const params = {};
    if (ledgerFilters.property_id) params.property_id = ledgerFilters.property_id;
    if (ledgerFilters.trigger_type) params.trigger_type = ledgerFilters.trigger_type;
    if (ledgerFilters.from_date) params.from_date = ledgerFilters.from_date;
    if (ledgerFilters.to_date) params.to_date = ledgerFilters.to_date;
    clientAPI
      .exportLedgerCsv(params)
      .then((res) => {
        const blob = res.data;
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `score_ledger_export_${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success('CSV downloaded');
      })
      .catch((err) => {
        toast.error(err?.response?.data?.detail || 'Export failed');
      })
      .finally(() => setExportingCsv(false));
  };

  const iconForAction = (action) => {
    if (action?.includes('DOCUMENT')) return <FileText className="w-5 h-5" />;
    if (action?.includes('EMAIL') || action?.includes('MESSAGE') || action?.includes('REMINDER') || action?.includes('DIGEST')) return <Mail className="w-5 h-5" />;
    if (action?.includes('LOGIN') || action?.includes('PASSWORD') || action?.includes('PORTAL_INVITE')) return <Shield className="w-5 h-5" />;
    return <Activity className="w-5 h-5" />;
  };

  const badgeClass = (action) => {
    if (action?.includes('SUCCESS') || action?.includes('COMPLETE')) return 'bg-green-100 text-green-600';
    if (action?.includes('FAILED')) return 'bg-red-100 text-red-600';
    return 'bg-electric-teal/10 text-electric-teal';
  };

  const formatDate = (iso) => (iso ? new Date(iso).toLocaleString() : '—');
  const deltaStr = (delta) => {
    if (delta == null) return '—';
    const d = Number(delta);
    if (d > 0) return `+${d}`;
    return String(d);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-midnight-blue flex items-center gap-2">
          <History className="w-7 h-7" />
          Audit & Change History
        </h2>
        <p className="text-gray-600 mt-1">Score change history and activity log for your account.</p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4">
          <button
            type="button"
            onClick={() => setActiveTab(TAB_SCORE_HISTORY)}
            className={`py-3 px-1 border-b-2 font-medium text-sm ${
              activeTab === TAB_SCORE_HISTORY
                ? 'border-electric-teal text-electric-teal'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Score History
          </button>
          <button
            type="button"
            onClick={() => setActiveTab(TAB_ACTIVITY_LOG)}
            className={`py-3 px-1 border-b-2 font-medium text-sm ${
              activeTab === TAB_ACTIVITY_LOG
                ? 'border-electric-teal text-electric-teal'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Activity Log
          </button>
        </nav>
      </div>

      {activeTab === TAB_SCORE_HISTORY && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3 items-end">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Property ID</label>
              <input
                type="text"
                placeholder="Filter by property"
                value={ledgerFilters.property_id}
                onChange={(e) => setLedgerFilters((f) => ({ ...f, property_id: e.target.value }))}
                className="border border-gray-300 rounded px-2 py-1.5 text-sm w-40"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Trigger type</label>
              <input
                type="text"
                placeholder="e.g. DOCUMENT_UPLOADED"
                value={ledgerFilters.trigger_type}
                onChange={(e) => setLedgerFilters((f) => ({ ...f, trigger_type: e.target.value }))}
                className="border border-gray-300 rounded px-2 py-1.5 text-sm w-44"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">From date</label>
              <input
                type="date"
                value={ledgerFilters.from_date}
                onChange={(e) => setLedgerFilters((f) => ({ ...f, from_date: e.target.value }))}
                className="border border-gray-300 rounded px-2 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">To date</label>
              <input
                type="date"
                value={ledgerFilters.to_date}
                onChange={(e) => setLedgerFilters((f) => ({ ...f, to_date: e.target.value }))}
                className="border border-gray-300 rounded px-2 py-1.5 text-sm"
              />
            </div>
            <button
              type="button"
              onClick={() => loadLedger()}
              disabled={ledgerLoading}
              className="px-3 py-1.5 bg-midnight-blue text-white rounded text-sm hover:bg-midnight-blue/90 disabled:opacity-50"
            >
              {ledgerLoading ? 'Loading…' : 'Apply'}
            </button>
            <button
              type="button"
              onClick={handleExportCsv}
              disabled={exportingCsv}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              {exportingCsv ? 'Exporting…' : 'Export CSV'}
            </button>
          </div>
          {ledgerError && (
            <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3">{ledgerError}</div>
          )}
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            {ledgerLoading && ledger.items.length === 0 ? (
              <div className="flex justify-center py-12">
                <div className="animate-spin rounded-full h-10 w-10 border-2 border-electric-teal border-t-transparent" />
              </div>
            ) : ledger.items.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <p className="text-gray-600 font-medium">No score history entries found</p>
                <p className="text-gray-500 text-sm mt-2 max-w-md mx-auto">
                  Entries appear when your compliance score is recalculated—for example after uploading documents,
                  confirming certificate details, updating requirements, or when the system runs a scheduled refresh.
                  Try clearing the filters above or check back after making changes to your portfolio.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="w-8" />
                      <th className="px-3 py-2 text-left font-medium text-gray-700">Timestamp</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-700">Change</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-700">Property</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-700">Before → After</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-700">Δ</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-700">Trigger</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-700">Actor</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 bg-white">
                    {ledger.items.map((row, idx) => {
                      const isExpanded = expandedRow === idx;
                      return (
                        <React.Fragment key={idx}>
                          <tr
                            className="hover:bg-gray-50 cursor-pointer"
                            onClick={() => setExpandedRow(isExpanded ? null : idx)}
                          >
                            <td className="px-2 py-2">
                              {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                            </td>
                            <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{formatDate(row.created_at)}</td>
                            <td className="px-3 py-2">
                              <span className="text-midnight-blue font-medium">
                                {row.trigger_label || row.trigger_type || '—'}
                              </span>
                            </td>
                            <td className="px-3 py-2 font-mono text-xs">{row.property_id || '—'}</td>
                            <td className="px-3 py-2">
                              {row.before_score != null ? row.before_score : '—'} → {row.after_score ?? '—'}
                              {row.before_grade != null || row.after_grade != null ? (
                                <span className="text-gray-500 ml-1">
                                  ({row.before_grade ?? '—'} → {row.after_grade ?? '—'})
                                </span>
                              ) : null}
                            </td>
                            <td className="px-3 py-2">
                              <span className={row.delta != null && row.delta < 0 ? 'text-red-600' : row.delta > 0 ? 'text-green-600' : ''}>
                                {deltaStr(row.delta)}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-gray-600">{row.trigger_type || '—'}</td>
                            <td className="px-3 py-2 text-gray-600">{row.actor_type || '—'}</td>
                          </tr>
                          {isExpanded && (
                            <tr className="bg-gray-50">
                              <td colSpan={8} className="px-4 py-3 text-xs text-gray-600">
                                <div className="grid grid-cols-2 gap-x-6 gap-y-2 max-w-2xl">
                                  <div><strong>Rule version:</strong> {row.rule_version ?? '—'}</div>
                                  {row.requirement_id && <div><strong>Requirement ID:</strong> {row.requirement_id}</div>}
                                  {row.document_id && <div><strong>Document ID:</strong> {row.document_id}</div>}
                                  {row.drivers_before && (
                                    <div>
                                      <strong>Drivers before:</strong>{' '}
                                      status={row.drivers_before.status ?? '—'}, timeline={row.drivers_before.timeline ?? '—'}, documents={row.drivers_before.documents ?? '—'}, overdue_penalty={row.drivers_before.overdue_penalty ?? '—'}
                                    </div>
                                  )}
                                  {row.drivers_after && (
                                    <div>
                                      <strong>Drivers after:</strong>{' '}
                                      status={row.drivers_after.status ?? '—'}, timeline={row.drivers_after.timeline ?? '—'}, documents={row.drivers_after.documents ?? '—'}, overdue_penalty={row.drivers_after.overdue_penalty ?? '—'}
                                    </div>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          {ledger.has_more && (
            <div className="flex justify-center">
              <button
                type="button"
                onClick={() => loadLedger(ledger.next_cursor)}
                disabled={ledgerLoading}
                className="px-4 py-2 border border-gray-300 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                {ledgerLoading ? 'Loading…' : 'Load more'}
              </button>
            </div>
          )}
        </div>
      )}

      {activeTab === TAB_ACTIVITY_LOG && (
        <>
          {timelineLoading && (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-10 w-10 border-2 border-electric-teal border-t-transparent" />
            </div>
          )}
          {timelineError && (
            <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3">{timelineError}</div>
          )}
          {!timelineLoading && !timelineError && (
            <div className="space-y-3">
              {timeline.length === 0 ? (
                <p className="text-gray-500 text-center py-8">No audit events found</p>
              ) : (
                timeline.map((event, idx) => (
                  <div key={idx} className="flex gap-4 p-4 bg-gray-50 rounded-lg">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${badgeClass(event.action)}`}
                    >
                      {iconForAction(event.action)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-midnight-blue">{event.action?.replace(/_/g, ' ')}</p>
                      <p className="text-sm text-gray-500">{formatDate(event.timestamp)}</p>
                      {event.metadata && Object.keys(event.metadata).length > 0 && (
                        <div className="mt-2 text-xs text-gray-400 bg-white p-2 rounded max-h-24 overflow-auto">
                          {JSON.stringify(event.metadata)}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
