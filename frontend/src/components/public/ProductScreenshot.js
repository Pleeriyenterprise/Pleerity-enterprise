import React from 'react';

/**
 * Wrapper for product screenshots on marketing pages.
 * Enterprise styling: border rgba(0,0,0,0.06), 16px radius, subtle shadow, white bg.
 */
const ProductScreenshot = ({ children, className = '' }) => (
  <div
    className={`rounded-2xl bg-white overflow-hidden ${className}`}
    style={{
      border: '1px solid rgba(0,0,0,0.06)',
      boxShadow: '0 1px 3px 0 rgba(0,0,0,0.08), 0 1px 2px -1px rgba(0,0,0,0.06)',
    }}
  >
    {children}
  </div>
);

export default ProductScreenshot;
