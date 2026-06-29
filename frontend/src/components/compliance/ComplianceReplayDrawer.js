import React, { useCallback, useState } from 'react';
import { History, Loader2, X } from 'lucide-react';
import { Button } from '../ui/button';
import complianceGraphAPI from '../../api/complianceGraphApi';

/**
 * Compliance Replay drawer — chronological decision replay (Phase 4).
 */
export default function ComplianceReplayDrawer({ decisionId, open, onClose }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [envelope, setEnvelope] = useState(null);

  const load = useCallback(async () => {
    if (!decisionId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await complianceGraphAPI.replayDecision(decisionId);
      setEnvelope(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Replay failed');
    } finally {
      setLoading(false);
    }
  }, [decisionId]);

  React.useEffect(() => {
    if (open && decisionId) load();
  }, [open, decisionId, load]);

  if (!open) return null;

  const payload = envelope?.payload || {};
  const phases = payload.phases || [];

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button type="button" className="flex-1 bg-black/30" aria-label="Close replay" onClick={onClose} />
      <aside className="w-full max-w-md bg-white shadow-xl flex flex-col h-full">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="font-semibold text-slate-900 flex items-center gap-2">
            <History className="h-5 w-5 text-teal-600" />
            Compliance Replay
          </h2>
          <button type="button" onClick={onClose} className="p-1 rounded hover:bg-slate-100">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading replay…
            </div>
          )}
          {error && <p className="text-sm text-red-600">{error}</p>}
          {envelope?.insufficient_evidence && (
            <p className="text-sm text-amber-700">{payload.reason || 'Insufficient evidence for replay.'}</p>
          )}
          {envelope && !envelope.insufficient_evidence && (
            <>
              <p className="text-xs font-mono text-slate-500 mb-3">{payload.decision_id}</p>
              <ol className="space-y-2">
                {phases.map((p, i) => (
                  <li key={`${p.phase}-${i}`} className="border-l-2 border-teal-500 pl-3 py-1">
                    <span className="text-xs uppercase tracking-wide text-teal-700">{p.phase}</span>
                    {p.source && <span className="text-xs text-slate-500 ml-2">({p.source})</span>}
                  </li>
                ))}
              </ol>
              {(payload.timeline || []).length > 0 && (
                <div className="mt-4">
                  <h3 className="text-xs font-semibold text-slate-600 mb-2">Timeline</h3>
                  <ul className="text-xs text-slate-600 space-y-1">
                    {payload.timeline.slice(0, 20).map((t, i) => (
                      <li key={i}>{t.occurred_at || '—'} — {t.summary || t.node_id || ''}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
        <div className="border-t p-3">
          <Button type="button" variant="outline" size="sm" onClick={load} disabled={loading}>
            Refresh replay
          </Button>
        </div>
      </aside>
    </div>
  );
}
