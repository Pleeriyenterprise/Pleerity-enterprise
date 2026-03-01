/**
 * Score Trend (90 days) line chart with muted risk bands.
 * Single line, subtle grid, summary stats. Uses recharts.
 */
import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ResponsiveContainer,
} from 'recharts';

const RISK_BANDS = [
  { yMin: 0, yMax: 39, fill: 'rgba(185, 28, 28, 0.08)', label: 'Critical (0-39)' },
  { yMin: 40, yMax: 59, fill: 'rgba(180, 83, 9, 0.08)', label: 'At Risk (40-59)' },
  { yMin: 60, yMax: 79, fill: 'rgba(21, 128, 61, 0.08)', label: 'Moderate (60-79)' },
  { yMin: 80, yMax: 100, fill: 'rgba(21, 128, 61, 0.05)', label: 'Healthy (80-100)' },
];

const LINE_COLOR = '#0d9488'; // electric-teal
const CHART_HEIGHT = 220;

function formatDateShort(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

export default function ScoreTrendChart({ points = [], summary = {}, className = '' }) {
  const data = Array.isArray(points) ? points.map((p) => ({ ...p, dateLabel: formatDateShort(p.date) })) : [];
  const hasData = data.length > 0;
  const current = summary.current ?? (data.length ? data[data.length - 1].score : null);
  const delta30 = summary.delta_30;
  const best90 = summary.best_90;
  const worst90 = summary.worst_90;

  return (
    <div className={className}>
      {/* Summary stats row */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mb-3 text-sm">
        {current != null && (
          <span className="text-gray-700">
            Current: <strong>{current}</strong>
          </span>
        )}
        {delta30 != null && (
          <span className={delta30 >= 0 ? 'text-green-600' : 'text-red-600'}>
            {delta30 >= 0 ? '+' : ''}{delta30} in last 30 days
          </span>
        )}
        {best90 != null && (
          <span className="text-gray-600">Best in 90 days: {best90}</span>
        )}
        {worst90 != null && (
          <span className="text-gray-600">Worst in 90 days: {worst90}</span>
        )}
      </div>

      {/* Chart */}
      <div style={{ width: '100%', height: CHART_HEIGHT }}>
        {hasData ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
              <XAxis
                dataKey="dateLabel"
                tick={{ fontSize: 11, fill: '#6b7280' }}
                axisLine={{ stroke: '#e5e7eb' }}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 11, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
                width={28}
              />
              {RISK_BANDS.map((band, i) => (
                <ReferenceArea
                  key={i}
                  y1={band.yMin}
                  y2={band.yMax}
                  fill={band.fill}
                  strokeOpacity={0}
                />
              ))}
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload;
                  return (
                    <div className="bg-white border border-gray-200 rounded-lg shadow-sm px-3 py-2 text-sm">
                      <div className="text-gray-600">{p.date}</div>
                      <div className="font-medium text-gray-900">Score: {p.score}</div>
                    </div>
                  );
                }}
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke={LINE_COLOR}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: LINE_COLOR, stroke: '#fff', strokeWidth: 1 }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            No trend data yet
          </div>
        )}
      </div>

      {/* Legend */}
      {hasData && (
        <div className="flex flex-wrap gap-4 mt-2 pt-2 border-t border-gray-100">
          {RISK_BANDS.map((band, i) => (
            <span key={i} className="flex items-center gap-1.5 text-xs text-gray-500">
              <span
                className="w-3 h-3 rounded-sm shrink-0"
                style={{ backgroundColor: band.fill }}
              />
              {band.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
