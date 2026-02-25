import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../ui/button';

/**
 * Hero mockup: "Portfolio Compliance Snapshot (Example)" for risk-first homepage.
 * Static, no API calls. Task: horizontal bar for score, properties count, category breakdown with bars.
 * Compliance-safe footer microtext; CTA "Generate My Risk Report" → /risk-check.
 */
const BAR_ITEMS = [
  { label: 'Gas Safety', pct: 80, color: 'bg-green-500' },
  { label: 'Electrical (EICR)', pct: 60, color: 'bg-amber-500' },
  { label: 'Licensing', pct: 40, color: 'bg-red-500', badge: 'Review required' },
  { label: 'Document Coverage', pct: 55, color: 'bg-amber-500' },
];

const PortfolioComplianceSnapshotMockup = () => {
  return (
    <div className="w-full max-w-md mx-auto">
      <div className="bg-white rounded-xl border border-gray-200 shadow-lg p-5">
        <h3 className="text-sm font-semibold text-midnight-blue mb-4">
          Portfolio Compliance Snapshot (Example)
        </h3>
        {/* Compliance Score: 62% horizontal bar */}
        <div className="mb-4">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-medium text-gray-600">Compliance Score</span>
            <span className="text-sm font-bold text-midnight-blue">62%</span>
          </div>
          <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-electric-teal rounded-full transition-all"
              style={{ width: '62%' }}
            />
          </div>
        </div>
        <div className="flex gap-4 text-xs text-gray-600 mb-4">
          <span>Properties monitored: <strong className="text-midnight-blue">4</strong></span>
          <span>2 properties require attention</span>
        </div>
        {/* Category breakdown with bars */}
        <div className="space-y-3">
          {BAR_ITEMS.map((item) => (
            <div key={item.label}>
              <div className="flex justify-between items-center mb-0.5">
                <span className="text-xs text-gray-700">{item.label}</span>
                <span className="flex items-center gap-1.5">
                  <span className="text-xs font-medium text-midnight-blue">{item.pct}%</span>
                  {item.badge && (
                    <span className="text-[10px] font-medium text-red-600 bg-red-50 px-1.5 py-0.5 rounded">
                      {item.badge}
                    </span>
                  )}
                </span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full ${item.color} rounded-full`}
                  style={{ width: `${item.pct}%` }}
                />
              </div>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-gray-500 mt-4 leading-snug">
          Illustrative portfolio example. Live score generated after assessment. Informational indicator only.
        </p>
      </div>
      <Button
        size="sm"
        className="w-full mt-3 bg-electric-teal hover:bg-electric-teal/90 text-white"
        asChild
      >
        <Link to="/risk-check">Generate My Risk Report</Link>
      </Button>
    </div>
  );
};

export default PortfolioComplianceSnapshotMockup;
