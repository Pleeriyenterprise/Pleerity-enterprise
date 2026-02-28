import React from 'react';

/**
 * Wrapper for product screenshots on marketing pages.
 * Flat, no rotation or animation. Enterprise styling.
 */
const ProductScreenshot = ({ children, className = '' }) => (
  <div
    className={`rounded-xl border border-gray-200 shadow-md bg-white overflow-hidden ${className}`}
  >
    {children}
  </div>
);

export default ProductScreenshot;
