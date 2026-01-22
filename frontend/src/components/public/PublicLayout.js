import React from 'react';
import PublicHeader from './PublicHeader';
import PublicFooter from './PublicFooter';

/**
 * PublicLayout - Wrapper component for all public-facing pages
 * Provides consistent header, footer, and page structure
 */
const PublicLayout = ({ children, className = '' }) => {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <PublicHeader />
      <main className={`flex-1 ${className}`}>
        {children}
      </main>
      <PublicFooter />
    </div>
  );
};

export default PublicLayout;
