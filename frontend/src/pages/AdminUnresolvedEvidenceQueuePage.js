import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { toast } from '@/utils/portalNotifications';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { adminAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { runGovernedAdminMutation } from '../utils/adminGovernedMutation';
import {
  getGovernanceConfirmationWording,
  getGovernanceWarning,
} from '../utils/adminActionGovernance';
import ListCognitionChip from '../components/operational/ListCognitionChip';

function GovernedActionModal({ open, title, onClose, onConfirm, confirming, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-5 space-y-4">
        <h2 className="text-lg font-semibold text-midnight-blue">{title}</h2>
        {children}
        <div className="flex gap-2 justify-end">
          <Button type="button" variant="outline" onClick={onClose} disabled={confirming}>
            Cancel
          </Button>
          <Button type="button" onClick={onConfirm} disabled={confirming}>
            {confirming ? 'Working…' : 'Confirm'}
          </Button>
        </div>
      </div>
    </div>
  );
}

/** @typedef {'resolve' | 'link' | 'reject'} ActionKind */

export default function AdminUnresolvedEvidenceQueuePage() {
  const [searchParams] = useSearchParams();
  const clientId = (searchParams.get('client_id') || '').trim();
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [rows, setRows] = useState([]);
  const [modal, setModal] = useState(null);
  const [reason, setReason] = useState('');
  const [propertyId, setPropertyId] = useState('');
  const [requirementId, setRequirementId] = useState('');
  const [acting, setActing] = useState(false);
  const [lastResult, setLastResult] = useState(null);

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

  const openAction = (kind, row) => {
    setModal({ kind, row });
    setReason('');
    setPropertyId(row.property_id || row.authoritative_property_id || '');
    setRequirementId(row.requirement_id || '');
    setLastResult(null);
  };

  const closeModal = () => {
    if (acting) return;
    setModal(null);
  };

  const executeAction = async () => {
    if (!modal?.row?.document_id) return;
    const docId = modal.row.document_id;
    setActing(true);
    try {
      let res;
      if (modal.kind === 'resolve') {
        if (!propertyId.trim()) {
          toast.error('Property ID is required to resolve scope');
          return;
        }
        res = await runGovernedAdminMutation({
          actionId: 'resolve_unresolved_scope',
          reason,
          resourceKey: docId,
          mutate: (headers) =>
            adminAPI.resolveUnresolvedDocumentScope(
              docId,
              {
                scope_type: 'PROPERTY',
                property_id: propertyId.trim(),
                requirement_id: requirementId.trim() || undefined,
                reason: reason.trim(),
              },
              { headers },
            ),
        });
      } else if (modal.kind === 'link') {
        if (!requirementId.trim()) {
          toast.error('Requirement ID is required');
          return;
        }
        res = await runGovernedAdminMutation({
          actionId: 'link_unresolved_requirement',
          reason,
          resourceKey: docId,
          mutate: (headers) =>
            adminAPI.linkUnresolvedDocumentRequirement(
              docId,
              { requirement_id: requirementId.trim(), reason: reason.trim() },
              { headers },
            ),
        });
      } else {
        res = await runGovernedAdminMutation({
          actionId: 'reject_unresolved_document',
          reason,
          resourceKey: docId,
          mutate: (headers) =>
            adminAPI.rejectUnresolvedDocument(docId, { reason: reason.trim() }, { headers }),
        });
      }
      setLastResult({ ok: true, message: res.data?.message, document_id: docId });
      toast.success(res.data?.message || 'Action completed');
      setModal(null);
      await load();
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Action failed';
      setLastResult({ ok: false, message: typeof detail === 'string' ? detail : JSON.stringify(detail) });
      toast.error(typeof detail === 'string' ? detail : 'Action failed');
    } finally {
      setActing(false);
    }
  };

  const modalActionId =
    modal?.kind === 'resolve'
      ? 'resolve_unresolved_scope'
      : modal?.kind === 'link'
        ? 'link_unresolved_requirement'
        : 'reject_unresolved_document';

  return (
    <UnifiedAdminLayout>
      <div className="space-y-4 max-w-6xl" data-testid="unresolved-queue-root">
        <div>
          <h1 className="text-2xl font-bold text-midnight-blue">UNRESOLVED evidence queue</h1>
          <p className="text-sm text-gray-600 mt-1">
            Operational disposition for documents awaiting ownership scope. All actions require reason and confirmation.
          </p>
          {clientId ? (
            <p className="text-xs text-gray-500 mt-2">
              Filtered to client <span className="font-mono">{clientId}</span>
            </p>
          ) : null}
        </div>

        {lastResult ? (
          <div
            className={`rounded-md border p-3 text-sm ${lastResult.ok ? 'border-green-200 bg-green-50 text-green-900' : 'border-red-200 bg-red-50 text-red-900'}`}
            data-testid="unresolved-last-result"
          >
            {lastResult.message}
          </div>
        ) : null}

        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {loading ? (
            <div className="p-8 text-sm text-gray-600">Loading…</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">
                  <tr>
                    <th className="px-4 py-3">Document</th>
                    <th className="px-4 py-3">Client / Property</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-gray-600">
                        No UNRESOLVED documents{clientId ? ' for this client' : ''}.
                      </td>
                    </tr>
                  ) : (
                    rows.map((r) => (
                      <tr key={r.document_id} data-testid={`unresolved-row-${r.document_id}`}>
                        <td className="px-4 py-3">
                          <div className="font-mono text-xs">{r.document_id}</div>
                          <div>{r.file_name || '—'}</div>
                          <ListCognitionChip entity={r} className="mt-2" />
                        </td>
                        <td className="px-4 py-3 text-xs">
                          <div>
                            Client:{' '}
                            {r.client_id ? (
                              <Link className="text-electric-teal hover:underline font-mono" to={`/admin/clients/${r.client_id}`}>
                                {r.client_id}
                              </Link>
                            ) : (
                              '—'
                            )}
                          </div>
                          <div className="font-mono mt-1">Property: {r.property_id || r.authoritative_property_id || '—'}</div>
                          <div className="mt-1">Req: {r.requirement_id || '—'}</div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs">{r.evidence_scope_type || 'UNRESOLVED'}</span>
                          <div className="text-xs text-gray-500">{r.status || '—'}</div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-2">
                            <Button size="sm" variant="outline" onClick={() => openAction('resolve', r)}>
                              Resolve scope
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => openAction('link', r)}>
                              Link requirement
                            </Button>
                            <Button size="sm" variant="destructive" onClick={() => openAction('reject', r)}>
                              Reject
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
          <div className="px-4 py-2 border-t text-xs text-gray-500">Total: {total}</div>
        </div>

        <GovernedActionModal
          open={Boolean(modal)}
          title={
            modal?.kind === 'resolve'
              ? 'Resolve UNRESOLVED scope'
              : modal?.kind === 'link'
                ? 'Link requirement'
                : 'Reject unresolved document'
          }
          onClose={closeModal}
          onConfirm={executeAction}
          confirming={acting}
        >
          {modal ? (
            <>
              <p className="text-xs text-gray-600">{getGovernanceWarning(modalActionId)}</p>
              <p className="text-xs font-mono text-gray-500">Document: {modal.row.document_id}</p>
              {modal.kind === 'resolve' ? (
                <>
                  <input
                    className="w-full border rounded px-3 py-2 text-sm"
                    placeholder="Property ID"
                    value={propertyId}
                    onChange={(e) => setPropertyId(e.target.value)}
                    data-testid="unresolved-resolve-property"
                  />
                  <input
                    className="w-full border rounded px-3 py-2 text-sm"
                    placeholder="Requirement ID (optional)"
                    value={requirementId}
                    onChange={(e) => setRequirementId(e.target.value)}
                  />
                </>
              ) : null}
              {modal.kind === 'link' ? (
                <input
                  className="w-full border rounded px-3 py-2 text-sm"
                  placeholder="Requirement ID"
                  value={requirementId}
                  onChange={(e) => setRequirementId(e.target.value)}
                  data-testid="unresolved-link-requirement"
                />
              ) : null}
              <textarea
                className="w-full border rounded px-3 py-2 text-sm min-h-[80px]"
                placeholder="Support reason (min 10 characters)"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                data-testid="unresolved-action-reason"
              />
              <p className="text-xs text-gray-500">{getGovernanceConfirmationWording(modalActionId)}</p>
            </>
          ) : null}
        </GovernedActionModal>
      </div>
    </UnifiedAdminLayout>
  );
}

