/**
 * Admin Cookie Consent Dashboard
 * 
 * Enterprise-grade consent analytics and logs for GDPR compliance.
 * Route: /admin/privacy/consent
 * Access: ROLE_ADMIN only
 */
import React, { useState, useEffect, useCallback } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import api from '../api/client';
import {
  Cookie,
  Users,
  CheckCircle2,
  XCircle,
  Settings,
  Download,
  RefreshCw,
  Search,
  Filter,
  Eye,
  Copy,
  Calendar,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Target,
  ChevronDown,
  FileText,
  Shield,
} from 'lucide-react';
import { cn } from '../lib/utils';

// Date range presets
const DATE_PRESETS = [
  { value: 'today', label: 'Today', days: 0 },
  { value: '7d', label: 'Last 7 Days', days: 7 },
  { value: '30d', label: 'Last 30 Days', days: 30 },
  { value: '90d', label: 'Last 90 Days', days: 90 },
];

// Action badge colors
const ACTION_COLORS = {
  ACCEPT_ALL: 'bg-green-100 text-green-800',
  REJECT_NON_ESSENTIAL: 'bg-red-100 text-red-800',
  CUSTOM: 'bg-blue-100 text-blue-800',
  WITHDRAW: 'bg-orange-100 text-orange-800',
  UNKNOWN: 'bg-gray-100 text-gray-800',
};

export default function AdminConsentDashboard() {
  // State
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  
  // Filters
  const [dateRange, setDateRange] = useState('30d');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [actionFilter, setActionFilter] = useState('all');
  const [marketingFilter, setMarketingFilter] = useState('any');
  const [analyticsFilter, setAnalyticsFilter] = useState('any');
  const [userTypeFilter, setUserTypeFilter] = useState('any');
  const [searchCrn, setSearchCrn] = useState('');
  const [searchEmail, setSearchEmail] = useState('');
  const [searchSession, setSearchSession] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  
  // Detail drawer
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailData, setDetailData] = useState(null);
  
  // Trend chart metric
  const [trendMetric, setTrendMetric] = useState('sessions');

  // Calculate date range
  const getDateRange = useCallback(() => {
    const to = new Date();
    let from = new Date();
    
    if (dateRange === 'custom') {
      return { from: fromDate, to: toDate };
    }
    
    const preset = DATE_PRESETS.find(p => p.value === dateRange);
    if (preset) {
      from.setDate(from.getDate() - preset.days);
    }
    
    return {
      from: from.toISOString().split('T')[0],
      to: to.toISOString().split('T')[0],
    };
  }, [dateRange, fromDate, toDate]);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const { from, to } = getDateRange();
      const response = await api.get('/admin/consent/stats', {
        params: { from, to },
      });
      setStats(response.data);
    } catch (error) {
      toast.error('Failed to load consent statistics');
      console.error(error);
    }
  }, [getDateRange]);

  // Fetch logs
  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const { from, to } = getDateRange();
      
      const params = {
        from,
        to,
        page,
        page_size: pageSize,
      };
      
      if (actionFilter !== 'all') params.action_taken = actionFilter;
      if (marketingFilter !== 'any') params.marketing = marketingFilter;
      if (analyticsFilter !== 'any') params.analytics = analyticsFilter;
      if (userTypeFilter !== 'any') params.user_type = userTypeFilter;
      if (searchCrn) params.crn = searchCrn;
      if (searchEmail) params.email = searchEmail;
      if (searchSession) params.session_id = searchSession;
      
      const response = await api.get('/admin/consent/logs', { params });
      setLogs(response.data.rows);
      setTotal(response.data.total);
    } catch (error) {
      toast.error('Failed to load consent logs');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [getDateRange, page, pageSize, actionFilter, marketingFilter, analyticsFilter, userTypeFilter, searchCrn, searchEmail, searchSession]);

  // Fetch detail
  const fetchDetail = async (eventId) => {
    setSelectedRecord(eventId);
    setDetailLoading(true);
    try {
      const response = await api.get(`/admin/consent/logs/${eventId}`);
      setDetailData(response.data);
    } catch (error) {
      toast.error('Failed to load consent details');
      console.error(error);
    } finally {
      setDetailLoading(false);
    }
  };

  // Export handlers
  const handleExportCSV = async () => {
    try {
      const { from, to } = getDateRange();
      window.open(`${process.env.REACT_APP_BACKEND_URL}/api/admin/consent/export.csv?from=${from}&to=${to}`, '_blank');
    } catch (error) {
      toast.error('Export failed');
    }
  };

  const handleExportPDF = async () => {
    try {
      const { from, to } = getDateRange();
      window.open(`${process.env.REACT_APP_BACKEND_URL}/api/admin/consent/export.pdf?from=${from}&to=${to}`, '_blank');
    } catch (error) {
      toast.error('Export failed');
    }
  };

  // Load data on mount and filter changes
  useEffect(() => {
    fetchStats();
    fetchLogs();
  }, [fetchStats, fetchLogs]);

  // Copy to clipboard
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  // Format timestamp for UK timezone
  const formatTimestamp = (iso) => {
    if (!iso) return '-';
    try {
      return new Date(iso).toLocaleString('en-GB', {
        timeZone: 'Europe/London',
        dateStyle: 'short',
        timeStyle: 'short',
      });
    } catch {
      return iso;
    }
  };

  // Calculate percentages
  const calcPercent = (value, total) => {
    if (!total || total === 0) return '0%';
    return `${((value / total) * 100).toFixed(1)}%`;
  };

  const totalActions = stats?.kpis?.accept_all_count + stats?.kpis?.reject_count + stats?.kpis?.custom_count || 0;

  return (
    <UnifiedAdminLayout>
      <div className="space-y-6" data-testid="admin-consent-dashboard">
        {/* Header */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-midnight-blue flex items-center gap-2">
              <Cookie className="w-7 h-7 text-teal-600" />
              Cookie Consent
            </h1>
            <p className="text-gray-500 mt-1">
              Evidence-grade consent analytics and logs for GDPR and outreach safety.
            </p>
          </div>
          
          <div className="flex flex-wrap items-center gap-2">
            {/* Date Range */}
            <Select value={dateRange} onValueChange={setDateRange}>
              <SelectTrigger className="w-40">
                <Calendar className="w-4 h-4 mr-2" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DATE_PRESETS.map(preset => (
                  <SelectItem key={preset.value} value={preset.value}>
                    {preset.label}
                  </SelectItem>
                ))}
                <SelectItem value="custom">Custom Range</SelectItem>
              </SelectContent>
            </Select>
            
            {/* Export Dropdown */}
            <Select onValueChange={(v) => v === 'csv' ? handleExportCSV() : handleExportPDF()}>
              <SelectTrigger className="w-36">
                <Download className="w-4 h-4 mr-2" />
                <SelectValue placeholder="Export" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="csv">Export CSV</SelectItem>
                <SelectItem value="pdf">Export PDF</SelectItem>
              </SelectContent>
            </Select>
            
            <Button 
              variant="outline" 
              onClick={() => { fetchStats(); fetchLogs(); }}
              disabled={loading}
            >
              <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
              Refresh
            </Button>
            
            <Badge variant="outline" className="text-gray-500">
              Retention: 24 months
            </Badge>
          </div>
        </div>

        {/* KPI Cards Row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Card 
            className="cursor-pointer hover:border-teal-300 transition-colors"
            onClick={() => setActionFilter('all')}
          >
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <Users className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats?.kpis?.total_sessions_shown || 0}</p>
                  <p className="text-xs text-gray-500">Total Visitors</p>
                  <p className="text-xs text-gray-400">unique sessions</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card 
            className={cn("cursor-pointer hover:border-green-300 transition-colors", actionFilter === 'ACCEPT_ALL' && "border-green-500")}
            onClick={() => setActionFilter(actionFilter === 'ACCEPT_ALL' ? 'all' : 'ACCEPT_ALL')}
          >
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 rounded-lg">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">
                    {stats?.kpis?.accept_all_count || 0}
                    <span className="text-sm font-normal text-gray-500 ml-1">
                      ({calcPercent(stats?.kpis?.accept_all_count, totalActions)})
                    </span>
                  </p>
                  <p className="text-xs text-gray-500">Accept All</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card 
            className={cn("cursor-pointer hover:border-red-300 transition-colors", actionFilter === 'REJECT_NON_ESSENTIAL' && "border-red-500")}
            onClick={() => setActionFilter(actionFilter === 'REJECT_NON_ESSENTIAL' ? 'all' : 'REJECT_NON_ESSENTIAL')}
          >
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-red-100 rounded-lg">
                  <XCircle className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">
                    {stats?.kpis?.reject_count || 0}
                    <span className="text-sm font-normal text-gray-500 ml-1">
                      ({calcPercent(stats?.kpis?.reject_count, totalActions)})
                    </span>
                  </p>
                  <p className="text-xs text-gray-500">Reject Non-Essential</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card 
            className={cn("cursor-pointer hover:border-blue-300 transition-colors", actionFilter === 'CUSTOM' && "border-blue-500")}
            onClick={() => setActionFilter(actionFilter === 'CUSTOM' ? 'all' : 'CUSTOM')}
          >
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <Settings className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">
                    {stats?.kpis?.custom_count || 0}
                    <span className="text-sm font-normal text-gray-500 ml-1">
                      ({calcPercent(stats?.kpis?.custom_count, totalActions)})
                    </span>
                  </p>
                  <p className="text-xs text-gray-500">Custom Preferences</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Category Breakdown + Trend */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <Card 
            className={cn("cursor-pointer hover:border-purple-300 transition-colors", analyticsFilter === 'allowed' && "border-purple-500")}
            onClick={() => setAnalyticsFilter(analyticsFilter === 'allowed' ? 'any' : 'allowed')}
          >
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-100 rounded-lg">
                  <BarChart3 className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">
                    {stats?.categories?.analytics_allowed_count || 0}
                    <span className="text-sm font-normal text-gray-500 ml-1">
                      ({calcPercent(stats?.categories?.analytics_allowed_count, totalActions)})
                    </span>
                  </p>
                  <p className="text-xs text-gray-500">Analytics Allowed</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card 
            className={cn("cursor-pointer hover:border-orange-300 transition-colors", marketingFilter === 'allowed' && "border-orange-500")}
            onClick={() => setMarketingFilter(marketingFilter === 'allowed' ? 'any' : 'allowed')}
          >
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-orange-100 rounded-lg">
                  <Target className="w-5 h-5 text-orange-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">
                    {stats?.categories?.marketing_allowed_count || 0}
                    <span className="text-sm font-normal text-gray-500 ml-1">
                      ({calcPercent(stats?.categories?.marketing_allowed_count, totalActions)})
                    </span>
                  </p>
                  <p className="text-xs text-gray-500">Marketing Allowed</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card className="cursor-pointer hover:border-cyan-300 transition-colors">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-cyan-100 rounded-lg">
                  <Settings className="w-5 h-5 text-cyan-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">
                    {stats?.categories?.functional_allowed_count || 0}
                    <span className="text-sm font-normal text-gray-500 ml-1">
                      ({calcPercent(stats?.categories?.functional_allowed_count, totalActions)})
                    </span>
                  </p>
                  <p className="text-xs text-gray-500">Functional Allowed</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          {/* Mini Trend Chart */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs text-gray-500">Consent Trend</p>
                <Select value={trendMetric} onValueChange={setTrendMetric}>
                  <SelectTrigger className="h-6 w-24 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sessions">Sessions</SelectItem>
                    <SelectItem value="marketing">Marketing</SelectItem>
                    <SelectItem value="analytics">Analytics</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-end gap-1 h-12">
                {(stats?.trend || []).slice(-14).map((day, i) => {
                  const value = trendMetric === 'sessions' ? day.sessions :
                               trendMetric === 'marketing' ? day.marketing_allowed :
                               day.analytics_allowed;
                  const max = Math.max(...(stats?.trend || []).map(d => 
                    trendMetric === 'sessions' ? d.sessions :
                    trendMetric === 'marketing' ? d.marketing_allowed :
                    d.analytics_allowed
                  )) || 1;
                  const height = Math.max((value / max) * 100, 5);
                  return (
                    <div 
                      key={i}
                      className="flex-1 bg-teal-500 rounded-t"
                      style={{ height: `${height}%` }}
                      title={`${day.date}: ${value}`}
                    />
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Filters Panel */}
        <Card>
          <CardHeader 
            className="py-3 cursor-pointer"
            onClick={() => setShowFilters(!showFilters)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-2">
                <Filter className="w-4 h-4" />
                Filters
              </CardTitle>
              <ChevronDown className={cn("w-4 h-4 transition-transform", showFilters && "rotate-180")} />
            </div>
          </CardHeader>
          {showFilters && (
            <CardContent className="pt-0">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="text-xs text-gray-500">Action Taken</label>
                  <Select value={actionFilter} onValueChange={setActionFilter}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="ACCEPT_ALL">Accept All</SelectItem>
                      <SelectItem value="REJECT_NON_ESSENTIAL">Reject</SelectItem>
                      <SelectItem value="CUSTOM">Custom</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs text-gray-500">Marketing</label>
                  <Select value={marketingFilter} onValueChange={setMarketingFilter}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">Any</SelectItem>
                      <SelectItem value="allowed">Allowed</SelectItem>
                      <SelectItem value="not_allowed">Not Allowed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs text-gray-500">Analytics</label>
                  <Select value={analyticsFilter} onValueChange={setAnalyticsFilter}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">Any</SelectItem>
                      <SelectItem value="allowed">Allowed</SelectItem>
                      <SelectItem value="not_allowed">Not Allowed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs text-gray-500">User Type</label>
                  <Select value={userTypeFilter} onValueChange={setUserTypeFilter}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">Any</SelectItem>
                      <SelectItem value="anonymous">Anonymous</SelectItem>
                      <SelectItem value="logged_in">Logged In</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs text-gray-500">CRN (exact)</label>
                  <Input 
                    value={searchCrn}
                    onChange={(e) => setSearchCrn(e.target.value)}
                    placeholder="CRN..."
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Email (contains)</label>
                  <Input 
                    value={searchEmail}
                    onChange={(e) => setSearchEmail(e.target.value)}
                    placeholder="Email..."
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Session ID (exact)</label>
                  <Input 
                    value={searchSession}
                    onChange={(e) => setSearchSession(e.target.value)}
                    placeholder="Session..."
                    className="mt-1"
                  />
                </div>
                <div className="flex items-end gap-2">
                  <Button onClick={fetchLogs} className="flex-1">
                    Apply
                  </Button>
                  <Button 
                    variant="outline"
                    onClick={() => {
                      setActionFilter('all');
                      setMarketingFilter('any');
                      setAnalyticsFilter('any');
                      setUserTypeFilter('any');
                      setSearchCrn('');
                      setSearchEmail('');
                      setSearchSession('');
                    }}
                  >
                    Clear
                  </Button>
                </div>
              </div>
            </CardContent>
          )}
        </Card>

        {/* Consent Log Table */}
        <Card>
          <CardHeader className="py-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Consent Log</CardTitle>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">
                  Showing {logs.length} of {total}
                </span>
                <Select value={String(pageSize)} onValueChange={(v) => setPageSize(Number(v))}>
                  <SelectTrigger className="w-20 h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="25">25</SelectItem>
                    <SelectItem value="50">50</SelectItem>
                    <SelectItem value="100">100</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="flex items-center justify-center h-48">
                <RefreshCw className="w-6 h-6 animate-spin text-teal-600" />
              </div>
            ) : logs.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-gray-500">
                <Cookie className="w-10 h-10 mb-2 text-gray-300" />
                <p>No consent records match these filters.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-y border-gray-200">
                    <tr>
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Action</th>
                      <th className="text-center px-4 py-2 text-xs font-medium text-gray-500 uppercase">Marketing</th>
                      <th className="text-center px-4 py-2 text-xs font-medium text-gray-500 uppercase">Analytics</th>
                      <th className="text-center px-4 py-2 text-xs font-medium text-gray-500 uppercase">Functional</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">User</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Session</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Country</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Page</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Version</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {logs.map((log) => (
                      <tr key={log.event_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-sm">
                          {formatTimestamp(log.created_at)}
                        </td>
                        <td className="px-4 py-2">
                          <Badge className={cn("text-xs", ACTION_COLORS[log.action_taken] || ACTION_COLORS.UNKNOWN)}>
                            {log.action_taken?.replace('_', ' ')}
                          </Badge>
                        </td>
                        <td className="px-4 py-2 text-center">
                          {log.preferences?.marketing ? (
                            <CheckCircle2 className="w-4 h-4 text-green-600 mx-auto" />
                          ) : (
                            <XCircle className="w-4 h-4 text-red-400 mx-auto" />
                          )}
                        </td>
                        <td className="px-4 py-2 text-center">
                          {log.preferences?.analytics ? (
                            <CheckCircle2 className="w-4 h-4 text-green-600 mx-auto" />
                          ) : (
                            <XCircle className="w-4 h-4 text-red-400 mx-auto" />
                          )}
                        </td>
                        <td className="px-4 py-2 text-center">
                          {log.preferences?.functional ? (
                            <CheckCircle2 className="w-4 h-4 text-green-600 mx-auto" />
                          ) : (
                            <XCircle className="w-4 h-4 text-red-400 mx-auto" />
                          )}
                        </td>
                        <td className="px-4 py-2 text-sm">
                          <span className={log.is_logged_in ? "text-gray-900" : "text-gray-400"}>
                            {log.user_display}
                          </span>
                        </td>
                        <td className="px-4 py-2">
                          <div className="flex items-center gap-1">
                            <span className="text-xs font-mono text-gray-500">
                              {log.session_id?.slice(0, 12)}...
                            </span>
                            <button 
                              onClick={() => copyToClipboard(log.session_id)}
                              className="text-gray-400 hover:text-gray-600"
                            >
                              <Copy className="w-3 h-3" />
                            </button>
                          </div>
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-500">
                          {log.country || '-'}
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-500 max-w-[100px] truncate">
                          {log.page_path || '-'}
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-500">
                          {log.consent_version}
                        </td>
                        <td className="px-4 py-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => fetchDetail(log.event_id)}
                          >
                            <Eye className="w-4 h-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            
            {/* Pagination */}
            {total > pageSize && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200">
                <span className="text-sm text-gray-500">
                  Page {page} of {Math.ceil(total / pageSize)}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(p => Math.min(Math.ceil(total / pageSize), p + 1))}
                    disabled={page >= Math.ceil(total / pageSize)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Detail Drawer */}
        <Dialog open={!!selectedRecord} onOpenChange={() => setSelectedRecord(null)}>
          <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-teal-600" />
                Consent Record Details
              </DialogTitle>
            </DialogHeader>
            
            {detailLoading ? (
              <div className="flex items-center justify-center h-48">
                <RefreshCw className="w-6 h-6 animate-spin text-teal-600" />
              </div>
            ) : detailData ? (
              <div className="space-y-4">
                {/* Consent Snapshot */}
                <div>
                  <h4 className="text-sm font-semibold text-gray-900 mb-2">Consent Snapshot</h4>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="text-gray-500">Event ID:</div>
                    <div className="font-mono text-xs">{detailData.event_id}</div>
                    <div className="text-gray-500">Session ID:</div>
                    <div className="font-mono text-xs flex items-center gap-1">
                      {detailData.session_id?.slice(0, 20)}...
                      <button onClick={() => copyToClipboard(detailData.session_id)}>
                        <Copy className="w-3 h-3 text-gray-400" />
                      </button>
                    </div>
                    {detailData.crn && (
                      <>
                        <div className="text-gray-500">CRN:</div>
                        <div className="font-mono">{detailData.crn}</div>
                      </>
                    )}
                    <div className="text-gray-500">Action:</div>
                    <div>
                      <Badge className={ACTION_COLORS[detailData.action_taken] || ACTION_COLORS.UNKNOWN}>
                        {detailData.action_taken?.replace('_', ' ')}
                      </Badge>
                    </div>
                    <div className="text-gray-500">Created:</div>
                    <div>{formatTimestamp(detailData.created_at)}</div>
                    {detailData.updated_at && (
                      <>
                        <div className="text-gray-500">Updated:</div>
                        <div>{formatTimestamp(detailData.updated_at)}</div>
                      </>
                    )}
                    <div className="text-gray-500">Version:</div>
                    <div>{detailData.consent_version}</div>
                  </div>
                  
                  {/* Preferences */}
                  <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                    <div className="grid grid-cols-4 gap-2 text-center">
                      <div>
                        <Shield className="w-4 h-4 mx-auto text-gray-600" />
                        <span className="text-xs text-gray-500 block">Necessary</span>
                        <CheckCircle2 className="w-4 h-4 mx-auto text-green-600" />
                      </div>
                      <div>
                        <Settings className="w-4 h-4 mx-auto text-gray-600" />
                        <span className="text-xs text-gray-500 block">Functional</span>
                        {detailData.preferences?.functional ? (
                          <CheckCircle2 className="w-4 h-4 mx-auto text-green-600" />
                        ) : (
                          <XCircle className="w-4 h-4 mx-auto text-red-400" />
                        )}
                      </div>
                      <div>
                        <BarChart3 className="w-4 h-4 mx-auto text-gray-600" />
                        <span className="text-xs text-gray-500 block">Analytics</span>
                        {detailData.preferences?.analytics ? (
                          <CheckCircle2 className="w-4 h-4 mx-auto text-green-600" />
                        ) : (
                          <XCircle className="w-4 h-4 mx-auto text-red-400" />
                        )}
                      </div>
                      <div>
                        <Target className="w-4 h-4 mx-auto text-gray-600" />
                        <span className="text-xs text-gray-500 block">Marketing</span>
                        {detailData.preferences?.marketing ? (
                          <CheckCircle2 className="w-4 h-4 mx-auto text-green-600" />
                        ) : (
                          <XCircle className="w-4 h-4 mx-auto text-red-400" />
                        )}
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Context */}
                <div>
                  <h4 className="text-sm font-semibold text-gray-900 mb-2">Context</h4>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="text-gray-500">Page:</div>
                    <div>{detailData.page_path || '-'}</div>
                    <div className="text-gray-500">Referrer:</div>
                    <div className="truncate">{detailData.referrer || '-'}</div>
                    <div className="text-gray-500">Country:</div>
                    <div>{detailData.country || '-'}</div>
                    {detailData.utm && (
                      <>
                        <div className="text-gray-500">UTM Source:</div>
                        <div>{detailData.utm.source || '-'}</div>
                      </>
                    )}
                  </div>
                </div>
                
                {/* Outreach Eligibility */}
                <div className="p-3 rounded-lg border border-gray-200">
                  <div className="flex items-center gap-2">
                    <Target className="w-4 h-4 text-gray-600" />
                    <span className="text-sm font-medium">Outreach Eligibility:</span>
                    {detailData.outreach_eligible ? (
                      <Badge className="bg-green-100 text-green-800">Eligible</Badge>
                    ) : (
                      <Badge className="bg-red-100 text-red-800">Do Not Market</Badge>
                    )}
                  </div>
                </div>
                
                {/* Timeline */}
                {detailData.timeline && detailData.timeline.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-900 mb-2">Timeline</h4>
                    <div className="space-y-2">
                      {detailData.timeline.map((event, i) => (
                        <div key={i} className="flex items-center gap-2 text-sm">
                          <div className="w-2 h-2 rounded-full bg-teal-500" />
                          <span className="text-gray-500">{formatTimestamp(event.created_at)}</span>
                          <Badge variant="outline" className="text-xs">
                            {event.event_type?.replace('_', ' ')}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </DialogContent>
        </Dialog>
      </div>
    </UnifiedAdminLayout>
  );
}
