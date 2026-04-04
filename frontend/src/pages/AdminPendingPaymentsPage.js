import React, { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw,
  Send,
  Copy,
  Loader2,
  AlertCircle,
  Search,
  MoreHorizontal,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { toast } from 'sonner';
import api, { adminAPI } from '../api/client';
import { useStepUpApi } from '../hooks/useStepUpApi';

const BUCKETS = [
  { id: 'pending', label: 'Pending setup' },
  { id: 'archived', label: 'Archived' },
  { id: 'purge_eligible', label: 'Purge eligible' },
  { id: 'test_like', label: 'Test-like' },
  { id: 'all', label: 'All (funnel)' },
];

const ARCHIVE_REASONS = [
  { value: 'stale_lead', label: 'Stale lead / no response' },
  { value: 'duplicate_test', label: 'Duplicate or test account' },
  { value: 'user_request', label: 'User requested removal' },
  { value: 'compliance', label: 'Compliance / operational' },
  { value: 'other', label: 'Other' },
];

function isEnterpriseArchived(item) {
  const s = (item.client_lifecycle_status || '').toUpperCase();
  return s === 'ARCHIVED' || s === 'PURGE_ELIGIBLE';
}

function enterpriseLifecycleClass(derived) {
  const d = (derived || '').toUpperCase();
  if (d === 'ARCHIVED' || d === 'PURGE_ELIGIBLE') return 'bg-slate-200 text-slate-800';
  if (d === 'ACTIVE') return 'bg-emerald-100 text-emerald-900';
  if (d === 'SUSPENDED') return 'bg-amber-100 text-amber-900';
  if (d === 'LEAD') return 'bg-violet-100 text-violet-900';
  return 'bg-sky-100 text-sky-900';
}

function paymentLifecycleClass(status) {
  const s = (status || '').toLowerCase();
  if (s === 'abandoned') return 'bg-amber-100 text-amber-800';
  if (s === 'archived') return 'bg-gray-100 text-gray-700';
  return 'bg-blue-100 text-blue-800';
}

function errMessage(error) {
  const d = error?.response?.data?.detail;
  if (d && typeof d === 'object') {
    if (Array.isArray(d.blockers)) return d.blockers.join(', ');
    return d.message || d.error_code || JSON.stringify(d);
  }
  return typeof d === 'string' ? d : error?.message || 'Request failed';
}

const AdminPendingPaymentsPage = ({ embedded = false }) => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [bucket, setBucket] = useState('pending');
  const [rowBusy, setRowBusy] = useState(null);

  const stepUp = useStepUpApi();

  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archiveClient, setArchiveClient] = useState(null);
  const [archiveReasonKey, setArchiveReasonKey] = useState('stale_lead');
  const [archiveNotes, setArchiveNotes] = useState('');

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteCheck, setDeleteCheck] = useState({ allowed: false, blockers: [] });
  const [deleteCheckLoading, setDeleteCheckLoading] = useState(false);

  const fetchPendingPayments = useCallback(async (q, b) => {
    setLoading(true);
    try {
      const params = { bucket: b || 'pending' };
      if (q && q.trim()) params.q = q.trim();
      const response = await adminAPI.getPendingPayments(params);
      const raw = response?.data?.items;
      setItems(Array.isArray(raw) ? raw : []);
    } catch (error) {
      console.error('Failed to fetch pending payments:', error);
      toast.error('Failed to load pending payments');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => fetchPendingPayments(searchQuery, bucket), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, bucket, fetchPendingPayments]);

  const handleSendPaymentLink = async (clientId) => {
    setSending(clientId);
    try {
      const response = await api.post(`/admin/intake/${clientId}/send-payment-link`);
      const { checkout_url, email_sent, reused } = response.data;
      toast.success(email_sent ? 'Payment link sent by email' : reused ? 'Existing link returned' : 'Payment link created');
      if (!email_sent && checkout_url) {
        toast.info('Email not configured. Use Copy link to share.');
      }
      await fetchPendingPayments(searchQuery, bucket);
    } catch (error) {
      toast.error(errMessage(error));
    } finally {
      setSending(null);
    }
  };

  const handleCopyLink = (item) => {
    const url = item.latest_checkout_url;
    if (!url) {
      toast.error('No link available. Click Send payment link first.');
      return;
    }
    navigator.clipboard.writeText(url).then(
      () => toast.success('Link copied to clipboard'),
      () => toast.error('Failed to copy')
    );
  };

  const openArchive = (row) => {
    setArchiveClient(row);
    setArchiveReasonKey('stale_lead');
    setArchiveNotes('');
    setArchiveOpen(true);
  };

  const submitArchive = async () => {
    if (!archiveClient?.client_id) return;
    const preset = ARCHIVE_REASONS.find((r) => r.value === archiveReasonKey);
    const parts = [preset?.label || archiveReasonKey];
    if (archiveNotes.trim()) parts.push(archiveNotes.trim());
    const archive_reason = parts.join(' — ');
    try {
      await stepUp.request((headers) =>
        adminAPI.archiveClient(archiveClient.client_id, { archive_reason }, { headers })
      );
      toast.success('Client archived');
      setArchiveOpen(false);
      await fetchPendingPayments(searchQuery, bucket);
    } catch (error) {
      if (error?.message === 'step_up_cancelled') return;
      toast.error(errMessage(error));
    }
  };

  const runRestore = async (clientId) => {
    setRowBusy(clientId);
    try {
      await stepUp.request((headers) => adminAPI.restoreClient(clientId, { headers }));
      toast.success('Client restored');
      await fetchPendingPayments(searchQuery, bucket);
    } catch (error) {
      if (error?.message === 'step_up_cancelled') return;
      toast.error(errMessage(error));
    } finally {
      setRowBusy(null);
    }
  };

  const runMarkPurge = async (clientId) => {
    setRowBusy(clientId);
    try {
      await stepUp.request((headers) => adminAPI.markClientPurgeEligible(clientId, { headers }));
      toast.success('Marked purge eligible');
      await fetchPendingPayments(searchQuery, bucket);
    } catch (error) {
      if (error?.message === 'step_up_cancelled') return;
      toast.error(errMessage(error));
    } finally {
      setRowBusy(null);
    }
  };

  const runFlagTestLike = async (clientId) => {
    setRowBusy(clientId);
    try {
      await stepUp.request((headers) => adminAPI.flagClientTestLike(clientId, {}, { headers }));
      toast.success('Flagged as test-like');
      await fetchPendingPayments(searchQuery, bucket);
    } catch (error) {
      if (error?.message === 'step_up_cancelled') return;
      toast.error(errMessage(error));
    } finally {
      setRowBusy(null);
    }
  };

  const openPermanentDelete = async (row) => {
    setDeleteTarget(row);
    setDeleteCheck({ allowed: false, blockers: [] });
    setDeleteOpen(true);
    setDeleteCheckLoading(true);
    try {
      const { data } = await adminAPI.getClientPermanentDeleteCheck(row.client_id);
      setDeleteCheck({
        allowed: !!data?.allowed,
        blockers: Array.isArray(data?.blockers) ? data.blockers : [],
      });
    } catch (error) {
      toast.error(errMessage(error));
      setDeleteCheck({ allowed: false, blockers: ['check_failed'] });
    } finally {
      setDeleteCheckLoading(false);
    }
  };

  const confirmPermanentDelete = async () => {
    if (!deleteTarget?.client_id) return;
    try {
      await stepUp.request((headers) =>
        adminAPI.permanentDeleteClient(deleteTarget.client_id, { headers })
      );
      toast.success('Client permanently deleted');
      setDeleteOpen(false);
      await fetchPendingPayments(searchQuery, bucket);
    } catch (error) {
      if (error?.message === 'step_up_cancelled') return;
      toast.error(errMessage(error));
    }
  };

  const runRetryProvisioning = async (jobId, clientId) => {
    if (!jobId) return;
    setRowBusy(clientId);
    try {
      await adminAPI.retryProvisioningJob(jobId);
      toast.success('Provisioning retry triggered');
      await fetchPendingPayments(searchQuery, bucket);
    } catch (error) {
      toast.error(errMessage(error));
    } finally {
      setRowBusy(null);
    }
  };

  const runResendSetup = async (clientId) => {
    setRowBusy(clientId);
    try {
      await stepUp.request((headers) => adminAPI.resendPasswordSetup(clientId, { headers }));
      toast.success('Setup email sent (or link regenerated)');
      await fetchPendingPayments(searchQuery, bucket);
    } catch (error) {
      if (error?.message === 'step_up_cancelled') return;
      toast.error(errMessage(error));
    } finally {
      setRowBusy(null);
    }
  };

  const formatDate = (d) => {
    if (d == null) return '—';
    try {
      const dt = typeof d === 'string' ? new Date(d) : d;
      if (Number.isNaN(dt.getTime())) return '—';
      return dt.toLocaleDateString(undefined, { dateStyle: 'short', timeStyle: 'short' });
    } catch {
      return '—';
    }
  };

  return (
    <div className={embedded ? '' : 'p-6 max-w-[1600px] mx-auto'}>
      <Card>
        <CardHeader>
          <CardTitle>Pending setup &amp; payment recovery</CardTitle>
          <CardDescription>
            Intake clients who have not completed payment or provisioning. Enterprise lifecycle (archive / purge) is separate from
            payment funnel status. Destructive actions require password confirmation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={bucket} onValueChange={setBucket} className="mb-4">
            <TabsList className="flex flex-wrap h-auto gap-1 p-1">
              {BUCKETS.map((t) => (
                <TabsTrigger key={t.id} value={t.id} className="text-xs sm:text-sm">
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <div className="flex flex-wrap items-center gap-4 mb-4">
            <div className="relative flex-1 min-w-[200px] max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by CRN, email, or name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-3 py-2 w-full border rounded-md text-sm"
              />
            </div>
            <Button onClick={() => fetchPendingPayments(searchQuery, bucket)} variant="outline" disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh
            </Button>
          </div>

          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : items.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">No rows for this view.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 font-medium">CRN</th>
                    <th className="text-left py-2 font-medium">Name</th>
                    <th className="text-left py-2 font-medium">Email</th>
                    <th className="text-left py-2 font-medium">Created</th>
                    <th className="text-left py-2 font-medium">Link sent</th>
                    <th className="text-left py-2 font-medium">Enterprise lifecycle</th>
                    <th className="text-left py-2 font-medium">Payment lifecycle</th>
                    <th className="text-left py-2 font-medium">Provisioning</th>
                    <th className="text-left py-2 font-medium">Billing</th>
                    <th className="text-left py-2 font-medium">Flags</th>
                    <th className="text-left py-2 font-medium">Archive reason</th>
                    <th className="text-left py-2 font-medium">Checkout</th>
                    <th className="text-left py-2 font-medium w-[200px]">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(items || []).map((item, index) => {
                    const busy = rowBusy === item.client_id;
                    const derived = item.derived_client_lifecycle_status || '—';
                    const payLc = item.lifecycle_status || 'pending_payment';
                    const prov = item.provisioning_state || {};
                    const bill = item.billing_state || {};
                    const canResendSetup = (item.onboarding_status || '') === 'PROVISIONED';
                    return (
                      <tr key={item.client_id || `row-${index}`} className="border-b hover:bg-muted/50">
                        <td className="py-2 whitespace-nowrap">{item.customer_reference || '—'}</td>
                        <td className="py-2 max-w-[140px] truncate" title={item.full_name}>
                          {item.full_name || '—'}
                        </td>
                        <td className="py-2 max-w-[160px] truncate" title={item.email}>
                          {item.email || '—'}
                        </td>
                        <td className="py-2 whitespace-nowrap text-xs">{formatDate(item.created_at)}</td>
                        <td className="py-2 whitespace-nowrap text-xs">{formatDate(item.checkout_link_sent_at)}</td>
                        <td className="py-2">
                          <span
                            className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${enterpriseLifecycleClass(derived)}`}
                          >
                            {derived}
                          </span>
                          {item.client_lifecycle_status ? (
                            <span className="block text-[10px] text-muted-foreground mt-0.5">
                              stored: {item.client_lifecycle_status}
                            </span>
                          ) : null}
                        </td>
                        <td className="py-2">
                          <span className={`inline-flex px-2 py-0.5 rounded text-xs ${paymentLifecycleClass(payLc)}`}>
                            {payLc}
                          </span>
                        </td>
                        <td className="py-2 whitespace-nowrap text-xs">
                          {prov.job_status || '—'}
                          {prov.job_id ? (
                            <span className="block text-muted-foreground font-mono truncate max-w-[120px]" title={prov.job_id}>
                              {prov.job_id.slice(0, 12)}…
                            </span>
                          ) : null}
                        </td>
                        <td className="py-2 text-xs whitespace-nowrap">
                          {bill.stripe_customer_id ? 'Cust' : '—'} / {bill.stripe_subscription_id ? 'Sub' : '—'}
                        </td>
                        <td className="py-2">
                          <div className="flex flex-wrap gap-1">
                            {item.is_test_like ? (
                              <Badge variant="secondary" className="text-[10px]">
                                Test-like
                              </Badge>
                            ) : null}
                            {item.purge_eligible ? (
                              <Badge variant="outline" className="text-[10px] border-amber-600 text-amber-800">
                                Purge
                              </Badge>
                            ) : null}
                            {!item.is_test_like && !item.purge_eligible ? (
                              <span className="text-muted-foreground">—</span>
                            ) : null}
                          </div>
                        </td>
                        <td className="py-2 max-w-[140px] text-xs text-muted-foreground truncate" title={item.archive_reason || ''}>
                          {item.archive_reason || '—'}
                        </td>
                        <td className="py-2">
                          {item.last_checkout_error_code ? (
                            <span
                              className="inline-flex items-center gap-1 text-amber-600"
                              title={item.last_checkout_error_message}
                            >
                              <AlertCircle className="h-3 w-3 shrink-0" />
                              {item.last_checkout_error_code}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="py-2">
                          <div className="flex flex-wrap gap-1 items-center">
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-8 px-2"
                              onClick={() => handleSendPaymentLink(item.client_id)}
                              disabled={sending === item.client_id || !item.client_id}
                            >
                              {sending === item.client_id ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <Send className="h-3 w-3" />
                              )}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-8 px-2"
                              onClick={() => handleCopyLink(item)}
                              disabled={!item.latest_checkout_url}
                              title="Copy payment link"
                            >
                              <Copy className="h-3 w-3" />
                            </Button>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button size="sm" variant="secondary" className="h-8 px-2" disabled={busy || !item.client_id}>
                                  {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <MoreHorizontal className="h-3 w-3" />}
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-56">
                                {!isEnterpriseArchived(item) ? (
                                  <DropdownMenuItem onClick={() => openArchive(item)}>Archive client…</DropdownMenuItem>
                                ) : (
                                  <DropdownMenuItem onClick={() => runRestore(item.client_id)}>Restore client</DropdownMenuItem>
                                )}
                                {(item.client_lifecycle_status || '').toUpperCase() === 'ARCHIVED' ? (
                                  <DropdownMenuItem onClick={() => runMarkPurge(item.client_id)}>
                                    Mark purge eligible
                                  </DropdownMenuItem>
                                ) : null}
                                {!item.is_test_like ? (
                                  <DropdownMenuItem onClick={() => runFlagTestLike(item.client_id)}>Flag test-like</DropdownMenuItem>
                                ) : null}
                                <DropdownMenuSeparator />
                                {prov.job_id ? (
                                  <DropdownMenuItem onClick={() => runRetryProvisioning(prov.job_id, item.client_id)}>
                                    Retry provisioning job
                                  </DropdownMenuItem>
                                ) : null}
                                <DropdownMenuItem
                                  disabled={!canResendSetup}
                                  title={
                                    canResendSetup
                                      ? 'Resend password setup email'
                                      : 'Only after provisioning completes (PROVISIONED)'
                                  }
                                  onClick={() => canResendSetup && runResendSetup(item.client_id)}
                                >
                                  Resend setup email
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  className="text-destructive focus:text-destructive"
                                  onClick={() => openPermanentDelete(item)}
                                >
                                  Permanent delete…
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={archiveOpen} onOpenChange={setArchiveOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Archive client</DialogTitle>
            <DialogDescription>
              Removes the organisation from default active lists and blocks portal access until restored. Choose a reason for the audit log.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <label className="text-sm font-medium">Reason</label>
            <select
              className="w-full border rounded-md px-3 py-2 text-sm"
              value={archiveReasonKey}
              onChange={(e) => setArchiveReasonKey(e.target.value)}
            >
              {ARCHIVE_REASONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
            <label className="text-sm font-medium">Notes (optional)</label>
            <textarea
              className="w-full border rounded-md px-3 py-2 text-sm min-h-[72px]"
              value={archiveNotes}
              onChange={(e) => setArchiveNotes(e.target.value)}
              placeholder="Extra context for compliance / support…"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setArchiveOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitArchive}>Archive</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Permanent delete</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="text-sm text-muted-foreground space-y-2">
                <p>
                  This removes the client document from the database. Allowed only when billing, subscriptions, properties, and other
                  dependencies are clear.
                </p>
                {deleteCheckLoading ? (
                  <p className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" /> Checking dependencies…
                  </p>
                ) : deleteCheck.allowed ? (
                  <p className="text-destructive font-medium">This action cannot be undone.</p>
                ) : (
                  <div>
                    <p className="font-medium text-foreground">Delete blocked:</p>
                    <ul className="list-disc pl-5 text-foreground">
                      {deleteCheck.blockers.map((b) => (
                        <li key={b} className="font-mono text-xs">
                          {b}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleteCheckLoading || !deleteCheck.allowed}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault();
                confirmPermanentDelete();
              }}
            >
              Delete permanently
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {stepUp.modal}
    </div>
  );
};

export default AdminPendingPaymentsPage;
