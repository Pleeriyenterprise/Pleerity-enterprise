import React, { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { Users, Plus, Pencil, Trash2, Loader2, CheckCircle, Clock, Mail, BarChart3, Info, ChevronDown, ChevronUp, ShieldOff, RefreshCw, Briefcase, Send, XCircle } from 'lucide-react';
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
  const [analyticsView, setAnalyticsView] = useState('top_performers');
  const [analyticsClientId, setAnalyticsClientId] = useState('');
  const [analyticsLimit, setAnalyticsLimit] = useState(50);
  const [analyticsData, setAnalyticsData] = useState({ contractors: [], total: 0, view: '' });
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [contractorExplainId, setContractorExplainId] = useState(null);
  const [contractorExplainData, setContractorExplainData] = useState(null);
  const [contractorExplainLoading, setContractorExplainLoading] = useState(false);
  const [editing, setEditing] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [networkFormOpen, setNetworkFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [invitingId, setInvitingId] = useState(null);
  const [resendingInviteId, setResendingInviteId] = useState(null);
  const [disablingAccessId, setDisablingAccessId] = useState(null);
  const [assignedJobsOpen, setAssignedJobsOpen] = useState(false);
  const [assignedJobsFor, setAssignedJobsFor] = useState(null);
  const [assignedJobsLoading, setAssignedJobsLoading] = useState(false);
  const [assignedJobs, setAssignedJobs] = useState([]);
  const [networkReviewApprovingId, setNetworkReviewApprovingId] = useState(null);
  const [networkReviewRejectingId, setNetworkReviewRejectingId] = useState(null);
  const [networkRejectModal, setNetworkRejectModal] = useState(null);
  const [networkRejectReason, setNetworkRejectReason] = useState('');
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
    if (activeTab === 'network_review') {
      params.pending_network_review = true;
    } else {
      if (sourceTypeFilter) params.source_type = sourceTypeFilter;
      if (activeTab === 'pending') params.status = 'pending_review';
      else if (statusFilter) params.status = statusFilter;
    }
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

  const loadAnalytics = useCallback(() => {
    setAnalyticsLoading(true);
    const params = { view: analyticsView, limit: analyticsLimit };
    if (analyticsClientId) params.client_id = analyticsClientId;
    adminAPI.getContractorAnalytics(params)
      .then((res) => {
        setAnalyticsData({
          contractors: res.data?.contractors || [],
          total: res.data?.total ?? 0,
          view: res.data?.view || analyticsView,
        });
      })
      .catch(() => {
        setAnalyticsData({ contractors: [], total: 0, view: analyticsView });
        toast.error('Failed to load contractor analytics');
      })
      .finally(() => setAnalyticsLoading(false));
  }, [analyticsView, analyticsClientId, analyticsLimit]);

  useEffect(() => { loadClients(); }, [loadClients]);
  useEffect(() => { loadContractors(); }, [loadContractors]);
  useEffect(() => {
    if (activeTab === 'analytics') loadAnalytics();
  }, [activeTab, loadAnalytics]);

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

  const humanPortalAccess = (value) => {
    const v = (value || '').toLowerCase();
    if (v === 'enabled') return 'Enabled';
    if (v === 'invite_pending') return 'Invite pending';
    if (v === 'disabled') return 'Disabled';
    return 'Not invited';
  };

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-7xl">
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
        <p className="text-gray-600 mb-4">
          Manage vetted trades and preferred contractors. Link to a client for client-specific contractors, or leave unset for system-wide use.
        </p>
        <div className="mb-6 rounded-lg border border-teal-200 bg-teal-50/80 px-4 py-3 text-sm text-midnight-blue">
          <strong className="font-semibold">Contractor portal invites:</strong>{' '}
          Each row must have an <strong>email</strong> before you can send access. Use{' '}
          <strong>Invite to portal</strong> to email a setup link, or <strong>Resend invite</strong> to rotate the link.
          Self-registrations from the website appear as <em>Pending</em> until you <strong>Approve</strong>, then invite.
          {' '}
          <strong className="font-semibold">Landlord → network:</strong> clients can submit a private contractor for review; use the{' '}
          <strong>Network review</strong> tab to approve (creates a platform network copy) or reject. New submissions trigger an internal email when{' '}
          <code className="text-xs bg-white/80 px-1 rounded border border-teal-100">ADMIN_NOTIFY_EMAIL</code> is configured.
        </div>

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
            <button
              type="button"
              onClick={() => setActiveTab('network_review')}
              className={`px-3 py-1.5 rounded text-sm font-medium flex items-center gap-1 ${activeTab === 'network_review' ? 'bg-electric-teal text-white' : 'bg-gray-100 text-gray-700'}`}
            >
              <Send className="w-4 h-4" />
              Network review
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('analytics')}
              className={`px-3 py-1.5 rounded text-sm font-medium flex items-center gap-1 ${activeTab === 'analytics' ? 'bg-electric-teal text-white' : 'bg-gray-100 text-gray-700'}`}
            >
              <BarChart3 className="w-4 h-4" />
              Analytics
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

        {activeTab === 'analytics' ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-4 items-end p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">View</label>
                <select
                  value={analyticsView}
                  onChange={(e) => setAnalyticsView(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[180px]"
                >
                  <option value="top_performers">Top performing</option>
                  <option value="sla_issues">SLA issues (&lt;80% on-time)</option>
                  <option value="high_rejection">High rejection (invoice approval &lt;80%)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Client filter</label>
                <select
                  value={analyticsClientId}
                  onChange={(e) => setAnalyticsClientId(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[200px]"
                >
                  <option value="">All contractors</option>
                  {clients.map((c) => (
                    <option key={c.client_id} value={c.client_id}>{clientLabel(c.client_id)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Limit</label>
                <select
                  value={analyticsLimit}
                  onChange={(e) => setAnalyticsLimit(Number(e.target.value))}
                  className="border border-gray-300 rounded-md px-3 py-2 text-sm"
                >
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                  <option value={200}>200</option>
                </select>
              </div>
              <Button variant="outline" onClick={loadAnalytics} disabled={analyticsLoading}>
                {analyticsLoading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                Refresh
              </Button>
            </div>
            {analyticsLoading ? (
              <div className="flex items-center gap-2 text-gray-500 py-8">
                <Loader2 className="w-5 h-5 animate-spin" />
                Loading analytics…
              </div>
            ) : analyticsData.contractors.length === 0 ? (
              <div className="bg-gray-50 rounded-lg border border-gray-200 p-8 text-center text-gray-600">
                No contractors match this view. Run score recalculation or assign jobs to see metrics.
              </div>
            ) : (
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Name</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Trades</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Client</th>
                      <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">Score</th>
                      <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">Reliability</th>
                      <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">SLA %</th>
                      <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">Invoice %</th>
                      <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">Jobs</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700 w-32">Explanation</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {analyticsData.contractors.map((c) => {
                      const showExplain = contractorExplainId === c.contractor_id;
                      return (
                        <React.Fragment key={c.contractor_id}>
                          <tr>
                            <td className="px-4 py-2 text-sm text-gray-900">{c.name || c.company_name}</td>
                            <td className="px-4 py-2 text-sm text-gray-600">{(c.trade_types || []).join(', ') || '—'}</td>
                            <td className="px-4 py-2 text-sm text-gray-600">{clientLabel(c.client_id)}</td>
                            <td className="px-4 py-2 text-sm text-right">{c.performance_score != null ? Math.round(c.performance_score) : '—'}</td>
                            <td className="px-4 py-2 text-sm text-right">{c.reliability_score != null ? `${Math.round((c.reliability_score || 0) * 100)}%` : '—'}</td>
                            <td className="px-4 py-2 text-sm text-right">{c.sla_success_rate != null ? `${Math.round((c.sla_success_rate || 0) * 100)}%` : '—'}</td>
                            <td className="px-4 py-2 text-sm text-right">{c.invoice_approval_rate != null ? `${Math.round((c.invoice_approval_rate || 0) * 100)}%` : '—'}</td>
                            <td className="px-4 py-2 text-sm text-right">{c.assigned_jobs ?? 0} / {c.completed_jobs ?? 0}</td>
                            <td className="px-4 py-2">
                              <button
                                type="button"
                                className="text-xs text-electric-teal hover:underline flex items-center gap-0.5"
                                onClick={async () => {
                                  if (showExplain) {
                                    setContractorExplainId(null);
                                    setContractorExplainData(null);
                                    return;
                                  }
                                  setContractorExplainId(c.contractor_id);
                                  if (contractorExplainData && contractorExplainId === c.contractor_id) return;
                                  setContractorExplainData(null);
                                  setContractorExplainLoading(true);
                                  try {
                                    const res = await adminAPI.getContractorExplanation(c.contractor_id);
                                    setContractorExplainData(res.data);
                                  } catch {
                                    setContractorExplainData(null);
                                  } finally {
                                    setContractorExplainLoading(false);
                                  }
                                }}
                              >
                                <Info className="w-3 h-3" /> Why this matters {showExplain ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                              </button>
                            </td>
                          </tr>
                          {showExplain && (
                            <tr className="bg-gray-50">
                              <td colSpan={9} className="px-4 py-3 text-sm text-gray-700 border-t border-gray-100">
                                {contractorExplainLoading ? (
                                  <p className="flex items-center gap-1"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</p>
                                ) : contractorExplainData ? (
                                  <>
                                    <p className="font-medium text-gray-800 mb-1">Why this matters</p>
                                    <p>{contractorExplainData.why_it_matters}</p>
                                    <p className="font-medium text-midnight-blue mt-1">{contractorExplainData.recommended_action_text}</p>
                                  </>
                                ) : (
                                  <p>Could not load explanation.</p>
                                )}
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
                <div className="px-4 py-2 bg-gray-50 text-sm text-gray-600 border-t border-gray-200">
                  Showing {analyticsData.contractors.length} of {analyticsData.total}
                </div>
              </div>
            )}
          </div>
        ) : loading ? (
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
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Landlord network</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Status</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Portal access</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Vetted</th>
                  <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {contractors.map((c) => {
                  const canNetworkReview =
                    (c.source_type || '') === 'landlord_added' &&
                    c.submitted_to_network_at &&
                    !c.approved_for_network_at &&
                    !(c.network_submission_rejection_reason || '').trim();
                  const landlordNetworkLabel =
                    (c.source_type || '') !== 'landlord_added'
                      ? '—'
                      : (c.network_submission_rejection_reason || '').trim()
                        ? <span className="text-red-600">Rejected</span>
                        : c.approved_for_network_at
                          ? <span className="text-green-700">On network</span>
                          : c.submitted_to_network_at
                            ? <span className="text-amber-700">Pending review</span>
                            : '—';
                  return (
                  <tr key={c.contractor_id}>
                    <td className="px-4 py-2 text-sm text-gray-900">{c.name || c.company_name}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{(c.trade_types || []).join(', ') || '—'}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{clientLabel(c.client_id)}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{c.source_type || '—'}</td>
                    <td className="px-4 py-2 text-sm">{landlordNetworkLabel}</td>
                    <td className="px-4 py-2 text-sm">
                      {c.status === 'pending_review' && <span className="text-amber-600">Pending</span>}
                      {c.status === 'suspended' && <span className="text-red-600">Suspended</span>}
                      {c.status === 'active' && <span className="text-green-600">Active</span>}
                      {!c.status && '—'}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-700">
                      <div className="flex flex-col">
                        <span>{humanPortalAccess(c.portal_access_status)}</span>
                        {c.portal_invite_expires_at && (
                          <span className="text-xs text-gray-500">
                            Expires {new Date(c.portal_invite_expires_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2">{c.vetted ? <CheckCircle className="w-4 h-4 text-green-600" /> : '—'}</td>
                    <td className="px-4 py-2 text-right">
                      <div className="flex flex-wrap items-center justify-end gap-1">
                      {canNetworkReview && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-green-700 border-green-300 text-xs"
                            disabled={!!networkReviewApprovingId || !!networkReviewRejectingId}
                            onClick={async () => {
                              setNetworkReviewApprovingId(c.contractor_id);
                              try {
                                await adminAPI.approveContractorToNetwork(c.contractor_id);
                                toast.success('Contractor added to platform network.');
                                loadContractors();
                              } catch (e) {
                                toast.error(e.response?.data?.detail || 'Approve to network failed');
                              } finally {
                                setNetworkReviewApprovingId(null);
                              }
                            }}
                          >
                            {networkReviewApprovingId === c.contractor_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5 mr-1 inline" />}
                            Approve to network
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-red-700 border-red-200 text-xs"
                            disabled={!!networkReviewApprovingId || !!networkReviewRejectingId}
                            onClick={() => {
                              setNetworkRejectModal({ id: c.contractor_id, name: c.name || c.company_name || c.contractor_id });
                              setNetworkRejectReason('');
                            }}
                          >
                            <XCircle className="w-3.5 h-3.5 mr-1 inline" />
                            Reject
                          </Button>
                        </>
                      )}
                      {c.status === 'pending_review' && (
                        <Button variant="outline" size="sm" className="text-green-700 border-green-300" onClick={() => handleApprove(c.contractor_id)}>
                          Approve
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs"
                        title={!c.email ? 'Add an email to this contractor first' : 'Send contractor portal setup link'}
                        disabled={!c.email || !!invitingId}
                        onClick={async () => {
                          setInvitingId(c.contractor_id);
                          try {
                            const res = await adminAPI.inviteContractorToPortal(c.contractor_id);
                            const url = res.data?.setup_url;
                            toast.success(url ? 'Invite sent. Link: ' + url : 'Invite created. Contractor can set password via the link.');
                            loadContractors();
                          } catch (e) {
                            toast.error(e.response?.data?.detail || 'Invite failed');
                          } finally {
                            setInvitingId(null);
                          }
                        }}
                      >
                        {invitingId === c.contractor_id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Mail className="w-3.5 h-3.5 mr-1 inline" />
                        )}
                        Invite to portal
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs"
                        title={!c.email ? 'Add an email first' : 'Resend portal setup link'}
                        disabled={!c.email || !!resendingInviteId}
                        onClick={async () => {
                          setResendingInviteId(c.contractor_id);
                          try {
                            const res = await adminAPI.resendContractorPortalInvite(c.contractor_id);
                            const url = res.data?.setup_url;
                            toast.success(url ? `Invite resent. Link: ${url}` : 'Invite resent');
                            loadContractors();
                          } catch (e) {
                            toast.error(e.response?.data?.detail || 'Resend failed');
                          } finally {
                            setResendingInviteId(null);
                          }
                        }}
                      >
                        {resendingInviteId === c.contractor_id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <RefreshCw className="w-3.5 h-3.5 mr-1 inline" />
                        )}
                        Resend invite
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        title="Disable contractor portal access"
                        disabled={!!disablingAccessId}
                        onClick={async () => {
                          if (!window.confirm(`Disable portal access for "${c.name || c.company_name}"? This revokes active job links and requires reassignment for open jobs.`)) {
                            return;
                          }
                          setDisablingAccessId(c.contractor_id);
                          try {
                            const res = await adminAPI.disableContractorPortalAccess(c.contractor_id, { reason: 'Disabled by admin' });
                            const required = res.data?.reassignment_required_count || 0;
                            toast.success(`Portal access disabled. ${required} open job(s) require reassignment.`);
                            loadContractors();
                          } catch (e) {
                            toast.error(e.response?.data?.detail || 'Disable access failed');
                          } finally {
                            setDisablingAccessId(null);
                          }
                        }}
                      >
                        {disablingAccessId === c.contractor_id ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldOff className="w-4 h-4" />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        title="View assigned jobs"
                        onClick={async () => {
                          setAssignedJobsOpen(true);
                          setAssignedJobsFor(c);
                          setAssignedJobs([]);
                          setAssignedJobsLoading(true);
                          try {
                            const res = await adminAPI.getContractorAssignedJobs(c.contractor_id, { include_closed: false, limit: 300 });
                            setAssignedJobs(res.data?.jobs || []);
                          } catch (e) {
                            setAssignedJobs([]);
                            toast.error(e.response?.data?.detail || 'Failed to load assigned jobs');
                          } finally {
                            setAssignedJobsLoading(false);
                          }
                        }}
                      >
                        <Briefcase className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => openEdit(c)}><Pencil className="w-4 h-4" /></Button>
                      <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700" onClick={() => handleDelete(c.contractor_id, c.name || c.company_name)}><Trash2 className="w-4 h-4" /></Button>
                      </div>
                    </td>
                  </tr>
                );
                })}
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
      {assignedJobsOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Assigned jobs</h2>
            <p className="text-sm text-gray-600 mb-4">
              {assignedJobsFor ? `${assignedJobsFor.name || assignedJobsFor.company_name}` : 'Contractor'}
            </p>
            {assignedJobsLoading ? (
              <div className="flex items-center gap-2 text-gray-500 py-8">
                <Loader2 className="w-5 h-5 animate-spin" />
                Loading assigned jobs…
              </div>
            ) : assignedJobs.length === 0 ? (
              <p className="text-sm text-gray-600">No open assigned jobs.</p>
            ) : (
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left text-sm font-medium text-gray-700">Work order</th>
                      <th className="px-3 py-2 text-left text-sm font-medium text-gray-700">Status</th>
                      <th className="px-3 py-2 text-left text-sm font-medium text-gray-700">Property</th>
                      <th className="px-3 py-2 text-left text-sm font-medium text-gray-700">Client</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {assignedJobs.map((job) => (
                      <tr key={job.work_order_id}>
                        <td className="px-3 py-2 text-sm text-gray-900">{job.work_order_id}</td>
                        <td className="px-3 py-2 text-sm text-gray-700">{job.status || '—'}</td>
                        <td className="px-3 py-2 text-sm text-gray-700">{job.property_id || '—'}</td>
                        <td className="px-3 py-2 text-sm text-gray-700">{clientLabel(job.client_id)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="flex gap-2 pt-4">
              <Button type="button" variant="outline" onClick={() => setAssignedJobsOpen(false)}>Close</Button>
            </div>
          </div>
        </div>
      )}
      {networkRejectModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4" onClick={() => !networkReviewRejectingId && setNetworkRejectModal(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Reject network submission</h2>
            <p className="text-sm text-gray-600 mb-4">
              Rejection is recorded on the contractor and is visible to the submitting organisation on their Contractors page.
              {' '}
              <span className="font-medium text-gray-800">{networkRejectModal.name}</span>
            </p>
            <label className="block text-sm font-medium text-gray-700 mb-1">Reason (optional)</label>
            <textarea
              value={networkRejectReason}
              onChange={(e) => setNetworkRejectReason(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-2 w-full text-sm mb-4"
              rows={3}
              placeholder="Brief reason for the client"
            />
            <div className="flex gap-2 justify-end">
              <Button type="button" variant="outline" disabled={!!networkReviewRejectingId} onClick={() => setNetworkRejectModal(null)}>
                Cancel
              </Button>
              <Button
                type="button"
                className="bg-red-600 hover:bg-red-700 text-white"
                disabled={!!networkReviewRejectingId}
                onClick={async () => {
                  setNetworkReviewRejectingId(networkRejectModal.id);
                  try {
                    await adminAPI.rejectContractorNetworkSubmission(networkRejectModal.id, {
                      reason: networkRejectReason.trim() || undefined,
                    });
                    toast.success('Network submission rejected.');
                    setNetworkRejectModal(null);
                    loadContractors();
                  } catch (e) {
                    toast.error(e.response?.data?.detail || 'Reject failed');
                  } finally {
                    setNetworkReviewRejectingId(null);
                  }
                }}
              >
                {networkReviewRejectingId ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Confirm reject'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </UnifiedAdminLayout>
  );
}
