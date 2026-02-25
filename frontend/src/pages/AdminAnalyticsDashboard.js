/**
 * Admin Analytics Dashboard
 * Business intelligence and reporting for Pleerity Enterprise.
 * Shows revenue, orders, conversion funnels, SLA performance, and customer insights.
 * Enhanced with custom date ranges and period comparison (month-over-month)
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import {
  ArrowLeft, TrendingUp, TrendingDown, Minus, DollarSign,
  Package, Users, Clock, Target, Activity, BarChart3,
  RefreshCw, Calendar, Zap, Printer, Download, Filter
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '../components/ui/select';
import { toast } from 'sonner';
import client from '../api/client';

// Enhanced Stat card with trend indicator and previous value
function StatCard({ title, value, change, trend, icon: Icon, color = 'teal', previousValue }) {
  const colorClasses = {
    teal: 'bg-teal-100 text-teal-600',
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    purple: 'bg-purple-100 text-purple-600',
    amber: 'bg-amber-100 text-amber-600',
    indigo: 'bg-indigo-100 text-indigo-600',
    orange: 'bg-orange-100 text-orange-600',
  };
  
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
  const trendColor = trend === 'up' ? 'text-green-600' : trend === 'down' ? 'text-red-600' : 'text-gray-500';
  
  return (
    <Card data-testid={`stat-card-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
            <Icon className="h-5 w-5" />
          </div>
          {change !== undefined && change !== null && (
            <div className={`flex items-center gap-1 ${trendColor}`}>
              <TrendIcon className="h-4 w-4" />
              <span className="text-sm font-medium">{change > 0 ? '+' : ''}{change}%</span>
            </div>
          )}
        </div>
        <div className="mt-4">
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-gray-500">{title}</p>
          {previousValue !== null && previousValue !== undefined && (
            <p className="text-xs text-gray-400 mt-1">
              Previous: {previousValue}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// Simple bar for progress visualization
function ProgressBar({ value, max, color = 'teal' }) {
  const percent = max > 0 ? (value / max) * 100 : 0;
  const colorClasses = {
    teal: 'bg-teal-500',
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
  };
  
  return (
    <div className="w-full bg-gray-200 rounded-full h-2">
      <div 
        className={`h-2 rounded-full ${colorClasses[color]}`}
        style={{ width: `${Math.min(percent, 100)}%` }}
      />
    </div>
  );
}

// Funnel step component
function FunnelStep({ stage, count, rate, isLast }) {
  return (
    <div className="flex items-center">
      <div className="flex-1">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-medium text-gray-900">{stage}</span>
          <span className="text-sm text-gray-600">{count}</span>
        </div>
        <ProgressBar value={rate} max={100} color="teal" />
        <span className="text-xs text-gray-500">{rate}% conversion</span>
      </div>
      {!isLast && (
        <div className="mx-4 text-gray-400">→</div>
      )}
    </div>
  );
}

export default function AdminAnalyticsDashboard() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState('30d');
  const [loading, setLoading] = useState(true);
  const [compareEnabled, setCompareEnabled] = useState(true);
  const [customDateRange, setCustomDateRange] = useState({ start: '', end: '' });
  const [showCustomRange, setShowCustomRange] = useState(false);
  const [advancedSummary, setAdvancedSummary] = useState(null);
  const [trendData, setTrendData] = useState(null);
  const [breakdownData, setBreakdownData] = useState(null);
  const [breakdownDimension, setBreakdownDimension] = useState('service');
  const [data, setData] = useState({
    summary: null,
    services: null,
    sla: null,
    customers: null,
    funnel: null,
    addons: null,
    dailyRevenue: null,
  });
  const [conversionOverview, setConversionOverview] = useState(null);
  const [conversionFunnel, setConversionFunnel] = useState(null);
  const [conversionFailures, setConversionFailures] = useState(null);
  const [conversionSourceFilter, setConversionSourceFilter] = useState('');
  const [conversionPlanFilter, setConversionPlanFilter] = useState('');
  const [marketingFunnel, setMarketingFunnel] = useState(null);
  const [marketingRiskCheck, setMarketingRiskCheck] = useState(null);
  const [revenueAnalytics, setRevenueAnalytics] = useState(null);
  const [revenuePeriod, setRevenuePeriod] = useState('30d');
  const [revenueBreakdown, setRevenueBreakdown] = useState('all');
  
  // Build query params for API calls
  const getQueryParams = useCallback(() => {
    if (showCustomRange && customDateRange.start && customDateRange.end) {
      return `start_date=${customDateRange.start}&end_date=${customDateRange.end}&compare=${compareEnabled}`;
    }
    return `period=${period}&compare=${compareEnabled}`;
  }, [period, showCustomRange, customDateRange, compareEnabled]);
  
  // Fetch advanced analytics (v2 endpoints)
  const fetchAdvancedData = useCallback(async () => {
    try {
      const params = getQueryParams();
      const [summaryRes, trendRes, breakdownRes] = await Promise.all([
        client.get(`/admin/analytics/v2/summary?${params}`),
        client.get(`/admin/analytics/v2/trends?${params}&granularity=day&metrics=revenue,orders`),
        client.get(`/admin/analytics/v2/breakdown?${params}&dimension=${breakdownDimension}`),
      ]);
      
      setAdvancedSummary(summaryRes.data);
      setTrendData(trendRes.data);
      setBreakdownData(breakdownRes.data);
    } catch (error) {
      console.error('Failed to fetch advanced analytics:', error);
    }
  }, [getQueryParams, breakdownDimension]);
  
  const fetchAllData = useCallback(async () => {
    try {
      setLoading(true);
      
      const [summaryRes, servicesRes, slaRes, customersRes, funnelRes, addonsRes] = await Promise.all([
        client.get(`/admin/analytics/summary?period=${period}`),
        client.get(`/admin/analytics/services?period=${period}`),
        client.get(`/admin/analytics/sla-performance?period=${period}`),
        client.get(`/admin/analytics/customers?period=${period}`),
        client.get(`/admin/analytics/conversion-funnel?period=${period}`),
        client.get(`/admin/analytics/addons?period=${period}`),
      ]);
      
      setData({
        summary: summaryRes.data,
        services: servicesRes.data,
        sla: slaRes.data,
        customers: customersRes.data,
        funnel: funnelRes.data,
        addons: addonsRes.data,
      });
      const convParams = showCustomRange && customDateRange.start && customDateRange.end
        ? `from=${customDateRange.start}&to=${customDateRange.end}`
        : `period=${period}`;
      const sourceParam = conversionSourceFilter ? `&source=${encodeURIComponent(conversionSourceFilter)}` : '';
      const planParam = conversionPlanFilter ? `&plan=${encodeURIComponent(conversionPlanFilter)}` : '';
      try {
        const [overviewRes, funnelResConv, failuresRes, marketingFunnelRes, marketingRiskCheckRes] = await Promise.all([
          client.get(`/admin/analytics/overview?${convParams}${sourceParam}${planParam}`),
          client.get(`/admin/analytics/funnel?${convParams}${sourceParam}${planParam}`),
          client.get(`/admin/analytics/failures?${convParams}`),
          client.get(`/admin/analytics/marketing-funnel?${convParams}`).catch(() => ({ data: null })),
          client.get(`/admin/analytics/marketing?period=${period}`).catch(() => ({ data: null })),
        ]);
        setConversionOverview(overviewRes.data);
        setConversionFunnel(funnelResConv.data);
        setConversionFailures(failuresRes.data);
        setMarketingFunnel(marketingFunnelRes?.data ?? null);
        setMarketingRiskCheck(marketingRiskCheckRes?.data ?? null);
      } catch (convErr) {
        console.error('Conversion funnel fetch failed:', convErr);
        setConversionOverview(null);
        setConversionFunnel(null);
        setConversionFailures(null);
      }
      // Also fetch advanced data
      await fetchAdvancedData();
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
      toast.error('Failed to load analytics data');
    } finally {
      setLoading(false);
    }
  }, [period, fetchAdvancedData, showCustomRange, customDateRange, conversionSourceFilter, conversionPlanFilter]);
  
  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);
  
  const fetchRevenueOnly = useCallback(async () => {
    try {
      const res = await client.get(`/admin/analytics/revenue?period=${revenuePeriod}&breakdown=${revenueBreakdown}`);
      setRevenueAnalytics(res.data);
    } catch (e) {
      setRevenueAnalytics(null);
    }
  }, [revenuePeriod, revenueBreakdown]);
  
  useEffect(() => {
    fetchRevenueOnly();
  }, [fetchRevenueOnly]);
  
  // Refresh advanced data when compare or breakdown changes
  useEffect(() => {
    if (!loading) {
      fetchAdvancedData();
    }
  }, [compareEnabled, breakdownDimension, customDateRange, loading, fetchAdvancedData]);
  
  const { summary, services, sla, customers, funnel, addons } = data;
  
  // Handle custom date range apply
  const applyCustomRange = () => {
    if (customDateRange.start && customDateRange.end) {
      setShowCustomRange(true);
      fetchAllData();
    } else {
      toast.error('Please select both start and end dates');
    }
  };
  
  // Clear custom range
  const clearCustomRange = () => {
    setShowCustomRange(false);
    setCustomDateRange({ start: '', end: '' });
    fetchAllData();
  };
  
  return (
    <UnifiedAdminLayout>
    <div className="space-y-6" data-testid="admin-analytics-dashboard">
        {/* Header */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <BarChart3 className="h-6 w-6 text-blue-600" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">Analytics Dashboard</h1>
                  <p className="text-gray-500">
                    Business intelligence and performance metrics
                  </p>
                </div>
              </div>
              
              <div className="flex items-center gap-3">
                {/* Period Selector */}
                {!showCustomRange && (
                  <Select value={period} onValueChange={(v) => { setPeriod(v); setShowCustomRange(false); }}>
                    <SelectTrigger className="w-40" data-testid="period-selector">
                      <Calendar className="h-4 w-4 mr-2" />
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="today">Today</SelectItem>
                      <SelectItem value="7d">Last 7 Days</SelectItem>
                      <SelectItem value="30d">Last 30 Days</SelectItem>
                      <SelectItem value="90d">Last 90 Days</SelectItem>
                      <SelectItem value="ytd">Year to Date</SelectItem>
                      <SelectItem value="all">All Time</SelectItem>
                    </SelectContent>
                  </Select>
                )}
                
                {/* Custom Date Range */}
                <div className="flex items-center gap-2">
                  <input
                    type="date"
                    value={customDateRange.start}
                    onChange={(e) => setCustomDateRange({ ...customDateRange, start: e.target.value })}
                    className="px-3 py-2 border rounded-md text-sm"
                    data-testid="custom-start-date"
                  />
                  <span className="text-gray-400">to</span>
                  <input
                    type="date"
                    value={customDateRange.end}
                    onChange={(e) => setCustomDateRange({ ...customDateRange, end: e.target.value })}
                    className="px-3 py-2 border rounded-md text-sm"
                    data-testid="custom-end-date"
                  />
                  {!showCustomRange ? (
                    <Button size="sm" onClick={applyCustomRange} data-testid="apply-custom-range">
                      Apply
                    </Button>
                  ) : (
                    <Button size="sm" variant="outline" onClick={clearCustomRange}>
                      Clear
                    </Button>
                  )}
                </div>
                
                {/* Compare Toggle */}
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={compareEnabled}
                    onChange={(e) => setCompareEnabled(e.target.checked)}
                    className="w-4 h-4 rounded border-gray-300"
                  />
                  <span className="text-sm text-gray-600">Compare</span>
                </label>
                
                <Button 
                  variant="outline" 
                  onClick={fetchAllData}
                  disabled={loading}
                >
                  <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
              </div>
            </div>
            
            {/* Period Info Bar */}
            {advancedSummary?.period && (
              <div className="flex items-center gap-4 text-sm text-gray-500 bg-gray-50 px-4 py-2 rounded-lg">
                <span>
                  <strong>Current:</strong> {new Date(advancedSummary.period.current.start).toLocaleDateString()} - {new Date(advancedSummary.period.current.end).toLocaleDateString()}
                  ({advancedSummary.period.current.days} days)
                </span>
                {advancedSummary.period.comparison && (
                  <span className="text-gray-400">
                    <strong>vs Previous:</strong> {new Date(advancedSummary.period.comparison.start).toLocaleDateString()} - {new Date(advancedSummary.period.comparison.end).toLocaleDateString()}
                  </span>
                )}
              </div>
            )}
          </div>
        
        {loading && !summary ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto text-teal-500" />
              <p className="mt-2 text-gray-500">Loading analytics...</p>
            </div>
          </div>
        ) : (
          <>
            {/* Summary Stats with Comparison */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
              <StatCard
                title="Total Revenue"
                value={advancedSummary?.metrics?.revenue?.formatted || summary?.revenue?.total_formatted || '£0.00'}
                change={advancedSummary?.metrics?.revenue?.change_percent || summary?.revenue?.change_percent}
                trend={advancedSummary?.metrics?.revenue?.trend || summary?.revenue?.trend}
                icon={DollarSign}
                color="green"
                previousValue={advancedSummary?.metrics?.revenue?.previous ? `£${(advancedSummary.metrics.revenue.previous / 100).toFixed(2)}` : null}
              />
              <StatCard
                title="Paid Orders"
                value={advancedSummary?.metrics?.orders?.current || summary?.orders?.paid || 0}
                change={advancedSummary?.metrics?.orders?.change_percent || summary?.orders?.change_percent}
                trend={advancedSummary?.metrics?.orders?.trend || summary?.orders?.trend}
                icon={Package}
                color="blue"
                previousValue={advancedSummary?.metrics?.orders?.previous}
              />
              <StatCard
                title="Avg Order Value"
                value={advancedSummary?.metrics?.average_order_value?.formatted || summary?.average_order_value?.formatted || '£0.00'}
                change={advancedSummary?.metrics?.average_order_value?.change_percent}
                trend={advancedSummary?.metrics?.average_order_value?.trend}
                icon={TrendingUp}
                color="purple"
                previousValue={advancedSummary?.metrics?.average_order_value?.previous ? `£${(advancedSummary.metrics.average_order_value.previous / 100).toFixed(2)}` : null}
              />
              <StatCard
                title="New Clients"
                value={advancedSummary?.metrics?.new_clients?.current || summary?.new_clients || 0}
                change={advancedSummary?.metrics?.new_clients?.change_percent}
                trend={advancedSummary?.metrics?.new_clients?.trend}
                icon={Users}
                color="indigo"
                previousValue={advancedSummary?.metrics?.new_clients?.previous}
              />
              <StatCard
                title="Leads"
                value={advancedSummary?.metrics?.leads?.current || 0}
                change={advancedSummary?.metrics?.leads?.change_percent}
                trend={advancedSummary?.metrics?.leads?.trend}
                icon={Target}
                color="orange"
                previousValue={advancedSummary?.metrics?.leads?.previous}
              />
            </div>
            
            {/* Breakdown Section */}
            {breakdownData && (
              <Card className="mb-8">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base">Revenue Breakdown</CardTitle>
                      <CardDescription>Analyze by different dimensions</CardDescription>
                    </div>
                    <Select value={breakdownDimension} onValueChange={setBreakdownDimension}>
                      <SelectTrigger className="w-40">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="service">By Service</SelectItem>
                        <SelectItem value="status">By Status</SelectItem>
                        <SelectItem value="day_of_week">By Day of Week</SelectItem>
                        <SelectItem value="hour">By Hour</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </CardHeader>
                <CardContent>
                  {breakdownData.items?.length > 0 ? (
                    <div className="space-y-3">
                      {breakdownData.items.slice(0, 8).map((item, index) => (
                        <div key={item.key}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium text-gray-900">{item.label}</span>
                            <div className="flex items-center gap-3">
                              <Badge variant="secondary" className="text-xs">{item.count} orders</Badge>
                              <span className="text-sm font-semibold">{item.revenue_formatted}</span>
                              <span className="text-xs text-gray-500">({item.percentage}%)</span>
                            </div>
                          </div>
                          <ProgressBar value={item.revenue} max={breakdownData.items[0]?.revenue || 1} color={index === 0 ? 'teal' : 'blue'} />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-500 text-center py-4">No data for this breakdown</p>
                  )}
                </CardContent>
              </Card>
            )}
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              {/* Service Performance */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Activity className="h-5 w-5 text-teal-600" />
                    Service Performance
                  </CardTitle>
                  <CardDescription>Revenue by service type</CardDescription>
                </CardHeader>
                <CardContent>
                  {services?.services?.length > 0 ? (
                    <div className="space-y-4">
                      {services.services.slice(0, 6).map((service, index) => (
                        <div key={service.service_code}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium text-gray-900 truncate max-w-[200px]">
                              {service.service_name}
                            </span>
                            <div className="flex items-center gap-2">
                              <Badge variant="secondary" className="text-xs">
                                {service.orders} orders
                              </Badge>
                              <span className="text-sm font-semibold text-gray-900">
                                {service.revenue_formatted}
                              </span>
                            </div>
                          </div>
                          <ProgressBar 
                            value={service.revenue_pence} 
                            max={services.services[0]?.revenue_pence || 1}
                            color={index === 0 ? 'teal' : 'blue'}
                          />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-center text-gray-500 py-8">No service data yet</p>
                  )}
                </CardContent>
              </Card>
              
              {/* Conversion Funnel */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Target className="h-5 w-5 text-purple-600" />
                    Conversion Funnel
                  </CardTitle>
                  <CardDescription>From draft to completion</CardDescription>
                </CardHeader>
                <CardContent>
                  {funnel?.funnel?.length > 0 ? (
                    <div className="space-y-4">
                      {funnel.funnel.map((step, index) => (
                        <div key={step.stage}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium text-gray-900">{step.stage}</span>
                            <span className="text-sm text-gray-600">{step.count}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="flex-1">
                              <ProgressBar 
                                value={step.conversion_rate} 
                                max={100}
                                color={step.conversion_rate > 50 ? 'green' : step.conversion_rate > 25 ? 'amber' : 'red'}
                              />
                            </div>
                            <span className="text-xs text-gray-500 w-16 text-right">
                              {step.conversion_rate}%
                            </span>
                          </div>
                        </div>
                      ))}
                      <div className="pt-2 border-t">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold text-gray-900">Overall Conversion</span>
                          <span className="text-lg font-bold text-teal-600">
                            {funnel.overall_conversion}%
                          </span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-center text-gray-500 py-8">No funnel data yet</p>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Conversion Funnel (Lead to First Value) - event-based */}
            <Card className="mb-8">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Target className="h-5 w-5 text-indigo-600" />
                  Conversion Funnel (Lead to First Value)
                </CardTitle>
                <CardDescription>
                  Operational analytics only. Not legal or compliance advice.
                </CardDescription>
                <div className="flex flex-wrap gap-2 mt-2">
                  <input
                    type="text"
                    placeholder="Source filter"
                    value={conversionSourceFilter}
                    onChange={(e) => setConversionSourceFilter(e.target.value)}
                    className="px-2 py-1 border rounded text-sm w-36"
                  />
                  <select
                    value={conversionPlanFilter}
                    onChange={(e) => setConversionPlanFilter(e.target.value)}
                    className="px-2 py-1 border rounded text-sm"
                  >
                    <option value="">All plans</option>
                    <option value="PLAN_1_SOLO">Solo</option>
                    <option value="PLAN_2_PORTFOLIO">Portfolio</option>
                    <option value="PLAN_3_PRO">Pro</option>
                  </select>
                  <Button size="sm" onClick={fetchAllData}>Apply</Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                {conversionOverview && (
                  <>
                    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
                      <StatCard title="Leads" value={conversionOverview.kpis?.leads ?? 0} icon={Target} color="orange" />
                      <StatCard title="Intake Submitted" value={conversionOverview.kpis?.intake_submitted ?? 0} icon={Activity} color="blue" />
                      <StatCard title="Checkout Started" value={conversionOverview.kpis?.checkout_started ?? 0} icon={Zap} color="purple" />
                      <StatCard title="Paid" value={conversionOverview.kpis?.payment_succeeded ?? 0} icon={DollarSign} color="green" />
                      <StatCard title="Provisioned" value={conversionOverview.kpis?.provisioning_completed ?? 0} icon={Package} color="teal" />
                      <StatCard title="Activation Email" value={conversionOverview.kpis?.activation_email_sent ?? 0} icon={Activity} color="indigo" />
                      <StatCard title="Password Set" value={conversionOverview.kpis?.password_set ?? 0} icon={Users} color="amber" />
                      <StatCard title="First Value" value={conversionOverview.kpis?.first_doc_uploaded ?? 0} icon={TrendingUp} color="green" />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <p className="text-sm text-gray-600">
                        <strong>Median Paid → Provisioned:</strong>{' '}
                        {conversionOverview.median_seconds?.paid_to_provisioned != null
                          ? `${Math.round(conversionOverview.median_seconds.paid_to_provisioned / 60)}m`
                          : '—'}
                      </p>
                      <p className="text-sm text-gray-600">
                        <strong>Median Provisioned → Password Set:</strong>{' '}
                        {conversionOverview.median_seconds?.provisioned_to_password_set != null
                          ? `${Math.round(conversionOverview.median_seconds.provisioned_to_password_set / 60)}m`
                          : '—'}
                      </p>
                      <p className="text-sm text-gray-600">
                        <strong>Median Password Set → First Value:</strong>{' '}
                        {conversionOverview.median_seconds?.password_set_to_first_value != null
                          ? `${Math.round(conversionOverview.median_seconds.password_set_to_first_value / 60)}m`
                          : '—'}
                      </p>
                    </div>
                    {conversionOverview.leads_by_source?.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-gray-900 mb-2">Leads by source</h4>
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b"><th className="text-left py-1">Source</th><th className="text-right py-1">Count</th></tr>
                          </thead>
                          <tbody>
                            {conversionOverview.leads_by_source.map((row) => (
                              <tr key={row.source} className="border-b border-gray-100">
                                <td className="py-1">{row.source}</td>
                                <td className="text-right">{row.count}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </>
                )}
                {conversionFunnel?.funnel?.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-900 mb-2">Funnel stages</h4>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-1">Stage</th>
                          <th className="text-right py-1">Count</th>
                          <th className="text-right py-1">Step %</th>
                          <th className="text-right py-1">Drop-off</th>
                        </tr>
                      </thead>
                      <tbody>
                        {conversionFunnel.funnel.map((step) => (
                          <tr key={step.stage} className="border-b border-gray-100">
                            <td className="py-1">{step.stage}</td>
                            <td className="text-right">{step.count}</td>
                            <td className="text-right">{step.step_conversion_percent}%</td>
                            <td className="text-right">{step.drop_off_count} ({step.drop_off_percent}%)</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {conversionFailures?.events?.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-900 mb-2">Recent failures</h4>
                    <div className="max-h-48 overflow-auto border rounded text-sm">
                      <table className="w-full">
                        <thead className="bg-gray-50 sticky top-0">
                          <tr>
                            <th className="text-left py-1 px-2">Time</th>
                            <th className="text-left py-1 px-2">Event</th>
                            <th className="text-left py-1 px-2">Client</th>
                            <th className="text-left py-1 px-2">Error</th>
                            <th className="text-left py-1 px-2">Request ID</th>
                          </tr>
                        </thead>
                        <tbody>
                          {conversionFailures.events.slice(0, 20).map((ev, i) => (
                            <tr key={i} className="border-t">
                              <td className="py-1 px-2 text-gray-600">{ev.ts ? new Date(ev.ts).toLocaleString() : '—'}</td>
                              <td className="py-1 px-2">{ev.event}</td>
                              <td className="py-1 px-2">{ev.client_id || '—'}</td>
                              <td className="py-1 px-2">{ev.error_code || '—'}</td>
                              <td className="py-1 px-2">
                                {ev.request_id ? (
                                  <button
                                    type="button"
                                    className="text-indigo-600 underline"
                                    onClick={() => { navigator.clipboard.writeText(ev.request_id); toast.success('Copied'); }}
                                  >
                                    Copy
                                  </button>
                                ) : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                {!conversionOverview && !conversionFunnel && !loading && (
                  <p className="text-gray-500 text-center py-4">No conversion funnel data for this period. Data appears as events are logged.</p>
                )}
              </CardContent>
            </Card>

            {/* Marketing Funnel (Leads → Trial → Portal → Paid) */}
            <Card className="mb-8">
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Filter className="h-5 w-5 text-teal-600" />
                      Marketing Funnel
                    </CardTitle>
                    <CardDescription>Leads, trials, portal activation, and paid conversions</CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={async () => {
                      const params = showCustomRange && customDateRange.start && customDateRange.end
                        ? `from_date=${customDateRange.start}&to_date=${customDateRange.end}`
                        : `period=${period}`;
                      try {
                        const res = await client.get(`/admin/analytics/marketing-funnel/export?${params}`, { responseType: 'blob' });
                        const url = window.URL.createObjectURL(res.data);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'marketing_funnel.csv';
                        a.click();
                        window.URL.revokeObjectURL(url);
                      } catch (e) {
                        toast.error('Export failed');
                      }
                    }}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Export CSV
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {marketingFunnel ? (
                  <div className="space-y-6">
                    {/* KPI row */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                      <div className="rounded-lg border p-3 bg-gray-50">
                        <p className="text-xs text-gray-500">Visitors</p>
                        <p className="text-xl font-bold text-gray-700">{marketingFunnel.kpis?.visitors ?? '—'}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-blue-50">
                        <p className="text-xs text-gray-600">Leads</p>
                        <p className="text-xl font-bold text-blue-700">{marketingFunnel.kpis?.leads_count ?? 0}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-amber-50">
                        <p className="text-xs text-gray-600">Trials</p>
                        <p className="text-xl font-bold text-amber-700">{marketingFunnel.kpis?.trials_count ?? 0}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-green-50">
                        <p className="text-xs text-gray-600">Paid</p>
                        <p className="text-xl font-bold text-green-700">{marketingFunnel.kpis?.paid_count ?? 0}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-teal-50">
                        <p className="text-xs text-gray-600">Conversion %</p>
                        <p className="text-xl font-bold text-teal-700">{marketingFunnel.kpis?.conversion_rate ?? 0}%</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-gray-50">
                        <p className="text-xs text-gray-500">MRR</p>
                        <p className="text-xl font-bold text-gray-700">{marketingFunnel.kpis?.mrr != null ? marketingFunnel.kpis.mrr : '—'}</p>
                      </div>
                    </div>
                    {/* Funnel stages */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900 mb-2">Funnel</h4>
                      <div className="space-y-2">
                        {marketingFunnel.funnel?.map((step, idx) => (
                          <div key={step.stage} className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-medium text-gray-800 w-36">{step.stage}</span>
                            <span className="text-sm text-gray-600">{step.count}</span>
                            <ProgressBar value={step.conversion_rate} max={100} color="teal" />
                            <span className="text-xs text-gray-500">{step.conversion_rate}%</span>
                            {step.drop_off_percent > 0 && (
                              <span className="text-xs text-red-600">↓{step.drop_off_percent}%</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                    {/* Source attribution */}
                    {marketingFunnel.source_breakdown?.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-gray-900 mb-2">Lead source</h4>
                        <div className="overflow-x-auto border rounded">
                          <table className="w-full text-sm">
                            <thead className="bg-gray-50">
                              <tr>
                                <th className="text-left py-2 px-3">Source</th>
                                <th className="text-right py-2 px-3">Leads</th>
                                <th className="text-right py-2 px-3">Trials</th>
                                <th className="text-right py-2 px-3">Paid</th>
                                <th className="text-right py-2 px-3">Conv %</th>
                              </tr>
                            </thead>
                            <tbody>
                              {marketingFunnel.source_breakdown.map((row) => (
                                <tr key={row.source} className="border-t">
                                  <td className="py-2 px-3">{row.source}</td>
                                  <td className="text-right py-2 px-3">{row.leads}</td>
                                  <td className="text-right py-2 px-3">{row.trials}</td>
                                  <td className="text-right py-2 px-3">{row.paid}</td>
                                  <td className="text-right py-2 px-3">{row.conversion_percent}%</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                    {/* Conversion timing */}
                    <div className="flex flex-wrap gap-4 text-sm">
                      <span className="text-gray-600">
                        Avg days lead → trial: <strong>{marketingFunnel.conversion_timing?.avg_days_lead_to_trial ?? '—'}</strong>
                      </span>
                      <span className="text-gray-600">
                        Avg days trial → paid: <strong>{marketingFunnel.conversion_timing?.avg_days_trial_to_paid ?? '—'}</strong>
                      </span>
                    </div>
                  </div>
                ) : (
                  <p className="text-gray-500 text-center py-6">No marketing funnel data for this period.</p>
                )}
              </CardContent>
            </Card>

            {/* Risk Check Funnel (demo → paid conversion linking) */}
            {marketingRiskCheck && (
              <Card className="mb-8">
                <CardHeader>
                  <CardTitle className="text-base">Risk Check Funnel</CardTitle>
                  <CardDescription>
                    Leads from /risk-check: created → CTA clicked → checkout started → converted (period: {marketingRiskCheck.period || '30d'})
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                      <div className="rounded-lg border p-3 bg-gray-50">
                        <p className="text-xs text-gray-500">Leads created</p>
                        <p className="text-xl font-bold">{marketingRiskCheck.risk_check?.leads_created ?? 0}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-blue-50">
                        <p className="text-xs text-gray-600">Activated CTA</p>
                        <p className="text-xl font-bold text-blue-700">{marketingRiskCheck.risk_check?.activated_cta ?? 0}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-amber-50">
                        <p className="text-xs text-gray-600">Checkout created</p>
                        <p className="text-xl font-bold text-amber-700">{marketingRiskCheck.risk_check?.checkout_created ?? 0}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-green-50">
                        <p className="text-xs text-gray-600">Converted</p>
                        <p className="text-xl font-bold text-green-700">{marketingRiskCheck.risk_check?.converted ?? 0}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-teal-50">
                        <p className="text-xs text-gray-600">Conversion %</p>
                        <p className="text-xl font-bold text-teal-700">{marketingRiskCheck.risk_check?.conversion_rate ?? 0}%</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-teal-50">
                        <p className="text-xs text-gray-600">After CTA %</p>
                        <p className="text-xl font-bold text-teal-700">{marketingRiskCheck.risk_check?.conversion_rate_after_cta ?? 0}%</p>
                      </div>
                    </div>
                    {Array.isArray(marketingRiskCheck.latest_leads) && marketingRiskCheck.latest_leads.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-gray-900 mb-2">Latest risk-check leads</h4>
                        <div className="overflow-x-auto border rounded">
                          <table className="w-full text-sm">
                            <thead className="bg-gray-50">
                              <tr>
                                <th className="text-left p-2">Date</th>
                                <th className="text-left p-2">Lead ID</th>
                                <th className="text-left p-2">Name</th>
                                <th className="text-left p-2">Email</th>
                                <th className="text-left p-2">Status</th>
                                <th className="text-left p-2">Score</th>
                              </tr>
                            </thead>
                            <tbody>
                              {marketingRiskCheck.latest_leads.slice(0, 20).map((row) => (
                                <tr key={row.lead_id} className="border-t">
                                  <td className="p-2">{row.created_at ? new Date(row.created_at).toLocaleDateString() : '—'}</td>
                                  <td className="p-2 font-mono text-xs">{row.lead_id || '—'}</td>
                                  <td className="p-2">{row.first_name || '—'}</td>
                                  <td className="p-2">{row.email || '—'}</td>
                                  <td className="p-2">{row.status || '—'}</td>
                                  <td className="p-2">{row.computed_score ?? '—'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Revenue Analytics */}
            <Card className="mb-8">
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <DollarSign className="h-5 w-5 text-green-600" />
                      Revenue
                    </CardTitle>
                    <CardDescription>Revenue KPIs, MRR, subscribers, and payment health from normalized payments</CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Select value={revenuePeriod} onValueChange={setRevenuePeriod}>
                      <SelectTrigger className="w-32">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="7d">7 days</SelectItem>
                        <SelectItem value="30d">30 days</SelectItem>
                        <SelectItem value="90d">90 days</SelectItem>
                        <SelectItem value="12m">12 months</SelectItem>
                      </SelectContent>
                    </Select>
                    <Select value={revenueBreakdown} onValueChange={setRevenueBreakdown}>
                      <SelectTrigger className="w-32">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="recurring">Recurring</SelectItem>
                        <SelectItem value="one_time">One-time</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {revenueAnalytics ? (
                  <div className="space-y-6">
                    {/* KPI row */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                      <div className="rounded-lg border p-3 bg-gray-50">
                        <p className="text-xs text-gray-500">Total Revenue (Lifetime)</p>
                        <p className="text-lg font-bold text-gray-700">{revenueAnalytics.kpis?.total_revenue_lifetime_formatted ?? '£0.00'}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-blue-50">
                        <p className="text-xs text-gray-600">Revenue (Period)</p>
                        <p className="text-lg font-bold text-blue-700">{revenueAnalytics.kpis?.revenue_period_formatted ?? '£0.00'}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-teal-50">
                        <p className="text-xs text-gray-600">MRR</p>
                        <p className="text-lg font-bold text-teal-700">{revenueAnalytics.kpis?.mrr_formatted ?? '£0.00'}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-amber-50">
                        <p className="text-xs text-gray-600">Active Subscribers</p>
                        <p className="text-lg font-bold text-amber-700">{revenueAnalytics.kpis?.active_subscribers ?? 0}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-gray-50">
                        <p className="text-xs text-gray-500">Churn / Canceled</p>
                        <p className="text-lg font-bold text-gray-700">{revenueAnalytics.kpis?.churn_rate != null ? `${revenueAnalytics.kpis.churn_rate}%` : (revenueAnalytics.kpis?.canceled_subscribers ?? 0)}</p>
                      </div>
                      <div className="rounded-lg border p-3 bg-green-50">
                        <p className="text-xs text-gray-600">ARPU</p>
                        <p className="text-lg font-bold text-green-700">{revenueAnalytics.kpis?.arpu_formatted ?? '—'}</p>
                      </div>
                    </div>
                    {/* Revenue graph (time series) */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900 mb-2">Revenue over time</h4>
                      {revenueAnalytics.time_series?.length > 0 ? (
                        <div className="space-y-1 max-h-48 overflow-y-auto">
                          {(() => {
                            const series = revenueAnalytics.time_series;
                            const maxPence = Math.max(...series.map((x) => x.revenue_pence), 1);
                            return series.map((d) => {
                              const pct = (d.revenue_pence / maxPence) * 100;
                            return (
                              <div key={d.date} className="flex items-center gap-2 text-sm">
                                <span className="text-gray-600 w-24">{d.date}</span>
                                <div className="flex-1 bg-gray-200 rounded h-6 overflow-hidden">
                                  <div className="bg-teal-500 h-full rounded" style={{ width: `${pct}%` }} />
                                </div>
                                <span className="text-gray-700 w-20 text-right">{d.revenue_formatted}</span>
                              </div>
                            );
                            });
                          })()}
                        </div>
                      ) : (
                        <p className="text-gray-500 text-sm py-4">No revenue data for this period.</p>
                      )}
                    </div>
                    {/* Subscriber overview */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900 mb-2">Subscriber overview</h4>
                      <div className="overflow-x-auto border rounded">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="text-left py-2 px-3">Plan</th>
                              <th className="text-right py-2 px-3">Active</th>
                              <th className="text-right py-2 px-3">Cancelled</th>
                              <th className="text-right py-2 px-3">MRR contribution</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(revenueAnalytics.subscriber_breakdown || []).map((row) => (
                              <tr key={row.plan_code} className="border-t">
                                <td className="py-2 px-3">{row.plan_name}</td>
                                <td className="text-right py-2 px-3">{row.active}</td>
                                <td className="text-right py-2 px-3">{row.cancelled}</td>
                                <td className="text-right py-2 px-3">{row.mrr_contribution_formatted}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                    {/* Payment health */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900 mb-2">Payment health</h4>
                      <div className="flex flex-wrap gap-4 text-sm">
                        <span className="text-gray-600">Failed (last 30d): <strong className="text-red-600">{revenueAnalytics.payment_health?.failed_payments_last_30d ?? 0}</strong></span>
                        <span className="text-gray-600">Past due: <strong>{revenueAnalytics.payment_health?.past_due_accounts ?? 0}</strong></span>
                        <span className="text-gray-600">Refunds (last 30d): <strong>{revenueAnalytics.payment_health?.refunds_last_30d ?? 0}</strong></span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-gray-500 text-center py-6">No revenue data. Revenue is populated from Stripe webhooks (payments collection).</p>
                )}
              </CardContent>
            </Card>
            
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
              {/* SLA Performance */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Clock className="h-5 w-5 text-blue-600" />
                    SLA Performance
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-center mb-4">
                    <p className="text-4xl font-bold text-gray-900">
                      {sla?.health_score || 0}%
                    </p>
                    <p className="text-sm text-gray-500">Health Score</p>
                  </div>
                  
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">On Time</span>
                      <div className="flex items-center gap-2">
                        <Badge className="bg-green-100 text-green-700">
                          {sla?.on_time?.count || 0}
                        </Badge>
                        <span className="text-sm text-gray-900">{sla?.on_time?.percent || 0}%</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Warnings</span>
                      <div className="flex items-center gap-2">
                        <Badge className="bg-amber-100 text-amber-700">
                          {sla?.warnings_issued?.count || 0}
                        </Badge>
                        <span className="text-sm text-gray-900">{sla?.warnings_issued?.percent || 0}%</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Breached</span>
                      <div className="flex items-center gap-2">
                        <Badge className="bg-red-100 text-red-700">
                          {sla?.breached?.count || 0}
                        </Badge>
                        <span className="text-sm text-gray-900">{sla?.breached?.percent || 0}%</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              {/* Add-on Analytics */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Zap className="h-5 w-5 text-amber-600" />
                    Add-on Performance
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="p-3 bg-purple-50 rounded-lg">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Zap className="h-4 w-4 text-purple-600" />
                          <span className="font-medium text-gray-900">Fast Track</span>
                        </div>
                        <span className="font-semibold text-purple-600">
                          {addons?.fast_track?.revenue_formatted || '£0.00'}
                        </span>
                      </div>
                      <div className="mt-2 flex items-center justify-between text-sm">
                        <span className="text-gray-500">{addons?.fast_track?.count || 0} orders</span>
                        <span className="text-gray-600">{addons?.fast_track?.adoption_rate || 0}% adoption</span>
                      </div>
                    </div>
                    
                    <div className="p-3 bg-cyan-50 rounded-lg">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Printer className="h-4 w-4 text-cyan-600" />
                          <span className="font-medium text-gray-900">Printed Copy</span>
                        </div>
                        <span className="font-semibold text-cyan-600">
                          {addons?.printed_copy?.revenue_formatted || '£0.00'}
                        </span>
                      </div>
                      <div className="mt-2 flex items-center justify-between text-sm">
                        <span className="text-gray-500">{addons?.printed_copy?.count || 0} orders</span>
                        <span className="text-gray-600">{addons?.printed_copy?.adoption_rate || 0}% adoption</span>
                      </div>
                    </div>
                    
                    <div className="pt-2 border-t">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-gray-700">Total Add-on Revenue</span>
                        <span className="font-bold text-gray-900">
                          {addons?.total_addon_revenue?.formatted || '£0.00'}
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              {/* Customer Insights */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Users className="h-5 w-5 text-green-600" />
                    Customer Insights
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="text-center p-3 bg-gray-50 rounded-lg">
                      <p className="text-2xl font-bold text-gray-900">
                        {customers?.total_customers || 0}
                      </p>
                      <p className="text-xs text-gray-500">Total Customers</p>
                    </div>
                    <div className="text-center p-3 bg-gray-50 rounded-lg">
                      <p className="text-2xl font-bold text-gray-900">
                        {customers?.repeat_rate || 0}%
                      </p>
                      <p className="text-xs text-gray-500">Repeat Rate</p>
                    </div>
                  </div>
                  
                  {customers?.top_customers?.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 mb-2">Top Customers</p>
                      <div className="space-y-2">
                        {customers.top_customers.slice(0, 3).map((customer, index) => (
                          <div key={customer.email} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                              <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-700 flex items-center justify-center text-xs font-medium">
                                {index + 1}
                              </span>
                              <span className="text-gray-700 truncate max-w-[120px]">
                                {customer.name || customer.email.split('@')[0]}
                              </span>
                            </div>
                            <span className="font-medium text-gray-900">
                              {customer.total_spent_formatted}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
            
            {/* Order Status Breakdown */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Order Status Breakdown</CardTitle>
                <CardDescription>Current distribution of order statuses</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                  {summary?.status_breakdown && Object.entries(summary.status_breakdown).map(([status, count]) => (
                    <div key={status} className="text-center p-3 bg-gray-50 rounded-lg">
                      <p className="text-2xl font-bold text-gray-900">{count}</p>
                      <p className="text-xs text-gray-500">{status.replace(/_/g, ' ')}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </>
        )}
    </div>
    </UnifiedAdminLayout>
  );
}
