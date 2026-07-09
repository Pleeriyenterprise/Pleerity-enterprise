import React, { useCallback, useState } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import ExplainThisPanel from '../components/compliance/ExplainThisPanel';
import ComplianceReplayDrawer from '../components/compliance/ComplianceReplayDrawer';
import DecisionDiffPanel from '../components/compliance/DecisionDiffPanel';
import complianceGraphAPI from '../api/complianceGraphApi';
import { GitBranch, RefreshCw } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';

export default function AdminComplianceDecisionExplorerPage() {
  const [clientId, setClientId] = useState('');
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [replayOpen, setReplayOpen] = useState(false);
  const [compareLeft, setCompareLeft] = useState(null);

  const load = useCallback(async () => {
    const cid = clientId.trim();
    if (!cid) {
      toast.error('Enter a client ID');
      return;
    }
    setLoading(true);
    try {
      const res = await complianceGraphAPI.listDecisions({ client_id: cid, limit: 50 });
      const items = res.data?.payload?.decisions || [];
      setDecisions(items);
      if (items.length === 0) toast.info('No decisions found for this client');
    } catch {
      toast.error('Failed to load decisions');
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  const selected = decisions.find((d) => d.decision_id === selectedId);

  return (
    <UnifiedAdminLayout title="Compliance Decision Explorer">
      <div className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs text-slate-600 mb-1">Client ID</label>
            <input
              className="border rounded px-3 py-2 text-sm w-72 font-mono"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="client UUID"
            />
          </div>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-2 px-4 py-2 bg-teal-700 text-white rounded text-sm hover:bg-teal-800 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Load decisions
          </button>
        </div>

        <p className="text-xs text-slate-500 flex items-center gap-1">
          <GitBranch className="h-3 w-3" />
          Read-only explorer — all data via Graph Service; no direct storage access.
        </p>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-1 border rounded-lg overflow-hidden bg-white">
            <div className="px-3 py-2 border-b bg-slate-50 text-xs font-semibold text-slate-700">
              Decisions ({decisions.length})
            </div>
            <ul className="max-h-[480px] overflow-y-auto divide-y">
              {decisions.map((d) => (
                <li key={d.decision_id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(d.decision_id)}
                    className={`w-full text-left px-3 py-2 text-xs hover:bg-slate-50 ${
                      selectedId === d.decision_id ? 'bg-teal-50 border-l-2 border-teal-600' : ''
                    }`}
                  >
                    <div className="font-mono truncate">{d.decision_id}</div>
                    <div className="text-slate-500 truncate">{d.summary || d.decision_outcome}</div>
                    <div className="text-slate-400">{d.decision_timestamp}</div>
                  </button>
                </li>
              ))}
              {!loading && decisions.length === 0 && (
                <li className="px-3 py-4 text-xs text-slate-500">No decisions loaded.</li>
              )}
            </ul>
          </div>

          <div className="lg:col-span-2 space-y-4">
            {selected ? (
              <>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="text-xs px-3 py-1 border rounded hover:bg-slate-50"
                    onClick={() => setReplayOpen(true)}
                  >
                    Open replay
                  </button>
                  <button
                    type="button"
                    className="text-xs px-3 py-1 border rounded hover:bg-slate-50"
                    onClick={() => setCompareLeft(selected.decision_id)}
                  >
                    Use as diff left
                  </button>
                </div>
                <ExplainThisPanel
                  decisionId={selected.decision_id}
                  clientId={clientId}
                  title="Explain decision"
                />
                <DecisionDiffPanel
                  leftDecisionId={compareLeft || selected.decision_id}
                  rightDecisionId={selected.decision_id}
                />
              </>
            ) : (
              <div className="border rounded-lg p-8 text-center text-sm text-slate-500 bg-white">
                Select a decision to explain, replay, or compare.
              </div>
            )}
          </div>
        </div>
      </div>

      <ComplianceReplayDrawer
        decisionId={selectedId}
        open={replayOpen}
        onClose={() => setReplayOpen(false)}
      />
    </UnifiedAdminLayout>
  );
}
