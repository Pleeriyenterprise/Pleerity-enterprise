import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api from '../api/client';
import { toast } from 'sonner';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { 
  LayoutDashboard, 
  Users, 
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
  UserMinus,
  RotateCcw,
  MailPlus,
  MessageSquare,
  History,
  Settings,
  ClipboardCheck,
  ExternalLink,
  Sparkles,
  CreditCard
} from 'lucide-react';

// Global Search Component
const GlobalSearch = ({ onSelectClient }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
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
      const response = await api.get(`/admin/search?q=${encodeURIComponent(searchTerm)}&limit=10`);
      setResults(response.data.results || []);
      setIsOpen(true);
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleInputChange = (e) => {
    const value = e.target.value;
    setQuery(value);
    
    // Debounce search
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }
    debounceTimer.current = setTimeout(() => {
      handleSearch(value);
    }, 300);
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

      {isOpen && results.length > 0 && (
        <div className="absolute top-full left-0 mt-2 w-96 bg-white rounded-xl shadow-lg border border-gray-200 z-50 overflow-hidden" data-testid="search-results">
          <div className="p-2 text-xs text-gray-500 border-b border-gray-100">
            {results.length} result{results.length !== 1 ? 's' : ''} found
          </div>
          <div className="max-h-80 overflow-y-auto">
            {results.map((client) => (
              <button
                key={client.client_id}
                onClick={() => handleSelectResult(client)}
                className="w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-0"
                data-testid={`search-result-${client.client_id}`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-midnight-blue">{client.full_name}</p>
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
            ))}
          </div>
        </div>
      )}

      {isOpen && query.length >= 2 && results.length === 0 && !loading && (
        <div className="absolute top-full left-0 mt-2 w-96 bg-white rounded-xl shadow-lg border border-gray-200 z-50 p-4 text-center text-gray-500">
          No results found
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

  const fetchClientData = useCallback(async () => {
    if (!clientId) return;
    setLoading(true);
    try {
      const [detailRes, readinessRes, timelineRes] = await Promise.all([
        api.get(`/admin/clients/${clientId}`),
        api.get(`/admin/clients/${clientId}/readiness`),
        api.get(`/admin/clients/${clientId}/audit-timeline?limit=30`)
      ]);
      
      setClient(detailRes.data);
      setReadiness(readinessRes.data);
      setTimeline(timelineRes.data.timeline || []);
      
      // Initialize profile form
      const c = detailRes.data.client;
      setProfileForm({
        full_name: c.full_name || '',
        phone: c.phone || '',
        company_name: c.company_name || '',
        preferred_contact: c.preferred_contact || 'EMAIL'
      });
    } catch (error) {
      toast.error('Failed to load client data');
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    if (clientId) {
      fetchClientData();
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
    try {
      await api.post(`/admin/clients/${clientId}/resend-password-setup`);
      toast.success('Password setup link resent');
      fetchClientData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to resend password link');
    } finally {
      setResendingPassword(false);
    }
  };

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

  const c = client.client;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto py-8" data-testid="client-detail-modal">
      <div className="bg-white rounded-xl w-full max-w-5xl mx-4 shadow-xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-midnight-blue text-white p-6 flex items-center justify-between flex-shrink-0">
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

        {/* Tabs */}
        <div className="border-b border-gray-200 px-6 flex-shrink-0">
          <div className="flex gap-6">
            {[
              { id: 'overview', label: 'Overview', icon: Eye },
              { id: 'setup', label: 'Setup Controls', icon: Settings },
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
                  {client.properties?.slice(0, 5).map((prop) => (
                    <div key={prop.property_id} className="flex items-center justify-between bg-gray-50 rounded-lg p-3">
                      <div>
                        <p className="font-medium">{prop.nickname || prop.address_line_1}</p>
                        <p className="text-sm text-gray-500">{prop.postcode}</p>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        prop.compliance_status === 'GREEN' ? 'bg-green-100 text-green-700' :
                        prop.compliance_status === 'AMBER' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'
                      }`}>{prop.compliance_status}</span>
                    </div>
                  ))}
                </div>
              </div>
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
                  {readiness?.checklist?.map((item) => (
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
                  <button
                    onClick={handleResendPassword}
                    disabled={resendingPassword}
                    className="flex items-center justify-center gap-2 p-4 bg-midnight-blue text-white rounded-lg hover:bg-blue-900 disabled:opacity-50 transition-colors"
                    data-testid="resend-password-btn"
                  >
                    {resendingPassword ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Mail className="w-5 h-5" />}
                    Resend Password Link
                  </button>
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
                {timeline.length === 0 ? (
                  <p className="text-gray-500 text-center py-8">No audit events found</p>
                ) : (
                  timeline.map((event, idx) => (
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
          const status = drilldownType === 'clients-active' ? '&subscription_status=ACTIVE' : 
                         drilldownType === 'clients-pending' ? '&onboarding_status=PENDING' : '';
          endpoint = `/admin/clients?limit=50${status}`;
        } else if (drilldownType === 'properties') {
          endpoint = '/admin/kpi/properties?limit=50';
        } else if (drilldownType.startsWith('compliance-')) {
          const status = drilldownType.replace('compliance-', '');
          endpoint = `/admin/kpi/properties?status_filter=${status}&limit=50`;
        }

        const response = await api.get(endpoint);
        if (cancelled) return;
        if (drilldownType.includes('client')) {
          setData(response.data.clients || []);
          setTotalCount(response.data.total || 0);
        } else {
          setData(response.data.properties || []);
          setTotalCount(response.data.total || 0);
        }
      } catch (error) {
        if (!cancelled) {
          toast.error('Failed to load drill-down data');
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
      default: return 'Details';
    }
  };

  const isClientView = drilldownType?.includes('client');

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
          ) : data.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              No records found
            </div>
          ) : isClientView ? (
            // Client list view
            <div className="space-y-3">
              {data.map((client) => (
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
          ) : (
            // Properties list view
            <div className="space-y-3">
              {data.map((property) => (
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
                      <p className="text-sm text-gray-500">{property.postcode} • {property.local_authority || 'N/A'}</p>
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
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(null);

  const fetchJobsStatus = async () => {
    try {
      const response = await api.get('/admin/jobs/status');
      setJobsStatus(response.data);
    } catch (error) {
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

  const triggerJob = async (jobType) => {
    setTriggering(jobType);
    try {
      const response = await api.post(`/admin/jobs/trigger/${jobType}`);
      toast.success(response.data.message);
      fetchJobsStatus();
    } catch (error) {
      toast.error(`Failed to trigger ${jobType} job`);
    } finally {
      setTriggering(null);
    }
  };

  // Map job IDs to job types for triggering
  const getJobType = (jobId) => {
    if (jobId.includes('daily')) return 'daily';
    if (jobId.includes('monthly')) return 'monthly';
    if (jobId.includes('compliance')) return 'compliance';
    return 'daily';
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

      {/* System Status */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className={`w-3 h-3 rounded-full ${jobsStatus?.system_status === 'operational' ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="font-medium text-midnight-blue">
            System Status: {jobsStatus?.system_status === 'operational' ? 'Operational' : 'Issues Detected'}
          </span>
        </div>

        {/* Scheduled Jobs */}
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Scheduled Jobs</h3>
          {jobsStatus?.scheduled_jobs?.map((job) => {
            const jobType = getJobType(job.id);
            return (
              <div key={job.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-4">
                  <Clock className="w-5 h-5 text-electric-teal" />
                  <div>
                    <p className="font-medium text-midnight-blue">{job.name}</p>
                    <p className="text-sm text-gray-500">
                      Next run: {job.next_run ? new Date(job.next_run).toLocaleString() : 'Not scheduled'}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => triggerJob(jobType)}
                  disabled={triggering !== null}
                  className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 transition-colors disabled:opacity-50"
                  data-testid={`trigger-${jobType}-btn`}
                >
                  {triggering === jobType ? (
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
      </div>

      {/* Manual Job Triggers */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-midnight-blue mb-4">Manual Job Triggers</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            onClick={() => triggerJob('daily')}
            disabled={triggering !== null}
            className="flex flex-col items-center gap-2 p-4 border border-gray-200 rounded-lg hover:border-electric-teal hover:bg-teal-50 transition-colors disabled:opacity-50"
            data-testid="manual-trigger-daily"
          >
            {triggering === 'daily' ? (
              <RefreshCw className="w-6 h-6 animate-spin text-electric-teal" />
            ) : (
              <Mail className="w-6 h-6 text-electric-teal" />
            )}
            <span className="font-medium text-midnight-blue">Daily Reminders</span>
            <span className="text-xs text-gray-500">Send expiry reminders</span>
          </button>

          <button
            onClick={() => triggerJob('monthly')}
            disabled={triggering !== null}
            className="flex flex-col items-center gap-2 p-4 border border-gray-200 rounded-lg hover:border-electric-teal hover:bg-teal-50 transition-colors disabled:opacity-50"
            data-testid="manual-trigger-monthly"
          >
            {triggering === 'monthly' ? (
              <RefreshCw className="w-6 h-6 animate-spin text-electric-teal" />
            ) : (
              <Calendar className="w-6 h-6 text-electric-teal" />
            )}
            <span className="font-medium text-midnight-blue">Monthly Digest</span>
            <span className="text-xs text-gray-500">Send compliance summary</span>
          </button>

          <button
            onClick={() => triggerJob('compliance')}
            disabled={triggering !== null}
            className="flex flex-col items-center gap-2 p-4 border border-gray-200 rounded-lg hover:border-amber-500 hover:bg-amber-50 transition-colors disabled:opacity-50"
            data-testid="manual-trigger-compliance"
          >
            {triggering === 'compliance' ? (
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
              <span className="font-medium text-amber-600">{jobsStatus?.daily_reminders?.pending_count || 0}</span>
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
              <span className="font-medium text-electric-teal">{jobsStatus?.monthly_digest?.total_sent || 0}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const ClientsManagement = () => {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedClient, setSelectedClient] = useState(null);
  const [clientDetails, setClientDetails] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    fetchClients();
  }, []);

  const fetchClients = async () => {
    try {
      const response = await api.get('/admin/clients?limit=100');
      setClients(response.data.clients);
    } catch (error) {
      toast.error('Failed to load clients');
    } finally {
      setLoading(false);
    }
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
      await api.post(`/admin/clients/${clientId}/resend-password-setup`);
      toast.success('Password setup email sent');
    } catch (error) {
      toast.error('Failed to send email');
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

  const filteredClients = clients.filter(client => {
    const matchesSearch = client.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         client.full_name?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || client.onboarding_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

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
        <h2 className="text-xl font-semibold text-midnight-blue">Clients ({clients.length})</h2>
      </div>

      {/* Search and Filter */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
        >
          <option value="all">All Status</option>
          <option value="PROVISIONED">Provisioned</option>
          <option value="PENDING_PAYMENT">Pending Payment</option>
          <option value="INTAKE_COMPLETE">Intake Complete</option>
        </select>
      </div>

      <div className="flex gap-6">
        {/* Client List */}
        <div className="flex-1 bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Client</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subscription</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredClients.map((client) => (
                  <tr 
                    key={client.client_id} 
                    className={`hover:bg-gray-50 cursor-pointer ${selectedClient === client.client_id ? 'bg-teal-50' : ''}`}
                    onClick={() => fetchClientDetails(client.client_id)}
                  >
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-midnight-blue">{client.full_name}</p>
                        <p className="text-sm text-gray-500">{client.email}</p>
                      </div>
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
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-midnight-blue">Client Details</h3>
              <button onClick={() => { setSelectedClient(null); setClientDetails(null); }} className="text-gray-400 hover:text-gray-600">
                <XCircle className="w-5 h-5" />
              </button>
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
            </div>

            {/* Portal User */}
            {clientDetails.portal_users?.length > 0 && (
              <div className="border-t pt-4">
                <h4 className="text-sm font-medium text-gray-500 mb-3">Portal Access</h4>
                {clientDetails.portal_users.map((user, idx) => (
                  <div key={idx} className="space-y-2">
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
                {clientDetails.portal_users[0]?.password_status === 'NOT_SET' && (
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
                  {Object.entries(clientDetails.readiness_check).map(([key, value]) => (
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
              {clientDetails.properties?.slice(0, 3).map((prop, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm mb-2">
                  <Building2 className="w-4 h-4 text-gray-400" />
                  <span>{prop.address_line_1}, {prop.city}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
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

  useEffect(() => {
    let cancelled = false;
    const fetchLogs = async () => {
      setLoading(true);
      try {
        let url = `/admin/audit-logs?limit=${limit}&skip=${page * limit}`;
        if (actionFilter) url += `&action=${actionFilter}`;
        const response = await api.get(url);
        if (cancelled) return;
        setLogs(response.data.logs);
        setTotalLogs(response.data.total);
      } catch (error) {
        if (!cancelled) toast.error('Failed to load audit logs');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchLogs();
    return () => { cancelled = true; };
  }, [actionFilter, page]);

  const getActionIcon = (action) => {
    if (action.includes('LOGIN')) return <Shield className="w-4 h-4" />;
    if (action.includes('EMAIL')) return <Mail className="w-4 h-4" />;
    if (action.includes('PASSWORD')) return <Activity className="w-4 h-4" />;
    if (action.includes('PROVISIONING')) return <CheckCircle className="w-4 h-4" />;
    return <FileText className="w-4 h-4" />;
  };

  const getActionColor = (action) => {
    if (action.includes('SUCCESS') || action.includes('COMPLETE')) return 'text-green-600 bg-green-50';
    if (action.includes('FAILED') || action.includes('ERROR')) return 'text-red-600 bg-red-50';
    if (action.includes('SENT')) return 'text-blue-600 bg-blue-50';
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
        <h2 className="text-xl font-semibold text-midnight-blue">Audit Logs ({totalLogs})</h2>
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
                {logs.map((log, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${getActionColor(log.action)}`}>
                        {getActionIcon(log.action)}
                        {log.action}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {log.metadata && Object.entries(log.metadata).slice(0, 3).map(([k, v]) => (
                        v && <span key={k} className="mr-3"><strong>{k}:</strong> {String(v).substring(0, 50)}</span>
                      ))}
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
      });
    } catch (e) {
      toast.error('Failed to load email delivery list');
      setData({ total: 0, returned: 0, has_more: false, items: [] });
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
      await adminAPI.resendPasswordSetup(resendConfirmRow.client_id);
      toast.success('Password setup email resent');
      setResendConfirmRow(null);
      fetchEmailDelivery();
    } catch (e) {
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
    } finally {
      setResendLoading(false);
    }
  }, [resendConfirmRow, fetchEmailDelivery]);

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
                {data.items.length === 0 ? (
                  <tr><td colSpan={7} className="px-4 py-6 text-gray-500 text-center">No records.</td></tr>
                ) : (
                  data.items.map((row, idx) => (
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
                      <td className="px-4 py-2 text-gray-600">{row.provider_error_type || row.provider_error_code ? `${row.provider_error_type || ''} ${row.provider_error_code || ''}`.trim() : '—'}</td>
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
    </div>
  );
};

const MessageLogs = () => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMessages();
  }, []);

  const fetchMessages = async () => {
    try {
      const response = await api.get('/admin/audit-logs?action=EMAIL_SENT&limit=50');
      // Also fetch failed emails
      const failedResponse = await api.get('/admin/audit-logs?action=EMAIL_FAILED&limit=50');
      
      const allMessages = [...response.data.logs, ...failedResponse.data.logs]
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      setMessages(allMessages);
    } catch (error) {
      toast.error('Failed to load message logs');
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-midnight-blue">Message Logs</h2>
        <button
          onClick={fetchMessages}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Recipient</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Template</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Provider ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {messages.map((msg, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(msg.timestamp).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-sm font-medium text-midnight-blue">
                    {msg.metadata?.recipient || 'N/A'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {msg.metadata?.template || 'N/A'}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                      msg.metadata?.status === 'sent' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {msg.metadata?.status === 'sent' ? (
                        <CheckCircle className="w-3 h-3" />
                      ) : (
                        <XCircle className="w-3 h-3" />
                      )}
                      {msg.metadata?.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 font-mono">
                    {msg.metadata?.postmark_id ? msg.metadata.postmark_id.substring(0, 12) + '...' : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// Admin Users Management Component
const AdminsManagement = () => {
  const [admins, setAdmins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [formData, setFormData] = useState({
    email: '',
    full_name: ''
  });

  useEffect(() => {
    fetchAdmins();
  }, []);

  const fetchAdmins = async () => {
    setLoading(true);
    try {
      const response = await api.get('/admin/admins');
      setAdmins(response.data.admins || []);
    } catch (error) {
      toast.error('Failed to load admin users');
    } finally {
      setLoading(false);
    }
  };

  const handleInvite = async (e) => {
    e.preventDefault();
    if (!formData.email || !formData.full_name) {
      toast.error('Please fill in all fields');
      return;
    }

    setInviteLoading(true);
    try {
      await api.post('/admin/admins/invite', formData);
      toast.success('Admin invitation sent successfully');
      setShowInviteForm(false);
      setFormData({ email: '', full_name: '' });
      fetchAdmins();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to send invitation');
    } finally {
      setInviteLoading(false);
    }
  };

  const handleDeactivate = async (portalUserId, email) => {
    if (!window.confirm(`Are you sure you want to deactivate ${email}?`)) return;
    
    setActionLoading(portalUserId);
    try {
      await api.delete(`/admin/admins/${portalUserId}`);
      toast.success('Admin deactivated successfully');
      fetchAdmins();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to deactivate admin');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReactivate = async (portalUserId) => {
    setActionLoading(portalUserId);
    try {
      await api.post(`/admin/admins/${portalUserId}/reactivate`);
      toast.success('Admin reactivated successfully');
      fetchAdmins();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to reactivate admin');
    } finally {
      setActionLoading(null);
    }
  };

  const handleResendInvite = async (portalUserId, email) => {
    setActionLoading(portalUserId);
    try {
      await api.post(`/admin/admins/${portalUserId}/resend-invite`);
      toast.success(`Invitation resent to ${email}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to resend invitation');
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusBadge = (status, passwordStatus) => {
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
            Manage administrator access to Compliance Vault Pro
          </p>
        </div>
        <div className="flex gap-3">
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
              {admins.map((admin) => {
                const statusBadge = getStatusBadge(admin.status, admin.password_status);
                const isLoading = actionLoading === admin.portal_user_id;
                const isDisabled = admin.status === 'DISABLED';
                const isPending = admin.status === 'INVITED' || admin.password_status === 'NOT_SET';

                return (
                  <tr 
                    key={admin.portal_user_id} 
                    className={`hover:bg-gray-50 transition-colors ${isDisabled ? 'opacity-60' : ''}`}
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
                          <p className="font-medium text-midnight-blue">
                            {admin.full_name || 'Unnamed Admin'}
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
                            ) : (
                              <button
                                onClick={() => handleDeactivate(admin.portal_user_id, admin.auth_email)}
                                className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                title="Deactivate Admin"
                                data-testid={`deactivate-admin-${admin.portal_user_id}`}
                              >
                                <UserMinus className="w-4 h-4" />
                              </button>
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
    </div>
  );
};

// Rules Management Component
const RulesManagement = () => {
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
    try {
      const response = await api.post('/admin/rules/seed');
      toast.success(`${response.data.created} rules created, ${response.data.skipped} skipped`);
      fetchRules();
    } catch (error) {
      toast.error('Failed to seed rules');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingRule) {
        await api.put(`/admin/rules/${editingRule.rule_id}`, formData);
        toast.success('Rule updated successfully');
      } else {
        await api.post('/admin/rules', formData);
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
    if (!window.confirm('Are you sure you want to deactivate this rule?')) return;
    try {
      await api.delete(`/admin/rules/${ruleId}`);
      toast.success('Rule deactivated');
      fetchRules();
    } catch (error) {
      toast.error('Failed to delete rule');
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
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-midnight-blue">Requirement Rules ({rules.length})</h2>
        <div className="flex gap-3">
          <button
            onClick={seedDefaultRules}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Seed Default Rules
          </button>
          <button
            onClick={() => { resetForm(); setEditingRule(null); setShowCreateForm(true); }}
            className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 transition-colors"
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
              {rules.map((rule) => (
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
                    <div className="flex items-center gap-2">
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
                        onClick={() => handleEdit(rule)}
                        className="text-electric-teal hover:text-teal-700"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      {rule.is_active && (
                        <button
                          onClick={() => handleDelete(rule.rule_id)}
                          className="text-red-500 hover:text-red-700"
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
          <p className="text-gray-600 mb-4">No rules configured yet</p>
          <button
            onClick={seedDefaultRules}
            className="px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600"
          >
            Load UK Default Rules
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
        {templates.map((template) => (
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
            
            {template.available_variables?.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {template.available_variables.map((v, i) => (
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
const StatisticsDashboard = () => {
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
            Last updated: {new Date(stats.generated_at).toLocaleString()}
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
        <div className="bg-white rounded-xl border border-gray-200 p-5" data-testid="stat-card-total-properties">
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
        <div className="bg-white rounded-xl border-2 border-green-200 p-5" data-testid="stat-card-compliant">
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
        <div className="bg-white rounded-xl border-2 border-amber-200 p-5" data-testid="stat-card-attention">
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
        <div className="bg-white rounded-xl border-2 border-red-200 p-5" data-testid="stat-card-action-required">
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
        <div className="bg-white rounded-xl border border-gray-200 p-5" data-testid="stat-card-expiring">
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
              <div className="flex items-center justify-between p-3 bg-red-50 rounded-lg border border-red-100">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                  <span className="text-sm font-medium text-red-800">Overdue Requirements</span>
                </div>
                <span className="text-lg font-bold text-red-600">{overdueCount}</span>
              </div>
            )}
            
            {expiring30Days > 0 && (
              <div className="flex items-center justify-between p-3 bg-amber-50 rounded-lg border border-amber-100">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-amber-500 rounded-full"></div>
                  <span className="text-sm font-medium text-amber-800">Due in 30 days</span>
                </div>
                <span className="text-lg font-bold text-amber-600">{expiring30Days}</span>
              </div>
            )}

            {stats.requirements?.expiring_next_60_days > expiring30Days && (
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100">
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
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <span className="text-sm text-gray-600">Total Clients</span>
              <span className="font-semibold text-midnight-blue">{stats.clients?.total || 0}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <span className="text-sm text-gray-600">Active Subscriptions</span>
              <span className="font-semibold text-green-600">{stats.clients?.by_subscription_status?.ACTIVE || 0}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <span className="text-sm text-gray-600">Total Requirements</span>
              <span className="font-semibold text-midnight-blue">{stats.requirements?.total || 0}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <span className="text-sm text-gray-600">Documents Uploaded</span>
              <span className="font-semibold text-midnight-blue">{stats.documents?.total || 0}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-teal-50 rounded-lg border border-teal-100">
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
                {stats.requirements?.by_status && Object.keys(stats.requirements.by_status).length > 0 ? (
                  <div className="space-y-3">
                    {Object.entries(stats.requirements.by_status)
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
const DashboardOverview = ({ onShowDrilldown }) => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pendingList, setPendingList] = useState({ documents: [], total: 0, returned: 0, has_more: false });
  const [pendingLoading, setPendingLoading] = useState(false);
  const [pendingHours, setPendingHours] = useState(24);
  const [pendingClientId, setPendingClientId] = useState('');

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await api.get('/admin/dashboard');
      setStats(response.data);
    } catch (error) {
      toast.error('Failed to load dashboard stats');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (loading || stats == null) return;
    let cancelled = false;
    const fetchPendingVerification = async () => {
      setPendingLoading(true);
      try {
        const { adminAPI } = await import('../api/client');
        const res = await adminAPI.getPendingVerificationDocuments(pendingHours, pendingClientId || null);
        if (cancelled) return;
        setPendingList({
          documents: res.data?.documents || [],
          total: res.data?.total ?? 0,
          returned: res.data?.returned ?? 0,
          has_more: res.data?.has_more ?? false,
        });
      } catch (e) {
        if (!cancelled) {
          toast.error('Failed to load pending verification list');
          setPendingList({ documents: [], total: 0, returned: 0, has_more: false });
        }
      } finally {
        if (!cancelled) setPendingLoading(false);
      }
    };
    fetchPendingVerification();
    return () => { cancelled = true; };
  }, [loading, stats, pendingHours, pendingClientId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  const unverifiedCount = stats?.stats?.unverified_documents_count ?? 0;

  const statCards = [
    { label: 'Total Clients', value: stats?.stats?.total_clients || 0, icon: Users, color: 'text-blue-600 bg-blue-100', drilldown: 'clients' },
    { label: 'Total Properties', value: stats?.stats?.total_properties || 0, icon: Building2, color: 'text-purple-600 bg-purple-100', drilldown: 'properties' },
    { label: 'Active Clients', value: stats?.stats?.active_clients || 0, icon: CheckCircle, color: 'text-green-600 bg-green-100', drilldown: 'clients-active' },
    { label: 'Pending Setup', value: stats?.stats?.pending_clients || 0, icon: Clock, color: 'text-amber-600 bg-amber-100', drilldown: 'clients-pending' },
    { label: 'Unverified Documents', value: unverifiedCount, icon: FileCheck, color: 'text-teal-600 bg-teal-100', drilldown: null, badge: true },
  ];

  const complianceCards = [
    { status: 'GREEN', label: 'Compliant', value: stats?.compliance_overview?.GREEN || 0, bgClass: 'bg-green-50 hover:bg-green-100', textClass: 'text-green-600', labelClass: 'text-green-700' },
    { status: 'AMBER', label: 'Attention Needed', value: stats?.compliance_overview?.AMBER || 0, bgClass: 'bg-amber-50 hover:bg-amber-100', textClass: 'text-amber-600', labelClass: 'text-amber-700' },
    { status: 'RED', label: 'Non-Compliant', value: stats?.compliance_overview?.RED || 0, bgClass: 'bg-red-50 hover:bg-red-100', textClass: 'text-red-600', labelClass: 'text-red-700' },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-midnight-blue">Dashboard Overview</h2>
      
      {/* Stats Grid - Clickable tiles */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
        {statCards.map((stat, idx) => {
          const Wrapper = stat.drilldown ? 'button' : 'div';
          return (
            <Wrapper
              key={idx}
              onClick={stat.drilldown ? () => onShowDrilldown && onShowDrilldown(stat.drilldown) : undefined}
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
      <div className="bg-white rounded-xl border border-gray-200 p-6" data-testid="pending-verification-section">
        <h3 className="text-lg font-semibold text-midnight-blue mb-4">Pending verification</h3>
        <p className="text-sm text-gray-500 mb-4">Documents with status UPLOADED older than selected hours (filterable by client).</p>
        <div className="flex flex-wrap items-center gap-4 mb-4">
          <label className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Older than (hours)</span>
            <select
              value={pendingHours}
              onChange={(e) => setPendingHours(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
              data-testid="pending-verification-hours"
            >
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
                  <th className="py-2 pr-4">Client ID</th>
                  <th className="py-2 pr-4">Property ID</th>
                  <th className="py-2 pr-4">Requirement ID</th>
                  <th className="py-2">Uploaded at</th>
                </tr>
              </thead>
              <tbody>
                {pendingList.documents.length === 0 ? (
                  <tr><td colSpan={5} className="py-4 text-gray-500 text-center">No documents matching filters.</td></tr>
                ) : (
                  pendingList.documents.map((doc) => (
                    <tr key={doc.document_id || doc.client_id + doc.uploaded_at} className="border-b border-gray-100">
                      <td className="py-2 pr-4 font-mono text-xs">{doc.document_id}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{doc.client_id}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{doc.property_id || '—'}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{doc.requirement_id || '—'}</td>
                      <td className="py-2 text-gray-600">{doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleString() : '—'}</td>
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

      {/* Recent Activity */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-midnight-blue mb-4">Recent Activity</h3>
        <div className="space-y-3">
          {stats?.recent_activity?.slice(0, 5).map((activity, idx) => (
            <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Activity className="w-5 h-5 text-electric-teal" />
              <div className="flex-1">
                <p className="text-sm font-medium text-midnight-blue">{activity.action}</p>
                <p className="text-xs text-gray-500">{new Date(activity.timestamp).toLocaleString()}</p>
              </div>
            </div>
          )) || (
            <p className="text-gray-500 text-sm">No recent activity</p>
          )}
        </div>
      </div>
    </div>
  );
};

// Main Admin Dashboard Component
const AdminDashboard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  
  // Support URL query param for tab (used by UnifiedAdminLayout sidebar links)
  const tabFromUrl = searchParams.get('tab');
  const [activeTab, setActiveTab] = useState(() => tabFromUrl || 'overview');
  const [selectedClientId, setSelectedClientId] = useState(null);
  const [drilldownType, setDrilldownType] = useState(null);

  // Update activeTab when URL changes (e.g., user clicks sidebar link)
  const effectiveTab = tabFromUrl || activeTab;

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

  const tabs = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'statistics', label: 'Statistics', icon: BarChart3 },
    { id: 'jobs', label: 'Jobs', icon: Clock },
    { id: 'clients', label: 'Clients', icon: Users },
    { id: 'admins', label: 'Admins', icon: UserCog },
    { id: 'rules', label: 'Rules', icon: BookOpen },
    { id: 'templates', label: 'Templates', icon: Mail },
    { id: 'emailDelivery', label: 'Email delivery', icon: Mail },
    { id: 'audit', label: 'Audit Logs', icon: FileText },
    { id: 'messages', label: 'Messages', icon: Activity },
  ];

  const renderContent = () => {
    switch (effectiveTab) {
      case 'overview': return <DashboardOverview onShowDrilldown={handleShowDrilldown} />;
      case 'statistics': return <StatisticsDashboard />;
      case 'jobs': return <JobsMonitoring />;
      case 'clients': return <ClientsManagement />;
      case 'admins': return <AdminsManagement />;
      case 'rules': return <RulesManagement />;
      case 'templates': return <EmailTemplates />;
      case 'emailDelivery': return <EmailDelivery />;
      case 'audit': return <AuditLogs />;
      case 'messages': return <MessageLogs />;
      default: return <DashboardOverview onShowDrilldown={handleShowDrilldown} />;
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
              onClick={() => setActiveTab(tab.id)}
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
