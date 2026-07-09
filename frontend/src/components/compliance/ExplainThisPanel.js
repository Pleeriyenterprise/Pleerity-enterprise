import React, { useCallback, useState } from 'react';
import { HelpCircle, Loader2 } from 'lucide-react';
import { Button } from '../ui/button';
import complianceGraphAPI from '../../api/complianceGraphApi';

/**
 * Reusable Explain This panel — Graph Service consumer (Phase 4).
 * Calls explain_for_scope or explain_decision; never queries storage directly.
 */
export default function ExplainThisPanel({
  scopeType,
  scopeId,
  clientId,
  decisionId,
  title = 'Explain this',
  className = '',
  onExplainLoaded,
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [envelope, setEnvelope] = useState(null);

  const load = useCallback(async () => {
    if (!clientId && !decisionId) {
      setError('Client or decision scope required.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      let res;
      if (decisionId) {
        res = await complianceGraphAPI.explainDecision(decisionId);
      } else {
        res = await complianceGraphAPI.explainScope({
          scope_type: scopeType,
          scope_id: scopeId,
          client_id: clientId,
        });
      }
      setEnvelope(res.data);
      if (onExplainLoaded) onExplainLoaded(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Explain failed');
    } finally {
      setLoading(false);
    }
  }, [scopeType, scopeId, clientId, decisionId, onExplainLoaded]);

  const payload = envelope?.payload || {};
  const insufficient = envelope?.insufficient_evidence;

  return (
    <div className={`rounded-lg border border-slate-200 bg-white p-4 ${className}`}>
      <div className="flex items-center justify-between gap-2 mb-3">
        <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
          <HelpCircle className="h-4 w-4 text-teal-600" />
          {title}
        </h3>
        <Button type="button" variant="outline" size="sm" onClick={load} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Explain'}
        </Button>
      </div>
      {error && <p className="text-sm text-red-600 mb-2">{error}</p>}
      {insufficient && (
        <p className="text-sm text-amber-700">{payload.executive_summary || payload.reason || 'Insufficient evidence.'}</p>
      )}
      {envelope && !insufficient && (
        <div className="space-y-2 text-sm text-slate-700">
          <p className="font-medium">{payload.executive_summary}</p>
          {payload.decision && (
            <dl className="grid grid-cols-2 gap-1 text-xs">
              <dt className="text-slate-500">Decision</dt>
              <dd className="font-mono truncate">{payload.decision.decision_id}</dd>
              <dt className="text-slate-500">Outcome</dt>
              <dd>{payload.decision.decision_outcome}</dd>
              <dt className="text-slate-500">Timestamp</dt>
              <dd>{payload.decision.decision_timestamp}</dd>
            </dl>
          )}
          {(payload.decision_reasoning || [])?.length > 0 && (
            <ul className="list-disc pl-4 text-xs text-slate-600">
              {payload.decision_reasoning.map((s) => (
                <li key={s.step}>{s.statement}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {!envelope && !error && !loading && (
        <p className="text-xs text-slate-500">Load an authoritative explanation from the Compliance Evidence Graph.</p>
      )}
    </div>
  );
}
