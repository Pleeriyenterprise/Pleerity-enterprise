import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { filenameFromContentDisposition } from '../api/client';
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
import { toast } from '@/utils/portalNotifications';
import { PortalLoadingPanel, portalPageRoot } from '../components/client/ClientPortalPatterns';
import { ArrowLeft, Download, Package } from 'lucide-react';
import { AUDIT_PACK_IMMUTABLE_DISCLOSURE } from '../utils/reportingSemanticsLabels';

/**
 * Property-scoped governed audit evidence ZIP (reports / compliance export — not tenant email delivery).
 */
export default function ReportsAuditPackPage() {
  const { hasFeature, entitlementsLoadFailed, loading } = useEntitlements();
  const navHasFeature = (k) => entitlementsLoadFailed || hasFeature(k);
  /** Route is gated by reports_pdf; this mirrors load behaviour if entitlements are still resolving. */
  const canUse = navHasFeature('reports_pdf');

  const [properties, setProperties] = useState([]);
  const [propertyId, setPropertyId] = useState('');
  const [loadingProps, setLoadingProps] = useState(true);
  const [generating, setGenerating] = useState(false);

  const loadProperties = useCallback(async () => {
    if (!canUse) {
      setLoadingProps(false);
      return;
    }
    setLoadingProps(true);
    try {
      const pRes = await api.get('/client/properties');
      setProperties(pRes.data.properties || []);
    } catch (e) {
      toast.error(e.response?.data?.detail?.message || e.response?.data?.detail || 'Failed to load properties');
    } finally {
      setLoadingProps(false);
    }
  }, [canUse]);

  useEffect(() => {
    loadProperties();
  }, [loadProperties]);

  const generateAuditEvidencePack = async () => {
    if (!propertyId) {
      toast.error('Select a property first');
      return;
    }
    setGenerating(true);
    try {
      const gen = await api.post('/client/compliance/audit-pack/generate', { property_id: propertyId });
      const packId = gen.data.pack_id;
      const res = await api.get(`/client/compliance/audit-pack/${packId}/download`, { responseType: 'blob' });
      const blob = new Blob([res.data], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filenameFromContentDisposition(res.headers, `${packId}.zip`);
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Audit evidence pack downloaded');
    } catch (e) {
      toast.error(e.response?.data?.detail?.message || e.response?.data?.detail || 'Failed to generate audit evidence pack');
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className={portalPageRoot} data-testid="reports-audit-pack-loading">
        <PortalLoadingPanel message="Loading…" />
      </div>
    );
  }

  return (
    <div className={portalPageRoot} data-testid="reports-audit-pack-page">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Button variant="ghost" size="sm" asChild className="w-fit">
          <Link to="/reports">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Reports
          </Link>
        </Button>
      </div>

      <h1 className="text-2xl font-semibold text-slate-900 mb-1">Audit evidence pack</h1>
      <p className="text-sm text-slate-600 mb-6 max-w-2xl">
        Download a governed ZIP for a single property: summary PDF, authority-filtered certificates, timeline, delivery
        index where applicable, manifest and checksums. For regulators, lenders, or archival evidence — not tenant email
        delivery.{' '}
        <span className="block mt-2 text-slate-700" data-testid="audit-pack-immutable-disclosure">
          {AUDIT_PACK_IMMUTABLE_DISCLOSURE}
        </span>
      </p>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="h-5 w-5 text-electric-teal" />
            Generate audit evidence pack
          </CardTitle>
          <CardDescription>Select a property, then build and download the ZIP.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loadingProps ? (
            <PortalLoadingPanel message="Loading properties…" />
          ) : (
            <>
              <div>
                <Label>Property</Label>
                <Select value={propertyId || undefined} onValueChange={setPropertyId}>
                  <SelectTrigger className="mt-1 max-w-md">
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
              <Button onClick={generateAuditEvidencePack} disabled={generating || !propertyId} className="w-full sm:w-auto">
                {generating ? 'Building…' : (
                  <>
                    <Download className="h-4 w-4 mr-2" />
                    Generate Audit Evidence Pack
                  </>
                )}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
