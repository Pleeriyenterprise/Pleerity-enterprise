import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Briefcase, Loader2, AlertCircle, CheckCircle, Send, UserPlus, Eye } from 'lucide-react';
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
  const [submittingId, setSubmittingId] = useState(null);

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
    if (activeTab === 'my') {
      return (
        <>
          No contractors in your list yet. To add someone new, open a job under Operations (maintenance or compliance) and use{' '}
          <span className="font-medium">Add contractor & assign</span> in the assignment section (
          <Link to="/operations/work-orders" className="text-electric-teal hover:underline">
            Operations → Jobs
          </Link>
          ).
        </>
      );
    }
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
        Browse contractors already on your account, the platform network, and the marketplace. New contacts are added when you assign someone on a job (open any job from Operations → Jobs), so details stay tied to the right property and workflow.
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
            <div className="text-gray-500 py-6 text-sm leading-relaxed">
              {getEmptyMessage()}
            </div>
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
                        Open jobs
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
    </div>
  );
}
