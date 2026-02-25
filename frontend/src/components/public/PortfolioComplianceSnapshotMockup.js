import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../ui/button';

/**
 * Hero mockup: "Compliance Score (Example Preview)" for risk-first homepage.
 * Static, no API calls. Task: 62%, risk label, 3 sample alerts, compliance-safe footer.
 * CTA "Generate My Risk Report" → /risk-check.
 */
const SAMPLE_ALERTS = [
  'Gas Safety: due soon',
  'EICR: not confirmed',
  'Document vault: incomplete',
];

const PortfolioComplianceSnapshotMockup = () => {
  return (
    <div className="w-full max-w-md mx-auto" aria-label="Example compliance score preview">
      <div className="bg-white rounded-xl border border-gray-200 shadow-lg p-5">
        <h3 className="text-sm font-semibold text-midnight-blue mb-4">
          Compliance Score (Example Preview)
        </h3>
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl font-bold text-midnight-blue">62%</span>
          <span className="text-xs font-medium text-amber-700 bg-amber-50 px-2 py-1 rounded">
            Moderate–High
          </span>
        </div>
        <ul className="space-y-2 mb-4">
          {SAMPLE_ALERTS.map((alert) => (
            <li key={alert} className="text-xs text-gray-700 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
              {alert}
            </li>
          ))}
        </ul>
        <p className="text-[10px] text-gray-500 leading-snug">
          Example preview. Your score is generated from your inputs. This is not legal advice.
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
