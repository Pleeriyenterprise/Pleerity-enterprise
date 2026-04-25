import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import api from '../../api/client';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Alert, AlertDescription, AlertTitle } from '../../components/ui/alert';
import { toast } from '@/utils/portalNotifications';
import { Info, RefreshCw, Download, ChevronRight } from 'lucide-react';

export default function AdminTenantDeliveryCompliancePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const clientId = searchParams.get('client_id') || '';
  const propertyId = searchParams.get('property_id') || '';

  const [clientInput, setClientInput] = useState(clientId);
  const [propertyInput, setPropertyInput] = useState(propertyId);
  const [deliveries, setDeliveries] = useState([]);
  const [packs, setPacks] = useState([]);
  const [notice, setNotice] = useState('');
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  const syncInputsFromUrl = useCallback(() => {
    setClientInput(searchParams.get('client_id') || '');
    setPropertyInput(searchParams.get('property_id') || '');
  }, [searchParams]);

  useEffect(() => {
    syncInputsFromUrl();
  }, [syncInputsFromUrl]);

  const applyFilters = () => {
    const next = new URLSearchParams();
    if (clientInput.trim()) next.set('client_id', clientInput.trim());
    if (propertyInput.trim()) next.set('property_id', propertyInput.trim());
    setSearchParams(next);
  };

  const loadLists = useCallback(async () => {
    if (!clientId.trim()) {
      setDeliveries([]);
      setPacks([]);
      setNotice('');
      return;
    }
    setLoading(true);
    try {
      const params = { client_id: clientId.trim() };
      if (propertyId.trim()) params.property_id = propertyId.trim();
      const [dRes, pRes] = await Promise.all([
        api.get('/admin/compliance/tenant-deliveries', { params }),
        api.get('/admin/compliance/audit-packs', { params }),
      ]);
      setDeliveries(dRes.data.items || []);
      setNotice(dRes.data.provider_evidence_notice || '');
      setPacks(pRes.data.items || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load');
      setDeliveries([]);
      setPacks([]);
    } finally {
      setLoading(false);
    }
  }, [clientId, propertyId]);

  useEffect(() => {
    loadLists();
  }, [loadLists]);

  const loadDetail = async (deliveryId) => {
    if (!clientId.trim()) return;
    try {
      const res = await api.get(`/admin/compliance/tenant-deliveries/${deliveryId}`, {
        params: { client_id: clientId.trim() },
      });
      setDetail(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load detail');
    }
  };

  const downloadPack = async (packId) => {
    if (!clientId.trim()) return;
    try {
      const res = await api.get(`/admin/compliance/audit-packs/${packId}/download`, {
        params: { client_id: clientId.trim() },
        responseType: 'blob',
      });
      const blob = new Blob([res.data], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${packId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Download started');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Download failed');
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Tenant delivery & audit packs</h1>
          <p className="text-sm text-slate-600">Inspect governed tenant email deliveries and audit ZIP exports by client.</p>
        </div>
        <Button variant="outline" asChild>
          <Link to="/admin/dashboard">Back to dashboard</Link>
        </Button>
      </div>

      <Alert className="border-amber-200 bg-amber-50">
        <Info className="h-4 w-4" />
        <AlertTitle>Email proof is provider evidence</AlertTitle>
        <AlertDescription>
          {notice ||
            'Delivery, open, and bounce events are recorded when the email provider reports them. This is not registered-mail or standalone proof that the tenant received the message.'}
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
          <CardDescription>client_id is required; property_id narrows lists.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-4 items-end">
          <div className="min-w-[220px] flex-1">
            <Label>Client ID</Label>
            <Input className="mt-1 font-mono text-sm" value={clientInput} onChange={(e) => setClientInput(e.target.value)} placeholder="e.g. cli_…" />
          </div>
          <div className="min-w-[220px] flex-1">
            <Label>Property ID (optional)</Label>
            <Input className="mt-1 font-mono text-sm" value={propertyInput} onChange={(e) => setPropertyInput(e.target.value)} />
          </div>
          <Button onClick={applyFilters}>Apply</Button>
          <Button variant="outline" onClick={loadLists} disabled={loading || !clientId.trim()}>
            <RefreshCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Tenant deliveries</CardTitle>
          </CardHeader>
          <CardContent>
            {!clientId.trim() ? (
              <p className="text-sm text-slate-600">Enter a client ID and apply filters.</p>
            ) : loading ? (
              <p className="text-sm text-slate-600">Loading…</p>
            ) : deliveries.length === 0 ? (
              <p className="text-sm text-slate-600">No rows.</p>
            ) : (
              <ul className="space-y-2">
                {deliveries.map((d) => (
                  <li key={d.delivery_id}>
                    <button
                      type="button"
                      className="w-full text-left flex items-center justify-between gap-2 rounded border border-slate-200 px-3 py-2 hover:bg-slate-50 text-sm"
                      onClick={() => loadDetail(d.delivery_id)}
                    >
                      <span className="font-mono text-xs">{d.delivery_id}</span>
                      <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Delivery detail</CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-3">
            {!detail ? (
              <p className="text-slate-600">Select a delivery from the list.</p>
            ) : (
              <>
                <div>
                  <span className="text-slate-500">Tenant</span>
                  <p>{detail.tenant?.full_name || detail.tenant?.portal_user_id || '—'}</p>
                </div>
                <div>
                  <span className="text-slate-500">Requirements</span>
                  <ul className="list-disc pl-5 mt-1">
                    {(detail.requirements || []).map((r) => (
                      <li key={r.requirement_id}>
                        {r.title || r.requirement_type} — <span className="font-mono">{r.tenant_delivery_proof_status || '—'}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <span className="text-slate-500">Provider message ID</span>
                  <p className="font-mono text-xs break-all">{detail.delivery?.provider_message_id || detail.message_log?.provider_message_id || '—'}</p>
                </div>
                <div>
                  <span className="text-slate-500">Audit IDs</span>
                  <p className="font-mono text-xs break-all">{(detail.delivery?.audit_log_ids || []).join(', ') || '—'}</p>
                </div>
                <div>
                  <span className="text-slate-500">Message log status</span>
                  <p className="font-mono">{detail.message_log?.status || '—'}</p>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Audit packs</CardTitle>
        </CardHeader>
        <CardContent>
          {!clientId.trim() ? (
            <p className="text-sm text-slate-600">Enter a client ID.</p>
          ) : packs.length === 0 ? (
            <p className="text-sm text-slate-600">No audit packs.</p>
          ) : (
            <ul className="space-y-2">
              {packs.map((p) => (
                <li key={p.pack_id} className="flex items-center justify-between gap-2 border border-slate-100 rounded px-3 py-2">
                  <div>
                    <div className="font-mono text-xs">{p.pack_id}</div>
                    <div className="text-xs text-slate-500">{p.generated_at?.slice(0, 19)} · {p.property_id}</div>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => downloadPack(p.pack_id)}>
                    <Download className="h-4 w-4 mr-1" />
                    ZIP
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
