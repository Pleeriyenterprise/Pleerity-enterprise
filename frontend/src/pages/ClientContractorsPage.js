import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Briefcase, Loader2, AlertCircle, CheckCircle, Plus, Send, UserPlus, Eye } from 'lucide-react';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';

function sourceLabel(sourceType) {
  const s = (sourceType || '').toLowerCase();
  if (s === 'landlord_added') return { label: 'My contractor', class: 'bg-slate-100 text-slate-700' };
  if (s === 'platform_network') return { label: 'Network', class: 'bg-blue-100 text-blue-800' };
  if (s === 'self_registered') return { label: 'Marketplace', class: 'bg-emerald-100 text-emerald-800' };
  return { label: sourceType || '—', class: 'bg-gray-100 text-gray-600' };
}

export default function ClientContractorsPage() {
  return (
    <EntitlementProtectedRoute requiredFeature="contractor_network">
      <ClientContractorsPageInner />
    </EntitlementProtectedRoute>
  );
}

function ClientContractorsPageInner() {
  const navigate = useNavigate();
  const [contractors, setContractors] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('my'); // 'my' | 'network' | 'marketplace'
  const [addFormOpen, setAddFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submittingId, setSubmittingId] = useState(null);
  const [addForm, setAddForm] = useState({
    company_name: '',
    trade_types_text: '',
    phone: '',
    email: '',
    contact_name: '',
    region: '',
    credentials_text: '',
    insurance_details: '',
    areas_text: '',
    notes: '',
  });

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const params = { skip: 0, limit: 100 };
    if (activeTab === 'my') params.source_type = 'landlord_added';
    if (activeTab === 'network') params.source_type = 'platform_network';
    if (activeTab === 'marketplace') params.source_type = 'self_registered';
    clientAPI
      .getContractors(params)
      .then((res) => {
        setContractors(res.data?.contractors || []);
        setTotal(res.data?.total ?? 0);
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail;
        if (err?.response?.status === 403) {
          setError(detail || 'Contractor network is not enabled for your account.');
        } else {
          setError(detail || 'Failed to load contractors.');
        }
        setContractors([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [activeTab]);

  useEffect(() => {
    load();
  }, [load]);

  const parseList = (text) => (text || '').split(',').map((s) => s.trim()).filter(Boolean);

  const handleAddSubmit = (e) => {
    e.preventDefault();
    const payload = {
      company_name: addForm.company_name.trim(),
      trade_types: parseList(addForm.trade_types_text) || ['general'],
      phone: addForm.phone.trim() || null,
      email: addForm.email.trim() || null,
      contact_name: addForm.contact_name.trim() || null,
      region: addForm.region.trim() || null,
      credentials: parseList(addForm.credentials_text),
      insurance_details: addForm.insurance_details.trim() || null,
      areas_served: parseList(addForm.areas_text),
      notes: addForm.notes.trim() || null,
    };
    if (!payload.company_name) {
      toast.error('Company name is required');
      return;
    }
    if (!payload.phone && !payload.email) {
      toast.error('Phone or email is required');
      return;
    }
    setSaving(true);
    clientAPI.createContractor(payload)
      .then(() => {
        toast.success('Contractor added');
        setAddFormOpen(false);
        setAddForm({ company_name: '', trade_types_text: '', phone: '', email: '', contact_name: '', region: '', credentials_text: '', insurance_details: '', areas_text: '', notes: '' });
        load();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to add contractor'))
      .finally(() => setSaving(false));
  };

  const handleSubmitToNetwork = (contractorId) => {
    setSubmittingId(contractorId);
    clientAPI.submitContractorToNetwork(contractorId)
      .then(() => {
        toast.success('Contractor submitted for network review');
        load();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Submission failed'))
      .finally(() => setSubmittingId(null));
  };

  const getCardTitle = () => {
    if (activeTab === 'my') return 'My contractors';
    if (activeTab === 'network') return 'Network contractors';
    return 'Marketplace contractors';
  };

  const getEmptyMessage = () => {
    if (activeTab === 'my') return 'No contractors added yet. Click "Add contractor" to add your own trades.';
    if (activeTab === 'network') return 'No network contractors available. Your administrator can add platform network contractors from Operations & Compliance → Contractors.';
    return 'No marketplace contractors available yet. Self-registered contractors appear here after admin approval.';
  };

  if (error && !loading) {
    return (
      <div className="p-6 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-4">
          <Briefcase className="w-7 h-7" />
          Contractors
        </h1>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-amber-900">Contractor network not enabled</p>
              <p className="text-sm text-amber-800 mt-1">{error}</p>
              <p className="text-sm text-amber-700 mt-2">
                Contact your account administrator or support to enable the contractor network for your account.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-2">
        <Briefcase className="w-7 h-7" />
        Contractors
      </h1>
      <p className="text-gray-600 mb-4">
        Your added contractors and the platform network. Add your own trades or use network contractors for jobs.
      </p>

      <div className="flex flex-wrap gap-2 mb-4 items-center">
        <button
          type="button"
          onClick={() => setActiveTab('my')}
          className={`px-3 py-1.5 rounded text-sm font-medium ${activeTab === 'my' ? 'bg-electric-teal text-white' : 'bg-gray-100 text-gray-700'}`}
        >
          My Contractors
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('network')}
          className={`px-3 py-1.5 rounded text-sm font-medium ${activeTab === 'network' ? 'bg-electric-teal text-white' : 'bg-gray-100 text-gray-700'}`}
        >
          Network Contractors
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('marketplace')}
          className={`px-3 py-1.5 rounded text-sm font-medium ${activeTab === 'marketplace' ? 'bg-electric-teal text-white' : 'bg-gray-100 text-gray-700'}`}
        >
          Marketplace
        </button>
        {activeTab === 'my' && (
          <Button size="sm" className="ml-auto bg-electric-teal hover:bg-electric-teal/90" onClick={() => setAddFormOpen(true)}>
            <Plus className="w-4 h-4 mr-1" />
            Add contractor
          </Button>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{getCardTitle()}</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : contractors.length === 0 ? (
            <p className="text-gray-500 py-6">
              {getEmptyMessage()}
            </p>
          ) : (
            <ul className="space-y-3">
              {contractors.map((c) => {
                const src = sourceLabel(c.source_type);
                const isMy = (c.source_type || '').toLowerCase() === 'landlord_added';
                const canSubmitToNetwork = isMy && !c.submitted_to_network_at;
                return (
                  <li
                    key={c.contractor_id}
                    className="flex flex-wrap items-center justify-between gap-2 p-3 bg-gray-50 rounded-lg border border-gray-100"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-900 flex items-center gap-2 flex-wrap">
                        {c.name}
                        <span className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded ${src.class}`}>
                          {src.label}
                        </span>
                        {c.vetted && (
                          <span className="inline-flex items-center gap-1 text-xs text-green-700 bg-green-100 px-1.5 py-0.5 rounded">
                            <CheckCircle className="w-3.5 h-3.5" />
                            Vetted
                          </span>
                        )}
                        {c.submitted_to_network_at && !c.approved_for_network_at && !(c.network_submission_rejection_reason || '').trim() && (
                          <span className="text-xs text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded">Submitted for review</span>
                        )}
                        {(c.network_submission_rejection_reason || '').trim() && (
                          <span className="text-xs text-red-700 bg-red-50 px-1.5 py-0.5 rounded">Network review declined</span>
                        )}
                        {c.approved_for_network_at && (
                          <span className="text-xs text-green-800 bg-green-50 px-1.5 py-0.5 rounded">On platform network</span>
                        )}
                      </p>
                      {(c.network_submission_rejection_reason || '').trim() && (
                        <p className="text-xs text-red-800 mt-1 max-w-xl">{c.network_submission_rejection_reason}</p>
                      )}
                      {c.company_name && <p className="text-sm text-gray-600">{c.company_name}</p>}
                      {(c.trade_types?.length > 0) && (
                        <p className="text-xs text-gray-500 mt-1">
                          {c.trade_types.join(', ')}
                        </p>
                      )}
                      {(c.phone || c.email) && (
                        <p className="text-xs text-gray-500 mt-0.5">
                          {[c.phone, c.email].filter(Boolean).join(' · ')}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1.5 items-center shrink-0">
                      <Button size="sm" variant="outline" onClick={() => navigate('/operations/work-orders')}>
                        <UserPlus className="w-3.5 h-3.5 mr-1" />
                        Assign
                      </Button>
                      {(activeTab === 'network' || activeTab === 'marketplace') && (
                        <Button size="sm" variant="ghost" onClick={() => navigate('/operations/work-orders')}>
                          <Eye className="w-3.5 h-3.5 mr-1" />
                          View
                        </Button>
                      )}
                      {canSubmitToNetwork && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSubmitToNetwork(c.contractor_id)}
                          disabled={submittingId === c.contractor_id}
                        >
                          {submittingId === c.contractor_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5 mr-1" />}
                          Submit to Network
                        </Button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          {total > 0 && <p className="text-sm text-gray-500 mt-2">Total: {total}</p>}
        </CardContent>
      </Card>

      {addFormOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Add contractor</h2>
            <p className="text-sm text-gray-600 mb-4">Add a contractor visible only to your organisation. Phone or email required.</p>
            <form onSubmit={handleAddSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Company name *</label>
                <input
                  type="text"
                  value={addForm.company_name}
                  onChange={(e) => setAddForm((f) => ({ ...f, company_name: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Trade types (comma-separated)</label>
                <input
                  type="text"
                  value={addForm.trade_types_text}
                  onChange={(e) => setAddForm((f) => ({ ...f, trade_types_text: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  placeholder="e.g. plumbing, electrical, gas"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Contact name</label>
                <input
                  type="text"
                  value={addForm.contact_name}
                  onChange={(e) => setAddForm((f) => ({ ...f, contact_name: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                <input
                  type="text"
                  value={addForm.phone}
                  onChange={(e) => setAddForm((f) => ({ ...f, phone: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  value={addForm.email}
                  onChange={(e) => setAddForm((f) => ({ ...f, email: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Region</label>
                <input
                  type="text"
                  value={addForm.region}
                  onChange={(e) => setAddForm((f) => ({ ...f, region: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Credentials (comma-separated)</label>
                <input
                  type="text"
                  value={addForm.credentials_text}
                  onChange={(e) => setAddForm((f) => ({ ...f, credentials_text: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  placeholder="e.g. Gas Safe, NICEIC"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Insurance details</label>
                <textarea
                  value={addForm.insurance_details}
                  onChange={(e) => setAddForm((f) => ({ ...f, insurance_details: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Areas served (comma-separated)</label>
                <input
                  type="text"
                  value={addForm.areas_text}
                  onChange={(e) => setAddForm((f) => ({ ...f, areas_text: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                <textarea
                  value={addForm.notes}
                  onChange={(e) => setAddForm((f) => ({ ...f, notes: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  rows={2}
                />
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="submit" disabled={saving} className="bg-electric-teal hover:bg-electric-teal/90">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Add'}
                </Button>
                <Button type="button" variant="outline" onClick={() => setAddFormOpen(false)}>Cancel</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
