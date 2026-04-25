import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import api from '../api/client';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';
import { toast } from '@/utils/portalNotifications';
import { PortalLoadingPanel, portalPageRoot } from '../components/client/ClientPortalPatterns';
import { ArrowLeft, Package, Send, Download, RefreshCw, Info } from 'lucide-react';

function statusBadge(ui) {
  if (!ui) return null;
  if (ui.failed) return <span className="text-xs font-medium text-red-700 bg-red-50 px-2 py-0.5 rounded">Failed</span>;
  if (ui.bounced) return <span className="text-xs font-medium text-amber-800 bg-amber-50 px-2 py-0.5 rounded">Bounced</span>;
  if (ui.acknowledged) return <span className="text-xs font-medium text-teal-800 bg-teal-50 px-2 py-0.5 rounded">Acknowledged</span>;
  if (ui.opened) return <span className="text-xs font-medium text-blue-800 bg-blue-50 px-2 py-0.5 rounded">Opened (provider)</span>;
  if (ui.delivered) return <span className="text-xs font-medium text-green-800 bg-green-50 px-2 py-0.5 rounded">Delivered (provider)</span>;
  if (ui.sent) return <span className="text-xs font-medium text-slate-700 bg-slate-100 px-2 py-0.5 rounded">Sent (provider accepted)</span>;
  if (ui.initiated) return <span className="text-xs font-medium text-slate-600 bg-slate-50 px-2 py-0.5 rounded">Initiated</span>;
  return null;
}

export default function ClientTenantComplianceDeliveryPage() {
  const { hasFeature, entitlementsLoadFailed } = useEntitlements();
  const navHasFeature = (k) => entitlementsLoadFailed || hasFeature(k);
  const [searchParams, setSearchParams] = useSearchParams();
  const propertyId = searchParams.get('property_id') || '';

  const [properties, setProperties] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [deliveries, setDeliveries] = useState([]);
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [generatingPack, setGeneratingPack] = useState(false);
  const [tenantId, setTenantId] = useState('');

  const canUse = navHasFeature('tenant_portal') && navHasFeature('reports_pdf');

  const load = useCallback(async () => {
    if (!canUse) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [pRes, tRes] = await Promise.all([api.get('/client/properties'), api.get('/client/tenants')]);
      setProperties(pRes.data.properties || []);
      setTenants(tRes.data.tenants || []);
      if (propertyId) {
        const dRes = await api.get('/client/compliance/tenant-deliveries', { params: { property_id: propertyId } });
        setDeliveries(dRes.data.items || []);
        setNotice(dRes.data.provider_evidence_notice || '');
      } else {
        setDeliveries([]);
        setNotice('');
      }
    } catch (e) {
      toast.error(e.response?.data?.detail?.message || e.response?.data?.detail || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [canUse, propertyId]);

  useEffect(() => {
    load();
  }, [load]);

  const tenantsForProperty = useMemo(() => {
    if (!propertyId) return [];
    return (tenants || []).filter((t) => (t.property_ids || []).includes(propertyId));
  }, [tenants, propertyId]);

  const onPropertyChange = (pid) => {
    const next = new URLSearchParams(searchParams);
    if (pid) next.set('property_id', pid);
    else next.delete('property_id');
    setSearchParams(next);
    setTenantId('');
  };

  const sendPack = async () => {
    if (!propertyId || !tenantId) {
      toast.error('Select a property and tenant');
      return;
    }
    setSending(true);
    try {
      await api.post('/client/compliance/tenant-delivery', {
        property_id: propertyId,
        tenant_portal_user_id: tenantId,
      });
      toast.success('Compliance pack sent');
      await load();
    } catch (e) {
      const d = e.response?.data?.detail;
      toast.error(typeof d === 'object' ? d?.message || JSON.stringify(d) : d || 'Send failed');
    } finally {
      setSending(false);
    }
  };

  const generateAuditPack = async () => {
    if (!propertyId) {
      toast.error('Select a property first');
      return;
    }
    setGeneratingPack(true);
    try {
      const gen = await api.post('/client/compliance/audit-pack/generate', { property_id: propertyId });
      const packId = gen.data.pack_id;
      const res = await api.get(`/client/compliance/audit-pack/${packId}/download`, { responseType: 'blob' });
      const blob = new Blob([res.data], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${packId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Audit pack downloaded');
    } catch (e) {
      toast.error(e.response?.data?.detail?.message || e.response?.data?.detail || 'Audit pack failed');
    } finally {
      setGeneratingPack(false);
    }
  };

  if (!canUse) {
    return (
      <div className={portalPageRoot}>
        <Card>
          <CardHeader>
            <CardTitle>Tenant delivery & audit pack</CardTitle>
            <CardDescription>Requires tenant portal and PDF reports on your plan.</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className={portalPageRoot}>
      <div className="mb-6 flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/tenants">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Tenants
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Tenant delivery & audit pack</h1>
          <p className="text-sm text-slate-600">Send the governed compliance PDF to a tenant and export a single audit-ready ZIP for a property.</p>
        </div>
      </div>

      {notice && (
        <Alert className="mb-4 border-amber-200 bg-amber-50">
          <Info className="h-4 w-4" />
          <AlertTitle>Provider evidence only</AlertTitle>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Send className="h-5 w-5 text-electric-teal" />
              Send compliance pack
            </CardTitle>
            <CardDescription>Uses governed email delivery with immutable delivery records.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Property</Label>
              <Select value={propertyId || undefined} onValueChange={onPropertyChange}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Select property" />
                </SelectTrigger>
                <SelectContent>
                  {(properties || []).map((p) => (
                    <SelectItem key={p.property_id} value={p.property_id}>
                      {[p.address_line_1, p.postcode].filter(Boolean).join(', ') || p.property_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Tenant</Label>
              <Select value={tenantId || undefined} onValueChange={setTenantId} disabled={!propertyId}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder={propertyId ? 'Select tenant' : 'Select a property first'} />
                </SelectTrigger>
                <SelectContent>
                  {tenantsForProperty.map((t) => (
                    <SelectItem key={t.portal_user_id} value={t.portal_user_id}>
                      {t.full_name || t.email || t.portal_user_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={sendPack} disabled={sending || !propertyId || !tenantId} className="w-full sm:w-auto">
              {sending ? 'Sending…' : 'Send pack'}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5 text-electric-teal" />
              Governed audit pack
            </CardTitle>
            <CardDescription>One ZIP: summary PDF, authority-filtered certificates, timeline, delivery index, manifest + checksums.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={generateAuditPack} disabled={generatingPack || !propertyId} variant="secondary">
              {generatingPack ? 'Building…' : (
                <>
                  <Download className="h-4 w-4 mr-2" />
                  Generate & download
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Delivery history</CardTitle>
            <CardDescription>Filtered by selected property.</CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={load} disabled={loading || !propertyId}>
            <RefreshCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <PortalLoadingPanel />
          ) : !propertyId ? (
            <p className="text-sm text-slate-600">Select a property to view delivery history.</p>
          ) : deliveries.length === 0 ? (
            <p className="text-sm text-slate-600">No deliveries yet for this property.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-slate-500">
                    <th className="py-2 pr-4">When</th>
                    <th className="py-2 pr-4">Recipient</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Provider ID</th>
                  </tr>
                </thead>
                <tbody>
                  {deliveries.map((d) => (
                    <tr key={d.delivery_id} className="border-b border-slate-100">
                      <td className="py-2 pr-4 whitespace-nowrap">{d.created_at?.slice(0, 19) || '—'}</td>
                      <td className="py-2 pr-4">{d.recipient_email || '—'}</td>
                      <td className="py-2 pr-4">{statusBadge(d.ui_status)}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{d.provider_message_id || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
