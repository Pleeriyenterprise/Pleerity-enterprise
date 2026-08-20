import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import api, { clientAPI, filenameFromContentDisposition } from '../api/client';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
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
import { ArrowLeft, Download, Printer } from 'lucide-react';
import { getPropertyDisplayName } from '../utils/propertyDisplayName';

/**
 * Landlord-facing Property Activity & Evidence Report.
 * Organises CVP records; does not claim legal sufficiency.
 */
export default function ReportsPropertyEvidencePage() {
  const [searchParams] = useSearchParams();
  const [properties, setProperties] = useState([]);
  const [propertyId, setPropertyId] = useState(searchParams.get('property_id') || '');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [loadingProps, setLoadingProps] = useState(true);
  const [report, setReport] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);

  const loadProperties = useCallback(async () => {
    setLoadingProps(true);
    try {
      const pRes = await api.get('/client/properties');
      setProperties(pRes.data.properties || []);
    } catch (e) {
      toast.error(e.response?.data?.detail?.message || e.response?.data?.detail || 'Failed to load properties');
    } finally {
      setLoadingProps(false);
    }
  }, []);

  useEffect(() => {
    loadProperties();
  }, [loadProperties]);

  const loadReport = async () => {
    if (!propertyId) {
      toast.error('Select a property first');
      return;
    }
    setLoadingReport(true);
    try {
      const res = await clientAPI.getPropertyActivityEvidenceReport(propertyId, {
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
      });
      setReport(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail?.message || e.response?.data?.detail || 'Failed to load report');
      setReport(null);
    } finally {
      setLoadingReport(false);
    }
  };

  const downloadHtml = async () => {
    if (!propertyId) {
      toast.error('Select a property first');
      return;
    }
    try {
      const res = await clientAPI.downloadPropertyActivityEvidenceReportHtml(propertyId, {
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
      });
      const blob = new Blob([res.data], { type: 'text/html;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filenameFromContentDisposition(res.headers, 'property-activity-evidence-report.html');
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(e.response?.data?.detail?.message || e.response?.data?.detail || 'Failed to download report');
    }
  };

  if (loadingProps) {
    return (
      <div className={portalPageRoot} data-testid="reports-property-evidence-loading">
        <PortalLoadingPanel message="Loading…" />
      </div>
    );
  }

  return (
    <div className={portalPageRoot} data-testid="reports-property-evidence-page">
      <div className="mb-6">
        <Button variant="ghost" size="sm" asChild className="w-fit">
          <Link to="/reports">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Reports
          </Link>
        </Button>
      </div>
      <h1 className="text-2xl font-semibold text-slate-900 mb-1">Property Activity &amp; Evidence Report</h1>
      <p className="text-sm text-slate-600 mb-6 max-w-2xl">
        A chronological record of what CVP stored for this property in the selected date range — occupancy,
        compliance, maintenance, rent, and contractor activity. This pack organises CVP records. It does not
        determine legal sufficiency, tribunal outcome, or regulatory approval.
      </p>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Select property and date range</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Property</Label>
            <Select value={propertyId} onValueChange={setPropertyId}>
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="Choose a property" />
              </SelectTrigger>
              <SelectContent>
                {properties.map((p) => (
                  <SelectItem key={p.property_id} value={p.property_id}>
                    {getPropertyDisplayName(p)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="evidence-from">From</Label>
              <input
                id="evidence-from"
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <Label htmlFor="evidence-to">To</Label>
              <input
                id="evidence-to"
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm"
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={loadReport} disabled={loadingReport}>
              {loadingReport ? 'Loading…' : 'View report'}
            </Button>
            <Button type="button" variant="outline" onClick={downloadHtml}>
              <Download className="h-4 w-4 mr-1" />
              Download HTML
            </Button>
            {report ? (
              <Button type="button" variant="outline" onClick={() => window.print()}>
                <Printer className="h-4 w-4 mr-1" />
                Print
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {report ? (
        <div className="space-y-6 bg-white border rounded-lg p-5" data-testid="property-evidence-report">
          <p className="text-sm border border-slate-200 bg-slate-50 rounded px-3 py-2">{report.disclaimer}</p>
          <p className="text-sm text-slate-600">
            <strong>{report.property?.name}</strong>
            {' · '}
            {report.date_range?.from} to {report.date_range?.to}
            {' · generated '}
            {String(report.generated_at || '').slice(0, 19).replace('T', ' ')} UTC
          </p>
          <section>
            <h2 className="text-lg font-semibold text-midnight-blue">Tenancy</h2>
            <ul className="mt-2 text-sm space-y-1">
              {(report.tenancies || []).length === 0 ? (
                <li className="text-gray-500">No rent tenancy records.</li>
              ) : (
                (report.tenancies || []).map((t) => (
                  <li key={t.tenancy_id}>
                    {t.tenant_display_name || 'Tenancy'} ({t.status})
                  </li>
                ))
              )}
            </ul>
          </section>
          <section>
            <h2 className="text-lg font-semibold text-midnight-blue">Compliance</h2>
            <ul className="mt-2 text-sm space-y-1">
              {(report.compliance || []).length === 0 ? (
                <li className="text-gray-500">No compliance requirements listed.</li>
              ) : (
                (report.compliance || []).map((c, i) => (
                  <li key={i}>
                    {c.name}: {c.status}
                    {c.due_date ? ` · due ${String(c.due_date).slice(0, 10)}` : ''}
                  </li>
                ))
              )}
            </ul>
          </section>
          <section>
            <h2 className="text-lg font-semibold text-midnight-blue">Maintenance</h2>
            <ul className="mt-2 text-sm space-y-1">
              {(report.maintenance || []).length === 0 ? (
                <li className="text-gray-500">No maintenance jobs in this range.</li>
              ) : (
                (report.maintenance || []).map((m) => (
                  <li key={m.work_order_id}>
                    {m.description} ({m.category}, {m.status})
                    {m.contractor_name ? ` — ${m.contractor_name}` : ''}
                  </li>
                ))
              )}
            </ul>
          </section>
          <section>
            <h2 className="text-lg font-semibold text-midnight-blue">Chronological activity</h2>
            <ul className="mt-2 text-sm space-y-2">
              {(report.chronology || []).length === 0 ? (
                <li className="text-gray-500">No activity recorded in this date range.</li>
              ) : (
                (report.chronology || []).map((ev, i) => (
                  <li key={`${ev.timestamp}-${i}`}>
                    <span className="text-gray-500">{String(ev.timestamp || '').slice(0, 16).replace('T', ' ')}</span>
                    {' '}
                    <strong>{ev.headline}</strong>
                    {' — '}
                    {ev.summary}
                  </li>
                ))
              )}
            </ul>
          </section>
        </div>
      ) : null}
    </div>
  );
}
