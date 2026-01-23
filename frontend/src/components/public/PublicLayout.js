import React from 'react';
import PublicHeader from './PublicHeader';
import PublicFooter from './PublicFooter';
import SupportChatWidget from '../SupportChatWidget';

/**
 * PublicLayout - Wrapper component for all public-facing pages
 * Provides consistent header, footer, and page structure
 * Includes AI support chat widget
 */
const PublicLayout = ({ children, className = '' }) => {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <PublicHeader />
      <main className={`flex-1 ${className}`}>
        {children}
      </main>
      <PublicFooter />
      <SupportChatWidget isAuthenticated={false} />
    </div>
  );
};

export default PublicLayout;
