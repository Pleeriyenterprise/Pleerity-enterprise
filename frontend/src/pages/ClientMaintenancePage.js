import React, { useState, useEffect, useCallback } from 'react';
import { clientAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Wrench, Plus, Loader2, AlertCircle, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';

export default function ClientMaintenancePage() {
  const [workOrders, setWorkOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [insights, setInsights] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [properties, setProperties] = useState([]);
  const [createForm, setCreateForm] = useState({ property_id: '', description: '', category: 'general', severity: 'medium' });
  const [createSaving, setCreateSaving] = useState(false);
  const [maintenanceError, setMaintenanceError] = useState(null);

  const loadWorkOrders = useCallback(() => {
    setLoading(true);
    setMaintenanceError(null);
    clientAPI.getMaintenanceWorkOrders({ skip: 0, limit: 100 })
      .then((res) => {
        setWorkOrders(res.data?.work_orders || []);
        setTotal(res.data?.total ?? 0);
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail;
        if (err?.response?.status === 403) {
          setMaintenanceError(detail || 'Maintenance workflows are not enabled for your account.');
        } else {
          setMaintenanceError('Failed to load work orders.');
          toast.error(detail || 'Failed to load work orders');
        }
        setWorkOrders([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, []);

  const loadInsights = useCallback(() => {
    setInsightsLoading(true);
    clientAPI.getPredictiveInsights({ limit: 20 })
      .then((res) => setInsights(res.data))
      .catch(() => setInsights(null))
      .finally(() => setInsightsLoading(false));
  }, []);

  const loadProperties = useCallback(() => {
    clientAPI.getProperties().then((res) => {
      setProperties(res.data?.properties || res.data || []);
    }).catch(() => setProperties([]));
  }, []);

  useEffect(() => { loadWorkOrders(); loadProperties(); }, [loadWorkOrders, loadProperties]);
  useEffect(() => { loadInsights(); }, [loadInsights]);

  const handleCreateSubmit = (e) => {
    e.preventDefault();
    if (!createForm.property_id || !createForm.description?.trim()) {
      toast.error('Select a property and enter a description');
      return;
    }
    setCreateSaving(true);
    clientAPI.createMaintenanceWorkOrder({
      property_id: createForm.property_id,
      description: createForm.description.trim(),
      category: createForm.category || undefined,
      severity: createForm.severity || undefined,
    })
      .then(() => {
        toast.success('Work order created');
        setCreateOpen(false);
        setCreateForm({ property_id: '', description: '', category: 'general', severity: 'medium' });
        loadWorkOrders();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Create failed'))
      .finally(() => setCreateSaving(false));
  };

  const formatDate = (s) => {
    if (!s) return '—';
    try {
      const d = typeof s === 'string' ? new Date(s) : s;
      return d.toLocaleDateString(undefined, { dateStyle: 'short' });
    } catch {
      return s;
    }
  };

  const propertyLabel = (id) => {
    const p = properties.find((x) => x.property_id === id);
    return p ? (p.nickname || p.address_line_1 || p.postcode || id) : id;
  };

  const statusBadge = (status) => {
    const map = { OPEN: 'bg-amber-100 text-amber-800', ASSIGNED: 'bg-blue-100 text-blue-800', IN_PROGRESS: 'bg-blue-100 text-blue-800', COMPLETED: 'bg-green-100 text-green-800', CANCELLED: 'bg-gray-100 text-gray-600' };
    return map[status] || 'bg-gray-100 text-gray-700';
  };

  if (maintenanceError && !loading) {
    return (
      <div className="p-6 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-4">
          <Wrench className="w-7 h-7" />
          Maintenance
        </h1>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-amber-900">Maintenance not enabled</p>
              <p className="text-sm text-amber-800 mt-1">{maintenanceError}</p>
              <p className="text-sm text-amber-700 mt-2">Contact your account administrator or support to enable maintenance workflows for your account.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Wrench className="w-7 h-7" />
          Maintenance
        </h1>
        <Button onClick={() => setCreateOpen(true)} className="bg-electric-teal hover:bg-electric-teal/90">
          <Plus className="w-4 h-4 mr-2" />
          Report issue
        </Button>
      </div>
      <p className="text-gray-600 mb-6">
        View and create work orders for repairs or maintenance. Your landlord or admin can assign contractors and update status.
      </p>

      {/* Predictive insights: show card when loaded (with optional empty state); 403 from API means feature off and we don't show */}
      {(insights !== null || insightsLoading) && (
        <Card className="mb-6 border-teal-200 bg-teal-50/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-electric-teal" />
              Predictive insights
              {insightsLoading && <Loader2 className="w-4 h-4 animate-spin text-teal-600" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {insightsLoading && (
              <p className="text-sm text-gray-500 py-2">Loading insights…</p>
            )}
            {!insightsLoading && insights?.properties?.length > 0 && insights.properties.some((p) => p.insights?.length > 0) && (
              insights.properties.filter((p) => p.insights?.length > 0).map((prop) => (
                <div key={prop.property_id} className="text-sm p-3 bg-white rounded-lg border border-teal-100">
                  <p className="font-medium text-gray-900">{prop.nickname || prop.address_line_1 || prop.property_id}</p>
                  {prop.insights.slice(0, 5).map((i, idx) => (
                    <div key={idx} className="mt-2 pl-2 border-l-2 border-teal-200">
                      <p className="text-gray-700">{i.recommendation}</p>
                      {i.detail && <p className="text-xs text-gray-500 mt-0.5">{i.detail}</p>}
                      <span className={`inline-block mt-1 text-xs px-1.5 py-0.5 rounded ${i.risk === 'high' || i.risk === 'urgent' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-600'}`}>{i.risk}</span>
                    </div>
                  ))}
                </div>
              ))
            )}
            {!insightsLoading && insights !== null && (!insights?.properties?.length || !insights.properties.some((p) => p.insights?.length > 0)) && (
              <p className="text-sm text-gray-600 py-2">
                No insights yet. Add property assets (e.g. boiler, last service date) on your properties to get recommendations, or ensure building age is set where relevant.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Work orders</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : workOrders.length === 0 ? (
            <p className="text-gray-500 py-6">No work orders yet. Use &quot;Report issue&quot; to create one.</p>
          ) : (
            <ul className="space-y-3">
              {workOrders.map((wo) => (
                <li key={wo.work_order_id} className="flex flex-wrap items-center justify-between gap-2 p-3 bg-gray-50 rounded-lg border border-gray-100">
                  <div>
                    <p className="font-medium text-gray-900">{propertyLabel(wo.property_id)}</p>
                    <p className="text-sm text-gray-600 truncate max-w-md">{wo.description || '—'}</p>
                    <p className="text-xs text-gray-500 mt-1">Created {formatDate(wo.created_at)} · {wo.source === 'tenant_request' ? 'Tenant' : wo.source || 'You'}</p>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${statusBadge(wo.status)}`}>{wo.status}</span>
                </li>
              ))}
            </ul>
          )}
          {total > 0 && <p className="text-sm text-gray-500 mt-2">Total: {total}</p>}
        </CardContent>
      </Card>

      {createOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Report an issue</h2>
            <form onSubmit={handleCreateSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Property *</label>
                <select
                  value={createForm.property_id}
                  onChange={(e) => setCreateForm((f) => ({ ...f, property_id: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  required
                >
                  <option value="">Select property</option>
                  {properties.map((p) => (
                    <option key={p.property_id} value={p.property_id}>{propertyLabel(p.property_id)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  rows={3}
                  placeholder="Describe the issue..."
                  required
                />
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="submit" disabled={createSaving} className="bg-electric-teal hover:bg-electric-teal/90">
                  {createSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Submit'}
                </Button>
                <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
