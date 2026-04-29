import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { toast } from '@/utils/portalNotifications';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { adminAPI } from '../api/client';

/**
 * Read-only UNRESOLVED evidence ownership queue (GET /admin/documents/unresolved).
 * Linked from the client control panel when the client has UNRESOLVED documents.
 */
export default function AdminUnresolvedEvidenceQueuePage() {
  const [searchParams] = useSearchParams();
  const clientId = (searchParams.get('client_id') || '').trim();
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [rows, setRows] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.listUnresolvedEvidenceDocuments({
        ...(clientId ? { client_id: clientId } : {}),
        limit: 100,
        skip: 0,
      });
      setRows(Array.isArray(res.data?.documents) ? res.data.documents : []);
      setTotal(typeof res.data?.total === 'number' ? res.data.total : 0);
    } catch {
      toast.error('Failed to load UNRESOLVED evidence queue');
      setRows([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <UnifiedAdminLayout>
      <div className="space-y-4 max-w-5xl" data-testid="unresolved-queue-root">
        <div>
          <h1 className="text-2xl font-bold text-midnight-blue">UNRESOLVED evidence queue</h1>
          <p className="text-sm text-gray-600 mt-1">
            Documents awaiting ownership scope (same API as support tooling). Use{' '}
            <Link to="/admin/dashboard" className="text-electric-teal font-medium hover:underline">
              Admin dashboard
            </Link>{' '}
            for pending verification; this queue is for UNRESOLVED scope only.
          </p>
          <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700">
            Read-only diagnostic: this queue identifies unresolved authority. Do not infer compliance from this table
            alone; cross-check pending verification and requirement state.
          </div>
          {clientId ? (
            <p className="text-xs text-gray-500 mt-2">
              Filtered to client <span className="font-mono">{clientId}</span> —{' '}
              <Link to="/admin/documents/unresolved-queue" className="text-electric-teal hover:underline">
                Clear filter
              </Link>{' '}
              or{' '}
              <Link to={`/admin/clients/${encodeURIComponent(clientId)}`} className="text-electric-teal hover:underline">
                Control panel
              </Link>
              .
            </p>
          ) : null}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {loading ? (
            <div className="p-8 text-sm text-gray-600">Loading…</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Document</th>
                    <th className="px-4 py-3">Client</th>
                    <th className="px-4 py-3">Uploaded</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="px-4 py-6 text-gray-600">
                        No UNRESOLVED documents{clientId ? ' for this client' : ''}.
                      </td>
                    </tr>
                  ) : (
                    rows.map((r) => (
                      <tr key={r.document_id || `${r.client_id}-${r.uploaded_at}`} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <div className="font-mono text-xs text-gray-800">{r.document_id}</div>
                          <div className="text-gray-700">{r.file_name || '—'}</div>
                        </td>
                        <td className="px-4 py-3">
                          {r.client_id ? (
                            <Link className="text-electric-teal hover:underline font-mono text-xs" to={`/admin/clients/${r.client_id}`}>
                              {r.client_id}
                            </Link>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="px-4 py-3 text-gray-700 whitespace-nowrap">
                          {r.uploaded_at ? String(r.uploaded_at) : '—'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
          <div className="px-4 py-2 border-t border-gray-100 text-xs text-gray-500">Total matching: {total}</div>
        </div>
      </div>
    </UnifiedAdminLayout>
  );
}
