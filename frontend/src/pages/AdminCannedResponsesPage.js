/**
 * Admin Canned Responses Management Page
 * 
 * Features:
 * - CRUD for canned responses
 * - Filter by category/channel
 * - Preview panel (how it looks in chat/WhatsApp)
 * - Soft delete (is_active flag)
 * - Full audit logging
 */
import React, { useState, useEffect, useCallback } from 'react';
import client from '../api/client';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import {
  MessageSquare,
  Plus,
  Edit2,
  Trash2,
  Search,
  Eye,
  RefreshCw,
  Save,
  Filter,
  Phone,
  Mail,
  Globe,
} from 'lucide-react';

const CHANNELS = [
  { value: 'WEB_CHAT', label: 'Web Chat', icon: Globe },
  { value: 'WHATSAPP', label: 'WhatsApp', icon: Phone },
  { value: 'EMAIL', label: 'Email', icon: Mail },
];

const CATEGORIES = [
  { value: 'orders', label: 'Orders' },
  { value: 'billing', label: 'Billing' },
  { value: 'login', label: 'Login' },
  { value: 'documents', label: 'Documents' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'cvp', label: 'CVP' },
  { value: 'technical', label: 'Technical' },
  { value: 'handoff', label: 'Handoff' },
  { value: 'other', label: 'Other' },
];

export default function AdminCannedResponsesPage() {
  const [responses, setResponses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [channelFilter, setChannelFilter] = useState('all');
  const [includeInactive, setIncludeInactive] = useState(false);
  
  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false);
  const [editingResponse, setEditingResponse] = useState(null);
  const [previewResponse, setPreviewResponse] = useState(null);
  
  // Form state
  const [form, setForm] = useState({
    label: '',
    category: 'other',
    channel: 'WEB_CHAT',
    response_text: '',
    icon: '💬',
    order: 0,
    trigger_keywords: '',
  });
  const [saving, setSaving] = useState(false);

  // Fetch responses
  const fetchResponses = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (categoryFilter !== 'all') params.append('category', categoryFilter);
      if (channelFilter !== 'all') params.append('channel', channelFilter);
      if (includeInactive) params.append('include_inactive', 'true');
      
      const response = await client.get(`/admin/support/responses?${params.toString()}`);
      setResponses(response.data.responses || []);
    } catch (error) {
      console.error('Failed to fetch responses:', error);
      toast.error('Failed to load responses');
    } finally {
      setLoading(false);
    }
  }, [search, categoryFilter, channelFilter, includeInactive]);

  useEffect(() => {
    fetchResponses();
  }, [fetchResponses]);

  // Handle form submit
  const handleSubmit = async () => {
    if (!form.label || !form.response_text) {
      toast.error('Label and response text are required');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        ...form,
        trigger_keywords: form.trigger_keywords
          ? form.trigger_keywords.split(',').map(k => k.trim()).filter(Boolean)
          : [],
      };

      if (editingResponse) {
        await client.put(`/admin/support/responses/${editingResponse.response_id}`, payload);
        toast.success('Response updated');
      } else {
        await client.post('/admin/support/responses', payload);
        toast.success('Response created');
      }

      setDialogOpen(false);
      setEditingResponse(null);
      setForm({ label: '', category: 'other', channel: 'WEB_CHAT', response_text: '', icon: '💬', order: 0, trigger_keywords: '' });
      fetchResponses();
    } catch (error) {
      console.error('Failed to save response:', error);
      toast.error(error.response?.data?.detail || 'Failed to save response');
    } finally {
      setSaving(false);
    }
  };

  // Delete response (soft)
  const handleDelete = async (responseId) => {
    if (!window.confirm('Are you sure you want to deactivate this response?')) return;
    
    try {
      await client.delete(`/admin/support/responses/${responseId}`);
      toast.success('Response deactivated');
      fetchResponses();
    } catch (error) {
      console.error('Failed to delete response:', error);
      toast.error('Failed to deactivate response');
    }
  };

  // Reactivate response
  const handleReactivate = async (responseId) => {
    try {
      await client.post(`/admin/support/responses/${responseId}/reactivate`);
      toast.success('Response reactivated');
      fetchResponses();
    } catch (error) {
      console.error('Failed to reactivate response:', error);
      toast.error('Failed to reactivate response');
    }
  };

  // Open edit dialog
  const openEdit = (response) => {
    setEditingResponse(response);
    setForm({
      label: response.label || '',
      category: response.category || 'other',
      channel: response.channel || 'WEB_CHAT',
      response_text: response.response_text || '',
      icon: response.icon || '💬',
      order: response.order || 0,
      trigger_keywords: (response.trigger_keywords || []).join(', '),
    });
    setDialogOpen(true);
  };

  // Open preview dialog
  const openPreview = (response) => {
    setPreviewResponse(response);
    setPreviewDialogOpen(true);
  };

  const getChannelIcon = (channel) => {
    const ch = CHANNELS.find(c => c.value === channel);
    return ch ? ch.icon : Globe;
  };

  return (
    <UnifiedAdminLayout>
    <div className="space-y-6" data-testid="admin-canned-responses-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <MessageSquare className="h-6 w-6 text-teal-600" />
            Canned Responses
          </h1>
          <p className="text-gray-500 mt-1">Manage quick responses for the support chatbot</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchResponses}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button
            onClick={() => {
              setEditingResponse(null);
              setForm({ label: '', category: 'other', channel: 'WEB_CHAT', response_text: '', icon: '💬', order: 0, trigger_keywords: '' });
              setDialogOpen(true);
            }}
            className="bg-teal-600 hover:bg-teal-700"
            data-testid="create-response-btn"
          >
            <Plus className="h-4 w-4 mr-2" />
            New Response
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4 items-center flex-wrap bg-gray-50 p-4 rounded-lg">
        <Filter className="h-5 w-5 text-gray-400" />
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search responses..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
            data-testid="search-responses-input"
          />
        </div>
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            {CATEGORIES.map(cat => (
              <SelectItem key={cat.value} value={cat.value}>{cat.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={channelFilter} onValueChange={setChannelFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Channel" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Channels</SelectItem>
            {CHANNELS.map(ch => (
              <SelectItem key={ch.value} value={ch.value}>{ch.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
            className="rounded"
          />
          Show inactive
        </label>
        <Button variant="outline" size="sm" onClick={fetchResponses}>
          Apply
        </Button>
      </div>

      {/* Responses List */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading responses...</div>
      ) : responses.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <MessageSquare className="h-12 w-12 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">No canned responses found</p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => setDialogOpen(true)}
            >
              Create your first response
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {responses.map(response => {
            const ChannelIcon = getChannelIcon(response.channel);
            return (
              <Card 
                key={response.response_id} 
                className={`hover:shadow-md transition-shadow ${!response.is_active ? 'opacity-60 bg-gray-50' : ''}`}
                data-testid={`response-${response.response_id}`}
              >
                <CardContent className="py-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xl">{response.icon}</span>
                        <h3 className="font-semibold text-gray-900">{response.label}</h3>
                        <Badge variant={response.is_active ? 'default' : 'secondary'}>
                          {response.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                        <Badge variant="outline" className="flex items-center gap-1">
                          <ChannelIcon className="h-3 w-3" />
                          {response.channel}
                        </Badge>
                        <Badge variant="secondary">{response.category}</Badge>
                      </div>
                      <p className="text-sm text-gray-600 line-clamp-2">{response.response_text}</p>
                      {response.trigger_keywords?.length > 0 && (
                        <div className="flex gap-1 mt-2 flex-wrap">
                          {response.trigger_keywords.map(kw => (
                            <Badge key={kw} variant="outline" className="text-xs">
                              {kw}
                            </Badge>
                          ))}
                        </div>
                      )}
                      <p className="text-xs text-gray-400 mt-2">
                        Order: {response.order} • Updated: {new Date(response.updated_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex gap-2 ml-4">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openPreview(response)}
                        title="Preview"
                      >
                        <Eye className="h-4 w-4 text-purple-500" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEdit(response)}
                        data-testid={`edit-response-${response.response_id}`}
                      >
                        <Edit2 className="h-4 w-4 text-blue-500" />
                      </Button>
                      {response.is_active ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(response.response_id)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleReactivate(response.response_id)}
                          title="Reactivate"
                        >
                          <RefreshCw className="h-4 w-4 text-green-500" />
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingResponse ? 'Edit Response' : 'Create Response'}</DialogTitle>
            <DialogDescription>
              Configure the canned response for the support chatbot
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="label">Label *</Label>
                <Input
                  id="label"
                  value={form.label}
                  onChange={(e) => setForm({ ...form, label: e.target.value })}
                  placeholder="Check Order Status"
                  data-testid="response-label-input"
                />
              </div>
              <div>
                <Label htmlFor="icon">Icon (emoji)</Label>
                <Input
                  id="icon"
                  value={form.icon}
                  onChange={(e) => setForm({ ...form, icon: e.target.value })}
                  placeholder="📦"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label htmlFor="category">Category *</Label>
                <Select
                  value={form.category}
                  onValueChange={(val) => setForm({ ...form, category: val })}
                >
                  <SelectTrigger data-testid="response-category-select">
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map(cat => (
                      <SelectItem key={cat.value} value={cat.value}>{cat.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="channel">Channel</Label>
                <Select
                  value={form.channel}
                  onValueChange={(val) => setForm({ ...form, channel: val })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select channel" />
                  </SelectTrigger>
                  <SelectContent>
                    {CHANNELS.map(ch => (
                      <SelectItem key={ch.value} value={ch.value}>{ch.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="order">Display Order</Label>
                <Input
                  id="order"
                  type="number"
                  value={form.order}
                  onChange={(e) => setForm({ ...form, order: parseInt(e.target.value) || 0 })}
                />
              </div>
            </div>

            <div>
              <Label htmlFor="response_text">Response Text *</Label>
              <Textarea
                id="response_text"
                value={form.response_text}
                onChange={(e) => setForm({ ...form, response_text: e.target.value })}
                placeholder="To check your order status, please log in to your account and visit the Orders page..."
                rows={6}
                data-testid="response-text-input"
              />
              <p className="text-xs text-gray-400 mt-1">Supports Markdown for web chat</p>
            </div>

            <div>
              <Label htmlFor="trigger_keywords">Trigger Keywords (comma-separated)</Label>
              <Input
                id="trigger_keywords"
                value={form.trigger_keywords}
                onChange={(e) => setForm({ ...form, trigger_keywords: e.target.value })}
                placeholder="order, status, tracking, delivery"
              />
              <p className="text-xs text-gray-400 mt-1">Keywords that trigger this response in AI matching</p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={saving}
              className="bg-teal-600 hover:bg-teal-700"
              data-testid="save-response-btn"
            >
              {saving ? (
                <><RefreshCw className="h-4 w-4 mr-2 animate-spin" /> Saving...</>
              ) : (
                <><Save className="h-4 w-4 mr-2" /> {editingResponse ? 'Update' : 'Create'}</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview Dialog */}
      <Dialog open={previewDialogOpen} onOpenChange={setPreviewDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Response Preview</DialogTitle>
            <DialogDescription>
              How this response appears to users
            </DialogDescription>
          </DialogHeader>

          {previewResponse && (
            <div className="space-y-4">
              {/* Web Chat Preview */}
              <div>
                <p className="text-sm font-medium text-gray-600 mb-2 flex items-center gap-2">
                  <Globe className="h-4 w-4" /> Web Chat Preview
                </p>
                <div className="bg-gray-100 rounded-lg p-4">
                  <div className="bg-white rounded-lg p-3 shadow-sm">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-8 h-8 bg-teal-100 rounded-full flex items-center justify-center">
                        <MessageSquare className="h-4 w-4 text-teal-600" />
                      </div>
                      <span className="font-medium text-sm">Pleerity Support</span>
                    </div>
                    <p className="text-sm text-gray-700 whitespace-pre-wrap">
                      {previewResponse.response_text}
                    </p>
                  </div>
                </div>
              </div>

              {/* WhatsApp Preview */}
              <div>
                <p className="text-sm font-medium text-gray-600 mb-2 flex items-center gap-2">
                  <Phone className="h-4 w-4" /> WhatsApp Preview
                </p>
                <div className="bg-[#e5ddd5] rounded-lg p-4">
                  <div className="bg-[#dcf8c6] rounded-lg p-3 max-w-[80%] ml-auto">
                    <p className="text-sm text-gray-800 whitespace-pre-wrap">
                      {previewResponse.response_text.replace(/\*\*/g, '*')}
                    </p>
                    <p className="text-[10px] text-gray-500 text-right mt-1">
                      {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setPreviewDialogOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
