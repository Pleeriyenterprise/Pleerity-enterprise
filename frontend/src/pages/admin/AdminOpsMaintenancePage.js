import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { Wrench, Plus, Loader2, UserPlus, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '../../components/ui/button';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'OPEN', label: 'Open' },
  { value: 'ASSIGNED', label: 'Assigned' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'CANCELLED', label: 'Cancelled' },
];

export default function AdminOpsMaintenancePage() {
  const [workOrders, setWorkOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [clients, setClients] = useState([]);
  const [contractors, setContractors] = useState([]);
  const [clientIdFilter, setClientIdFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [assigningId, setAssigningId] = useState(null);
  const [updatingId, setUpdatingId] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    client_id: '',
    property_id: '',
    description: '',
    category: 'general',
    severity: 'medium',
  });
  const [createSaving, setCreateSaving] = useState(false);

  const loadClients = useCallback(() => {
    adminAPI.getClients(0, 500).then((res) => {
      setClients(res.data?.clients || res.data?.items || []);
    }).catch(() => setClients([]));
  }, []);

  const loadContractors = useCallback(() => {
    adminAPI.getContractors({ skip: 0, limit: 500 }).then((res) => {
      setContractors(res.data?.contractors || []);
    }).catch(() => setContractors([]));
  }, []);

  const loadWorkOrders = useCallback(() => {
    setLoading(true);
    const params = { skip: 0, limit: 200 };
    if (clientIdFilter) params.client_id = clientIdFilter;
    if (statusFilter) params.status = statusFilter;
    adminAPI.getWorkOrders(params)
      .then((res) => {
        setWorkOrders(res.data?.work_orders || []);
        setTotal(res.data?.total ?? 0);
      })
      .catch(() => {
        setWorkOrders([]);
        setTotal(0);
        toast.error('Failed to load work orders');
      })
      .finally(() => setLoading(false));
  }, [clientIdFilter, statusFilter]);

  useEffect(() => { loadClients(); loadContractors(); }, [loadClients, loadContractors]);
  useEffect(() => { loadWorkOrders(); }, [loadWorkOrders]);

  const handleAssign = (workOrderId, contractorId) => {
    if (!contractorId) return;
    setAssigningId(workOrderId);
    adminAPI.updateWorkOrder(workOrderId, { contractor_id: contractorId })
      .then(() => {
        toast.success('Contractor assigned');
        loadWorkOrders();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Assign failed'))
      .finally(() => setAssigningId(null));
  };

  const handleStatusChange = (workOrderId, status) => {
    setUpdatingId(workOrderId);
    adminAPI.updateWorkOrder(workOrderId, { status })
      .then(() => {
        toast.success('Status updated');
        loadWorkOrders();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Update failed'))
      .finally(() => setUpdatingId(null));
  };

  const handleCreateSubmit = (e) => {
    e.preventDefault();
    if (!createForm.client_id || !createForm.property_id || !createForm.description?.trim()) {
      toast.error('Client, property and description are required');
      return;
    }
    setCreateSaving(true);
    adminAPI.createWorkOrder({
      client_id: createForm.client_id,
      property_id: createForm.property_id,
      description: createForm.description.trim(),
      category: createForm.category || undefined,
      severity: createForm.severity || undefined,
    })
      .then(() => {
        toast.success('Work order created');
        setCreateOpen(false);
        setCreateForm({ client_id: '', property_id: '', description: '', category: 'general', severity: 'medium' });
        loadWorkOrders();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Create failed'))
      .finally(() => setCreateSaving(false));
  };

  const clientLabel = (id) => {
    if (!id) return '—';
    const c = clients.find((x) => x.client_id === id);
    return c ? (c.company_name || c.full_name || c.email || id) : id;
  };

  const contractorLabel = (id) => {
    if (!id) return '—';
    const c = contractors.find((x) => x.contractor_id === id);
    return c ? c.name : id;
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

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-6xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Wrench className="w-7 h-7" />
            Maintenance (Work Orders)
          </h1>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={loadWorkOrders} disabled={loading}>
              <RefreshCw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button onClick={() => setCreateOpen(true)} className="bg-electric-teal hover:bg-electric-teal/90">
              <Plus className="w-4 h-4 mr-2" />
              Create work order
            </Button>
          </div>
        </div>
        <p className="text-gray-600 mb-6">
          View and manage work orders. Assign contractors from the <Link to="/admin/ops/contractors" className="text-electric-teal hover:underline">Contractors</Link> list.
        </p>

        <div className="flex flex-wrap gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Client</label>
            <select
              value={clientIdFilter}
              onChange={(e) => setClientIdFilter(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[200px]"
            >
              <option value="">All clients</option>
              {clients.map((c) => (
                <option key={c.client_id} value={c.client_id}>{clientLabel(c.client_id)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[140px]"
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value || 'all'} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-gray-500 py-8">
            <Loader2 className="w-5 h-5 animate-spin" />
            Loading…
          </div>
        ) : workOrders.length === 0 ? (
          <div className="bg-gray-50 rounded-lg border border-gray-200 p-8 text-center text-gray-600">
            No work orders found. Create one or have tenants/clients report issues (when maintenance is enabled).
          </div>
        ) : (
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">ID / Property</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Client</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Description</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Status</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Contractor</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Created</th>
                  <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {workOrders.map((wo) => (
                  <tr key={wo.work_order_id}>
                    <td className="px-4 py-2 text-sm">
                      <span className="text-gray-500 font-mono text-xs">{wo.work_order_id?.slice(0, 8)}…</span>
                      <br />
                      <span className="text-gray-700">{wo.property_id}</span>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">{clientLabel(wo.client_id)}</td>
                    <td className="px-4 py-2 text-sm text-gray-700 max-w-[200px] truncate" title={wo.description}>{wo.description || '—'}</td>
                    <td className="px-4 py-2">
                      <select
                        value={wo.status}
                        onChange={(e) => handleStatusChange(wo.work_order_id, e.target.value)}
                        disabled={updatingId === wo.work_order_id}
                        className="border border-gray-300 rounded px-2 py-1 text-sm"
                      >
                        {STATUS_OPTIONS.filter((o) => o.value).map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                      {updatingId === wo.work_order_id && <Loader2 className="w-4 h-4 inline ml-1 animate-spin" />}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {wo.contractor_id ? (
                        contractorLabel(wo.contractor_id)
                      ) : (
                        <select
                          className="border border-gray-300 rounded px-2 py-1 text-sm min-w-[120px]"
                          value=""
                          onChange={(e) => {
                            const v = e.target.value;
                            if (v) handleAssign(wo.work_order_id, v);
                          }}
                          disabled={assigningId === wo.work_order_id}
                        >
                          <option value="">Assign…</option>
                          {contractors.map((c) => (
                            <option key={c.contractor_id} value={c.contractor_id}>{c.name}</option>
                          ))}
                        </select>
                      )}
                      {assigningId === wo.work_order_id && <Loader2 className="w-4 h-4 inline ml-1 animate-spin" />}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-500">{formatDate(wo.created_at)}</td>
                    <td className="px-4 py-2 text-right text-sm">
                      <span className="text-gray-400 text-xs">{wo.source === 'tenant_request' ? 'Tenant' : wo.source || '—'}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {total > 0 && <p className="text-sm text-gray-500 mt-2">Total: {total}</p>}
      </div>

      {createOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Create work order</h2>
            <form onSubmit={handleCreateSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Client *</label>
                <select
                  value={createForm.client_id}
                  onChange={(e) => setCreateForm((f) => ({ ...f, client_id: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  required
                >
                  <option value="">Select client</option>
                  {clients.map((c) => (
                    <option key={c.client_id} value={c.client_id}>{clientLabel(c.client_id)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Property ID *</label>
                <input
                  type="text"
                  value={createForm.property_id}
                  onChange={(e) => setCreateForm((f) => ({ ...f, property_id: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  placeholder="property_id from client portfolio"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  rows={3}
                  required
                />
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="submit" disabled={createSaving} className="bg-electric-teal hover:bg-electric-teal/90">
                  {createSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create'}
                </Button>
                <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </UnifiedAdminLayout>
  );
}
