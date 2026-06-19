import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  RefreshCw,
  Search,
  CheckCircle,
  XCircle,
  MessageSquare,
  Copy,
  Archive,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import UnifiedAdminLayout from '../../../components/admin/UnifiedAdminLayout';
import { discoveryApi, isDiscoveryModuleEnabled } from '../../../api/discoveryApi';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Alert, AlertDescription } from '../../../components/ui/alert';
import { toast } from '@/utils/portalNotifications';

const REVIEW_STATUS_OPTIONS = [
  { value: '', label: 'All review statuses' },
  { value: 'needs_review', label: 'Needs review' },
  { value: 'duplicate_detected', label: 'Duplicate detected' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'archived', label: 'Archived' },
];

const DUPLICATE_STATUS_OPTIONS = [
  { value: '', label: 'All duplicate statuses' },
  { value: 'none', label: 'None' },
  { value: 'possible', label: 'Possible' },
  { value: 'confirmed', label: 'Confirmed' },
];

const REJECT_REASONS = [
  { value: 'low_quality', label: 'Low quality' },
  { value: 'invalid_contact', label: 'Invalid contact' },
  { value: 'policy_violation', label: 'Policy violation' },
  { value: 'duplicate', label: 'Duplicate' },
  { value: 'other', label: 'Other' },
];

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-GB');
  } catch {
    return String(iso);
  }
}

function statusBadgeClass(status) {
  const map = {
    needs_review: 'bg-amber-100 text-amber-800',
    duplicate_detected: 'bg-orange-100 text-orange-800',
    approved: 'bg-green-100 text-green-800',
    rejected: 'bg-red-100 text-red-800',
    archived: 'bg-gray-100 text-gray-700',
    possible: 'bg-yellow-100 text-yellow-800',
    confirmed: 'bg-red-100 text-red-800',
    none: 'bg-gray-100 text-gray-600',
  };
  return map[status] || 'bg-gray-100 text-gray-700';
}

function Badge({ value }) {
  if (!value) return <span className="text-gray-400">—</span>;
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${statusBadgeClass(value)}`}>
      {String(value).replace(/_/g, ' ')}
    </span>
  );
}

function ConfirmModal({ open, title, description, confirmLabel, confirmVariant = 'default', onConfirm, onCancel, children, confirmDisabled }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
        <h3 className="text-lg font-semibold text-midnight-blue">{title}</h3>
        {description && <p className="text-sm text-gray-600">{description}</p>}
        {children}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button variant={confirmVariant} onClick={onConfirm} disabled={confirmDisabled}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function AdminDiscoveryReviewPage() {
  const moduleEnabled = isDiscoveryModuleEnabled();
  const [summary, setSummary] = useState(null);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({ review_status: '', duplicate_status: '', provider: '' });
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [audit, setAudit] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionModal, setActionModal] = useState(null);
  const [actionFields, setActionFields] = useState({});
  const [actionSubmitting, setActionSubmitting] = useState(false);

  const loadQueue = useCallback(async () => {
    if (!moduleEnabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = { limit: 100 };
      if (filters.review_status) params.review_status = filters.review_status;
      if (filters.duplicate_status) params.duplicate_status = filters.duplicate_status;
      if (filters.provider.trim()) params.provider = filters.provider.trim();
      const [queueRes, summaryRes] = await Promise.all([
        discoveryApi.getReviewQueue(params),
        discoveryApi.getReviewSummary(),
      ]);
      setItems(queueRes.data?.items || []);
      setTotal(queueRes.data?.total || 0);
      setSummary(summaryRes.data || null);
    } catch (err) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || err.message;
      setError(typeof msg === 'string' ? msg : 'Failed to load discovery review queue');
    } finally {
      setLoading(false);
    }
  }, [filters, moduleEnabled]);

  const loadDetail = useCallback(async (prospectId) => {
    if (!prospectId || !moduleEnabled) return;
    setDetailLoading(true);
    try {
      const [detailRes, auditRes] = await Promise.all([
        discoveryApi.getReviewDetail(prospectId),
        discoveryApi.getAuditHistory(prospectId, { limit: 100 }),
      ]);
      setDetail(detailRes.data);
      setAudit(auditRes.data);
    } catch (err) {
      toast.error(err.response?.data?.detail?.message || 'Failed to load prospect detail');
      setDetail(null);
      setAudit(null);
    } finally {
      setDetailLoading(false);
    }
  }, [moduleEnabled]);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    if (selectedId) loadDetail(selectedId);
    else {
      setDetail(null);
      setAudit(null);
    }
  }, [selectedId, loadDetail]);

  const openAction = (type) => {
    setActionFields({});
    setActionModal(type);
  };

  const closeAction = () => {
    setActionModal(null);
    setActionFields({});
  };

  const runAction = async () => {
    if (!selectedId || !actionModal) return;
    setActionSubmitting(true);
    try {
      if (actionModal === 'approve') {
        await discoveryApi.approveProspect(selectedId, {
          override_reason: actionFields.override_reason,
          notes: actionFields.notes,
          reason_code: actionFields.reason_code,
        });
        toast.success('Prospect approved');
      } else if (actionModal === 'reject') {
        await discoveryApi.rejectProspect(selectedId, {
          reason_code: actionFields.reason_code,
          notes: actionFields.notes,
        });
        toast.success('Prospect rejected');
      } else if (actionModal === 'request_changes') {
        await discoveryApi.requestChanges(selectedId, {
          change_request_notes: actionFields.change_request_notes,
        });
        toast.success('Change request recorded');
      } else if (actionModal === 'mark_duplicate') {
        await discoveryApi.markDuplicate(selectedId);
        toast.success('Duplicate marked');
      } else if (actionModal === 'clear_duplicate') {
        await discoveryApi.clearDuplicate(selectedId, {
          reason_code: actionFields.reason_code,
          notes: actionFields.notes,
        });
        toast.success('Duplicate cleared');
      } else if (actionModal === 'archive') {
        await discoveryApi.archiveProspect(selectedId);
        toast.success('Prospect archived');
      }
      closeAction();
      await loadQueue();
      await loadDetail(selectedId);
    } catch (err) {
      toast.error(err.response?.data?.detail?.message || 'Action failed');
    } finally {
      setActionSubmitting(false);
    }
  };

  const needsDuplicateOverride = useMemo(() => {
    if (!detail) return false;
    return (
      detail.duplicate_status === 'confirmed' ||
      detail.review_status === 'duplicate_detected'
    );
  }, [detail]);

  const rejectValid = Boolean(actionFields.reason_code && actionFields.notes?.trim());
  const changesValid = Boolean(actionFields.change_request_notes?.trim());
  const approveValid = needsDuplicateOverride
    ? Boolean(actionFields.override_reason?.trim() && actionFields.notes?.trim())
    : true;

  if (!moduleEnabled) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6 max-w-3xl">
          <Alert>
            <AlertDescription>
              Discovery review is not enabled. Set REACT_APP_DISCOVERY_MODULE_ENABLED=true for non-production admin testing.
            </AlertDescription>
          </Alert>
        </div>
      </UnifiedAdminLayout>
    );
  }

  return (
    <UnifiedAdminLayout>
      <div className="p-4 lg:p-6 space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-midnight-blue">Discovery Review</h1>
            <p className="text-sm text-gray-600">Manual reviewer workflow — no CRM import in this stage.</p>
          </div>
          <Button variant="outline" onClick={loadQueue} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              ['Needs review', summary.total_needs_review],
              ['Duplicates', summary.total_duplicates],
              ['Approved', summary.total_approved],
              ['High priority', summary.high_priority_count],
            ].map(([label, value]) => (
              <Card key={label}>
                <CardContent className="pt-4">
                  <p className="text-xs text-gray-500">{label}</p>
                  <p className="text-2xl font-semibold">{value ?? 0}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Filters</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <select
              className="border rounded-md px-3 py-2 text-sm"
              value={filters.review_status}
              onChange={(e) => setFilters((f) => ({ ...f, review_status: e.target.value }))}
            >
              {REVIEW_STATUS_OPTIONS.map((o) => (
                <option key={o.value || 'all'} value={o.value}>{o.label}</option>
              ))}
            </select>
            <select
              className="border rounded-md px-3 py-2 text-sm"
              value={filters.duplicate_status}
              onChange={(e) => setFilters((f) => ({ ...f, duplicate_status: e.target.value }))}
            >
              {DUPLICATE_STATUS_OPTIONS.map((o) => (
                <option key={o.value || 'all'} value={o.value}>{o.label}</option>
              ))}
            </select>
            <Input
              placeholder="Provider filter"
              value={filters.provider}
              onChange={(e) => setFilters((f) => ({ ...f, provider: e.target.value }))}
              className="max-w-xs"
            />
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
          <Card className="xl:col-span-3">
            <CardHeader>
              <CardTitle>Review queue</CardTitle>
              <CardDescription>{total} prospect(s)</CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {loading ? (
                <div className="flex items-center gap-2 text-gray-500 py-8 justify-center">
                  <Loader2 className="w-5 h-5 animate-spin" /> Loading queue…
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="py-2 pr-2">Company / contact</th>
                      <th className="py-2 pr-2">Contact</th>
                      <th className="py-2 pr-2">Provider</th>
                      <th className="py-2 pr-2">Review</th>
                      <th className="py-2 pr-2">Duplicate</th>
                      <th className="py-2 pr-2">Quality</th>
                      <th className="py-2 pr-2">Priority</th>
                      <th className="py-2 pr-2">Created</th>
                      <th className="py-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => (
                      <tr
                        key={row.prospect_id}
                        className={`border-b hover:bg-gray-50 ${selectedId === row.prospect_id ? 'bg-teal-50' : ''}`}
                      >
                        <td className="py-2 pr-2">
                          <div className="font-medium">{row.company_name || '—'}</div>
                          <div className="text-xs text-gray-500">{row.contact_name || '—'}</div>
                        </td>
                        <td className="py-2 pr-2 text-xs">
                          {row.has_email ? 'Email ✓' : 'Email —'}
                          <br />
                          {row.has_phone ? 'Phone ✓' : 'Phone —'}
                        </td>
                        <td className="py-2 pr-2">{row.provider || '—'}</td>
                        <td className="py-2 pr-2"><Badge value={row.review_status} /></td>
                        <td className="py-2 pr-2"><Badge value={row.duplicate_status} /></td>
                        <td className="py-2 pr-2">{row.platform_quality_score ?? '—'}</td>
                        <td className="py-2 pr-2">{row.review_priority ?? '—'}</td>
                        <td className="py-2 pr-2 text-xs">{formatDate(row.created_at)}</td>
                        <td className="py-2">
                          <Button size="sm" variant="outline" onClick={() => setSelectedId(row.prospect_id)}>
                            <Search className="w-3 h-3 mr-1" /> Review
                          </Button>
                        </td>
                      </tr>
                    ))}
                    {!items.length && (
                      <tr>
                        <td colSpan={9} className="py-8 text-center text-gray-500">No prospects in queue.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>

          <Card className="xl:col-span-2">
            <CardHeader>
              <CardTitle>Prospect detail</CardTitle>
              <CardDescription>
                {selectedId ? `ID: ${selectedId}` : 'Select a prospect from the queue'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 max-h-[70vh] overflow-y-auto">
              {!selectedId && (
                <p className="text-sm text-gray-500">Choose a row to inspect quality, duplicates, and audit history.</p>
              )}
              {selectedId && detailLoading && (
                <div className="flex items-center gap-2 text-gray-500">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading detail…
                </div>
              )}
              {detail && !detailLoading && (
                <>
                  <section>
                    <h4 className="font-medium text-sm mb-1">Identity</h4>
                    <dl className="text-sm grid grid-cols-2 gap-1">
                      <dt className="text-gray-500">Company</dt><dd>{detail.prospect?.company_name || '—'}</dd>
                      <dt className="text-gray-500">Contact</dt><dd>{detail.prospect?.contact_name || '—'}</dd>
                      <dt className="text-gray-500">Email</dt><dd>{detail.prospect?.email || (detail.prospect?.erasure_status === 'erased' ? '[ERASED]' : '—')}</dd>
                      <dt className="text-gray-500">Phone</dt><dd>{detail.prospect?.phone || '—'}</dd>
                    </dl>
                  </section>

                  <section>
                    <h4 className="font-medium text-sm mb-1">Business context</h4>
                    <dl className="text-sm grid grid-cols-2 gap-1">
                      <dt className="text-gray-500">Provider</dt><dd>{detail.prospect?.provider || '—'}</dd>
                      <dt className="text-gray-500">Campaign</dt><dd>{detail.prospect?.campaign_id || '—'}</dd>
                      <dt className="text-gray-500">Lawful basis</dt><dd>{detail.lawful_basis || '—'}</dd>
                      <dt className="text-gray-500">Marketing consent</dt><dd>{detail.marketing_consent ? 'Yes' : 'No'}</dd>
                    </dl>
                  </section>

                  <section>
                    <h4 className="font-medium text-sm mb-1">Quality score: {detail.platform_quality_score ?? '—'}</h4>
                    {detail.quality_breakdown && (
                      <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                        {JSON.stringify(detail.quality_breakdown, null, 2)}
                      </pre>
                    )}
                    {detail.quality_explanation?.breakdown_lines?.length > 0 && (
                      <ul className="text-xs text-gray-600 list-disc ml-4 mt-1">
                        {detail.quality_explanation.breakdown_lines.map((line) => (
                          <li key={line}>{line}</li>
                        ))}
                      </ul>
                    )}
                  </section>

                  <section>
                    <h4 className="font-medium text-sm mb-1">Duplicate evidence</h4>
                    {detail.duplicate_evidence ? (
                      <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                        {JSON.stringify(detail.duplicate_evidence, null, 2)}
                      </pre>
                    ) : (
                      <p className="text-xs text-gray-500">No duplicate evidence recorded.</p>
                    )}
                  </section>

                  <section>
                    <h4 className="font-medium text-sm mb-1">Origin lineage</h4>
                    <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                      {JSON.stringify(detail.origin_lineage || [], null, 2)}
                    </pre>
                  </section>

                  <section>
                    <h4 className="font-medium text-sm mb-1">Import readiness</h4>
                    <Alert>
                      <AlertTriangle className="w-4 h-4" />
                      <AlertDescription>{detail.import_readiness_notice}</AlertDescription>
                    </Alert>
                    <pre className="text-xs bg-gray-50 p-2 rounded mt-2 overflow-x-auto">
                      {JSON.stringify(detail.import_readiness || {}, null, 2)}
                    </pre>
                  </section>

                  <section>
                    <h4 className="font-medium text-sm mb-1">Audit history</h4>
                    {detail.audit_summary && (
                      <p className="text-xs text-gray-600 mb-2">
                        {(detail.audit_summary.lines || []).join(' ')}
                      </p>
                    )}
                    <ul className="text-xs space-y-2">
                      {(audit?.items || []).map((ev) => (
                        <li key={ev.audit_id} className="border rounded p-2">
                          <div className="font-medium">{ev.event_type}</div>
                          <div className="text-gray-500">{formatDate(ev.created_at)} · {ev.actor_email || ev.actor_id || 'system'}</div>
                        </li>
                      ))}
                    </ul>
                  </section>

                  <div className="flex flex-wrap gap-2 pt-2 border-t">
                    <Button size="sm" onClick={() => openAction('approve')}>
                      <CheckCircle className="w-3 h-3 mr-1" /> Approve
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => openAction('reject')}>
                      <XCircle className="w-3 h-3 mr-1" /> Reject
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => openAction('request_changes')}>
                      <MessageSquare className="w-3 h-3 mr-1" /> Request changes
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => openAction('mark_duplicate')}>
                      <Copy className="w-3 h-3 mr-1" /> Mark duplicate
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => openAction('clear_duplicate')}>
                      Clear duplicate
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => openAction('archive')}>
                      <Archive className="w-3 h-3 mr-1" /> Archive
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <ConfirmModal
        open={actionModal === 'approve'}
        title="Approve prospect"
        description={needsDuplicateOverride ? 'Confirmed duplicate — override reason and notes are required.' : 'Confirm approval. No CRM import will occur.'}
        confirmLabel={actionSubmitting ? 'Submitting…' : 'Confirm approve'}
        onCancel={closeAction}
        onConfirm={runAction}
        confirmDisabled={actionSubmitting || !approveValid}
      >
        {needsDuplicateOverride && (
          <div className="space-y-2">
            <Input
              placeholder="Override reason (required)"
              value={actionFields.override_reason || ''}
              onChange={(e) => setActionFields((f) => ({ ...f, override_reason: e.target.value }))}
            />
            <Input
              placeholder="Notes (required)"
              value={actionFields.notes || ''}
              onChange={(e) => setActionFields((f) => ({ ...f, notes: e.target.value }))}
            />
          </div>
        )}
      </ConfirmModal>

      <ConfirmModal
        open={actionModal === 'reject'}
        title="Reject prospect"
        description="Reason code and notes are required."
        confirmLabel={actionSubmitting ? 'Submitting…' : 'Confirm reject'}
        confirmVariant="destructive"
        onCancel={closeAction}
        onConfirm={runAction}
        confirmDisabled={actionSubmitting || !rejectValid}
      >
        <div className="space-y-2">
          <select
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={actionFields.reason_code || ''}
            onChange={(e) => setActionFields((f) => ({ ...f, reason_code: e.target.value }))}
          >
            <option value="">Select reason</option>
            {REJECT_REASONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
          <Input
            placeholder="Notes (required)"
            value={actionFields.notes || ''}
            onChange={(e) => setActionFields((f) => ({ ...f, notes: e.target.value }))}
          />
        </div>
      </ConfirmModal>

      <ConfirmModal
        open={actionModal === 'request_changes'}
        title="Request changes"
        description="Describe what must change before re-review."
        confirmLabel={actionSubmitting ? 'Submitting…' : 'Confirm request'}
        onCancel={closeAction}
        onConfirm={runAction}
        confirmDisabled={actionSubmitting || !changesValid}
      >
        <Input
          placeholder="Change request notes (required)"
          value={actionFields.change_request_notes || ''}
          onChange={(e) => setActionFields((f) => ({ ...f, change_request_notes: e.target.value }))}
        />
      </ConfirmModal>

      <ConfirmModal
        open={actionModal === 'mark_duplicate'}
        title="Mark duplicate"
        description="Run duplicate classification and update status."
        confirmLabel={actionSubmitting ? 'Submitting…' : 'Confirm mark duplicate'}
        onCancel={closeAction}
        onConfirm={runAction}
        confirmDisabled={actionSubmitting}
      />

      <ConfirmModal
        open={actionModal === 'clear_duplicate'}
        title="Clear duplicate"
        description="Clear duplicate status after review."
        confirmLabel={actionSubmitting ? 'Submitting…' : 'Confirm clear'}
        onCancel={closeAction}
        onConfirm={runAction}
        confirmDisabled={actionSubmitting}
      />

      <ConfirmModal
        open={actionModal === 'archive'}
        title="Archive prospect"
        description="Archive this prospect after terminal review decision."
        confirmLabel={actionSubmitting ? 'Submitting…' : 'Confirm archive'}
        onCancel={closeAction}
        onConfirm={runAction}
        confirmDisabled={actionSubmitting}
      />
    </UnifiedAdminLayout>
  );
}
