import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Search, Download, Mail, FileText, Play, Check } from 'lucide-react';
import client from '../api/client';
import { toast } from 'sonner';

const AdminRiskLeadsPage = () => {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [resending, setResending] = useState(null);
  const [markingConverted, setMarkingConverted] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const params = { limit: 100, offset: 0 };
      if (filter && filter !== 'all') params.risk_band = filter;
      if (search) params.q = search;
      const res = await client.get('/admin/risk-leads', { params });
      setItems(Array.isArray(res.data?.items) ? res.data.items : []);
      setTotal(res.data?.total ?? 0);
    } catch (e) {
      console.error(e);
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [filter, search]);

  useEffect(() => {
    load();
  }, [load]);

  const handleExportCsv = async () => {
    try {
      const params = {};
      if (filter && filter !== 'all') params.risk_band = filter;
      const res = await client.get('/admin/risk-leads/export/csv', { params, responseType: 'blob' });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'risk_leads_export.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
    }
  };

  const handleResendReport = async (leadId) => {
    setResending(leadId);
    try {
      await client.post(`/admin/risk-leads/${leadId}/resend-report`);
      toast.success('Report email sent');
      load();
    } catch (e) {
      console.error(e);
      toast.error(e.response?.data?.detail || 'Failed to send email');
    } finally {
      setResending(null);
    }
  };

  const handleMarkConverted = async (leadId) => {
    setMarkingConverted(leadId);
    try {
      await client.post(`/admin/risk-leads/${leadId}/mark-converted`);
      toast.success('Marked as converted');
      load();
    } catch (e) {
      console.error(e);
      toast.error(e.response?.data?.detail || 'Failed to update');
    } finally {
      setMarkingConverted(null);
    }
  };

  const bandColor = (band) => {
    if (band === 'HIGH') return 'bg-red-100 text-red-700';
    if (band === 'MODERATE') return 'bg-amber-100 text-amber-700';
    return 'bg-green-100 text-green-700';
  };

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-2">Risk Check Leads</h1>
        <p className="text-gray-600 mb-8">Leads from the Compliance Risk Check conversion demo</p>

        <div className="flex gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input placeholder="Search by name, email, lead ID..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" />
          </div>
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-40"><SelectValue placeholder="All bands" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All bands</SelectItem>
              <SelectItem value="HIGH">High</SelectItem>
              <SelectItem value="MODERATE">Moderate</SelectItem>
              <SelectItem value="LOW">Low</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={load}>Apply</Button>
          <Button variant="outline" size="sm" onClick={handleExportCsv}><Download className="w-4 h-4 mr-2" /> Export CSV</Button>
        </div>

        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-gray-50 text-left text-sm text-gray-600">
                  <th className="p-3">Date</th>
                  <th className="p-3">Name</th>
                  <th className="p-3">Email</th>
                  <th className="p-3">Properties</th>
                  <th className="p-3">Risk Band</th>
                  <th className="p-3">Score</th>
                  <th className="p-3">Plan</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">UTM Source</th>
                  <th className="p-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={10} className="p-8 text-center text-gray-500">Loading…</td></tr>
                ) : items.length === 0 ? (
                  <tr><td colSpan={10} className="p-8 text-center text-gray-500">No risk check leads yet.</td></tr>
                ) : (
                  items.map((row) => (
                    <tr key={row.lead_id} className="border-b hover:bg-gray-50">
                      <td className="p-3 text-sm">{row.created_at ? new Date(row.created_at).toLocaleDateString() : '—'}</td>
                      <td className="p-3">{row.first_name || '—'}</td>
                      <td className="p-3">{row.email || '—'}</td>
                      <td className="p-3">{row.property_count ?? '—'}</td>
                      <td className="p-3"><Badge className={bandColor(row.risk_band)}>{row.risk_band || '—'}</Badge></td>
                      <td className="p-3">{row.computed_score ?? '—'}</td>
                      <td className="p-3 text-sm">{row.recommended_plan_code || '—'}</td>
                      <td className="p-3"><Badge variant={row.status === 'converted' ? 'default' : 'secondary'}>{row.status || 'new'}</Badge></td>
                      <td className="p-3 text-sm">{row.utm_source || '—'}</td>
                      <td className="p-3">
                        <div className="flex flex-wrap gap-1">
                          <Button variant="outline" size="sm" asChild>
                            <Link to={`/admin/risk-leads/report/${row.lead_id}`} target="_blank" rel="noopener noreferrer"><FileText className="w-4 h-4 mr-1" /> Open Risk Report</Link>
                          </Button>
                          <Button variant="outline" size="sm" asChild>
                            <Link to={row.recommended_plan_code ? `/intake/start?plan=${row.recommended_plan_code}` : '/intake/start'} target="_blank" rel="noopener noreferrer"><Play className="w-4 h-4 mr-1" /> Start Intake</Link>
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleResendReport(row.lead_id)} disabled={resending === row.lead_id}>
                            <Mail className="w-4 h-4 mr-1" /> {resending === row.lead_id ? 'Sending…' : 'Resend report'}
                          </Button>
                          {row.status !== 'converted' && (
                            <Button variant="ghost" size="sm" onClick={() => handleMarkConverted(row.lead_id)} disabled={markingConverted === row.lead_id}>
                              <Check className="w-4 h-4 mr-1" /> {markingConverted === row.lead_id ? 'Updating…' : 'Mark Converted'}
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
        {!loading && total > 0 && <p className="text-sm text-gray-500 mt-4">Total: {total}</p>}
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminRiskLeadsPage;
