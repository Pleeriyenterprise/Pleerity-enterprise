/**
 * Executive Overview — investor-ready snapshot.
 * Admin → Analytics → Executive Overview.
 * Clean, minimal: MRR, ARR, Revenue YTD, SaaS health, revenue composition, 12-month trend.
 */
import React, { useState, useEffect, useCallback } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import client from '../api/client';

const DONUT_COLORS = ['#0f766e', '#0d9488', '#14b8a6', '#99f6e4', '#ccfbf1'];

function KpiCard({ title, value, changePct, trend }) {
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
  const trendColor = trend === 'up' ? 'text-green-600' : trend === 'down' ? 'text-red-600' : 'text-gray-500';
  return (
    <Card className="border-gray-200 bg-white">
      <CardContent className="p-6">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{title}</p>
        <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
        {changePct != null && (
          <div className={`mt-1 flex items-center gap-1 text-sm ${trendColor}`}>
            <TrendIcon className="h-4 w-4" />
            <span>{changePct > 0 ? '+' : ''}{changePct}% vs prior period</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function AdminExecutiveOverviewPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await client.get('/admin/analytics/executive-overview');
      setData(res.data);
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      if (status === 403) {
        setError('You don’t have permission to view Executive Overview. This page is available to Owner and Admin only.');
      } else {
        const msg = typeof detail === 'string' ? detail : (detail && typeof detail === 'object' && detail.message ? detail.message : null) || 'Failed to load executive overview';
        const statusInfo = status != null ? ` (${status})` : '';
        setError(msg + statusInfo);
      }
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading && !data) {
    return (
      <UnifiedAdminLayout>
        <div className="flex items-center justify-center min-h-[400px]">
          <p className="text-gray-500">Loading executive overview…</p>
        </div>
      </UnifiedAdminLayout>
    );
  }

  if (error) {
    return (
      <UnifiedAdminLayout>
        <div className="max-w-4xl mx-auto p-6">
          <p className="text-red-600">{error}</p>
          <button type="button" onClick={fetchData} className="mt-2 text-sm text-gray-600 underline">
            Retry
          </button>
        </div>
      </UnifiedAdminLayout>
    );
  }

  const r1 = data?.row1_core || {};
  const r2 = data?.row2_saas || {};
  const composition = data?.revenue_composition || [];
  const trend = data?.monthly_trend_12 || [];
  const subscriptionPerformance = data?.subscription_performance || [];
  const financialStability = data?.financial_stability || {};
  const riskIndicators = data?.risk_indicators || {};
  const valuationSnapshot = data?.valuation_snapshot || {};
  const growthEfficiency = data?.growth_efficiency || {};
  const totalComp = composition.reduce((s, c) => s + (c.value_pence || 0), 0);
  const maxTrend = Math.max(...trend.map((t) => t.total_pence || 0), 1);

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto p-6 space-y-8 bg-white">
        <header className="border-b border-gray-200 pb-6">
          <h1 className="text-xl font-semibold text-gray-900">Executive Overview</h1>
          <p className="mt-1 text-sm text-gray-500">
            Core financial and subscription health. Investor-ready snapshot.
          </p>
        </header>

        {/* Row 1 — Core Financial KPIs */}
        <section>
          <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide mb-4">Core financials</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard
              title="MRR"
              value={r1.mrr_formatted ?? '£0.00'}
              changePct={r1.change_revenue_month_pct}
              trend={r1.trend_mrr}
            />
            <KpiCard
              title="ARR"
              value={r1.arr_formatted ?? '£0.00'}
              changePct={r1.change_revenue_month_pct}
              trend={r1.trend_mrr}
            />
            <KpiCard
              title="Total revenue (YTD)"
              value={r1.revenue_ytd_formatted ?? '£0.00'}
              changePct={r1.change_revenue_ytd_pct}
              trend={r1.trend_revenue_ytd}
            />
            <Card className="border-gray-200 bg-white">
              <CardContent className="p-6">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Gross profit (YTD)</p>
                <p className="mt-1 text-2xl font-semibold text-gray-900">
                  {r1.gross_profit_ytd_formatted ?? '—'}
                </p>
                <p className="mt-1 text-xs text-gray-500">Revenue minus cost (cost_pence on payments when set)</p>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* Row 2 — SaaS health */}
        <section>
          <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide mb-4">SaaS health</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
            <Card className="border-gray-200 bg-white">
              <CardContent className="p-6">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Active subscribers</p>
                <p className="mt-1 text-2xl font-semibold text-gray-900">{r2.active_subscribers ?? 0}</p>
              </CardContent>
            </Card>
            <Card className="border-gray-200 bg-white">
              <CardContent className="p-6">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">New subscribers (30d)</p>
                <p className="mt-1 text-2xl font-semibold text-gray-900">{r2.new_subscribers_30d ?? 0}</p>
              </CardContent>
            </Card>
            <Card className="border-gray-200 bg-white">
              <CardContent className="p-6">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Churn rate</p>
                <p className="mt-1 text-2xl font-semibold text-gray-900">
                  {r2.churn_rate != null ? `${r2.churn_rate}%` : '—'}
                </p>
              </CardContent>
            </Card>
            <Card className="border-gray-200 bg-white">
              <CardContent className="p-6">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">NRR</p>
                <p className="mt-1 text-2xl font-semibold text-gray-900">{r2.nrr != null ? `${r2.nrr}%` : '—'}</p>
                {r2.nrr_note && (
                  <p className="mt-1 text-xs text-gray-500">{r2.nrr_note}</p>
                )}
              </CardContent>
            </Card>
            <Card className="border-gray-200 bg-white">
              <CardContent className="p-6">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">ARPU</p>
                <p className="mt-1 text-2xl font-semibold text-gray-900">{r2.arpu_formatted ?? '—'}</p>
              </CardContent>
            </Card>
            <Card className="border-gray-200 bg-white">
              <CardContent className="p-6">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">LTV (approx)</p>
                <p className="mt-1 text-2xl font-semibold text-gray-900">{r2.ltv_formatted ?? '—'}</p>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* Subscription performance */}
        <section>
          <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide mb-4">Subscription performance</h2>
          <Card className="border-gray-200 bg-white">
            <CardContent className="p-6">
              {subscriptionPerformance.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-2 pr-4 font-medium text-gray-700">Plan</th>
                        <th className="text-right py-2 px-4 font-medium text-gray-700">Active</th>
                        <th className="text-right py-2 px-4 font-medium text-gray-700">Trial</th>
                        <th className="text-right py-2 px-4 font-medium text-gray-700">Churned</th>
                        <th className="text-right py-2 px-4 font-medium text-gray-700">MRR</th>
                      </tr>
                    </thead>
                    <tbody>
                      {subscriptionPerformance.map((row) => (
                        <tr key={row.plan_code} className="border-b border-gray-100">
                          <td className="py-2 pr-4 text-gray-900">{row.plan_name}</td>
                          <td className="text-right py-2 px-4 text-gray-700">{row.active}</td>
                          <td className="text-right py-2 px-4 text-gray-700">{row.trial}</td>
                          <td className="text-right py-2 px-4 text-gray-700">{row.churned}</td>
                          <td className="text-right py-2 px-4 font-medium text-gray-900">{row.mrr_contribution_formatted}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No subscription data.</p>
              )}
            </CardContent>
          </Card>
        </section>

        {/* Revenue composition (donut) */}
        <section>
          <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide mb-4">Revenue breakdown</h2>
          <Card className="border-gray-200 bg-white">
            <CardContent className="p-6">
              {composition.length > 0 ? (
                <div className="flex flex-wrap items-start gap-8">
                  <div className="relative w-40 h-40 flex-shrink-0">
                    <svg className="w-40 h-40 transform -rotate-90" viewBox="0 0 100 100">
                      {composition.map((item, idx) => {
                        let cumulative = 0;
                        for (let i = 0; i < idx; i++) cumulative += totalComp ? (composition[i].value_pence / totalComp) * 100 : 0;
                        const percent = totalComp ? (item.value_pence / totalComp) * 100 : 0;
                        const dashArray = `${percent} ${100 - percent}`;
                        const dashOffset = -cumulative;
                        return (
                          <circle
                            key={item.label}
                            cx="50"
                            cy="50"
                            r="40"
                            fill="transparent"
                            stroke={DONUT_COLORS[idx % DONUT_COLORS.length]}
                            strokeWidth="20"
                            strokeDasharray={dashArray}
                            strokeDashoffset={dashOffset}
                          />
                        );
                      })}
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-lg font-semibold text-gray-700">
                        £{(totalComp / 100).toLocaleString('en-GB', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>
                  <div className="flex-1 min-w-[200px] space-y-2">
                    {composition.map((item, idx) => (
                      <div key={item.label} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-3 h-3 rounded-full flex-shrink-0"
                            style={{ backgroundColor: DONUT_COLORS[idx % DONUT_COLORS.length] }}
                          />
                          <span className="text-gray-700">{item.label}</span>
                        </div>
                        <span className="text-gray-900 font-medium">
                          £{(item.value_pence / 100).toLocaleString('en-GB', { minimumFractionDigits: 2 })} ({item.percent}%)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No revenue data for this period.</p>
              )}
            </CardContent>
          </Card>
        </section>

        {/* Monthly revenue trend (12 months) */}
        <section>
          <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide mb-4">Monthly revenue trend (12 months)</h2>
          <Card className="border-gray-200 bg-white">
            <CardContent className="p-6">
              {trend.length > 0 ? (
                <div className="space-y-3">
                  {trend.map((m) => (
                    <div key={m.month} className="flex items-center gap-4">
                      <span className="text-sm text-gray-600 w-20">{m.label}</span>
                      <div className="flex-1 h-8 bg-gray-100 rounded overflow-hidden flex">
                        <div
                          className="bg-teal-600"
                          style={{
                            width: `${(m.recurring_pence / maxTrend) * 100}%`,
                            minWidth: m.recurring_pence > 0 ? '2px' : 0,
                          }}
                          title={`Recurring: £${(m.recurring_pence / 100).toFixed(2)}`}
                        />
                        <div
                          className="bg-teal-400"
                          style={{
                            width: `${(m.one_time_pence / maxTrend) * 100}%`,
                            minWidth: m.one_time_pence > 0 ? '2px' : 0,
                          }}
                          title={`One-time: £${(m.one_time_pence / 100).toFixed(2)}`}
                        />
                      </div>
                      <span className="text-sm font-medium text-gray-900 w-24 text-right">
                        £{(m.total_pence / 100).toLocaleString('en-GB', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  ))}
                  <div className="flex gap-4 pt-2 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <span className="w-3 h-3 rounded bg-teal-600" /> Recurring
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-3 h-3 rounded bg-teal-400" /> One-time
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No trend data available.</p>
              )}
            </CardContent>
          </Card>
        </section>

        {/* Financial stability */}
        <section>
          <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide mb-4">Financial stability</h2>
          <Card className="border-gray-200 bg-white">
            <CardContent className="p-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Cash in (30d)</p>
                  <p className="mt-1 text-xl font-semibold text-gray-900">{financialStability.cash_in_30d_formatted ?? '£0.00'}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Failed payments (30d)</p>
                  <p className="mt-1 text-xl font-semibold text-red-600">{financialStability.failed_payments_30d ?? 0}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Refunds (30d)</p>
                  <p className="mt-1 text-xl font-semibold text-gray-900">{financialStability.refunds_30d ?? 0}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Past due accounts</p>
                  <p className="mt-1 text-xl font-semibold text-gray-900">{financialStability.past_due_accounts ?? 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* Risk indicators */}
        <section>
          <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide mb-4">Risk indicators</h2>
          <Card className="border-gray-200 bg-white">
            <CardContent className="p-6">
              <div className="flex flex-wrap items-center gap-6">
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Revenue from top 5 customers (YTD)</p>
                  <p className="mt-1 text-xl font-semibold text-gray-900">{riskIndicators.revenue_top5_pct != null ? `${riskIndicators.revenue_top5_pct}%` : '—'}</p>
                  <p className="mt-1 text-xs text-gray-500">High concentration may indicate dependency risk.</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* Growth efficiency */}
        <section>
          <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide mb-4">Growth efficiency</h2>
          <Card className="border-gray-200 bg-white">
            <CardContent className="p-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">Funnel (30d)</p>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Visitors</span>
                      <span className="font-medium text-gray-900">{growthEfficiency.visitors != null ? growthEfficiency.visitors : '—'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Leads</span>
                      <span className="font-medium text-gray-900">{growthEfficiency.leads_30d ?? 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Trials</span>
                      <span className="font-medium text-gray-900">{growthEfficiency.trials_30d ?? 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Paid</span>
                      <span className="font-medium text-gray-900">{growthEfficiency.paid ?? 0}</span>
                    </div>
                    <div className="flex justify-between border-t border-gray-100 pt-2 mt-2">
                      <span className="text-gray-600">Conversion %</span>
                      <span className="font-medium text-gray-900">{growthEfficiency.conversion_pct != null ? `${growthEfficiency.conversion_pct}%` : '—'}</span>
                    </div>
                  </div>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">Efficiency (when CAC available)</p>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Cost per lead</span>
                      <span className="font-medium text-gray-900">{growthEfficiency.cost_per_lead != null ? growthEfficiency.cost_per_lead : '—'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Cost per acquisition (CPA)</span>
                      <span className="font-medium text-gray-900">{growthEfficiency.cpa != null ? growthEfficiency.cpa : '—'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Payback period (months)</span>
                      <span className="font-medium text-gray-900">{growthEfficiency.payback_months != null ? growthEfficiency.payback_months : '—'}</span>
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-gray-500">Requires marketing spend / CAC tracking.</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* Valuation snapshot (admin only) */}
        <section>
          <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide mb-4">Valuation snapshot</h2>
          <Card className="border-gray-200 bg-white">
            <CardContent className="p-6">
              <p className="text-xs text-gray-500 mb-3">Confidential. Not for public display.</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">ARR</p>
                  <p className="mt-1 text-xl font-semibold text-gray-900">{valuationSnapshot.arr_formatted ?? '£0.00'}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Typical multiple (early-stage SaaS)</p>
                  <p className="mt-1 text-xl font-semibold text-gray-900">{valuationSnapshot.multiple_low != null ? `${valuationSnapshot.multiple_low}–${valuationSnapshot.multiple_high}x` : '—'}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Implied valuation range</p>
                  <p className="mt-1 text-xl font-semibold text-gray-900">{valuationSnapshot.implied_valuation_formatted ?? '—'}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </UnifiedAdminLayout>
  );
}
