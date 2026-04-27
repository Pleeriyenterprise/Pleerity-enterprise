import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useSearchParams, useLocation, Link } from 'react-router-dom';
import api, { adminAPI, parseApiError, parseStructuredApiDetail } from '../api/client';
import { useStepUpApi } from '../hooks/useStepUpApi';
import { toast } from '@/utils/portalNotifications';
import { jurisdictionSourceLabel } from '../utils/jurisdictionComplianceCopy';
import { presentScoreChangeReason } from '../utils/timelinePresent';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import AccountEnvironmentBadge from '../components/admin/AccountEnvironmentBadge';
import {
  accountEnvironmentActionNote,
  clientOrgPermanentDeleteHint,
  isNonProductionAccount,
  NON_PRODUCTION_ACCOUNT_LABEL,
  PRODUCTION_ACCOUNT_LABEL,
} from '../utils/adminAccountClassification';
import { 
  LayoutDashboard, 
  Users, 
  User,
  FileText, 
  FileCheck,
  Mail, 
  Clock, 
  Play,
  RefreshCw,
  ChevronRight,
  CheckCircle,
  XCircle,
  AlertCircle,
  LogOut,
  Search,
  Filter,
  Eye,
  Send,
  Calendar,
  Building2,
  Shield,
  Activity,
  BookOpen,
  Plus,
  Edit,
  Trash2,
  Save,
  X,
  BarChart3,
  TrendingUp,
  PieChart,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  UserCog,
  UserPlus,
  RotateCcw,
  Download,
  MailPlus,
  Archive,
  MessageSquare,
  History,
  Settings,
  ClipboardCheck,
  ExternalLink,
  Sparkles,
  CreditCard,
  Copy,
  Upload
} from 'lucide-react';

/** Normalize API error detail (string or FastAPI validation array) for toast messages. */
function normalizeErrorDetail(detail, fallback) {
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail) && detail.message) {
    const b = detail.blockers;
    if (Array.isArray(b) && b.length > 0) {
      return `${detail.message}: ${b.join(', ')}`;
    }
    return detail.message;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    return first.msg || (first.loc && first.loc.join('. ')) || String(first);
  }
  return fallback;
}

const ADMIN_CLIENT_LIFECYCLE_BUCKETS = [
  { id: 'active', label: 'Active' },
  { id: 'pending_setup', label: 'Pending setup' },
  { id: 'suspended', label: 'Suspended' },
  { id: 'archived', label: 'Archived' },
  { id: 'purge_eligible', label: 'Purge eligible' },
  { id: 'test_like', label: 'Test / Dummy / Pre-production' },
  { id: 'all', label: 'All' },
];

function adminEnterpriseLifecycleBadgeClass(derived) {
  const d = (derived || '').toUpperCase();
  if (d === 'ARCHIVED' || d === 'PURGE_ELIGIBLE') return 'bg-slate-200 text-slate-800';
  if (d === 'ACTIVE') return 'bg-emerald-100 text-emerald-900';
  if (d === 'SUSPENDED') return 'bg-amber-100 text-amber-900';
  if (d === 'LEAD') return 'bg-violet-100 text-violet-900';
  return 'bg-sky-100 text-sky-900';
}

// Global Search Component
function globalSearchInactiveLabel(client) {
  const st = (client.client_lifecycle_status || '').toUpperCase();
  if (client.is_deleted || st === 'ARCHIVED' || st === 'PURGE_ELIGIBLE') return 'Archived';
  if (st === 'SUSPENDED') return 'Suspended';
  return null;
}

const GlobalSearch = ({ onSelectClient }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);
  const searchRef = useRef(null);
  const debounceTimer = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearch = useCallback(async (searchTerm) => {
    if (!searchTerm || searchTerm.length < 2) {
      setResults([]);
      return;
    }

    setLoading(true);
    try {
      const params = new URLSearchParams({
        q: searchTerm,
        limit: '10',
        ...(includeArchived ? { include_archived: 'true' } : {}),
      });
      const response = await api.get(`/admin/search?${params.toString()}`);
      setResults(response.data.results || []);
      setIsOpen(true);
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [includeArchived]);

  const handleInputChange = (e) => {
    const value = e.target.value;
    setQuery(value);

    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }
    debounceTimer.current = setTimeout(() => {
      handleSearch(value);
    }, 300);
  };

  const toggleIncludeArchived = (checked) => {
    setIncludeArchived(checked);
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }
    if (query.trim().length >= 2) {
      debounceTimer.current = setTimeout(() => handleSearch(query.trim()), 150);
    }
  };

  const handleSelectResult = (client) => {
    setQuery('');
    setResults([]);
    setIsOpen(false);
    onSelectClient(client);
  };

  return (
    <div ref={searchRef} className="relative" data-testid="global-search">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          value={query}
          onChange={handleInputChange}
          placeholder="Search by CRN, email, name, postcode..."
          className="w-64 pl-10 pr-4 py-2 bg-white/10 border border-white/20 rounded-lg text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-electric-teal focus:border-transparent"
          data-testid="global-search-input"
        />
        {loading && (
          <RefreshCw className="absolute right-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400 animate-spin" />
        )}
      </div>
      <label className="flex items-center gap-2 mt-1.5 text-[11px] text-white/75 cursor-pointer select-none max-w-64">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => toggleIncludeArchived(e.target.checked)}
          className="rounded border-white/40 bg-white/10 text-electric-teal focus:ring-electric-teal"
          data-testid="global-search-include-archived"
        />
        Include archived &amp; suspended
      </label>

      {isOpen && results.length > 0 && (
        <div className="absolute top-full left-0 mt-2 w-96 bg-white rounded-xl shadow-lg border border-gray-200 z-50 overflow-hidden" data-testid="search-results">
          <div className="p-2 text-xs text-gray-500 border-b border-gray-100">
            {results.length} result{results.length !== 1 ? 's' : ''} found
            {!includeArchived ? <span className="block text-[10px] text-gray-400 mt-0.5">Archived / suspended hidden — enable above to find them</span> : null}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {results.map((client) => {
              const inactiveLabel = includeArchived ? globalSearchInactiveLabel(client) : null;
              return (
              <button
                key={client.client_id}
                onClick={() => handleSelectResult(client)}
                className="w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-0"
                data-testid={`search-result-${client.client_id}`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-midnight-blue flex flex-wrap items-center gap-1.5">
                      {client.full_name}
                      <AccountEnvironmentBadge doc={client} />
                      {inactiveLabel ? (
                        <span className="text-[10px] font-normal px-1.5 py-0 rounded bg-slate-200 text-slate-700">
                          {inactiveLabel}
                        </span>
                      ) : null}
                    </p>
                    <p className="text-sm text-gray-500">{client.email}</p>
                  </div>
                  <div className="text-right">
                    {client.customer_reference && (
                      <span className="inline-block px-2 py-1 bg-electric-teal/10 text-electric-teal text-xs font-mono rounded">
                        {client.customer_reference}
                      </span>
                    )}
                    {client.matched_via === 'postcode' && (
                      <p className="text-xs text-gray-400 mt-1">via {client.matched_postcode}</p>
                    )}
                  </div>
                </div>
              </button>
              );
            })}
          </div>
        </div>
      )}

      {isOpen && query.length >= 2 && results.length === 0 && !loading && (
        <div className="absolute top-full left-0 mt-2 w-96 bg-white rounded-xl shadow-lg border border-gray-200 z-50 p-4 text-center text-gray-500 text-sm">
          <p>No results found</p>
          {!includeArchived ? (
            <p className="text-[11px] text-gray-400 mt-2">Try &quot;Include archived &amp; suspended&quot; if this is a dormant account.</p>
          ) : null}
        </div>
      )}
    </div>
  );
};

// Client Detail Modal Component
const ClientDetailModal = ({ clientId, onClose }) => {
  const [client, setClient] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState('overview');
  const [messageForm, setMessageForm] = useState({ subject: '', message: '', send_copy_to_admin: false });
  const [sendingMessage, setSendingMessage] = useState(false);
  const [profileForm, setProfileForm] = useState({});
  const [savingProfile, setSavingProfile] = useState(false);
  const [triggeringProvision, setTriggeringProvision] = useState(false);
  const [resendingPassword, setResendingPassword] = useState(false);
  const [lastResendActivationLink, setLastResendActivationLink] = useState(null);
  const [lastResendMessageId, setLastResendMessageId] = useState(null);
  const [sendingPaymentLink, setSendingPaymentLink] = useState(false);
  const [selectedPropertyId, setSelectedPropertyId] = useState(null);
  const [scoreHistoryData, setScoreHistoryData] = useState(null);
  const [scoreHistoryLoading, setScoreHistoryLoading] = useState(false);
  const [scoreHistoryError, setScoreHistoryError] = useState(null);
  const [fullHistoryModal, setFullHistoryModal] = useState(null);
  const [uploadPropertyId, setUploadPropertyId] = useState('');
  const [uploadRequirementId, setUploadRequirementId] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadingDocument, setUploadingDocument] = useState(false);
  const [clientAvatarUrl, setClientAvatarUrl] = useState(null);

  const fetchClientData = useCallback(async () => {
    if (!clientId) return;
    setLoading(true);
    try {
      const [detailRes, readinessRes, timelineRes] = await Promise.all([
        api.get(`/admin/clients/${clientId}`),
        api.get(`/admin/clients/${clientId}/readiness`),
        api.get(`/admin/clients/${clientId}/audit-timeline?limit=30`)
      ]);
      
      const data = detailRes.data;
      const c = data?.client;
      setClient(data);
      setReadiness(readinessRes.data);
      setTimeline(timelineRes.data.timeline || []);
      if (c && typeof c === 'object') {
        setProfileForm({
          full_name: c.full_name || '',
          phone: c.phone || '',
          company_name: c.company_name || '',
          preferred_contact: c.preferred_contact || 'EMAIL'
        });
      }
      if (c?.avatar_ext || c?.avatar_updated_at) {
        api.get(`/admin/clients/${clientId}/avatar`, { responseType: 'blob' })
          .then((av) => {
            setClientAvatarUrl((prev) => {
              if (prev) URL.revokeObjectURL(prev);
              return URL.createObjectURL(av.data);
            });
          })
          .catch(() => setClientAvatarUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev);
            return null;
          }));
      } else {
        setClientAvatarUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return null;
        });
      }
    } catch (error) {
      toast.error('Failed to load client data');
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    if (clientId) {
      fetchClientData();
      setSelectedPropertyId(null);
      setScoreHistoryData(null);
      setScoreHistoryError(null);
      setFullHistoryModal(null);
      setLastResendActivationLink(null);
      setUploadPropertyId('');
      setUploadRequirementId('');
      setUploadFile(null);
      setClientAvatarUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    }
  }, [clientId, fetchClientData]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!messageForm.subject || !messageForm.message) {
      toast.error('Please fill in subject and message');
      return;
    }

    setSendingMessage(true);
    try {
      await api.post(`/admin/clients/${clientId}/message`, messageForm);
      toast.success('Message sent successfully');
      setMessageForm({ subject: '', message: '', send_copy_to_admin: false });
      fetchClientData(); // Refresh timeline
    } catch (error) {
      toast.error('Failed to send message');
    } finally {
      setSendingMessage(false);
    }
  };

  const handleSaveProfile = async () => {
    setSavingProfile(true);
    try {
      await api.patch(`/admin/clients/${clientId}/profile`, profileForm);
      toast.success('Profile updated successfully');
      fetchClientData();
    } catch (error) {
      toast.error('Failed to update profile');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleTriggerProvision = async () => {
    if (!window.confirm('Trigger provisioning for this client? This will set up their portal access.')) return;
    
    setTriggeringProvision(true);
    try {
      await api.post(`/admin/clients/${clientId}/provision`);
      toast.success('Provisioning triggered successfully');
      fetchClientData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to trigger provisioning');
    } finally {
      setTriggeringProvision(false);
    }
  };

  const handleResendPassword = async () => {
    if (!window.confirm('Resend password setup link? This will revoke any existing tokens.')) return;
    
    setResendingPassword(true);
    setLastResendActivationLink(null);
    setLastResendMessageId(null);
    try {
      const res = await api.post(`/admin/clients/${clientId}/resend-password-setup`);
      toast.success(res?.data?.message || 'Password setup link resent');
      if (res?.data?.activation_link) {
        setLastResendActivationLink(res.data.activation_link);
      } else {
        setLastResendActivationLink(null);
      }
      if (res?.data?.message_id) {
        setLastResendMessageId(res.data.message_id);
      } else {
        setLastResendMessageId(null);
      }
      fetchClientData();
    } catch (error) {
      const detail = error.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : (detail?.message || 'Failed to resend password link');
      toast.error(msg);
    } finally {
      setResendingPassword(false);
    }
  };

  const handleCopyActivationLink = () => {
    if (!lastResendActivationLink) return;
    navigator.clipboard.writeText(lastResendActivationLink).then(
      () => toast.success('Activation link copied to clipboard'),
      () => toast.error('Copy failed')
    );
  };

  const handleSendPaymentLink = async () => {
    setSendingPaymentLink(true);
    try {
      const res = await api.post(`/admin/intake/${clientId}/send-payment-link`);
      toast.success(res?.data?.checkout_url ? 'Payment link created' : 'Payment link sent');
      fetchClientData();
    } catch (error) {
      const detail = error.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : detail?.message || 'Failed to send payment link';
      toast.error(msg);
    } finally {
      setSendingPaymentLink(false);
    }
  };

  const handleCopyPaymentLink = () => {
    const url = client?.client?.latest_checkout_url;
    if (!url) return;
    navigator.clipboard.writeText(url).then(() => toast.success('Link copied to clipboard')).catch(() => toast.error('Copy failed'));
  };

  const handleUploadDocument = async (e) => {
    e.preventDefault();
    if (!uploadPropertyId || !uploadRequirementId || !uploadFile || !clientId) {
      toast.error('Please select property, requirement, and a file');
      return;
    }
    setUploadingDocument(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('client_id', clientId);
      formData.append('property_id', uploadPropertyId);
      formData.append('requirement_id', uploadRequirementId);
      await api.post('/documents/admin/upload', formData);
      toast.success('Document uploaded successfully');
      setUploadFile(null);
      setUploadRequirementId('');
      setUploadPropertyId('');
      if (document.getElementById('admin-upload-file-input')) document.getElementById('admin-upload-file-input').value = '';
      fetchClientData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : (detail?.message || 'Failed to upload document');
      toast.error(msg);
    } finally {
      setUploadingDocument(false);
    }
  };

  const paymentCompleteItem = readiness?.checklist?.find((i) => i.item === 'payment_complete');
  const showPaymentLinkActions = paymentCompleteItem?.status !== 'complete';

  const fetchComplianceScoreHistory = useCallback(async (propertyId, limit = 20) => {
    if (!propertyId) return null;
    setScoreHistoryLoading(true);
    setScoreHistoryError(null);
    try {
      const res = await adminAPI.getComplianceScoreHistory(propertyId, limit);
      return res?.data ?? null;
    } catch (err) {
      const status = err.response?.status;
      const msg = status === 403 || status === 401
        ? 'Not authorized'
        : (err.response?.data?.detail ?? (typeof err.response?.data?.message === 'string' ? err.response.data.message : 'Failed to load score history'));
      setScoreHistoryError(msg);
      toast.error(msg);
      return null;
    } finally {
      setScoreHistoryLoading(false);
    }
  }, []);

  const handleViewScoreHistory = useCallback(async (propertyId) => {
    setSelectedPropertyId(propertyId);
    setScoreHistoryData(null);
    const data = await fetchComplianceScoreHistory(propertyId, 20);
    if (data) setScoreHistoryData(data);
  }, [fetchComplianceScoreHistory]);

  const handleViewFullHistory = useCallback(async () => {
    if (!selectedPropertyId) return;
    setScoreHistoryLoading(true);
    try {
      const data = await fetchComplianceScoreHistory(selectedPropertyId, 200);
      if (data?.history?.length) setFullHistoryModal(data.history);
      else setFullHistoryModal([]);
    } finally {
      setScoreHistoryLoading(false);
    }
  }, [selectedPropertyId, fetchComplianceScoreHistory]);

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-xl p-8">
          <RefreshCw className="w-8 h-8 animate-spin text-electric-teal mx-auto" />
          <p className="text-gray-500 mt-4">Loading client details...</p>
        </div>
      </div>
    );
  }

  if (!client) return null;

  const c = client?.client;
  if (!c || typeof c !== 'object') return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto py-8" data-testid="client-detail-modal">
      <div className="bg-white rounded-xl w-full max-w-5xl mx-4 shadow-xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-midnight-blue text-white p-6 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-4">
            {clientAvatarUrl ? (
              <div className="w-14 h-14 rounded-full overflow-hidden border-2 border-white/30 flex-shrink-0">
                <img src={clientAvatarUrl} alt="" className="w-full h-full object-cover" />
              </div>
            ) : (
              <div className="w-14 h-14 rounded-full bg-electric-teal/30 flex items-center justify-center flex-shrink-0">
                <User className="w-8 h-8 text-white/80" />
              </div>
            )}
            <div>
              <h2 className="text-xl font-bold">{c.full_name}</h2>
              <div className="flex items-center gap-4 mt-1 text-sm text-gray-300">
              <span>{c.email}</span>
              {c.customer_reference && (
                <span className="px-2 py-0.5 bg-electric-teal/20 text-electric-teal rounded font-mono">
                  {c.customer_reference}
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
            data-testid="close-client-detail"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200 px-6 flex-shrink-0">
          <div className="flex gap-6">
            {[
              { id: 'overview', label: 'Overview', icon: Eye },
              { id: 'setup', label: 'Setup Controls', icon: Settings },
              { id: 'upload', label: 'Upload document', icon: Upload },
              { id: 'messaging', label: 'Messaging', icon: MessageSquare },
              { id: 'timeline', label: 'Audit Timeline', icon: History }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveSection(tab.id)}
                className={`flex items-center gap-2 py-4 border-b-2 transition-colors ${
                  activeSection === tab.id
                    ? 'border-electric-teal text-electric-teal'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
                data-testid={`client-tab-${tab.id}`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeSection === 'overview' && (
            <div className="space-y-6">
              {/* Client Info */}
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h3 className="font-semibold text-midnight-blue">Client Information</h3>
                  <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                    <div><span className="text-gray-500 text-sm">Type:</span> <span className="font-medium">{c.client_type}</span></div>
                    <div><span className="text-gray-500 text-sm">Company:</span> <span className="font-medium">{c.company_name || '—'}</span></div>
                    <div><span className="text-gray-500 text-sm">Phone:</span> <span className="font-medium">{c.phone || '—'}</span></div>
                    <div><span className="text-gray-500 text-sm">Plan:</span> <span className="font-medium">{c.billing_plan}</span></div>
                  </div>
                </div>
                <div className="space-y-4">
                  <h3 className="font-semibold text-midnight-blue">Status</h3>
                  <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="text-gray-500 text-sm">Subscription:</span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        c.subscription_status === 'ACTIVE' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                      }`}>{c.subscription_status}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-gray-500 text-sm">Onboarding:</span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        c.onboarding_status === 'PROVISIONED' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                      }`}>{c.onboarding_status}</span>
                    </div>
                    <div><span className="text-gray-500 text-sm">Created:</span> <span className="font-medium">{new Date(c.created_at).toLocaleDateString()}</span></div>
                  </div>
                </div>
              </div>

              {/* Compliance Summary */}
              <div>
                <h3 className="font-semibold text-midnight-blue mb-4">Compliance Summary</h3>
                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-gray-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-midnight-blue">{client.compliance_summary?.total || 0}</p>
                    <p className="text-sm text-gray-500">Total Requirements</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-green-600">{client.compliance_summary?.compliant || 0}</p>
                    <p className="text-sm text-green-700">Compliant</p>
                  </div>
                  <div className="bg-amber-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-amber-600">{client.compliance_summary?.expiring_soon || 0}</p>
                    <p className="text-sm text-amber-700">Expiring Soon</p>
                  </div>
                  <div className="bg-red-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-red-600">{client.compliance_summary?.overdue || 0}</p>
                    <p className="text-sm text-red-700">Overdue</p>
                  </div>
                </div>
              </div>

              {/* Properties */}
              <div>
                <h3 className="font-semibold text-midnight-blue mb-4">Properties ({client.properties?.length || 0})</h3>
                <div className="space-y-2">
                  {(client.properties ?? []).slice(0, 5).map((prop) => (
                    <div key={prop.property_id} className="flex items-center justify-between bg-gray-50 rounded-lg p-3">
                      <div>
                        <p className="font-medium">{prop.nickname || prop.address_line_1}</p>
                        <p className="text-sm text-gray-500">{prop.postcode}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          prop.compliance_status === 'GREEN' ? 'bg-green-100 text-green-700' :
                          prop.compliance_status === 'AMBER' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'
                        }`}>{prop.compliance_status}</span>
                        <button
                          type="button"
                          onClick={() => handleViewScoreHistory(prop.property_id)}
                          className="text-xs text-electric-teal hover:underline font-medium"
                          data-testid={`view-score-history-${prop.property_id}`}
                        >
                          Score history
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Compliance panel (property-level, when a property is selected) */}
              {selectedPropertyId && (
                <div className="border-t pt-6 mt-6">
                  <h3 className="font-semibold text-midnight-blue mb-4">Compliance</h3>
                  {scoreHistoryLoading && !scoreHistoryData && (
                    <div className="space-y-2">
                      <div className="h-4 bg-gray-200 rounded w-48 animate-pulse" />
                      <div className="overflow-x-auto rounded-lg border border-gray-200">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="px-4 py-2 text-left font-medium text-gray-600">Timestamp</th>
                              <th className="px-4 py-2 text-left font-medium text-gray-600">Score</th>
                              <th className="px-4 py-2 text-left font-medium text-gray-600">Trigger reason</th>
                              <th className="px-4 py-2 text-left font-medium text-gray-600">Actor</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-200">
                            {[1, 2, 3, 4, 5].map((i) => (
                              <tr key={i}>
                                <td className="px-4 py-2"><span className="inline-block h-4 bg-gray-100 rounded w-32 animate-pulse" /></td>
                                <td className="px-4 py-2"><span className="inline-block h-4 bg-gray-100 rounded w-8 animate-pulse" /></td>
                                <td className="px-4 py-2"><span className="inline-block h-4 bg-gray-100 rounded w-24 animate-pulse" /></td>
                                <td className="px-4 py-2"><span className="inline-block h-4 bg-gray-100 rounded w-16 animate-pulse" /></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                  {scoreHistoryError && !scoreHistoryData && (
                    <div className="space-y-2">
                      <p className="text-sm text-red-600">{scoreHistoryError}</p>
                      <button
                        type="button"
                        onClick={() => handleViewScoreHistory(selectedPropertyId)}
                        className="text-sm font-medium text-electric-teal hover:underline"
                        data-testid="retry-score-history"
                      >
                        Retry
                      </button>
                    </div>
                  )}
                  {scoreHistoryData && (
                    <>
                      <div className="mb-4">
                        <p className="text-sm font-medium text-gray-700 mb-1">Current Compliance Score</p>
                        <p className="text-sm text-gray-600">
                          <span className="font-semibold">{scoreHistoryData.current_score ?? '—'}</span>
                          {scoreHistoryData.last_calculated_at && (
                            <span className="text-gray-500 ml-2">
                              (last calculated {new Date(scoreHistoryData.last_calculated_at).toLocaleString()})
                            </span>
                          )}
                        </p>
                      </div>
                      <p className="text-sm font-medium text-gray-700 mb-2">Compliance Score History</p>
                      {(scoreHistoryData.history ?? []).length === 0 ? (
                        <p className="text-sm text-gray-500 py-4">No compliance score history recorded yet.</p>
                      ) : (
                        <>
                          <div className="overflow-x-auto rounded-lg border border-gray-200">
                            <table className="w-full text-sm">
                              <thead className="bg-gray-50">
                                <tr>
                                  <th className="px-4 py-2 text-left font-medium text-gray-600">Timestamp</th>
                                  <th className="px-4 py-2 text-left font-medium text-gray-600">Score</th>
                                  <th className="px-4 py-2 text-left font-medium text-gray-600">Trigger reason</th>
                                  <th className="px-4 py-2 text-left font-medium text-gray-600">Actor</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-200">
                                {(scoreHistoryData.history ?? []).map((row, idx) => {
                                  const pr = presentScoreChangeReason(row.reason);
                                  return (
                                  <tr key={idx}>
                                    <td className="px-4 py-2">{row.created_at ? new Date(row.created_at).toLocaleString() : '—'}</td>
                                    <td className="px-4 py-2 font-medium">{row.score ?? '—'}</td>
                                    <td className="px-4 py-2" title={pr.description || undefined}>
                                      <span className="text-gray-900">{pr.title}</span>
                                      {pr.description ? <span className="block text-xs text-gray-500 mt-0.5">{pr.description}</span> : null}
                                    </td>
                                    <td className="px-4 py-2">{row.actor?.role === 'SYSTEM' ? 'System' : (row.actor?.id ?? row.actor?.role ?? '—')}</td>
                                  </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                          {(scoreHistoryData.history ?? []).length >= 20 && (
                            <button
                              type="button"
                              onClick={handleViewFullHistory}
                              disabled={scoreHistoryLoading}
                              className="mt-3 flex items-center gap-2 text-sm text-electric-teal hover:underline font-medium disabled:opacity-50"
                              data-testid="view-full-score-history"
                            >
                              {scoreHistoryLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <History className="w-4 h-4" />}
                              View Full History
                            </button>
                          )}
                        </>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* Full History Modal */}
              {fullHistoryModal !== null && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4" data-testid="full-history-modal">
                  <div className="bg-white rounded-xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col shadow-xl">
                    <div className="flex items-center justify-between p-4 border-b">
                      <h3 className="font-semibold text-midnight-blue">Compliance Score History (full)</h3>
                      <button type="button" onClick={() => setFullHistoryModal(null)} className="p-2 hover:bg-gray-100 rounded-lg">
                        <X className="w-5 h-5" />
                      </button>
                    </div>
                    <div className="overflow-auto flex-1 p-4">
                      {fullHistoryModal.length === 0 ? (
                        <p className="text-sm text-gray-500">No compliance score history recorded yet.</p>
                      ) : (
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50 sticky top-0">
                            <tr>
                              <th className="px-4 py-2 text-left font-medium text-gray-600">Timestamp</th>
                              <th className="px-4 py-2 text-left font-medium text-gray-600">Score</th>
                              <th className="px-4 py-2 text-left font-medium text-gray-600">Trigger reason</th>
                              <th className="px-4 py-2 text-left font-medium text-gray-600">Actor</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-200">
                            {fullHistoryModal.map((row, idx) => {
                              const pr = presentScoreChangeReason(row.reason);
                              return (
                              <tr key={idx}>
                                <td className="px-4 py-2">{row.created_at ? new Date(row.created_at).toLocaleString() : '—'}</td>
                                <td className="px-4 py-2 font-medium">{row.score ?? '—'}</td>
                                <td className="px-4 py-2">
                                  <span className="text-gray-900">{pr.title}</span>
                                  {pr.description ? <span className="block text-xs text-gray-500 mt-0.5">{pr.description}</span> : null}
                                </td>
                                <td className="px-4 py-2">{row.actor?.role === 'SYSTEM' ? 'System' : (row.actor?.id ?? row.actor?.role ?? '—')}</td>
                              </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeSection === 'setup' && (
            <div className="space-y-6">
              {/* Readiness Checklist */}
              <div>
                <h3 className="font-semibold text-midnight-blue mb-4 flex items-center gap-2">
                  <ClipboardCheck className="w-5 h-5" />
                  Readiness Checklist
                </h3>
                <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                  {(readiness?.checklist ?? []).map((item) => (
                    <div key={item.item} className="flex items-center gap-3">
                      {item.status === 'complete' ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : item.status === 'failed' ? (
                        <XCircle className="w-5 h-5 text-red-500" />
                      ) : (
                        <Clock className="w-5 h-5 text-amber-500" />
                      )}
                      <span className={item.status === 'complete' ? 'text-gray-700' : 'text-gray-500'}>{item.label}</span>
                      {item.required && <span className="text-xs text-red-500">*required</span>}
                    </div>
                  ))}
                </div>
                {readiness?.last_failure && (
                  <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-sm font-medium text-red-700">Last Failure</p>
                    <p className="text-sm text-red-600">{readiness.last_failure.reason}</p>
                    <p className="text-xs text-red-500 mt-1">{new Date(readiness.last_failure.timestamp).toLocaleString()}</p>
                  </div>
                )}
              </div>

              {/* Setup Actions */}
              <div>
                <h3 className="font-semibold text-midnight-blue mb-4">Setup Actions</h3>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={handleTriggerProvision}
                    disabled={triggeringProvision || c.onboarding_status === 'PROVISIONED'}
                    className="flex items-center justify-center gap-2 p-4 bg-electric-teal text-white rounded-lg hover:bg-teal-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    data-testid="trigger-provision-btn"
                  >
                    {triggeringProvision ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                    Trigger Provisioning
                  </button>
                  <div className="flex flex-col gap-2">
                    <button
                      onClick={handleResendPassword}
                      disabled={resendingPassword}
                      className="flex items-center justify-center gap-2 p-4 bg-midnight-blue text-white rounded-lg hover:bg-blue-900 disabled:opacity-50 transition-colors"
                      data-testid="resend-password-btn"
                    >
                      {resendingPassword ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Mail className="w-5 h-5" />}
                      Resend Password Link
                    </button>
                    {lastResendActivationLink && (
                      <button
                        type="button"
                        onClick={handleCopyActivationLink}
                        className="flex items-center justify-center gap-2 p-2 text-sm text-electric-teal hover:underline border border-electric-teal/50 rounded-lg"
                        data-testid="copy-activation-link-btn"
                      >
                        <Copy className="w-4 h-4" />
                        Copy link (fallback if email did not arrive)
                      </button>
                    )}
                    {lastResendMessageId && (
                      <p className="text-xs text-gray-500">
                        Recorded in Notification Health (message_id: <code className="font-mono">{lastResendMessageId}</code>)
                      </p>
                    )}
                  </div>
                  {showPaymentLinkActions && (
                    <div className="col-span-2 flex flex-col gap-2">
                      <button
                        onClick={handleSendPaymentLink}
                        disabled={sendingPaymentLink}
                        className="flex items-center justify-center gap-2 p-4 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 transition-colors"
                        data-testid="send-payment-link-btn"
                      >
                        {sendingPaymentLink ? <RefreshCw className="w-5 h-5 animate-spin" /> : <CreditCard className="w-5 h-5" />}
                        {c.checkout_link_sent_at ? 'Resend Payment Link' : 'Send Payment Link'}
                      </button>
                      {c.checkout_link_sent_at && (
                        <div className="flex items-center gap-3 text-sm text-gray-600">
                          <span>Last sent: {new Date(c.checkout_link_sent_at).toLocaleString()}</span>
                          {c.latest_checkout_url && (
                            <button
                              type="button"
                              onClick={handleCopyPaymentLink}
                              className="flex items-center gap-1 text-electric-teal hover:underline"
                              title="Copy payment link"
                            >
                              <Copy className="h-3.5 w-3.5" />
                              Copy link
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Profile Update */}
              <div>
                <h3 className="font-semibold text-midnight-blue mb-4">Update Profile</h3>
                <div className="bg-gray-50 rounded-lg p-4 space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                      <input
                        type="text"
                        value={profileForm.full_name}
                        onChange={(e) => setProfileForm({ ...profileForm, full_name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                        data-testid="profile-name-input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                      <input
                        type="text"
                        value={profileForm.phone}
                        onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                        data-testid="profile-phone-input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Company Name</label>
                      <input
                        type="text"
                        value={profileForm.company_name}
                        onChange={(e) => setProfileForm({ ...profileForm, company_name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                        data-testid="profile-company-input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Preferred Contact</label>
                      <select
                        value={profileForm.preferred_contact}
                        onChange={(e) => setProfileForm({ ...profileForm, preferred_contact: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                        data-testid="profile-contact-select"
                      >
                        <option value="EMAIL">Email</option>
                        <option value="SMS">SMS</option>
                        <option value="BOTH">Both</option>
                      </select>
                    </div>
                  </div>
                  <button
                    onClick={handleSaveProfile}
                    disabled={savingProfile}
                    className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 disabled:opacity-50 transition-colors"
                    data-testid="save-profile-btn"
                  >
                    {savingProfile ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    Save Changes
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'upload' && (
            <div className="space-y-6">
              <h3 className="font-semibold text-midnight-blue mb-4 flex items-center gap-2">
                <Upload className="w-5 h-5" />
                Upload document on behalf of client
              </h3>
              <p className="text-sm text-gray-600">Select a property and requirement, then choose a file. The document will be stored against the client&apos;s record and can be verified in Compliance.</p>
              <form onSubmit={handleUploadDocument} className="bg-gray-50 rounded-lg p-6 space-y-4 max-w-lg">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Property</label>
                  <select
                    value={uploadPropertyId}
                    onChange={(e) => { setUploadPropertyId(e.target.value); setUploadRequirementId(''); }}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                    required
                    data-testid="admin-upload-property"
                  >
                    <option value="">Select property</option>
                    {(client?.properties ?? []).map((p) => (
                      <option key={p.property_id} value={p.property_id}>
                        {p.nickname || p.address_line_1 || p.property_id}
                        {p.postcode ? ` (${p.postcode})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Requirement</label>
                  <select
                    value={uploadRequirementId}
                    onChange={(e) => setUploadRequirementId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                    required
                    disabled={!uploadPropertyId}
                    data-testid="admin-upload-requirement"
                  >
                    <option value="">Select requirement</option>
                    {(client?.requirements ?? [])
                      .filter((r) => r.property_id === uploadPropertyId)
                      .map((r) => (
                        <option key={r.requirement_id} value={r.requirement_id}>
                          {r.requirement_type || r.requirement_id}
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">File</label>
                  <input
                    id="admin-upload-file-input"
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                    data-testid="admin-upload-file"
                  />
                  <p className="text-xs text-gray-500 mt-1">PDF, JPG, PNG, or DOC/DOCX</p>
                </div>
                <button
                  type="submit"
                  disabled={uploadingDocument || !uploadPropertyId || !uploadRequirementId || !uploadFile}
                  className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  data-testid="admin-upload-submit"
                >
                  {uploadingDocument ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                  {uploadingDocument ? 'Uploading…' : 'Upload document'}
                </button>
              </form>
            </div>
          )}

          {activeSection === 'messaging' && (
            <div className="space-y-6">
              <h3 className="font-semibold text-midnight-blue flex items-center gap-2">
                <MessageSquare className="w-5 h-5" />
                Send Message to Client
              </h3>
              <form onSubmit={handleSendMessage} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                  <input
                    type="text"
                    value={messageForm.subject}
                    onChange={(e) => setMessageForm({ ...messageForm, subject: e.target.value })}
                    placeholder="Enter email subject..."
                    className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                    data-testid="message-subject-input"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Message</label>
                  <textarea
                    value={messageForm.message}
                    onChange={(e) => setMessageForm({ ...messageForm, message: e.target.value })}
                    placeholder="Enter your message..."
                    rows={6}
                    className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent resize-none"
                    data-testid="message-body-input"
                    required
                  />
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="sendCopy"
                    checked={messageForm.send_copy_to_admin}
                    onChange={(e) => setMessageForm({ ...messageForm, send_copy_to_admin: e.target.checked })}
                    className="w-4 h-4 text-electric-teal rounded focus:ring-electric-teal"
                    data-testid="message-copy-checkbox"
                  />
                  <label htmlFor="sendCopy" className="text-sm text-gray-600">Send copy to my email</label>
                </div>
                <button
                  type="submit"
                  disabled={sendingMessage}
                  className="flex items-center gap-2 px-6 py-3 bg-electric-teal text-white rounded-lg hover:bg-teal-600 disabled:opacity-50 transition-colors"
                  data-testid="send-message-btn"
                >
                  {sendingMessage ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                  Send Email
                </button>
              </form>
            </div>
          )}

          {activeSection === 'timeline' && (
            <div className="space-y-4">
              <h3 className="font-semibold text-midnight-blue flex items-center gap-2">
                <History className="w-5 h-5" />
                Audit Timeline
              </h3>
              <div className="space-y-3">
                {(timeline ?? []).length === 0 ? (
                  <p className="text-gray-500 text-center py-8">No audit events found</p>
                ) : (
                  (timeline ?? []).map((event, idx) => (
                    <div key={idx} className="flex gap-4 p-4 bg-gray-50 rounded-lg">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                        event.action?.includes('SUCCESS') || event.action?.includes('COMPLETE') ? 'bg-green-100 text-green-600' :
                        event.action?.includes('FAILED') ? 'bg-red-100 text-red-600' : 'bg-electric-teal/10 text-electric-teal'
                      }`}>
                        {event.action?.includes('DOCUMENT') ? <FileText className="w-5 h-5" /> :
                         event.action?.includes('EMAIL') || event.action?.includes('MESSAGE') ? <Mail className="w-5 h-5" /> :
                         event.action?.includes('LOGIN') || event.action?.includes('PASSWORD') ? <Shield className="w-5 h-5" /> :
                         <Activity className="w-5 h-5" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-midnight-blue">{event.action?.replace(/_/g, ' ')}</p>
                        <p className="text-sm text-gray-500">{new Date(event.timestamp).toLocaleString()}</p>
                        {event.metadata && Object.keys(event.metadata).length > 0 && (
                          <div className="mt-2 text-xs text-gray-400 bg-white p-2 rounded">
                            {JSON.stringify(event.metadata, null, 2).slice(0, 200)}...
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// KPI Drilldown Modal Component
const KPIDrilldownModal = ({ drilldownType, onClose, onSelectClient }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    if (!drilldownType) return;
    let cancelled = false;
    const fetchDrilldownData = async () => {
      setLoading(true);
      try {
        let endpoint = '';
        
        // Map drilldown type to API endpoint
        if (drilldownType === 'clients' || drilldownType === 'clients-active' || drilldownType === 'clients-pending') {
          const status =
            drilldownType === 'clients-active'
              ? '&subscription_status=ACTIVE'
              : drilldownType === 'clients-pending'
                ? '&lifecycle_bucket=pending_setup'
                : '';
          endpoint = `/admin/clients?limit=50${status}`;
        } else if (drilldownType === 'properties') {
          endpoint = '/admin/kpi/properties?limit=50';
        } else if (drilldownType.startsWith('compliance-')) {
          const status = drilldownType.replace('compliance-', '');
          endpoint = `/admin/kpi/properties?status_filter=${status}&limit=50`;
        } else if (drilldownType === 'requirements-all') {
          endpoint = '/admin/kpi/requirements?limit=50';
        } else if (drilldownType === 'requirements-overdue') {
          endpoint = '/admin/kpi/requirements?status_filter=OVERDUE&limit=50';
        } else if (drilldownType === 'requirements-expiring-30') {
          endpoint = '/admin/kpi/requirements?due_within_days=30&exclude_overdue=true&limit=50';
        } else if (drilldownType === 'requirements-expiring-60') {
          endpoint = '/admin/kpi/requirements?due_within_days=60&min_due_days=31&exclude_overdue=true&limit=50';
        } else if (drilldownType === 'documents-all') {
          endpoint = '/admin/kpi/documents?limit=50';
        } else if (drilldownType === 'documents-uploaded') {
          endpoint = '/admin/kpi/documents?status_filter=UPLOADED&limit=50';
        }

        if (!endpoint) {
          throw new Error(`Unsupported drilldown type: ${drilldownType}`);
        }
        const response = await api.get(endpoint);
        if (cancelled) return;
        if (drilldownType.includes('client')) {
          setData(response.data.clients || []);
          setTotalCount(response.data.total || 0);
        } else if (drilldownType.startsWith('documents-')) {
          setData(response.data.documents || []);
          setTotalCount(response.data.total || 0);
        } else if (drilldownType.startsWith('requirements-')) {
          setData(response.data.requirements || []);
          setTotalCount(response.data.total || 0);
        } else {
          setData(response.data.properties || []);
          setTotalCount(response.data.total || 0);
        }
    } catch (error) {
        if (!cancelled) {
          const msg = normalizeErrorDetail(error.response?.data?.detail, error.message || 'Failed to load drill-down data');
          toast.error(msg);
          setData([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchDrilldownData();
    return () => { cancelled = true; };
  }, [drilldownType]);

  const getTitle = () => {
    switch (drilldownType) {
      case 'clients': return 'All Clients';
      case 'clients-active': return 'Active Clients';
      case 'clients-pending': return 'Pending Setup Clients';
      case 'properties': return 'All Properties';
      case 'compliance-GREEN': return 'Compliant Properties';
      case 'compliance-AMBER': return 'Attention Needed Properties';
      case 'compliance-RED': return 'Non-Compliant Properties';
      case 'requirements-all': return 'All Requirements';
      case 'requirements-overdue': return 'Overdue Requirements';
      case 'requirements-expiring-30': return 'Requirements Due in 30 Days';
      case 'requirements-expiring-60': return 'Requirements Due in 31-60 Days';
      case 'documents-all': return 'All Documents';
      case 'documents-uploaded': return 'Uploaded Documents';
      default: return 'Details';
    }
  };

  const isClientView = drilldownType?.includes('client');
  const isDocumentView = drilldownType?.startsWith('documents-');
  const isRequirementView = drilldownType?.startsWith('requirements-');

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="kpi-drilldown-modal">
      <div className="bg-white rounded-xl w-full max-w-4xl mx-4 shadow-xl max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-midnight-blue text-white p-6 flex items-center justify-between flex-shrink-0">
          <div>
            <h2 className="text-xl font-bold">{getTitle()}</h2>
            <p className="text-sm text-gray-300 mt-1">Total: {totalCount} records</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
            data-testid="close-drilldown-modal"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
            </div>
          ) : (data ?? []).length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              No records found
            </div>
          ) : isClientView ? (
            // Client list view
            <div className="space-y-3">
              {(data ?? []).map((client) => (
                <button
                  key={client.client_id}
                  onClick={() => {
                    onClose();
                    onSelectClient(client);
                  }}
                  className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors text-left"
                  data-testid={`drilldown-client-${client.client_id}`}
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-midnight-blue text-white rounded-full flex items-center justify-center font-semibold">
                      {client.full_name?.charAt(0)?.toUpperCase() || 'C'}
                    </div>
                    <div>
                      <p className="font-medium text-midnight-blue">{client.full_name}</p>
                      <p className="text-sm text-gray-500">{client.email}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    {client.customer_reference && (
                      <span className="inline-block px-2 py-1 bg-electric-teal/10 text-electric-teal text-xs font-mono rounded mb-1">
                        {client.customer_reference}
                      </span>
                    )}
                    <div className="flex gap-2 mt-1">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        client.subscription_status === 'ACTIVE' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                      }`}>
                        {client.subscription_status}
                      </span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          ) : isDocumentView ? (
            // Document list view
            <div className="space-y-3">
              {(data ?? []).map((doc) => (
                <div
                  key={doc.document_id}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                  data-testid={`drilldown-document-${doc.document_id}`}
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                      doc.status === 'UPLOADED' ? 'bg-blue-100 text-blue-600' :
                      doc.status === 'VERIFIED' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-600'
                    }`}>
                      <FileText className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="font-medium text-midnight-blue">{doc.file_name || doc.document_id || 'Document'}</p>
                      <p className="text-sm text-gray-500">
                        Uploaded {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : 'N/A'}
                        {doc.property?.nickname ? ` • ${doc.property.nickname}` : ''}
                        {!doc.property?.nickname && doc.property?.address_line_1 ? ` • ${doc.property.address_line_1}` : ''}
                        {doc.property?.effective_jurisdiction_label
                          ? ` • ${doc.property.effective_jurisdiction_label}${
                              doc.property.jurisdiction_source
                                ? ` · Source: ${jurisdictionSourceLabel(doc.property.jurisdiction_source)}`
                                : ''
                            }`
                          : ''}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      doc.status === 'VERIFIED' ? 'bg-green-100 text-green-700' :
                      doc.status === 'UPLOADED' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'
                    }`}>
                      {doc.status || 'UNKNOWN'}
                    </span>
                    {doc.client && (
                      <p className="text-xs text-gray-500 mt-1">
                        {doc.client.full_name}
                        {doc.client.customer_reference ? ` (${doc.client.customer_reference})` : ''}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : isRequirementView ? (
            // Requirement list view
            <div className="space-y-3">
              {(data ?? []).map((req) => (
                <div
                  key={req.requirement_id}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                  data-testid={`drilldown-requirement-${req.requirement_id}`}
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                      req.status === 'COMPLIANT' ? 'bg-green-100 text-green-600' :
                      (req.status === 'EXPIRING_SOON' ? 'bg-amber-100 text-amber-600' : 'bg-red-100 text-red-600')
                    }`}>
                      <FileCheck className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="font-medium text-midnight-blue">{req.category || req.requirement_type || 'Requirement'}</p>
                      <p className="text-sm text-gray-500">
                        Due {req.due_date ? new Date(req.due_date).toLocaleDateString() : 'N/A'}
                        {req.property?.nickname ? ` • ${req.property.nickname}` : ''}
                        {!req.property?.nickname && req.property?.address_line_1 ? ` • ${req.property.address_line_1}` : ''}
                        {req.property?.effective_jurisdiction_label
                          ? ` • ${req.property.effective_jurisdiction_label}${
                              req.property.jurisdiction_source
                                ? ` · Source: ${jurisdictionSourceLabel(req.property.jurisdiction_source)}`
                                : ''
                            }`
                          : ''}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      req.status === 'COMPLIANT' ? 'bg-green-100 text-green-700' :
                      (req.status === 'EXPIRING_SOON' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700')
                    }`}>
                      {req.status || 'UNKNOWN'}
                    </span>
                    {req.client && (
                      <p className="text-xs text-gray-500 mt-1">
                        {req.client.full_name}
                        {req.client.customer_reference ? ` (${req.client.customer_reference})` : ''}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            // Properties list view
            <div className="space-y-3">
              {(data ?? []).map((property) => (
                <div
                  key={property.property_id}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                  data-testid={`drilldown-property-${property.property_id}`}
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                      property.compliance_status === 'GREEN' ? 'bg-green-100 text-green-600' :
                      property.compliance_status === 'AMBER' ? 'bg-amber-100 text-amber-600' : 'bg-red-100 text-red-600'
                    }`}>
                      <Building2 className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="font-medium text-midnight-blue">{property.nickname || property.address_line_1 || 'Property'}</p>
                      <p className="text-sm text-gray-500">
                        {property.postcode} • {property.local_authority || 'N/A'}
                        {property.effective_jurisdiction_label
                          ? ` • ${property.effective_jurisdiction_label}${
                              property.jurisdiction_source
                                ? ` · Source: ${jurisdictionSourceLabel(property.jurisdiction_source)}`
                                : ''
                            }`
                          : ''}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      property.compliance_status === 'GREEN' ? 'bg-green-100 text-green-700' :
                      property.compliance_status === 'AMBER' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {property.compliance_status || 'UNKNOWN'}
                    </span>
                    {property.client && (
                      <p className="text-xs text-gray-500 mt-1">
                        {property.client.full_name}
                        {property.client.customer_reference && ` (${property.client.customer_reference})`}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Tab Components
const JobsMonitoring = () => {
  const [jobsStatus, setJobsStatus] = useState(null);
  const [frameworkAudit, setFrameworkAudit] = useState(null);
  const [healthSummary, setHealthSummary] = useState(null);
  const [jobsStatusError, setJobsStatusError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(null);

  const fetchJobsStatus = async () => {
    setJobsStatusError(null);
    try {
      const [auditRes, healthRes] = await Promise.all([
        api.get('/admin/observability/framework-audit'),
        api.get('/admin/observability/health-summary').catch(() => ({ data: null })),
      ]);
      const audit = auditRes?.data || {};
      const inventory = audit.inventory || [];
      const byJob = Object.fromEntries(inventory.map((row) => [row.job_name, row]));
      const scheduledJobs = inventory
        .filter((row) => row.registered)
        .map((row) => ({
          id: row.job_name,
          name: row.purpose || row.job_name,
          next_run: row.next_run_time || null,
        }));
      setFrameworkAudit(audit);
      setJobsStatus({
        system_status: scheduledJobs.length > 0 ? 'operational' : 'issues',
        scheduled_jobs: scheduledJobs,
        deprecated: false,
        daily_reminders: {
          last_run: byJob.daily_reminders?.last_finished_at || null,
          pending_count: null,
        },
        monthly_digest: {
          last_run: byJob.monthly_digest?.last_finished_at || null,
          total_sent: null,
        },
      });
      setHealthSummary(healthRes?.data ?? null);
    } catch (error) {
      setJobsStatusError(error.response?.data?.detail || 'Failed to load job status. Check Automation Control Centre or server logs.');
      setJobsStatus(null);
      setFrameworkAudit(null);
      setHealthSummary(null);
      toast.error('Failed to load jobs status');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobsStatus();
    const interval = setInterval(fetchJobsStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const triggerJob = async (jobId) => {
    if (!jobId) return;
    setTriggering(jobId);
    try {
      const response = await api.post('/admin/jobs/run', { job: jobId });
      const message = response.data?.message || `${jobId} completed`;
      toast.success(message);
      fetchJobsStatus();
    } catch (error) {
      toast.error(error.response?.data?.detail || `Failed to run ${jobId}`);
    } finally {
      setTriggering(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-midnight-blue">Background Jobs</h2>
        <button
          onClick={fetchJobsStatus}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* System Status - aligned with System Health / Automation Centre (single source of truth) */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          {(() => {
            const strictStatus = healthSummary?.overall_health ?? (jobsStatus?.system_status === 'operational' ? 'healthy' : 'degraded');
            const isOk = strictStatus === 'healthy';
            const label = strictStatus === 'healthy' ? 'Operational' : strictStatus === 'degraded' ? 'Degraded' : strictStatus === 'failed' ? 'Failed' : 'Attention required';
            return (
              <>
                <div className={`w-3 h-3 rounded-full ${isOk ? 'bg-green-500' : strictStatus === 'failed' ? 'bg-red-500' : 'bg-amber-500'}`} />
                <span className="font-medium text-midnight-blue">
                  System Status: {label}
                </span>
              </>
            );
          })()}
          {(jobsStatusError || (healthSummary && healthSummary.overall_health !== 'healthy') || jobsStatus?.system_status === 'issues') && (
            <Link
              to="/admin/automation"
              className="ml-2 text-sm text-electric-teal hover:underline"
              title="Open Automation Control Centre"
            >
              View details →
            </Link>
          )}
        </div>
        {jobsStatusError && (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4">
            {jobsStatusError}
          </p>
        )}
        {!jobsStatusError && jobsStatus?.system_status === 'issues' && (jobsStatus?.scheduled_jobs?.length === 0) && (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4">
            No scheduled jobs loaded. The background scheduler may not be running—check server startup logs. <Link to="/admin/automation" className="text-electric-teal hover:underline">Automation Control Centre</Link> · <Link to="/admin/system-health" className="text-electric-teal hover:underline">System Health</Link>
          </p>
        )}

        {/* Scheduled Jobs */}
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Scheduled Jobs</h3>
          <p className="text-xs text-gray-500">Routine automation runs automatically. Use Run Now only for recovery or testing.</p>
          {(jobsStatus?.scheduled_jobs ?? []).map((job) => {
            const jobId = job?.id;
            return (
              <div key={jobId || job?.name} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-4">
                  <Clock className="w-5 h-5 text-electric-teal" />
                  <div>
                    <p className="font-medium text-midnight-blue">{job?.name}</p>
                    <p className="text-sm text-gray-500">
                      Next run: {job?.next_run ? new Date(job.next_run).toLocaleString() : 'Not scheduled'}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => triggerJob(jobId)}
                  disabled={triggering !== null || !jobId}
                  className="flex items-center gap-2 px-4 py-2 border border-gray-400 bg-white text-gray-700 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
                  data-testid={`trigger-${jobId}-btn`}
                  title="Use only for recovery or testing"
                >
                  {triggering === jobId ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  Run Now
                </button>
              </div>
            );
          })}
        </div>

        {frameworkAudit?.reconciliation && (
          <p className="mt-3 text-xs text-gray-500">
            Observability truth source active. Registry-only: {(frameworkAudit.reconciliation.registry_only || []).length}, Scheduler-only: {(frameworkAudit.reconciliation.scheduler_only || []).length}.
          </p>
        )}
      </div>

      {/* Manual Job Triggers */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-midnight-blue mb-4">Manual Job Triggers</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            onClick={() => triggerJob('daily_reminders')}
            disabled={triggering !== null}
            className="flex flex-col items-center gap-2 p-4 border border-gray-200 rounded-lg hover:border-electric-teal hover:bg-teal-50 transition-colors disabled:opacity-50"
            data-testid="manual-trigger-daily"
          >
            {triggering === 'daily_reminders' ? (
              <RefreshCw className="w-6 h-6 animate-spin text-electric-teal" />
            ) : (
              <Mail className="w-6 h-6 text-electric-teal" />
            )}
            <span className="font-medium text-midnight-blue">Daily Reminders</span>
            <span className="text-xs text-gray-500">Send expiry reminders</span>
          </button>

          <button
            onClick={() => triggerJob('monthly_digest')}
            disabled={triggering !== null}
            className="flex flex-col items-center gap-2 p-4 border border-gray-200 rounded-lg hover:border-electric-teal hover:bg-teal-50 transition-colors disabled:opacity-50"
            data-testid="manual-trigger-monthly"
          >
            {triggering === 'monthly_digest' ? (
              <RefreshCw className="w-6 h-6 animate-spin text-electric-teal" />
            ) : (
              <Calendar className="w-6 h-6 text-electric-teal" />
            )}
            <span className="font-medium text-midnight-blue">Monthly Digest</span>
            <span className="text-xs text-gray-500">Send compliance summary</span>
          </button>

          <button
            onClick={() => triggerJob('compliance_check_morning')}
            disabled={triggering !== null}
            className="flex flex-col items-center gap-2 p-4 border border-gray-200 rounded-lg hover:border-amber-500 hover:bg-amber-50 transition-colors disabled:opacity-50"
            data-testid="manual-trigger-compliance"
          >
            {triggering === 'compliance_check_morning' ? (
              <RefreshCw className="w-6 h-6 animate-spin text-amber-600" />
            ) : (
              <AlertTriangle className="w-6 h-6 text-amber-600" />
            )}
            <span className="font-medium text-midnight-blue">Compliance Check</span>
            <span className="text-xs text-gray-500">Check status changes & alert</span>
          </button>
        </div>
      </div>

      {/* Job Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-midnight-blue mb-4">Daily Reminders</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Last Run</span>
              <span className="font-medium">
                {jobsStatus?.daily_reminders?.last_run 
                  ? new Date(jobsStatus.daily_reminders.last_run).toLocaleString() 
                  : 'Never'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Pending Reminders</span>
              <span className="font-medium text-amber-600">
                {jobsStatus?.daily_reminders?.pending_count == null ? '—' : jobsStatus.daily_reminders.pending_count}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-midnight-blue mb-4">Monthly Digest</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Last Run</span>
              <span className="font-medium">
                {jobsStatus?.monthly_digest?.last_run 
                  ? new Date(jobsStatus.monthly_digest.last_run).toLocaleString() 
                  : 'Never'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Total Sent</span>
              <span className="font-medium text-electric-teal">
                {jobsStatus?.monthly_digest?.total_sent == null ? '—' : jobsStatus.monthly_digest.total_sent}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const ClientsManagement = () => {
  const stepUpClients = useStepUpApi();
  const [searchParams, setSearchParams] = useSearchParams();
  const [clients, setClients] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedClient, setSelectedClient] = useState(null);
  const [clientDetails, setClientDetails] = useState(null);
  const [searchInputValue, setSearchInputValue] = useState(() => searchParams.get('q') || '');
  const planFilter = searchParams.get('plan_code') || '';
  const subscriptionFilter = searchParams.get('subscription_status') || '';
  const statusFilter = searchParams.get('onboarding_status') || 'all';
  const lifecycleBucket = searchParams.get('lifecycle_bucket') || 'active';
  const accountEnvironment = searchParams.get('account_environment') || 'all';
  const searchTerm = searchParams.get('q') || '';

  useEffect(() => {
    setSearchInputValue(searchTerm);
  }, [searchTerm]);

  const updateParams = (updates) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value == null || value === '' || value === 'all') next.delete(key);
      else next.set(key, value);
    });
    setSearchParams(next, { replace: true });
  };

  const searchDebounceRef = useRef(null);
  const handleSearchChange = (e) => {
    const v = e.target.value;
    setSearchInputValue(v);
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    searchDebounceRef.current = setTimeout(() => updateParams({ q: v }), 300);
  };

  const fetchClients = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: '100' });
      if (planFilter && planFilter !== 'all') params.set('plan_code', planFilter);
      if (subscriptionFilter && subscriptionFilter !== 'all') params.set('subscription_status', subscriptionFilter);
      if (statusFilter && statusFilter !== 'all') params.set('onboarding_status', statusFilter);
      if (searchTerm.trim()) params.set('q', searchTerm.trim());
      if (lifecycleBucket && lifecycleBucket !== 'active') {
        params.set('lifecycle_bucket', lifecycleBucket);
      }
      if (accountEnvironment && accountEnvironment !== 'all') {
        params.set('account_environment', accountEnvironment);
      }
      const response = await api.get(`/admin/clients?${params.toString()}`);
      setClients(response.data.clients || []);
      setTotal(response.data.total ?? 0);
    } catch (error) {
      const msg = error.response?.data?.detail || error.message || 'Failed to load clients';
      toast.error(msg);
      setClients([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [planFilter, subscriptionFilter, statusFilter, lifecycleBucket, accountEnvironment, searchTerm]);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  const handleClearFilters = () => {
    setSearchParams({}, { replace: true });
  };

  const fetchClientDetails = async (clientId) => {
    try {
      const response = await api.get(`/admin/clients/${clientId}/full-status`);
      setClientDetails(response.data);
      setSelectedClient(clientId);
    } catch (error) {
      toast.error('Failed to load client details');
    }
  };

  const resendPasswordSetup = async (clientId) => {
    try {
      await stepUpClients.request((headers) =>
        api.post(`/admin/clients/${clientId}/resend-password-setup`, null, { headers }),
      );
      toast.success('Password setup email sent');
    } catch (error) {
      if (error?.message !== 'step_up_cancelled') {
        toast.error(normalizeErrorDetail(error.response?.data?.detail, 'Failed to send email'));
      }
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      PROVISIONED: 'bg-green-100 text-green-800',
      PENDING_PAYMENT: 'bg-amber-100 text-amber-800',
      INTAKE_COMPLETE: 'bg-blue-100 text-blue-800',
      INVITED: 'bg-purple-100 text-purple-800',
      ACTIVE: 'bg-green-100 text-green-800',
      SET: 'bg-green-100 text-green-800',
      NOT_SET: 'bg-red-100 text-red-800'
    };
    return styles[status] || 'bg-gray-100 text-gray-800';
  };

  const hasFilters =
    planFilter ||
    subscriptionFilter ||
    (statusFilter && statusFilter !== 'all') ||
    (lifecycleBucket && lifecycleBucket !== 'active') ||
    (accountEnvironment && accountEnvironment !== 'all') ||
    searchTerm.trim();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-midnight-blue">Clients ({total})</h2>
      </div>

      {/* Search and Filter */}
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2">
          {ADMIN_CLIENT_LIFECYCLE_BUCKETS.map((b) => (
            <button
              key={b.id}
              type="button"
              onClick={() => updateParams({ lifecycle_bucket: b.id === 'active' ? null : b.id })}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                lifecycleBucket === b.id
                  ? 'bg-electric-teal text-white border-electric-teal'
                  : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
              }`}
            >
              {b.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Account type</span>
          {[
            { id: 'all', label: 'All', activeClass: 'bg-electric-teal text-white border-electric-teal' },
            { id: 'live', label: 'Live (production)', activeClass: 'bg-slate-800 text-white border-slate-800' },
            {
              id: 'non_production',
              label: 'Test / Dummy / Pre-production',
              activeClass: 'bg-fuchsia-700 text-white border-fuchsia-700',
            },
          ].map((b) => (
            <button
              key={b.id}
              type="button"
              onClick={() => updateParams({ account_environment: b.id === 'all' ? null : b.id })}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                accountEnvironment === b.id ? b.activeClass : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
              }`}
            >
              {b.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search by name, email or CRN..."
              value={searchInputValue}
              onChange={handleSearchChange}
              className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
            />
          </div>
          <select
            value={planFilter || 'all'}
            onChange={(e) => updateParams({ plan_code: e.target.value })}
            className="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
            aria-label="Plan filter"
          >
            <option value="all">All Plans</option>
            <option value="solo">Solo</option>
            <option value="portfolio">Portfolio</option>
            <option value="pro">Pro</option>
          </select>
          <select
            value={subscriptionFilter || 'all'}
            onChange={(e) => updateParams({ subscription_status: e.target.value })}
            className="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
            aria-label="Subscription status filter"
          >
            <option value="all">All Subscription</option>
            <option value="ACTIVE">Active</option>
            <option value="TRIALING">Trialing</option>
            <option value="PENDING">Pending</option>
            <option value="PAST_DUE">Past due</option>
            <option value="CANCELED">Canceled</option>
            <option value="NONE">None</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => updateParams({ onboarding_status: e.target.value })}
            className="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
            aria-label="Onboarding status filter"
          >
            <option value="all">All Status</option>
            <option value="PROVISIONED">Provisioned</option>
            <option value="PENDING_PAYMENT">Pending Payment</option>
            <option value="INTAKE_COMPLETE">Intake Complete</option>
          </select>
          {hasFilters && (
            <button
              type="button"
              onClick={handleClearFilters}
              className="px-4 py-2 border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 focus:ring-2 focus:ring-electric-teal"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="flex gap-6">
        {/* Client List */}
        <div className="flex-1 bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Client</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Lifecycle</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Onboarding</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subscription</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {clients.map((client) => (
                  <tr 
                    key={client.client_id} 
                    className={`hover:bg-gray-50 cursor-pointer ${selectedClient === client.client_id ? 'bg-teal-50' : ''}`}
                    onClick={() => fetchClientDetails(client.client_id)}
                  >
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-midnight-blue">{client.full_name}</p>
                        <p className="text-sm text-gray-500">{client.email}</p>
                        {client.customer_reference ? (
                          <p className="text-xs text-gray-400 font-mono mt-0.5">{client.customer_reference}</p>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-6 py-4 max-w-[200px]">
                      <span
                        className={`inline-flex px-2 py-1 text-xs font-medium rounded-md ${adminEnterpriseLifecycleBadgeClass(
                          client.derived_client_lifecycle_status,
                        )}`}
                      >
                        {client.derived_client_lifecycle_status || '—'}
                      </span>
                      <div className="mt-1 flex flex-wrap gap-1 items-center">
                        <AccountEnvironmentBadge doc={client} showLiveBadge />
                        {client.purge_eligible ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-800">Purge</span>
                        ) : null}
                      </div>
                      {client.client_lifecycle_status &&
                      client.client_lifecycle_status !== client.derived_client_lifecycle_status ? (
                        <p className="text-[10px] text-gray-400 mt-1" title="Stored enterprise status (may differ until next sync)">
                          stored: {client.client_lifecycle_status}
                        </p>
                      ) : null}
                      {client.archive_reason ? (
                        <p className="text-[10px] text-gray-500 mt-1 line-clamp-2" title={client.archive_reason}>
                          {client.archive_reason}
                        </p>
                      ) : null}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(client.onboarding_status)}`}>
                        {client.onboarding_status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(client.subscription_status)}`}>
                        {client.subscription_status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={(e) => { e.stopPropagation(); fetchClientDetails(client.client_id); }}
                        className="text-electric-teal hover:text-teal-700"
                      >
                        <Eye className="w-5 h-5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Client Details Panel */}
        {clientDetails && (
          <div className="w-96 bg-white rounded-xl border border-gray-200 p-6 space-y-6">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-lg font-semibold text-midnight-blue">Client Details</h3>
                <AccountEnvironmentBadge doc={clientDetails.client} showLiveBadge />
              </div>
              <button onClick={() => { setSelectedClient(null); setClientDetails(null); }} className="text-gray-400 hover:text-gray-600">
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div
              className={`rounded-lg border p-3 text-sm ${
                isNonProductionAccount(clientDetails.client)
                  ? 'border-fuchsia-400 bg-fuchsia-50/80 text-fuchsia-950'
                  : 'border-slate-200 bg-slate-50 text-slate-800'
              }`}
            >
              <p className="font-semibold">
                {isNonProductionAccount(clientDetails.client) ? NON_PRODUCTION_ACCOUNT_LABEL : PRODUCTION_ACCOUNT_LABEL}
              </p>
              <p className="mt-1 text-gray-700">{clientOrgPermanentDeleteHint(isNonProductionAccount(clientDetails.client))}</p>
            </div>

            {/* Client Info */}
            <div className="space-y-3">
              <div>
                <p className="text-sm text-gray-500">Name</p>
                <p className="font-medium">{clientDetails.client?.full_name}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Email</p>
                <p className="font-medium">{clientDetails.client?.email}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Onboarding</p>
                  <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(clientDetails.client?.onboarding_status)}`}>
                    {clientDetails.client?.onboarding_status}
                  </span>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Subscription</p>
                  <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(clientDetails.client?.subscription_status)}`}>
                    {clientDetails.client?.subscription_status}
                  </span>
                </div>
              </div>
              <div className="border-t border-gray-100 pt-3 mt-3">
                <p className="text-sm text-gray-500 mb-2">Enterprise lifecycle</p>
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`inline-flex px-2 py-1 text-xs font-medium rounded-md ${adminEnterpriseLifecycleBadgeClass(
                      clientDetails.derived_client_lifecycle_status,
                    )}`}
                  >
                    {clientDetails.derived_client_lifecycle_status || '—'}
                  </span>
                  {clientDetails.client?.client_lifecycle_status ? (
                    <span className="text-xs text-gray-500">stored: {clientDetails.client.client_lifecycle_status}</span>
                  ) : null}
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-600 items-center">
                  <AccountEnvironmentBadge doc={clientDetails.client} showLiveBadge />
                  {clientDetails.client?.purge_eligible ? <span>Purge eligible</span> : null}
                  {clientDetails.client?.is_deleted ? <span className="text-amber-700">Archived / hidden</span> : null}
                </div>
                {clientDetails.client?.archive_reason ? (
                  <p className="text-xs text-gray-500 mt-2">
                    <span className="font-medium text-gray-600">Archive reason: </span>
                    {clientDetails.client.archive_reason}
                  </p>
                ) : null}
              </div>
            </div>

            {/* Portal User */}
            {(clientDetails.portal_users ?? []).length > 0 && (
              <div className="border-t pt-4">
                <h4 className="text-sm font-medium text-gray-500 mb-3">Portal Access</h4>
                {(clientDetails.portal_users ?? []).map((user, idx) => (
                  <div key={user.portal_user_id || idx} className="space-y-2 border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="text-xs font-mono text-gray-500">{user.auth_email || user.email || 'Portal user'}</span>
                      <AccountEnvironmentBadge doc={user} showLiveBadge />
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Status</span>
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(user.status)}`}>
                        {user.status}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Password</span>
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(user.password_status)}`}>
                        {user.password_status}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Role</span>
                      <span className="text-sm font-medium">{user.role}</span>
                    </div>
                  </div>
                ))}
                {(clientDetails.portal_users ?? [])[0]?.password_status === 'NOT_SET' && (
                  <button
                    onClick={() => resendPasswordSetup(clientDetails.client?.client_id)}
                    className="w-full mt-3 flex items-center justify-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 transition-colors"
                  >
                    <Send className="w-4 h-4" />
                    Resend Password Setup
                  </button>
                )}
              </div>
            )}

            {/* Readiness Check */}
            {clientDetails.readiness_check && (
              <div className="border-t pt-4">
                <h4 className="text-sm font-medium text-gray-500 mb-3">Readiness Check</h4>
                <div className="space-y-2">
                  {Object.entries(clientDetails.readiness_check ?? {}).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">{key.replace(/_/g, ' ')}</span>
                      {value ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-500" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Properties */}
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-gray-500 mb-3">
                Properties ({clientDetails.properties_count || 0})
              </h4>
              {(clientDetails.properties ?? []).slice(0, 3).map((prop, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm mb-2">
                  <Building2 className="w-4 h-4 text-gray-400" />
                  <span>{prop.address_line_1}, {prop.city}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      {stepUpClients.modal}
    </div>
  );
};

const AuditLogs = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('');
  const [totalLogs, setTotalLogs] = useState(0);
  const [page, setPage] = useState(0);
  const limit = 20;

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      let url = `/admin/audit-logs?limit=${limit}&skip=${page * limit}`;
      if (actionFilter) url += `&action=${actionFilter}`;
      const response = await api.get(url);
      const data = response?.data;
      const logList = Array.isArray(data?.logs) ? data.logs : [];
      setLogs(logList);
      setTotalLogs(typeof data?.total === 'number' ? data.total : 0);
    } catch (error) {
      toast.error('Failed to load audit logs');
      setLogs([]);
      setTotalLogs(0);
    } finally {
      setLoading(false);
    }
  }, [actionFilter, page]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const getActionIcon = (action) => {
    const a = action ?? '';
    if (a.includes('LOGIN')) return <Shield className="w-4 h-4" />;
    if (a.includes('EMAIL')) return <Mail className="w-4 h-4" />;
    if (a.includes('PASSWORD')) return <Activity className="w-4 h-4" />;
    if (a.includes('PROVISIONING')) return <CheckCircle className="w-4 h-4" />;
    return <FileText className="w-4 h-4" />;
  };

  const getActionColor = (action) => {
    const a = action ?? '';
    if (a.includes('SUCCESS') || a.includes('COMPLETE')) return 'text-green-600 bg-green-50';
    if (a.includes('FAILED') || a.includes('ERROR')) return 'text-red-600 bg-red-50';
    if (a.includes('SENT')) return 'text-blue-600 bg-blue-50';
    return 'text-gray-600 bg-gray-50';
  };

  const actionOptions = [
    'USER_LOGIN_SUCCESS',
    'USER_LOGIN_FAILED',
    'PASSWORD_SET_SUCCESS',
    'PASSWORD_TOKEN_GENERATED',
    'EMAIL_SENT',
    'EMAIL_FAILED',
    'PROVISIONING_COMPLETE',
    'PROVISIONING_FAILED',
    'ADMIN_ACTION',
    'INTAKE_SUBMITTED'
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-midnight-blue">System Audit Logs ({totalLogs})</h2>
        <button
          onClick={fetchLogs}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filter */}
      <div className="flex gap-4">
        <select
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(0); }}
          className="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
        >
          <option value="">All Actions</option>
          {actionOptions.map(action => (
            <option key={action} value={action}>{action.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      {/* Logs Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {(logs ?? []).filter(Boolean).map((log, idx) => (
                  <tr key={log?.log_id ?? idx} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {log?.timestamp ? new Date(log.timestamp).toLocaleString() : '—'}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${getActionColor(log?.action)}`}>
                        {getActionIcon(log?.action)}
                        {log?.action ?? '—'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {log?.metadata && typeof log.metadata === 'object' && !Array.isArray(log.metadata)
                        ? Object.entries(log.metadata).slice(0, 3).map(([k, v]) => (
                            v != null && <span key={k} className="mr-3"><strong>{k}:</strong> {String(v).substring(0, 50)}</span>
                          ))
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          Showing {page * limit + 1} to {Math.min((page + 1) * limit, totalLogs)} of {totalLogs}
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            Previous
          </button>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={(page + 1) * limit >= totalLogs}
            className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

// Template aliases that support Resend from Email delivery (only password-setup has an endpoint)
const EMAIL_DELIVERY_RESEND_TEMPLATES = { 'password-setup': true };

// Email Delivery (read-only, no recipient) — message_logs + EMAIL_SKIPPED_NO_RECIPIENT
const EmailDelivery = () => {
  const stepUpEmail = useStepUpApi();
  const [data, setData] = useState({ total: 0, returned: 0, has_more: false, items: [] });
  const [loading, setLoading] = useState(true);
  const [templateAlias, setTemplateAlias] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [clientId, setClientId] = useState('');
  const [sinceHours, setSinceHours] = useState(72);
  const [skip, setSkip] = useState(0);
  const [resendConfirmRow, setResendConfirmRow] = useState(null);
  const [resendLoading, setResendLoading] = useState(false);
  const limit = 50;

  const fetchEmailDelivery = useCallback(async (overrideSkip = null) => {
    setLoading(true);
    const currentSkip = overrideSkip !== null ? overrideSkip : skip;
    try {
      const { adminAPI } = await import('../api/client');
      const res = await adminAPI.getEmailDelivery({
        template_alias: templateAlias || undefined,
        status: statusFilter || undefined,
        client_id: clientId || undefined,
        since_hours: sinceHours,
        limit,
        skip: currentSkip,
      });
      setData({
        total: res.data?.total ?? 0,
        returned: res.data?.returned ?? 0,
        has_more: res.data?.has_more ?? false,
        items: res.data?.items ?? [],
        empty_reason: res.data?.empty_reason ?? null,
      });
    } catch (e) {
      toast.error('Failed to load email delivery list');
      setData({ total: 0, returned: 0, has_more: false, items: [], empty_reason: null });
    } finally {
      setLoading(false);
    }
  }, [templateAlias, statusFilter, clientId, sinceHours, skip]);

  useEffect(() => {
    fetchEmailDelivery();
  }, [fetchEmailDelivery]);

  const handleResendConfirm = useCallback(async () => {
    if (!resendConfirmRow?.client_id) return;
    setResendLoading(true);
    try {
      const { adminAPI } = await import('../api/client');
      const cid = resendConfirmRow.client_id;
      await stepUpEmail.request((headers) => adminAPI.resendPasswordSetup(cid, { headers }));
      toast.success('Password setup email resent');
      setResendConfirmRow(null);
      fetchEmailDelivery();
    } catch (e) {
      if (e?.message === 'step_up_cancelled') {
        /* closed password modal */
      } else {
        const detail = e.response?.data?.detail;
        const code = detail?.error_code || (typeof detail === 'object' ? detail?.error_code : null);
        if (e.response?.status === 502 && code === 'EMAIL_SEND_FAILED') {
          toast.error('Email send failed. Check provider or try again later.');
        } else if (e.response?.status === 429) {
          toast.error(detail?.message || 'Too many requests. Please try again later.');
        } else if (e.response?.status === 404) {
          toast.error('Client or portal user not found.');
        } else {
          toast.error(e.response?.data?.detail?.message || e.message || 'Resend failed');
        }
      }
    } finally {
      setResendLoading(false);
    }
  }, [resendConfirmRow, fetchEmailDelivery, stepUpEmail]);

  const canShowResend = (row) =>
    row.status === 'failed' &&
    row.client_id &&
    EMAIL_DELIVERY_RESEND_TEMPLATES[row.template_alias] === true;

  return (
    <div className="space-y-6">
      {/* Resend confirm modal */}
      {resendConfirmRow && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-labelledby="resend-modal-title">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 id="resend-modal-title" className="text-lg font-semibold text-midnight-blue mb-2">Resend password setup email?</h3>
            <p className="text-sm text-gray-600 mb-4">
              This will send a new password setup link for client <span className="font-mono text-xs">{resendConfirmRow.client_id}</span>. Existing tokens will be revoked.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setResendConfirmRow(null)}
                disabled={resendLoading}
                className="px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleResendConfirm}
                disabled={resendLoading}
                className="px-3 py-2 text-sm bg-electric-teal text-white rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
                data-testid="email-delivery-resend-confirm"
              >
                {resendLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : null}
                Resend
              </button>
            </div>
          </div>
        </div>
      )}
      <h2 className="text-xl font-semibold text-midnight-blue">Email delivery (last 72h)</h2>
      <p className="text-sm text-gray-500">Read-only view for debugging. No recipient emails shown.</p>
      <div className="flex flex-wrap items-center gap-4 mb-4">
        <label className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Template</span>
          <input
            type="text"
            value={templateAlias}
            onChange={(e) => setTemplateAlias(e.target.value)}
            placeholder="e.g. monthly_digest"
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-40"
            data-testid="email-delivery-template"
          />
        </label>
        <label className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Status</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
            data-testid="email-delivery-status"
          >
            <option value="">All</option>
            <option value="sent">Sent</option>
            <option value="failed">Failed</option>
            <option value="skipped">Skipped</option>
          </select>
        </label>
        <label className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Client ID</span>
          <input
            type="text"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="Optional"
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-40"
            data-testid="email-delivery-client-id"
          />
        </label>
        <label className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Hours</span>
          <select
            value={sinceHours}
            onChange={(e) => setSinceHours(Number(e.target.value))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
            data-testid="email-delivery-hours"
          >
            <option value={24}>24</option>
            <option value={72}>72</option>
            <option value={168}>168</option>
            <option value={720}>720</option>
          </select>
        </label>
        <button
          type="button"
          onClick={() => { setSkip(0); fetchEmailDelivery(0); }}
          disabled={loading}
          className="px-4 py-2 bg-electric-teal text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
          data-testid="email-delivery-apply"
        >
          {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Apply
        </button>
      </div>
      {loading ? (
        <div className="flex justify-center py-8">
          <RefreshCw className="w-6 h-6 animate-spin text-electric-teal" />
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Template</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Client ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Message ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Provider error</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {(data?.items ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center">
                      <p className="text-gray-600 font-medium">No records.</p>
                      <p className="text-gray-500 text-sm mt-1">
                        {data?.empty_reason === 'no_sends_attempted'
                          ? 'No sends were attempted in this window. Automation may not have run or no notifications were due.'
                          : data?.empty_reason === 'template_or_filter_excluded_all'
                          ? 'Template or filter excluded all results. Try widening filters.'
                          : data?.empty_reason === 'automation_did_not_run_or_no_provider_events'
                          ? 'No message logs in window. Automation may not have run or provider events not yet received.'
                          : 'No email delivery records for the selected filters and time range.'}
                      </p>
                    </td>
                  </tr>
                ) : (
                  (data?.items ?? []).map((row, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-4 py-2 whitespace-nowrap text-gray-600">{row.created_at ? new Date(row.created_at).toLocaleString() : '—'}</td>
                      <td className="px-4 py-2 text-gray-700">{row.template_alias ?? '—'}</td>
                      <td className="px-4 py-2">
                        <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                          row.status === 'failed' ? 'bg-red-100 text-red-800' :
                          row.status === 'skipped' ? 'bg-amber-100 text-amber-800' : 'bg-green-100 text-green-800'
                        }`}>
                          {row.status ?? '—'}
                        </span>
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">{row.client_id ?? '—'}</td>
                      <td className="px-4 py-2 font-mono text-xs truncate max-w-[120px]" title={row.message_id}>{row.message_id ?? '—'}</td>
                      <td className="px-4 py-2 text-gray-600 max-w-[200px] truncate" title={row.error_message || row.provider_error_type || row.provider_error_code}>{row.provider_error_type || row.provider_error_code ? `${row.provider_error_type || ''} ${row.provider_error_code || ''}`.trim() : row.error_message || '—'}</td>
                      <td className="px-4 py-2">
                        {canShowResend(row) ? (
                          <button
                            type="button"
                            onClick={() => setResendConfirmRow(row)}
                            className="text-xs font-medium text-electric-teal hover:underline"
                            data-testid="email-delivery-resend"
                          >
                            Resend
                          </button>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {data.total > 0 && (
            <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between text-sm text-gray-500">
              <span>Showing {data.returned} of {data.total}{data.has_more ? ' (more available)' : ''}</span>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - limit))}
                  className="px-3 py-1 rounded border border-gray-300 disabled:opacity-50"
                  data-testid="email-delivery-prev"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={!data.has_more}
                  onClick={() => setSkip(skip + limit)}
                  className="px-3 py-1 rounded border border-gray-300 disabled:opacity-50"
                  data-testid="email-delivery-next"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {stepUpEmail.modal}
    </div>
  );
};

// Admin Users Management Component
const HARD_DELETE_CONFIRM_PHRASE = 'PERMANENTLY DELETE TEST ACCOUNT';

const AdminsManagement = () => {
  const { user: authUser } = useAuth();
  const stepUp = useStepUpApi();
  const [admins, setAdmins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [showArchived, setShowArchived] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    full_name: ''
  });

  const fetchAdmins = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get('/admin/admins', {
        params: { include_archived: showArchived },
      });
      setAdmins(response.data.admins || []);
    } catch (error) {
      toast.error('Failed to load admin users');
    } finally {
      setLoading(false);
    }
  }, [showArchived]);

  useEffect(() => {
    fetchAdmins();
  }, [fetchAdmins]);

  const handleInvite = async (e) => {
    e.preventDefault();
    if (!formData.email || !formData.full_name) {
      toast.error('Please fill in all fields');
      return;
    }

    setInviteLoading(true);
    try {
      await stepUp.request((headers) => api.post('/admin/admins/invite', formData, { headers }));
      toast.success('Admin invitation sent successfully');
      setShowInviteForm(false);
      setFormData({ email: '', full_name: '' });
      fetchAdmins();
    } catch (error) {
      if (error?.message === 'step_up_cancelled') {
        /* user closed modal */
      } else {
        toast.error(normalizeErrorDetail(error.response?.data?.detail, 'Failed to send invitation'));
      }
    } finally {
      setInviteLoading(false);
    }
  };

  const handleArchive = async (portalUserId, email) => {
    if (!window.confirm(`Archive ${email}? They will be signed out and hidden from normal lists.`)) return;

    setActionLoading(portalUserId);
    try {
      await stepUp.request((headers) =>
        api.post(`/admin/users/${portalUserId}/archive`, null, { headers }),
      );
      toast.success('User archived');
      fetchAdmins();
    } catch (error) {
      if (error?.message !== 'step_up_cancelled') {
        toast.error(normalizeErrorDetail(error.response?.data?.detail, 'Failed to archive user'));
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleRestoreUser = async (portalUserId) => {
    setActionLoading(portalUserId);
    try {
      await stepUp.request((headers) =>
        api.post(`/admin/users/${portalUserId}/restore`, null, { headers }),
      );
      toast.success('User restored');
      fetchAdmins();
    } catch (error) {
      if (error?.message !== 'step_up_cancelled') {
        toast.error(normalizeErrorDetail(error.response?.data?.detail, 'Failed to restore user'));
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handlePermanentDelete = async (portalUserId, email, adminRow) => {
    setActionLoading(portalUserId);
    try {
      const check = await api.get(`/admin/users/${portalUserId}/permanent-delete-check`);
      const { allowed, blockers = [] } = check.data || {};
      if (!allowed) {
        toast.error(
          blockers.length
            ? `Cannot permanently delete: ${blockers.join(', ')}`
            : 'Cannot permanently delete this user',
        );
        return;
      }
      const envNote = accountEnvironmentActionNote(Boolean(adminRow?.is_test_like));
      if (
        !window.confirm(
          `${envNote}\n\nPermanently remove ${email} from the database? This cannot be undone. Billing records and the client account are not deleted.`,
        )
      ) {
        return;
      }
      const typed = window.prompt(
        `Owner confirmation: type exactly:\n${HARD_DELETE_CONFIRM_PHRASE}`,
      );
      if (typed !== HARD_DELETE_CONFIRM_PHRASE) {
        toast.error('Phrase did not match — permanent delete cancelled.');
        return;
      }
      await stepUp.request((headers) =>
        api.delete(`/admin/users/${portalUserId}/permanent`, { headers }),
      );
      toast.success('User permanently deleted');
      fetchAdmins();
    } catch (error) {
      if (error?.message !== 'step_up_cancelled') {
        toast.error(normalizeErrorDetail(error.response?.data?.detail, 'Failed to permanently delete user'));
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleReactivate = async (portalUserId) => {
    setActionLoading(portalUserId);
    try {
      await stepUp.request((headers) =>
        api.post(`/admin/admins/${portalUserId}/reactivate`, null, { headers }),
      );
      toast.success('Admin reactivated successfully');
      fetchAdmins();
    } catch (error) {
      if (error?.message !== 'step_up_cancelled') {
        toast.error(normalizeErrorDetail(error.response?.data?.detail, 'Failed to reactivate admin'));
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleResendInvite = async (portalUserId, email) => {
    setActionLoading(portalUserId);
    try {
      const res = await stepUp.request((headers) =>
        api.post(`/admin/admins/${portalUserId}/resend-invite`, null, { headers }),
      );
      const data = res?.data;
      if (data?.duplicate) {
        toast.info(data.message || 'A recent invitation was already recorded. Check spam or wait before retrying.');
      } else {
        toast.success(data?.message || `Invitation resent to ${email}`);
      }
    } catch (error) {
      if (error?.message !== 'step_up_cancelled') {
        toast.error(normalizeErrorDetail(error.response?.data?.detail, 'Failed to resend invitation'));
      }
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusBadge = (status, passwordStatus, isDeleted) => {
    if (isDeleted) {
      return { label: 'Archived', className: 'bg-slate-100 text-slate-800 border border-slate-300' };
    }
    if (status === 'DISABLED') {
      return { label: 'Disabled', className: 'bg-gray-100 text-gray-700 border border-gray-300' };
    }
    if (status === 'INVITED' || passwordStatus === 'NOT_SET') {
      return { label: 'Pending Setup', className: 'bg-amber-50 text-amber-700 border border-amber-200' };
    }
    if (status === 'ACTIVE') {
      return { label: 'Active', className: 'bg-emerald-50 text-emerald-700 border border-emerald-200' };
    }
    return { label: status, className: 'bg-gray-100 text-gray-700' };
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="admins-loading">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="admins-management">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-midnight-blue">Admin Users</h2>
          <p className="text-sm text-gray-500 mt-1">
            Manage administrator access to Compliance Vault Pro. For deactivate (suspend), archive, restore, and
            permanent delete across all portal identities, use{' '}
            <Link to="/admin/ops/identities" className="text-electric-teal font-medium hover:underline">
              Identity lifecycle
            </Link>
            .
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
              className="rounded border-gray-300"
              data-testid="admins-show-archived"
            />
            Show archived
          </label>
          <button
            onClick={fetchAdmins}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
            data-testid="refresh-admins-btn"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={() => setShowInviteForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 transition-colors"
            data-testid="invite-admin-btn"
          >
            <UserPlus className="w-4 h-4" />
            Invite Admin
          </button>
        </div>
      </div>

      {/* Invite Form Modal */}
      {showInviteForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="invite-admin-modal">
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-electric-teal/10 rounded-lg flex items-center justify-center">
                  <UserPlus className="w-5 h-5 text-electric-teal" />
                </div>
                <h3 className="text-lg font-semibold text-midnight-blue">Invite New Admin</h3>
              </div>
              <button
                onClick={() => { setShowInviteForm(false); setFormData({ email: '', full_name: '' }); }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                data-testid="close-invite-modal-btn"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleInvite} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-midnight-blue mb-2">
                  Full Name
                </label>
                <input
                  type="text"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  placeholder="Enter admin's full name"
                  className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent transition-all"
                  data-testid="invite-admin-name-input"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-midnight-blue mb-2">
                  Email Address
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="admin@company.com"
                  className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent transition-all"
                  data-testid="invite-admin-email-input"
                  required
                />
              </div>

              <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600">
                <p className="flex items-start gap-2">
                  <Mail className="w-4 h-4 mt-0.5 text-electric-teal flex-shrink-0" />
                  An invitation email will be sent with a secure link to set up their account.
                </p>
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => { setShowInviteForm(false); setFormData({ email: '', full_name: '' }); }}
                  className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                  data-testid="cancel-invite-btn"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={inviteLoading}
                  className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 transition-colors disabled:opacity-50"
                  data-testid="submit-invite-btn"
                >
                  {inviteLoading ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                  Send Invitation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Admin Stats Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-electric-teal/10 rounded-lg flex items-center justify-center">
              <Users className="w-5 h-5 text-electric-teal" />
            </div>
            <div>
              <p className="text-2xl font-bold text-midnight-blue">{admins.length}</p>
              <p className="text-xs text-gray-500">Total Admins</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
              <CheckCircle className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-midnight-blue">
                {admins.filter(a => a.status === 'ACTIVE' && a.password_status === 'SET').length}
              </p>
              <p className="text-xs text-gray-500">Active</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
              <Clock className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-midnight-blue">
                {admins.filter(a => a.status === 'INVITED' || a.password_status === 'NOT_SET').length}
              </p>
              <p className="text-xs text-gray-500">Pending Setup</p>
            </div>
          </div>
        </div>
      </div>

      {/* Admin List */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-4 text-left text-xs font-semibold text-midnight-blue uppercase tracking-wider">
                  Admin
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-midnight-blue uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-midnight-blue uppercase tracking-wider">
                  Last Login
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-midnight-blue uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-4 text-right text-xs font-semibold text-midnight-blue uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {(admins ?? []).map((admin) => {
                const isArchived = admin.is_deleted === true;
                const isOwner = admin.role === 'ROLE_OWNER';
                const statusBadge = getStatusBadge(admin.status, admin.password_status, isArchived);
                const isLoading = actionLoading === admin.portal_user_id;
                const isDisabled = admin.status === 'DISABLED' && !isArchived;
                const isPending = admin.status === 'INVITED' || admin.password_status === 'NOT_SET';

                return (
                  <tr 
                    key={admin.portal_user_id} 
                    className={`hover:bg-gray-50 transition-colors ${isDisabled || isArchived ? 'opacity-60' : ''}`}
                    data-testid={`admin-row-${admin.portal_user_id}`}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold ${
                          isDisabled ? 'bg-gray-400' : 'bg-midnight-blue'
                        }`}>
                          {admin.full_name?.charAt(0)?.toUpperCase() || admin.auth_email?.charAt(0)?.toUpperCase() || 'A'}
                        </div>
                        <div>
                          <p className="font-medium text-midnight-blue flex flex-wrap items-center gap-2">
                            {admin.full_name || 'Unnamed Admin'}
                            <AccountEnvironmentBadge doc={admin} showLiveBadge />
                          </p>
                          <p className="text-sm text-gray-500">{admin.auth_email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${statusBadge.className}`}>
                        {statusBadge.label}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {admin.last_login 
                        ? new Date(admin.last_login).toLocaleDateString('en-GB', {
                            day: 'numeric',
                            month: 'short',
                            year: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })
                        : <span className="text-gray-400">Never</span>
                      }
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {admin.created_at 
                        ? new Date(admin.created_at).toLocaleDateString('en-GB', {
                            day: 'numeric',
                            month: 'short',
                            year: 'numeric'
                          })
                        : '—'
                      }
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-2">
                        {isLoading ? (
                          <RefreshCw className="w-4 h-4 animate-spin text-electric-teal" />
                        ) : (
                          <>
                            {isArchived ? (
                              <>
                                <button
                                  onClick={() => handleRestoreUser(admin.portal_user_id)}
                                  className="p-2 text-electric-teal hover:bg-electric-teal/10 rounded-lg transition-colors"
                                  title="Restore user"
                                  data-testid={`restore-admin-${admin.portal_user_id}`}
                                >
                                  <RotateCcw className="w-4 h-4" />
                                </button>
                                {authUser?.role === 'ROLE_OWNER' && admin.hard_delete_allowed ? (
                                  <button
                                    onClick={() => handlePermanentDelete(admin.portal_user_id, admin.auth_email, admin)}
                                    className="p-2 text-gray-400 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
                                    title="Permanently delete test account (pre-flight checks passed)"
                                    data-testid={`permanent-delete-admin-${admin.portal_user_id}`}
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </button>
                                ) : authUser?.role === 'ROLE_OWNER' && !admin.hard_delete_allowed ? (
                                  <span
                                    className="p-2 text-gray-300 cursor-not-allowed inline-flex"
                                    title={
                                      admin.hard_delete_blockers?.length
                                        ? `Not eligible: ${admin.hard_delete_blockers.join(', ')}`
                                        : 'Not eligible for permanent delete'
                                    }
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </span>
                                ) : null}
                              </>
                            ) : (
                              <>
                                {isPending && !isDisabled && (
                                  <button
                                    onClick={() => handleResendInvite(admin.portal_user_id, admin.auth_email)}
                                    className="p-2 text-electric-teal hover:bg-electric-teal/10 rounded-lg transition-colors"
                                    title="Resend Invitation"
                                    data-testid={`resend-invite-${admin.portal_user_id}`}
                                  >
                                    <MailPlus className="w-4 h-4" />
                                  </button>
                                )}
                                {isDisabled ? (
                                  <button
                                    onClick={() => handleReactivate(admin.portal_user_id)}
                                    className="p-2 text-electric-teal hover:bg-electric-teal/10 rounded-lg transition-colors"
                                    title="Reactivate Admin"
                                    data-testid={`reactivate-admin-${admin.portal_user_id}`}
                                  >
                                    <RotateCcw className="w-4 h-4" />
                                  </button>
                                ) : !isOwner ? (
                                  <button
                                    onClick={() => handleArchive(admin.portal_user_id, admin.auth_email)}
                                    className="p-2 text-gray-400 hover:text-amber-700 hover:bg-amber-50 rounded-lg transition-colors"
                                    title="Archive user"
                                    data-testid={`archive-admin-${admin.portal_user_id}`}
                                  >
                                    <Archive className="w-4 h-4" />
                                  </button>
                                ) : null}
                              </>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {admins.length === 0 && (
          <div className="text-center py-12">
            <UserCog className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 mb-4">No admin users found</p>
            <button
              onClick={() => setShowInviteForm(true)}
              className="px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 transition-colors"
            >
              Invite First Admin
            </button>
          </div>
        )}
      </div>
      {stepUp.modal}
    </div>
  );
};

// Rules Management Component — legacy Mongo requirement_rules viewer (published policy lives in Compliance Policy Registry).
const RulesManagement = () => {
  const { isOwner } = useAuth();
  const ownerSession = typeof isOwner === 'function' ? isOwner() : false;
  const [legacyMaintenanceEnv, setLegacyMaintenanceEnv] = useState(false);
  const [legacyDangerAcknowledged, setLegacyDangerAcknowledged] = useState(false);
  const [conflictSummary, setConflictSummary] = useState(null);

  const legacyMutationHeaders =
    legacyMaintenanceEnv && legacyDangerAcknowledged && ownerSession
      ? { 'X-Legacy-Requirement-Rules-Maintenance': '1' }
      : {};

  const canMutateLegacy = Boolean(ownerSession && legacyMaintenanceEnv && legacyDangerAcknowledged);

  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);
  const [propertyTypes, setPropertyTypes] = useState([]);
  const [editingRule, setEditingRule] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState({
    rule_type: '',
    name: '',
    description: '',
    category: 'OTHER',
    frequency_days: 365,
    warning_days: 30,
    applicable_to: 'ALL',
    is_mandatory: true,
    risk_weight: 3,
    regulatory_reference: '',
    notes: ''
  });

  useEffect(() => {
    fetchRules();
    fetchCategories();
    (async () => {
      try {
        const [m, c] = await Promise.all([
          api.get('/admin/rules/maintenance-status').catch(() => ({ data: {} })),
          api.get('/admin/rules/conflict-summary').catch(() => ({ data: null })),
        ]);
        setLegacyMaintenanceEnv(!!m.data?.legacy_maintenance_environment_enabled);
        setConflictSummary(c.data);
      } catch {
        setConflictSummary(null);
      }
    })();
  }, []);

  const fetchRules = async () => {
    setLoading(true);
    try {
      const response = await api.get('/admin/rules?active_only=false');
      setRules(response.data.rules);
    } catch (error) {
      toast.error('Failed to load rules');
    } finally {
      setLoading(false);
    }
  };

  const fetchCategories = async () => {
    try {
      const response = await api.get('/admin/rules/categories');
      setCategories(response.data.categories);
      setPropertyTypes(response.data.property_types);
    } catch (error) {
      console.error('Failed to load categories');
    }
  };

  const seedDefaultRules = async () => {
    if (!canMutateLegacy) {
      toast.error('Legacy mutations are disabled. Owner + server maintenance mode + acknowledgement required.');
      return;
    }
    try {
      const response = await api.post('/admin/rules/seed', {}, { headers: legacyMutationHeaders });
      toast.success(`${response.data.created} rules created, ${response.data.skipped} skipped`);
      fetchRules();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to seed rules');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canMutateLegacy) {
      toast.error('Legacy mutations are disabled. Owner + server maintenance mode + acknowledgement required.');
      return;
    }
    try {
      if (editingRule) {
        await api.put(`/admin/rules/${editingRule.rule_id}`, formData, { headers: legacyMutationHeaders });
        toast.success('Rule updated successfully');
      } else {
        await api.post('/admin/rules', formData, { headers: legacyMutationHeaders });
        toast.success('Rule created successfully');
      }
      setShowCreateForm(false);
      setEditingRule(null);
      resetForm();
      fetchRules();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save rule');
    }
  };

  const handleEdit = (rule) => {
    if (!canMutateLegacy) {
      toast.error('Legacy edits require Owner maintenance mode.');
      return;
    }
    if (rule.governed) {
      toast.error('Governed rows are maintained via Compliance Policy Registry publish.');
      return;
    }
    setFormData({
      rule_type: rule.rule_type,
      name: rule.name,
      description: rule.description,
      category: rule.category,
      frequency_days: rule.frequency_days,
      warning_days: rule.warning_days,
      applicable_to: rule.applicable_to,
      is_mandatory: rule.is_mandatory,
      risk_weight: rule.risk_weight,
      regulatory_reference: rule.regulatory_reference || '',
      notes: rule.notes || ''
    });
    setEditingRule(rule);
    setShowCreateForm(true);
  };

  const handleDelete = async (ruleId) => {
    if (!canMutateLegacy) {
      toast.error('Legacy mutations are disabled.');
      return;
    }
    if (!window.confirm('Are you sure you want to deactivate this rule?')) return;
    try {
      await api.delete(`/admin/rules/${ruleId}`, { headers: legacyMutationHeaders });
      toast.success('Rule deactivated');
      fetchRules();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete rule');
    }
  };

  const resetForm = () => {
    setFormData({
      rule_type: '',
      name: '',
      description: '',
      category: 'OTHER',
      frequency_days: 365,
      warning_days: 30,
      applicable_to: 'ALL',
      is_mandatory: true,
      risk_weight: 3,
      regulatory_reference: '',
      notes: ''
    });
  };

  const getCategoryColor = (category) => {
    const colors = {
      SAFETY: 'bg-red-100 text-red-800',
      ELECTRICAL: 'bg-yellow-100 text-yellow-800',
      ENERGY: 'bg-green-100 text-green-800',
      FIRE: 'bg-orange-100 text-orange-800',
      HEALTH: 'bg-blue-100 text-blue-800',
      REGULATORY: 'bg-purple-100 text-purple-800',
      OTHER: 'bg-gray-100 text-gray-800'
    };
    return colors[category] || colors.OTHER;
  };

  const getRiskColor = (weight) => {
    if (weight >= 4) return 'text-red-600';
    if (weight >= 3) return 'text-amber-600';
    return 'text-green-600';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-amber-200 bg-amber-50/80 p-4 text-sm text-amber-950">
        <p className="font-semibold text-amber-900 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" aria-hidden />
          Legacy requirement rules (read-only)
        </p>
        <p className="mt-2 text-amber-900/90">
          This is a legacy requirement-rules view. Client-facing compliance obligations are governed by the published
          Compliance Policy Registry. Editing legacy rules may create conflicts and should not be used for normal
          compliance policy changes.
        </p>
        <p className="mt-2">
          <Link to="/admin/compliance/registry" className="font-medium text-electric-teal hover:underline">
            Open Compliance Engine → Policy Registry
          </Link>{' '}
          for canonical requirements, jurisdiction, applicability, evidence modes, primary resolution workflow,
          criticality, scoring policy, client visibility, and publish status.
        </p>
      </div>

      {conflictSummary ? (
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm">
          <p className="font-semibold text-midnight-blue">Conflict & supplemental summary (read-only)</p>
          <ul className="mt-2 list-disc pl-5 text-gray-700 space-y-1">
            <li>
              Governed published rows:{' '}
              <span className="font-mono">{conflictSummary.governed_published_count ?? 0}</span>
            </li>
            <li>
              Legacy ungoverned rows in Mongo:{' '}
              <span className="font-mono">{conflictSummary.ungoverned_row_count ?? 0}</span>
            </li>
            <li>
              Same rule_type in both governed and ungoverned (data conflict):{' '}
              <span className="font-mono">{conflictSummary.overlap_count ?? 0}</span>
            </li>
            <li>
              Active ungoverned supplemental rules:{' '}
              <span className="font-mono">{conflictSummary.ungoverned_active_supplemental_count ?? 0}</span>
            </li>
            <li>
              Distinct active ungoverned rule_types (may block first governed publish for that type):{' '}
              <span className="font-mono">{(conflictSummary.distinct_active_ungoverned_rule_types || []).length}</span>
            </li>
          </ul>
          {(conflictSummary.overlap_governed_and_ungoverned || []).length > 0 ? (
            <p className="mt-2 text-xs text-red-800">
              Overlaps: {(conflictSummary.overlap_governed_and_ungoverned || [])
                .slice(0, 6)
                .map((r) => r.rule_type)
                .join(', ')}
              {(conflictSummary.overlap_governed_and_ungoverned || []).length > 6 ? ' …' : ''}
            </p>
          ) : null}
          <p className="mt-2 text-xs text-gray-500">{conflictSummary.publish_block_note}</p>
        </div>
      ) : null}

      {ownerSession && legacyMaintenanceEnv ? (
        <div className="rounded-lg border border-red-200 bg-red-50/60 p-4 text-sm">
          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              className="mt-1"
              checked={legacyDangerAcknowledged}
              onChange={(e) => setLegacyDangerAcknowledged(e.target.checked)}
            />
            <span className="text-red-950">
              <span className="font-semibold">Dangerous legacy maintenance</span> — I am ROLE_OWNER and infra has enabled
              LEGACY_REQUIREMENT_RULES_MAINTENANCE. I understand mutations may conflict with the Policy Registry and provisioning.
            </span>
          </label>
        </div>
      ) : null}
      {ownerSession && !legacyMaintenanceEnv ? (
        <p className="text-xs text-gray-600">
          Emergency legacy edits require server env LEGACY_REQUIREMENT_RULES_MAINTENANCE=true plus Owner acknowledgement
          (disabled here because the environment flag is off).
        </p>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-midnight-blue">Legacy requirement rules ({rules.length})</h2>
          <p className="text-xs text-gray-500 mt-1">Read-only snapshot of MongoDB requirement_rules (includes governed copies).</p>
        </div>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={seedDefaultRules}
            disabled={!canMutateLegacy}
            title={!canMutateLegacy ? 'Disabled for normal ops — Policy Registry is authoritative.' : ''}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <RefreshCw className="w-4 h-4" />
            Seed Default Rules
          </button>
          <button
            type="button"
            onClick={() => {
              if (!canMutateLegacy) return;
              resetForm();
              setEditingRule(null);
              setShowCreateForm(true);
            }}
            disabled={!canMutateLegacy}
            title={!canMutateLegacy ? 'Disabled for normal ops — Policy Registry is authoritative.' : ''}
            className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Plus className="w-4 h-4" />
            Add Rule
          </button>
        </div>
      </div>

      {/* Create/Edit Form Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-midnight-blue">
                {editingRule ? 'Edit Rule' : 'Create New Rule'}
              </h3>
              <button onClick={() => { setShowCreateForm(false); setEditingRule(null); }} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Rule Type (ID)</label>
                  <input
                    type="text"
                    value={formData.rule_type}
                    onChange={(e) => setFormData({...formData, rule_type: e.target.value.toLowerCase().replace(/\s+/g, '_')})}
                    disabled={!!editingRule}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal disabled:bg-gray-100"
                    placeholder="e.g., gas_safety"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    placeholder="e.g., Gas Safety Certificate"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  rows={2}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({...formData, category: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  >
                    {categories.map(cat => (
                      <option key={cat.value} value={cat.value}>{cat.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Applicable To</label>
                  <select
                    value={formData.applicable_to}
                    onChange={(e) => setFormData({...formData, applicable_to: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  >
                    {propertyTypes.map(pt => (
                      <option key={pt.value} value={pt.value}>{pt.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Frequency (days)</label>
                  <input
                    type="number"
                    value={formData.frequency_days}
                    onChange={(e) => setFormData({...formData, frequency_days: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    min={1}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Warning (days)</label>
                  <input
                    type="number"
                    value={formData.warning_days}
                    onChange={(e) => setFormData({...formData, warning_days: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    min={1}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Risk Weight (1-5)</label>
                  <input
                    type="number"
                    value={formData.risk_weight}
                    onChange={(e) => setFormData({...formData, risk_weight: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    min={1}
                    max={5}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Regulatory Reference</label>
                <input
                  type="text"
                  value={formData.regulatory_reference}
                  onChange={(e) => setFormData({...formData, regulatory_reference: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  placeholder="e.g., Gas Safety Regulations 1998"
                />
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.is_mandatory}
                    onChange={(e) => setFormData({...formData, is_mandatory: e.target.checked})}
                    className="w-4 h-4 text-electric-teal rounded"
                  />
                  <span className="text-sm text-gray-700">Mandatory</span>
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => { setShowCreateForm(false); setEditingRule(null); }}
                  className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600"
                >
                  <Save className="w-4 h-4" />
                  {editingRule ? 'Update Rule' : 'Create Rule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Rules Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rule</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Frequency</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Applies To</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Risk</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {(rules ?? []).map((rule) => (
                <tr key={rule.rule_id} className={`hover:bg-gray-50 ${!rule.is_active ? 'opacity-50' : ''}`}>
                  <td className="px-6 py-4">
                    <div>
                      <p className="font-medium text-midnight-blue">{rule.name}</p>
                      <p className="text-sm text-gray-500">{rule.rule_type}</p>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getCategoryColor(rule.category)}`}>
                      {rule.category}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {rule.frequency_days >= 365 
                      ? `${Math.round(rule.frequency_days / 365)} year${rule.frequency_days >= 730 ? 's' : ''}`
                      : `${rule.frequency_days} days`
                    }
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {rule.applicable_to}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`font-bold ${getRiskColor(rule.risk_weight)}`}>
                      {rule.risk_weight}/5
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 flex-wrap">
                      {rule.governed ? (
                        <span className="text-xs bg-purple-100 text-purple-900 px-2 py-0.5 rounded border border-purple-200">
                          Governed registry
                        </span>
                      ) : null}
                      {rule.is_active ? (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-500" />
                      )}
                      {rule.is_mandatory && (
                        <span className="text-xs bg-red-100 text-red-800 px-2 py-0.5 rounded">Required</span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleEdit(rule)}
                        disabled={!canMutateLegacy || rule.governed}
                        title={rule.governed ? 'Edit in Policy Registry' : !canMutateLegacy ? 'Owner maintenance only' : 'Edit'}
                        className="text-electric-teal hover:text-teal-700 disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      {rule.is_active && (
                        <button
                          type="button"
                          onClick={() => handleDelete(rule.rule_id)}
                          disabled={!canMutateLegacy || rule.governed}
                          title={rule.governed ? 'Managed by registry' : !canMutateLegacy ? 'Owner maintenance only' : 'Deactivate'}
                          className="text-red-500 hover:text-red-700 disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {rules.length === 0 && (
        <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
          <BookOpen className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 mb-4">No legacy requirement rules in MongoDB yet.</p>
          <button
            type="button"
            onClick={seedDefaultRules}
            disabled={!canMutateLegacy}
            className="px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Load UK Default Rules (Owner maintenance only)
          </button>
        </div>
      )}
    </div>
  );
};

// Email Templates Management Component
const EmailTemplates = () => {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [aliases, setAliases] = useState([]);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [previewHtml, setPreviewHtml] = useState(null);
  const [formData, setFormData] = useState({
    alias: '',
    name: '',
    subject: '',
    html_body: '',
    text_body: '',
    available_variables: [],
    notes: ''
  });

  useEffect(() => {
    fetchTemplates();
    fetchAliases();
  }, []);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const response = await api.get('/admin/templates?active_only=false');
      setTemplates(response.data.templates);
    } catch (error) {
      toast.error('Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  const fetchAliases = async () => {
    try {
      const response = await api.get('/admin/templates/aliases');
      setAliases(response.data.aliases);
    } catch (error) {
      console.error('Failed to load aliases');
    }
  };

  const seedDefaultTemplates = async () => {
    try {
      const response = await api.post('/admin/templates/seed');
      toast.success(`${response.data.created} templates created, ${response.data.skipped} skipped`);
      fetchTemplates();
    } catch (error) {
      toast.error('Failed to seed templates');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        available_variables: formData.available_variables.filter(v => v.trim())
      };
      
      if (editingTemplate) {
        await api.put(`/admin/templates/${editingTemplate.template_id}`, payload);
        toast.success('Template updated successfully');
      } else {
        await api.post('/admin/templates', payload);
        toast.success('Template created successfully');
      }
      setShowCreateForm(false);
      setEditingTemplate(null);
      resetForm();
      fetchTemplates();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save template');
    }
  };

  const handleEdit = (template) => {
    setFormData({
      alias: template.alias,
      name: template.name,
      subject: template.subject,
      html_body: template.html_body,
      text_body: template.text_body,
      available_variables: template.available_variables || [],
      notes: template.notes || ''
    });
    setEditingTemplate(template);
    setShowCreateForm(true);
  };

  const handlePreview = async (templateId) => {
    try {
      const response = await api.post(`/admin/templates/${templateId}/preview`, { sample_data: {} });
      setPreviewHtml(response.data);
    } catch (error) {
      toast.error('Failed to generate preview');
    }
  };

  const handleDelete = async (templateId) => {
    if (!window.confirm('Are you sure you want to deactivate this template?')) return;
    try {
      await api.delete(`/admin/templates/${templateId}`);
      toast.success('Template deactivated');
      fetchTemplates();
    } catch (error) {
      toast.error('Failed to delete template');
    }
  };

  const resetForm = () => {
    setFormData({
      alias: '',
      name: '',
      subject: '',
      html_body: '',
      text_body: '',
      available_variables: [],
      notes: ''
    });
  };

  const getAliasLabel = (alias) => {
    const found = aliases.find(a => a.value === alias);
    return found ? found.label : alias;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-midnight-blue">Email Templates ({templates.length})</h2>
        <div className="flex gap-3">
          <button
            onClick={seedDefaultTemplates}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Seed Default Templates
          </button>
          <button
            onClick={() => { resetForm(); setEditingTemplate(null); setShowCreateForm(true); }}
            className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Template
          </button>
        </div>
      </div>

      {/* Preview Modal */}
      {previewHtml && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold text-midnight-blue">Email Preview</h3>
              <button onClick={() => setPreviewHtml(null)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 bg-gray-100">
              <p className="text-sm text-gray-600 mb-2"><strong>Subject:</strong> {previewHtml.subject}</p>
            </div>
            <div className="p-4 overflow-y-auto max-h-[60vh]">
              <div dangerouslySetInnerHTML={{ __html: previewHtml.html_body }} />
            </div>
          </div>
        </div>
      )}

      {/* Create/Edit Form Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-4xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-midnight-blue">
                {editingTemplate ? 'Edit Template' : 'Create New Template'}
              </h3>
              <button onClick={() => { setShowCreateForm(false); setEditingTemplate(null); }} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Template Type</label>
                  <select
                    value={formData.alias}
                    onChange={(e) => setFormData({...formData, alias: e.target.value})}
                    disabled={!!editingTemplate}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal disabled:bg-gray-100"
                    required
                  >
                    <option value="">Select type...</option>
                    {aliases.map(a => (
                      <option key={a.value} value={a.value}>{a.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    placeholder="e.g., Password Setup Email"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subject Line</label>
                <input
                  type="text"
                  value={formData.subject}
                  onChange={(e) => setFormData({...formData, subject: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  placeholder="e.g., Set Your Password - Compliance Vault Pro"
                  required
                />
                <p className="text-xs text-gray-500 mt-1">Use {"{{variable_name}}"} for dynamic content</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">HTML Body</label>
                <textarea
                  value={formData.html_body}
                  onChange={(e) => setFormData({...formData, html_body: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal font-mono text-sm"
                  rows={10}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Plain Text Body</label>
                <textarea
                  value={formData.text_body}
                  onChange={(e) => setFormData({...formData, text_body: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal font-mono text-sm"
                  rows={6}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Available Variables (comma-separated)</label>
                <input
                  type="text"
                  value={formData.available_variables.join(', ')}
                  onChange={(e) => setFormData({...formData, available_variables: e.target.value.split(',').map(v => v.trim())})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  placeholder="e.g., client_name, setup_link, company_name"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => { setShowCreateForm(false); setEditingTemplate(null); }}
                  className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600"
                >
                  <Save className="w-4 h-4" />
                  {editingTemplate ? 'Update Template' : 'Create Template'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Templates Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {(templates ?? []).map((template) => (
          <div 
            key={template.template_id} 
            className={`bg-white rounded-xl border border-gray-200 p-6 ${!template.is_active ? 'opacity-50' : ''}`}
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800 mb-2 inline-block">
                  {getAliasLabel(template.alias)}
                </span>
                <h3 className="text-lg font-semibold text-midnight-blue">{template.name}</h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handlePreview(template.template_id)}
                  className="text-gray-400 hover:text-electric-teal"
                  title="Preview"
                >
                  <Eye className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleEdit(template)}
                  className="text-electric-teal hover:text-teal-700"
                  title="Edit"
                >
                  <Edit className="w-4 h-4" />
                </button>
                {template.is_active && (
                  <button
                    onClick={() => handleDelete(template.template_id)}
                    className="text-red-500 hover:text-red-700"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
            
            <p className="text-sm text-gray-600 mb-3">
              <strong>Subject:</strong> {template.subject}
            </p>
            
            {(template.available_variables ?? []).length > 0 && (
              <div className="flex flex-wrap gap-1">
                {(template.available_variables ?? []).map((v, i) => (
                  <span key={i} className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
                    {"{{"}{v}{"}}"}
                  </span>
                ))}
              </div>
            )}
            
            {!template.is_active && (
              <p className="text-xs text-red-500 mt-3">Inactive</p>
            )}
          </div>
        ))}
      </div>

      {templates.length === 0 && (
        <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
          <Mail className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 mb-4">No email templates configured yet</p>
          <button
            onClick={seedDefaultTemplates}
            className="px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600"
          >
            Load Default Templates
          </button>
        </div>
      )}
    </div>
  );
};

// Statistics Dashboard - Executive View
const StatisticsDashboard = ({ onNavigateToTab }) => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [chartsExpanded, setChartsExpanded] = useState(false);

  useEffect(() => {
    fetchStatistics();
  }, []);

  const fetchStatistics = async () => {
    setLoading(true);
    try {
      const response = await api.get('/admin/statistics');
      setStats(response.data);
    } catch (error) {
      toast.error('Failed to load statistics');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-600">Unable to load statistics</p>
      </div>
    );
  }

  // Calculate primary metrics
  const totalProperties = stats.properties?.total || 0;
  const compliantCount = stats.properties?.by_compliance_status?.GREEN || 0;
  const attentionCount = stats.properties?.by_compliance_status?.AMBER || 0;
  const actionCount = stats.properties?.by_compliance_status?.RED || 0;
  const expiring30Days = stats.requirements?.expiring_next_30_days || 0;
  const overdueCount = stats.requirements?.overdue || 0;
  const complianceRate = stats.requirements?.compliance_rate_percent || 0;

  // Calculate chart data
  const requirementsByType = stats.requirements?.by_type || {};
  const requirementLabels = Object.keys(requirementsByType);
  const requirementValues = Object.values(requirementsByType);
  const totalReqs = requirementValues.reduce((a, b) => a + b, 0);

  // Sort requirements by count for donut display
  const sortedRequirements = Object.entries(requirementsByType)
    .sort(([,a], [,b]) => b - a)
    .slice(0, 6);

  // Colors for donut chart
  const donutColors = [
    '#0B1D3A', // midnight-blue
    '#00B8A9', // electric-teal
    '#3B82F6', // blue
    '#8B5CF6', // purple
    '#F59E0B', // amber
    '#6B7280', // gray
  ];

  return (
    <div className="space-y-6" data-testid="statistics-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-midnight-blue">Compliance Statistics</h2>
          <p className="text-sm text-gray-500 mt-1">
            Last updated: {stats?.generated_at ? new Date(stats.generated_at).toLocaleString() : '—'}
          </p>
        </div>
        <button
          onClick={fetchStatistics}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          data-testid="refresh-statistics-btn"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Primary Layer - Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Total Properties */}
        <div
          role={onNavigateToTab ? 'button' : undefined}
          tabIndex={onNavigateToTab ? 0 : undefined}
          onClick={onNavigateToTab ? () => onNavigateToTab('overview', { drilldown: 'properties' }) : undefined}
          onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('overview', { drilldown: 'properties' }); } } : undefined}
          className={`bg-white rounded-xl border border-gray-200 p-5 ${onNavigateToTab ? 'cursor-pointer hover:border-teal-200 hover:shadow-sm transition-all' : ''}`}
          data-testid="stat-card-total-properties"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-3xl font-bold text-midnight-blue">{totalProperties}</p>
              <p className="text-sm font-medium text-gray-600 mt-1">Total Properties</p>
              <p className="text-xs text-gray-400 mt-1">Across all clients</p>
            </div>
            <Building2 className="w-8 h-8 text-gray-300" />
          </div>
        </div>

        {/* Compliant - GREEN */}
        <div
          role={onNavigateToTab ? 'button' : undefined}
          tabIndex={onNavigateToTab ? 0 : undefined}
          onClick={onNavigateToTab ? () => onNavigateToTab('overview', { drilldown: 'compliance-GREEN' }) : undefined}
          onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('overview', { drilldown: 'compliance-GREEN' }); } } : undefined}
          className={`bg-white rounded-xl border-2 border-green-200 p-5 ${onNavigateToTab ? 'cursor-pointer hover:border-green-300 hover:shadow-sm transition-all' : ''}`}
          data-testid="stat-card-compliant"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-3xl font-bold text-green-600">{compliantCount}</p>
              <p className="text-sm font-medium text-green-700 mt-1">Compliant</p>
              <p className="text-xs text-gray-400 mt-1">All requirements met</p>
            </div>
            <CheckCircle className="w-8 h-8 text-green-400" />
          </div>
        </div>

        {/* Attention Needed - AMBER */}
        <div
          role={onNavigateToTab ? 'button' : undefined}
          tabIndex={onNavigateToTab ? 0 : undefined}
          onClick={onNavigateToTab ? () => onNavigateToTab('overview', { drilldown: 'compliance-AMBER' }) : undefined}
          onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('overview', { drilldown: 'compliance-AMBER' }); } } : undefined}
          className={`bg-white rounded-xl border-2 border-amber-200 p-5 ${onNavigateToTab ? 'cursor-pointer hover:border-amber-300 hover:shadow-sm transition-all' : ''}`}
          data-testid="stat-card-attention"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-3xl font-bold text-amber-600">{attentionCount}</p>
              <p className="text-sm font-medium text-amber-700 mt-1">Attention Needed</p>
              <p className="text-xs text-gray-400 mt-1">Expiring soon</p>
            </div>
            <AlertCircle className="w-8 h-8 text-amber-400" />
          </div>
        </div>

        {/* Action Required - RED */}
        <div
          role={onNavigateToTab ? 'button' : undefined}
          tabIndex={onNavigateToTab ? 0 : undefined}
          onClick={onNavigateToTab ? () => onNavigateToTab('overview', { drilldown: 'compliance-RED' }) : undefined}
          onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('overview', { drilldown: 'compliance-RED' }); } } : undefined}
          className={`bg-white rounded-xl border-2 border-red-200 p-5 ${onNavigateToTab ? 'cursor-pointer hover:border-red-300 hover:shadow-sm transition-all' : ''}`}
          data-testid="stat-card-action-required"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-3xl font-bold text-red-600">{actionCount}</p>
              <p className="text-sm font-medium text-red-700 mt-1">Action Required</p>
              <p className="text-xs text-gray-400 mt-1">Non-compliant</p>
            </div>
            <XCircle className="w-8 h-8 text-red-400" />
          </div>
        </div>

        {/* Upcoming Expiries */}
        <div
          role={onNavigateToTab ? 'button' : undefined}
          tabIndex={onNavigateToTab ? 0 : undefined}
          onClick={onNavigateToTab ? () => onNavigateToTab('overview', { drilldown: 'requirements-expiring-30' }) : undefined}
          onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('overview', { drilldown: 'requirements-expiring-30' }); } } : undefined}
          className={`bg-white rounded-xl border border-gray-200 p-5 ${onNavigateToTab ? 'cursor-pointer hover:border-teal-200 hover:shadow-sm transition-all' : ''}`}
          data-testid="stat-card-expiring"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-3xl font-bold text-midnight-blue">{expiring30Days}</p>
              <p className="text-sm font-medium text-gray-600 mt-1">Expiring Soon</p>
              <p className="text-xs text-gray-400 mt-1">Next 30 days</p>
            </div>
            <Calendar className="w-8 h-8 text-gray-300" />
          </div>
        </div>
      </div>

      {/* Action-Oriented Widgets - Higher priority than charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Urgent Actions */}
        <div className="bg-white rounded-xl border border-gray-200 p-6" data-testid="urgent-actions-widget">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-red-100 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-red-600" />
            </div>
            <div>
              <h3 className="font-semibold text-midnight-blue">Urgent Actions</h3>
              <p className="text-xs text-gray-500">Overdue and due soon</p>
            </div>
          </div>
          
          <div className="space-y-3">
            {overdueCount > 0 && (
              <div
                role={onNavigateToTab ? 'button' : undefined}
                tabIndex={onNavigateToTab ? 0 : undefined}
                onClick={onNavigateToTab ? () => onNavigateToTab('overview', { drilldown: 'requirements-overdue' }) : undefined}
                onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('overview', { drilldown: 'requirements-overdue' }); } } : undefined}
                className={`flex items-center justify-between p-3 bg-red-50 rounded-lg border border-red-100 ${onNavigateToTab ? 'cursor-pointer hover:bg-red-100 transition-colors' : ''}`}
              >
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                  <span className="text-sm font-medium text-red-800">Overdue Requirements</span>
                </div>
                <span className="text-lg font-bold text-red-600">{overdueCount}</span>
              </div>
            )}
            
            {expiring30Days > 0 && (
              <div
                role={onNavigateToTab ? 'button' : undefined}
                tabIndex={onNavigateToTab ? 0 : undefined}
                onClick={onNavigateToTab ? () => onNavigateToTab('overview', { drilldown: 'requirements-expiring-30' }) : undefined}
                onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('overview', { drilldown: 'requirements-expiring-30' }); } } : undefined}
                className={`flex items-center justify-between p-3 bg-amber-50 rounded-lg border border-amber-100 ${onNavigateToTab ? 'cursor-pointer hover:bg-amber-100 transition-colors' : ''}`}
              >
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-amber-500 rounded-full"></div>
                  <span className="text-sm font-medium text-amber-800">Due in 30 days</span>
                </div>
                <span className="text-lg font-bold text-amber-600">{expiring30Days}</span>
              </div>
            )}

            {stats.requirements?.expiring_next_60_days > expiring30Days && (
              <div
                role={onNavigateToTab ? 'button' : undefined}
                tabIndex={onNavigateToTab ? 0 : undefined}
                onClick={onNavigateToTab ? () => onNavigateToTab('overview', { drilldown: 'requirements-expiring-60' }) : undefined}
                onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('overview', { drilldown: 'requirements-expiring-60' }); } } : undefined}
                className={`flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100 ${onNavigateToTab ? 'cursor-pointer hover:bg-gray-100 transition-colors' : ''}`}
              >
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                  <span className="text-sm font-medium text-gray-700">Due in 31-60 days</span>
                </div>
                <span className="text-lg font-bold text-gray-600">
                  {(stats.requirements?.expiring_next_60_days || 0) - expiring30Days}
                </span>
              </div>
            )}

            {overdueCount === 0 && expiring30Days === 0 && (
              <div className="flex items-center gap-3 p-4 bg-green-50 rounded-lg border border-green-100">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <span className="text-sm font-medium text-green-800">No urgent actions required</span>
              </div>
            )}
          </div>
        </div>

        {/* System Summary */}
        <div className="bg-white rounded-xl border border-gray-200 p-6" data-testid="system-summary-widget">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-teal-100 rounded-lg">
              <BarChart3 className="w-5 h-5 text-electric-teal" />
            </div>
            <div>
              <h3 className="font-semibold text-midnight-blue">System Summary</h3>
              <p className="text-xs text-gray-500">Current portfolio status</p>
            </div>
          </div>

          <div className="space-y-3">
            <div
              role={onNavigateToTab ? 'button' : undefined}
              tabIndex={onNavigateToTab ? 0 : undefined}
              onClick={onNavigateToTab ? () => onNavigateToTab('overview', { drilldown: 'clients' }) : undefined}
              onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('overview', { drilldown: 'clients' }); } } : undefined}
              className={`flex items-center justify-between p-3 bg-gray-50 rounded-lg ${onNavigateToTab ? 'cursor-pointer hover:bg-gray-100 transition-colors' : ''}`}
            >
              <span className="text-sm text-gray-600">Total Clients</span>
              <span className="font-semibold text-midnight-blue">{stats.clients?.total || 0}</span>
            </div>
            <div
              role={onNavigateToTab ? 'button' : undefined}
              tabIndex={onNavigateToTab ? 0 : undefined}
              onClick={onNavigateToTab ? () => onNavigateToTab('overview', { drilldown: 'clients-active' }) : undefined}
              onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('overview', { drilldown: 'clients-active' }); } } : undefined}
              className={`flex items-center justify-between p-3 bg-gray-50 rounded-lg ${onNavigateToTab ? 'cursor-pointer hover:bg-gray-100 transition-colors' : ''}`}
            >
              <span className="text-sm text-gray-600">Active Subscriptions</span>
              <span className="font-semibold text-green-600">{stats.clients?.by_subscription_status?.ACTIVE || 0}</span>
            </div>
            <div
              role={onNavigateToTab ? 'button' : undefined}
              tabIndex={onNavigateToTab ? 0 : undefined}
              onClick={onNavigateToTab ? () => onNavigateToTab('clients') : undefined}
              onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('clients'); } } : undefined}
              className={`flex items-center justify-between p-3 bg-gray-50 rounded-lg ${onNavigateToTab ? 'cursor-pointer hover:bg-gray-100 transition-colors' : ''}`}
            >
              <span className="text-sm text-gray-600">Total Requirements</span>
              <span className="font-semibold text-midnight-blue">{stats.requirements?.total || 0}</span>
            </div>
            <div
              role={onNavigateToTab ? 'button' : undefined}
              tabIndex={onNavigateToTab ? 0 : undefined}
              onClick={onNavigateToTab ? () => onNavigateToTab('overview', { drilldown: 'documents-all' }) : undefined}
              onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('overview', { drilldown: 'documents-all' }); } } : undefined}
              className={`flex items-center justify-between p-3 bg-gray-50 rounded-lg ${onNavigateToTab ? 'cursor-pointer hover:bg-gray-100 transition-colors' : ''}`}
            >
              <span className="text-sm text-gray-600">Documents Uploaded</span>
              <span className="font-semibold text-midnight-blue">{stats.documents?.total || 0}</span>
            </div>
            <div
              role={onNavigateToTab ? 'button' : undefined}
              tabIndex={onNavigateToTab ? 0 : undefined}
              onClick={onNavigateToTab ? () => onNavigateToTab('overview', { drilldown: 'requirements-all' }) : undefined}
              onKeyDown={onNavigateToTab ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigateToTab('overview', { drilldown: 'requirements-all' }); } } : undefined}
              className={`flex items-center justify-between p-3 bg-teal-50 rounded-lg border border-teal-100 ${onNavigateToTab ? 'cursor-pointer hover:bg-teal-100 transition-colors' : ''}`}
            >
              <span className="text-sm font-medium text-teal-700">Overall Compliance Rate</span>
              <span className="font-bold text-electric-teal">{complianceRate}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Secondary Layer - Collapsible Charts */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <button
          onClick={() => setChartsExpanded(!chartsExpanded)}
          className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
          data-testid="toggle-charts-btn"
        >
          <div className="flex items-center gap-3">
            <PieChart className="w-5 h-5 text-gray-400" />
            <span className="font-medium text-midnight-blue">Detailed Analytics</span>
          </div>
          {chartsExpanded ? (
            <ChevronUp className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          )}
        </button>

        {chartsExpanded && (
          <div className="p-6 pt-0 border-t border-gray-100">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-4">
              {/* Requirements Breakdown - Donut Style */}
              <div data-testid="requirements-breakdown-chart">
                <h4 className="text-sm font-semibold text-midnight-blue mb-4">Requirements by Certificate Type</h4>
                {sortedRequirements.length > 0 ? (
                  <div className="flex items-start gap-6">
                    {/* Simple visual donut representation */}
                    <div className="relative w-32 h-32 flex-shrink-0">
                      <svg className="w-32 h-32 transform -rotate-90" viewBox="0 0 100 100">
                        {(() => {
                          let cumulativePercent = 0;
                          return sortedRequirements.map(([type, count], idx) => {
                            const percent = (count / totalReqs) * 100;
                            const dashArray = `${percent} ${100 - percent}`;
                            const dashOffset = -cumulativePercent;
                            cumulativePercent += percent;
                            return (
                              <circle
                                key={type}
                                cx="50"
                                cy="50"
                                r="40"
                                fill="transparent"
                                stroke={donutColors[idx] || '#E5E7EB'}
                                strokeWidth="20"
                                strokeDasharray={dashArray}
                                strokeDashoffset={dashOffset}
                                style={{ transition: 'stroke-dasharray 0.3s ease' }}
                              />
                            );
                          });
                        })()}
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-lg font-bold text-midnight-blue">{totalReqs}</span>
                      </div>
                    </div>
                    {/* Legend */}
                    <div className="flex-1 space-y-2">
                      {sortedRequirements.map(([type, count], idx) => (
                        <div key={type} className="flex items-center justify-between text-sm">
                          <div className="flex items-center gap-2">
                            <div 
                              className="w-3 h-3 rounded-full" 
                              style={{ backgroundColor: donutColors[idx] || '#E5E7EB' }}
                            />
                            <span className="text-gray-600 capitalize">
                              {type.replace(/_/g, ' ').toLowerCase()}
                            </span>
                          </div>
                          <span className="font-medium text-midnight-blue">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No requirements data available</p>
                )}
              </div>

              {/* Compliance Trend - Simplified Bar Representation */}
              <div data-testid="compliance-trend-chart">
                <h4 className="text-sm font-semibold text-midnight-blue mb-4">Requirement Status Distribution</h4>
                {stats.requirements?.by_status && Object.keys(stats.requirements.by_status ?? {}).length > 0 ? (
                  <div className="space-y-3">
                    {Object.entries(stats.requirements?.by_status ?? {})
                      .sort(([,a], [,b]) => b - a)
                      .map(([status, count]) => {
                        const percent = totalReqs > 0 ? Math.round((count / totalReqs) * 100) : 0;
                        let barColor = 'bg-gray-400';
                        if (status === 'COMPLIANT') barColor = 'bg-green-500';
                        else if (status === 'EXPIRING_SOON') barColor = 'bg-amber-500';
                        else if (status === 'OVERDUE' || status === 'EXPIRED') barColor = 'bg-red-500';
                        else if (status === 'PENDING') barColor = 'bg-blue-500';
                        
                        return (
                          <div key={status}>
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-sm text-gray-600 capitalize">
                                {status.replace(/_/g, ' ').toLowerCase()}
                              </span>
                              <span className="text-sm font-medium text-midnight-blue">
                                {count} ({percent}%)
                              </span>
                            </div>
                            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                              <div 
                                className={`h-full ${barColor} rounded-full transition-all duration-300`}
                                style={{ width: `${percent}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No status data available</p>
                )}
              </div>
            </div>

            {/* Email & Document Stats - Tertiary Info */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-8 pt-6 border-t border-gray-100">
              <div className="text-center">
                <p className="text-2xl font-bold text-midnight-blue">{stats.emails?.sent || 0}</p>
                <p className="text-xs text-gray-500">Emails Sent</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-midnight-blue">{stats.emails?.delivery_rate || 0}%</p>
                <p className="text-xs text-gray-500">Delivery Rate</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-midnight-blue">{stats.documents?.ai_analyzed || 0}</p>
                <p className="text-xs text-gray-500">AI Analyzed</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-midnight-blue">{stats.rules?.active || 0}</p>
                <p className="text-xs text-gray-500">Active Rules</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Dashboard Overview
const EMPTY_STATS = { stats: {}, compliance_overview: {}, recent_activity: [] };

const DashboardOverview = ({ onShowDrilldown, onSelectClient }) => {
  const navigate = useNavigate();
  const [stats, setStats] = useState(EMPTY_STATS);
  const [loading, setLoading] = useState(true);
  const [dashboardError, setDashboardError] = useState(null);
  const [pendingList, setPendingList] = useState({ documents: [], total: 0, returned: 0, has_more: false });
  const [pendingLoading, setPendingLoading] = useState(false);
  const [pendingHours, setPendingHours] = useState(0);
  const [pendingClientId, setPendingClientId] = useState('');
  const [pendingListWarning, setPendingListWarning] = useState(null);
  const [rejectModalDoc, setRejectModalDoc] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectSubmitting, setRejectSubmitting] = useState(false);
  const [verifyOverrideModal, setVerifyOverrideModal] = useState(null);
  const [verifyOverrideReason, setVerifyOverrideReason] = useState('');
  const [verifyOverrideSubmitting, setVerifyOverrideSubmitting] = useState(false);
  const [resolveMatchModal, setResolveMatchModal] = useState(null);
  const [resolveMatchAction, setResolveMatchAction] = useState('approve_override');
  const [resolveMatchReason, setResolveMatchReason] = useState('');
  const [resolveRelinkId, setResolveRelinkId] = useState('');
  const [resolveSubmitting, setResolveSubmitting] = useState(false);
  const [backfillBusy, setBackfillBusy] = useState(false);
  const [priorityActions, setPriorityActions] = useState({ actions: [], total: 0 });
  const [priorityActionsClientId, setPriorityActionsClientId] = useState('');
  const [clientsForFilter, setClientsForFilter] = useState([]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      console.log('[CVP] AdminDashboard first load: calling GET /admin/dashboard');
    }
    fetchStats();
  }, []);

  useEffect(() => {
    if (loading || dashboardError) return;
    adminAPI.getClients(0, 500)
      .then((res) => setClientsForFilter(res.data?.clients || []))
      .catch(() => setClientsForFilter([]));
  }, [loading, dashboardError]);

  useEffect(() => {
    if (loading || dashboardError) return;
    const params = { limit: 20 };
    if (priorityActionsClientId && priorityActionsClientId.trim()) params.client_id = priorityActionsClientId.trim();
    adminAPI.getPriorityActions(params)
      .then((res) => setPriorityActions({ actions: res.data?.actions || [], total: res.data?.total ?? 0 }))
      .catch(() => setPriorityActions({ actions: [], total: 0 }));
  }, [loading, dashboardError, priorityActionsClientId]);

  const fetchPendingVerification = useCallback(async () => {
    setPendingLoading(true);
    setPendingListWarning(null);
    try {
      const { adminAPI } = await import('../api/client');
      const res = await adminAPI.getPendingVerificationDocuments(pendingHours, pendingClientId || null);
      const data = res?.data;
      const docs = Array.isArray(data?.documents) ? data.documents : [];
      setPendingList({
        documents: docs,
        total: typeof data?.total === 'number' ? data.total : 0,
        returned: typeof data?.returned === 'number' ? data.returned : docs.length,
        has_more: Boolean(data?.has_more),
      });
    } catch (e) {
      setPendingList({ documents: [], total: 0, returned: 0, has_more: false });
      setPendingListWarning('Could not load pending verification list. You can try again or refresh the page.');
      toast.error('Failed to load pending verification list');
    } finally {
      setPendingLoading(false);
    }
  }, [pendingHours, pendingClientId]);

  const handleVerifyDocument = async (doc) => {
    if (!doc?.document_id) return;
    try {
      await adminAPI.verifyDocument(doc.document_id, {});
      toast.success('Document verified');
      fetchPendingVerification();
      fetchStats();
    } catch (e) {
      if (e.response?.status === 409) {
        const s = parseStructuredApiDetail(e);
        setVerifyOverrideModal({ doc, detail: s });
        setVerifyOverrideReason('');
        toast.error(
          s?.message || 'Automated evidence check blocked verification. Use override after manual review, or Resolve match.',
        );
        return;
      }
      toast.error(parseApiError(e, 'Failed to verify document'));
    }
  };

  const handleVerifyWithOverride = async () => {
    const doc = verifyOverrideModal?.doc;
    if (!doc?.document_id) return;
    const reason = verifyOverrideReason.trim();
    if (!reason) {
      toast.error('Enter a short reason for the override (audit trail)');
      return;
    }
    setVerifyOverrideSubmitting(true);
    try {
      await adminAPI.verifyDocument(doc.document_id, {
        evidence_mismatch_override: true,
        evidence_mismatch_override_reason: reason,
      });
      toast.success('Document verified with evidence-match override (audit log: EVIDENCE_MATCH_OVERRIDE_VERIFY)');
      setVerifyOverrideModal(null);
      setVerifyOverrideReason('');
      fetchPendingVerification();
      fetchStats();
    } catch (e) {
      toast.error(parseApiError(e, 'Verify with override failed'));
    } finally {
      setVerifyOverrideSubmitting(false);
    }
  };

  const handleResolveEvidenceMatch = async () => {
    const doc = resolveMatchModal;
    if (!doc?.document_id) return;
    const action = (resolveMatchAction || '').trim();
    if (action === 'relink_requirement' && !resolveRelinkId.trim()) {
      toast.error('Enter the target requirement_id for relink');
      return;
    }
    setResolveSubmitting(true);
    try {
      const body = {
        action,
        reason: resolveMatchReason.trim() || undefined,
        ...(action === 'relink_requirement' ? { relink_requirement_id: resolveRelinkId.trim() } : {}),
      };
      await adminAPI.resolveEvidenceMatch(doc.document_id, body);
      const auditHint =
        action === 'approve_override'
          ? 'EVIDENCE_MATCH_ADMIN_APPROVE_OVERRIDE'
          : action === 'reject_evidence'
            ? 'EVIDENCE_MATCH_ADMIN_REJECT'
            : 'EVIDENCE_MATCH_ADMIN_RELINK';
      toast.success(`Resolution recorded (${auditHint})`);
      setResolveMatchModal(null);
      setResolveMatchReason('');
      setResolveRelinkId('');
      fetchPendingVerification();
      fetchStats();
    } catch (e) {
      toast.error(parseApiError(e, 'Resolve evidence match failed'));
    } finally {
      setResolveSubmitting(false);
    }
  };

  const handleBackfillEvidenceMatch = async () => {
    if (!window.confirm('Run evidence-match backfill on up to 50 documents missing match_outcome? This is audited.')) return;
    setBackfillBusy(true);
    try {
      const { data } = await adminAPI.backfillEvidenceMatch({ limit: 50, dry_run: false });
      toast.success(`Backfill complete: updated ${data?.updated ?? 0} (scanned ${data?.scanned ?? 0})`);
      fetchPendingVerification();
    } catch (e) {
      toast.error(parseApiError(e, 'Backfill failed'));
    } finally {
      setBackfillBusy(false);
    }
  };

  const handleRejectDocument = async () => {
    if (!rejectModalDoc?.document_id || !rejectReason.trim()) {
      toast.error('Please enter a reason for rejection');
      return;
    }
    setRejectSubmitting(true);
    try {
      await api.post(
        `/documents/reject/${rejectModalDoc.document_id}`,
        new URLSearchParams({ reason: rejectReason.trim() }),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      );
      toast.success('Document rejected');
      setRejectModalDoc(null);
      setRejectReason('');
      fetchPendingVerification();
      fetchStats();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to reject document');
    } finally {
      setRejectSubmitting(false);
    }
  };

  const handleViewDocument = async (doc) => {
    if (!doc?.document_id) return;
    try {
      const res = await api.get(`/admin/documents/${doc.document_id}/file`, { params: { download: false }, responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      window.open(url, '_blank', 'noopener,noreferrer');
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) {
      const data = e.response?.data;
      if (data instanceof Blob) {
        data.text().then((text) => {
          try {
            const j = JSON.parse(text);
            toast.error(j.detail || 'Document file unavailable');
          } catch {
            toast.error('Document file unavailable');
          }
        }).catch(() => toast.error('Document file unavailable'));
      } else {
        toast.error(data?.detail || 'Failed to open document');
      }
    }
  };

  const handleDownloadDocument = async (doc) => {
    if (!doc?.document_id) return;
    try {
      const res = await api.get(`/admin/documents/${doc.document_id}/file`, { params: { download: true }, responseType: 'blob' });
      const blob = new Blob([res.data], { type: res.data.type || 'application/octet-stream' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.file_name || doc.original_filename || 'document';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('Download started');
    } catch (e) {
      const data = e.response?.data;
      if (data instanceof Blob) {
        data.text().then((text) => {
          try {
            const j = JSON.parse(text);
            toast.error(j.detail || 'Document file unavailable');
          } catch {
            toast.error('Document file unavailable');
          }
        }).catch(() => toast.error('Document file unavailable'));
      } else {
        toast.error(data?.detail || 'Failed to download document');
      }
    }
  };

  const fetchStats = async () => {
    try {
      const response = await api.get('/admin/dashboard');
      setDashboardError(null);
      const data = response?.data;
      setStats(data && typeof data === 'object' && !Array.isArray(data) ? data : EMPTY_STATS);
    } catch (error) {
      const status = error.response?.status;
      const rawDetail = error.response?.data?.detail;
      const message = normalizeErrorDetail(rawDetail, error.message || 'Failed to load dashboard');
      setDashboardError({ status, message });
      setStats(EMPTY_STATS);
      if (status === 403) {
        toast.error('Not authorized');
      } else if (status === 401) {
        toast.error('Session expired');
      } else {
        toast.error(message);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (loading || dashboardError) return;
    fetchPendingVerification();
  }, [loading, dashboardError, pendingHours, pendingClientId, fetchPendingVerification]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  if (dashboardError) {
    const is403 = dashboardError.status === 403;
    const is401 = dashboardError.status === 401;
    return (
      <div className="space-y-6">
        <h2 className="text-xl font-semibold text-midnight-blue">Dashboard Overview</h2>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-center">
          <AlertCircle className="w-10 h-10 text-amber-600 mx-auto mb-2" />
          <p className="font-medium text-amber-900">
            {is401 && 'Session expired. Please sign in again.'}
            {is403 && 'Not authorized to view this page.'}
            {!is401 && !is403 && 'Failed to load dashboard. Please try again or refresh.'}
          </p>
          <p className="text-sm text-amber-700 mt-1">{typeof dashboardError.message === 'string' ? dashboardError.message : 'An error occurred.'}</p>
        </div>
      </div>
    );
  }

  const unverifiedCount = stats?.stats?.unverified_documents_count ?? 0;

  const statCards = [
    { label: 'Total Clients', value: stats?.stats?.total_clients || 0, icon: Users, color: 'text-blue-600 bg-blue-100', drilldown: 'clients' },
    { label: 'Total Properties', value: stats?.stats?.total_properties || 0, icon: Building2, color: 'text-purple-600 bg-purple-100', drilldown: 'properties' },
    { label: 'Active Clients', value: stats?.stats?.active_clients || 0, icon: CheckCircle, color: 'text-green-600 bg-green-100', drilldown: 'clients-active' },
    { label: 'Pending Setup', value: stats?.stats?.pending_clients || 0, icon: Clock, color: 'text-amber-600 bg-amber-100', drilldown: 'clients-pending' },
    { label: 'Unverified Documents', value: unverifiedCount, icon: FileCheck, color: 'text-teal-600 bg-teal-100', drilldown: 'scroll-pending-verification', badge: true },
  ];

  const complianceCards = [
    { status: 'GREEN', label: 'Compliant', value: stats?.compliance_overview?.GREEN || 0, bgClass: 'bg-green-50 hover:bg-green-100', textClass: 'text-green-600', labelClass: 'text-green-700' },
    { status: 'AMBER', label: 'Attention Needed', value: stats?.compliance_overview?.AMBER || 0, bgClass: 'bg-amber-50 hover:bg-amber-100', textClass: 'text-amber-600', labelClass: 'text-amber-700' },
    { status: 'RED', label: 'Non-Compliant', value: stats?.compliance_overview?.RED || 0, bgClass: 'bg-red-50 hover:bg-red-100', textClass: 'text-red-600', labelClass: 'text-red-700' },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-midnight-blue">Dashboard Overview</h2>

      {Array.isArray(stats?.operational_alerts) && stats.operational_alerts.length > 0 && (
        <div
          className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-2"
          data-testid="admin-operational-alerts"
        >
          <h3 className="text-sm font-semibold text-amber-900 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            Operational signals
          </h3>
          <ul className="space-y-2 text-sm text-amber-950">
            {stats.operational_alerts.map((a) => (
              <li key={a.code} className="border-b border-amber-100 last:border-0 pb-2 last:pb-0">
                <span className="font-medium">{a.message}</span>
                {a.hint && <p className="text-amber-900 mt-0.5">{a.hint}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Operational Priorities / Action Queue */}
      <div className="bg-white rounded-xl border border-gray-200 p-6" data-testid="admin-priority-actions-panel">
        <h3 className="text-lg font-semibold text-midnight-blue mb-2">Operational Priorities</h3>
        <p className="text-sm text-gray-500 mb-4">Urgent items across compliance, jobs, incidents, approvals, and risk</p>
        <div className="flex flex-wrap items-center gap-4 mb-4">
          <label className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Filter by client</span>
            <select
              value={priorityActionsClientId}
              onChange={(e) => setPriorityActionsClientId(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm min-w-[180px]"
              data-testid="admin-priority-actions-client-filter"
            >
              <option value="">All clients</option>
              {(clientsForFilter || []).map((c) => {
                const crn = c.customer_reference || c.crn || '';
                const name = c.full_name || c.company_name || '';
                const label = crn && name ? `${crn} — ${name}` : name || crn || c.client_id;
                return (
                  <option key={c.client_id} value={c.client_id}>
                    {label}
                  </option>
                );
              })}
            </select>
          </label>
        </div>
        {priorityActions.actions?.length > 0 ? (
          <ul className="space-y-3">
            {priorityActions.actions.map((action, idx) => {
              const clientForAction = action.client_id && (clientsForFilter || []).find((x) => x.client_id === action.client_id);
              const clientDisplay = clientForAction
                ? (() => {
                    const crn = clientForAction.customer_reference || clientForAction.crn || '';
                    const name = clientForAction.full_name || clientForAction.company_name || '';
                    return crn && name ? `${crn} — ${name}` : name || crn || action.client_id;
                  })()
                : action.client_id;
              return (
              <li key={idx} className="flex items-start justify-between gap-4 py-2 border-b border-gray-100 last:border-0">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-midnight-blue">{action.title}</p>
                  {action.description && (
                    <p className="text-xs text-gray-600 mt-0.5 line-clamp-2">{action.description}</p>
                  )}
                  {action.client_id && (
                    <p className="text-xs text-gray-500 mt-1">Client: {clientDisplay}</p>
                  )}
                </div>
                {action.recommended_url ? (
                  action.recommended_url.startsWith('/admin/clients/') && action.client_id ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        if (onSelectClient) onSelectClient(action.client_id);
                        else navigate('/admin/dashboard', { state: { selectedClientId: action.client_id } });
                      }}
                      className="shrink-0 inline-flex px-3 py-1.5 bg-electric-teal text-white rounded-lg text-sm font-medium hover:opacity-90 cursor-pointer border-0"
                    >
                      {action.recommended_action_label || 'View client'}
                    </button>
                  ) : (
                    <Link
                      to={action.recommended_url}
                      className="shrink-0 inline-flex px-3 py-1.5 bg-electric-teal text-white rounded-lg text-sm font-medium hover:opacity-90 no-underline cursor-pointer"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {action.recommended_action_label || 'View'}
                    </Link>
                  )
                ) : (
                  <span className="shrink-0 px-3 py-1.5 bg-gray-200 text-gray-600 rounded-lg text-sm">—</span>
                )}
              </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-gray-500 py-4">No priority actions for the selected filter.</p>
        )}
      </div>

      {/* Stats Grid - Clickable tiles */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
        {statCards.map((stat, idx) => {
          const Wrapper = stat.drilldown ? 'button' : 'div';
          return (
            <Wrapper
              key={idx}
              onClick={stat.drilldown === 'scroll-pending-verification'
                ? () => document.getElementById('pending-verification-section')?.scrollIntoView({ behavior: 'smooth' })
                : stat.drilldown ? () => onShowDrilldown && onShowDrilldown(stat.drilldown) : undefined}
              className={`bg-white rounded-xl border border-gray-200 p-6 text-left transition-all ${stat.drilldown ? 'hover:shadow-lg hover:border-electric-teal cursor-pointer group' : ''}`}
              data-testid={stat.drilldown ? `kpi-tile-${stat.drilldown}` : 'kpi-tile-unverified-documents'}
            >
              <div className="flex items-center gap-4">
                <div className={`p-3 rounded-lg ${stat.color} ${stat.drilldown ? 'group-hover:scale-110 transition-transform' : ''}`}>
                  <stat.icon className="w-6 h-6" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-2xl font-bold text-midnight-blue flex items-center gap-2">
                    {stat.value}
                    {stat.badge && stat.value > 0 && (
                      <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-teal-100 text-teal-700" title="Awaiting admin verification">
                        pending
                      </span>
                    )}
                  </p>
                  <p className="text-sm text-gray-500">{stat.label}</p>
                </div>
              </div>
              {stat.drilldown && (
                <div className="mt-3 text-xs text-electric-teal opacity-0 group-hover:opacity-100 transition-opacity">
                  Click to view details →
                </div>
              )}
            </Wrapper>
          );
        })}
      </div>

      {/* Compliance Overview - Clickable tiles */}
      {stats?.compliance_overview && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-midnight-blue mb-4">Compliance Overview</h3>
          <div className="grid grid-cols-3 gap-4">
            {complianceCards.map((card) => (
              <button
                key={card.status}
                onClick={() => onShowDrilldown && onShowDrilldown(`compliance-${card.status}`)}
                className={`text-center p-4 rounded-lg cursor-pointer transition-all hover:shadow-md group ${card.bgClass}`}
                data-testid={`kpi-tile-compliance-${card.status}`}
              >
                <p className={`text-3xl font-bold ${card.textClass}`}>{card.value}</p>
                <p className={`text-sm ${card.labelClass}`}>{card.label}</p>
                <p className="mt-2 text-xs text-electric-teal opacity-0 group-hover:opacity-100 transition-opacity">
                  View properties →
                </p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Pending verification (UPLOADED older than X hours) */}
      <div id="pending-verification-section" className="bg-white rounded-xl border border-gray-200 p-6" data-testid="pending-verification-section">
        <h3 className="text-lg font-semibold text-midnight-blue mb-4">Pending verification</h3>
        <p className="text-sm text-gray-500 mb-4">
          Documents with status UPLOADED (awaiting verification). Set minimum age in hours to focus on older
          queue items; choose 0 to list every pending upload, including those just added.
        </p>
        {pendingListWarning && (
          <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800" role="alert">
            {pendingListWarning}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-4 mb-4">
          <label className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Min. age (hours)</span>
            <select
              value={pendingHours}
              onChange={(e) => setPendingHours(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
              data-testid="pending-verification-hours"
            >
              <option value={0}>0 — all pending</option>
              <option value={24}>24</option>
              <option value={48}>48</option>
              <option value={72}>72</option>
            </select>
          </label>
          <label className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Client ID</span>
            <input
              type="text"
              value={pendingClientId}
              onChange={(e) => setPendingClientId(e.target.value)}
              placeholder="Optional"
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-48"
              data-testid="pending-verification-client-id"
            />
          </label>
          <button
            type="button"
            onClick={fetchPendingVerification}
            disabled={pendingLoading}
            className="px-4 py-2 bg-electric-teal text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
            data-testid="pending-verification-refresh"
          >
            {pendingLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Refresh list
          </button>
          <button
            type="button"
            onClick={handleBackfillEvidenceMatch}
            disabled={backfillBusy || pendingLoading}
            className="px-4 py-2 bg-midnight-blue text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50"
            data-testid="pending-verification-backfill-evidence-match"
            title="Batch-tag or re-persist evidence match for legacy rows (audited)"
          >
            {backfillBusy ? 'Backfill…' : 'Backfill evidence match'}
          </button>
        </div>
        {pendingLoading ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-6 h-6 animate-spin text-electric-teal" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-600">
                  <th className="py-2 pr-4">Document ID</th>
                  <th className="py-2 pr-4">Client</th>
                  <th className="py-2 pr-4">CRN</th>
                  <th className="py-2 pr-4">Client ID</th>
                  <th className="py-2 pr-4">Property ID</th>
                  <th className="py-2 pr-4">Requirement</th>
                  <th className="py-2 pr-4">Predicted type</th>
                  <th className="py-2 pr-4">Match outcome</th>
                  <th className="py-2 pr-4">Confidence</th>
                  <th className="py-2 pr-4">Satisfies</th>
                  <th className="py-2 pr-4">Mismatch reason</th>
                  <th className="py-2 pr-4">Legacy</th>
                  <th className="py-2 pr-4">Uploaded at</th>
                  <th className="py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(pendingList.documents ?? []).length === 0 ? (
                  <tr><td colSpan={14} className="py-4 text-gray-500 text-center">No documents matching filters.</td></tr>
                ) : (
                  (pendingList.documents ?? []).filter(Boolean).map((doc, idx) => (
                    <tr
                      key={doc?.document_id ?? doc?.client_id ?? idx}
                      className="border-b border-gray-100 hover:bg-gray-50"
                    >
                      <td
                        className="py-2 pr-4 font-mono text-xs cursor-pointer"
                        onClick={() => doc?.client_id && onSelectClient?.(doc.client_id)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && doc?.client_id) onSelectClient?.(doc.client_id); }}
                      >{doc?.document_id ?? '—'}</td>
                      <td
                        className="py-2 pr-4 font-medium text-midnight-blue cursor-pointer"
                        onClick={() => doc?.client_id && onSelectClient?.(doc.client_id)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && doc?.client_id) onSelectClient?.(doc.client_id); }}
                      >{doc?.client_name ?? '—'}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{doc?.crn ?? '—'}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{doc?.client_id ?? '—'}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{doc?.property_id ?? '—'}</td>
                      <td className="py-2 pr-4 text-xs max-w-[140px]" title={doc?.requirement_id || ''}>
                        <div className="font-mono text-[11px] text-gray-700">{doc?.requirement_id ?? '—'}</div>
                        {doc?.requirement_label && (
                          <div className="text-gray-500 truncate mt-0.5">{doc.requirement_label}</div>
                        )}
                      </td>
                      <td className="py-2 pr-4 text-xs">{doc?.predicted_document_type ?? '—'}</td>
                      <td className="py-2 pr-4 text-xs">{doc?.match_outcome ?? '—'}</td>
                      <td className="py-2 pr-4 text-xs">{doc?.match_confidence != null ? String(doc.match_confidence) : '—'}</td>
                      <td className="py-2 pr-4 text-xs">
                        {doc?.evidence_satisfies_requirement === true ? (
                          <span className="text-green-700">Yes</span>
                        ) : doc?.evidence_satisfies_requirement === false ? (
                          <span className="text-amber-800">No</span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="py-2 pr-4 text-xs max-w-[160px]">
                        <div className="line-clamp-2" title={doc?.mismatch_reason_text || doc?.mismatch_reason_code || ''}>
                          {doc?.mismatch_reason_text || doc?.mismatch_reason_code || '—'}
                        </div>
                      </td>
                      <td className="py-2 pr-4 text-xs">
                        {doc?.evidence_match_legacy_state ? (
                          <span className="px-1.5 py-0.5 rounded bg-gray-200 text-gray-800" title="Pre-engine or unclassified — not a strong auto-match">
                            {String(doc.evidence_match_legacy_state)}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="py-2 pr-4 text-gray-600">{doc?.uploaded_at ? new Date(doc.uploaded_at).toLocaleString() : '—'}</td>
                      <td className="py-2 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-2 flex-wrap">
                          <button
                            type="button"
                            onClick={() => handleViewDocument(doc)}
                            className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded"
                            title="View document"
                            data-testid={`view-doc-${doc?.document_id}`}
                          >
                            <Eye className="w-3.5 h-3.5" />
                            View
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDownloadDocument(doc)}
                            className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded"
                            title="Download document"
                            data-testid={`download-doc-${doc?.document_id}`}
                          >
                            <Download className="w-3.5 h-3.5" />
                            Download
                          </button>
                          <button
                            type="button"
                            onClick={() => handleVerifyDocument(doc)}
                            className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-green-700 bg-green-100 hover:bg-green-200 rounded"
                            data-testid={`verify-doc-${doc?.document_id}`}
                          >
                            <CheckCircle className="w-3.5 h-3.5" />
                            Verify
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setResolveMatchModal(doc);
                              setResolveMatchAction('approve_override');
                              setResolveMatchReason('');
                              setResolveRelinkId('');
                            }}
                            className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-teal-900 bg-teal-100 hover:bg-teal-200 rounded"
                            data-testid={`resolve-match-${doc?.document_id}`}
                          >
                            Resolve match
                          </button>
                          <button
                            type="button"
                            onClick={() => { setRejectModalDoc({ document_id: doc.document_id, client_name: doc.client_name }); setRejectReason(''); }}
                            className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-red-700 bg-red-100 hover:bg-red-200 rounded"
                            data-testid={`reject-doc-${doc?.document_id}`}
                          >
                            <XCircle className="w-3.5 h-3.5" />
                            Reject
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            {pendingList.total > 0 && (
              <p className="text-xs text-gray-500 mt-2">
                Showing {pendingList.returned} of {pendingList.total}
                {pendingList.has_more ? ' (more available)' : ''}.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Reject document modal */}
      {rejectModalDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-labelledby="reject-document-title">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h2 id="reject-document-title" className="text-lg font-semibold text-midnight-blue mb-2">Reject document</h2>
            <p className="text-sm text-gray-600 mb-4">
              Document {rejectModalDoc.document_id}
              {rejectModalDoc.client_name && ` · ${rejectModalDoc.client_name}`}
            </p>
            <label className="block text-sm font-medium text-gray-700 mb-2">Reason for rejection (required)</label>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. Document does not meet requirement"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm min-h-[80px] mb-4"
              data-testid="reject-document-reason"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => { setRejectModalDoc(null); setRejectReason(''); }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRejectDocument}
                disabled={!rejectReason.trim() || rejectSubmitting}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded-lg flex items-center gap-2"
                data-testid="reject-document-submit"
              >
                {rejectSubmitting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                Reject
              </button>
            </div>
          </div>
        </div>
      )}

      {verifyOverrideModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-labelledby="verify-override-title">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
            <h2 id="verify-override-title" className="text-lg font-semibold text-midnight-blue mb-2">Verify with evidence override</h2>
            <p className="text-sm text-gray-600 mb-2">
              Document {verifyOverrideModal.doc?.document_id}
              {verifyOverrideModal.doc?.client_name && ` · ${verifyOverrideModal.doc.client_name}`}
            </p>
            {verifyOverrideModal.detail?.evidence_match && (
              <div className="text-xs text-gray-700 bg-gray-50 border border-gray-200 rounded-lg p-3 mb-3 font-mono">
                <div>Outcome: {verifyOverrideModal.detail.evidence_match.match_outcome ?? '—'}</div>
                <div>Predicted: {verifyOverrideModal.detail.evidence_match.predicted_document_type ?? '—'}</div>
                <div className="mt-1 text-gray-600">{verifyOverrideModal.detail.evidence_match.mismatch_reason_text ?? ''}</div>
              </div>
            )}
            <p className="text-xs text-amber-800 mb-3">
              Override is audited (EVIDENCE_MATCH_OVERRIDE_VERIFY). Use only after manual review of the file against the obligation.
            </p>
            <label className="block text-sm font-medium text-gray-700 mb-2">Reason (required)</label>
            <textarea
              value={verifyOverrideReason}
              onChange={(e) => setVerifyOverrideReason(e.target.value)}
              placeholder="e.g. Verified CP12 against gas safety obligation — filename misleading"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm min-h-[80px] mb-4"
              data-testid="verify-override-reason"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => { setVerifyOverrideModal(null); setVerifyOverrideReason(''); }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleVerifyWithOverride}
                disabled={!verifyOverrideReason.trim() || verifyOverrideSubmitting}
                className="px-4 py-2 text-sm font-medium text-white bg-green-700 hover:bg-green-800 disabled:opacity-50 rounded-lg flex items-center gap-2"
                data-testid="verify-override-submit"
              >
                {verifyOverrideSubmitting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                Verify with override
              </button>
            </div>
          </div>
        </div>
      )}

      {resolveMatchModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-labelledby="resolve-match-title">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
            <h2 id="resolve-match-title" className="text-lg font-semibold text-midnight-blue mb-2">Resolve evidence match</h2>
            <p className="text-sm text-gray-600 mb-4">
              Document {resolveMatchModal.document_id} — audited admin action on the evidence document matching queue.
            </p>
            <label className="block text-sm font-medium text-gray-700 mb-2">Action</label>
            <select
              value={resolveMatchAction}
              onChange={(e) => setResolveMatchAction(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3"
              data-testid="resolve-match-action"
            >
              <option value="approve_override">Approve override (treat as matching obligation)</option>
              <option value="reject_evidence">Reject evidence (document REJECTED)</option>
              <option value="relink_requirement">Relink to another requirement (scope-checked)</option>
            </select>
            {resolveMatchAction === 'relink_requirement' && (
              <label className="block text-sm font-medium text-gray-700 mb-2">
                New requirement_id
                <input
                  type="text"
                  value={resolveRelinkId}
                  onChange={(e) => setResolveRelinkId(e.target.value)}
                  className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono"
                  placeholder="requirement_id"
                  data-testid="resolve-match-relink-id"
                />
              </label>
            )}
            <label className="block text-sm font-medium text-gray-700 mb-2 mt-2">Notes (optional)</label>
            <textarea
              value={resolveMatchReason}
              onChange={(e) => setResolveMatchReason(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm min-h-[72px] mb-4"
              data-testid="resolve-match-notes"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => { setResolveMatchModal(null); setResolveMatchReason(''); setResolveRelinkId(''); }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleResolveEvidenceMatch}
                disabled={resolveSubmitting}
                className="px-4 py-2 text-sm font-medium text-white bg-electric-teal hover:opacity-90 disabled:opacity-50 rounded-lg"
                data-testid="resolve-match-submit"
              >
                {resolveSubmitting ? <RefreshCw className="w-4 h-4 animate-spin" /> : 'Submit'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Recent Activity */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-midnight-blue mb-4">Recent Activity</h3>
        <div className="space-y-3">
          {(() => {
            const raw = stats?.recent_activity ?? [];
            const activities = Array.isArray(raw) ? raw.filter(Boolean).slice(0, 5) : [];
            return activities.length > 0
              ? activities.map((activity, idx) => (
                  <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                    <Activity className="w-5 h-5 text-electric-teal" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-midnight-blue">{activity?.action ?? '—'}</p>
                      <p className="text-xs text-gray-500">{activity?.timestamp ? new Date(activity.timestamp).toLocaleString() : '—'}</p>
                    </div>
                  </div>
                ))
              : <p className="text-gray-500 text-sm">No recent activity</p>;
          })()}
        </div>
      </div>
    </div>
  );
};

// Main Admin Dashboard Component
const AdminDashboard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Support URL query param for tab (used by UnifiedAdminLayout sidebar links)
  const tabFromUrl = searchParams.get('tab');
  const [activeTab, setActiveTab] = useState(() => tabFromUrl || 'overview');
  const [selectedClientId, setSelectedClientId] = useState(null);
  const [drilldownType, setDrilldownType] = useState(null);

  // Open client panel when navigated with state (e.g. from priority action "View client" from another tab)
  useEffect(() => {
    const stateClientId = location.state?.selectedClientId;
    if (stateClientId) {
      setSelectedClientId(stateClientId);
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state?.selectedClientId, location.pathname, navigate]);

  // Effective tab: URL takes precedence when present, so sidebar links work. When user clicks a tab we update the URL too.
  const effectiveTab = (tabFromUrl && tabFromUrl !== 'overview') ? tabFromUrl : (activeTab || 'overview');

  /** Switch tab and keep URL in sync so that tab clicks work even when we landed on Clients (or any tab) via sidebar. */
  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (tabId === 'overview') next.delete('tab');
      else next.set('tab', tabId);
      return next;
    });
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleSelectClient = (client) => {
    setSelectedClientId(client.client_id);
  };

  const handleShowDrilldown = (type) => {
    setDrilldownType(type);
  };

  /** Navigate to another tab from Statistics (and optionally open a drilldown modal on Overview). */
  const handleNavigateToTab = (tabId, options = {}) => {
    if (options.drilldown) setDrilldownType(options.drilldown);
    handleTabChange(tabId);
  };

  const tabs = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'statistics', label: 'Statistics', icon: BarChart3 },
    { id: 'jobs', label: 'Jobs', icon: Clock },
    { id: 'clients', label: 'Clients', icon: Users },
    { id: 'admins', label: 'Admins', icon: UserCog },
    { id: 'rules', label: 'Legacy rules', icon: BookOpen },
    { id: 'templates', label: 'Templates', icon: Mail },
    { id: 'emailDelivery', label: 'Email delivery', icon: Mail },
    { id: 'audit', label: 'System Audit Logs', icon: FileText },
  ];

  const renderContent = () => {
    switch (effectiveTab) {
      case 'overview': return <DashboardOverview onShowDrilldown={handleShowDrilldown} onSelectClient={(id) => setSelectedClientId(id)} />;
      case 'statistics': return <StatisticsDashboard onNavigateToTab={handleNavigateToTab} />;
      case 'jobs': return <JobsMonitoring />;
      case 'clients': return <ClientsManagement />;
      case 'admins': return <AdminsManagement />;
      case 'rules': return <RulesManagement />;
      case 'templates': return <EmailTemplates />;
      case 'emailDelivery': return <EmailDelivery />;
      case 'audit': return <AuditLogs />;
      default: return <DashboardOverview onShowDrilldown={handleShowDrilldown} onSelectClient={(id) => setSelectedClientId(id)} />;
    }
  };

  return (
    <UnifiedAdminLayout>
      {/* Client Detail Modal */}
      {selectedClientId && (
        <ClientDetailModal 
          clientId={selectedClientId} 
          onClose={() => setSelectedClientId(null)} 
        />
      )}

      {/* KPI Drilldown Modal */}
      {drilldownType && (
        <KPIDrilldownModal 
          drilldownType={drilldownType} 
          onClose={() => setDrilldownType(null)}
          onSelectClient={handleSelectClient}
        />
      )}

      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900" data-testid="admin-dashboard-title">Dashboard Overview</h1>
        <p className="text-gray-500 mt-1">Manage clients, automation rules, and system settings</p>
      </div>

      {/* Tab Navigation (internal to this page for sub-sections) */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="flex space-x-4 overflow-x-auto pb-1" data-testid="admin-tab-nav">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              data-testid={`admin-tab-${tab.id}`}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-t-lg transition-colors whitespace-nowrap ${
                effectiveTab === tab.id 
                  ? 'bg-electric-teal text-white' 
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Main Content */}
      <main data-testid="admin-main-content">
        {renderContent()}
      </main>
    </UnifiedAdminLayout>
  );
};

export default AdminDashboard;
