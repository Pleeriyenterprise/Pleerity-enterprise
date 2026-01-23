/**
 * Admin Enablement Dashboard
 * Customer Enablement Automation Engine - Admin Observability & Control
 * 
 * Features:
 * - System overview with stats
 * - Enablement timeline per client
 * - Template management
 * - Suppression rules
 * - Manual event trigger (testing)
 */
import React, { useState, useEffect, useCallback } from 'react';
import client from '../api/client';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import {
  Zap,
  Mail,
  Bell,
  MessageSquare,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Shield,
  RefreshCw,
  Play,
  Pause,
  Search,
  Filter,
  Users,
  FileText,
  Settings,
  History,
  Activity,
  TrendingUp,
  BarChart3,
  Eye,
  EyeOff,
  Plus,
  Trash2,
  ChevronRight,
  Calendar,
} from 'lucide-react';

// Status colors
const STATUS_COLORS = {
  SUCCESS: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
  SUPPRESSED: 'bg-yellow-100 text-yellow-800',
  PENDING: 'bg-blue-100 text-blue-800',
};

// Category icons
const CATEGORY_ICONS = {
  ONBOARDING_GUIDANCE: Users,
  VALUE_CONFIRMATION: CheckCircle,
  COMPLIANCE_AWARENESS: AlertTriangle,
  INACTIVITY_SUPPORT: Clock,
  FEATURE_GATE_EXPLANATION: Shield,
};

// Channel icons
const CHANNEL_ICONS = {
  IN_APP: Bell,
  EMAIL: Mail,
  ASSISTANT: MessageSquare,
};

// ============================================
// Overview Dashboard Component
// ============================================

const OverviewDashboard = () => {
  const [stats, setStats] = useState(null);
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, overviewRes] = await Promise.all([
        client.get(`/admin/enablement/stats?days=${days}`),
        client.get('/admin/enablement/overview'),
      ]);
      setStats(statsRes.data);
      setOverview(overviewRes.data);
    } catch (err) {
      toast.error('Failed to load enablement data');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Period Selector */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Enablement Overview</h2>
          <p className="text-sm text-gray-500">Educational automation system stats</p>
        </div>
        <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">Last 7 days</SelectItem>
            <SelectItem value="30">Last 30 days</SelectItem>
            <SelectItem value="90">Last 90 days</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-2xl font-bold">{stats?.total_actions || 0}</p>
                <p className="text-sm text-gray-500">Total Actions</p>
              </div>
              <Activity className="w-8 h-8 text-electric-teal" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-2xl font-bold text-green-600">{stats?.success_count || 0}</p>
                <p className="text-sm text-gray-500">Delivered</p>
              </div>
              <CheckCircle className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-2xl font-bold text-yellow-600">{stats?.suppressed_count || 0}</p>
                <p className="text-sm text-gray-500">Suppressed</p>
              </div>
              <EyeOff className="w-8 h-8 text-yellow-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-2xl font-bold text-red-600">{stats?.failed_count || 0}</p>
                <p className="text-sm text-gray-500">Failed</p>
              </div>
              <XCircle className="w-8 h-8 text-red-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* System Status */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">System Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">Active Templates</span>
              <Badge variant="outline">{overview?.active_templates || 0}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Active Suppressions</span>
              <Badge variant="outline" className={overview?.active_suppressions > 0 ? 'bg-yellow-50' : ''}>
                {overview?.active_suppressions || 0}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">By Category</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(stats?.by_category || {}).map(([cat, count]) => {
                const Icon = CATEGORY_ICONS[cat] || Activity;
                return (
                  <div key={cat} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Icon className="w-4 h-4 text-gray-500" />
                      <span className="text-sm">{cat.replace(/_/g, ' ')}</span>
                    </div>
                    <span className="text-sm font-medium">{count}</span>
                  </div>
                );
              })}
              {Object.keys(stats?.by_category || {}).length === 0 && (
                <p className="text-sm text-gray-500">No actions yet</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Actions</CardTitle>
        </CardHeader>
        <CardContent>
          {overview?.recent_actions?.length > 0 ? (
            <div className="space-y-3">
              {overview.recent_actions.map((action) => (
                <div key={action.action_id} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div className="flex items-center gap-3">
                    <Badge className={STATUS_COLORS[action.status]}>{action.status}</Badge>
                    <div>
                      <p className="text-sm font-medium">{action.rendered_title}</p>
                      <p className="text-xs text-gray-500">
                        {action.category} • {action.channel}
                      </p>
                    </div>
                  </div>
                  <span className="text-xs text-gray-400">
                    {new Date(action.created_at).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500 text-center py-8">No recent actions</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

// ============================================
// Templates Management Component
// ============================================

const TemplatesManager = () => {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('all');

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const res = await client.get('/admin/enablement/templates');
      setTemplates(res.data.templates);
    } catch (err) {
      toast.error('Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, []);

  const toggleTemplate = async (templateCode) => {
    try {
      await client.put(`/admin/enablement/templates/${templateCode}/toggle`);
      toast.success('Template toggled');
      fetchTemplates();
    } catch (err) {
      toast.error('Failed to toggle template');
    }
  };

  const reseedTemplates = async () => {
    try {
      await client.post('/admin/enablement/templates/seed');
      toast.success('Templates reseeded');
      fetchTemplates();
    } catch (err) {
      toast.error('Failed to reseed templates');
    }
  };

  const filteredTemplates = categoryFilter === 'all'
    ? templates
    : templates.filter(t => t.category === categoryFilter);

  const categories = [...new Set(templates.map(t => t.category))];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Enablement Templates</h2>
          <p className="text-sm text-gray-500">Educational message templates</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All Categories" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Categories</SelectItem>
              {categories.map(cat => (
                <SelectItem key={cat} value={cat}>{cat.replace(/_/g, ' ')}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={reseedTemplates}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Reseed
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTemplates.map(template => {
            const CategoryIcon = CATEGORY_ICONS[template.category] || Activity;
            return (
              <Card key={template.template_id}>
                <CardContent className="py-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <CategoryIcon className="w-5 h-5 text-electric-teal mt-1" />
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-medium">{template.title}</p>
                          <Badge variant="outline" className="text-xs">
                            {template.template_code}
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-600 mt-1">{template.body.slice(0, 100)}...</p>
                        <div className="flex items-center gap-3 mt-2">
                          <span className="text-xs text-gray-500">
                            Category: {template.category.replace(/_/g, ' ')}
                          </span>
                          <span className="text-xs text-gray-500">
                            Channels: {template.channels.join(', ')}
                          </span>
                          <span className="text-xs text-gray-500">
                            Triggers: {template.event_triggers.length}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={template.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}>
                        {template.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                      <Switch
                        checked={template.is_active}
                        onCheckedChange={() => toggleTemplate(template.template_code)}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

// ============================================
// Suppression Rules Component
// ============================================

const SuppressionRules = () => {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newRule, setNewRule] = useState({
    client_id: '',
    category: '',
    template_code: '',
    reason: '',
  });

  const fetchRules = async () => {
    setLoading(true);
    try {
      const res = await client.get('/admin/enablement/suppressions');
      setRules(res.data.rules);
    } catch (err) {
      toast.error('Failed to load suppressions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  const createRule = async () => {
    if (!newRule.reason) {
      toast.error('Reason is required');
      return;
    }
    try {
      await client.post('/admin/enablement/suppressions', {
        client_id: newRule.client_id || null,
        category: newRule.category || null,
        template_code: newRule.template_code || null,
        reason: newRule.reason,
      });
      toast.success('Suppression rule created');
      setShowCreate(false);
      setNewRule({ client_id: '', category: '', template_code: '', reason: '' });
      fetchRules();
    } catch (err) {
      toast.error('Failed to create rule');
    }
  };

  const deleteRule = async (ruleId) => {
    if (!window.confirm('Deactivate this suppression rule?')) return;
    try {
      await client.delete(`/admin/enablement/suppressions/${ruleId}`);
      toast.success('Rule deactivated');
      fetchRules();
    } catch (err) {
      toast.error('Failed to deactivate rule');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Suppression Rules</h2>
          <p className="text-sm text-gray-500">Control which notifications are suppressed</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Add Rule
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      ) : rules.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-gray-500">
            <Shield className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No active suppression rules</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {rules.map(rule => (
            <Card key={rule.rule_id}>
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{rule.reason}</p>
                    <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                      {rule.client_id && <span>Client: {rule.client_id}</span>}
                      {rule.category && <span>Category: {rule.category}</span>}
                      {rule.template_code && <span>Template: {rule.template_code}</span>}
                      {!rule.client_id && !rule.category && !rule.template_code && (
                        <span className="text-yellow-600">Global suppression</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      Created: {new Date(rule.created_at).toLocaleString()}
                    </p>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => deleteRule(rule.rule_id)}>
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Suppression Rule</DialogTitle>
            <DialogDescription>
              Suppress enablement notifications. Leave fields empty for broader scope.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label>Client ID (optional)</Label>
              <Input
                placeholder="Leave empty for all clients"
                value={newRule.client_id}
                onChange={(e) => setNewRule({ ...newRule, client_id: e.target.value })}
              />
            </div>
            <div>
              <Label>Category (optional)</Label>
              <Select
                value={newRule.category}
                onValueChange={(v) => setNewRule({ ...newRule, category: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All categories" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All categories</SelectItem>
                  <SelectItem value="ONBOARDING_GUIDANCE">Onboarding Guidance</SelectItem>
                  <SelectItem value="VALUE_CONFIRMATION">Value Confirmation</SelectItem>
                  <SelectItem value="COMPLIANCE_AWARENESS">Compliance Awareness</SelectItem>
                  <SelectItem value="INACTIVITY_SUPPORT">Inactivity Support</SelectItem>
                  <SelectItem value="FEATURE_GATE_EXPLANATION">Feature Gate Explanation</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Reason *</Label>
              <Textarea
                placeholder="Why is this suppression needed?"
                value={newRule.reason}
                onChange={(e) => setNewRule({ ...newRule, reason: e.target.value })}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button onClick={createRule}>Create Rule</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

// ============================================
// Client Timeline Component
// ============================================

const ClientTimeline = () => {
  const [clientId, setClientId] = useState('');
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const searchTimeline = async () => {
    if (!clientId.trim()) {
      toast.error('Enter a client ID');
      return;
    }
    setLoading(true);
    setSearched(true);
    try {
      const res = await client.get(`/admin/enablement/clients/${clientId}/timeline`);
      setTimeline(res.data.actions);
    } catch (err) {
      toast.error('Failed to load timeline');
      setTimeline([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Client Enablement Timeline</h2>
        <p className="text-sm text-gray-500">View enablement history for a specific client</p>
      </div>

      <div className="flex gap-2">
        <Input
          placeholder="Enter Client ID (e.g., client-001)"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && searchTimeline()}
          className="max-w-md"
        />
        <Button onClick={searchTimeline} disabled={loading}>
          <Search className="w-4 h-4 mr-2" />
          Search
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      ) : searched && timeline.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-gray-500">
            <History className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No enablement actions found for this client</p>
          </CardContent>
        </Card>
      ) : timeline.length > 0 ? (
        <div className="space-y-3">
          {timeline.map(action => {
            const ChannelIcon = CHANNEL_ICONS[action.channel] || Bell;
            return (
              <Card key={action.action_id}>
                <CardContent className="py-4">
                  <div className="flex items-start gap-4">
                    <div className={`p-2 rounded-lg ${STATUS_COLORS[action.status]}`}>
                      <ChannelIcon className="w-4 h-4" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{action.rendered_title}</p>
                        <Badge className={STATUS_COLORS[action.status]}>{action.status}</Badge>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{action.rendered_body}</p>
                      <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                        <span>Category: {action.category}</span>
                        <span>Channel: {action.channel}</span>
                        <span>Event: {action.event_type}</span>
                      </div>
                      {action.status_reason && (
                        <p className="text-xs text-yellow-600 mt-1">Reason: {action.status_reason}</p>
                      )}
                    </div>
                    <span className="text-xs text-gray-400 whitespace-nowrap">
                      {new Date(action.created_at).toLocaleString()}
                    </span>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : null}
    </div>
  );
};

// ============================================
// Manual Trigger Component (Testing)
// ============================================

const ManualTrigger = () => {
  const [eventTypes, setEventTypes] = useState([]);
  const [trigger, setTrigger] = useState({
    event_type: '',
    client_id: '',
    context_payload: '{}',
  });
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    const fetchEventTypes = async () => {
      try {
        const res = await client.get('/admin/enablement/event-types');
        setEventTypes(res.data.event_types);
      } catch (err) {
        console.error('Failed to fetch event types');
      }
    };
    fetchEventTypes();
  }, []);

  const triggerEvent = async () => {
    if (!trigger.event_type || !trigger.client_id) {
      toast.error('Event type and Client ID are required');
      return;
    }

    let contextPayload = {};
    try {
      contextPayload = JSON.parse(trigger.context_payload);
    } catch {
      toast.error('Invalid JSON in context payload');
      return;
    }

    setTriggering(true);
    try {
      const res = await client.post('/admin/enablement/trigger', {
        event_type: trigger.event_type,
        client_id: trigger.client_id,
        context_payload: contextPayload,
      });
      toast.success(res.data.message);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to trigger event');
    } finally {
      setTriggering(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Manual Event Trigger</h2>
        <p className="text-sm text-gray-500">Trigger enablement events for testing (respects all rules)</p>
      </div>

      <Card>
        <CardContent className="py-6 space-y-4">
          <div>
            <Label>Event Type *</Label>
            <Select
              value={trigger.event_type}
              onValueChange={(v) => setTrigger({ ...trigger, event_type: v })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select event type" />
              </SelectTrigger>
              <SelectContent>
                {eventTypes.map(et => (
                  <SelectItem key={et.value} value={et.value}>{et.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Client ID *</Label>
            <Input
              placeholder="e.g., client-001"
              value={trigger.client_id}
              onChange={(e) => setTrigger({ ...trigger, client_id: e.target.value })}
            />
          </div>

          <div>
            <Label>Context Payload (JSON)</Label>
            <Textarea
              placeholder='{"property_address": "123 Main St"}'
              value={trigger.context_payload}
              onChange={(e) => setTrigger({ ...trigger, context_payload: e.target.value })}
              rows={4}
              className="font-mono text-sm"
            />
          </div>

          <Button onClick={triggerEvent} disabled={triggering} className="w-full">
            <Zap className="w-4 h-4 mr-2" />
            {triggering ? 'Triggering...' : 'Trigger Event'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

// ============================================
// Main Component
// ============================================

const AdminEnablementDashboard = () => {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <UnifiedAdminLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900" data-testid="enablement-dashboard-title">
            Customer Enablement Engine
          </h1>
          <p className="text-gray-500 mt-1">
            Educational automation system • Not marketing • Not sales
          </p>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="overview" data-testid="tab-overview">
              <BarChart3 className="w-4 h-4 mr-2" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="templates" data-testid="tab-templates">
              <FileText className="w-4 h-4 mr-2" />
              Templates
            </TabsTrigger>
            <TabsTrigger value="suppressions" data-testid="tab-suppressions">
              <Shield className="w-4 h-4 mr-2" />
              Suppressions
            </TabsTrigger>
            <TabsTrigger value="timeline" data-testid="tab-timeline">
              <History className="w-4 h-4 mr-2" />
              Client Timeline
            </TabsTrigger>
            <TabsTrigger value="trigger" data-testid="tab-trigger">
              <Zap className="w-4 h-4 mr-2" />
              Manual Trigger
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <OverviewDashboard />
          </TabsContent>

          <TabsContent value="templates">
            <TemplatesManager />
          </TabsContent>

          <TabsContent value="suppressions">
            <SuppressionRules />
          </TabsContent>

          <TabsContent value="timeline">
            <ClientTimeline />
          </TabsContent>

          <TabsContent value="trigger">
            <ManualTrigger />
          </TabsContent>
        </Tabs>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminEnablementDashboard;
