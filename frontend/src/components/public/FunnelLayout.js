import React from 'react';
import { Link } from 'react-router-dom';

/**
 * Minimal layout for conversion funnels (e.g. /risk-check).
 * No full marketing navbar, no footer. Top bar: logo (left), "Back to Home" (right).
 * Centered content area for step indicator and form.
 */
const FunnelLayout = ({ children, className = '' }) => {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <header className="border-b border-gray-200 sticky top-0 z-50 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 flex justify-between items-center h-14">
          <Link to="/" className="flex items-center" data-testid="funnel-logo">
            <img src="/pleerity-logo.jpg" alt="Pleerity" className="h-8 w-auto" />
          </Link>
          <Link
            to="/"
            className="text-sm text-gray-600 hover:text-midnight-blue"
            data-testid="funnel-back-home"
          >
            Back to Home
          </Link>
        </div>
      </header>
      <main className={`flex-1 ${className}`}>
        {children}
      </main>
    </div>
  );
};

export default FunnelLayout;
