import React, { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import client from '../api/client';
import { toast } from 'sonner';
import { ArrowLeft } from 'lucide-react';

const SCORE_CAP = 97;

function riskBandLabel(band) {
  if (band === 'HIGH') return 'High';
  if (band === 'MODERATE') return 'Moderate–High';
  return 'Low';
}

const AdminRiskReportPage = () => {
  const { leadId } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!leadId) return;
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const res = await client.get(`/admin/risk-leads/${leadId}/report`);
        if (!cancelled) setReport(res.data);
      } catch (e) {
        if (!cancelled) toast.error(e.response?.data?.detail || 'Failed to load report');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [leadId]);

  if (loading) {
    return (
      <UnifiedAdminLayout>
        <div className="max-w-4xl mx-auto px-4 py-8">
          <p className="text-gray-500">Loading report…</p>
        </div>
      </UnifiedAdminLayout>
    );
  }

  if (!report) {
    return (
      <UnifiedAdminLayout>
        <div className="max-w-4xl mx-auto px-4 py-8">
          <p className="text-gray-500">Report not found.</p>
          <Button variant="outline" asChild className="mt-4">
            <Link to="/admin/risk-leads"><ArrowLeft className="w-4 h-4 mr-2" /> Back to Risk Check Leads</Link>
          </Button>
        </div>
      </UnifiedAdminLayout>
    );
  }

  return (
    <UnifiedAdminLayout>
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-6">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/admin/risk-leads"><ArrowLeft className="w-4 h-4 mr-1" /> Back to Risk Check Leads</Link>
          </Button>
        </div>
        <h1 className="text-2xl font-bold text-midnight-blue mb-2">Risk Report</h1>
        <p className="text-sm text-gray-500 mb-8">Lead ID: {report.lead_id}</p>

        <div className="space-y-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardContent className="pt-6">
                <h2 className="text-xl font-semibold text-midnight-blue mb-4">Risk Snapshot</h2>
                <div className="text-center py-4">
                  <p className="text-4xl font-bold text-midnight-blue">Compliance Risk Score (estimate): {report.score} / {SCORE_CAP}</p>
                  <p className="text-lg text-gray-700 mt-2">Risk Level: {riskBandLabel(report.risk_band)}</p>
                  <p className="text-sm text-gray-500 mt-1">Based on structured weighting of safety and monitoring indicators.</p>
                </div>
                <div className="mt-6 p-4 bg-amber-50 rounded-lg">
                  <h3 className="font-semibold text-midnight-blue mb-2">Estimated exposure band</h3>
                  <p className="text-gray-700">{report.exposure_range_label}</p>
                  <p className="text-xs text-gray-500 mt-2">Typical financial exposure range can vary; informational only.</p>
                </div>
                {report.flags && report.flags.length > 0 && (
                  <div className="mt-6">
                    <h3 className="font-semibold text-midnight-blue mb-2">Flags detected</h3>
                    <ul className="list-disc pl-5 space-y-2 text-sm text-gray-700">
                      {report.flags.map((f, i) => (
                        <li key={i}><strong>{f.title}</strong>: {f.description}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="mt-6 p-3 bg-gray-100 rounded text-xs text-gray-600">
                  Informational tracking indicator only. Not legal advice. Local rules vary.
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <h3 className="text-lg font-semibold text-midnight-blue mb-4">Recommended plan</h3>
                <p className="text-gray-700">{report.recommended_plan_code || '—'}</p>
                <Button variant="outline" className="mt-6" asChild>
                  <Link to={`/intake/start?plan=${report.recommended_plan_code || ''}&lead_id=${report.lead_id}`} target="_blank" rel="noopener noreferrer">
                    Start Intake for this lead
                  </Link>
                </Button>
              </CardContent>
            </Card>
          </div>

          {report.property_breakdown && report.property_breakdown.length > 0 && (
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold text-midnight-blue mb-2">
                  {report.property_breakdown.length === 1 ? 'Property compliance position' : 'Portfolio score'}
                </h3>
                {report.property_breakdown.map((row, i) => (
                  <div key={i} className="border rounded p-3 mb-2 text-sm">
                    <span className="font-medium">{row.label}</span> – {row.score}% · Gas: {row.gas} · Electrical: {row.electrical} · Tracking: {row.tracking}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          <p className="text-xs text-gray-500 border-t pt-6">{report.disclaimer_text}</p>
        </div>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminRiskReportPage;
