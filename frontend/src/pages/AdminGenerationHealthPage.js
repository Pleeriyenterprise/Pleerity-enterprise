/**
 * Admin → Analytics → Generation health (provider reliability, runs, failed orders).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import client from '../api/client';
import ordersApi from '../api/ordersApi';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { Activity, RefreshCw } from 'lucide-react';

function formatTime(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return String(iso);
  }
}

export default function AdminGenerationHealthPage() {
  const [hours, setHours] = useState(24);
  const [health, setHealth] = useState(null);
  const [runs, setRuns] = useState([]);
  const [failedOrders, setFailedOrders] = useState([]);
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runFilters, setRunFilters] = useState({
    status: '',
    provider: '',
    service_code: '',
  });
  const [detailRun, setDetailRun] = useState(null);
  const [retryOrder, setRetryOrder] = useState(null);
  const [retryReason, setRetryReason] = useState('');
  const [retryProvider, setRetryProvider] = useState('default');
  const [retrySubmitting, setRetrySubmitting] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [h, r, f, p] = await Promise.all([
        client.get('/admin/analytics/provider-health', { params: { hours } }),
        client.get('/admin/analytics/generation-runs', {
          params: {
            limit: 50,
            status: runFilters.status || undefined,
            provider: runFilters.provider || undefined,
            service_code: runFilters.service_code || undefined,
          },
        }),
        client.get('/admin/analytics/failed-orders', { params: { limit: 50 } }),
        client.get('/admin/analytics/prompt-failure-patterns', { params: { limit: 40 } }),
      ]);
      setHealth(h.data);
      setRuns(Array.isArray(r.data) ? r.data : []);
      setFailedOrders(Array.isArray(f.data) ? f.data : []);
      setPatterns(Array.isArray(p.data) ? p.data : []);
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'Failed to load';
      toast.error(typeof msg === 'string' ? msg : 'Failed to load generation health');
    } finally {
      setLoading(false);
    }
  }, [hours, runFilters.status, runFilters.provider, runFilters.service_code]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const openaiCard = health?.providers?.find((x) => x.provider === 'openai');
  const geminiCard = health?.providers?.find((x) => x.provider === 'gemini');
  const totals = health?.totals || {};

  const submitRetry = async () => {
    if (!retryOrder) return;
    const reason = retryReason.trim();
    if (reason.length < 3) {
      toast.error('Please enter a reason (min 3 characters).');
      return;
    }
    setRetrySubmitting(true);
    try {
      const pref =
        retryOrder._pref ??
        (retryProvider === 'openai' || retryProvider === 'gemini' ? retryProvider : null);
      const res = await ordersApi.retryGeneration(retryOrder.order_id, {
        preferred_provider: pref,
        reason,
      });
      if (res?.success === false && res?.error) {
        toast.error(res.message || res.error || 'Retry failed to start');
      } else {
        toast.success('Retry queued successfully');
        if (res?.generation?.success && res?.review?.success !== false) {
          toast.success('Generation completed — check order status for INTERNAL_REVIEW');
        }
      }
      setRetryOrder(null);
      setRetryReason('');
      setRetryProvider('default');
      loadAll();
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'Retry failed to start');
    } finally {
      setRetrySubmitting(false);
    }
  };

  return (
    <UnifiedAdminLayout>
      <div className="space-y-6 p-4 max-w-[1400px] mx-auto" data-testid="admin-generation-health">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Generation health</h1>
            <p className="text-sm text-gray-500">
              Provider reliability, recent runs, failed orders, and prompt failure patterns.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-xs text-gray-500">Window (h)</Label>
            <Input
              type="number"
              min={1}
              max={336}
              className="w-20 h-9"
              value={hours}
              onChange={(e) => setHours(Number(e.target.value) || 24)}
            />
            <Button variant="outline" size="sm" onClick={() => loadAll()} disabled={loading}>
              <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">OpenAI success rate</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold">
                {openaiCard ? `${(openaiCard.success_rate * 100).toFixed(1)}%` : '—'}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Avg latency {openaiCard?.avg_latency_ms ?? 0} ms · runs {openaiCard?.total_runs ?? 0}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Gemini success rate</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold">
                {geminiCard ? `${(geminiCard.success_rate * 100).toFixed(1)}%` : '—'}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Avg latency {geminiCard?.avg_latency_ms ?? 0} ms · runs {geminiCard?.total_runs ?? 0}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Fallback successes</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold">{totals.fallback_successes ?? 0}</p>
              <p className="text-xs text-gray-500 mt-1">Completed after provider failover</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Retryable failures</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold">{totals.retryable_failures ?? 0}</p>
              <p className="text-xs text-gray-500 mt-1">
                Total runs {totals.total_runs ?? 0} · failed {totals.failed_runs ?? 0}
              </p>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Recent generation runs
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 overflow-x-auto">
            <div className="flex flex-wrap gap-2 items-end">
              <div>
                <Label className="text-xs">Status</Label>
                <Input
                  className="h-9 w-32"
                  placeholder="COMPLETED/FAILED"
                  value={runFilters.status}
                  onChange={(e) => setRunFilters((s) => ({ ...s, status: e.target.value }))}
                />
              </div>
              <div>
                <Label className="text-xs">Provider</Label>
                <Input
                  className="h-9 w-28"
                  placeholder="openai/gemini"
                  value={runFilters.provider}
                  onChange={(e) => setRunFilters((s) => ({ ...s, provider: e.target.value }))}
                />
              </div>
              <div>
                <Label className="text-xs">Service code</Label>
                <Input
                  className="h-9 w-36"
                  placeholder="e.g. MR_BASIC"
                  value={runFilters.service_code}
                  onChange={(e) => setRunFilters((s) => ({ ...s, service_code: e.target.value }))}
                />
              </div>
              <Button size="sm" variant="secondary" onClick={() => loadAll()}>
                Apply filters
              </Button>
            </div>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2 pr-2">Time</th>
                  <th className="py-2 pr-2">Order ref</th>
                  <th className="py-2 pr-2">Service</th>
                  <th className="py-2 pr-2">Doc type</th>
                  <th className="py-2 pr-2">Preferred</th>
                  <th className="py-2 pr-2">Used</th>
                  <th className="py-2 pr-2">Fallback</th>
                  <th className="py-2 pr-2">Retries</th>
                  <th className="py-2 pr-2">Status</th>
                  <th className="py-2 pr-2">Error type</th>
                  <th className="py-2"> </th>
                </tr>
              </thead>
              <tbody>
                {runs.map((row) => (
                  <tr key={row.run_id} className="border-b border-gray-100">
                    <td className="py-2 pr-2 whitespace-nowrap">{formatTime(row.created_at)}</td>
                    <td className="py-2 pr-2 font-mono text-xs">{row.order_ref || row.order_id}</td>
                    <td className="py-2 pr-2">{row.service_code || '—'}</td>
                    <td className="py-2 pr-2">{row.doc_type || '—'}</td>
                    <td className="py-2 pr-2">{row.provider_preferred || '—'}</td>
                    <td className="py-2 pr-2">{row.provider_used || '—'}</td>
                    <td className="py-2 pr-2">{row.fallback_used ? 'Yes' : 'No'}</td>
                    <td className="py-2 pr-2">{row.retry_count ?? 0}</td>
                    <td className="py-2 pr-2">
                      <Badge variant="outline">{row.status}</Badge>
                    </td>
                    <td className="py-2 pr-2 text-xs">{row.final_error_type || '—'}</td>
                    <td className="py-2">
                      <Button variant="ghost" size="sm" onClick={() => setDetailRun(row)}>
                        Details
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!runs.length && !loading && (
              <p className="text-sm text-gray-500">No runs in the current filter.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Failed orders</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2 pr-2">Order ref</th>
                  <th className="py-2 pr-2">Service</th>
                  <th className="py-2 pr-2">Summary</th>
                  <th className="py-2 pr-2">Retryable</th>
                  <th className="py-2 pr-2">Updated</th>
                  <th className="py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {failedOrders.map((o) => (
                  <tr key={o.order_id} className="border-b border-gray-100">
                    <td className="py-2 pr-2 font-mono text-xs">{o.order_ref || o.order_id}</td>
                    <td className="py-2 pr-2">{o.service_code}</td>
                    <td className="py-2 pr-2 max-w-md">
                      <span className="text-xs text-gray-600">{o.final_error_type}</span>
                      <div className="text-gray-800 line-clamp-2">{o.final_error_message_short}</div>
                      {o.automatic_retry_pending && (
                        <p className="text-xs text-amber-700 mt-1">
                          Automatic retry scheduled
                          {o.scheduled_automatic_retry_at
                            ? ` (${formatTime(o.scheduled_automatic_retry_at)})`
                            : ''}
                        </p>
                      )}
                    </td>
                    <td className="py-2 pr-2">{o.retryable ? 'Yes' : 'No'}</td>
                    <td className="py-2 pr-2 whitespace-nowrap">{formatTime(o.updated_at)}</td>
                    <td className="py-2">
                      <div className="flex flex-wrap gap-1">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setRetryOrder({ ...o, _pref: undefined });
                            setRetryProvider('default');
                            setRetryReason('');
                          }}
                        >
                          Retry
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            setRetryOrder({ ...o, _pref: 'openai' });
                            setRetryProvider('openai');
                            setRetryReason('');
                          }}
                        >
                          OpenAI
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            setRetryOrder({ ...o, _pref: 'gemini' });
                            setRetryProvider('gemini');
                            setRetryReason('');
                          }}
                        >
                          Gemini
                        </Button>
                        <Link
                          to="/admin/orders"
                          className="inline-flex items-center text-xs text-teal-700 underline px-2"
                        >
                          Orders
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!failedOrders.length && !loading && (
              <p className="text-sm text-gray-500">No failed orders in the recent window.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Prompt failure patterns</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2 pr-2">Service / doc</th>
                  <th className="py-2 pr-2">Template</th>
                  <th className="py-2 pr-2">Version</th>
                  <th className="py-2 pr-2">Failure type</th>
                  <th className="py-2 pr-2">Count</th>
                </tr>
              </thead>
              <tbody>
                {patterns.map((p, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="py-2 pr-2">
                      {p.service_code || '—'} / {p.doc_type || '—'}
                    </td>
                    <td className="py-2 pr-2 font-mono text-xs">{p.prompt_template_id || '—'}</td>
                    <td className="py-2 pr-2">{p.prompt_version_used ?? '—'}</td>
                    <td className="py-2 pr-2">{p.final_error_type}</td>
                    <td className="py-2 pr-2">{p.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!patterns.length && !loading && (
              <p className="text-sm text-gray-500">No aggregated failure patterns yet.</p>
            )}
          </CardContent>
        </Card>

        <Dialog open={!!detailRun} onOpenChange={() => setDetailRun(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Generation run</DialogTitle>
            </DialogHeader>
            {detailRun && (
              <div className="space-y-2 text-sm">
                <p>
                  <span className="text-gray-500">Run:</span> {detailRun.run_id}
                </p>
                <p>
                  <span className="text-gray-500">Order:</span> {detailRun.order_id}
                </p>
                <p>
                  <span className="text-gray-500">Status:</span> {detailRun.status}
                </p>
                <p>
                  <span className="text-gray-500">Error type (classified):</span>{' '}
                  {detailRun.final_error_type || '—'}
                </p>
                <p className="text-gray-600 text-xs">
                  Raw provider traces are not shown here by default. Use backend logs for deep diagnosis.
                </p>
              </div>
            )}
          </DialogContent>
        </Dialog>

        <Dialog open={!!retryOrder} onOpenChange={() => !retrySubmitting && setRetryOrder(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Retry generation</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <p className="text-sm text-gray-600">
                Order <span className="font-mono">{retryOrder?.order_id}</span>
              </p>
              {retryOrder?.automatic_retry_pending && (
                <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-2">
                  An automatic retry was scheduled. Submitting this manual retry cancels the pending
                  automatic run and re-queues immediately.
                </p>
              )}
              <div>
                <Label>Preferred provider (optional)</Label>
                <Select
                  value={retryProvider}
                  onValueChange={(v) => {
                    setRetryProvider(v);
                    setRetryOrder((ro) => (ro ? { ...ro, _pref: undefined } : ro));
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Default (env)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">Default (env)</SelectItem>
                    <SelectItem value="openai">OpenAI first</SelectItem>
                    <SelectItem value="gemini">Gemini first</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Reason (required)</Label>
                <Textarea
                  rows={3}
                  value={retryReason}
                  onChange={(e) => setRetryReason(e.target.value)}
                  placeholder="e.g. Manual retry after provider outage"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setRetryOrder(null)} disabled={retrySubmitting}>
                Cancel
              </Button>
              <Button onClick={submitRetry} disabled={retrySubmitting}>
                {retrySubmitting ? 'Submitting…' : 'Submit retry'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </UnifiedAdminLayout>
  );
}
