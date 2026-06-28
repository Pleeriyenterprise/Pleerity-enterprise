import React, { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../../api/client';
import { MessageSquare, RefreshCw } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';

function formatTime(iso) {
  return iso ? new Date(iso).toLocaleString() : '—';
}

/**
 * Admin annotations for operational evidence contexts (separate from runtime evidence).
 */
export default function OperationalEvidenceAnnotations({
  eventId,
  rootExecutionId,
  correlationId,
  compact = false,
}) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);

  const hasContext = Boolean(eventId || rootExecutionId || correlationId);

  const load = useCallback(async () => {
    if (!hasContext) return;
    setLoading(true);
    try {
      const params = {};
      if (eventId) params.event_id = eventId;
      if (rootExecutionId) params.root_execution_id = rootExecutionId;
      if (correlationId) params.correlation_id = correlationId;
      const res = await adminAPI.getOperationalEvidenceAnnotations(params);
      setItems(res.data?.items || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [eventId, rootExecutionId, correlationId, hasContext]);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    const trimmed = note.trim();
    if (!trimmed || !hasContext) return;
    setSaving(true);
    try {
      await adminAPI.createOperationalEvidenceAnnotation({
        event_id: eventId || undefined,
        root_execution_id: rootExecutionId || undefined,
        correlation_id: correlationId || undefined,
        note: trimmed,
      });
      setNote('');
      toast.success('Annotation saved');
      load();
    } catch {
      toast.error('Failed to save annotation');
    } finally {
      setSaving(false);
    }
  };

  if (!hasContext) return null;

  return (
    <div className={compact ? 'mt-3' : 'mt-4 border-t border-gray-100 pt-3'}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <h4 className="text-sm font-medium text-gray-900 flex items-center gap-1">
          <MessageSquare className="w-4 h-4 text-teal-700" />
          Annotations
        </h4>
        <button type="button" onClick={load} className="text-xs text-gray-500 hover:text-gray-700">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>
      {items.length > 0 && (
        <ul className="space-y-2 mb-3 max-h-40 overflow-auto">
          {items.map((ann) => (
            <li key={ann.annotation_id || ann.id} className="text-xs bg-gray-50 rounded px-2 py-1.5">
              <p className="text-gray-800 whitespace-pre-wrap">{ann.note}</p>
              <p className="text-gray-400 mt-0.5">
                {ann.actor_id} · {formatTime(ann.created_at)}
              </p>
            </li>
          ))}
        </ul>
      )}
      {!items.length && !loading && (
        <p className="text-xs text-gray-500 mb-2">No annotations yet.</p>
      )}
      <form onSubmit={submit} className="flex flex-col gap-2">
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Add investigation note…"
          rows={compact ? 2 : 3}
          className="border border-gray-300 rounded text-sm px-2 py-1.5 resize-y"
          maxLength={4000}
        />
        <button
          type="submit"
          disabled={saving || !note.trim()}
          className="self-start px-3 py-1 text-xs bg-teal-700 text-white rounded hover:bg-teal-800 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Add annotation'}
        </button>
      </form>
    </div>
  );
}
