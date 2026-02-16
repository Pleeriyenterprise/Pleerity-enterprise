/**
 * Notification Health Dashboard – delivery logs and failure monitoring (read-only).
 * Uses GET /api/admin/message-logs and GET /api/admin/message-logs/{message_id}.
 */
import React, { useState, useEffect, useCallback } from 'react';
import api from '../api/client';
import { toast } from 'sonner';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '../components/ui/sheet';
import {
  Mail,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ShieldAlert,
  Activity,
  RefreshCw,
  Search,
  Filter,
  Eye,
  Calendar,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { cn } from '../lib/utils';

// Failure spike detector: show warning if failed >= X in last 15m or failure rate > Y% in last 1h
const FAILURE_SPIKE_COUNT = 10;
const FAILURE_SPIKE_RATE_PCT = 50;

const DEFAULT_HOURS = 24;
const PAGE_SIZE = 20;

function toISO(d) {
  if (!d) return undefined;
  if (typeof d.toISOString === 'function') return d.toISOString();
  return d;
}

function last24h() {
  const to = new Date();
  const from = new Date(to.getTime() - DEFAULT_HOURS * 60 * 60 * 1000);
  return { from: toISO(from), to: toISO(to) };
}

function defaultDateInputs() {
  const { from, to } = last24h();
  return {
    from: from ? from.slice(0, 16) : '',
    to: to ? to.slice(0, 16) : '',
  };
}

function last15m() {
  const to = new Date();
  const from = new Date(to.getTime() - 15 * 60 * 1000);
  return { from: toISO(from), to: toISO(to) };
}

function last1h() {
  const to = new Date();
  const from = new Date(to.getTime() - 60 * 60 * 1000);
  return { from: toISO(from), to: toISO(to) };
}

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'SENT', label: 'SENT' },
  { value: 'FAILED', label: 'FAILED' },
  { value: 'PENDING', label: 'PENDING' },
  { value: 'DELIVERED', label: 'DELIVERED' },
  { value: 'BOUNCED', label: 'BOUNCED' },
  { value: 'BLOCKED', label: 'Blocked (any BLOCKED_*)' },
];

const CHANNEL_OPTIONS = [
  { value: '', label: 'All channels' },
  { value: 'EMAIL', label: 'EMAIL' },
  { value: 'SMS', label: 'SMS' },
];

const statusBadgeClass = (status) => {
  if (!status) return 'bg-gray-100 text-gray-800';
  if (status === 'SENT' || status === 'DELIVERED') return 'bg-green-100 text-green-800';
  if (status === 'FAILED' || status === 'BOUNCED') return 'bg-red-100 text-red-800';
  if (String(status).startsWith('BLOCKED_')) return 'bg-amber-100 text-amber-800';
  if (status === 'PENDING') return 'bg-blue-100 text-blue-800';
  return 'bg-gray-100 text-gray-800';
};

const AdminNotificationHealthPage = () => {
  const [unauthorized, setUnauthorized] = useState(false);
  const [loading, setLoading] = useState(true);
  const [kpis, setKpis] = useState({ sent24: 0, failed24: 0, blocked24: 0, deliveryEvents24: 0 });
  const [spikeWarning, setSpikeWarning] = useState(null);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [detailLog, setDetailLog] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);

  const defaultRange = defaultDateInputs();
  const [dateFrom, setDateFrom] = useState(defaultRange.from);
  const [dateTo, setDateTo] = useState(defaultRange.to);
  const [statusFilter, setStatusFilter] = useState('');
  const [channelFilter, setChannelFilter] = useState('');
  const [templateKeyFilter, setTemplateKeyFilter] = useState('');
  const [clientIdFilter, setClientIdFilter] = useState('');
  const [recipientFilter, setRecipientFilter] = useState('');

  const buildParams = useCallback((overrides = {}) => {
    const from = overrides.from ?? dateFrom;
    const to = overrides.to ?? dateTo;
    const params = {
      limit: overrides.limit ?? PAGE_SIZE,
      offset: overrides.offset ?? offset,
    };
    if (from) params.from = new Date(from).toISOString();
    if (to) params.to = new Date(to).toISOString();
    if (overrides.status !== undefined) {
      if (overrides.status === 'BLOCKED') params.status_prefix = 'BLOCKED';
      else if (overrides.status) params.status = overrides.status;
    } else {
      if (statusFilter === 'BLOCKED') params.status_prefix = 'BLOCKED';
      else if (statusFilter) params.status = statusFilter;
    }
    if (overrides.channel !== undefined) { if (overrides.channel) params.channel = overrides.channel; }
    else if (channelFilter) params.channel = channelFilter;
    if (overrides.template_key !== undefined) { if (overrides.template_key) params.template_key = overrides.template_key; }
    else if (templateKeyFilter) params.template_key = templateKeyFilter;
    if (overrides.client_id !== undefined) { if (overrides.client_id) params.client_id = overrides.client_id; }
    else if (clientIdFilter) params.client_id = clientIdFilter;
    if (overrides.recipient !== undefined) { if (overrides.recipient) params.recipient = overrides.recipient; }
    else if (recipientFilter) params.recipient = recipientFilter;
    return params;
  }, [dateFrom, dateTo, statusFilter, channelFilter, templateKeyFilter, clientIdFilter, recipientFilter, offset]);

  const fetchKpis = useCallback(async () => {
    const { from, to } = last24h();
    if (!from || !to) return;
    const base = { from, to, limit: 1, offset: 0 };
    try {
      const [sentRes, failedRes, blockedRes, deliveryRes] = await Promise.all([
        api.get('/admin/message-logs', { params: { ...base, status: 'SENT' } }),
        api.get('/admin/message-logs', { params: { ...base, status: 'FAILED' } }),
        api.get('/admin/message-logs', { params: { ...base, status_prefix: 'BLOCKED' } }),
        api.get('/admin/message-logs', { params: { ...base, status: 'DELIVERED,BOUNCED' } }),
      ]);
      setKpis({
        sent24: sentRes.data?.total ?? 0,
        failed24: failedRes.data?.total ?? 0,
        blocked24: blockedRes.data?.total ?? 0,
        deliveryEvents24: deliveryRes.data?.total ?? 0,
      });
    } catch (e) {
      if (e.response?.status === 401 || e.response?.status === 403) {
        setUnauthorized(true);
        return;
      }
      setKpis({ sent24: 0, failed24: 0, blocked24: 0, deliveryEvents24: 0 });
    }
  }, []);

  const fetchSpike = useCallback(async () => {
    const m15 = last15m();
    const h1 = last1h();
    try {
      const [failed15Res, failed1hRes, total1hRes] = await Promise.all([
        api.get('/admin/message-logs', { params: { ...m15, status: 'FAILED', limit: 1, offset: 0 } }),
        api.get('/admin/message-logs', { params: { ...h1, status: 'FAILED', limit: 1, offset: 0 } }),
        api.get('/admin/message-logs', { params: { ...h1, limit: 1, offset: 0 } }),
      ]);
      const failed15 = failed15Res.data?.total ?? 0;
      const failed1h = failed1hRes.data?.total ?? 0;
      const total1h = total1hRes.data?.total ?? 0;
      const ratePct = total1h > 0 ? (failed1h / total1h) * 100 : 0;
      if (failed15 >= FAILURE_SPIKE_COUNT) {
        setSpikeWarning(`High failure count: ${failed15} failed in the last 15 minutes.`);
      } else if (ratePct > FAILURE_SPIKE_RATE_PCT) {
        setSpikeWarning(`High failure rate: ${ratePct.toFixed(1)}% in the last hour (${failed1h}/${total1h}).`);
      } else {
        setSpikeWarning(null);
      }
    } catch {
      setSpikeWarning(null);
    }
  }, []);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const params = buildParams();
      const res = await api.get('/admin/message-logs', { params });
      setItems(res.data?.items ?? []);
      setTotal(res.data?.total ?? 0);
      if (res.data?.total === 0 && (res.response?.status === 401 || res.response?.status === 403)) {
        setUnauthorized(true);
      }
    } catch (e) {
      if (e.response?.status === 401 || e.response?.status === 403) {
        setUnauthorized(true);
      } else {
        toast.error('Failed to load message logs');
      }
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  useEffect(() => {
    if (unauthorized) return;
    fetchKpis();
    fetchSpike();
  }, [fetchKpis, fetchSpike, unauthorized]);

  useEffect(() => {
    if (unauthorized) return;
    fetchList();
  }, [fetchList, unauthorized]);

  const openDetail = async (messageId) => {
    setDetailOpen(true);
    setDetailLog(null);
    setDetailLoading(true);
    try {
      const res = await api.get(`/admin/message-logs/${encodeURIComponent(messageId)}`);
      const log = res.data;
      for (const k of ['created_at', 'sent_at', 'delivered_at', 'bounced_at', 'opened_at']) {
        if (log[k] && typeof log[k] === 'string' && log[k].length > 24) {
          // already ISO string
        } else if (log[k] && typeof log[k]?.isoformat === 'function') {
          log[k] = log[k].isoformat();
        }
      }
      setDetailLog(log);
    } catch (e) {
      if (e.response?.status === 401 || e.response?.status === 403) setUnauthorized(true);
      else toast.error('Failed to load message details');
      setDetailLog(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const applyFilters = () => {
    setOffset(0);
  };

  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  if (unauthorized) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6 flex flex-col items-center justify-center min-h-[40vh]">
          <ShieldAlert className="w-12 h-12 text-amber-500 mb-4" />
          <h2 className="text-xl font-semibold text-gray-800">Not authorized</h2>
          <p className="text-gray-500 mt-1">You do not have permission to view the Notification Health dashboard.</p>
        </div>
      </UnifiedAdminLayout>
    );
  }

  return (
    <UnifiedAdminLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-gray-900">Notification Health</h1>
          <Button variant="outline" size="sm" onClick={() => { fetchKpis(); fetchSpike(); fetchList(); }}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>

        {spikeWarning && (
          <div className="flex items-center gap-3 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-amber-800" role="alert">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <span>{spikeWarning}</span>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2 text-gray-500 text-sm">
              <CheckCircle className="w-4 h-4" />
              Sent (last 24h)
            </div>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{kpis.sent24}</p>
          </div>
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2 text-gray-500 text-sm">
              <XCircle className="w-4 h-4" />
              Failed (last 24h)
            </div>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{kpis.failed24}</p>
          </div>
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2 text-gray-500 text-sm">
              <ShieldAlert className="w-4 h-4" />
              Blocked (last 24h)
            </div>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{kpis.blocked24}</p>
          </div>
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2 text-gray-500 text-sm">
              <Activity className="w-4 h-4" />
              Delivery events (last 24h)
            </div>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{kpis.deliveryEvents24}</p>
          </div>
        </div>

        <div className="rounded-lg border bg-white shadow-sm">
          <div className="p-4 border-b flex flex-wrap items-end gap-4">
            <div className="flex items-center gap-2">
              <Label className="text-sm whitespace-nowrap">From</Label>
              <Input
                type="datetime-local"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-44"
              />
            </div>
            <div className="flex items-center gap-2">
              <Label className="text-sm whitespace-nowrap">To</Label>
              <Input
                type="datetime-local"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-44"
              />
            </div>
            <Select value={statusFilter || 'all'} onValueChange={(v) => setStatusFilter(v === 'all' ? '' : v)}>
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((o) => (
                  <SelectItem key={o.value || 'all'} value={o.value || 'all'}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={channelFilter || 'all'} onValueChange={(v) => setChannelFilter(v === 'all' ? '' : v)}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Channel" />
              </SelectTrigger>
              <SelectContent>
                {CHANNEL_OPTIONS.map((o) => (
                  <SelectItem key={o.value || 'all'} value={o.value || 'all'}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              placeholder="Template key"
              value={templateKeyFilter}
              onChange={(e) => setTemplateKeyFilter(e.target.value)}
              className="w-40"
            />
            <Input
              placeholder="Client ID"
              value={clientIdFilter}
              onChange={(e) => setClientIdFilter(e.target.value)}
              className="w-36"
            />
            <Input
              placeholder="Recipient search"
              value={recipientFilter}
              onChange={(e) => setRecipientFilter(e.target.value)}
              className="w-40"
            />
            <Button onClick={applyFilters}>
              <Filter className="w-4 h-4 mr-2" />
              Apply
            </Button>
          </div>

          <div className="overflow-x-auto">
            {loading ? (
              <div className="flex justify-center py-12">
                <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="text-left px-4 py-3 font-medium text-gray-700">created_at</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-700">client_id</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-700">channel</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-700">template_key</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-700">recipient</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-700">status</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-700">attempt_count</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-700">provider_message_id</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-700">error_message</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-700 w-24">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr key={row.message_id} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-2 text-gray-600">{row.created_at ? String(row.created_at).slice(0, 19) : '—'}</td>
                      <td className="px-4 py-2">
                        <button
                          type="button"
                          onClick={() => { setClientIdFilter(row.client_id || ''); applyFilters(); }}
                          className="text-electric-teal hover:underline font-mono text-xs"
                        >
                          {row.client_id || '—'}
                        </button>
                      </td>
                      <td className="px-4 py-2">{row.channel || '—'}</td>
                      <td className="px-4 py-2 font-mono text-xs">{row.template_key || '—'}</td>
                      <td className="px-4 py-2 text-gray-600 max-w-[140px] truncate" title={row.recipient || ''}>{row.recipient || '—'}</td>
                      <td className="px-4 py-2">
                        <Badge className={cn('font-normal', statusBadgeClass(row.status))}>{row.status || '—'}</Badge>
                      </td>
                      <td className="px-4 py-2">{row.attempt_count ?? '—'}</td>
                      <td className="px-4 py-2 font-mono text-xs max-w-[120px] truncate" title={row.provider_message_id || row.postmark_message_id || ''}>
                        {row.provider_message_id || row.postmark_message_id || '—'}
                      </td>
                      <td className="px-4 py-2 max-w-[180px]" title={row.error_message || ''}>
                        <span className="truncate block">{row.error_message ? String(row.error_message).slice(0, 40) + (row.error_message.length > 40 ? '…' : '') : '—'}</span>
                      </td>
                      <td className="px-4 py-2">
                        <Button variant="ghost" size="sm" onClick={() => openDetail(row.message_id)} title="View details">
                          <Eye className="w-4 h-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {!loading && items.length === 0 && (
              <div className="py-8 text-center text-gray-500">No message logs match the filters.</div>
            )}
          </div>

          {total > 0 && (
            <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50 text-sm text-gray-600">
              <span>
                {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => { setOffset((o) => Math.max(0, o - PAGE_SIZE)); }}
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => { setOffset((o) => o + PAGE_SIZE); }}
                >
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      <Sheet open={detailOpen} onOpenChange={setDetailOpen}>
        <SheetContent className="w-full max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Message log details</SheetTitle>
          </SheetHeader>
          {detailLoading && (
            <div className="flex justify-center py-8">
              <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
            </div>
          )}
          {!detailLoading && detailLog && (
            <div className="mt-4 space-y-4 text-sm">
              <div><span className="font-medium text-gray-500">message_id</span><p className="font-mono text-xs mt-0.5 break-all">{detailLog.message_id}</p></div>
              {detailLog.idempotency_key != null && <div><span className="font-medium text-gray-500">idempotency_key</span><p className="font-mono text-xs mt-0.5 break-all">{detailLog.idempotency_key}</p></div>}
              {detailLog.provider_message_id != null && <div><span className="font-medium text-gray-500">provider_message_id</span><p className="font-mono text-xs mt-0.5">{detailLog.provider_message_id}</p></div>}
              <div><span className="font-medium text-gray-500">Timestamps</span><ul className="mt-1 space-y-0.5 text-gray-700"><li>created_at: {detailLog.created_at ?? '—'}</li><li>sent_at: {detailLog.sent_at ?? '—'}</li><li>delivered_at: {detailLog.delivered_at ?? '—'}</li><li>bounced_at: {detailLog.bounced_at ?? '—'}</li>{detailLog.opened_at != null && <li>opened_at: {detailLog.opened_at}</li>}</ul></div>
              {detailLog.error_message && <div><span className="font-medium text-gray-500">error_message</span><pre className="mt-1 p-2 bg-gray-100 rounded text-xs whitespace-pre-wrap break-words">{detailLog.error_message}</pre></div>}
              {detailLog.metadata && <div><span className="font-medium text-gray-500">metadata</span><pre className="mt-1 p-2 bg-gray-100 rounded text-xs overflow-x-auto">{JSON.stringify(detailLog.metadata, null, 2)}</pre></div>}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </UnifiedAdminLayout>
  );
};

export default AdminNotificationHealthPage;
