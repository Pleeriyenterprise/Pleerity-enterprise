import React from 'react';
import { Button } from '../ui/button';
import { Shield, Calendar, FileText } from 'lucide-react';

/**
 * Marketing dashboard preview: HTML/CSS mock of app dashboard (Portfolio Overview, Upcoming Expiries, Generate Report).
 * Used on homepage hero. Not an image — looks like the real app. Generate Report is disabled in preview.
 */
const DashboardPreview = () => {
  return (
    <div className="w-full max-w-md mx-auto space-y-4">
      {/* Portfolio Overview card */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 bg-electric-teal/10 rounded-lg flex items-center justify-center">
              <Shield className="w-5 h-5 text-electric-teal" />
            </div>
            <span className="font-semibold text-midnight-blue text-sm">Portfolio Overview</span>
          </div>
          <span className="text-lg font-bold text-electric-teal">78%</span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-amber-50 rounded-lg px-3 py-2 border border-amber-100">
            <span className="text-amber-700 font-medium">Expiring Soon</span>
            <p className="text-amber-800 font-bold mt-0.5">3</p>
          </div>
          <div className="bg-red-50 rounded-lg px-3 py-2 border border-red-100">
            <span className="text-red-700 font-medium">Overdue</span>
            <p className="text-red-800 font-bold mt-0.5">0</p>
          </div>
        </div>
      </div>

      {/* Upcoming Expiries mini list */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <Calendar className="w-4 h-4 text-electric-teal" />
          <span className="font-semibold text-midnight-blue text-sm">Upcoming Expiries</span>
        </div>
        <ul className="space-y-2">
          {[
            { label: 'Gas Safety – 12 Acacia Rd', days: '28 days' },
            { label: 'EICR – 12 Acacia Rd', days: '45 days' },
            { label: 'EPC – 8 Birch Lane', days: '90 days' },
          ].map((item, i) => (
            <li key={i} className="flex justify-between text-xs text-gray-600 py-1 border-b border-gray-50 last:border-0">
              <span className="truncate pr-2">{item.label}</span>
              <span className="text-amber-600 shrink-0">{item.days}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Generate Report button (disabled in preview) */}
      <Button
        disabled
        variant="outline"
        className="w-full border-gray-200 text-gray-400 cursor-not-allowed"
      >
        <FileText className="w-4 h-4 mr-2" />
        Generate Report
      </Button>

      <p className="text-xs text-gray-500 text-center px-2">
        Example preview. Your dashboard reflects your uploaded documents and confirmed dates.
      </p>
    </div>
  );
};

export default DashboardPreview;
