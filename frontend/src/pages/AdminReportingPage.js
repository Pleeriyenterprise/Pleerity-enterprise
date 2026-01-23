/**
 * Admin Reporting Dashboard
 * Export reports on-demand (CSV, Excel, PDF) and manage scheduled report delivery.
 */
import React, { useState, useEffect, useCallback } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import {
  FileText, Download, Calendar, Clock, Mail, Play, Trash2,
  Plus, RefreshCw, CheckCircle, XCircle, AlertCircle, Eye,
  FileSpreadsheet, FileJson, FilePdf, Filter, Search
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
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
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import client from '../api/client';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Format icons
const formatIcons = {
  csv: FileSpreadsheet,
  xlsx: FileSpreadsheet,
  pdf: FilePdf,
  json: FileJson,
};

// Stat Card component
function StatCard({ title, value, icon: Icon, color = 'blue', description }) {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    purple: 'bg-purple-100 text-purple-600',
    amber: 'bg-amber-100 text-amber-600',
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

export default function AdminReportingPage() {
  const [activeTab, setActiveTab] = useState('generate');
  const [loading, setLoading] = useState(false);
  const [reportTypes, setReportTypes] = useState([]);
  const [formats, setFormats] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [history, setHistory] = useState([]);
  const [previewData, setPreviewData] = useState(null);
  
  // Form state
  const [selectedType, setSelectedType] = useState('leads');
  const [selectedFormat, setSelectedFormat] = useState('csv');
  const [selectedPeriod, setSelectedPeriod] = useState('30d');
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');
  
  // Schedule dialog
  const [showScheduleDialog, setShowScheduleDialog] = useState(false);
  const [scheduleForm, setScheduleForm] = useState({
    name: '',
    report_type: 'leads',
    frequency: 'weekly',
    recipients: '',
    format: 'csv',
    enabled: true,
  });
  
  // Fetch report configuration
  const fetchConfig = useCallback(async () => {
    try {
      const { data } = await client.get('/admin/reports/types');
      setReportTypes(data.types || []);
      setFormats(data.formats || []);
      setPeriods(data.periods || []);
    } catch (error) {
      console.error('Failed to fetch report config:', error);
      toast.error('Failed to load report options');
    }
  }, []);
  
  // Fetch schedules
  const fetchSchedules = useCallback(async () => {
    try {
      const { data } = await client.get('/admin/reports/schedules');
      setSchedules(data.schedules || []);
    } catch (error) {
      console.error('Failed to fetch schedules:', error);
    }
  }, []);
  
  // Fetch executions
  const fetchExecutions = useCallback(async () => {
    try {
      const { data } = await client.get('/admin/reports/executions');
      setExecutions(data.executions || []);
    } catch (error) {
      console.error('Failed to fetch executions:', error);
    }
  }, []);
  
  // Fetch history
  const fetchHistory = useCallback(async () => {
    try {
      const { data } = await client.get('/admin/reports/history');
      setHistory(data.history || []);
    } catch (error) {
      console.error('Failed to fetch history:', error);
    }
  }, []);
  
  useEffect(() => {
    fetchConfig();
    fetchSchedules();
    fetchExecutions();
    fetchHistory();
  }, [fetchConfig, fetchSchedules, fetchExecutions, fetchHistory]);
  
  // Preview report
  const handlePreview = async () => {
    setLoading(true);
    try {
      let url = `/admin/reports/preview/${selectedType}?period=${selectedPeriod}&limit=20`;
      if (selectedPeriod === 'custom' && customStartDate && customEndDate) {
        url = `/admin/reports/preview/${selectedType}?start_date=${customStartDate}&end_date=${customEndDate}&limit=20`;
      }
      
      const { data } = await client.get(url);
      setPreviewData(data);
      toast.success(`Preview loaded: ${data.total_rows} total rows`);
    } catch (error) {
      console.error('Preview failed:', error);
      toast.error('Failed to load preview');
    } finally {
      setLoading(false);
    }
  };
  
  // Generate and download report
  const handleDownload = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('admin_token');
      
      let requestBody = {
        report_type: selectedType,
        format: selectedFormat,
        period: selectedPeriod,
        filters: {}
      };
      
      if (selectedPeriod === 'custom' && customStartDate && customEndDate) {
        requestBody.start_date = customStartDate;
        requestBody.end_date = customEndDate;
      }
      
      const response = await fetch(`${API_URL}/api/admin/reports/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(requestBody)
      });
      
      if (!response.ok) throw new Error('Download failed');
      
      const blob = await response.blob();
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `${selectedType}_report.${selectedFormat}`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename=(.+)/);
        if (match) filename = match[1];
      }
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success('Report downloaded successfully');
      fetchHistory();
    } catch (error) {
      console.error('Download failed:', error);
      toast.error('Failed to download report');
    } finally {
      setLoading(false);
    }
  };
  
  // Create schedule
  const handleCreateSchedule = async () => {
    try {
      const recipients = scheduleForm.recipients.split(',').map(e => e.trim()).filter(Boolean);
      if (recipients.length === 0) {
        toast.error('Please enter at least one recipient email');
        return;
      }
      
      await client.post('/admin/reports/schedules', {
        ...scheduleForm,
        recipients
      });
      
      toast.success('Schedule created successfully');
      setShowScheduleDialog(false);
      setScheduleForm({
        name: '',
        report_type: 'leads',
        frequency: 'weekly',
        recipients: '',
        format: 'csv',
        enabled: true,
      });
      fetchSchedules();
    } catch (error) {
      console.error('Failed to create schedule:', error);
      toast.error(error.response?.data?.detail || 'Failed to create schedule');
    }
  };
  
  // Toggle schedule
  const handleToggleSchedule = async (scheduleId) => {
    try {
      await client.put(`/admin/reports/schedules/${scheduleId}/toggle`);
      toast.success('Schedule updated');
      fetchSchedules();
    } catch (error) {
      console.error('Failed to toggle schedule:', error);
      toast.error('Failed to update schedule');
    }
  };
  
  // Run schedule now
  const handleRunNow = async (scheduleId) => {
    setLoading(true);
    try {
      const { data } = await client.post(`/admin/reports/schedules/${scheduleId}/run`);
      toast.success(`Report sent to ${data.recipients.join(', ')}`);
      fetchExecutions();
    } catch (error) {
      console.error('Failed to run schedule:', error);
      toast.error('Failed to run scheduled report');
    } finally {
      setLoading(false);
    }
  };
  
  // Delete schedule
  const handleDeleteSchedule = async (scheduleId) => {
    if (!window.confirm('Are you sure you want to delete this schedule?')) return;
    
    try {
      await client.delete(`/admin/reports/schedules/${scheduleId}`);
      toast.success('Schedule deleted');
      fetchSchedules();
    } catch (error) {
      console.error('Failed to delete schedule:', error);
      toast.error('Failed to delete schedule');
    }
  };
  
  return (
    <UnifiedAdminLayout>
      <div className="p-6 space-y-6" data-testid="admin-reporting-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Reporting</h1>
            <p className="text-gray-500">Generate and schedule business reports</p>
          </div>
          <Button 
            onClick={() => setShowScheduleDialog(true)}
            data-testid="create-schedule-btn"
          >
            <Plus className="h-4 w-4 mr-2" />
            New Schedule
          </Button>
        </div>
        
        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Report Types"
            value={reportTypes.length}
            icon={FileText}
            color="blue"
            description="Available reports"
          />
          <StatCard
            title="Active Schedules"
            value={schedules.filter(s => s.enabled).length}
            icon={Calendar}
            color="green"
            description={`${schedules.length} total`}
          />
          <StatCard
            title="Reports Sent"
            value={executions.length}
            icon={Mail}
            color="purple"
            description="This month"
          />
          <StatCard
            title="Exports"
            value={history.length}
            icon={Download}
            color="amber"
            description="Recent downloads"
          />
        </div>
        
        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="generate" data-testid="tab-generate">
              <Download className="h-4 w-4 mr-2" />
              Generate Report
            </TabsTrigger>
            <TabsTrigger value="schedules" data-testid="tab-schedules">
              <Calendar className="h-4 w-4 mr-2" />
              Schedules ({schedules.length})
            </TabsTrigger>
            <TabsTrigger value="history" data-testid="tab-history">
              <Clock className="h-4 w-4 mr-2" />
              History
            </TabsTrigger>
          </TabsList>
          
          {/* Generate Tab */}
          <TabsContent value="generate" className="mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Form */}
              <Card className="lg:col-span-1">
                <CardHeader>
                  <CardTitle>Export Settings</CardTitle>
                  <CardDescription>Configure your report</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label>Report Type</Label>
                    <Select value={selectedType} onValueChange={setSelectedType}>
                      <SelectTrigger data-testid="select-report-type">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {reportTypes.map(type => (
                          <SelectItem key={type.value} value={type.value}>
                            {type.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-gray-500 mt-1">
                      {reportTypes.find(t => t.value === selectedType)?.description}
                    </p>
                  </div>
                  
                  <div>
                    <Label>Format</Label>
                    <Select value={selectedFormat} onValueChange={setSelectedFormat}>
                      <SelectTrigger data-testid="select-format">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {formats.map(format => (
                          <SelectItem key={format.value} value={format.value}>
                            {format.label} - {format.description}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div>
                    <Label>Period</Label>
                    <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
                      <SelectTrigger data-testid="select-period">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {periods.map(period => (
                          <SelectItem key={period.value} value={period.value}>
                            {period.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  {selectedPeriod === 'custom' && (
                    <div className="space-y-2">
                      <div>
                        <Label>Start Date</Label>
                        <Input
                          type="date"
                          value={customStartDate}
                          onChange={e => setCustomStartDate(e.target.value)}
                          data-testid="input-start-date"
                        />
                      </div>
                      <div>
                        <Label>End Date</Label>
                        <Input
                          type="date"
                          value={customEndDate}
                          onChange={e => setCustomEndDate(e.target.value)}
                          data-testid="input-end-date"
                        />
                      </div>
                    </div>
                  )}
                  
                  <div className="flex gap-2 pt-4">
                    <Button
                      variant="outline"
                      onClick={handlePreview}
                      disabled={loading}
                      className="flex-1"
                      data-testid="preview-btn"
                    >
                      <Eye className="h-4 w-4 mr-2" />
                      Preview
                    </Button>
                    <Button
                      onClick={handleDownload}
                      disabled={loading}
                      className="flex-1"
                      data-testid="download-btn"
                    >
                      {loading ? (
                        <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Download className="h-4 w-4 mr-2" />
                      )}
                      Download
                    </Button>
                  </div>
                </CardContent>
              </Card>
              
              {/* Preview */}
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Preview</CardTitle>
                  <CardDescription>
                    {previewData
                      ? `Showing ${previewData.preview.length} of ${previewData.total_rows} rows`
                      : 'Click Preview to see sample data'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {previewData ? (
                    <div className="overflow-auto max-h-[500px]">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            {previewData.columns.map(col => (
                              <TableHead key={col} className="whitespace-nowrap">
                                {col}
                              </TableHead>
                            ))}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {previewData.preview.map((row, idx) => (
                            <TableRow key={idx}>
                              {previewData.columns.map(col => (
                                <TableCell key={col} className="whitespace-nowrap">
                                  {String(row[col] ?? '-')}
                                </TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-64 text-gray-400">
                      <div className="text-center">
                        <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                        <p>Select options and click Preview</p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>
          
          {/* Schedules Tab */}
          <TabsContent value="schedules" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Scheduled Reports</CardTitle>
                <CardDescription>Automated report delivery via email</CardDescription>
              </CardHeader>
              <CardContent>
                {schedules.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Frequency</TableHead>
                        <TableHead>Recipients</TableHead>
                        <TableHead>Format</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Next Run</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {schedules.map(schedule => {
                        const FormatIcon = formatIcons[schedule.format] || FileText;
                        return (
                          <TableRow key={schedule.schedule_id} data-testid={`schedule-row-${schedule.schedule_id}`}>
                            <TableCell className="font-medium">{schedule.name}</TableCell>
                            <TableCell>
                              <Badge variant="outline">
                                {reportTypes.find(t => t.value === schedule.report_type)?.label || schedule.report_type}
                              </Badge>
                            </TableCell>
                            <TableCell className="capitalize">{schedule.frequency}</TableCell>
                            <TableCell>
                              <div className="max-w-[200px] truncate" title={schedule.recipients.join(', ')}>
                                {schedule.recipients.join(', ')}
                              </div>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1">
                                <FormatIcon className="h-4 w-4 text-gray-500" />
                                <span className="uppercase text-xs">{schedule.format}</span>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant={schedule.enabled ? 'default' : 'secondary'}>
                                {schedule.enabled ? 'Active' : 'Paused'}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm text-gray-500">
                              {schedule.next_run
                                ? new Date(schedule.next_run).toLocaleDateString()
                                : '-'}
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex items-center justify-end gap-1">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleRunNow(schedule.schedule_id)}
                                  title="Run Now"
                                  data-testid={`run-now-${schedule.schedule_id}`}
                                >
                                  <Play className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleToggleSchedule(schedule.schedule_id)}
                                  title={schedule.enabled ? 'Pause' : 'Enable'}
                                >
                                  {schedule.enabled ? (
                                    <XCircle className="h-4 w-4 text-amber-500" />
                                  ) : (
                                    <CheckCircle className="h-4 w-4 text-green-500" />
                                  )}
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleDeleteSchedule(schedule.schedule_id)}
                                  title="Delete"
                                  data-testid={`delete-schedule-${schedule.schedule_id}`}
                                >
                                  <Trash2 className="h-4 w-4 text-red-500" />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <Calendar className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No scheduled reports yet</p>
                    <Button
                      variant="outline"
                      className="mt-4"
                      onClick={() => setShowScheduleDialog(true)}
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Create Schedule
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
            
            {/* Recent Executions */}
            {executions.length > 0 && (
              <Card className="mt-6">
                <CardHeader>
                  <CardTitle>Recent Executions</CardTitle>
                  <CardDescription>Scheduled report delivery history</CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Schedule</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Recipients</TableHead>
                        <TableHead>Rows</TableHead>
                        <TableHead>Trigger</TableHead>
                        <TableHead>Executed</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {executions.slice(0, 10).map(exec => (
                        <TableRow key={exec.execution_id}>
                          <TableCell className="font-medium">{exec.schedule_name}</TableCell>
                          <TableCell className="capitalize">{exec.report_type}</TableCell>
                          <TableCell>{exec.recipients?.length || 0}</TableCell>
                          <TableCell>{exec.row_count?.toLocaleString()}</TableCell>
                          <TableCell>
                            <Badge variant={exec.trigger_type === 'manual' ? 'outline' : 'secondary'}>
                              {exec.trigger_type}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm text-gray-500">
                            {new Date(exec.executed_at).toLocaleString()}
                          </TableCell>
                          <TableCell>
                            {exec.email_results?.every(r => r.status === 'sent') ? (
                              <CheckCircle className="h-4 w-4 text-green-500" />
                            ) : (
                              <AlertCircle className="h-4 w-4 text-amber-500" />
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            )}
          </TabsContent>
          
          {/* History Tab */}
          <TabsContent value="history" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Export History</CardTitle>
                <CardDescription>Recent on-demand report downloads</CardDescription>
              </CardHeader>
              <CardContent>
                {history.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Report ID</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Format</TableHead>
                        <TableHead>Rows</TableHead>
                        <TableHead>Period</TableHead>
                        <TableHead>Generated</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {history.map(log => (
                        <TableRow key={log.resource_id || log.audit_id}>
                          <TableCell className="font-mono text-xs">
                            {log.resource_id}
                          </TableCell>
                          <TableCell className="capitalize">
                            {log.metadata?.report_type}
                          </TableCell>
                          <TableCell className="uppercase text-xs">
                            {log.metadata?.format}
                          </TableCell>
                          <TableCell>{log.metadata?.row_count?.toLocaleString()}</TableCell>
                          <TableCell className="text-sm text-gray-500 max-w-[200px] truncate">
                            {log.metadata?.period}
                          </TableCell>
                          <TableCell className="text-sm text-gray-500">
                            {new Date(log.timestamp).toLocaleString()}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <Clock className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No export history yet</p>
                    <p className="text-sm mt-2">Download a report to see it here</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
        
        {/* Create Schedule Dialog */}
        <Dialog open={showScheduleDialog} onOpenChange={setShowScheduleDialog}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Create Scheduled Report</DialogTitle>
              <DialogDescription>
                Set up automated report delivery to your team
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div>
                <Label>Schedule Name</Label>
                <Input
                  placeholder="e.g., Weekly Leads Report"
                  value={scheduleForm.name}
                  onChange={e => setScheduleForm({ ...scheduleForm, name: e.target.value })}
                  data-testid="schedule-name-input"
                />
              </div>
              
              <div>
                <Label>Report Type</Label>
                <Select
                  value={scheduleForm.report_type}
                  onValueChange={v => setScheduleForm({ ...scheduleForm, report_type: v })}
                >
                  <SelectTrigger data-testid="schedule-type-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {reportTypes.map(type => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <Label>Frequency</Label>
                <Select
                  value={scheduleForm.frequency}
                  onValueChange={v => setScheduleForm({ ...scheduleForm, frequency: v })}
                >
                  <SelectTrigger data-testid="schedule-frequency-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">Daily (8:00 AM)</SelectItem>
                    <SelectItem value="weekly">Weekly (Monday 8:00 AM)</SelectItem>
                    <SelectItem value="monthly">Monthly (1st of month)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <Label>Format</Label>
                <Select
                  value={scheduleForm.format}
                  onValueChange={v => setScheduleForm({ ...scheduleForm, format: v })}
                >
                  <SelectTrigger data-testid="schedule-format-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {formats.map(format => (
                      <SelectItem key={format.value} value={format.value}>
                        {format.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <Label>Recipients</Label>
                <Input
                  placeholder="email1@example.com, email2@example.com"
                  value={scheduleForm.recipients}
                  onChange={e => setScheduleForm({ ...scheduleForm, recipients: e.target.value })}
                  data-testid="schedule-recipients-input"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Comma-separated email addresses
                </p>
              </div>
              
              <div className="flex items-center justify-between">
                <Label>Enabled</Label>
                <Switch
                  checked={scheduleForm.enabled}
                  onCheckedChange={v => setScheduleForm({ ...scheduleForm, enabled: v })}
                  data-testid="schedule-enabled-switch"
                />
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowScheduleDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateSchedule} data-testid="save-schedule-btn">
                Create Schedule
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </UnifiedAdminLayout>
  );
}
