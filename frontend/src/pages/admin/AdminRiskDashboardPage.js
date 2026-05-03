/**
 * Admin Risk & Insights dashboard.
 * Replaces placeholder: aggregate risk signals, top properties/clients, counts by level/type, recent signals.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { AlertTriangle, Activity, Building2, Users, Loader2, RefreshCw, TrendingUp } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';
import {
  humanRiskType,
  humanSeverity,
  severityBadgeClass,
  humanAction,
  humanStatus,
  presentClientName,
  presentPropertyName,
  groupSignalsByProperty,
} from '../../utils/riskPresentation';

function formatDate(s) {
  if (!s) return '—';
  try {
    const d = typeof s === 'string' ? new Date(s) : s;
    return d.toLocaleDateString(undefined, { dateStyle: 'short' });
  } catch {
    return String(s);
  }
}

function LevelBadge({ level }) {
  const cls = severityBadgeClass(level);
  return <span className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${cls}`}>{humanSeverity(level)}</span>;
}

export default function AdminRiskDashboardPage() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [clients, setClients] = useState([]);
  const [clientFilter, setClientFilter] = useState('');
  const [riskLevelFilter, setRiskLevelFilter] = useState('');
  const [riskTypeFilter, setRiskTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const loadClients = useCallback(() => {
    adminAPI.getClients(0, 500).then((res) => {
      setClients(res.data?.clients || res.data?.items || []);
    }).catch(() => setClients([]));
  }, []);

  const loadSummary = useCallback(() => {
    setLoading(true);
    const params = { limit: 200 };
    if (clientFilter) params.client_id = clientFilter;
    if (riskLevelFilter) params.risk_level = riskLevelFilter;
    if (riskTypeFilter) params.risk_type = riskTypeFilter;
    if (statusFilter) params.status = statusFilter;
    adminAPI.getRiskSignalsSummary(params)
      .then((res) => setSummary(res.data))
      .catch(() => {
        setSummary(null);
        toast.error('Failed to load risk signals');
      })
      .finally(() => setLoading(false));
  }, [clientFilter, riskLevelFilter, riskTypeFilter, statusFilter]);

  useEffect(() => { loadClients(); }, [loadClients]);
  useEffect(() => { loadSummary(); }, [loadSummary]);

  const byLevel = summary?.byLevel || {};
  const byType = summary?.byType || {};
  const recent = summary?.recentSignals || [];
  const topProperties = summary?.topProperties || [];
  const topClients = summary?.topClients || [];
  const topComplianceRisks = summary?.topComplianceRisks || [];
  const topMaintenanceRisks = summary?.topMaintenanceRisks || [];
  const repeatedIssuesProperties = summary?.repeatedIssuesProperties || [];
  const slaBreachRisks = summary?.slaBreachRisks || [];
  const portfolioHeatmap = summary?.portfolioHeatmap || [];

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-6xl">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Activity className="w-7 h-7 text-electric-teal" />
              Risk & Insights
            </h1>
            <p className="text-gray-600 mt-1">Clear, grouped issues across your portfolio with practical next steps for each property.</p>
          </div>
          <Button variant="outline" onClick={loadSummary} disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <RefreshCw className="w-4 h-4 mr-2" />}
            Refresh
          </Button>
        </div>

        {/* Filters */}
        <Card className="mb-6">
          <CardContent className="pt-4">
            <div className="flex flex-wrap gap-3 items-center">
              <Select value={clientFilter || 'all'} onValueChange={(v) => setClientFilter(v === 'all' ? '' : v)}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="All clients" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All clients</SelectItem>
                  {clients.map((c) => (
                    <SelectItem key={c.client_id} value={c.client_id}>
                      {c.company_name || c.full_name || c.client_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={riskLevelFilter || 'all'} onValueChange={(v) => setRiskLevelFilter(v === 'all' ? '' : v)}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Risk level" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All levels</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="high">Urgent</SelectItem>
                  <SelectItem value="medium">Needs attention</SelectItem>
                  <SelectItem value="low">Monitor</SelectItem>
                </SelectContent>
              </Select>
              <Select value={statusFilter || 'all'} onValueChange={(v) => setStatusFilter(v === 'all' ? '' : v)}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="acknowledged">Acknowledged</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {loading ? (
          <div className="flex items-center justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-electric-teal" /></div>
        ) : !summary ? (
          <Card><CardContent className="py-8 text-center text-gray-500">No active risk issues yet. Once risk checks run, clear issue summaries will appear here.</CardContent></Card>
        ) : (
          <>
            {(() => {
              const grouped = groupSignalsByProperty(recent);
              const urgentCount = recent.filter((s) => ['critical', 'high'].includes((s.risk_level || '').toLowerCase())).length;
              const needsAttentionCount = recent.filter((s) => (s.risk_level || '').toLowerCase() === 'medium').length;
              const topAffected = grouped.slice(0, 3).map((g) => g.propertyName).filter(Boolean);
              return (
                <Card className="mb-6">
                  <CardHeader>
                    <CardTitle className="text-base">Decision summary</CardTitle>
                    <CardDescription>What needs attention right now</CardDescription>
                  </CardHeader>
                  <CardContent className="text-sm text-gray-700 space-y-1">
                    <p>{summary.totalActive ?? 0} active issues across {grouped.length} properties.</p>
                    <p>{urgentCount} urgent and {needsAttentionCount} needs-attention issues.</p>
                    <p>Most affected: {topAffected.length ? topAffected.join(', ') : 'No property concentration detected'}.</p>
                  </CardContent>
                </Card>
              );
            })()}
            {/* KPI row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-500">Active signals</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold text-midnight-blue">{summary.totalActive ?? 0}</p>
                  <p className="text-xs text-gray-500 mt-1">of {summary.totalSignals ?? 0} total</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-500 flex items-center gap-1"><AlertTriangle className="w-4 h-4" /> By priority</CardTitle>
                </CardHeader>
                <CardContent className="text-sm">
                  {Object.entries(byLevel).length ? (
                    <ul className="space-y-1">
                      {Object.entries(byLevel).map(([k, v]) => (
                          <li key={k}><LevelBadge level={k} /> {v}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-gray-500">—</p>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-500 flex items-center gap-1"><Building2 className="w-4 h-4" /> Top properties</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold text-midnight-blue">{topProperties.length}</p>
                  <p className="text-xs text-gray-500 mt-1">properties with signals</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-500 flex items-center gap-1"><Users className="w-4 h-4" /> Top clients</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold text-midnight-blue">{topClients.length}</p>
                  <p className="text-xs text-gray-500 mt-1">clients with signals</p>
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Issue categories</CardTitle>
                  <CardDescription>Counts by issue theme</CardDescription>
                </CardHeader>
                <CardContent>
                  {Object.entries(byType).length ? (
                    <ul className="space-y-2">
                      {Object.entries(byType)
                        .sort((a, b) => b[1] - a[1])
                        .map(([type, count]) => (
                          <li key={type} className="flex justify-between text-sm">
                            <span className="text-gray-700">{humanRiskType(type, 'admin')}</span>
                            <span className="font-medium">{count}</span>
                          </li>
                        ))}
                    </ul>
                  ) : (
                    <p className="text-gray-500 text-sm">No signals in this view.</p>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Top affected properties</CardTitle>
                  <CardDescription>By signal count</CardDescription>
                </CardHeader>
                <CardContent>
                  {topProperties.length ? (
                    <ul className="space-y-2">
                      {topProperties.slice(0, 10).map(({ property_id, property_name, count }) => (
                        <li key={property_id} className="flex justify-between text-sm">
                          <span className="text-gray-700 truncate max-w-[220px]" title={property_name || property_id}>{property_name || presentPropertyName({ property_name })}</span>
                          <span className="font-medium">{count}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-gray-500 text-sm">—</p>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Top compliance risks / Top maintenance risks / Repeated issues / SLA breach */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-700">Top compliance risks</CardTitle>
                  <CardDescription>Certificate expiry, churn</CardDescription>
                </CardHeader>
                <CardContent>
                  {topComplianceRisks.length ? (
                    <ul className="space-y-1.5 text-sm">
                      {topComplianceRisks.slice(0, 5).map((s) => (
                        <li key={s.signal_id} className="flex justify-between gap-2">
                          <span className="truncate text-gray-700" title={presentPropertyName(s)}>{humanRiskType(s, 'admin')}</span>
                          <LevelBadge level={s.risk_level} />
                        </li>
                      ))}
                    </ul>
                  ) : <p className="text-gray-500 text-sm">—</p>}
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-700">Top maintenance risks</CardTitle>
                  <CardDescription>Asset & operational</CardDescription>
                </CardHeader>
                <CardContent>
                  {topMaintenanceRisks.length ? (
                    <ul className="space-y-1.5 text-sm">
                      {topMaintenanceRisks.slice(0, 5).map((s) => (
                        <li key={s.signal_id} className="flex justify-between gap-2">
                          <span className="truncate text-gray-700">{humanRiskType(s, 'admin')}</span>
                          <LevelBadge level={s.risk_level} />
                        </li>
                      ))}
                    </ul>
                  ) : <p className="text-gray-500 text-sm">—</p>}
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-700">Properties with repeated issues</CardTitle>
                  <CardDescription>Recurring repairs risk</CardDescription>
                </CardHeader>
                <CardContent>
                  {repeatedIssuesProperties.length ? (
                    <ul className="space-y-1.5 text-sm">
                      {repeatedIssuesProperties.slice(0, 5).map(({ property_id, property_name, count }) => (
                        <li key={property_id} className="flex justify-between">
                          <span className="text-xs truncate max-w-[180px]" title={property_name || property_id}>{property_name || presentPropertyName({ property_name })}</span>
                          <span className="font-medium">{count}</span>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="text-gray-500 text-sm">—</p>}
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-700">Response time risks</CardTitle>
                  <CardDescription>Jobs past agreed response targets</CardDescription>
                </CardHeader>
                <CardContent>
                  {slaBreachRisks.length ? (
                    <ul className="space-y-1.5 text-sm">
                      {slaBreachRisks.slice(0, 5).map((s) => (
                        <li key={s.signal_id} className="flex justify-between gap-2">
                          <span className="truncate text-gray-700" title={presentPropertyName(s)}>{presentPropertyName(s)}</span>
                          <LevelBadge level={s.risk_level} />
                        </li>
                      ))}
                    </ul>
                  ) : <p className="text-gray-500 text-sm">—</p>}
                </CardContent>
              </Card>
            </div>

            {/* Portfolio risk heatmap */}
            {portfolioHeatmap.length > 0 && (
              <Card className="mb-6">
                <CardHeader>
                  <CardTitle className="text-base">Portfolio risk heatmap</CardTitle>
                  <CardDescription>Top properties by signal count (by severity)</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-gray-500">
                          <th className="py-2 pr-4">Property</th>
                          <th className="py-2 pr-4">Client</th>
                          <th className="py-2 pr-4 text-red-600">Urgent</th>
                          <th className="py-2 pr-4 text-orange-600">High</th>
                          <th className="py-2 pr-4 text-amber-600">Needs attention</th>
                          <th className="py-2">Low</th>
                        </tr>
                      </thead>
                      <tbody>
                        {portfolioHeatmap.slice(0, 20).map((row) => (
                          <tr key={row.property_id} className="border-b border-gray-100">
                            <td className="py-2 pr-4 text-xs truncate max-w-[180px]" title={presentPropertyName(row)}>{presentPropertyName(row)}</td>
                            <td className="py-2 pr-4 text-xs truncate max-w-[140px]" title={presentClientName(row)}>{presentClientName(row)}</td>
                            <td className="py-2 pr-4 font-medium">{row.critical ?? 0}</td>
                            <td className="py-2 pr-4 font-medium">{row.high ?? 0}</td>
                            <td className="py-2 pr-4">{row.medium ?? 0}</td>
                            <td className="py-2">{row.low ?? 0}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Recent issues</CardTitle>
                <CardDescription>Latest issues by property with plain-language actions</CardDescription>
              </CardHeader>
              <CardContent>
                {recent.length ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-gray-500">
                          <th className="py-2 pr-4">Property</th>
                          <th className="py-2 pr-4">Issue</th>
                          <th className="py-2 pr-4">Priority</th>
                          <th className="py-2 pr-4">Status</th>
                          <th className="py-2 pr-4">Generated</th>
                          <th className="py-2">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {recent.slice(0, 25).map((s) => (
                          <tr key={s.signal_id} className="border-b border-gray-100">
                            <td className="py-2 pr-4 text-xs truncate max-w-[160px]" title={presentPropertyName(s)}>{presentPropertyName(s)}</td>
                            <td className="py-2 pr-4">{humanRiskType(s, 'admin') || '—'}</td>
                            <td className="py-2 pr-4"><LevelBadge level={s.risk_level} /></td>
                            <td className="py-2 pr-4">{humanStatus(s.status)}</td>
                            <td className="py-2 pr-4">{formatDate(s.generated_at || s.updated_at)}</td>
                            <td className="py-2 text-gray-600 truncate max-w-[260px]" title={humanAction(s.recommended_action, s)}>{humanAction(s.recommended_action, s)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-gray-500 text-sm">No recent signals.</p>
                )}
              </CardContent>
            </Card>
          </>
        )}

        <div className="mt-6">
          <button type="button" onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/admin/ops'))} className="text-electric-teal hover:underline text-sm">
            ← Back to Ops
          </button>
        </div>
      </div>
    </UnifiedAdminLayout>
  );
}
