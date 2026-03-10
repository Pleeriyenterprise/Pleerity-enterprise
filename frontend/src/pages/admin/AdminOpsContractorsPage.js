import React, { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { Users, Plus, Pencil, Trash2, Loader2, CheckCircle, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '../../components/ui/button';

export default function AdminOpsContractorsPage() {
  const [contractors, setContractors] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [clients, setClients] = useState([]);
  const [clientIdFilter, setClientIdFilter] = useState('');
  const [vettedOnly, setVettedOnly] = useState(false);
  const [sourceTypeFilter, setSourceTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [editing, setEditing] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [networkFormOpen, setNetworkFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: '',
    trade_types: [],
    trade_types_text: '',
    vetted: false,
    email: '',
    phone: '',
    company_name: '',
    client_id: '',
    areas_served: [],
    areas_text: '',
    notes: '',
    status: '',
    credentials: [],
    credentials_text: '',
    insurance_details: '',
    contact_name: '',
    region: '',
  });
  const [networkForm, setNetworkForm] = useState({
    company_name: '',
    trade_types_text: '',
    phone: '',
    email: '',
    region: '',
    contact_name: '',
    credentials_text: '',
    insurance_details: '',
    areas_text: '',
    notes: '',
  });

  const loadClients = useCallback(() => {
    adminAPI.getClients(0, 500).then((res) => {
      const list = res.data?.clients || res.data?.items || [];
      setClients(list);
    }).catch(() => setClients([]));
  }, []);

  const loadContractors = useCallback(() => {
    setLoading(true);
    const params = { skip: 0, limit: 200 };
    if (clientIdFilter) params.client_id = clientIdFilter;
    if (vettedOnly) params.vetted_only = true;
    if (sourceTypeFilter) params.source_type = sourceTypeFilter;
    if (activeTab === 'pending') params.status = 'pending_review';
    else if (statusFilter) params.status = statusFilter;
    adminAPI.getContractors(params)
      .then((res) => {
        setContractors(res.data?.contractors || []);
        setTotal(res.data?.total ?? 0);
      })
      .catch(() => {
        setContractors([]);
        setTotal(0);
        toast.error('Failed to load contractors');
      })
      .finally(() => setLoading(false));
  }, [clientIdFilter, vettedOnly, sourceTypeFilter, statusFilter, activeTab]);

  useEffect(() => { loadClients(); }, [loadClients]);
  useEffect(() => { loadContractors(); }, [loadContractors]);

  const openCreate = () => {
    setEditing(null);
    setForm({
      name: '',
      trade_types: [],
      trade_types_text: '',
      vetted: false,
      email: '',
      phone: '',
      company_name: '',
      client_id: '',
      areas_served: [],
      areas_text: '',
      notes: '',
      status: '',
      credentials: [],
      credentials_text: '',
      insurance_details: '',
      contact_name: '',
      region: '',
    });
    setFormOpen(true);
  };

  const openEdit = (c) => {
    setEditing(c);
    setForm({
      name: c.name || '',
      trade_types: Array.isArray(c.trade_types) ? c.trade_types : [],
      trade_types_text: (c.trade_types || []).join(', '),
      vetted: !!c.vetted,
      email: c.email || '',
      phone: c.phone || '',
      company_name: c.company_name || '',
      client_id: c.client_id || '',
      areas_served: Array.isArray(c.areas_served) ? c.areas_served : [],
      areas_text: (c.areas_served || []).join(', '),
      notes: c.notes || '',
      status: c.status || '',
      credentials: Array.isArray(c.credentials) ? c.credentials : [],
      credentials_text: (c.credentials || []).join(', '),
      insurance_details: c.insurance_details || '',
      contact_name: c.contact_name || '',
      region: c.region || '',
    });
    setFormOpen(true);
  };

  const parseList = (text) => text.split(',').map((s) => s.trim()).filter(Boolean);

  const handleSubmit = (e) => {
    e.preventDefault();
    const payload = {
      name: form.name.trim(),
      trade_types: parseList(form.trade_types_text),
      vetted: form.vetted,
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      company_name: form.company_name.trim() || null,
      client_id: form.client_id || null,
      areas_served: parseList(form.areas_text),
      notes: form.notes.trim() || null,
      status: form.status.trim() || null,
      credentials: parseList(form.credentials_text),
      insurance_details: form.insurance_details.trim() || null,
      contact_name: form.contact_name.trim() || null,
      region: form.region.trim() || null,
    };
    if (!payload.name) {
      toast.error('Name is required');
      return;
    }
    setSaving(true);
    if (editing) {
      adminAPI.updateContractor(editing.contractor_id, payload)
        .then(() => {
          toast.success('Contractor updated');
          setFormOpen(false);
          loadContractors();
        })
        .catch((err) => toast.error(err?.response?.data?.detail || 'Update failed'))
        .finally(() => setSaving(false));
    } else {
      adminAPI.createContractor(payload)
        .then(() => {
          toast.success('Contractor created');
          setFormOpen(false);
          loadContractors();
        })
        .catch((err) => toast.error(err?.response?.data?.detail || 'Create failed'))
        .finally(() => setSaving(false));
    }
  };

  const handleApprove = (contractorId) => {
    adminAPI.approveContractor(contractorId)
      .then(() => {
        toast.success('Contractor approved');
        loadContractors();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Approve failed'));
  };

  const handleNetworkSubmit = (e) => {
    e.preventDefault();
    const payload = {
      company_name: networkForm.company_name.trim(),
      trade_types: parseList(networkForm.trade_types_text) || ['general'],
      phone: networkForm.phone.trim() || null,
      email: networkForm.email.trim() || null,
      region: networkForm.region.trim() || null,
      contact_name: networkForm.contact_name.trim() || null,
      credentials: parseList(networkForm.credentials_text),
      insurance_details: networkForm.insurance_details.trim() || null,
      areas_served: parseList(networkForm.areas_text),
      notes: networkForm.notes.trim() || null,
    };
    if (!payload.company_name) {
      toast.error('Company name is required');
      return;
    }
    setSaving(true);
    adminAPI.createNetworkContractor(payload)
      .then(() => {
        toast.success('Network contractor added');
        setNetworkFormOpen(false);
        setNetworkForm({ company_name: '', trade_types_text: '', phone: '', email: '', region: '', contact_name: '', credentials_text: '', insurance_details: '', areas_text: '', notes: '' });
        loadContractors();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Create failed'))
      .finally(() => setSaving(false));
  };

  const handleDelete = (contractorId, name) => {
    if (!window.confirm(`Delete contractor "${name}"?`)) return;
    adminAPI.deleteContractor(contractorId)
      .then(() => {
        toast.success('Contractor deleted');
        loadContractors();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Delete failed'));
  };

  const clientLabel = (id) => {
    if (!id) return '—';
    const c = clients.find((x) => x.client_id === id);
    return c ? (c.company_name || c.full_name || c.email || id) : id;
  };

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-5xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Users className="w-7 h-7" />
            Contractors
          </h1>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setNetworkFormOpen(true)}>
              Add network contractor
            </Button>
            <Button onClick={openCreate} className="bg-electric-teal hover:bg-electric-teal/90">
              <Plus className="w-4 h-4 mr-2" />
              Add contractor
            </Button>
          </div>
        </div>
        <p className="text-gray-600 mb-6">
          Manage vetted trades and preferred contractors. Link to a client for client-specific contractors, or leave unset for system-wide use.
        </p>

        <div className="flex flex-wrap gap-4 mb-6">
          <div className="flex gap-2 items-end">
            <button
              type="button"
              onClick={() => setActiveTab('all')}
              className={`px-3 py-1.5 rounded text-sm font-medium ${activeTab === 'all' ? 'bg-electric-teal text-white' : 'bg-gray-100 text-gray-700'}`}
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('pending')}
              className={`px-3 py-1.5 rounded text-sm font-medium flex items-center gap-1 ${activeTab === 'pending' ? 'bg-electric-teal text-white' : 'bg-gray-100 text-gray-700'}`}
            >
              <Clock className="w-4 h-4" />
              Pending Approvals
            </button>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Client filter</label>
            <select
              value={clientIdFilter}
              onChange={(e) => setClientIdFilter(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[200px]"
            >
              <option value="">All contractors</option>
              {clients.map((c) => (
                <option key={c.client_id} value={c.client_id}>{clientLabel(c.client_id)}</option>
              ))}
            </select>
          </div>
          {activeTab === 'all' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Source</label>
                <select
                  value={sourceTypeFilter}
                  onChange={(e) => setSourceTypeFilter(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[160px]"
                >
                  <option value="">All sources</option>
                  <option value="landlord_added">Landlord added</option>
                  <option value="platform_network">Platform network</option>
                  <option value="self_registered">Self-registered</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[140px]"
                >
                  <option value="">All statuses</option>
                  <option value="active">Active</option>
                  <option value="pending_review">Pending review</option>
                  <option value="suspended">Suspended</option>
                </select>
              </div>
            </>
          )}
          <div className="flex items-center gap-2 pt-6">
            <input
              type="checkbox"
              id="vetted-only"
              checked={vettedOnly}
              onChange={(e) => setVettedOnly(e.target.checked)}
              className="rounded border-gray-300"
            />
            <label htmlFor="vetted-only" className="text-sm text-gray-700">Vetted only</label>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-gray-500 py-8">
            <Loader2 className="w-5 h-5 animate-spin" />
            Loading…
          </div>
        ) : contractors.length === 0 ? (
          <div className="bg-gray-50 rounded-lg border border-gray-200 p-8 text-center text-gray-600">
            No contractors found. Add one to get started.
          </div>
        ) : (
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Name</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Trades</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Client</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Source</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Status</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Vetted</th>
                  <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {contractors.map((c) => (
                  <tr key={c.contractor_id}>
                    <td className="px-4 py-2 text-sm text-gray-900">{c.name || c.company_name}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{(c.trade_types || []).join(', ') || '—'}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{clientLabel(c.client_id)}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{c.source_type || '—'}</td>
                    <td className="px-4 py-2 text-sm">
                      {c.status === 'pending_review' && <span className="text-amber-600">Pending</span>}
                      {c.status === 'suspended' && <span className="text-red-600">Suspended</span>}
                      {c.status === 'active' && <span className="text-green-600">Active</span>}
                      {!c.status && '—'}
                    </td>
                    <td className="px-4 py-2">{c.vetted ? <CheckCircle className="w-4 h-4 text-green-600" /> : '—'}</td>
                    <td className="px-4 py-2 text-right">
                      {c.status === 'pending_review' && (
                        <Button variant="outline" size="sm" className="mr-1 text-green-700 border-green-300" onClick={() => handleApprove(c.contractor_id)}>
                          Approve
                        </Button>
                      )}
                      <Button variant="ghost" size="sm" onClick={() => openEdit(c)}><Pencil className="w-4 h-4" /></Button>
                      <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700" onClick={() => handleDelete(c.contractor_id, c.name || c.company_name)}><Trash2 className="w-4 h-4" /></Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {total > 0 && <p className="text-sm text-gray-500 mt-2">Total: {total}</p>}
      </div>

      {formOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">{editing ? 'Edit contractor' : 'Add contractor'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Trade types (comma-separated)</label>
                <input
                  type="text"
                  value={form.trade_types_text}
                  onChange={(e) => setForm((f) => ({ ...f, trade_types_text: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  placeholder="e.g. plumbing, electrical, gas"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Client (optional)</label>
                <select
                  value={form.client_id}
                  onChange={(e) => setForm((f) => ({ ...f, client_id: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                >
                  <option value="">— System-wide —</option>
                  {clients.map((c) => (
                    <option key={c.client_id} value={c.client_id}>{clientLabel(c.client_id)}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="vetted"
                  checked={form.vetted}
                  onChange={(e) => setForm((f) => ({ ...f, vetted: e.target.checked }))}
                  className="rounded border-gray-300"
                />
                <label htmlFor="vetted" className="text-sm text-gray-700">Vetted</label>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                <input
                  type="text"
                  value={form.phone}
                  onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Company name</label>
                <input
                  type="text"
                  value={form.company_name}
                  onChange={(e) => setForm((f) => ({ ...f, company_name: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Areas served (comma-separated)</label>
                <input
                  type="text"
                  value={form.areas_text}
                  onChange={(e) => setForm((f) => ({ ...f, areas_text: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  placeholder="e.g. London, SW1"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  rows={2}
                />
              </div>
              {editing && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                    <select
                      value={form.status}
                      onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
                      className="border border-gray-300 rounded-md px-3 py-2 w-full"
                    >
                      <option value="">—</option>
                      <option value="active">Active</option>
                      <option value="pending_review">Pending review</option>
                      <option value="suspended">Suspended</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Contact name</label>
                    <input
                      type="text"
                      value={form.contact_name}
                      onChange={(e) => setForm((f) => ({ ...f, contact_name: e.target.value }))}
                      className="border border-gray-300 rounded-md px-3 py-2 w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Region</label>
                    <input
                      type="text"
                      value={form.region}
                      onChange={(e) => setForm((f) => ({ ...f, region: e.target.value }))}
                      className="border border-gray-300 rounded-md px-3 py-2 w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Credentials (comma-separated)</label>
                    <input
                      type="text"
                      value={form.credentials_text}
                      onChange={(e) => setForm((f) => ({ ...f, credentials_text: e.target.value }))}
                      className="border border-gray-300 rounded-md px-3 py-2 w-full"
                      placeholder="e.g. Gas Safe, NICEIC"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Insurance details</label>
                    <textarea
                      value={form.insurance_details}
                      onChange={(e) => setForm((f) => ({ ...f, insurance_details: e.target.value }))}
                      className="border border-gray-300 rounded-md px-3 py-2 w-full"
                      rows={2}
                    />
                  </div>
                </>
              )}
              <div className="flex gap-2 pt-2">
                <Button type="submit" disabled={saving} className="bg-electric-teal hover:bg-electric-teal/90">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : (editing ? 'Save' : 'Create')}
                </Button>
                <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>Cancel</Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {networkFormOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Add network contractor</h2>
            <p className="text-sm text-gray-600 mb-4">Visible to all organisations. Company name and at least one trade required.</p>
            <form onSubmit={handleNetworkSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Company name *</label>
                <input
                  type="text"
                  value={networkForm.company_name}
                  onChange={(e) => setNetworkForm((f) => ({ ...f, company_name: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Trade types (comma-separated)</label>
                <input
                  type="text"
                  value={networkForm.trade_types_text}
                  onChange={(e) => setNetworkForm((f) => ({ ...f, trade_types_text: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  placeholder="e.g. plumbing, electrical"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Contact name</label>
                <input
                  type="text"
                  value={networkForm.contact_name}
                  onChange={(e) => setNetworkForm((f) => ({ ...f, contact_name: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                <input
                  type="text"
                  value={networkForm.phone}
                  onChange={(e) => setNetworkForm((f) => ({ ...f, phone: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  value={networkForm.email}
                  onChange={(e) => setNetworkForm((f) => ({ ...f, email: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Region</label>
                <input
                  type="text"
                  value={networkForm.region}
                  onChange={(e) => setNetworkForm((f) => ({ ...f, region: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Credentials (comma-separated)</label>
                <input
                  type="text"
                  value={networkForm.credentials_text}
                  onChange={(e) => setNetworkForm((f) => ({ ...f, credentials_text: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Insurance details</label>
                <textarea
                  value={networkForm.insurance_details}
                  onChange={(e) => setNetworkForm((f) => ({ ...f, insurance_details: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Areas served (comma-separated)</label>
                <input
                  type="text"
                  value={networkForm.areas_text}
                  onChange={(e) => setNetworkForm((f) => ({ ...f, areas_text: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                <textarea
                  value={networkForm.notes}
                  onChange={(e) => setNetworkForm((f) => ({ ...f, notes: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  rows={2}
                />
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="submit" disabled={saving} className="bg-electric-teal hover:bg-electric-teal/90">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Add'}
                </Button>
                <Button type="button" variant="outline" onClick={() => setNetworkFormOpen(false)}>Cancel</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </UnifiedAdminLayout>
  );
}
