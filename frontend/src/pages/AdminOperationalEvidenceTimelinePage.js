import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { adminAPI } from '../api/client';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import OperationalEvidenceAnnotations from '../components/admin/OperationalEvidenceAnnotations';
import { GitBranch, RefreshCw, ChevronDown, ChevronRight, Copy, ExternalLink } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';

const SEVERITY_CLASS = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  error: 'bg-orange-100 text-orange-800 border-orange-200',
  warning: 'bg-amber-100 text-amber-800 border-amber-200',
  info: 'bg-blue-50 text-blue-800 border-blue-200',
};

const STATUS_CLASS = {
  success: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  degraded: 'bg-amber-100 text-amber-900',
  started: 'bg-gray-100 text-gray-700',
  open: 'bg-red-50 text-red-700',
  resolved: 'bg-green-50 text-green-700',
};

function copyText(text) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => toast.success('Copied')).catch(() => toast.error('Copy failed'));
}

export default function AdminOperationalEvidenceTimelinePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [viewMode, setViewMode] = useState(searchParams.get('view') || 'story');
  const [loading, setLoading] = useState(true);
  const [events, setEvents] = useState({ items: [], total: 0, next_cursor: null });
  const [story, setStory] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [expandedChain, setExpandedChain] = useState(true);
  const [includeArchived, setIncludeArchived] = useState(searchParams.get('include_archived') === '1');
  const [portfolio, setPortfolio] = useState(null);
  const [intelligence, setIntelligence] = useState(null);
  const [retentionStats, setRetentionStats] = useState(null);
  const [maintenanceBusy, setMaintenanceBusy] = useState(false);
  const [filters, setFilters] = useState({
    search: searchParams.get('search') || '',
    correlation_id: searchParams.get('correlation_id') || '',
    root_execution_id: searchParams.get('root_execution_id') || '',
    incident_id: searchParams.get('incident_id') || '',
    job_run_id: searchParams.get('job_run_id') || '',
    property_id: searchParams.get('property_id') || '',
    client_id: searchParams.get('client_id') || '',
    category: searchParams.get('category') || '',
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 50, include_archived: includeArchived };
      Object.entries(filters).forEach(([k, v]) => {
        if (v) params[k] = v;
      });
      if (filters.root_execution_id || filters.correlation_id) {
        const storyRes = await adminAPI.getOperationalEvidenceStory({
          root_execution_id: filters.root_execution_id || undefined,
          correlation_id: filters.correlation_id || undefined,
        });
        setPortfolio(null);
        setStory(storyRes.data);
        setEvents({ items: storyRes.data.items || [], total: storyRes.data.event_count || 0 });
      } else if (filters.incident_id) {
        const res = await adminAPI.getOperationalEvidenceIncidentView(filters.incident_id);
        setPortfolio(null);
        setStory(res.data.story);
        setEvents(res.data.timeline || { items: [] });
      } else if (filters.job_run_id) {
        const res = await adminAPI.getOperationalEvidenceJobRunView(filters.job_run_id);
        setPortfolio(null);
        setStory(res.data.story);
        setEvents(res.data.timeline || { items: [] });
      } else if (
        filters.client_id
        && !filters.incident_id
        && !filters.job_run_id
        && !filters.correlation_id
        && !filters.root_execution_id
      ) {
        const res = await adminAPI.getOperationalEvidencePortfolioView(filters.client_id, {
          include_archived: includeArchived,
        });
        setPortfolio(res.data);
        setStory(res.data.story);
        setEvents(res.data.timeline || { items: [], total: 0 });
      } else {
        const res = await adminAPI.getOperationalEvidenceEvents(params);
        setPortfolio(null);
        setEvents(res.data);
        setStory(null);
      }
    } catch {
      toast.error('Failed to load operational evidence');
    } finally {
      setLoading(false);
    }
  }, [filters, includeArchived]);

  const loadSidebarMeta = useCallback(async () => {
    try {
      const [intelRes, retentionRes] = await Promise.all([
        adminAPI.getOperationalEvidenceIntelligence({ hours: 24 }),
        adminAPI.getOperationalEvidenceRetentionStats(),
      ]);
      setIntelligence(intelRes.data);
      setRetentionStats(retentionRes.data);
    } catch {
      setIntelligence(null);
      setRetentionStats(null);
    }
  }, []);

  useEffect(() => {
    loadSidebarMeta();
  }, [loadSidebarMeta]);

  useEffect(() => {
    load();
  }, [load]);

  const applyFilters = (e) => {
    e.preventDefault();
    const next = {};
    Object.entries(filters).forEach(([k, v]) => {
      if (v) next[k] = v;
    });
    if (viewMode !== 'story') next.view = viewMode;
    if (includeArchived) next.include_archived = '1';
    setSearchParams(next, { replace: true });
    load();
  };

  const runBackfill = async () => {
    setMaintenanceBusy(true);
    try {
      const res = await adminAPI.runOperationalEvidenceBackfill({ days: 7, limit_per_source: 200 });
      toast.success(`Backfill complete: ${res.data?.totals?.emitted ?? 0} emitted`);
      load();
      loadSidebarMeta();
    } catch {
      toast.error('Backfill failed');
    } finally {
      setMaintenanceBusy(false);
    }
  };

  const formatTime = (iso) => (iso ? new Date(iso).toLocaleString() : '—');

  const renderStory = () => {
    if (!story || !story.steps?.length) {
      return (
        <p className="text-sm text-gray-500 py-8 text-center">
          No operational story for current filters. Adjust filters or wait for instrumented events.
        </p>
      );
    }
    return (
      <div className="space-y-1">
        <div className="mb-4 p-4 rounded-lg border bg-white">
          <h2 className="text-lg font-semibold text-gray-900">{story.title}</h2>
          <p className="text-sm text-gray-600 mt-1">
            Status: <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_CLASS[story.status] || 'bg-gray-100'}`}>{story.status}</span>
            {' · '}
            {story.customer_impact?.summary || 'No customer impact'}
          </p>
          {story.correlation_id && (
            <button type="button" onClick={() => copyText(story.correlation_id)} className="text-xs text-teal-700 mt-2 flex items-center gap-1">
              <Copy className="w-3 h-3" /> {story.correlation_id}
            </button>
          )}
        </div>
        {story.steps.map((step, idx) => (
          <div key={step.event_id || idx} className="flex gap-3">
            <div className="flex flex-col items-center w-6">
              <div className="w-2 h-2 rounded-full bg-teal-600 mt-2" />
              {idx < story.steps.length - 1 && <div className="w-px flex-1 bg-teal-200 min-h-[24px]" />}
            </div>
            <div className="flex-1 pb-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-gray-900">{step.label}</p>
                  <p className="text-sm text-gray-600">{step.summary}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{formatTime(step.occurred_at)}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {step.status && (
                    <span className={`text-xs px-2 py-0.5 rounded ${STATUS_CLASS[step.status] || 'bg-gray-100'}`}>{step.status}</span>
                  )}
                  {step.deep_link && (
                    <Link to={step.deep_link} className="text-teal-600 hover:text-teal-800">
                      <ExternalLink className="w-4 h-4" />
                    </Link>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderTimeline = () => (
    <ul className="divide-y divide-gray-100 border rounded-lg bg-white">
      {(events.items || []).map((ev) => (
        <li key={ev.event_id} className="p-4 hover:bg-gray-50 cursor-pointer" onClick={() => setSelectedEvent(ev)}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-xs px-2 py-0.5 rounded border ${SEVERITY_CLASS[ev.severity] || SEVERITY_CLASS.info}`}>{ev.severity}</span>
                <span className="text-xs font-mono text-gray-500">{ev.event_type}</span>
                {ev.confidence?.score != null && (
                  <span className="text-xs text-gray-400">{ev.confidence.score}% confidence</span>
                )}
              </div>
              <p className="text-sm font-medium text-gray-900 mt-1 truncate">{(ev.evidence || {}).summary || ev.event_type}</p>
              <p className="text-xs text-gray-500 mt-0.5">{formatTime(ev.occurred_at)} · {ev.category}</p>
            </div>
            {(ev.evidence || {}).deep_link && (
              <Link to={(ev.evidence || {}).deep_link} className="text-teal-600 shrink-0" onClick={(e) => e.stopPropagation()}>
                <ExternalLink className="w-4 h-4" />
              </Link>
            )}
          </div>
        </li>
      ))}
      {!events.items?.length && !loading && (
        <li className="p-8 text-center text-sm text-gray-500">No evidence events yet.</li>
      )}
    </ul>
  );

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <GitBranch className="w-7 h-7 text-teal-700" />
            Operational Evidence Timeline
          </h1>
          <div className="flex items-center gap-2">
            <select
              value={viewMode}
              onChange={(e) => setViewMode(e.target.value)}
              className="border border-gray-300 rounded px-2 py-1.5 text-sm"
            >
              <option value="story">Operational Story</option>
              <option value="timeline">Raw Timeline</option>
              <option value="tree">Execution Tree</option>
            </select>
            <button type="button" onClick={load} className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border rounded hover:bg-gray-50">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </button>
          </div>
        </div>

        <form onSubmit={applyFilters} className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-3 mb-6 p-4 bg-gray-50 rounded-lg border">
          <input
            placeholder="Search summary / correlation"
            value={filters.search}
            onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
            className="border rounded px-2 py-1.5 text-sm"
          />
          <input
            placeholder="Correlation ID"
            value={filters.correlation_id}
            onChange={(e) => setFilters((f) => ({ ...f, correlation_id: e.target.value }))}
            className="border rounded px-2 py-1.5 text-sm font-mono"
          />
          <input
            placeholder="Root execution ID"
            value={filters.root_execution_id}
            onChange={(e) => setFilters((f) => ({ ...f, root_execution_id: e.target.value }))}
            className="border rounded px-2 py-1.5 text-sm font-mono"
          />
          <input
            placeholder="Incident ID"
            value={filters.incident_id}
            onChange={(e) => setFilters((f) => ({ ...f, incident_id: e.target.value }))}
            className="border rounded px-2 py-1.5 text-sm"
          />
          <input
            placeholder="Job run ID"
            value={filters.job_run_id}
            onChange={(e) => setFilters((f) => ({ ...f, job_run_id: e.target.value }))}
            className="border rounded px-2 py-1.5 text-sm font-mono"
          />
          <input
            placeholder="Property ID"
            value={filters.property_id}
            onChange={(e) => setFilters((f) => ({ ...f, property_id: e.target.value }))}
            className="border rounded px-2 py-1.5 text-sm"
          />
          <input
            placeholder="Client ID (portfolio view)"
            value={filters.client_id}
            onChange={(e) => setFilters((f) => ({ ...f, client_id: e.target.value }))}
            className="border rounded px-2 py-1.5 text-sm font-mono"
          />
          <select
            value={filters.category}
            onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}
            className="border rounded px-2 py-1.5 text-sm"
          >
            <option value="">All categories</option>
            <option value="scheduler">Scheduler</option>
            <option value="queue">Queue</option>
            <option value="incident">Incident</option>
            <option value="compliance">Compliance</option>
            <option value="risk">Risk</option>
          </select>
          <label className="flex items-center gap-2 text-sm text-gray-700 px-1">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(e) => setIncludeArchived(e.target.checked)}
            />
            Include archived (warm tier)
          </label>
          <button type="submit" className="bg-teal-700 text-white rounded px-4 py-1.5 text-sm hover:bg-teal-800">
            Apply filters
          </button>
        </form>

        {portfolio && (
          <div className="mb-6 p-4 rounded-lg border border-indigo-200 bg-indigo-50/50">
            <h2 className="text-sm font-semibold text-indigo-900">Portfolio evidence — {portfolio.client_id}</h2>
            <p className="text-sm text-indigo-800 mt-1">
              {portfolio.summary?.event_count ?? 0} events · {portfolio.summary?.properties_with_evidence ?? 0} properties ·{' '}
              {portfolio.summary?.high_impact_count ?? 0} high-impact
            </p>
            {portfolio.by_category?.length > 0 && (
              <p className="text-xs text-indigo-700 mt-2">
                Top categories:{' '}
                {portfolio.by_category.slice(0, 5).map((c) => `${c.category} (${c.count})`).join(', ')}
              </p>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            {loading ? (
              <p className="text-sm text-gray-500 py-12 text-center">Loading evidence…</p>
            ) : viewMode === 'story' ? (
              renderStory()
            ) : viewMode === 'tree' && story?.tree ? (
              <div className="border rounded-lg bg-white p-4">
                <button type="button" className="flex items-center gap-1 text-sm font-medium mb-3" onClick={() => setExpandedChain(!expandedChain)}>
                  {expandedChain ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  Execution tree ({story.tree.nodes?.length || 0} nodes)
                </button>
                {expandedChain && (
                  <ul className="space-y-2 text-sm">
                    {(story.tree.nodes || []).map((n) => (
                      <li key={n.event_id} className="pl-4 border-l-2 border-teal-200" style={{ marginLeft: (n.execution_depth || 0) * 12 }}>
                        <span className="font-medium">{n.event_type}</span>
                        <span className="text-gray-500 ml-2">{n.summary}</span>
                        {n.child_count > 0 && <span className="text-xs text-gray-400 ml-2">({n.child_count} children)</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              renderTimeline()
            )}
          </div>

          <div className="space-y-4">
            <div className="border rounded-lg bg-white p-4 h-fit">
              <h3 className="font-semibold text-gray-900 mb-3">Intelligence (24h)</h3>
              {!intelligence ? (
                <p className="text-sm text-gray-500">No intelligence data.</p>
              ) : (
                <div className="text-sm space-y-3">
                  {intelligence.top_failure_event_types?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase">Top failures</p>
                      <ul className="mt-1 space-y-0.5">
                        {intelligence.top_failure_event_types.slice(0, 5).map((r) => (
                          <li key={r.event_type} className="text-gray-700">
                            {r.event_type} <span className="text-gray-400">({r.count})</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {intelligence.retry_loop_correlations?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase">Retry loops</p>
                      <ul className="mt-1 space-y-0.5">
                        {intelligence.retry_loop_correlations.slice(0, 3).map((r) => (
                          <li key={r.correlation_id} className="text-xs font-mono text-gray-600 truncate">
                            {r.correlation_id} ({r.count})
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="border rounded-lg bg-white p-4 h-fit">
              <h3 className="font-semibold text-gray-900 mb-3">Retention & maintenance</h3>
              {retentionStats && (
                <p className="text-sm text-gray-600 mb-2">
                  {retentionStats.total_events} total · {retentionStats.warm_count} warm · hot default window{' '}
                  {retentionStats.warm_after_days}d
                </p>
              )}
              <button
                type="button"
                disabled={maintenanceBusy}
                onClick={runBackfill}
                className="text-sm px-3 py-1.5 border border-teal-300 rounded text-teal-800 hover:bg-teal-50 disabled:opacity-50"
              >
                Run 7-day backfill
              </button>
            </div>

            <div className="border rounded-lg bg-white p-4 h-fit">
              <h3 className="font-semibold text-gray-900 mb-3">Event detail</h3>
              {selectedEvent ? (
                <div className="text-sm space-y-2">
                  <p><strong>Type:</strong> {selectedEvent.event_type}</p>
                  <p><strong>When:</strong> {formatTime(selectedEvent.occurred_at)}</p>
                  <p><strong>Summary:</strong> {(selectedEvent.evidence || {}).summary}</p>
                  <p><strong>Impact:</strong> {(selectedEvent.customer_impact || {}).summary}</p>
                  <p><strong>Confidence:</strong> {(selectedEvent.confidence || {}).score}% — {(selectedEvent.confidence || {}).reason}</p>
                  {selectedEvent.retention?.tier && (
                    <p><strong>Retention:</strong> {selectedEvent.retention.tier}</p>
                  )}
                  {selectedEvent.correlation_id && (
                    <button type="button" onClick={() => copyText(selectedEvent.correlation_id)} className="text-teal-700 flex items-center gap-1">
                      <Copy className="w-3 h-3" /> Correlation ID
                    </button>
                  )}
                  {(selectedEvent.evidence || {}).deep_link && (
                    <Link to={(selectedEvent.evidence || {}).deep_link} className="text-teal-700 flex items-center gap-1">
                      <ExternalLink className="w-3 h-3" /> Source record
                    </Link>
                  )}
                  <OperationalEvidenceAnnotations
                    eventId={selectedEvent.event_id}
                    rootExecutionId={selectedEvent.root_execution_id}
                    correlationId={selectedEvent.correlation_id}
                    compact
                  />
                </div>
              ) : (
                <p className="text-sm text-gray-500">Select an event to inspect evidence and correlation.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </UnifiedAdminLayout>
  );
}
