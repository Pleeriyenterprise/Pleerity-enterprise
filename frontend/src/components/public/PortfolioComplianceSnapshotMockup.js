import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../ui/button';

/**
 * Hero mockup: "Portfolio Compliance Snapshot (Example)" for risk-first homepage.
 * Static, no API calls. Task: 62% horizontal bar, properties count, category breakdown with bars.
 * CTA "Generate My Risk Report" → /risk-check.
 */
const CATEGORIES = [
  { label: 'Gas Safety', value: 80, color: 'bg-emerald-500' },
  { label: 'Electrical (EICR)', value: 60, color: 'bg-amber-500' },
  { label: 'Licensing', value: 40, color: 'bg-red-500', badge: 'Review required' },
  { label: 'Document Coverage', value: 55, color: 'bg-amber-500' },
];

const PortfolioComplianceSnapshotMockup = () => {
  return (
    <div className="w-full max-w-md mx-auto" aria-label="Example portfolio compliance snapshot">
      <div className="bg-white rounded-xl border border-gray-200 shadow-lg p-5">
        <h3 className="text-sm font-semibold text-midnight-blue mb-4">
          Portfolio Compliance Snapshot (Example)
        </h3>

        {/* Compliance Score: 62% horizontal bar */}
        <div className="mb-4">
          <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
            <span>Compliance Score</span>
            <span className="font-semibold text-midnight-blue">62%</span>
          </div>
          <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-electric-teal rounded-full transition-all"
              style={{ width: '62%' }}
              aria-hidden
            />
          </div>
        </div>

        <p className="text-xs text-gray-700 mb-0.5">Properties monitored: 4</p>
        <p className="text-xs text-amber-700 font-medium mb-4">2 properties require attention</p>

        {/* Category breakdown with bars + rounded percentages */}
        <div className="space-y-3 mb-4">
          {CATEGORIES.map((cat) => (
            <div key={cat.label}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-700">{cat.label}</span>
                <span className="flex items-center gap-1.5">
                  <span className="font-medium text-gray-800">{cat.value}%</span>
                  {cat.badge && (
                    <span className="text-[10px] font-medium text-red-700 bg-red-50 px-1.5 py-0.5 rounded">
                      {cat.badge}
                    </span>
                  )}
                </span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full ${cat.color} rounded-full transition-all`}
                  style={{ width: `${cat.value}%` }}
                  aria-hidden
                />
              </div>
            </div>
          ))}
        </div>

        <p className="text-[10px] text-gray-500 leading-snug">
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
