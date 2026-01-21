import React from 'react';

/**
 * Sparkline Chart Component
 * A minimal, SVG-based sparkline for displaying score trends.
 * 
 * Props:
 * - data: Array of numbers (scores)
 * - width: Chart width (default 120)
 * - height: Chart height (default 32)
 * - color: Line/fill color (default electric-teal)
 * - showArea: Fill area under line (default true)
 * - showDots: Show data point dots (default false)
 * - trendDirection: 'up' | 'down' | 'stable' | 'neutral'
 */
const Sparkline = ({ 
  data = [], 
  width = 120, 
  height = 32, 
  color = '#00B8A9',
  showArea = true,
  showDots = false,
  trendDirection = 'neutral',
  className = ''
}) => {
  if (!data || data.length < 2) {
    return (
      <div 
        className={`flex items-center justify-center text-xs text-gray-400 ${className}`}
        style={{ width, height }}
      >
        No trend data
      </div>
    );
  }

  // Calculate min/max for scaling
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1; // Avoid division by zero
  
  // Add padding to the range
  const paddedMin = min - range * 0.1;
  const paddedMax = max + range * 0.1;
  const paddedRange = paddedMax - paddedMin;

  // Calculate points
  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = height - ((value - paddedMin) / paddedRange) * height;
    return { x, y, value };
  });

  // Create SVG path
  const linePath = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(' ');

  // Create area path (closed shape)
  const areaPath = `${linePath} L ${width} ${height} L 0 ${height} Z`;

  // Determine color based on trend
  const trendColors = {
    up: '#22c55e',      // green-500
    down: '#ef4444',    // red-500
    stable: '#00B8A9',  // electric-teal
    neutral: '#9ca3af'  // gray-400
  };
  
  const effectiveColor = trendColors[trendDirection] || color;

  return (
    <svg 
      width={width} 
      height={height} 
      className={className}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
    >
      {/* Gradient definition for area fill */}
      <defs>
        <linearGradient id={`sparkline-gradient-${trendDirection}`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={effectiveColor} stopOpacity="0.3" />
          <stop offset="100%" stopColor={effectiveColor} stopOpacity="0.05" />
        </linearGradient>
      </defs>

      {/* Area fill */}
      {showArea && (
        <path
          d={areaPath}
          fill={`url(#sparkline-gradient-${trendDirection})`}
        />
      )}

      {/* Line */}
      <path
        d={linePath}
        fill="none"
        stroke={effectiveColor}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Data point dots */}
      {showDots && points.map((point, index) => (
        <circle
          key={index}
          cx={point.x}
          cy={point.y}
          r={2}
          fill={effectiveColor}
        />
      ))}

      {/* End point indicator */}
      <circle
        cx={points[points.length - 1].x}
        cy={points[points.length - 1].y}
        r={3}
        fill={effectiveColor}
      />
    </svg>
  );
};

export default Sparkline;
