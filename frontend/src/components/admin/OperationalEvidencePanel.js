import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../api/client';
import OperationalEvidenceAnnotations from './OperationalEvidenceAnnotations';
import { ChevronDown, ChevronRight, ExternalLink, RefreshCw } from 'lucide-react';

const STATUS_CLASS = {
  success: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  degraded: 'bg-amber-100 text-amber-900',
  started: 'bg-gray-100 text-gray-700',
  open: 'bg-red-50 text-red-700',
  resolved: 'bg-green-50 text-green-700',
};

function formatTime(iso) {
  return iso ? new Date(iso).toLocaleString() : '—';
}

/**
 * Compact embedded operational evidence story for Incidents and Automation pages.
 */
export default function OperationalEvidencePanel({
  incidentId,
  jobRunId,
  defaultExpanded = false,
  className = '',
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [loading, setLoading] = useState(false);
  const [story, setStory] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!incidentId && !jobRunId) return;
    setLoading(true);
    setError(null);
    try {
      const res = incidentId
        ? await adminAPI.getOperationalEvidenceIncidentView(incidentId)
        : await adminAPI.getOperationalEvidenceJobRunView(jobRunId);
      setStory(res.data?.story || null);
      setEvents(res.data?.timeline?.items || []);
    } catch {
      setError('Could not load operational evidence');
      setStory(null);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [incidentId, jobRunId]);

  useEffect(() => {
    if (expanded) load();
  }, [expanded, load]);

  const fullTimelineHref = incidentId
    ? `/admin/ops/evidence-timeline?incident_id=${encodeURIComponent(incidentId)}`
    : `/admin/ops/evidence-timeline?job_run_id=${encodeURIComponent(jobRunId)}`;

  return (
    <div className={`border border-teal-200 rounded-lg bg-teal-50/40 ${className}`}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-sm font-medium text-teal-900 hover:bg-teal-50 rounded-lg"
      >
        <span className="flex items-center gap-1.5">
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          Operational evidence
        </span>
        <Link
          to={fullTimelineHref}
          onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1 text-xs text-teal-700 hover:underline font-normal"
        >
          Full timeline
          <ExternalLink className="w-3 h-3" />
        </Link>
      </button>

      {expanded && (
        <div className="px-3 pb-3 border-t border-teal-100">
          {loading && (
            <p className="text-sm text-gray-500 py-3 flex items-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" />
              Loading evidence…
            </p>
          )}
          {!loading && error && <p className="text-sm text-red-600 py-3">{error}</p>}
          {!loading && !error && !story?.steps?.length && events.length === 0 && (
            <p className="text-sm text-gray-500 py-3">
              No instrumented evidence yet for this context.
            </p>
          )}
          {!loading && !error && story?.steps?.length > 0 && (
            <div className="mt-2 space-y-2">
              <div className="text-sm">
                <span className="font-medium text-gray-900">{story.title}</span>
                {' · '}
                <span className={`px-1.5 py-0.5 rounded text-xs ${STATUS_CLASS[story.status] || 'bg-gray-100'}`}>
                  {story.status}
                </span>
              </div>
              <ol className="space-y-1.5">
                {story.steps.slice(0, 6).map((step, idx) => (
                  <li key={step.event_id || idx} className="flex gap-2 text-xs text-gray-700">
                    <span className="text-gray-400 shrink-0 w-28">{formatTime(step.occurred_at)}</span>
                    <span className="font-medium text-gray-800">{step.label}</span>
                    {step.detail && <span className="text-gray-600 truncate">{step.detail}</span>}
                  </li>
                ))}
              </ol>
              {story.steps.length > 6 && (
                <p className="text-xs text-gray-500">+ {story.steps.length - 6} more steps in full timeline</p>
              )}
            </div>
          )}
          {!loading && !error && !story?.steps?.length && events.length > 0 && (
            <ul className="mt-2 space-y-1.5">
              {events.slice(0, 5).map((ev) => (
                <li key={ev.event_id} className="flex gap-2 text-xs text-gray-700">
                  <span className="text-gray-400 shrink-0 w-28">{formatTime(ev.occurred_at)}</span>
                  <span className="font-medium">{ev.event_type}</span>
                  <span className="truncate">{ev.summary || ev.evidence?.summary}</span>
                </li>
              ))}
            </ul>
          )}
          <OperationalEvidenceAnnotations
            eventId={story?.steps?.[0]?.event_id}
            rootExecutionId={story?.root_execution_id || events[0]?.root_execution_id}
            correlationId={story?.correlation_id || events[0]?.correlation_id}
            compact
          />
        </div>
      )}
    </div>
  );
}
