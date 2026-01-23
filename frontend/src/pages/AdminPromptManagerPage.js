/**
 * Admin Prompt Manager Page
 * Enterprise-grade prompt management for AI document generation
 * 
 * Features:
 * - Prompt template CRUD
 * - Draft -> Tested -> Active lifecycle
 * - Prompt Playground for testing
 * - Version history and audit log
 * - Schema validation
 */
import React, { useState, useEffect, useCallback } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import {
  FileCode, Play, CheckCircle, XCircle, RefreshCw, Plus, Edit, Trash2,
  AlertTriangle, History, Activity, Rocket, Eye, Save, Code, Sparkles,
  TestTube, ArchiveIcon, Clock, User, ChevronRight, Search, Filter,
  Copy, Check
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle
} from '../components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import client from '../api/client';

// Status badge colors
const statusColors = {
  DRAFT: 'bg-gray-100 text-gray-700',
  TESTED: 'bg-blue-100 text-blue-700',
  ACTIVE: 'bg-green-100 text-green-700',
  DEPRECATED: 'bg-amber-100 text-amber-700',
  ARCHIVED: 'bg-red-100 text-red-700',
};

const testStatusColors = {
  PASSED: 'bg-green-100 text-green-700',
  FAILED: 'bg-red-100 text-red-700',
  PENDING: 'bg-gray-100 text-gray-700',
  RUNNING: 'bg-blue-100 text-blue-700',
};

// Stat Card component
function StatCard({ title, value, icon: Icon, color = 'blue', description }) {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    purple: 'bg-purple-100 text-purple-600',
    amber: 'bg-amber-100 text-amber-600',
    red: 'bg-red-100 text-red-600',
  };
  
  return (
    <Card data-testid={`stat-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
        <div className="mt-4">
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-gray-500">{title}</p>
          {description && <p className="text-xs text-gray-400 mt-1">{description}</p>}
        </div>
      </CardContent>
    </Card>
  );
}

export default function AdminPromptManagerPage() {
  const [activeTab, setActiveTab] = useState('templates');
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [auditLog, setAuditLog] = useState([]);
  const [serviceCodes, setServiceCodes] = useState([]);
  const [docTypes, setDocTypes] = useState([]);
  
  // Filters
  const [filters, setFilters] = useState({
    service_code: '',
    status: '',
    search: '',
  });
  
  // Dialogs
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [showTestDialog, setShowTestDialog] = useState(false);
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [showActivateDialog, setShowActivateDialog] = useState(false);
  
  // Selected template
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [editingTemplate, setEditingTemplate] = useState(null);
  
  // Template form
  const [templateForm, setTemplateForm] = useState({
    service_code: '',
    doc_type: '',
    name: '',
    description: '',
    system_prompt: '',
    user_prompt_template: '',
    temperature: 0.3,
    max_tokens: 4000,
    tags: '',
    output_schema: {
      schema_version: '1.0',
      root_type: 'object',
      strict_validation: true,
      fields: [],
    },
  });
  
  // Test form
  const [testForm, setTestForm] = useState({
    test_input_data: '{\n  "example_field": "example_value"\n}',
    temperature_override: null,
  });
  const [testResult, setTestResult] = useState(null);
  const [testRunning, setTestRunning] = useState(false);
  
  // Activation form
  const [activationReason, setActivationReason] = useState('');
  
  // Load data
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, templatesRes, auditRes, serviceCodesRes, docTypesRes] = await Promise.all([
        client.get('/admin/prompts/stats/overview'),
        client.get('/admin/prompts', {
          params: {
            service_code: filters.service_code || undefined,
            status: filters.status || undefined,
            search: filters.search || undefined,
            page_size: 50,
          }
        }),
        client.get('/admin/prompts/audit/log', { params: { limit: 30 } }),
        client.get('/admin/prompts/reference/service-codes'),
        client.get('/admin/prompts/reference/doc-types'),
      ]);
      
      setStats(statsRes.data);
      setTemplates(templatesRes.data.prompts || []);
      setAuditLog(auditRes.data.entries || []);
      setServiceCodes(serviceCodesRes.data.service_codes || []);
      setDocTypes(docTypesRes.data.doc_types || []);
    } catch (error) {
      console.error('Load error:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [filters]);
  
  useEffect(() => {
    loadData();
  }, [loadData]);
  
  // Reset template form
  const resetTemplateForm = () => {
    setTemplateForm({
      service_code: '',
      doc_type: '',
      name: '',
      description: '',
      system_prompt: '',
      user_prompt_template: 'Process the following input data:\n\n{{INPUT_DATA_JSON}}\n\nProvide your analysis as JSON.',
      temperature: 0.3,
      max_tokens: 4000,
      tags: '',
      output_schema: {
        schema_version: '1.0',
        root_type: 'object',
        strict_validation: true,
        fields: [],
      },
    });
    setEditingTemplate(null);
  };
  
  // Open create dialog
  const openCreateDialog = () => {
    resetTemplateForm();
    setShowTemplateDialog(true);
  };
  
  // Open edit dialog
  const openEditDialog = (template) => {
    setEditingTemplate(template);
    setTemplateForm({
      service_code: template.service_code,
      doc_type: template.doc_type,
      name: template.name,
      description: template.description || '',
      system_prompt: template.system_prompt,
      user_prompt_template: template.user_prompt_template,
      temperature: template.temperature,
      max_tokens: template.max_tokens,
      tags: (template.tags || []).join(', '),
      output_schema: template.output_schema || {
        schema_version: '1.0',
        root_type: 'object',
        strict_validation: true,
        fields: [],
      },
    });
    setShowTemplateDialog(true);
  };
  
  // Save template
  const handleSaveTemplate = async () => {
    if (!templateForm.name || !templateForm.service_code || !templateForm.doc_type) {
      toast.error('Please fill in all required fields');
      return;
    }
    
    if (!templateForm.user_prompt_template.includes('{{INPUT_DATA_JSON}}')) {
      toast.error('User prompt must contain {{INPUT_DATA_JSON}} placeholder');
      return;
    }
    
    setLoading(true);
    try {
      const payload = {
        ...templateForm,
        tags: templateForm.tags ? templateForm.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
      };
      
      if (editingTemplate) {
        await client.put(`/admin/prompts/${editingTemplate.template_id}`, payload);
        toast.success('Template updated');
      } else {
        await client.post('/admin/prompts', payload);
        toast.success('Template created');
      }
      
      setShowTemplateDialog(false);
      resetTemplateForm();
      loadData();
    } catch (error) {
      console.error('Save error:', error);
      toast.error(error.response?.data?.detail || 'Failed to save template');
    } finally {
      setLoading(false);
    }
  };
  
  // Open test dialog
  const openTestDialog = (template) => {
    setSelectedTemplate(template);
    setTestForm({
      test_input_data: '{\n  "example_field": "example_value"\n}',
      temperature_override: null,
    });
    setTestResult(null);
    setShowTestDialog(true);
  };
  
  // Run test
  const handleRunTest = async () => {
    if (!selectedTemplate) return;
    
    let parsedInput;
    try {
      parsedInput = JSON.parse(testForm.test_input_data);
    } catch (e) {
      toast.error('Invalid JSON in test input');
      return;
    }
    
    setTestRunning(true);
    setTestResult(null);
    
    try {
      const res = await client.post('/admin/prompts/test', {
        template_id: selectedTemplate.template_id,
        test_input_data: parsedInput,
        temperature_override: testForm.temperature_override,
      });
      
      setTestResult(res.data);
      
      if (res.data.status === 'PASSED') {
        toast.success('Test passed! Schema validation successful.');
      } else {
        toast.warning('Test completed with issues. Check validation errors.');
      }
      
      // Reload to get updated test status
      loadData();
    } catch (error) {
      console.error('Test error:', error);
      toast.error(error.response?.data?.detail || 'Test execution failed');
    } finally {
      setTestRunning(false);
    }
  };
  
  // Mark as tested
  const handleMarkTested = async (template) => {
    if (template.last_test_status !== 'PASSED') {
      toast.error('Template must have a passing test first');
      return;
    }
    
    try {
      await client.post(`/admin/prompts/${template.template_id}/mark-tested`);
      toast.success('Template marked as TESTED');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to mark as tested');
    }
  };
  
  // Open activation dialog
  const openActivateDialog = (template) => {
    setSelectedTemplate(template);
    setActivationReason('');
    setShowActivateDialog(true);
  };
  
  // Activate template
  const handleActivate = async () => {
    if (!selectedTemplate || activationReason.length < 10) {
      toast.error('Please provide a detailed activation reason (min 10 characters)');
      return;
    }
    
    try {
      await client.post(`/admin/prompts/${selectedTemplate.template_id}/activate`, {
        template_id: selectedTemplate.template_id,
        activation_reason: activationReason,
      });
      
      toast.success('Template activated! Previous version deprecated.');
      setShowActivateDialog(false);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Activation failed');
    }
  };
  
  // Archive template
  const handleArchive = async (template) => {
    if (template.status === 'ACTIVE') {
      toast.error('Cannot archive active template. Activate a new version first.');
      return;
    }
    
    if (!window.confirm('Archive this template? It will be hidden from normal views.')) {
      return;
    }
    
    try {
      await client.delete(`/api/admin/prompts/${template.template_id}`);
      toast.success('Template archived');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Archive failed');
    }
  };
  
  // View template details
  const openDetailDialog = (template) => {
    setSelectedTemplate(template);
    setShowDetailDialog(true);
  };
  
  // Add schema field
  const addSchemaField = () => {
    setTemplateForm(prev => ({
      ...prev,
      output_schema: {
        ...prev.output_schema,
        fields: [
          ...prev.output_schema.fields,
          { field_name: '', field_type: 'string', description: '', required: true },
        ],
      },
    }));
  };
  
  // Update schema field
  const updateSchemaField = (index, updates) => {
    setTemplateForm(prev => ({
      ...prev,
      output_schema: {
        ...prev.output_schema,
        fields: prev.output_schema.fields.map((f, i) => 
          i === index ? { ...f, ...updates } : f
        ),
      },
    }));
  };
  
  // Remove schema field
  const removeSchemaField = (index) => {
    setTemplateForm(prev => ({
      ...prev,
      output_schema: {
        ...prev.output_schema,
        fields: prev.output_schema.fields.filter((_, i) => i !== index),
      },
    }));
  };
  
  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
  };
  
  return (
    <UnifiedAdminLayout>
      <div className="space-y-6" data-testid="prompt-manager-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Prompt Manager</h1>
            <p className="text-sm text-gray-500 mt-1">
              Manage AI document generation prompts with version control and testing
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadData}
              disabled={loading}
              data-testid="refresh-btn"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button onClick={openCreateDialog} data-testid="create-prompt-btn">
              <Plus className="h-4 w-4 mr-2" />
              New Prompt
            </Button>
          </div>
        </div>
        
        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <StatCard
              title="Total Templates"
              value={stats.total_templates}
              icon={FileCode}
              color="blue"
            />
            <StatCard
              title="Active"
              value={stats.by_status?.active || 0}
              icon={CheckCircle}
              color="green"
            />
            <StatCard
              title="Draft"
              value={stats.by_status?.draft || 0}
              icon={Edit}
              color="amber"
            />
            <StatCard
              title="Tested"
              value={stats.by_status?.tested || 0}
              icon={TestTube}
              color="purple"
            />
            <StatCard
              title="Tests (24h)"
              value={stats.tests_last_24h || 0}
              icon={Play}
              color="blue"
            />
          </div>
        )}
        
        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-3 max-w-md">
            <TabsTrigger value="templates" data-testid="templates-tab">
              <FileCode className="h-4 w-4 mr-2" />
              Templates
            </TabsTrigger>
            <TabsTrigger value="audit" data-testid="audit-tab">
              <History className="h-4 w-4 mr-2" />
              Audit Log
            </TabsTrigger>
            <TabsTrigger value="guide" data-testid="guide-tab">
              <Sparkles className="h-4 w-4 mr-2" />
              Guide
            </TabsTrigger>
          </TabsList>
          
          {/* Templates Tab */}
          <TabsContent value="templates" className="space-y-4">
            {/* Filters */}
            <Card>
              <CardContent className="p-4">
                <div className="flex flex-wrap gap-4 items-end">
                  <div className="flex-1 min-w-[200px]">
                    <Label className="text-xs">Search</Label>
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                      <Input
                        placeholder="Search by name..."
                        className="pl-10"
                        value={filters.search}
                        onChange={(e) => setFilters(f => ({ ...f, search: e.target.value }))}
                        data-testid="search-input"
                      />
                    </div>
                  </div>
                  <div className="w-48">
                    <Label className="text-xs">Service Code</Label>
                    <Select
                      value={filters.service_code}
                      onValueChange={(v) => setFilters(f => ({ ...f, service_code: v === 'all' ? '' : v }))}
                    >
                      <SelectTrigger data-testid="service-filter">
                        <SelectValue placeholder="All Services" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Services</SelectItem>
                        {serviceCodes.map(sc => (
                          <SelectItem key={sc.code} value={sc.code}>{sc.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="w-40">
                    <Label className="text-xs">Status</Label>
                    <Select
                      value={filters.status}
                      onValueChange={(v) => setFilters(f => ({ ...f, status: v === 'all' ? '' : v }))}
                    >
                      <SelectTrigger data-testid="status-filter">
                        <SelectValue placeholder="All Status" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Status</SelectItem>
                        <SelectItem value="DRAFT">Draft</SelectItem>
                        <SelectItem value="TESTED">Tested</SelectItem>
                        <SelectItem value="ACTIVE">Active</SelectItem>
                        <SelectItem value="DEPRECATED">Deprecated</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            {/* Templates Table */}
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Service</TableHead>
                      <TableHead>Version</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Last Test</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {templates.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={7} className="text-center py-8 text-gray-500">
                          No prompt templates found. Create your first one!
                        </TableCell>
                      </TableRow>
                    ) : (
                      templates.map(template => (
                        <TableRow key={template.template_id} data-testid={`template-row-${template.template_id}`}>
                          <TableCell>
                            <div>
                              <p className="font-medium text-gray-900">{template.name}</p>
                              <p className="text-xs text-gray-500 truncate max-w-[200px]">
                                {template.description || 'No description'}
                              </p>
                            </div>
                          </TableCell>
                          <TableCell>
                            <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                              {template.service_code}
                            </code>
                          </TableCell>
                          <TableCell>
                            <span className="text-sm">v{template.version}</span>
                          </TableCell>
                          <TableCell>
                            <Badge className={statusColors[template.status] || ''}>
                              {template.status}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {template.last_test_status ? (
                              <Badge className={testStatusColors[template.last_test_status] || ''}>
                                {template.last_test_status}
                              </Badge>
                            ) : (
                              <span className="text-xs text-gray-400">Not tested</span>
                            )}
                          </TableCell>
                          <TableCell className="text-xs text-gray-500">
                            {formatDate(template.updated_at || template.created_at)}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => openDetailDialog(template)}
                                title="View Details"
                                data-testid={`view-btn-${template.template_id}`}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => openTestDialog(template)}
                                title="Test in Playground"
                                data-testid={`test-btn-${template.template_id}`}
                              >
                                <Play className="h-4 w-4" />
                              </Button>
                              {template.status === 'DRAFT' && (
                                <>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => openEditDialog(template)}
                                    title="Edit"
                                  >
                                    <Edit className="h-4 w-4" />
                                  </Button>
                                  {template.last_test_status === 'PASSED' && (
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => handleMarkTested(template)}
                                      title="Mark as Tested"
                                      className="text-blue-600"
                                    >
                                      <CheckCircle className="h-4 w-4" />
                                    </Button>
                                  )}
                                </>
                              )}
                              {template.status === 'TESTED' && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => openActivateDialog(template)}
                                  title="Activate"
                                  className="text-green-600"
                                  data-testid={`activate-btn-${template.template_id}`}
                                >
                                  <Rocket className="h-4 w-4" />
                                </Button>
                              )}
                              {template.status !== 'ACTIVE' && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleArchive(template)}
                                  title="Archive"
                                  className="text-red-600"
                                >
                                  <ArchiveIcon className="h-4 w-4" />
                                </Button>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
          
          {/* Audit Log Tab */}
          <TabsContent value="audit" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Audit Trail</CardTitle>
                <CardDescription>
                  Complete history of all prompt changes, tests, and activations
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[500px]">
                  <div className="space-y-4">
                    {auditLog.length === 0 ? (
                      <p className="text-center text-gray-500 py-8">No audit entries yet</p>
                    ) : (
                      auditLog.map((entry, idx) => (
                        <div
                          key={entry.audit_id || idx}
                          className="flex items-start gap-4 p-4 bg-gray-50 rounded-lg"
                          data-testid={`audit-entry-${idx}`}
                        >
                          <div className={`p-2 rounded-full ${
                            entry.action === 'ACTIVATED' ? 'bg-green-100 text-green-600' :
                            entry.action === 'CREATED' ? 'bg-blue-100 text-blue-600' :
                            entry.action === 'TEST_PASSED' ? 'bg-green-100 text-green-600' :
                            entry.action === 'TEST_FAILED' ? 'bg-red-100 text-red-600' :
                            'bg-gray-100 text-gray-600'
                          }`}>
                            <Activity className="h-4 w-4" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline">{entry.action}</Badge>
                              <span className="text-xs text-gray-500">v{entry.version}</span>
                            </div>
                            <p className="text-sm text-gray-700 mt-1">{entry.changes_summary}</p>
                            <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                              <span className="flex items-center gap-1">
                                <User className="h-3 w-3" />
                                {entry.performed_by}
                              </span>
                              <span className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {formatDate(entry.performed_at)}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </TabsContent>
          
          {/* Guide Tab */}
          <TabsContent value="guide" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Prompt Manager Guide</CardTitle>
                <CardDescription>
                  How to use the enterprise prompt management system
                </CardDescription>
              </CardHeader>
              <CardContent className="prose prose-sm max-w-none">
                <h3>Lifecycle: Draft → Tested → Active</h3>
                <ol>
                  <li><strong>Draft</strong>: Create and edit your prompt template freely</li>
                  <li><strong>Test</strong>: Use the Playground to test with sample data</li>
                  <li><strong>Mark as Tested</strong>: Once tests pass schema validation</li>
                  <li><strong>Activate</strong>: Deploy to production (previous version becomes deprecated)</li>
                </ol>
                
                <h3>The <code>{'{{INPUT_DATA_JSON}}'}</code> Pattern</h3>
                <p>
                  All prompts use a single injection point: <code>{'{{INPUT_DATA_JSON}}'}</code>.
                  This ensures safe, controlled data injection without scattered placeholders.
                </p>
                <pre className="bg-gray-100 p-4 rounded-lg overflow-x-auto">
{`// Example user prompt template:
Analyze this business data:

{{INPUT_DATA_JSON}}

Provide workflow recommendations in JSON format.`}
                </pre>
                
                <h3>Schema Validation</h3>
                <p>
                  Define output schema fields to validate LLM responses. 
                  Tests must pass schema validation before a template can be activated.
                </p>
                
                <h3>Version Control</h3>
                <ul>
                  <li>Each prompt change creates a new version (except for DRAFT edits)</li>
                  <li>Active prompts are never modified - always deprecated</li>
                  <li>Generated documents store <code>prompt_version_used</code> permanently</li>
                </ul>
                
                <h3>Audit Trail</h3>
                <p>
                  Every action is logged: who, what, when, and test evidence.
                  This ensures compliance and enables troubleshooting.
                </p>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
        
        {/* Create/Edit Template Dialog */}
        <Dialog open={showTemplateDialog} onOpenChange={setShowTemplateDialog}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {editingTemplate ? 'Edit Prompt Template' : 'Create New Prompt Template'}
              </DialogTitle>
              <DialogDescription>
                {editingTemplate 
                  ? 'Update the template configuration. Non-draft templates will create a new version.'
                  : 'Create a new prompt template for AI document generation.'}
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-6 py-4">
              {/* Basic Info */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Service Code *</Label>
                  <Select
                    value={templateForm.service_code}
                    onValueChange={(v) => setTemplateForm(f => ({ ...f, service_code: v }))}
                  >
                    <SelectTrigger data-testid="form-service-code">
                      <SelectValue placeholder="Select service" />
                    </SelectTrigger>
                    <SelectContent>
                      {serviceCodes.map(sc => (
                        <SelectItem key={sc.code} value={sc.code}>{sc.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Document Type *</Label>
                  <Select
                    value={templateForm.doc_type}
                    onValueChange={(v) => setTemplateForm(f => ({ ...f, doc_type: v }))}
                  >
                    <SelectTrigger data-testid="form-doc-type">
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      {docTypes.map(dt => (
                        <SelectItem key={dt.code} value={dt.code}>{dt.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div className="space-y-2">
                <Label>Name *</Label>
                <Input
                  value={templateForm.name}
                  onChange={(e) => setTemplateForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g., Workflow Blueprint Generator v2"
                  data-testid="form-name"
                />
              </div>
              
              <div className="space-y-2">
                <Label>Description</Label>
                <Input
                  value={templateForm.description}
                  onChange={(e) => setTemplateForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Brief description of this prompt's purpose"
                />
              </div>
              
              {/* System Prompt */}
              <div className="space-y-2">
                <Label>System Prompt *</Label>
                <Textarea
                  value={templateForm.system_prompt}
                  onChange={(e) => setTemplateForm(f => ({ ...f, system_prompt: e.target.value }))}
                  placeholder="Define the AI's role and behavior..."
                  className="min-h-[120px] font-mono text-sm"
                  data-testid="form-system-prompt"
                />
              </div>
              
              {/* User Prompt Template */}
              <div className="space-y-2">
                <Label>
                  User Prompt Template *
                  <span className="text-xs text-gray-500 ml-2">
                    Must contain {'{{INPUT_DATA_JSON}}'}
                  </span>
                </Label>
                <Textarea
                  value={templateForm.user_prompt_template}
                  onChange={(e) => setTemplateForm(f => ({ ...f, user_prompt_template: e.target.value }))}
                  placeholder="Process the following input:\n\n{{INPUT_DATA_JSON}}\n\nProvide output as JSON."
                  className="min-h-[150px] font-mono text-sm"
                  data-testid="form-user-prompt"
                />
                {!templateForm.user_prompt_template.includes('{{INPUT_DATA_JSON}}') && (
                  <p className="text-xs text-red-500 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    Missing required {'{{INPUT_DATA_JSON}}'} placeholder
                  </p>
                )}
              </div>
              
              {/* LLM Configuration */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Temperature</Label>
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    value={templateForm.temperature}
                    onChange={(e) => setTemplateForm(f => ({ ...f, temperature: parseFloat(e.target.value) }))}
                  />
                  <p className="text-xs text-gray-500">0 = deterministic, 2 = creative</p>
                </div>
                <div className="space-y-2">
                  <Label>Max Tokens</Label>
                  <Input
                    type="number"
                    min="100"
                    max="32000"
                    value={templateForm.max_tokens}
                    onChange={(e) => setTemplateForm(f => ({ ...f, max_tokens: parseInt(e.target.value) }))}
                  />
                </div>
              </div>
              
              {/* Tags */}
              <div className="space-y-2">
                <Label>Tags</Label>
                <Input
                  value={templateForm.tags}
                  onChange={(e) => setTemplateForm(f => ({ ...f, tags: e.target.value }))}
                  placeholder="workflow, automation, v2 (comma-separated)"
                />
              </div>
              
              {/* Output Schema */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Output Schema Fields</Label>
                  <Button variant="outline" size="sm" onClick={addSchemaField}>
                    <Plus className="h-3 w-3 mr-1" />
                    Add Field
                  </Button>
                </div>
                <div className="space-y-2">
                  {templateForm.output_schema.fields.map((field, idx) => (
                    <div key={idx} className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
                      <Input
                        placeholder="field_name"
                        className="flex-1"
                        value={field.field_name}
                        onChange={(e) => updateSchemaField(idx, { field_name: e.target.value })}
                      />
                      <Select
                        value={field.field_type}
                        onValueChange={(v) => updateSchemaField(idx, { field_type: v })}
                      >
                        <SelectTrigger className="w-28">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="string">string</SelectItem>
                          <SelectItem value="number">number</SelectItem>
                          <SelectItem value="boolean">boolean</SelectItem>
                          <SelectItem value="array">array</SelectItem>
                          <SelectItem value="object">object</SelectItem>
                        </SelectContent>
                      </Select>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeSchemaField(idx)}
                        className="text-red-500"
                      >
                        <XCircle className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                  {templateForm.output_schema.fields.length === 0 && (
                    <p className="text-sm text-gray-500 text-center py-4">
                      No schema fields defined. Add fields to validate LLM output.
                    </p>
                  )}
                </div>
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowTemplateDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleSaveTemplate} disabled={loading} data-testid="save-template-btn">
                {loading ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                {editingTemplate ? 'Update' : 'Create'} Template
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Test Dialog (Prompt Playground) */}
        <Dialog open={showTestDialog} onOpenChange={setShowTestDialog}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <TestTube className="h-5 w-5" />
                Prompt Playground
              </DialogTitle>
              <DialogDescription>
                Test &quot;{selectedTemplate?.name}&quot; with sample input data
              </DialogDescription>
            </DialogHeader>
            
            <div className="grid grid-cols-2 gap-6 py-4">
              {/* Input Side */}
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Test Input Data (JSON)</Label>
                  <Textarea
                    value={testForm.test_input_data}
                    onChange={(e) => setTestForm(f => ({ ...f, test_input_data: e.target.value }))}
                    placeholder='{"field": "value"}'
                    className="min-h-[300px] font-mono text-sm"
                    data-testid="test-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Temperature Override (optional)</Label>
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    placeholder="Use template default"
                    value={testForm.temperature_override || ''}
                    onChange={(e) => setTestForm(f => ({ 
                      ...f, 
                      temperature_override: e.target.value ? parseFloat(e.target.value) : null 
                    }))}
                  />
                </div>
                <Button 
                  onClick={handleRunTest} 
                  disabled={testRunning} 
                  className="w-full"
                  data-testid="run-test-btn"
                >
                  {testRunning ? (
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4 mr-2" />
                  )}
                  Run Test
                </Button>
              </div>
              
              {/* Output Side */}
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Test Result</Label>
                  {testResult ? (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <Badge className={testStatusColors[testResult.status] || ''}>
                          {testResult.status}
                        </Badge>
                        <span className="text-xs text-gray-500">
                          {testResult.execution_time_ms}ms
                        </span>
                      </div>
                      
                      {testResult.schema_validation_passed ? (
                        <div className="flex items-center gap-2 text-green-600 text-sm">
                          <CheckCircle className="h-4 w-4" />
                          Schema validation passed
                        </div>
                      ) : (
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 text-red-600 text-sm">
                            <XCircle className="h-4 w-4" />
                            Schema validation failed
                          </div>
                          {testResult.schema_validation_errors?.length > 0 && (
                            <ul className="text-xs text-red-500 list-disc pl-5">
                              {testResult.schema_validation_errors.map((err, i) => (
                                <li key={i}>{err}</li>
                              ))}
                            </ul>
                          )}
                        </div>
                      )}
                      
                      <div className="space-y-2">
                        <Label className="text-xs">Parsed Output</Label>
                        <ScrollArea className="h-[250px] border rounded-lg p-3">
                          <pre className="text-xs font-mono whitespace-pre-wrap">
                            {testResult.parsed_output 
                              ? JSON.stringify(testResult.parsed_output, null, 2)
                              : testResult.raw_output || 'No output'}
                          </pre>
                        </ScrollArea>
                      </div>
                    </div>
                  ) : (
                    <div className="h-[350px] border rounded-lg flex items-center justify-center text-gray-400">
                      <div className="text-center">
                        <TestTube className="h-8 w-8 mx-auto mb-2 opacity-50" />
                        <p className="text-sm">Run a test to see results</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </DialogContent>
        </Dialog>
        
        {/* Detail Dialog */}
        <Dialog open={showDetailDialog} onOpenChange={setShowDetailDialog}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{selectedTemplate?.name}</DialogTitle>
              <DialogDescription>
                Template details and configuration
              </DialogDescription>
            </DialogHeader>
            
            {selectedTemplate && (
              <div className="space-y-4 py-4">
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label className="text-xs text-gray-500">Status</Label>
                    <Badge className={statusColors[selectedTemplate.status] || ''}>
                      {selectedTemplate.status}
                    </Badge>
                  </div>
                  <div>
                    <Label className="text-xs text-gray-500">Version</Label>
                    <p className="font-medium">v{selectedTemplate.version}</p>
                  </div>
                  <div>
                    <Label className="text-xs text-gray-500">Service</Label>
                    <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                      {selectedTemplate.service_code}
                    </code>
                  </div>
                </div>
                
                <div>
                  <Label className="text-xs text-gray-500">System Prompt</Label>
                  <ScrollArea className="h-32 border rounded-lg p-3 mt-1">
                    <pre className="text-xs font-mono whitespace-pre-wrap">
                      {selectedTemplate.system_prompt}
                    </pre>
                  </ScrollArea>
                </div>
                
                <div>
                  <Label className="text-xs text-gray-500">User Prompt Template</Label>
                  <ScrollArea className="h-32 border rounded-lg p-3 mt-1">
                    <pre className="text-xs font-mono whitespace-pre-wrap">
                      {selectedTemplate.user_prompt_template}
                    </pre>
                  </ScrollArea>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs text-gray-500">Temperature</Label>
                    <p className="font-medium">{selectedTemplate.temperature}</p>
                  </div>
                  <div>
                    <Label className="text-xs text-gray-500">Max Tokens</Label>
                    <p className="font-medium">{selectedTemplate.max_tokens}</p>
                  </div>
                </div>
                
                <div>
                  <Label className="text-xs text-gray-500">Output Schema</Label>
                  <ScrollArea className="h-32 border rounded-lg p-3 mt-1">
                    <pre className="text-xs font-mono whitespace-pre-wrap">
                      {JSON.stringify(selectedTemplate.output_schema, null, 2)}
                    </pre>
                  </ScrollArea>
                </div>
                
                <div className="grid grid-cols-2 gap-4 text-sm text-gray-500">
                  <div>
                    <Label className="text-xs text-gray-400">Created</Label>
                    <p>{formatDate(selectedTemplate.created_at)} by {selectedTemplate.created_by}</p>
                  </div>
                  {selectedTemplate.activated_at && (
                    <div>
                      <Label className="text-xs text-gray-400">Activated</Label>
                      <p>{formatDate(selectedTemplate.activated_at)} by {selectedTemplate.activated_by}</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
        
        {/* Activate Dialog */}
        <Dialog open={showActivateDialog} onOpenChange={setShowActivateDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Rocket className="h-5 w-5 text-green-600" />
                Activate Prompt Template
              </DialogTitle>
              <DialogDescription>
                This will deploy the template to production. Any existing active version will be deprecated.
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-amber-800">
                    <p className="font-medium">Important</p>
                    <ul className="list-disc pl-4 mt-1 space-y-1">
                      <li>This action cannot be undone</li>
                      <li>The current active version will be deprecated</li>
                      <li>All new document generations will use this version</li>
                    </ul>
                  </div>
                </div>
              </div>
              
              <div className="space-y-2">
                <Label>Activation Reason *</Label>
                <Textarea
                  value={activationReason}
                  onChange={(e) => setActivationReason(e.target.value)}
                  placeholder="Describe why you're activating this version (min 10 characters)..."
                  className="min-h-[100px]"
                  data-testid="activation-reason"
                />
                <p className="text-xs text-gray-500">
                  This will be recorded in the audit log for compliance purposes.
                </p>
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowActivateDialog(false)}>
                Cancel
              </Button>
              <Button 
                onClick={handleActivate} 
                disabled={activationReason.length < 10}
                className="bg-green-600 hover:bg-green-700"
                data-testid="confirm-activate-btn"
              >
                <Rocket className="h-4 w-4 mr-2" />
                Activate Now
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </UnifiedAdminLayout>
  );
}
