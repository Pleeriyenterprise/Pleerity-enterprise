/**
 * Admin Lead Management Dashboard
 * 
 * Features:
 * - Lead list with filters (source, stage, intent, status)
 * - Lead detail view with transcript, audit log
 * - Actions: assign, contact, convert, mark lost
 * - Manual lead creation
 * - SLA breach indicators
 * - Stats overview
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
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
import { toast } from 'sonner';
import {
  Users,
  Plus,
  Search,
  Filter,
  Eye,
  Phone,
  Mail,
  MessageSquare,
  UserCheck,
  UserX,
  Clock,
  AlertTriangle,
  TrendingUp,
  RefreshCw,
  ChevronRight,
  Send,
  Merge,
  Bot,
  FileText,
  Upload,
} from 'lucide-react';

// Intent score colors
const intentColors = {
  HIGH: 'bg-green-100 text-green-800 border-green-200',
  MEDIUM: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  LOW: 'bg-gray-100 text-gray-800 border-gray-200',
};

// Stage colors
const stageColors = {
  NEW: 'bg-blue-100 text-blue-800',
  CONTACTED: 'bg-purple-100 text-purple-800',
  QUALIFIED: 'bg-indigo-100 text-indigo-800',
  PROPOSAL_SENT: 'bg-cyan-100 text-cyan-800',
  WON: 'bg-green-100 text-green-800',
  LOST: 'bg-red-100 text-red-800',
};

// Source icons
const sourceIcons = {
  WEB_CHAT: MessageSquare,
  WHATSAPP: Phone,
  INTAKE_ABANDONED: Clock,
  DOCUMENT_SERVICES: FileText,
  ADMIN: Users,
  CONTACT_FORM: Mail,
};

export default function AdminLeadsPage() {
  useAuth(); // Ensure authenticated
  
  // State
  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sources, setSources] = useState({});
  
  // Filters
  const [search, setSearch] = useState('');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [stageFilter, setStageFilter] = useState('all');
  const [intentFilter, setIntentFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [slaBreachOnly, setSlaBreachOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  
  // Dialog state
  const [selectedLead, setSelectedLead] = useState(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [actionDialogOpen, setActionDialogOpen] = useState(false);
  const [actionType, setActionType] = useState(null);
  
  // Form state
  const [createForm, setCreateForm] = useState({
    name: '',
    email: '',
    phone: '',
    company_name: '',
    service_interest: 'UNKNOWN',
    message_summary: '',
    intent_score: '',
    admin_notes: '',
  });
  const [actionForm, setActionForm] = useState({});
  const [saving, setSaving] = useState(false);

  // Fetch sources
  useEffect(() => {
    const fetchSources = async () => {
      try {
        const response = await client.get('/admin/leads/sources');
        setSources(response.data);
      } catch (error) {
        console.error('Failed to fetch sources:', error);
      }
    };
    fetchSources();
  }, []);

  // Fetch leads
  const fetchLeads = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (sourceFilter !== 'all') params.append('source_platform', sourceFilter);
      if (stageFilter !== 'all') params.append('stage', stageFilter);
      if (intentFilter !== 'all') params.append('intent_score', intentFilter);
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (slaBreachOnly) params.append('sla_breach_only', 'true');
      params.append('page', page.toString());
      params.append('limit', '50');
      
      const response = await client.get(`/admin/leads?${params.toString()}`);
      setLeads(response.data.leads || []);
      setTotal(response.data.total || 0);
      setStats(response.data.stats || {});
    } catch (error) {
      console.error('Failed to fetch leads:', error);
      toast.error('Failed to load leads');
    } finally {
      setLoading(false);
    }
  }, [search, sourceFilter, stageFilter, intentFilter, statusFilter, slaBreachOnly, page]);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  // Open lead detail
  const openLeadDetail = async (leadId) => {
    try {
      const response = await client.get(`/admin/leads/${leadId}`);
      setSelectedLead(response.data);
      setDetailDialogOpen(true);
    } catch (error) {
      console.error('Failed to load lead:', error);
      toast.error('Failed to load lead details');
    }
  };

  // Create lead
  const handleCreateLead = async () => {
    if (!createForm.email) {
      toast.error('Email is required');
      return;
    }
    
    setSaving(true);
    try {
      const params = new URLSearchParams();
      Object.entries(createForm).forEach(([key, value]) => {
        if (value) params.append(key, value);
      });
      
      await client.post(`/admin/leads?${params.toString()}`);
      toast.success('Lead created');
      setCreateDialogOpen(false);
      setCreateForm({
        name: '',
        email: '',
        phone: '',
        company_name: '',
        service_interest: 'UNKNOWN',
        message_summary: '',
        intent_score: '',
        admin_notes: '',
      });
      fetchLeads();
    } catch (error) {
      console.error('Failed to create lead:', error);
      toast.error(error.response?.data?.detail || 'Failed to create lead');
    } finally {
      setSaving(false);
    }
  };

  // Lead actions
  const openAction = (lead, type) => {
    setSelectedLead(lead);
    setActionType(type);
    setActionForm({});
    setActionDialogOpen(true);
  };

  const handleAction = async () => {
    if (!selectedLead || !actionType) return;
    
    setSaving(true);
    try {
      switch (actionType) {
        case 'contact':
          await client.post(`/admin/leads/${selectedLead.lead_id}/contact`, null, {
            params: {
              contact_method: actionForm.contact_method || 'email',
              notes: actionForm.notes,
              outcome: actionForm.outcome,
            }
          });
          toast.success('Contact logged');
          break;
        
        case 'assign':
          await client.post(`/admin/leads/${selectedLead.lead_id}/assign`, null, {
            params: {
              admin_id: actionForm.admin_id,
              notify_admin: actionForm.notify_admin || true,
            }
          });
          toast.success('Lead assigned');
          break;
        
        case 'convert':
          await client.post(`/admin/leads/${selectedLead.lead_id}/convert`, null, {
            params: {
              client_id: actionForm.client_id,
              conversion_notes: actionForm.notes,
            }
          });
          toast.success('Lead converted to client');
          break;
        
        case 'lost':
          await client.post(`/admin/leads/${selectedLead.lead_id}/mark-lost`, null, {
            params: {
              reason: actionForm.reason,
              competitor: actionForm.competitor,
            }
          });
          toast.success('Lead marked as lost');
          break;
        
        case 'message':
          await client.post(`/admin/leads/${selectedLead.lead_id}/send-message`, null, {
            params: {
              subject: actionForm.subject,
              message: actionForm.message,
            }
          });
          toast.success('Message sent');
          break;
        
        case 'summary':
          await client.post(`/admin/leads/${selectedLead.lead_id}/generate-summary`);
          toast.success('AI summary generated');
          break;
      }
      
      setActionDialogOpen(false);
      fetchLeads();
      
      // Refresh detail if open
      if (detailDialogOpen && selectedLead) {
        openLeadDetail(selectedLead.lead_id);
      }
    } catch (error) {
      console.error('Action failed:', error);
      toast.error(error.response?.data?.detail || 'Action failed');
    } finally {
      setSaving(false);
    }
  };

  const SourceIcon = (source) => sourceIcons[source] || Users;

  return (
    <UnifiedAdminLayout>
    <div className="space-y-6" data-testid="admin-leads-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Users className="h-6 w-6 text-teal-600" />
            Lead Management
          </h1>
          <p className="text-gray-500 mt-1">Capture, qualify, and convert leads</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchLeads}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button
            variant="outline"
            onClick={() => toast.info('CSV Import coming soon')}
          >
            <Upload className="h-4 w-4 mr-2" />
            Import CSV
          </Button>
          <Button
            onClick={() => setCreateDialogOpen(true)}
            className="bg-teal-600 hover:bg-teal-700"
            data-testid="create-lead-btn"
          >
            <Plus className="h-4 w-4 mr-2" />
            New Lead
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid md:grid-cols-6 gap-4">
          <Card>
            <CardContent className="py-4">
              <div className="text-3xl font-bold text-teal-600">{stats.total_leads || 0}</div>
              <div className="text-sm text-gray-500">Total Leads</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4">
              <div className="text-3xl font-bold text-blue-600">{stats.new_leads || 0}</div>
              <div className="text-sm text-gray-500">New</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4">
              <div className="text-3xl font-bold text-purple-600">{stats.contacted_leads || 0}</div>
              <div className="text-sm text-gray-500">Contacted</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4">
              <div className="text-3xl font-bold text-green-600">{stats.converted_leads || 0}</div>
              <div className="text-sm text-gray-500">Converted</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4">
              <div className="text-3xl font-bold text-green-700">{stats.conversion_rate || 0}%</div>
              <div className="text-sm text-gray-500">Conversion Rate</div>
            </CardContent>
          </Card>
          <Card className={stats.sla_breaches_today > 0 ? 'border-red-300 bg-red-50' : ''}>
            <CardContent className="py-4">
              <div className={`text-3xl font-bold ${stats.sla_breaches_today > 0 ? 'text-red-600' : 'text-gray-600'}`}>
                {stats.sla_breaches_today || 0}
              </div>
              <div className="text-sm text-gray-500 flex items-center gap-1">
                {stats.sla_breaches_today > 0 && <AlertTriangle className="h-3 w-3 text-red-500" />}
                SLA Breaches
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-4 items-center flex-wrap bg-gray-50 p-4 rounded-lg">
        <Filter className="h-5 w-5 text-gray-400" />
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search leads..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
            data-testid="search-leads-input"
          />
        </div>
        <Select value={sourceFilter} onValueChange={setSourceFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Source" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Sources</SelectItem>
            {sources.source_platforms?.map(s => (
              <SelectItem key={s} value={s}>{s.replace(/_/g, ' ')}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={stageFilter} onValueChange={setStageFilter}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Stage" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Stages</SelectItem>
            {sources.stages?.map(s => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={intentFilter} onValueChange={setIntentFilter}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Intent" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Intent</SelectItem>
            {sources.intent_scores?.map(s => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={slaBreachOnly}
            onChange={(e) => setSlaBreachOnly(e.target.checked)}
            className="rounded"
          />
          SLA Breaches
        </label>
        <Button variant="outline" size="sm" onClick={fetchLeads}>
          Apply
        </Button>
      </div>

      {/* Leads List */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading leads...</div>
      ) : leads.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Users className="h-12 w-12 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">No leads found</p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => setCreateDialogOpen(true)}
            >
              Create your first lead
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {leads.map(lead => {
            const Icon = SourceIcon(lead.source_platform);
            return (
              <Card 
                key={lead.lead_id} 
                className={`hover:shadow-md transition-shadow cursor-pointer ${lead.sla_breach ? 'border-red-300 bg-red-50' : ''}`}
                onClick={() => openLeadDetail(lead.lead_id)}
                data-testid={`lead-${lead.lead_id}`}
              >
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 flex-1">
                      <div className={`p-2 rounded-lg ${lead.sla_breach ? 'bg-red-100' : 'bg-gray-100'}`}>
                        <Icon className={`h-5 w-5 ${lead.sla_breach ? 'text-red-600' : 'text-gray-600'}`} />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-semibold text-gray-900">
                            {lead.name || lead.email || 'Unknown'}
                          </span>
                          {lead.sla_breach && (
                            <Badge variant="destructive" className="text-xs">
                              <AlertTriangle className="h-3 w-3 mr-1" />
                              SLA Breach
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-sm text-gray-500">
                          <span>{lead.email}</span>
                          {lead.phone && <span>• {lead.phone}</span>}
                          {lead.company_name && <span>• {lead.company_name}</span>}
                        </div>
                        <div className="flex items-center gap-2 mt-2">
                          <Badge variant="secondary" className="text-xs">
                            {lead.source_platform?.replace(/_/g, ' ')}
                          </Badge>
                          <Badge className={`text-xs ${stageColors[lead.stage] || ''}`}>
                            {lead.stage}
                          </Badge>
                          <Badge variant="outline" className={`text-xs ${intentColors[lead.intent_score] || ''}`}>
                            {lead.intent_score} Intent
                          </Badge>
                          {lead.service_interest && lead.service_interest !== 'UNKNOWN' && (
                            <Badge variant="outline" className="text-xs">
                              {lead.service_interest.replace(/_/g, ' ')}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right text-xs text-gray-400">
                        <div>{new Date(lead.created_at).toLocaleDateString()}</div>
                        <div>{new Date(lead.created_at).toLocaleTimeString()}</div>
                      </div>
                      <ChevronRight className="h-5 w-5 text-gray-400" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
          
          {/* Pagination */}
          <div className="flex items-center justify-between py-4">
            <div className="text-sm text-gray-500">
              Showing {leads.length} of {total} leads
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 1}
                onClick={() => setPage(p => p - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={leads.length < 50}
                onClick={() => setPage(p => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Create Lead Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create Lead Manually</DialogTitle>
            <DialogDescription>
              Add a new lead to the system
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  placeholder="John Smith"
                />
              </div>
              <div>
                <Label htmlFor="email">Email *</Label>
                <Input
                  id="email"
                  type="email"
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  placeholder="john@example.com"
                  required
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="phone">Phone</Label>
                <Input
                  id="phone"
                  value={createForm.phone}
                  onChange={(e) => setCreateForm({ ...createForm, phone: e.target.value })}
                  placeholder="+44 7123 456789"
                />
              </div>
              <div>
                <Label htmlFor="company">Company</Label>
                <Input
                  id="company"
                  value={createForm.company_name}
                  onChange={(e) => setCreateForm({ ...createForm, company_name: e.target.value })}
                  placeholder="Acme Ltd"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Service Interest</Label>
                <Select
                  value={createForm.service_interest}
                  onValueChange={(val) => setCreateForm({ ...createForm, service_interest: val })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {sources.service_interests?.map(s => (
                      <SelectItem key={s} value={s}>{s.replace(/_/g, ' ')}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Intent Score</Label>
                <Select
                  value={createForm.intent_score}
                  onValueChange={(val) => setCreateForm({ ...createForm, intent_score: val })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Auto-calculate" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">Auto-calculate</SelectItem>
                    {sources.intent_scores?.map(s => (
                      <SelectItem key={s} value={s}>{s}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            <div>
              <Label htmlFor="message">Message/Notes</Label>
              <Textarea
                id="message"
                value={createForm.message_summary}
                onChange={(e) => setCreateForm({ ...createForm, message_summary: e.target.value })}
                placeholder="Initial enquiry details..."
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateLead}
              disabled={saving}
              className="bg-teal-600 hover:bg-teal-700"
            >
              {saving ? 'Creating...' : 'Create Lead'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Lead Detail Dialog */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          {selectedLead && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {selectedLead.name || selectedLead.email}
                  {selectedLead.sla_breach && (
                    <Badge variant="destructive">
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      SLA Breach
                    </Badge>
                  )}
                </DialogTitle>
                <DialogDescription>
                  {selectedLead.lead_id} • Created {new Date(selectedLead.created_at).toLocaleString()}
                </DialogDescription>
              </DialogHeader>

              <Tabs defaultValue="details">
                <TabsList>
                  <TabsTrigger value="details">Details</TabsTrigger>
                  <TabsTrigger value="transcript">Transcript</TabsTrigger>
                  <TabsTrigger value="audit">Audit Log</TabsTrigger>
                </TabsList>

                <TabsContent value="details" className="space-y-4">
                  {/* Contact Info */}
                  <Card>
                    <CardHeader className="py-3">
                      <CardTitle className="text-sm">Contact Information</CardTitle>
                    </CardHeader>
                    <CardContent className="grid md:grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-gray-500">Email:</span>{' '}
                        <span className="font-medium">{selectedLead.email || '-'}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Phone:</span>{' '}
                        <span className="font-medium">{selectedLead.phone || '-'}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Company:</span>{' '}
                        <span className="font-medium">{selectedLead.company_name || '-'}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Source:</span>{' '}
                        <Badge variant="secondary">{selectedLead.source_platform?.replace(/_/g, ' ')}</Badge>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Status */}
                  <Card>
                    <CardHeader className="py-3">
                      <CardTitle className="text-sm">Status & Qualification</CardTitle>
                    </CardHeader>
                    <CardContent className="grid md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className="text-gray-500">Stage:</span>{' '}
                        <Badge className={stageColors[selectedLead.stage]}>{selectedLead.stage}</Badge>
                      </div>
                      <div>
                        <span className="text-gray-500">Intent:</span>{' '}
                        <Badge variant="outline" className={intentColors[selectedLead.intent_score]}>
                          {selectedLead.intent_score}
                        </Badge>
                      </div>
                      <div>
                        <span className="text-gray-500">Service:</span>{' '}
                        <span className="font-medium">{selectedLead.service_interest?.replace(/_/g, ' ')}</span>
                      </div>
                    </CardContent>
                  </Card>

                  {/* AI Summary */}
                  {selectedLead.ai_summary && (
                    <Card className="bg-blue-50 border-blue-200">
                      <CardHeader className="py-3">
                        <CardTitle className="text-sm flex items-center gap-2">
                          <Bot className="h-4 w-4" />
                          AI Summary
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm">{selectedLead.ai_summary}</p>
                      </CardContent>
                    </Card>
                  )}

                  {/* Message */}
                  {selectedLead.message_summary && (
                    <Card>
                      <CardHeader className="py-3">
                        <CardTitle className="text-sm">Message</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm text-gray-700">{selectedLead.message_summary}</p>
                      </CardContent>
                    </Card>
                  )}

                  {/* Actions */}
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" onClick={() => openAction(selectedLead, 'contact')}>
                      <Phone className="h-4 w-4 mr-1" />
                      Log Contact
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => openAction(selectedLead, 'message')}>
                      <Send className="h-4 w-4 mr-1" />
                      Send Message
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => openAction(selectedLead, 'assign')}>
                      <UserCheck className="h-4 w-4 mr-1" />
                      Assign
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => openAction(selectedLead, 'summary')}>
                      <Bot className="h-4 w-4 mr-1" />
                      Generate Summary
                    </Button>
                    <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={() => openAction(selectedLead, 'convert')}>
                      <TrendingUp className="h-4 w-4 mr-1" />
                      Convert to Client
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => openAction(selectedLead, 'lost')}>
                      <UserX className="h-4 w-4 mr-1" />
                      Mark Lost
                    </Button>
                  </div>
                </TabsContent>

                <TabsContent value="transcript">
                  {selectedLead.transcript?.length > 0 ? (
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {selectedLead.transcript.map((msg, idx) => (
                        <div
                          key={idx}
                          className={`p-3 rounded-lg ${msg.sender === 'user' ? 'bg-blue-50 ml-8' : 'bg-gray-100 mr-8'}`}
                        >
                          <div className="text-xs text-gray-500 mb-1">
                            {msg.sender === 'user' ? 'Lead' : 'Bot'} • {new Date(msg.timestamp).toLocaleString()}
                          </div>
                          <p className="text-sm">{msg.message_text}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 text-center py-8">No transcript available</p>
                  )}
                </TabsContent>

                <TabsContent value="audit">
                  {selectedLead.audit_log?.length > 0 ? (
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {selectedLead.audit_log.map((log, idx) => (
                        <div key={idx} className="flex items-start gap-3 text-sm py-2 border-b">
                          <div className="w-32 text-xs text-gray-400">
                            {new Date(log.created_at).toLocaleString()}
                          </div>
                          <div className="flex-1">
                            <Badge variant="outline" className="text-xs mb-1">
                              {log.event.replace(/_/g, ' ')}
                            </Badge>
                            <div className="text-gray-600">{log.actor_id} ({log.actor_type})</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 text-center py-8">No audit log entries</p>
                  )}
                </TabsContent>
              </Tabs>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Action Dialog */}
      <Dialog open={actionDialogOpen} onOpenChange={setActionDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {actionType === 'contact' && 'Log Contact'}
              {actionType === 'assign' && 'Assign Lead'}
              {actionType === 'convert' && 'Convert to Client'}
              {actionType === 'lost' && 'Mark as Lost'}
              {actionType === 'message' && 'Send Message'}
              {actionType === 'summary' && 'Generate AI Summary'}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {actionType === 'contact' && (
              <>
                <div>
                  <Label>Contact Method</Label>
                  <Select
                    value={actionForm.contact_method || ''}
                    onValueChange={(val) => setActionForm({ ...actionForm, contact_method: val })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select method" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="email">Email</SelectItem>
                      <SelectItem value="phone">Phone</SelectItem>
                      <SelectItem value="whatsapp">WhatsApp</SelectItem>
                      <SelectItem value="in_person">In Person</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Outcome</Label>
                  <Select
                    value={actionForm.outcome || ''}
                    onValueChange={(val) => setActionForm({ ...actionForm, outcome: val })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select outcome" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="answered">Answered</SelectItem>
                      <SelectItem value="voicemail">Voicemail</SelectItem>
                      <SelectItem value="no_response">No Response</SelectItem>
                      <SelectItem value="callback_requested">Callback Requested</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Notes</Label>
                  <Textarea
                    value={actionForm.notes || ''}
                    onChange={(e) => setActionForm({ ...actionForm, notes: e.target.value })}
                    placeholder="Contact notes..."
                  />
                </div>
              </>
            )}

            {actionType === 'assign' && (
              <div>
                <Label>Assign to Admin (email)</Label>
                <Input
                  value={actionForm.admin_id || ''}
                  onChange={(e) => setActionForm({ ...actionForm, admin_id: e.target.value })}
                  placeholder="admin@pleerity.com"
                />
              </div>
            )}

            {actionType === 'convert' && (
              <>
                <div>
                  <Label>Client ID</Label>
                  <Input
                    value={actionForm.client_id || ''}
                    onChange={(e) => setActionForm({ ...actionForm, client_id: e.target.value })}
                    placeholder="CLT-XXXX"
                  />
                </div>
                <div>
                  <Label>Conversion Notes</Label>
                  <Textarea
                    value={actionForm.notes || ''}
                    onChange={(e) => setActionForm({ ...actionForm, notes: e.target.value })}
                    placeholder="How was the lead converted..."
                  />
                </div>
              </>
            )}

            {actionType === 'lost' && (
              <>
                <div>
                  <Label>Reason *</Label>
                  <Textarea
                    value={actionForm.reason || ''}
                    onChange={(e) => setActionForm({ ...actionForm, reason: e.target.value })}
                    placeholder="Why was this lead lost..."
                    required
                  />
                </div>
                <div>
                  <Label>Competitor (if applicable)</Label>
                  <Input
                    value={actionForm.competitor || ''}
                    onChange={(e) => setActionForm({ ...actionForm, competitor: e.target.value })}
                    placeholder="Competitor name"
                  />
                </div>
              </>
            )}

            {actionType === 'message' && (
              <>
                <div>
                  <Label>Subject *</Label>
                  <Input
                    value={actionForm.subject || ''}
                    onChange={(e) => setActionForm({ ...actionForm, subject: e.target.value })}
                    placeholder="Email subject"
                    required
                  />
                </div>
                <div>
                  <Label>Message *</Label>
                  <Textarea
                    value={actionForm.message || ''}
                    onChange={(e) => setActionForm({ ...actionForm, message: e.target.value })}
                    placeholder="Your message..."
                    rows={5}
                    required
                  />
                </div>
              </>
            )}

            {actionType === 'summary' && (
              <p className="text-sm text-gray-600">
                Generate an AI-powered summary of this lead based on their conversation and enquiry details.
              </p>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setActionDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleAction}
              disabled={saving}
              className="bg-teal-600 hover:bg-teal-700"
            >
              {saving ? 'Processing...' : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
    </UnifiedAdminLayout>
  );
}
