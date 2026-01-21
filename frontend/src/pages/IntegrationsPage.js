import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Webhook,
  Plus,
  ArrowLeft,
  Save,
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Eye,
  EyeOff,
  Trash2,
  ToggleLeft,
  ToggleRight,
  RefreshCw,
  Send,
  Copy,
  ExternalLink,
  Info,
  Clock,
  Activity,
  Shield,
  Lock
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Switch } from '../components/ui/switch';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { toast } from 'sonner';
import api from '../api/client';
import UpgradePrompt from '../components/UpgradePrompt';

const IntegrationsPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [webhooks, setWebhooks] = useState([]);
  const [availableEvents, setAvailableEvents] = useState([]);
  const [rateLimitInfo, setRateLimitInfo] = useState(null);
  const [stats, setStats] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [testingWebhookId, setTestingWebhookId] = useState(null);
  const [deletingWebhookId, setDeletingWebhookId] = useState(null);
  const [showSecretId, setShowSecretId] = useState(null);
  const [newSecret, setNewSecret] = useState(null);
  const [entitlements, setEntitlements] = useState(null);

  // Check if webhooks feature is available
  const hasWebhooksAccess = entitlements?.features?.webhooks?.enabled;

  useEffect(() => {
    fetchData();
    fetchEntitlements();
  }, []);

  const fetchEntitlements = async () => {
    try {
      const response = await api.get('/client/entitlements');
      setEntitlements(response.data);
    } catch (error) {
      console.error('Failed to fetch entitlements:', error);
    }
  };

  const fetchData = async () => {
    try {
      const [webhooksRes, eventsRes, statsRes] = await Promise.all([
        api.get('/webhooks'),
        api.get('/webhooks/events'),
        api.get('/webhooks/stats')
      ]);
      
      setWebhooks(webhooksRes.data.webhooks || []);
      setRateLimitInfo(webhooksRes.data.rate_limit);
      setAvailableEvents(eventsRes.data.events || []);
      setStats(statsRes.data);
    } catch (error) {
      toast.error('Failed to load integrations');
    } finally {
      setLoading(false);
    }
  };

  const testWebhook = async (webhookId) => {
    setTestingWebhookId(webhookId);
    try {
      const response = await api.post(`/webhooks/${webhookId}/test`);
      if (response.data.success) {
        toast.success(`Test successful! Status: ${response.data.status_code}`);
      } else {
        toast.error(`Test failed: ${response.data.error || 'Unknown error'}`);
      }
      fetchData(); // Refresh to get updated status
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to test webhook');
    } finally {
      setTestingWebhookId(null);
    }
  };

  const toggleWebhook = async (webhookId, currentStatus) => {
    try {
      const endpoint = currentStatus ? 'disable' : 'enable';
      await api.post(`/webhooks/${webhookId}/${endpoint}`);
      toast.success(`Webhook ${currentStatus ? 'disabled' : 'enabled'}`);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to toggle webhook');
    }
  };

  const deleteWebhook = async (webhookId) => {
    if (!window.confirm('Are you sure you want to delete this webhook?')) return;
    
    setDeletingWebhookId(webhookId);
    try {
      await api.delete(`/webhooks/${webhookId}`);
      toast.success('Webhook deleted');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete webhook');
    } finally {
      setDeletingWebhookId(null);
    }
  };

  const regenerateSecret = async (webhookId) => {
    if (!window.confirm('Regenerating the secret will invalidate the current one. Continue?')) return;
    
    try {
      const response = await api.post(`/webhooks/${webhookId}/regenerate-secret`);
      setNewSecret({ id: webhookId, secret: response.data.secret });
      toast.success('Secret regenerated. Copy it now - it won\'t be shown again!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to regenerate secret');
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  const getStatusBadge = (webhook) => {
    if (!webhook.is_active) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
          <ToggleLeft className="w-3 h-3" />
          Disabled
        </span>
      );
    }
    
    if (webhook.failure_count >= 3) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
          <AlertTriangle className="w-3 h-3" />
          Degraded
        </span>
      );
    }
    
    if (webhook.last_status && webhook.last_status >= 200 && webhook.last_status < 300) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
          <CheckCircle className="w-3 h-3" />
          Healthy
        </span>
      );
    }
    
    if (webhook.last_status) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
          <XCircle className="w-3 h-3" />
          Error ({webhook.last_status})
        </span>
      );
    }
    
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
        <Clock className="w-3 h-3" />
        Never triggered
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-electric-teal mx-auto mb-3" />
          <p className="text-gray-600">Loading integrations...</p>
        </div>
      </div>
    );
  }

  // Show upgrade prompt if webhooks not available
  if (entitlements && !hasWebhooksAccess) {
    return (
      <div className="min-h-screen bg-gray-50" data-testid="integrations-page">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
          <div className="max-w-6xl mx-auto px-4 py-4">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => navigate('/app/dashboard')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                data-testid="back-btn"
              >
                <ArrowLeft className="w-5 h-5 text-gray-600" />
              </button>
              <div>
                <h1 className="text-xl font-semibold text-midnight-blue flex items-center gap-2">
                  <Webhook className="w-6 h-6 text-electric-teal" />
                  Integrations
                </h1>
                <p className="text-sm text-gray-500">Manage webhooks and external integrations</p>
              </div>
            </div>
          </div>
        </header>

        <main className="max-w-2xl mx-auto px-4 py-12">
          <UpgradePrompt
            featureName="Webhooks & Integrations"
            featureDescription="Connect Compliance Vault Pro to your existing systems. Receive real-time notifications when compliance events occur, automate workflows, and integrate with property management software."
            requiredPlan="PLAN_3_PRO"
            requiredPlanName="Professional"
            currentPlan={entitlements?.plan_name}
            variant="card"
          />
          
          {/* Feature Preview */}
          <div className="mt-8 bg-white rounded-xl border border-gray-200 p-6" data-testid="webhooks-preview">
            <h3 className="font-semibold text-midnight-blue mb-4 flex items-center gap-2">
              <Lock className="w-4 h-4 text-gray-400" />
              What you'll unlock with Professional
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                <Webhook className="w-5 h-5 text-electric-teal mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900">Custom Webhooks</p>
                  <p className="text-sm text-gray-500">Send events to your own endpoints</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                <Activity className="w-5 h-5 text-electric-teal mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900">Real-time Events</p>
                  <p className="text-sm text-gray-500">Instant notifications for compliance changes</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                <Shield className="w-5 h-5 text-electric-teal mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900">Signed Payloads</p>
                  <p className="text-sm text-gray-500">HMAC-SHA256 signature verification</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                <RefreshCw className="w-5 h-5 text-electric-teal mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900">Automatic Retries</p>
                  <p className="text-sm text-gray-500">Reliable delivery with exponential backoff</p>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="integrations-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => navigate('/app/dashboard')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                data-testid="back-btn"
              >
                <ArrowLeft className="w-5 h-5 text-gray-600" />
              </button>
              <div>
                <h1 className="text-xl font-semibold text-midnight-blue flex items-center gap-2">
                  <Webhook className="w-6 h-6 text-electric-teal" />
                  Integrations
                </h1>
                <p className="text-sm text-gray-500">Manage webhooks and external integrations</p>
              </div>
            </div>
            <Button
              onClick={() => setShowCreateModal(true)}
              className="bg-electric-teal hover:bg-teal-600"
              data-testid="create-webhook-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              Create Webhook
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Stats Overview */}
        {stats && (
          <div className="grid grid-cols-4 gap-4 mb-8" data-testid="webhook-stats">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500">Total Webhooks</p>
                    <p className="text-2xl font-bold text-midnight-blue">{stats.total_webhooks}</p>
                  </div>
                  <Webhook className="w-8 h-8 text-gray-400" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500">Active</p>
                    <p className="text-2xl font-bold text-green-600">{stats.active_webhooks}</p>
                  </div>
                  <Activity className="w-8 h-8 text-green-400" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500">Total Deliveries</p>
                    <p className="text-2xl font-bold text-midnight-blue">{stats.total_deliveries}</p>
                  </div>
                  <Send className="w-8 h-8 text-gray-400" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500">Success Rate</p>
                    <p className="text-2xl font-bold text-electric-teal">
                      {stats.success_rate?.toFixed(1) || 0}%
                    </p>
                  </div>
                  <CheckCircle className="w-8 h-8 text-electric-teal" />
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Rate Limit & Retry Policy Info */}
        {rateLimitInfo && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-8" data-testid="rate-limit-info">
            <div className="flex items-start gap-3">
              <Info className="w-5 h-5 text-blue-600 mt-0.5" />
              <div className="text-sm text-blue-800">
                <p className="font-medium mb-1">Webhook Delivery Policy</p>
                <ul className="space-y-1 text-blue-700">
                  <li>• Rate limit: {rateLimitInfo.max_requests_per_minute} requests/minute per client</li>
                  <li>• Retries: {rateLimitInfo.max_retries} attempts with {rateLimitInfo.retry_backoff} backoff</li>
                  <li>• Timeout: {rateLimitInfo.timeout_seconds} seconds per request</li>
                  <li>• Auto-disable: After {rateLimitInfo.auto_disable_after_failures} consecutive failures</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Webhooks List */}
        <div className="space-y-4">
          {webhooks.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Webhook className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-600 mb-2">No webhooks configured</h3>
                <p className="text-sm text-gray-500 mb-4">
                  Create a webhook to receive real-time notifications when compliance events occur.
                </p>
                <Button
                  onClick={() => setShowCreateModal(true)}
                  className="bg-electric-teal hover:bg-teal-600"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Create Your First Webhook
                </Button>
              </CardContent>
            </Card>
          ) : (
            webhooks.map((webhook) => (
              <Card key={webhook.webhook_id} className="overflow-hidden" data-testid={`webhook-${webhook.webhook_id}`}>
                <CardContent className="p-0">
                  <div className="p-4 border-b border-gray-100">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="font-semibold text-midnight-blue">{webhook.name}</h3>
                          {getStatusBadge(webhook)}
                        </div>
                        <div className="flex items-center gap-2 text-sm text-gray-500">
                          <ExternalLink className="w-3 h-3" />
                          <span className="font-mono text-xs break-all">{webhook.url}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={webhook.is_active}
                          onCheckedChange={() => toggleWebhook(webhook.webhook_id, webhook.is_active)}
                          data-testid={`toggle-${webhook.webhook_id}`}
                        />
                      </div>
                    </div>
                  </div>
                  
                  {/* Event Types */}
                  <div className="px-4 py-3 bg-gray-50 border-b border-gray-100">
                    <p className="text-xs font-medium text-gray-500 mb-2">Subscribed Events</p>
                    <div className="flex flex-wrap gap-2">
                      {webhook.event_types?.map((event) => (
                        <span 
                          key={event}
                          className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-white border border-gray-200 text-gray-700"
                        >
                          {event}
                        </span>
                      ))}
                    </div>
                  </div>
                  
                  {/* Delivery Stats */}
                  <div className="px-4 py-3 grid grid-cols-4 gap-4 text-sm border-b border-gray-100">
                    <div>
                      <p className="text-gray-500">Last Status</p>
                      <p className="font-medium">
                        {webhook.last_status ? (
                          <span className={webhook.last_status >= 200 && webhook.last_status < 300 ? 'text-green-600' : 'text-red-600'}>
                            HTTP {webhook.last_status}
                          </span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-500">Last Triggered</p>
                      <p className="font-medium text-midnight-blue">
                        {webhook.last_triggered ? (
                          new Date(webhook.last_triggered).toLocaleString()
                        ) : (
                          <span className="text-gray-400">Never</span>
                        )}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-500">Success Rate</p>
                      <p className="font-medium text-midnight-blue">
                        {webhook.success_rate !== null ? `${webhook.success_rate}%` : '—'}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-500">Failures</p>
                      <p className={`font-medium ${webhook.failure_count > 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {webhook.failure_count}
                      </p>
                    </div>
                  </div>
                  
                  {/* Last Error (if any) */}
                  {webhook.last_error && (
                    <div className="px-4 py-2 bg-red-50 border-b border-red-100">
                      <p className="text-xs text-red-700">
                        <AlertTriangle className="w-3 h-3 inline mr-1" />
                        {webhook.last_error}
                      </p>
                    </div>
                  )}
                  
                  {/* New Secret Display */}
                  {newSecret?.id === webhook.webhook_id && (
                    <div className="px-4 py-3 bg-green-50 border-b border-green-100">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-xs font-medium text-green-800 mb-1">New Signing Secret (copy now!)</p>
                          <code className="text-sm font-mono text-green-700 break-all">{newSecret.secret}</code>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(newSecret.secret)}
                        >
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  )}
                  
                  {/* Actions */}
                  <div className="px-4 py-3 flex items-center justify-between bg-white">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => testWebhook(webhook.webhook_id)}
                        disabled={testingWebhookId === webhook.webhook_id}
                        data-testid={`test-${webhook.webhook_id}`}
                      >
                        {testingWebhookId === webhook.webhook_id ? (
                          <Loader2 className="w-4 h-4 animate-spin mr-1" />
                        ) : (
                          <Send className="w-4 h-4 mr-1" />
                        )}
                        Test
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => regenerateSecret(webhook.webhook_id)}
                      >
                        <RefreshCw className="w-4 h-4 mr-1" />
                        Regenerate Secret
                      </Button>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      onClick={() => deleteWebhook(webhook.webhook_id)}
                      disabled={deletingWebhookId === webhook.webhook_id}
                      data-testid={`delete-${webhook.webhook_id}`}
                    >
                      {deletingWebhookId === webhook.webhook_id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>

        {/* Available Events Reference */}
        <div className="mt-8">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Shield className="w-5 h-5 text-electric-teal" />
                Available Event Types
              </CardTitle>
              <CardDescription>
                Subscribe to these events when creating a webhook
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="divide-y divide-gray-100">
                {availableEvents.map((event) => (
                  <div key={event.type} className="py-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium text-midnight-blue">{event.name}</p>
                        <code className="text-xs text-gray-500 font-mono">{event.type}</code>
                        <p className="text-sm text-gray-600 mt-1">{event.description}</p>
                      </div>
                    </div>
                    {event.payload_fields && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {event.payload_fields.map((field) => (
                          <span 
                            key={field}
                            className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded font-mono"
                          >
                            {field}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </main>

      {/* Create Webhook Modal */}
      {showCreateModal && (
        <CreateWebhookModal
          availableEvents={availableEvents}
          onClose={() => setShowCreateModal(false)}
          onCreated={(secret) => {
            setShowCreateModal(false);
            fetchData();
            if (secret) {
              toast.success('Webhook created! Copy the signing secret.', { duration: 5000 });
            }
          }}
        />
      )}
    </div>
  );
};

// Create Webhook Modal Component
const CreateWebhookModal = ({ availableEvents, onClose, onCreated }) => {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [selectedEvents, setSelectedEvents] = useState([]);
  const [customSecret, setCustomSecret] = useState('');
  const [useCustomSecret, setUseCustomSecret] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createdSecret, setCreatedSecret] = useState(null);

  const toggleEvent = (eventType) => {
    setSelectedEvents(prev => 
      prev.includes(eventType) 
        ? prev.filter(e => e !== eventType)
        : [...prev, eventType]
    );
  };

  const handleCreate = async () => {
    if (!name.trim()) {
      toast.error('Please enter a webhook name');
      return;
    }
    if (!url.trim() || !url.startsWith('http')) {
      toast.error('Please enter a valid URL');
      return;
    }
    if (selectedEvents.length === 0) {
      toast.error('Please select at least one event type');
      return;
    }

    setCreating(true);
    try {
      const response = await api.post('/webhooks', {
        name: name.trim(),
        url: url.trim(),
        event_types: selectedEvents,
        secret: useCustomSecret && customSecret.trim() ? customSecret.trim() : null
      });
      
      setCreatedSecret(response.data.secret);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create webhook');
      setCreating(false);
    }
  };

  const copyAndClose = () => {
    if (createdSecret) {
      navigator.clipboard.writeText(createdSecret);
      toast.success('Secret copied to clipboard');
    }
    onCreated(createdSecret);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto" data-testid="create-webhook-modal">
        {!createdSecret ? (
          <>
            <div className="p-6 border-b border-gray-100">
              <h2 className="text-xl font-semibold text-midnight-blue">Create Webhook</h2>
              <p className="text-sm text-gray-500 mt-1">
                Configure a new webhook endpoint to receive compliance events
              </p>
            </div>
            
            <div className="p-6 space-y-4">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My Integration Webhook"
                  data-testid="webhook-name-input"
                />
              </div>
              
              {/* URL */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Endpoint URL</label>
                <Input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://api.example.com/webhook"
                  data-testid="webhook-url-input"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Must be a valid HTTPS URL that can receive POST requests
                </p>
              </div>
              
              {/* Custom Secret Toggle */}
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-sm text-gray-700">Use Custom Secret</p>
                  <p className="text-xs text-gray-500">Or we'll generate a secure one for you</p>
                </div>
                <Switch
                  checked={useCustomSecret}
                  onCheckedChange={setUseCustomSecret}
                />
              </div>
              
              {useCustomSecret && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Signing Secret</label>
                  <Input
                    type="password"
                    value={customSecret}
                    onChange={(e) => setCustomSecret(e.target.value)}
                    placeholder="Enter your secret..."
                    data-testid="webhook-secret-input"
                  />
                </div>
              )}
              
              {/* Event Types */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Event Types</label>
                <div className="space-y-2 max-h-60 overflow-y-auto border border-gray-200 rounded-lg p-3">
                  {availableEvents.map((event) => (
                    <label 
                      key={event.type}
                      className="flex items-start gap-3 p-2 hover:bg-gray-50 rounded cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedEvents.includes(event.type)}
                        onChange={() => toggleEvent(event.type)}
                        className="mt-1 rounded border-gray-300 text-electric-teal focus:ring-electric-teal"
                      />
                      <div>
                        <p className="text-sm font-medium text-gray-800">{event.name}</p>
                        <p className="text-xs text-gray-500">{event.description}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>
            
            <div className="p-6 border-t border-gray-100 flex justify-end gap-3">
              <Button variant="ghost" onClick={onClose}>Cancel</Button>
              <Button
                onClick={handleCreate}
                disabled={creating}
                className="bg-electric-teal hover:bg-teal-600"
                data-testid="submit-webhook-btn"
              >
                {creating ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Plus className="w-4 h-4 mr-2" />
                )}
                Create Webhook
              </Button>
            </div>
          </>
        ) : (
          <>
            <div className="p-6 border-b border-gray-100">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                  <CheckCircle className="w-6 h-6 text-green-600" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-midnight-blue">Webhook Created!</h2>
                  <p className="text-sm text-gray-500">Save your signing secret</p>
                </div>
              </div>
            </div>
            
            <div className="p-6">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                <p className="text-sm text-amber-800 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 mt-0.5" />
                  <span>
                    <strong>Important:</strong> Copy this signing secret now. It will only be shown once and cannot be retrieved later.
                  </span>
                </p>
              </div>
              
              <div className="bg-gray-50 rounded-lg p-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">Signing Secret</label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-sm font-mono bg-white p-3 rounded border border-gray-200 break-all">
                    {createdSecret}
                  </code>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      navigator.clipboard.writeText(createdSecret);
                      toast.success('Copied!');
                    }}
                  >
                    <Copy className="w-4 h-4" />
                  </Button>
                </div>
              </div>
              
              <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>How to verify webhooks:</strong><br />
                  We sign all webhook payloads using HMAC-SHA256. The signature is included in the 
                  <code className="mx-1 px-1 bg-blue-100 rounded">X-Webhook-Signature</code> header 
                  in the format <code className="mx-1 px-1 bg-blue-100 rounded">sha256={"<hex_digest>"}</code>.
                </p>
              </div>
            </div>
            
            <div className="p-6 border-t border-gray-100 flex justify-end">
              <Button
                onClick={copyAndClose}
                className="bg-electric-teal hover:bg-teal-600"
              >
                <Copy className="w-4 h-4 mr-2" />
                Copy Secret & Close
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default IntegrationsPage;
