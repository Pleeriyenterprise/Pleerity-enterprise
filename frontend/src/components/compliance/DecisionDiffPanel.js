import React, { useCallback, useState } from 'react';
import { GitCompare, Loader2 } from 'lucide-react';
import { Button } from '../ui/button';
import complianceGraphAPI from '../../api/complianceGraphApi';

/**
 * Decision Diff panel — compare two decisions via Graph Service (Phase 4).
 */
export default function DecisionDiffPanel({ leftDecisionId, rightDecisionId, className = '' }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [envelope, setEnvelope] = useState(null);
  const [left, setLeft] = useState(leftDecisionId || '');
  const [right, setRight] = useState(rightDecisionId || '');

  const compare = useCallback(async () => {
    if (!left.trim() || !right.trim()) {
      setError('Both decision IDs required.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await complianceGraphAPI.compareDecisions(left.trim(), right.trim());
      setEnvelope(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Compare failed');
    } finally {
      setLoading(false);
    }
  }, [left, right]);

  const payload = envelope?.payload || {};
  const diff = payload.diff || {};

  return (
    <div className={`rounded-lg border border-slate-200 bg-white p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-3">
        <GitCompare className="h-4 w-4 text-teal-600" />
        Decision Diff
      </h3>
      <div className="grid grid-cols-2 gap-2 mb-3">
        <input
          className="text-xs border rounded px-2 py-1 font-mono"
          placeholder="Left decision ID"
          value={left}
          onChange={(e) => setLeft(e.target.value)}
        />
        <input
          className="text-xs border rounded px-2 py-1 font-mono"
          placeholder="Right decision ID"
          value={right}
          onChange={(e) => setRight(e.target.value)}
        />
      </div>
      <Button type="button" variant="outline" size="sm" onClick={compare} disabled={loading}>
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Compare'}
      </Button>
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      {envelope?.insufficient_evidence && (
        <p className="text-sm text-amber-700 mt-2">{payload.reason || 'Insufficient evidence.'}</p>
      )}
      {envelope && !envelope.insufficient_evidence && (
        <div className="mt-3 text-sm">
          <p className="text-slate-600 mb-2">
            Outcome changed: <strong>{payload.outcome_changed ? 'Yes' : 'No'}</strong>
          </p>
          {Object.keys(diff).length === 0 ? (
            <p className="text-xs text-slate-500">No structural differences detected.</p>
          ) : (
            <pre className="text-xs bg-slate-50 p-2 rounded overflow-x-auto">{JSON.stringify(diff, null, 2)}</pre>
          )}
        </div>
      )}
    </div>
  );
}
