import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { 
  Search, 
  RefreshCw, 
  ExternalLink, 
  Mail, 
  MessageSquare,
  Key,
  Play,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  CreditCard,
  Building2,
  User,
  Calendar,
  Copy,
  Send,
  Loader2,
  ChevronRight,
  ArrowLeft,
  FileText,
  Phone,
  Info,
  AlertCircle
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { toast } from 'sonner';
import api from '../api/client';

const AdminBillingPage = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Search state
  const [searchQuery, setSearchQuery] = useState(searchParams.get('q') || '');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  
  // Selected client state
  const [selectedClientId, setSelectedClientId] = useState(searchParams.get('client') || null);
  const [billingSnapshot, setBillingSnapshot] = useState(null);
  const [loadingSnapshot, setLoadingSnapshot] = useState(false);
  
  // Action states
  const [syncing, setSyncing] = useState(false);
  const [creatingPortal, setCreatingPortal] = useState(false);
  const [resendingSetup, setResendingSetup] = useState(false);
  const [provisioning, setProvisioning] = useState(false);
  const [portalLink, setPortalLink] = useState(null);
  
  // Message modal
  const [showMessageModal, setShowMessageModal] = useState(false);
  const [messageChannels, setMessageChannels] = useState(['email']);
  const [messageTemplate, setMessageTemplate] = useState('');
  const [customMessage, setCustomMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  
  // Statistics
  const [statistics, setStatistics] = useState(null);

  // Fetch statistics on mount
  useEffect(() => {
    fetchStatistics();
  }, []);

  // Fetch client details when selected
  useEffect(() => {
    if (selectedClientId) {
      fetchBillingSnapshot(selectedClientId);
      setSearchParams({ client: selectedClientId });
    }
  }, [selectedClientId, setSearchParams]);

  const fetchStatistics = async () => {
    try {
      const response = await api.get('/admin/billing/statistics');
      setStatistics(response.data);
    } catch (error) {
      console.error('Failed to fetch statistics:', error);
    }
  };

  const handleSearch = async (query) => {
    if (!query || query.length < 2) {
      setSearchResults([]);
      return;
    }
    
    setSearching(true);
    try {
      const response = await api.get(`/admin/billing/clients/search?q=${encodeURIComponent(query)}`);
      setSearchResults(response.data.clients || []);
    } catch (error) {
      console.error('Search error:', error);
      toast.error('Search failed');
    } finally {
      setSearching(false);
    }
  };

  const fetchBillingSnapshot = async (clientId) => {
    setLoadingSnapshot(true);
    try {
      const response = await api.get(`/admin/billing/clients/${clientId}`);
      setBillingSnapshot(response.data);
    } catch (error) {
      console.error('Fetch snapshot error:', error);
      toast.error('Failed to load billing details');
    } finally {
      setLoadingSnapshot(false);
    }
  };

  const handleSync = async () => {
    if (!selectedClientId) return;
    
    setSyncing(true);
    try {
      const response = await api.post(`/admin/billing/clients/${selectedClientId}/sync`);
      
      if (response.data.success) {
        toast.success('Billing synced', {
          description: response.data.changes_detected 
            ? 'Changes detected and applied' 
            : 'Already up to date',
        });
        
        if (response.data.provisioning_triggered) {
          toast.info('Provisioning triggered', {
            description: 'Client provisioning has been started',
          });
        }
        
        // Refresh snapshot
        await fetchBillingSnapshot(selectedClientId);
      } else {
        toast.warning(response.data.message);
      }
    } catch (error) {
      console.error('Sync error:', error);
      toast.error(error.response?.data?.detail || 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const handleCreatePortalLink = async () => {
    if (!selectedClientId) return;
    
    setCreatingPortal(true);
    try {
      const response = await api.post(`/admin/billing/clients/${selectedClientId}/portal-link`);
      
      if (response.data.success) {
        setPortalLink(response.data.portal_url);
        toast.success('Portal link created');
      }
    } catch (error) {
      console.error('Portal link error:', error);
      toast.error(error.response?.data?.detail || 'Failed to create portal link');
    } finally {
      setCreatingPortal(false);
    }
  };

  const handleResendSetup = async () => {
    if (!selectedClientId) return;
    
    setResendingSetup(true);
    try {
      const response = await api.post(`/admin/billing/clients/${selectedClientId}/resend-setup`);
      
      if (response.data.success) {
        toast.success('Setup email sent', {
          description: `Sent to ${response.data.email}`,
        });
      }
    } catch (error) {
      console.error('Resend setup error:', error);
      toast.error(error.response?.data?.detail || 'Failed to send setup email');
    } finally {
      setResendingSetup(false);
    }
  };

  const handleForceProvision = async () => {
    if (!selectedClientId) return;
    
    setProvisioning(true);
    try {
      const response = await api.post(`/admin/billing/clients/${selectedClientId}/force-provision`);
      
      if (response.data.success) {
        toast.success('Provisioning complete', {
          description: response.data.message,
        });
        await fetchBillingSnapshot(selectedClientId);
      } else {
        toast.error(response.data.message);
      }
    } catch (error) {
      console.error('Provision error:', error);
      toast.error(error.response?.data?.detail || 'Provisioning failed');
    } finally {
      setProvisioning(false);
    }
  };

  const handleSendMessage = async () => {
    if (!selectedClientId || messageChannels.length === 0) return;
    
    setSendingMessage(true);
    try {
      const response = await api.post(`/admin/billing/clients/${selectedClientId}/message`, {
        channels: messageChannels,
        template_id: messageTemplate || null,
        custom_text: customMessage || null,
      });
      
      if (response.data.success) {
        const results = response.data.results;
        let successCount = 0;
        if (results.in_app?.sent) successCount++;
        if (results.email?.sent) successCount++;
        if (results.sms?.sent) successCount++;
        
        toast.success(`Message sent via ${successCount} channel(s)`);
        setShowMessageModal(false);
        setCustomMessage('');
        setMessageTemplate('');
      }
    } catch (error) {
      console.error('Send message error:', error);
      toast.error(error.response?.data?.detail || 'Failed to send message');
    } finally {
      setSendingMessage(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  const getEntitlementBadge = (status) => {
    switch (status) {
      case 'ENABLED':
        return <span className="px-2 py-1 text-xs font-medium bg-green-100 text-green-700 rounded-full">ENABLED</span>;
      case 'LIMITED':
        return <span className="px-2 py-1 text-xs font-medium bg-amber-100 text-amber-700 rounded-full">LIMITED</span>;
      case 'DISABLED':
        return <span className="px-2 py-1 text-xs font-medium bg-red-100 text-red-700 rounded-full">DISABLED</span>;
      default:
        return <span className="px-2 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded-full">{status}</span>;
    }
  };

  const getSubscriptionBadge = (status) => {
    const statusColors = {
      ACTIVE: 'bg-green-100 text-green-700',
      TRIALING: 'bg-blue-100 text-blue-700',
      PAST_DUE: 'bg-amber-100 text-amber-700',
      CANCELED: 'bg-red-100 text-red-700',
      UNPAID: 'bg-red-100 text-red-700',
      NONE: 'bg-gray-100 text-gray-700',
    };
    
    return (
      <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[status] || 'bg-gray-100 text-gray-700'}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="admin-billing-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate('/admin')}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              data-testid="back-btn"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div>
              <h1 className="text-xl font-semibold text-midnight-blue flex items-center gap-2">
                <CreditCard className="w-6 h-6 text-electric-teal" />
                Billing & Subscriptions
              </h1>
              <p className="text-sm text-gray-500">Manage client billing, subscriptions, and entitlements</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Search & Results */}
          <div className="lg:col-span-1 space-y-4">
            {/* Search */}
            <Card data-testid="search-panel">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Find Client</CardTitle>
                <CardDescription>Search by email, CRN, ID, or postcode</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    type="text"
                    placeholder="Enter search term..."
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      handleSearch(e.target.value);
                    }}
                    className="pl-10"
                    data-testid="search-input"
                  />
                </div>
                
                {/* Search Results */}
                {searchResults.length > 0 && (
                  <div className="mt-4 space-y-2 max-h-96 overflow-y-auto" data-testid="search-results">
                    {searchResults.map((client) => (
                      <button
                        key={client.client_id}
                        onClick={() => setSelectedClientId(client.client_id)}
                        className={`w-full text-left p-3 rounded-lg border transition-colors ${
                          selectedClientId === client.client_id
                            ? 'border-electric-teal bg-teal-50'
                            : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                        }`}
                        data-testid={`client-result-${client.client_id}`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium text-gray-900 text-sm">{client.contact_name || client.company_name || 'Unknown'}</p>
                            <p className="text-xs text-gray-500">{client.contact_email}</p>
                            {client.crn && <p className="text-xs text-gray-400">CRN: {client.crn}</p>}
                          </div>
                          {getEntitlementBadge(client.entitlement_status)}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
                
                {searching && (
                  <div className="mt-4 text-center text-gray-500 text-sm">
                    <Loader2 className="w-4 h-4 animate-spin inline mr-2" />
                    Searching...
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Quick Stats */}
            {statistics && (
              <Card data-testid="statistics-panel">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Subscription Stats</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Enabled</span>
                    <span className="font-semibold text-green-600">{statistics.entitlement_counts?.enabled || 0}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Limited</span>
                    <span className="font-semibold text-amber-600">{statistics.entitlement_counts?.limited || 0}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Disabled</span>
                    <span className="font-semibold text-red-600">{statistics.entitlement_counts?.disabled || 0}</span>
                  </div>
                  <hr />
                  <div className="text-xs text-gray-500 space-y-1">
                    <p>Solo: {statistics.plan_counts?.PLAN_1_SOLO || 0}</p>
                    <p>Portfolio: {statistics.plan_counts?.PLAN_2_PORTFOLIO || 0}</p>
                    <p>Professional: {statistics.plan_counts?.PLAN_3_PRO || 0}</p>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Clients Needing Attention */}
            {statistics?.clients_needing_attention?.length > 0 && (
              <Card data-testid="attention-panel">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    Needs Attention
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {statistics.clients_needing_attention.slice(0, 5).map((client) => (
                    <button
                      key={client.client_id}
                      onClick={() => setSelectedClientId(client.client_id)}
                      className="w-full text-left p-2 rounded border border-amber-200 bg-amber-50 hover:bg-amber-100 transition-colors"
                    >
                      <p className="text-sm font-medium text-gray-900">{client.contact_email}</p>
                      <p className="text-xs text-amber-700">
                        {client.entitlement_status === 'LIMITED' ? 'Payment issue' : 'Setup incomplete'}
                      </p>
                    </button>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right Column - Client Details */}
          <div className="lg:col-span-2">
            {loadingSnapshot ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <Loader2 className="w-8 h-8 animate-spin text-electric-teal mx-auto mb-3" />
                  <p className="text-gray-500">Loading billing details...</p>
                </CardContent>
              </Card>
            ) : billingSnapshot ? (
              <div className="space-y-4">
                {/* Client Identity */}
                <Card data-testid="client-identity">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base flex items-center gap-2">
                        <User className="w-4 h-4" />
                        Client Details
                      </CardTitle>
                      {getEntitlementBadge(billingSnapshot.entitlement_status)}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-gray-500">Name</p>
                        <p className="font-medium">{billingSnapshot.contact_name || 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Email</p>
                        <p className="font-medium">{billingSnapshot.contact_email}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Company</p>
                        <p className="font-medium">{billingSnapshot.company_name || 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">CRN</p>
                        <p className="font-medium font-mono text-xs">{billingSnapshot.crn || 'N/A'}</p>
                      </div>
                      <div className="col-span-2">
                        <p className="text-gray-500">Client ID</p>
                        <p className="font-mono text-xs text-gray-600">{billingSnapshot.client_id}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Plan & Subscription */}
                <Card data-testid="subscription-info">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <CreditCard className="w-4 h-4" />
                      Subscription & Plan
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-gray-500">Plan</p>
                        <p className="font-medium">{billingSnapshot.plan_name} ({billingSnapshot.plan_code})</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Property Limit</p>
                        <p className="font-medium">
                          {billingSnapshot.current_property_count} / {billingSnapshot.max_properties}
                          {billingSnapshot.over_property_limit && (
                            <span className="ml-2 text-red-500">(Over limit!)</span>
                          )}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500">Subscription Status</p>
                        <div className="mt-1">{getSubscriptionBadge(billingSnapshot.subscription_status)}</div>
                      </div>
                      <div>
                        <p className="text-gray-500">Onboarding</p>
                        <p className="font-medium">{billingSnapshot.onboarding_status}</p>
                      </div>
                      {billingSnapshot.current_period_end && (
                        <div className="col-span-2">
                          <p className="text-gray-500">Current Period</p>
                          <p className="font-medium">
                            {new Date(billingSnapshot.current_period_start).toLocaleDateString()} - {new Date(billingSnapshot.current_period_end).toLocaleDateString()}
                            {billingSnapshot.cancel_at_period_end && (
                              <span className="ml-2 text-amber-600">(Cancels at end)</span>
                            )}
                          </p>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* Stripe Details */}
                <Card data-testid="stripe-info">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <FileText className="w-4 h-4" />
                      Stripe Details
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500">Customer ID</span>
                        {billingSnapshot.stripe_customer_id ? (
                          <code className="text-xs bg-gray-100 px-2 py-1 rounded">{billingSnapshot.stripe_customer_id}</code>
                        ) : (
                          <span className="text-gray-400">Not set</span>
                        )}
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500">Subscription ID</span>
                        {billingSnapshot.stripe_subscription_id ? (
                          <code className="text-xs bg-gray-100 px-2 py-1 rounded">{billingSnapshot.stripe_subscription_id}</code>
                        ) : (
                          <span className="text-gray-400">Not set</span>
                        )}
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500">Onboarding Fee Paid</span>
                        {billingSnapshot.onboarding_fee_paid ? (
                          <CheckCircle className="w-4 h-4 text-green-500" />
                        ) : (
                          <XCircle className="w-4 h-4 text-gray-400" />
                        )}
                      </div>
                      {billingSnapshot.payment_failed_at && (
                        <Alert className="border-red-200 bg-red-50">
                          <AlertCircle className="w-4 h-4 text-red-600" />
                          <AlertDescription className="text-red-800">
                            Payment failed on {new Date(billingSnapshot.payment_failed_at).toLocaleDateString()}
                          </AlertDescription>
                        </Alert>
                      )}
                      {billingSnapshot.last_synced_at && (
                        <p className="text-xs text-gray-400 mt-2">
                          Last synced: {new Date(billingSnapshot.last_synced_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* Admin Actions */}
                <Card data-testid="admin-actions">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">Admin Actions</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {/* Sync Button */}
                    <Button
                      onClick={handleSync}
                      disabled={syncing}
                      variant="outline"
                      className="w-full justify-start"
                      data-testid="sync-btn"
                    >
                      {syncing ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <RefreshCw className="w-4 h-4 mr-2" />
                      )}
                      Sync Billing Now
                    </Button>

                    {/* Portal Link */}
                    <Button
                      onClick={handleCreatePortalLink}
                      disabled={creatingPortal || !billingSnapshot.stripe_customer_id}
                      variant="outline"
                      className="w-full justify-start"
                      data-testid="portal-link-btn"
                    >
                      {creatingPortal ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <ExternalLink className="w-4 h-4 mr-2" />
                      )}
                      Create Manage Billing Link
                    </Button>

                    {portalLink && (
                      <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                        <p className="text-xs text-green-700 mb-2">Billing Portal Link:</p>
                        <div className="flex gap-2">
                          <Input value={portalLink} readOnly className="text-xs font-mono" />
                          <Button size="sm" variant="outline" onClick={() => copyToClipboard(portalLink)}>
                            <Copy className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Resend Setup */}
                    <Button
                      onClick={handleResendSetup}
                      disabled={resendingSetup || !billingSnapshot.portal_user}
                      variant="outline"
                      className="w-full justify-start"
                      data-testid="resend-setup-btn"
                    >
                      {resendingSetup ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <Key className="w-4 h-4 mr-2" />
                      )}
                      Resend Password Setup Link
                      {billingSnapshot.password_setup_complete && (
                        <span className="ml-auto text-xs text-green-600">(Already set)</span>
                      )}
                    </Button>

                    {/* Force Provision */}
                    <Button
                      onClick={handleForceProvision}
                      disabled={provisioning || billingSnapshot.entitlement_status !== 'ENABLED'}
                      variant="outline"
                      className="w-full justify-start"
                      data-testid="provision-btn"
                    >
                      {provisioning ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <Play className="w-4 h-4 mr-2" />
                      )}
                      Re-run Provisioning
                      {billingSnapshot.entitlement_status !== 'ENABLED' && (
                        <span className="ml-auto text-xs text-gray-400">(Requires ENABLED)</span>
                      )}
                    </Button>

                    {/* Send Message */}
                    <Button
                      onClick={() => setShowMessageModal(true)}
                      variant="outline"
                      className="w-full justify-start"
                      data-testid="message-btn"
                    >
                      <MessageSquare className="w-4 h-4 mr-2" />
                      Send Message
                    </Button>
                  </CardContent>
                </Card>

                {/* Recent Stripe Events */}
                {billingSnapshot.recent_stripe_events?.length > 0 && (
                  <Card data-testid="stripe-events">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">Recent Stripe Events</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {billingSnapshot.recent_stripe_events.map((event, idx) => (
                          <div key={idx} className="flex items-center justify-between p-2 bg-gray-50 rounded text-sm">
                            <div>
                              <p className="font-medium">{event.type}</p>
                              <p className="text-xs text-gray-500">{new Date(event.created).toLocaleString()}</p>
                            </div>
                            <span className={`px-2 py-1 text-xs rounded ${
                              event.status === 'PROCESSED' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                            }`}>
                              {event.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            ) : (
              <Card>
                <CardContent className="py-12 text-center">
                  <Search className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500">Search for a client to view billing details</p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>

      {/* Message Modal */}
      {showMessageModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 max-w-lg w-full mx-4 shadow-xl" data-testid="message-modal">
            <h3 className="text-lg font-semibold mb-4">Send Message to Client</h3>
            
            {/* Channels */}
            <div className="mb-4">
              <label className="text-sm font-medium text-gray-700 mb-2 block">Channels</label>
              <div className="flex gap-2">
                {['in_app', 'email', 'sms'].map((channel) => (
                  <button
                    key={channel}
                    onClick={() => {
                      if (messageChannels.includes(channel)) {
                        setMessageChannels(messageChannels.filter(c => c !== channel));
                      } else {
                        setMessageChannels([...messageChannels, channel]);
                      }
                    }}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      messageChannels.includes(channel)
                        ? 'bg-electric-teal text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {channel === 'in_app' ? 'In-App' : channel.charAt(0).toUpperCase() + channel.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Template */}
            <div className="mb-4">
              <label className="text-sm font-medium text-gray-700 mb-2 block">Template (Optional)</label>
              <select
                value={messageTemplate}
                onChange={(e) => setMessageTemplate(e.target.value)}
                className="w-full p-2 border border-gray-200 rounded-lg"
              >
                <option value="">Custom Message</option>
                <option value="payment_received">Payment Received</option>
                <option value="provisioning_complete">Provisioning Complete</option>
                <option value="payment_failed">Payment Failed</option>
                <option value="subscription_canceled">Subscription Cancelled</option>
              </select>
            </div>
            
            {/* Custom Message */}
            {!messageTemplate && (
              <div className="mb-4">
                <label className="text-sm font-medium text-gray-700 mb-2 block">Message</label>
                <textarea
                  value={customMessage}
                  onChange={(e) => setCustomMessage(e.target.value)}
                  rows={4}
                  className="w-full p-3 border border-gray-200 rounded-lg resize-none"
                  placeholder="Enter your message..."
                />
              </div>
            )}
            
            {/* Actions */}
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowMessageModal(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleSendMessage}
                disabled={sendingMessage || messageChannels.length === 0}
                className="bg-electric-teal hover:bg-teal-600"
              >
                {sendingMessage ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Send className="w-4 h-4 mr-2" />
                )}
                Send Message
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminBillingPage;
