import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '../ui/card';
import {
  hasLifecycleKpiBreakdown,
  lifecycleKpiBreakdownEntries,
  lifecycleKpiEffectiveMode,
} from '../../utils/lifecycleKpiBreakdown';

/**
 * Secondary lifecycle attention breakdown (P5-S4).
 * Shown when additive lifecycle_kpi_breakdown is present on compliance score stats.
 * Monolithic KPI tiles remain unchanged.
 */
export default function LifecycleKpiAttentionStrip({ stats, className = '' }) {
  const navigate = useNavigate();
  if (!hasLifecycleKpiBreakdown(stats)) return null;

  const entries = lifecycleKpiBreakdownEntries(stats);
  if (!entries.length) return null;

  const mode = lifecycleKpiEffectiveMode(stats);
  const modeHint =
    mode === 'shadow'
      ? 'Lifecycle attention breakdown (observe-only; headline counts remain legacy on staging).'
      : mode === 'active'
        ? 'Lifecycle attention breakdown (authoritative on preview).'
        : 'Lifecycle attention breakdown.';

  return (
    <Card className={`enterprise-card border-dashed border-amber-200 bg-amber-50/40 ${className}`} data-testid="lifecycle-kpi-attention-strip">
      <CardContent className="pt-4 pb-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-midnight-blue">Lifecycle attention breakdown</p>
            <p className="text-xs text-gray-600 mt-0.5">{modeHint}</p>
          </div>
          <button
            type="button"
            className="text-xs text-electric-teal hover:underline shrink-0"
            onClick={() => navigate('/requirements?status=DUE_SOON')}
          >
            View requirements →
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {entries.map((row) => (
            <span
              key={row.key}
              className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-white px-3 py-1 text-xs text-amber-900"
              data-testid={`lifecycle-kpi-bucket-${row.key}`}
            >
              <span className="font-semibold tabular-nums">{row.count}</span>
              <span>{row.label}</span>
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
