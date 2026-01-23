/**
 * Admin Analytics Dashboard
 * Business intelligence and reporting for Pleerity Enterprise.
 * Shows revenue, orders, conversion funnels, SLA performance, and customer insights.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import {
  ArrowLeft, TrendingUp, TrendingDown, Minus, DollarSign,
  Package, Users, Clock, Target, Activity, BarChart3,
  RefreshCw, Calendar, Zap, Printer
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '../components/ui/select';
import { toast } from 'sonner';
import client from '../api/client';

// Stat card with trend indicator
function StatCard({ title, value, change, trend, icon: Icon, color = 'teal' }) {
  const colorClasses = {
    teal: 'bg-teal-100 text-teal-600',
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    purple: 'bg-purple-100 text-purple-600',
    amber: 'bg-amber-100 text-amber-600',
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
          {change !== undefined && (
            <div className={`flex items-center gap-1 ${trendColor}`}>
              <TrendIcon className="h-4 w-4" />
              <span className="text-sm font-medium">{Math.abs(change)}%</span>
            </div>
          )}
        </div>
        <div className="mt-4">
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-gray-500">{title}</p>
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
  const [data, setData] = useState({
    summary: null,
    services: null,
    sla: null,
    customers: null,
    funnel: null,
    addons: null,
    dailyRevenue: null,
  });
  
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
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
      toast.error('Failed to load analytics data');
    } finally {
      setLoading(false);
    }
  }, [period]);
  
  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);
  
  const { summary, services, sla, customers, funnel, addons } = data;
  
  return (
    <UnifiedAdminLayout>
    <div className="space-y-6" data-testid="admin-analytics-dashboard">
        {/* Header */}
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
            
            <div className="flex items-center gap-4">
              <Select value={period} onValueChange={setPeriod}>
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
            {/* Summary Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <StatCard
                title="Total Revenue"
                value={summary?.revenue?.total_formatted || '£0.00'}
                change={summary?.revenue?.change_percent}
                trend={summary?.revenue?.trend}
                icon={DollarSign}
                color="green"
              />
              <StatCard
                title="Paid Orders"
                value={summary?.orders?.paid || 0}
                change={summary?.orders?.change_percent}
                trend={summary?.orders?.trend}
                icon={Package}
                color="blue"
              />
              <StatCard
                title="Avg Order Value"
                value={summary?.average_order_value?.formatted || '£0.00'}
                change={summary?.average_order_value?.change_percent}
                trend={summary?.average_order_value?.change_percent > 0 ? 'up' : 'down'}
                icon={TrendingUp}
                color="purple"
              />
              <StatCard
                title="Completion Rate"
                value={`${summary?.completion_rate?.percent || 0}%`}
                icon={Target}
                color="teal"
              />
            </div>
            
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
