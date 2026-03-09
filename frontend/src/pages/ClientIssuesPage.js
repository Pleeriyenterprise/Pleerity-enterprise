/**
 * Operations → Issues: work orders in open/reported state (filtered view).
 * "Create issue" creates a work order. Gated by maintenance_workflows.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { AlertCircle, Plus, Loader2, Wrench } from 'lucide-react';
import { toast } from 'sonner';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';

const OPEN_STATUSES = ['OPEN', 'ASSIGNED'];

function ClientIssuesPageInner() {
  const navigate = useNavigate();
  const [workOrders, setWorkOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [properties, setProperties] = useState([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ property_id: '', description: '', category: 'general', severity: 'medium' });
  const [createSaving, setCreateSaving] = useState(false);
  const [error, setError] = useState(null);

  const loadWorkOrders = useCallback(() => {
    setLoading(true);
    setError(null);
    clientAPI
      .getMaintenanceWorkOrders({ skip: 0, limit: 200 })
      .then((res) => {
        const all = res.data?.work_orders || [];
        const open = all.filter((wo) => OPEN_STATUSES.includes(wo.status));
        setWorkOrders(open);
        setTotal(open.length);
      })
      .catch((err) => {
        if (err?.response?.status === 403) {
          setError(err?.response?.data?.detail || 'Maintenance workflows are not enabled for your account.');
        } else {
          setError('Failed to load issues.');
          toast.error(err?.response?.data?.detail || 'Failed to load issues');
        }
        setWorkOrders([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, []);

  const loadProperties = useCallback(() => {
    clientAPI.getProperties().then((res) => {
      setProperties(res.data?.properties || res.data || []);
    }).catch(() => setProperties([]));
  }, []);

  useEffect(() => {
    loadWorkOrders();
    loadProperties();
  }, [loadWorkOrders, loadProperties]);

  const handleCreateSubmit = (e) => {
    e.preventDefault();
    if (!createForm.property_id || !createForm.description?.trim()) {
      toast.error('Select a property and enter a description');
      return;
    }
    setCreateSaving(true);
    clientAPI
      .createMaintenanceWorkOrder({
        property_id: createForm.property_id,
        description: createForm.description.trim(),
        category: createForm.category || undefined,
        severity: createForm.severity || undefined,
      })
      .then(() => {
        toast.success('Issue reported. A work order has been created.');
        setCreateOpen(false);
        setCreateForm({ property_id: '', description: '', category: 'general', severity: 'medium' });
        loadWorkOrders();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to report issue'))
      .finally(() => setCreateSaving(false));
  };

  const propertyLabel = (id) => {
    const p = properties.find((x) => x.property_id === id);
    return p ? (p.nickname || p.address_line_1 || p.postcode || id) : id;
  };

  const formatDate = (s) => {
    if (!s) return '—';
    try {
      return new Date(s).toLocaleDateString(undefined, { dateStyle: 'short' });
    } catch {
      return s;
    }
  };

  if (error && !loading) {
    return (
      <div className="p-6 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-4">
          <AlertCircle className="w-7 h-7" />
          Issues
        </h1>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6">
            <p className="font-medium text-amber-900">{error}</p>
            <p className="text-sm text-amber-800 mt-2">Contact your administrator to enable maintenance workflows.</p>
            <Button variant="outline" className="mt-4" onClick={() => navigate('/operations/work-orders')}>
              View Work Orders
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <AlertCircle className="w-7 h-7" />
          Issues
        </h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/operations/work-orders')}>
            View all work orders
          </Button>
          <Button onClick={() => setCreateOpen(true)} className="bg-electric-teal hover:bg-electric-teal/90">
            <Plus className="w-4 h-4 mr-2" />
            Report issue
          </Button>
        </div>
      </div>
      <p className="text-gray-600 mb-6">
        Open and assigned issues across your portfolio. Report an issue to create a work order for your admin or contractor to action.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Open issues</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : workOrders.length === 0 ? (
            <p className="text-gray-500 py-6">No open issues. Use &quot;Report issue&quot; to create one, or view all work orders for full history.</p>
          ) : (
            <ul className="space-y-3">
              {workOrders.map((wo) => (
                <li
                  key={wo.work_order_id}
                  className="flex flex-wrap items-center justify-between gap-2 p-3 bg-gray-50 rounded-lg border border-gray-100"
                >
                  <div>
                    <p className="font-medium text-gray-900">{propertyLabel(wo.property_id)}</p>
                    <p className="text-sm text-gray-600 truncate max-w-md">{wo.description || '—'}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      Created {formatDate(wo.created_at)} · {wo.source === 'tenant_request' ? 'Tenant' : wo.source || 'You'}
                    </p>
                  </div>
                  <span className="px-2 py-1 rounded text-xs font-medium bg-amber-100 text-amber-800">{wo.status}</span>
                </li>
              ))}
            </ul>
          )}
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

export default function ClientIssuesPage() {
  return (
    <EntitlementProtectedRoute requiredFeature="maintenance_workflows">
      <ClientIssuesPageInner />
    </EntitlementProtectedRoute>
  );
}
